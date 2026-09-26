# -*- coding: utf-8 -*-
"""Marchés dérivables des matrices de buts du modèle.

Aucun prix, aucune sélection et aucune estimation artificielle.
Les marchés qui nécessitent une donnée absente ne sont pas produits.
"""
from __future__ import annotations

from .statistical_model import ModelOutput


def _event(m, predicate):
    return sum(p for h, row in enumerate(m) for a, p in enumerate(row)
               if predicate(h, a))


def _ou(m, line):
    over = _event(m, lambda h, a: h + a > line)
    return over, 1.0 - over


def _team_ou(m, line, home=True):
    over = _event(m, (lambda h, a: h > line) if home
                  else (lambda h, a: a > line))
    return over, 1.0 - over


def _result(m):
    return (
        _event(m, lambda h, a: h > a),
        _event(m, lambda h, a: h == a),
        _event(m, lambda h, a: h < a),
    )


def _btts(m):
    yes = _event(m, lambda h, a: h >= 1 and a >= 1)
    return yes, 1.0 - yes


def _clean(m, home=True):
    return _event(m, (lambda h, a: a == 0) if home else (lambda h, a: h == 0))


def _exact_goals(m):
    out = {
        f"exact_goals_{n}": _event(m, lambda h, a, n=n: h + a == n)
        for n in range(6)
    }
    out["exact_goals_6_plus"] = _event(m, lambda h, a: h + a >= 6)
    return out


def _three_way_handicap(m, line):
    """BetPawa: Domicile -N / Nul -N / Extérieur +N.

    Le parseur normalise la ligne en entier positif N. Le règlement est donc
    comparé sur (buts domicile - N) contre buts extérieur.
    """
    if line < 0:
        raise ValueError("La ligne handicap doit être fournie en valeur positive")
    return (
        _event(m, lambda h, a: h - line > a),
        _event(m, lambda h, a: h - line == a),
        _event(m, lambda h, a: h - line < a),
    )


