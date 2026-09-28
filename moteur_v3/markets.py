from __future__ import annotations

from typing import Mapping


LIGNES_TOTAL = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5)
LIGNES_EQUIPE = (0.5, 1.5, 2.5, 3.5)
MAX_SCORE_EXACT = 4


def _event(matrix, predicate):
    return sum(p for h, row in enumerate(matrix) for a, p in enumerate(row) if predicate(h, a))


def _result(matrix):
    return (
        _event(matrix, lambda h, a: h > a),
        _event(matrix, lambda h, a: h == a),
        _event(matrix, lambda h, a: h < a),
    )


def _btts(matrix):
    yes = _event(matrix, lambda h, a: h > 0 and a > 0)
    return yes, 1.0 - yes


def _ou(matrix, line):
    over = _event(matrix, lambda h, a: h + a > line)
    return over, 1.0 - over


def _team_ou(matrix, line, home):
    over = _event(matrix, lambda h, a: (h if home else a) > line)
    return over, 1.0 - over


def _clean(matrix, home):
    return _event(matrix, lambda h, a: a == 0) if home else _event(matrix, lambda h, a: h == 0)


def _handicap(matrix, line):
    # La ligne est celle observée chez BetPawa : elle peut être négative ou positive.
    # Le calcul applique littéralement domicile - ligne face à extérieur, avec trois issues.
    return _result(tuple(
        tuple(p for p in row) for row in matrix
    )) if False else (
        _event(matrix, lambda h, a: h - line > a),
        _event(matrix, lambda h, a: h - line == a),
        _event(matrix, lambda h, a: h - line < a),
    )


def _half_convolution(first, second):
    # Joint distribution des scores mi-temps et fin de match.
    # On retourne les probabilités des 9 couples HT/FT, sans approximation
    # « résultat HT × résultat 2e mi-temps ».
    out = {(h1, a1, hf, af): 0.0 for h1 in range(len(first)) for a1 in range(len(first[h1]))
           for hf in range(3) for af in range(3)}
    # La grille ci-dessus n'est qu'un conteneur; les résultats sont agrégés
    # directement dans les 9 états utiles.
    states = {(r1, r2): 0.0 for r1 in "1X2" for r2 in "1X2"}
    for h1, row1 in enumerate(first):
        for a1, p1 in enumerate(row1):
            ht = "1" if h1 > a1 else "X" if h1 == a1 else "2"
            for h2, row2 in enumerate(second):
                for a2, p2 in enumerate(row2):
                    ft_h, ft_a = h1 + h2, a1 + a2
                    ft = "1" if ft_h > ft_a else "X" if ft_h == ft_a else "2"
                    states[(ht, ft)] += p1 * row2[a2]
    return states


