"""Bibliothèque stricte de justification marketing.

Contrat : les noms et définitions de ce module sont ceux de la bibliothèque
métier, pas des alias de l'ancien système. Une donnée n'est publiée que si
elle est calculable exactement à partir des historiques réellement fournis.
Cette couche ne choisit aucun marché et ne modifie aucun calcul du moteur.
"""
from __future__ import annotations

from statistics import mean

MIN_MATCHES = 5
MIN_ROLE_MATCHES = 3

# Les H2H sont une information contextuelle affichée séparément. Ils ne participent
# jamais à la justification ni à l'éligibilité d'un marché.
H2H_JUSTIFICATION_ACTIVE = False


def _valid(matches):
    return [
        m for m in (matches or [])
        if isinstance(m, dict)
        and isinstance(m.get("buts_marques"), (int, float))
        and isinstance(m.get("buts_encaisses"), (int, float))
    ]


def _recent(matches):
    matches = _valid(matches)
    return matches if len(matches) >= MIN_MATCHES else []


def _role_matches(matches, domicile):
    return [m for m in _valid(matches) if m.get("domicile") is domicile]


def _recent_role(matches, domicile):
    matches = _role_matches(matches, domicile)
    return matches if len(matches) >= MIN_ROLE_MATCHES else []


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def _streak(matches, predicate):
    if not matches:
        return None
    count = 0
    for m in reversed(matches):
        if predicate(m):
            count += 1
        else:
            break
    return count


def _h2h(h2h):
    return [
        x for x in (h2h or [])
        if isinstance(x, dict)
        and isinstance(x.get("buts_a"), (int, float))
        and isinstance(x.get("buts_b"), (int, float))
    ]


def _market_line(market):
    import re
    # Nomenclature réellement utilisée par le moteur : over_2.5, over_1.5,
    # etc. L'ancien identifiant explicite reste accepté pour compatibilité.
    m = re.search(r"^(over|under)_(-?\d+(?:\.\d+)?)$", market or "")
    if m:
        return (float(m.group(2)), m.group(1))
    m = re.search(r"^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$", market or "")
    return (float(m.group(1)), m.group(2)) if m else None


def _team_goals_line(market):
    """buts_equipe_(domicile|exterieur)_L_(over|under) -> (côté, ligne, sens) ou None."""
    import re
    m = re.search(r"^buts_equipe_(domicile|exterieur)_(-?\d+(?:\.\d+)?)_(over|under)$", market or "")
    return (m.group(1), float(m.group(2)), m.group(3)) if m else None


def _au_moins(ligne):
    """Ligne de buts en demi-but -> nombre entier de buts minimal : 1,5 -> 2 ; 2,5 -> 3 ; 0,5 -> 1."""
    import math
    return math.floor(ligne) + 1


def _buts(n):
    return f"{n} but{'s' if n > 1 else ''}"


def sens_handicap_equipe(ligne, equipe):
    """Ce que demande un handicap, en mots simples, du point de vue de l'équipe (buts marqués + ligne > buts encaissés).
    +0,5 -> « X ne perd pas » ; +1,5 -> « X ne perd pas par 2 buts d'écart ou plus » ; -0,5 -> « X gagne » ;
    -1,5 -> « X gagne par 2 buts d'écart ou plus »."""
    import math
    m = math.floor(-ligne) + 1  # écart minimal (buts marqués - encaissés) pour couvrir le handicap
    buts = lambda n: f"{n} but{'s' if n > 1 else ''}"
    if m >= 1:
        return f"{equipe} gagne" + (f" par {buts(m)} d'écart ou plus" if m > 1 else "")
    if m == 0:
        return f"{equipe} ne perd pas"
    return f"{equipe} ne perd pas par {buts(1 - m)} d'écart ou plus"


def _handicap_line(market):
    """handicap_(domicile|exterieur)_L -> (côté, ligne) ou None."""
    import re
    m = re.search(r"^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$", market or "")
    return (m.group(1), float(m.group(2))) if m else None