def _half_pair_markets(first, second):
    fh, fd, fa = _result(first)
    sh, sd, sa = _result(second)
    out = {}

    # Résultat de chaque mi-temps.
    out.update({
        "mi_temps_victoire": fh, "mi_temps_nul": fd, "mi_temps_defaite": fa,
        "2e_mi_temps_victoire": sh, "2e_mi_temps_nul": sd,
        "2e_mi_temps_defaite": sa,
    })

    # Double chance et BTTS de chaque mi-temps.
    out.update({
        "mi_temps_dc_1X": fh + fd, "mi_temps_dc_X2": fd + fa,
        "mi_temps_dc_12": fh + fa,
        "2e_mi_temps_dc_1X": sh + sd, "2e_mi_temps_dc_X2": sd + sa,
        "2e_mi_temps_dc_12": sh + sa,
    })
    fb, fn = _btts(first)
    sb, sn = _btts(second)
    out.update({
        "mi_temps_btts_oui": fb, "mi_temps_btts_non": fn,
        "2e_mi_temps_btts_oui": sb, "2e_mi_temps_btts_non": sn,
        "mi_temps_clean_sheet_dom": _clean(first, True),
        "mi_temps_clean_sheet_ext": _clean(first, False),
        "2e_mi_temps_clean_sheet_dom": _clean(second, True),
        "2e_mi_temps_clean_sheet_ext": _clean(second, False),
    })

    # Totaux de buts de chaque mi-temps.
    for x in range(6):
        o, u = _ou(first, x + 0.5)
        out[f"mi_temps_over_{x}_5"], out[f"mi_temps_under_{x}_5"] = o, u
        o, u = _ou(second, x + 0.5)
        out[f"2e_mi_temps_over_{x}_5"], out[f"2e_mi_temps_under_{x}_5"] = o, u

    # Marchés qui combinent les deux mi-temps. Ils utilisent l'indépendance
    # des deux matrices produites par le modèle; ils ne sont jamais produits
    # si une des deux matrices manque.
    out["htft_1_1"] = fh * sh
    out["htft_1_X"] = fh * sd
    out["htft_1_2"] = fh * sa
    out["htft_X_1"] = fd * sh
    out["htft_X_X"] = fd * sd
    out["htft_X_2"] = fd * sa
    out["htft_2_1"] = fa * sh
    out["htft_2_X"] = fa * sd
    out["htft_2_2"] = fa * sa

    # « gagne les deux mi-temps » et « gagne au moins une mi-temps ».
    out["dom_wins_both_halves"] = fh * sh
    out["ext_wins_both_halves"] = fa * sa
    out["dom_wins_at_least_one_half"] = 1.0 - (1.0 - fh) * (1.0 - sh)
    out["ext_wins_at_least_one_half"] = 1.0 - (1.0 - fa) * (1.0 - sa)

    # « marque dans les deux mi-temps » nécessite les probabilités de but
    # d'une équipe dans chaque matrice.
    dom_score_first = _event(first, lambda h, a: h >= 1)
    dom_score_second = _event(second, lambda h, a: h >= 1)
    ext_score_first = _event(first, lambda h, a: a >= 1)
    ext_score_second = _event(second, lambda h, a: a >= 1)
    out["dom_scores_both_halves"] = dom_score_first * dom_score_second
    out["ext_scores_both_halves"] = ext_score_first * ext_score_second

    # Mi-temps avec le plus de buts: comparaison des deux totaux sous
    # l'hypothèse d'indépendance des deux matrices.
    first_gt = second_gt = equal = 0.0
    for h1, r1 in enumerate(first):
        for a1, p1 in enumerate(r1):
            g1 = h1 + a1
            for h2, r2 in enumerate(second):
                for a2, p2 in enumerate(r2):
                    g2 = h2 + a2
                    p = p1 * r2[a2]
                    if g1 > g2:
                        first_gt += p
                    elif g1 < g2:
                        second_gt += p
                    else:
                        equal += p
    out["half_most_goals_first"] = first_gt
    out["half_most_goals_second"] = second_gt
    out["half_most_goals_equal"] = equal

    return out


def derive_goal_markets(model: ModelOutput, handicap_lines=()):
    m = model.score_matrix
    w, d, l = _result(m)
    out = {
        "victoire": w, "nul": d, "defaite": l,
        "dc_1X": w + d, "dc_X2": d + l, "dc_12": w + l,
    }

    by, bn = _btts(m)
    out.update({"btts_oui": by, "btts_non": bn})

    for x in range(6):
        o, u = _ou(m, x + 0.5)
        out[f"over_{x}_5"], out[f"under_{x}_5"] = o, u

    for x in (0, 1):
        o, u = _team_ou(m, x, True)
        out[f"buts_dom_over_{x}_5"], out[f"buts_dom_under_{x}_5"] = o, u
        o, u = _team_ou(m, x, False)
        out[f"buts_ext_over_{x}_5"], out[f"buts_ext_under_{x}_5"] = o, u

    out["clean_sheet_dom"] = _clean(m, True)
    out["clean_sheet_ext"] = _clean(m, False)
    out.update(_exact_goals(m))

    for line in handicap_lines:
        h, draw, ext = _three_way_handicap(m, float(line))
        n = int(line) if float(line).is_integer() else float(line)
        out[f"handicap_3way_{n:g}_dom"] = h
        out[f"handicap_3way_{n:g}_nul"] = draw
        out[f"handicap_3way_{n:g}_ext"] = ext

    if model.score_matrix_first_half is not None and model.score_matrix_second_half is not None:
        out.update(_half_pair_markets(
            model.score_matrix_first_half,
            model.score_matrix_second_half,
        ))

    # Corners/cartons ne sont volontairement pas inventés à partir des buts:
    # ils nécessitent leurs propres distributions historiques.
    return out