def _half_markets(first, second, handicap_lines):
    out = {}
    fr, sr = _result(first), _result(second)

    out.update({
        "ht_1": fr[0], "ht_X": fr[1], "ht_2": fr[2],
        "2h_1": sr[0], "2h_X": sr[1], "2h_2": sr[2],
        "ht_dc_1X": fr[0] + fr[1], "ht_dc_X2": fr[1] + fr[2],
        "ht_dc_12": fr[0] + fr[2],
        "2h_dc_1X": sr[0] + sr[1], "2h_dc_X2": sr[1] + sr[2],
        "2h_dc_12": sr[0] + sr[2],
    })

    for prefix, matrix in (("ht", first), ("2h", second)):
        by, bn = _btts(matrix)
        out[f"{prefix}_btts_yes"], out[f"{prefix}_btts_no"] = by, bn
        for line in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5):
            o, u = _ou(matrix, line)
            out[f"{prefix}_over_{str(line).replace('.', '_')}"] = o
            out[f"{prefix}_under_{str(line).replace('.', '_')}"] = u
        for line in (0.5, 1.5):
            o, u = _team_ou(matrix, line, True)
            out[f"{prefix}_home_over_{str(line).replace('.', '_')}"] = o
            out[f"{prefix}_home_under_{str(line).replace('.', '_')}"] = u
            o, u = _team_ou(matrix, line, False)
            out[f"{prefix}_away_over_{str(line).replace('.', '_')}"] = o
            out[f"{prefix}_away_under_{str(line).replace('.', '_')}"] = u
        out[f"{prefix}_clean_home"] = _clean(matrix, True)
        out[f"{prefix}_clean_away"] = _clean(matrix, False)
        for line in handicap_lines:
            h, d, a = _handicap(matrix, float(line))
            token = f"{float(line):g}"
            out[f"{prefix}_handicap_{token}_1"] = h
            out[f"{prefix}_handicap_{token}_X"] = d
            out[f"{prefix}_handicap_{token}_2"] = a

    # Marque dans les deux mi-temps / gagne les deux / au moins une.
    for side, idx in (("home", 0), ("away", 1)):
        sf = _event(first, lambda h, a, idx=idx: (h, a)[idx] > 0)
        ss = _event(second, lambda h, a, idx=idx: (h, a)[idx] > 0)
        wf = fr[0] if side == "home" else fr[2]
        ws = sr[0] if side == "home" else sr[2]
        out[f"{side}_scores_both_halves"] = sf * ss
        out[f"{side}_wins_both_halves"] = wf * ws
        out[f"{side}_wins_at_least_one_half"] = 1 - (1 - wf) * (1 - ws)

    # Une seule distribution jointe permet de calculer HT/FT correctement.
    joint = _half_convolution(first, second)
    for ht in "1X2":
        for ft in "1X2":
            out[f"htft_{ht}_{ft}"] = joint[(ht, ft)]

    first_more = second_more = equal = 0.0
    for h1, row1 in enumerate(first):
        for a1, p1 in enumerate(row1):
            g1 = h1 + a1
            for h2, row2 in enumerate(second):
                for a2, p2 in enumerate(row2):
                    p = p1 * row2[a2]
                    g2 = h2 + a2
                    if g1 > g2:
                        first_more += p
                    elif g1 < g2:
                        second_more += p
                    else:
                        equal += p
    out["half_most_goals_first"] = first_more
    out["half_most_goals_second"] = second_more
    out["half_most_goals_equal"] = equal
    return out


def derive_markets(model, handicap_lines: Mapping[str, float] | list[float] | tuple[float, ...] = ()):
    m = model.score
    r = _result(m)
    out = {
        "1x2_1": r[0], "1x2_X": r[1], "1x2_2": r[2],
        "dc_1X": r[0] + r[1], "dc_X2": r[1] + r[2], "dc_12": r[0] + r[2],
    }

    by, bn = _btts(m)
    out["btts_yes"], out["btts_no"] = by, bn

    # AJOUT 28/09/2026 (Patrick : « intégrer le calcul de tous les marchés ») : lignes 6,5 et 7,5 cotées par BetPawa.
    for line in LIGNES_TOTAL:
        o, u = _ou(m, line)
        token = str(line).replace(".", "_")
        out[f"over_{token}"], out[f"under_{token}"] = o, u

    for line in LIGNES_EQUIPE:  # AJOUT 28/09/2026 : 2,5 et 3,5 buts d'une équipe
        token = str(line).replace(".", "_")
        o, u = _team_ou(m, line, True)
        out[f"home_over_{token}"], out[f"home_under_{token}"] = o, u
        o, u = _team_ou(m, line, False)
        out[f"away_over_{token}"], out[f"away_under_{token}"] = o, u

    out["clean_home"], out["clean_away"] = _clean(m, True), _clean(m, False)
    # AJOUT 28/09/2026 : compléments « encaisse au moins un but » (cotés par BetPawa).
    out["clean_home_no"], out["clean_away_no"] = 1.0 - out["clean_home"], 1.0 - out["clean_away"]
    # AJOUT 28/09/2026 : score exact (grille BetPawa 0-0 à 4-4) et parité du total de buts.
    for h in range(MAX_SCORE_EXACT + 1):
        for a in range(MAX_SCORE_EXACT + 1):
            out[f"score_{h}_{a}"] = m[h][a]
    out["total_pair"] = _event(m, lambda h, a: (h + a) % 2 == 0)
    out["total_impair"] = 1.0 - out["total_pair"]

    for n in range(6):
        out[f"exact_goals_{n}"] = _event(m, lambda h, a, n=n: h + a == n)
    out["exact_goals_6_plus"] = _event(m, lambda h, a: h + a >= 6)

    for line in handicap_lines:
        h, d, a = _handicap(m, float(line))
        token = f"{float(line):g}"
        out[f"handicap_{token}_1"] = h
        out[f"handicap_{token}_X"] = d
        out[f"handicap_{token}_2"] = a

    if model.first_score is not None and model.second_score is not None:
        out.update(_half_markets(model.first_score, model.second_score, handicap_lines))

    # Corners/cartons ne sont jamais dérivés des buts.
    return out


