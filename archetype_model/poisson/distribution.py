"""
archetype_model/poisson/distribution.py — Matrice de Poisson jointe
(ARCHETYPE_FOOT v3, §7) :

    P(X=x) = e^{-λ_A} λ_A^x / x!        P(Y=y) = e^{-λ_B} λ_B^y / y!
    P(X=x, Y=y) = P(X=x) × P(Y=y)       (indépendance, v3 §7)

DÉCISION DE CONCEPTION à ne pas re-deviner ailleurs : la matrice est
TRONQUÉE à `max_buts` buts par équipe (défaut 15). Aucun match réel
n'approche cette borne (λ football réalistes : 0.2 à ~3.5), la masse de
probabilité résiduelle au-delà est négligeable, mais elle n'est
JAMAIS nulle mathématiquement -- la somme de la matrice retournée est
donc très proche de 1.0 sans être exactement 1.0. Ne jamais supposer
`somme(matrice) == 1.0` exactement dans le code appelant ; utiliser
`masse_totale()` si le résidu de troncature doit être vérifié.

Fonction PURE : prend des λ déjà calculés (ex. via
poisson.lambda_estimators.estime_lambdas), ne connaît rien du
football, de data.loader ni de statistics.

GESTION DE L'ABSENT : un λ peut être None (scénario indisponible, voir
lambda_estimators.py) -- dans ce cas, aucune matrice ne peut être
construite pour ce scénario. `matrice_scores` retourne None plutôt que
de deviner une valeur, jamais une exception.
"""

import math

MAX_BUTS_PAR_DEFAUT = 15


def loi_poisson(lam, k):
    """P(X=k) pour une loi de Poisson de paramètre λ=lam. None si lam
    est None (jamais une exception, jamais un faux 0)."""
    if lam is None:
        return None
    return math.exp(-lam) * lam**k / math.factorial(k)


def distribution_marginale(lam, max_buts=MAX_BUTS_PAR_DEFAUT):
    """[P(X=0), P(X=1), ..., P(X=max_buts)] pour une loi de Poisson λ.
    None si lam est None."""
    if lam is None:
        return None
    return [loi_poisson(lam, k) for k in range(max_buts + 1)]


def matrice_scores(lambda_a, lambda_b, max_buts=MAX_BUTS_PAR_DEFAUT):
    """
    Matrice jointe (v3 §7), taille (max_buts+1) x (max_buts+1) :
    matrice[x][y] = P(X=x) * P(Y=y).

    None si lambda_a OU lambda_b est None -- une matrice à moitié
    construite serait pire qu'aucune matrice, jamais retournée.
    """
    if lambda_a is None or lambda_b is None:
        return None
    dist_a = distribution_marginale(lambda_a, max_buts)
    dist_b = distribution_marginale(lambda_b, max_buts)
    return [[pa * pb for pb in dist_b] for pa in dist_a]


def masse_totale(matrice):
    """Somme de toutes les cellules -- doit être très proche de 1.0
    (voir décision de troncature en tête de fichier), jamais utilisée
    pour re-normaliser la matrice (la troncature est un choix assumé,
    pas une erreur à corriger silencieusement)."""
    if matrice is None:
        return None
    return sum(sum(ligne) for ligne in matrice)
