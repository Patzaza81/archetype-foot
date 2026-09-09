"""
archetype_model/signals/statistiques_signal.py — Signal Statistiques
UNIQUE par marché (ARCHETYPE_FOOT v3, §11.1) :

    "Un seul signal par marché (jamais offensif + défensif + tendance
    comptés séparément) : fréquence observée sur l'échantillon 5-12,
    direction, N, niveau de fiabilité -- composantes visibles pour
    l'explication, jamais comptées comme votes indépendants."

Chaque fonction ci-dessous produit CE signal unique pour un marché
donné -- jamais plusieurs indicateurs combinés en un score.

DIFFÉRENCE IMPORTANTE avec h2h_markets.py (pas le même risque) :
h2h_markets doit normaliser des confrontations passées où l'équipe A
n'a pas toujours joué à domicile (risque d'inversion, cf. bug connu de
l'ancien moteur). Ici, ce risque n'existe PAS : `fenetre` est TOUJOURS
la fenêtre déjà correctement attribuée à une équipe et un rôle précis
par `data.loader`/`data.validation` (domicile pour A, extérieur pour
B) -- déjà vérifiée et testée ailleurs dans ce projet. Ce module ne
fait que lire des statistiques déjà bien orientées, jamais une
réorientation lui-même.

PÉRIMÈTRE : ce module produit un signal par ÉQUIPE ET PAR RÔLE (celui
qu'elle joue dans le match analysé), pas un signal combiné des deux
équipes -- cohérent avec le principe général du projet (jamais de
score composite). La combinaison éventuelle de plusieurs signaux se
fait en aval (filtre de candidature, §12), jamais ici.

Chaque fonction attend une `fenetre` déjà produite par
`data.validation.classifie_fenetre` -- ne refiltre ni ne tronque rien
elle-même.
"""

from ..data import validation
from ..statistics import team_stats, goals

DIRECTION_FAVORABLE = "favorable"
DIRECTION_NEUTRE = "neutre"
DIRECTION_DEFAVORABLE = "defavorable"

FIABILITE_SUFFISANT = "SUFFISANT"
FIABILITE_INSUFFISANT = "INSUFFISANT"


def _direction(frequence):
    """>0.5 favorable, <0.5 défavorable, ==0.5 neutre -- jamais forcé
    arbitrairement vers un côté à l'exact milieu (même règle que
    h2h_markets._compare, cohérence délibérée entre les deux modules)."""
    if frequence > 0.5:
        return DIRECTION_FAVORABLE
    if frequence < 0.5:
        return DIRECTION_DEFAVORABLE
    return DIRECTION_NEUTRE


def _signal_insuffisant(marche, n_brut):
    return {"marche": marche, "direction": None, "frequence": None, "n": n_brut, "fiabilite": FIABILITE_INSUFFISANT}


def _signal(marche, frequence, n):
    return {"marche": marche, "direction": _direction(frequence), "frequence": frequence,
            "n": n, "fiabilite": FIABILITE_SUFFISANT}


def signal_victoire(fenetre, marche="victoire"):
    """Fréquence de victoire de l'équipe sur sa fenêtre (déjà orientée
    domicile ou extérieur selon son rôle dans le match analysé)."""
    if fenetre["statut"] != validation.STATUT_UTILISABLE:
        return _signal_insuffisant(marche, fenetre["n_brut"])
    resultats = team_stats.resultats(fenetre["matchs_retenus"])
    return _signal(marche, resultats["frequence_victoires"], resultats["n"])


def signal_btts(fenetre, marche="btts"):
    """Fréquence des matchs récents de cette équipe où les deux
    équipes ont marqué (goals.btts, déjà testé)."""
    if fenetre["statut"] != validation.STATUT_UTILISABLE:
        return _signal_insuffisant(marche, fenetre["n_brut"])
    r = goals.btts(fenetre["matchs_retenus"])
    return _signal(marche, r["frequence"], r["n"])


def signal_over_under_total(fenetre, ligne):
    """Fréquence Over sur le total de buts des matchs récents de cette
    équipe (goals.over_under, déjà testé). `ligne` en X.5."""
    marche = f"over_under_total_{ligne}"
    if fenetre["statut"] != validation.STATUT_UTILISABLE:
        return _signal_insuffisant(marche, fenetre["n_brut"])
    r = goals.over_under(fenetre["matchs_retenus"], ligne)
    return _signal(marche, r["frequence_over"], r["n"])


def signal_buts_equipe(fenetre, ligne):
    """Fréquence à laquelle CETTE équipe (pas le match, elle
    spécifiquement -- v3 §9.4.1/9.4.2, TEAM_GOALS) a marqué plus de
    `ligne` buts sur sa fenêtre récente."""
    marche = f"buts_equipe_{ligne}"
    if fenetre["statut"] != validation.STATUT_UTILISABLE:
        return _signal_insuffisant(marche, fenetre["n_brut"])
    matchs = fenetre["matchs_retenus"]
    n = len(matchs)
    frequence = sum(1 for m in matchs if m["buts_marques"] > ligne) / n
    return _signal(marche, frequence, n)