def _predicate_for_market(market):
    if market == "1x2_1":
        return lambda h, a: h > a
    if market == "1x2_X":
        return lambda h, a: h == a
    if market == "1x2_2":
        return lambda h, a: h < a
    if market == "dc_1X":
        return lambda h, a: h >= a
    if market == "dc_X2":
        return lambda h, a: h <= a
    if market == "dc_12":
        return lambda h, a: h != a
    if market == "btts_yes":
        return lambda h, a: h > 0 and a > 0
    if market == "btts_no":
        return lambda h, a: h == 0 or a == 0
    if market.startswith(("over_", "under_")):
        side, token = market.split("_", 1)
        line = float(token.replace("_", "."))
        return (lambda h, a, line=line: h + a > line) if side == "over" else (lambda h, a, line=line: h + a <= line)
    if market.startswith(("home_over_", "home_under_")):
        side, token = market.split("_", 2)[1:]
        line = float(token.replace("_", "."))
        return (lambda h, a, line=line: h > line) if side == "over" else (lambda h, a, line=line: h <= line)
    if market.startswith(("away_over_", "away_under_")):
        side, token = market.split("_", 2)[1:]
        line = float(token.replace("_", "."))
        return (lambda h, a, line=line: a > line) if side == "over" else (lambda h, a, line=line: a <= line)
    if market == "clean_home":
        return lambda h, a: a == 0
    if market == "clean_away":
        return lambda h, a: h == 0
    if market == "clean_home_no":
        return lambda h, a: a > 0
    if market == "clean_away_no":
        return lambda h, a: h > 0
    if market.startswith("score_"):
        _, sh, sa = market.split("_")
        return lambda h, a, sh=int(sh), sa=int(sa): h == sh and a == sa
    if market == "total_pair":
        return lambda h, a: (h + a) % 2 == 0
    if market == "total_impair":
        return lambda h, a: (h + a) % 2 == 1
    if market.startswith("exact_goals_"):
        token = market.removeprefix("exact_goals_")
        if token == "6_plus":
            return lambda h, a: h + a >= 6
        n = int(token)
        return lambda h, a, n=n: h + a == n
    if market.startswith("handicap_"):
        _, token, side = market.split("_")
        line = float(token)
        if side == "1":
            return lambda h, a, line=line: h - line > a
        if side == "X":
            return lambda h, a, line=line: h - line == a
        if side == "2":
            return lambda h, a, line=line: h - line < a
    return None


def gagne(market, h, a):
    """Résultat réel d'un marché plein temps pour le score h-a (None si le marché n'est pas plein temps)."""
    p = _predicate_for_market(market)
    return None if p is None else bool(p(h, a))


def pairwise_joint_probability(markets, matrix):
    """Probabilités conjointes exactes pour les marchés FT dérivés de la matrice."""
    predicates = {m: _predicate_for_market(m) for m in markets}
    out = {}
    for a in markets:
        for b in markets:
            pa, pb = predicates.get(a), predicates.get(b)
            if pa is None or pb is None:
                continue
            out[(a, b)] = _event(matrix, lambda h, x, pa=pa, pb=pb: pa(h, x) and pb(h, x))
    return out
