"""
archetype_model/statistics/goals.py — Tendances de buts (v3 §5) :
BTTS, Over/Under, fréquences de buts totaux.

Comme team_stats.py, agnostique de la source (domicile/extérieur/futur
global) -- prend une liste de matchs au format data.loader.

Le "but total" d'un match, du point de vue d'UNE équipe dans sa propre
liste de matchs, est buts_marques + buts_encaisses -- correct par
construction : buts_encaisses de l'équipe suivie EST le nombre de buts
marqués par l'adversaire dans ce match précis, donc la somme est bien
le score total du match, jamais une approximation.
"""

from .distributions import distribution_paliers


def buts_totaux_par_match(matchs):
    return [m["buts_marques"] + m["buts_encaisses"] for m in matchs]


def btts(matchs):
    """Both Teams To Score : les deux équipes ont marqué dans le match."""
    n = len(matchs)
    if n == 0:
        return {"n": 0, "occurrences": 0, "frequence": None}
    occurrences = sum(1 for m in matchs if m["buts_marques"] > 0 and m["buts_encaisses"] > 0)
    return {"n": n, "occurrences": occurrences, "frequence": occurrences / n}


def over_under(matchs, ligne):
    """Fréquence Over/Under sur le total de buts du match, pour une
    ligne donnée (ex. 2.5). `ligne` est un nombre à virgule (X.5) par
    construction du marché -- aucun match ne peut être exactement égal
    à la ligne, over+under couvrent donc 100% des cas sans reste."""
    totaux = buts_totaux_par_match(matchs)
    n = len(totaux)
    if n == 0:
        return {"n": 0, "ligne": ligne, "over": 0, "under": 0, "frequence_over": None, "frequence_under": None}
    over = sum(1 for t in totaux if t > ligne)
    under = n - over
    return {
        "n": n,
        "ligne": ligne,
        "over": over,
        "under": under,
        "frequence_over": over / n,
        "frequence_under": under / n,
    }


def distribution_buts_totaux(matchs):
    """Distribution 0/1/2/3+ appliquée au total de buts du match
    (pas au seul but marqué par l'équipe -- voir distribution() dans
    team_stats.stats_offensives pour cette dernière)."""
    return distribution_paliers(buts_totaux_par_match(matchs))
