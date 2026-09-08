"""
archetype_model/statistics/distributions.py — Primitives statistiques
génériques (moyenne, médiane, variance, écart-type, min/max,
distribution par paliers de buts), réutilisées par team_stats.py et
goals.py. Aucune connaissance du domaine football ici -- juste des
listes de nombres.

DÉCISION DE CONCEPTION à ne pas re-deviner ailleurs : `variance` et
`ecart_type` utilisent la variance de POPULATION (division par N, pas
N-1). Choix délibéré : on décrit la dispersion RÉELLE de la fenêtre de
matchs observée (5 à 12 valeurs), pas une estimation d'une population
plus large -- l'estimateur non biaisé (N-1) n'a pas de sens ici, ces
matchs ne sont pas un échantillon aléatoire d'un univers plus grand,
c'est la fenêtre entière qu'on décrit.

Toutes les fonctions scalaires renvoient None sur une liste vide --
jamais une exception, jamais 0 (0 serait une fausse valeur, pas une
absence de donnée).
"""

import statistics as _stats_stdlib


def moyenne(valeurs):
    if not valeurs:
        return None
    return sum(valeurs) / len(valeurs)


def mediane(valeurs):
    if not valeurs:
        return None
    return _stats_stdlib.median(valeurs)


def variance(valeurs):
    """Variance de POPULATION (division par N). Voir décision en tête
    de fichier. None si moins de 1 valeur ; 0.0 (pas None) sur une
    seule valeur, cas correct (aucune dispersion, pas une absence de
    donnée)."""
    if not valeurs:
        return None
    m = moyenne(valeurs)
    return sum((v - m) ** 2 for v in valeurs) / len(valeurs)


def ecart_type(valeurs):
    if not valeurs:
        return None
    return variance(valeurs) ** 0.5


def minimum(valeurs):
    return min(valeurs) if valeurs else None


def maximum(valeurs):
    return max(valeurs) if valeurs else None


def distribution_paliers(valeurs):
    """Distribution 0/1/2/3+ (v3 §5). Clés fixes toujours présentes
    (0 partout si la liste est vide), jamais un dict partiel -- un
    appelant qui lit distribution["3+"] ne doit jamais lever de
    KeyError."""
    paliers = {"0": 0, "1": 0, "2": 0, "3+": 0}
    for v in valeurs:
        if v <= 0:
            paliers["0"] += 1
        elif v == 1:
            paliers["1"] += 1
        elif v == 2:
            paliers["2"] += 1
        else:
            paliers["3+"] += 1
    return paliers