def construit_donnees(
    marche: str,
    matchs_a,
    matchs_b,
    h2h=None,
    *,
    odds_scraped=None,
    market_prob_pct=None,
):
    """Construit uniquement les champs EXACTS de la bibliothèque."""
    a_dom = _recent_role(matchs_a, True)
    b_ext = _recent_role(matchs_b, False)
    h = _h2h(h2h)
    # CORRECTIF 21/09/2026 : les statistiques « combinées » (phrases « des deux équipes ») exigent des matchs des DEUX
    # équipes. Avant, si l'une n'avait pas assez de matchs à son lieu (seuil de 3), ses matchs étaient ignorés et la
    # phrase « des deux équipes » était calculée sur une seule (cas réel : Dallas, 2 matchs à domicile, 6 à l'extérieur).
    combined = a_dom + b_ext if (a_dom and b_ext) else []

    data = {
        "odds_scraped": odds_scraped if isinstance(odds_scraped, (int, float)) else None,
        "market_prob_pct": market_prob_pct if isinstance(market_prob_pct, (int, float)) else None,
        "ev_percentage": None,
        "home_unbeaten_streak": None,
        "home_win_rate": None,
        "away_loss_rate": None,
        "away_winless_streak": None,
        "away_concede_pct": None,
        "h2h_unbeaten_count": None,
        "h2h_total": len(h),
        "over_15_rate_combined": None,
        "avg_goals_conceded_combined": None,
        "avg_goals_scored_combined": None,
        "avg_total_goals_combined": None,
        "h2h_over_rate": None,
        "target_goals": None,
        "h2h_over_count": None,
        "both_teams_score_rate": None,
        "away_score_rate": None,
        "home_concede_rate": None,
        # CORRECTIF 21/09/2026 : ces deux clés n'existaient que si l'équipe à domicile avait >= 3 matchs à
        # domicile ; la branche X2 / 1x2_exterieur les lit sans condition -> KeyError sinon.
        "home_loss_rate": None,
        "home_winless_streak": None,
        # CORRECTIF 21/09/2026 : la série « sans défaite » de l'équipe visiteuse n'existait pas ; le texte
        # X2 « sans défaite en déplacement » s'appuyait sur away_winless_streak (= sans VICTOIRE : nuls
        # ou défaites), soit exactement le contraire de ce qu'il affirmait. away_win_rate complète le
        # tableau « forme récente » de l'extérieur (symétrique de home_win_rate).
        "away_unbeaten_streak": None,
        "away_win_rate": None,
        # AJOUT 21/09/2026 -- champs des nouveaux marchés (nul, sans nul, BTTS non,
        # lignes de buts quelconques, buts d'une équipe). Tous calculés exactement
        # sur les mêmes historiques, avec les mêmes seuils minimaux que ci-dessus.
        "draw_rate_combined": None,
        "h2h_draw_count": None,
        "over_rate_combined": None,
        "team_over_rate": None,
        "opp_over_rate": None,
        "clean_sheet_rate": None,
        "handicap_cover_rate": None,
        "handicap_n": None,
        "handicap_k": None,
        "target_handicap": None,
        "h2h_home_win_count": None,
        "h2h_away_win_count": None,
    }

    if data["market_prob_pct"] is not None and data["odds_scraped"] is not None:
        data["ev_percentage"] = round(((data["market_prob_pct"] / 100.0 * data["odds_scraped"]) - 1.0) * 100.0, 1)

    if len(a_dom) >= MIN_ROLE_MATCHES:
        data["home_unbeaten_streak"] = _streak(a_dom, lambda m: m["buts_marques"] >= m["buts_encaisses"])
        data["home_win_rate"] = _pct(sum(m["buts_marques"] > m["buts_encaisses"] for m in a_dom), len(a_dom))
        data["home_concede_rate"] = _pct(sum(m["buts_encaisses"] >= 1 for m in a_dom), len(a_dom))
        data["home_loss_rate"] = _pct(sum(m["buts_marques"] < m["buts_encaisses"] for m in a_dom), len(a_dom))
        data["home_winless_streak"] = _streak(a_dom, lambda m: m["buts_marques"] <= m["buts_encaisses"])

    if len(b_ext) >= MIN_ROLE_MATCHES:
        data["away_loss_rate"] = _pct(sum(m["buts_marques"] < m["buts_encaisses"] for m in b_ext), len(b_ext))
        data["away_winless_streak"] = _streak(b_ext, lambda m: m["buts_marques"] <= m["buts_encaisses"])
        data["away_unbeaten_streak"] = _streak(b_ext, lambda m: m["buts_marques"] >= m["buts_encaisses"])
        data["away_win_rate"] = _pct(sum(m["buts_marques"] > m["buts_encaisses"] for m in b_ext), len(b_ext))
        data["away_concede_pct"] = _pct(sum(m["buts_encaisses"] >= 1 for m in b_ext), len(b_ext))
        data["away_score_rate"] = _pct(sum(m["buts_marques"] >= 1 for m in b_ext), len(b_ext))

    if len(combined) >= MIN_MATCHES:
        data["over_15_rate_combined"] = _pct(
            sum(m["buts_marques"] + m["buts_encaisses"] > 1.5 for m in combined),
            len(combined),
        )
        data["avg_goals_conceded_combined"] = round(
            mean(m["buts_encaisses"] for m in combined), 2
        )
        data["avg_goals_scored_combined"] = round(
            mean(m["buts_marques"] for m in combined), 2
        )
        data["avg_total_goals_combined"] = round(
            mean(m["buts_marques"] + m["buts_encaisses"] for m in combined), 2
        )
        data["both_teams_score_rate"] = _pct(
            sum(m["buts_marques"] >= 1 and m["buts_encaisses"] >= 1 for m in combined),
            len(combined),
        )
        data["draw_rate_combined"] = _pct(
            sum(m["buts_marques"] == m["buts_encaisses"] for m in combined),
            len(combined),
        )
    if h:
        data["h2h_unbeaten_count"] = sum(x["buts_a"] >= x["buts_b"] for x in h)
        data["h2h_draw_count"] = sum(x["buts_a"] == x["buts_b"] for x in h)
        data["h2h_home_win_count"] = sum(x["buts_a"] > x["buts_b"] for x in h)
        data["h2h_away_win_count"] = sum(x["buts_b"] > x["buts_a"] for x in h)
    line = _market_line(marche)
    # CORRECTIF 21/09/2026 : ces champs n'étaient calculés que pour les lignes « over ».
    # Pour un marché « under », h2h_over_count restait None : la preuve « Historique
    # fermé » (h2h_under_count) prévue plus bas ne pouvait donc jamais être produite.
    if line:
        target = line[0]
        data["target_goals"] = target
        if len(combined) >= MIN_MATCHES:
            data["over_rate_combined"] = _pct(
                sum(m["buts_marques"] + m["buts_encaisses"] > target for m in combined),
                len(combined),
            )
        if h:
            data["h2h_over_count"] = sum(x["buts_a"] + x["buts_b"] > target for x in h)
            data["h2h_over_rate"] = _pct(data["h2h_over_count"], len(h))
    tm = _team_goals_line(marche)
    if tm:
        cote_marche, ligne_equipe, _ = tm
        # domicile : l'équipe = celle qui reçoit (ses matchs à domicile), l'adversaire = celle qui se déplace.
        equipe_ms, adverse_ms = (a_dom, b_ext) if cote_marche == "domicile" else (b_ext, a_dom)
        data["target_goals"] = ligne_equipe
        if len(equipe_ms) >= MIN_ROLE_MATCHES:
            data["team_over_rate"] = _pct(sum(m["buts_marques"] > ligne_equipe for m in equipe_ms), len(equipe_ms))
        if len(adverse_ms) >= MIN_ROLE_MATCHES:
            data["opp_over_rate"] = _pct(sum(m["buts_encaisses"] > ligne_equipe for m in adverse_ms), len(adverse_ms))

    hc = _handicap_line(marche)
    if hc:
        cote_marche, ligne_handicap = hc
        equipe_ms = a_dom if cote_marche == "domicile" else b_ext
        data["target_handicap"] = ligne_handicap
        if len(equipe_ms) >= MIN_ROLE_MATCHES:
            data["handicap_n"] = len(equipe_ms)
            data["handicap_k"] = sum(m["buts_marques"] + ligne_handicap > m["buts_encaisses"] for m in equipe_ms)
            data["handicap_cover_rate"] = _pct(data["handicap_k"], data["handicap_n"])
    return data


