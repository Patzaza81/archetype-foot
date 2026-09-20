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
    combined = a_dom + b_ext

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
        "h2h_over_rate": None,
        "target_goals": None,
        "h2h_over_count": None,
        "both_teams_score_rate": None,
        "away_score_rate": None,
        "home_concede_rate": None,
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
        data["both_teams_score_rate"] = _pct(
            sum(m["buts_marques"] >= 1 and m["buts_encaisses"] >= 1 for m in combined),
            len(combined),
        )

    if h:
        data["h2h_unbeaten_count"] = sum(x["buts_a"] >= x["buts_b"] for x in h)

    line = _market_line(marche)
    if line and line[1] == "over":
        target = line[0]
        data["target_goals"] = target
        if h:
            data["h2h_over_count"] = sum(x["buts_a"] + x["buts_b"] > target for x in h)
            data["h2h_over_rate"] = _pct(data["h2h_over_count"], len(h))

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
    preuves = []

    # Les preuves spécifiques au marché passent avant l'EV. L'EV reste la
    # preuve de secours lorsque aucune preuve spécifique exacte n'est
    # disponible, mais ne doit plus masquer une preuve métier disponible.
    if marche in {"double_chance_1X", "1x2_domicile"}:
        if d["home_unbeaten_streak"] is not None and (
            d["home_unbeaten_streak"] >= 4 or (d["home_win_rate"] is not None and d["home_win_rate"] >= 65)
        ):
            preuves.append(_proof(
                f"Régularité à domicile : {a} reste sur {d['home_unbeaten_streak']} matchs sans défaite dans son stade.",
                type="home_unbeaten_streak", valeur=d["home_unbeaten_streak"],
            ))
        if d["away_concede_pct"] is not None and (
            (d["away_loss_rate"] is not None and d["away_loss_rate"] >= 50) or
            (d["away_winless_streak"] is not None and d["away_winless_streak"] >= 4)
        ):
            preuves.append(_proof(
                f"Fragilité adverse : {b} a concédé au moins un but lors de {d['away_concede_pct']:.1f}% de ses récents déplacements.",
                type="away_concede_pct", valeur=d["away_concede_pct"],
            ))
        if d["h2h_unbeaten_count"] is not None and d["h2h_unbeaten_count"] >= 3:
            preuves.append(_proof(
                f"Avantage historique : {a} est restée invaincue lors de {d['h2h_unbeaten_count']} des {d['h2h_total']} dernières confrontations directes.",
                type="h2h_unbeaten_count", valeur=d["h2h_unbeaten_count"], total=d["h2h_total"],
            ))

    elif marche in {"double_chance_X2", "1x2_exterieur"}:
        if d["away_winless_streak"] is not None and d["away_winless_streak"] >= 4:
            preuves.append(_proof(
                f"Régularité à l'extérieur : {b} reste sur {d['away_winless_streak']} matchs sans défaite en déplacement.",
                type="away_winless_streak", valeur=d["away_winless_streak"],
            ))
        if d["home_loss_rate"] is not None and d["home_winless_streak"] is not None and (
            d["home_loss_rate"] >= 50 or d["home_winless_streak"] >= 4
        ):
            preuves.append(_proof(
                f"Fragilité à domicile : {a} présente {d['home_loss_rate']:.1f}% de défaites récentes à domicile.",
                type="home_loss_rate", valeur=d["home_loss_rate"],
            ))
        if h:
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
                    f"Rythme offensif : plus de 1.5 but inscrit dans {d['over_15_rate_combined']:.1f}% des matchs récents des deux équipes.",
                    type="over_15_rate_combined", valeur=d["over_15_rate_combined"],
                ))
            if d["avg_goals_conceded_combined"] is not None and d["avg_goals_conceded_combined"] >= 1.8:
                preuves.append(_proof(
                    f"Série ouverte : ces deux formations concèdent en moyenne {d['avg_goals_conceded_combined']:.2f} buts par rencontre cette saison.",
                    type="avg_goals_conceded_combined", valeur=d["avg_goals_conceded_combined"],
                ))
            if d["h2h_over_count"] is not None and d["h2h_over_rate"] is not None and d["h2h_over_rate"] >= 70:
                txt = str(target).replace(".", ",")
                preuves.append(_proof(
                    f"Historique prolifique : la barre des {txt} buts a été franchie dans {d['h2h_over_count']} des {d['h2h_total']} derniers duels.",
                    type="h2h_over_count", valeur=d["h2h_over_count"], total=d["h2h_total"],
                ))

    elif line and line[1] == "under":
        target = line[0]
        if target == 1.5 and d["over_15_rate_combined"] is not None and d["over_15_rate_combined"] <= 25:
            preuves.append(_proof(
                f"Rythme fermé : plus de 1.5 but dans seulement {d['over_15_rate_combined']:.1f}% des matchs récents des deux équipes.",
                type="under_15_rate_combined", valeur=d["over_15_rate_combined"],
            ))
        if d["h2h_over_count"] is not None and d["h2h_over_rate"] is not None and d["h2h_over_rate"] <= 30:
            txt = str(target).replace(".", ",")
            preuves.append(_proof(
                f"Historique fermé : la barre des {txt} buts n'a été franchie que dans {d['h2h_over_count']} des {d['h2h_total']} derniers duels.",
                type="h2h_under_count", valeur=d["h2h_over_count"], total=d["h2h_total"],
            ))

    elif marche == "btts_oui":
        if d["both_teams_score_rate"] is not None and d["both_teams_score_rate"] >= 70:
            preuves.append(_proof(
                f"Efficacité croisée : les deux équipes ont trouvé le chemin des filets dans {d['both_teams_score_rate']:.1f}% de leurs matchs récents.",
                type="both_teams_score_rate", valeur=d["both_teams_score_rate"],
            ))
        if (
            d["away_score_rate"] is not None and d["away_score_rate"] >= 70 and
            d["home_concede_rate"] is not None and d["home_concede_rate"] >= 70
        ):
            preuves.append(_proof(
                f"Match ouvert : {b} marque régulièrement à l'extérieur face à une défense de {a} rarement imbattable.",
                type="away_score_rate_home_concede_rate", away_score_rate=d["away_score_rate"], home_concede_rate=d["home_concede_rate"],
            ))

    if d["ev_percentage"] is not None:
        preuves.append(_proof(
            f"Avantage Statistique : +{d['ev_percentage']:.1f}%",
            type="ev_percentage", valeur=d["ev_percentage"],
            explication=f"La cote actuelle est supérieure de {d['ev_percentage']:.1f}% à ce que nos calculs jugent équitable.",
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