def _proof(text, **extra):
    d = {"texte": text}
    d.update(extra)
    return d


def construit_justification_bibliotheque(
    marche,
    matchs_a,
    matchs_b,
    h2h=None,
    nom_domicile="",
    nom_exterieur="",
    *,
    odds_scraped=None,
    market_prob_pct=None,
):
    """Rendu exclusif de la nouvelle bibliothèque.

    Aucune formulation héritée n'est utilisée. Lorsqu'aucune preuve exacte
    du contrat n'est disponible, aucune justification marketing générique
    n'est fabriquée.
    """
    d = construit_donnees(
        marche, matchs_a, matchs_b, h2h,
        odds_scraped=odds_scraped,
        market_prob_pct=market_prob_pct,
    )
    a = nom_domicile or "Équipe à domicile"
    b = nom_exterieur or "Équipe à l'extérieur"
    # CORRECTIF 21/09/2026 : `h` était utilisé plus bas (branche X2 / 1x2_exterieur) sans être défini
    # ici -> NameError pour double_chance_X2 et 1x2_exterieur (introduit par 6f60b3b, 20/09/2026).
    h = _h2h(h2h)
    marche = marche or ""
    preuves = []

    # Les preuves spécifiques au marché passent avant l'EV. L'EV reste la
    # preuve de secours lorsque aucune preuve spécifique exacte n'est
    # disponible, mais ne doit plus masquer une preuve métier disponible.
    if marche == "1x2_domicile":
        if d["home_win_rate"] is not None and d["home_win_rate"] >= 65:
            preuves.append(_proof(
                f"{a} s'impose dans {d['home_win_rate']:.0f} % de ses récentes sorties à domicile.",
                type="home_win_rate", valeur=d["home_win_rate"],
            ))
        if d["away_loss_rate"] is not None and d["away_loss_rate"] >= 50:
            preuves.append(_proof(
                f"{b} cède la victoire dans {d['away_loss_rate']:.0f} % de ses derniers déplacements.",
                type="away_loss_rate", valeur=d["away_loss_rate"],
            ))
        if H2H_JUSTIFICATION_ACTIVE and d["h2h_home_win_count"] is not None and d["h2h_total"] >= MIN_MATCHES and _pct(d["h2h_home_win_count"], d["h2h_total"]) >= 60:
            preuves.append(_proof(
                f"Les confrontations récentes tournent aussi en faveur de {a} : {d['h2h_home_win_count']} victoires sur {d['h2h_total']} duels.",
                type="h2h_home_win_count", valeur=d["h2h_home_win_count"], total=d["h2h_total"],
            ))

    elif marche == "double_chance_1X":
        if d["home_unbeaten_streak"] is not None and d["home_unbeaten_streak"] >= 4:
            preuves.append(_proof(
                f"{a} reste difficile à faire tomber chez elle, avec {d['home_unbeaten_streak']} matchs consécutifs sans défaite.",
                type="home_unbeaten_streak", valeur=d["home_unbeaten_streak"],
            ))
        if d["home_win_rate"] is not None and d["home_win_rate"] >= 65:
            preuves.append(_proof(
                f"À domicile, {a} gagne {d['home_win_rate']:.0f} % de ses rencontres récentes.",
                type="home_win_rate", valeur=d["home_win_rate"],
            ))
        if H2H_JUSTIFICATION_ACTIVE and d["h2h_unbeaten_count"] is not None and d["h2h_total"] >= MIN_MATCHES and _pct(d["h2h_unbeaten_count"], d["h2h_total"]) >= 60:
            preuves.append(_proof(
                f"{a} a évité la défaite dans {d['h2h_unbeaten_count']} des {d['h2h_total']} derniers duels entre les deux équipes.",
                type="h2h_unbeaten_count", valeur=d["h2h_unbeaten_count"], total=d["h2h_total"],
            ))

    elif marche == "1x2_exterieur":
        if d["away_win_rate"] is not None and d["away_win_rate"] >= 65:
            preuves.append(_proof(
                f"En déplacement, {b} gagne {d['away_win_rate']:.0f} % de ses dernières rencontres.",
                type="away_win_rate", valeur=d["away_win_rate"],
            ))
        if d["home_loss_rate"] is not None and d["home_loss_rate"] >= 50:
            preuves.append(_proof(
                f"{a} s'incline dans {d['home_loss_rate']:.0f} % de ses dernières réceptions.",
                type="home_loss_rate", valeur=d["home_loss_rate"],
            ))
        if H2H_JUSTIFICATION_ACTIVE and d["h2h_away_win_count"] is not None and d["h2h_total"] >= MIN_MATCHES and _pct(d["h2h_away_win_count"], d["h2h_total"]) >= 60:
            preuves.append(_proof(
                f"Les duels récents donnent également l'avantage à {b} : {d['h2h_away_win_count']} victoires sur {d['h2h_total']}.",
                type="h2h_away_win_count", valeur=d["h2h_away_win_count"], total=d["h2h_total"],
            ))

    elif marche == "double_chance_X2":
        if d["away_unbeaten_streak"] is not None and d["away_unbeaten_streak"] >= 4:
            preuves.append(_proof(
                f"Régularité à l'extérieur : {b} reste sur {d['away_unbeaten_streak']} matchs sans défaite en déplacement.",
                type="away_unbeaten_streak", valeur=d["away_unbeaten_streak"],
            ))
        if d["home_loss_rate"] is not None and d["home_winless_streak"] is not None and (
            d["home_loss_rate"] >= 50 or d["home_winless_streak"] >= 4
        ):
            preuves.append(_proof(
                f"Fragilité à domicile : {a} présente {d['home_loss_rate']:.0f} % de défaites récentes à domicile.",
                type="home_loss_rate", valeur=d["home_loss_rate"],
            ))
        if H2H_JUSTIFICATION_ACTIVE and h:
            h2h_x2 = sum(x["buts_a"] <= x["buts_b"] for x in h)
            if _pct(h2h_x2, len(h)) >= 70:
                preuves.append(_proof(
                    f"Avantage historique : {b} est restée invaincue lors de {h2h_x2} des {len(h)} dernières confrontations directes.",
                    type="h2h_x2_unbeaten_count", valeur=h2h_x2, total=len(h),
                ))

    line = _market_line(marche)
    if marche.startswith("over_under_total_") or line:
        target = line[0] if line else 2.5
        if line is None or line[1] == "over":
            if target == 1.5 and d["over_15_rate_combined"] is not None and d["over_15_rate_combined"] >= 75:
                preuves.append(_proof(
                    f"Au moins 2 buts ont été marqués dans {d['over_15_rate_combined']:.0f} % des derniers matchs des deux équipes.",
                    type="over_15_rate_combined", valeur=d["over_15_rate_combined"],
                ))
            if target != 1.5 and d["over_rate_combined"] is not None and d["over_rate_combined"] >= 75:
                txt = str(target).replace(".", ",")
                preuves.append(_proof(
                    f"Au moins {_buts(_au_moins(target))} ont été marqués dans {d['over_rate_combined']:.0f} % des derniers matchs des deux équipes.",
                    type="over_line_rate_combined", valeur=d["over_rate_combined"], ligne=target,
                ))
            if target != 1.5 and d["avg_total_goals_combined"] is not None and d["market_prob_pct"] is not None:
                txt = str(target).replace(".", ",")
                preuves.append(_proof(
                    f"Dans les derniers matchs des deux équipes, il y a en moyenne {d['avg_total_goals_combined']:.2f} buts par match. "
                    f"Notre modèle estime {d['market_prob_pct']:.0f} % de chances d'avoir au moins {_buts(_au_moins(target))} dans ce match.",
                    type="total_goals_model_path", valeur=d["market_prob_pct"], ligne=target,
                    moyenne_total=d["avg_total_goals_combined"],
                    moyenne_marques=d["avg_goals_scored_combined"],
                    moyenne_encaisses=d["avg_goals_conceded_combined"],
                ))
            if d["avg_goals_conceded_combined"] is not None and d["avg_goals_conceded_combined"] >= 1.8:
                preuves.append(_proof(
                    f"Les deux défenses encaissent en moyenne {d['avg_goals_conceded_combined']:.2f} buts par match sur leurs derniers matchs.",
                    type="avg_goals_conceded_combined", valeur=d["avg_goals_conceded_combined"],
                ))
            if H2H_JUSTIFICATION_ACTIVE and d["h2h_over_count"] is not None and d["h2h_over_rate"] is not None and d["h2h_over_rate"] >= 70:
                txt = str(target).replace(".", ",")
                preuves.append(_proof(
                    f"Au moins {_buts(_au_moins(target))} ont été marqués dans {d['h2h_over_count']} des {d['h2h_total']} derniers duels entre les deux équipes.",
                    type="h2h_over_count", valeur=d["h2h_over_count"], total=d["h2h_total"],
                ))
        elif line[1] == "under":
            if target == 1.5 and d["over_15_rate_combined"] is not None and d["over_15_rate_combined"] <= 25:
                preuves.append(_proof(
                    f"Peu de buts : 2 buts ou plus dans seulement {d['over_15_rate_combined']:.0f} % des derniers matchs des deux équipes.",
                    type="under_15_rate_combined", valeur=d["over_15_rate_combined"],
                ))
            if H2H_JUSTIFICATION_ACTIVE and d["h2h_over_count"] is not None and d["h2h_over_rate"] is not None and d["h2h_over_rate"] <= 30:
                txt = str(target).replace(".", ",")
                preuves.append(_proof(
                    f"Peu de buts dans les duels directs : {_buts(_au_moins(target))} ou plus seulement dans {d['h2h_over_count']} des {d['h2h_total']} derniers duels.",
                    type="h2h_under_count", valeur=d["h2h_over_count"], total=d["h2h_total"],
                ))
            if target != 1.5 and d["over_rate_combined"] is not None and d["over_rate_combined"] <= 25:
                txt = str(target).replace(".", ",")
                preuves.append(_proof(
                    f"Peu de buts : {_buts(_au_moins(target))} ou plus dans seulement {d['over_rate_combined']:.0f} % des derniers matchs des deux équipes.",
                    type="under_line_rate_combined", valeur=d["over_rate_combined"], ligne=target,
                ))

    elif marche == "btts_oui":
        if d["both_teams_score_rate"] is not None and d["both_teams_score_rate"] >= 70:
            preuves.append(_proof(
                f"Les deux équipes ont marqué dans {d['both_teams_score_rate']:.0f} % de leurs derniers matchs.",
                type="both_teams_score_rate", valeur=d["both_teams_score_rate"],
            ))
        if (
            d["away_score_rate"] is not None and d["away_score_rate"] >= 70 and
            d["home_concede_rate"] is not None and d["home_concede_rate"] >= 70
        ):
            preuves.append(_proof(
                f"{b} marque souvent à l'extérieur et {a} encaisse souvent à domicile : les deux équipes devraient marquer.",
                type="away_score_rate_home_concede_rate", away_score_rate=d["away_score_rate"], home_concede_rate=d["home_concede_rate"],
            ))

    elif marche == "btts_non":
        if d["both_teams_score_rate"] is not None and d["both_teams_score_rate"] <= 30:
            preuves.append(_proof(
                f"Seulement {d['both_teams_score_rate']:.0f} % des derniers matchs ont vu les deux équipes marquer.",
                type="both_teams_score_rate_low", valeur=d["both_teams_score_rate"],
            ))
        if d["away_score_rate"] is not None and d["away_score_rate"] <= 30:
            preuves.append(_proof(
                f"{b} a marqué dans seulement {d['away_score_rate']:.0f} % de ses derniers matchs à l'extérieur.",
                type="away_score_rate_low", valeur=d["away_score_rate"],
            ))
        if d["home_concede_rate"] is not None and d["home_concede_rate"] <= 30:
            preuves.append(_proof(
                f"{a} n'a encaissé aucun but dans {100.0 - d['home_concede_rate']:.0f} % de ses derniers matchs à domicile.",
                type="home_clean_sheet_rate", valeur=round(100.0 - d["home_concede_rate"], 1),
            ))

    elif marche == "double_chance_12":
        if d["draw_rate_combined"] is not None and d["draw_rate_combined"] <= 20:
            preuves.append(_proof(
                f"Peu de matchs nuls : seulement {d['draw_rate_combined']:.0f} % des derniers matchs des deux équipes se sont terminés par une égalité.",
                type="draw_rate_combined_low", valeur=d["draw_rate_combined"],
            ))
        if H2H_JUSTIFICATION_ACTIVE and d["h2h_draw_count"] is not None and d["h2h_total"] >= MIN_MATCHES and _pct(d["h2h_draw_count"], d["h2h_total"]) <= 20:
            preuves.append(_proof(
                f"Peu de nuls entre ces deux équipes : {d['h2h_draw_count']} seulement sur leurs {d['h2h_total']} derniers duels.",
                type="h2h_no_draw_count", valeur=d["h2h_draw_count"], total=d["h2h_total"],
            ))

    elif marche == "1x2_nul":
        if d["draw_rate_combined"] is not None and d["draw_rate_combined"] >= 35:
            preuves.append(_proof(
                f"Beaucoup de matchs nuls : {d['draw_rate_combined']:.0f} % des derniers matchs des deux équipes se sont terminés par une égalité.",
                type="draw_rate_combined_high", valeur=d["draw_rate_combined"],
            ))
        if H2H_JUSTIFICATION_ACTIVE and d["h2h_draw_count"] is not None and d["h2h_total"] >= MIN_MATCHES and _pct(d["h2h_draw_count"], d["h2h_total"]) >= 40:
            preuves.append(_proof(
                f"Beaucoup de nuls entre ces deux équipes : {d['h2h_draw_count']} sur leurs {d['h2h_total']} derniers duels.",
                type="h2h_draw_count", valeur=d["h2h_draw_count"], total=d["h2h_total"],
            ))

    elif marche == "cage_inviolee_domicile":
        if d["home_concede_rate"] is not None:
            taux = round(100.0 - d["home_concede_rate"], 1)
            d["clean_sheet_rate"] = taux
            if taux >= 70:
                preuves.append(_proof(
                    f"{a} n'a encaissé aucun but dans {taux:.0f} % de ses derniers matchs à domicile.",
                    type="home_clean_sheet_rate", valeur=taux,
                ))
        if d["away_score_rate"] is not None and d["away_score_rate"] <= 30:
            preuves.append(_proof(
                f"{b} a marqué dans seulement {d['away_score_rate']:.0f} % de ses derniers déplacements.",
                type="away_score_rate_low", valeur=d["away_score_rate"],
            ))

    elif marche == "cage_inviolee_exterieur":
        if d["away_concede_pct"] is not None:
            taux = round(100.0 - d["away_concede_pct"], 1)
            d["clean_sheet_rate"] = taux
            if taux >= 70:
                preuves.append(_proof(
                    f"{b} n'a encaissé aucun but dans {taux:.0f} % de ses dernières sorties.",
                    type="away_clean_sheet_rate", valeur=taux,
                ))
        if d["home_win_rate"] is not None and d["home_win_rate"] <= 30:
            preuves.append(_proof(
                f"{a} gagne peu à domicile : seulement {d['home_win_rate']:.0f} % de victoires sur ses derniers matchs chez elle.",
                type="home_win_rate_low", valeur=d["home_win_rate"],
            ))

    elif _handicap_line(marche):
        cote_marche, ligne_handicap = _handicap_line(marche)
        equipe = a if cote_marche == "domicile" else b
        lieu = "à domicile" if cote_marche == "domicile" else "à l'extérieur"
        taux = d["handicap_cover_rate"]
        if taux is not None and taux >= 70:
            n, k = d["handicap_n"], d["handicap_k"]
            preuves.append(_proof(
                f"{sens_handicap_equipe(ligne_handicap, equipe)} : c'est le cas dans {k} de ses {n} dernières rencontres {lieu} ({taux:.0f} %).",
                type="handicap_cover_rate", valeur=taux, ligne=ligne_handicap,
            ))
    elif _team_goals_line(marche):
        cote_marche, ligne_equipe, sens = _team_goals_line(marche)
        txt = str(ligne_equipe).replace(".", ",")
        equipe, adverse = (a, b) if cote_marche == "domicile" else (b, a)
        lieu_e, lieu_a = ("à domicile", "en déplacement") if cote_marche == "domicile" else ("en déplacement", "à domicile")
        if sens == "over":
            if d["team_over_rate"] is not None and d["team_over_rate"] >= 70:
                preuves.append(_proof(
                    f"{equipe} a marqué au moins {_buts(_au_moins(ligne_equipe))} dans {d['team_over_rate']:.0f} % de ses derniers matchs {lieu_e}.",
                    type="team_goals_over_rate", valeur=d["team_over_rate"], ligne=ligne_equipe,
                ))
            if d["opp_over_rate"] is not None and d["opp_over_rate"] >= 70:
                preuves.append(_proof(
                    f"{adverse} a encaissé au moins {_buts(_au_moins(ligne_equipe))} dans {d['opp_over_rate']:.0f} % de ses derniers matchs {lieu_a}.",
                    type="opp_concede_over_rate", valeur=d["opp_over_rate"], ligne=ligne_equipe,
                ))
        else:
            if d["team_over_rate"] is not None and d["team_over_rate"] <= 30:
                preuves.append(_proof(
                    f"{equipe} a marqué {_buts(_au_moins(ligne_equipe))} ou plus dans seulement {d['team_over_rate']:.0f} % de ses derniers matchs {lieu_e}.",
                    type="team_goals_under_rate", valeur=d["team_over_rate"], ligne=ligne_equipe,
                ))
            if d["opp_over_rate"] is not None and d["opp_over_rate"] <= 30:
                preuves.append(_proof(
                    f"{adverse} a encaissé {_buts(_au_moins(ligne_equipe))} ou plus dans seulement {d['opp_over_rate']:.0f} % de ses derniers matchs {lieu_a}.",
                    type="opp_concede_under_rate", valeur=d["opp_over_rate"], ligne=ligne_equipe,
                ))

    if d["ev_percentage"] is not None:
        preuves.append(_proof(
            f"Le prix proposé laisse {d['ev_percentage']:.0f} % de marge par rapport à notre estimation.",
            type="ev_percentage", valeur=d["ev_percentage"],
            explication=f"La cote actuelle laisse {d['ev_percentage']:.0f} % de marge par rapport à notre estimation.",
        ))

    preuves_specifiques = [p for p in preuves if p.get("type") != "ev_percentage"]
    resume = preuves_specifiques[0]["texte"] if preuves_specifiques else None
    # AJOUT 19/09/2026 (Patrick, règle maîtresse) -- un marché retenu doit
    # recevoir une justification SPÉCIFIQUE à ce marché, jamais seulement
    # la preuve EV générique (interchangeable entre tous les marchés,
    # toujours ajoutée en dernier ci-dessus). Ce champ permet à main.py
    # d'appliquer NO DATA -> NO GO : si aucune preuve spécifique n'existe,
    # le marché ne doit pas être retenu, jamais affiché avec une
    # justification générique inventée pour combler le vide.
    preuve_specifique_disponible = bool(preuves_specifiques)

    return {
        "resume": resume,
        "preuves": preuves[:3],
        "donnees_suffisantes": preuve_specifique_disponible,
        "preuve_specifique_disponible": preuve_specifique_disponible,
        "bibliotheque": d,
    }


def confirmation_historique_bibliotheque(marche, matchs_a, matchs_b, h2h=None):
    r = construit_justification_bibliotheque(marche, matchs_a, matchs_b, h2h=h2h)
    for p in r["preuves"]:
        if "valeur" in p and "total" in p:
            return {"nb_confirmant": p["valeur"], "nb_echantillon": p["total"], "pourcentage": round(100*p["valeur"]/p["total"], 1)}
    return None
