"""
archetype_model/poisson/correlation.py — Corrélation de Pearson exacte
entre deux marchés, calculée sur la matrice Poisson jointe déjà
produite pour le match (`distribution.matrice_scores`).

Portage de `calculs.py::correlation_marches` (ancien moteur, Module 3
v6.3, Étape 4) vers archetype_model -- MÊME MATHÉMATIQUE, adaptée au
format de matrice d'archetype_model (liste de listes `matrice[x][y]`,
voir `distribution.matrice_scores`) au lieu du format dict `{(x,y):
proba}` de l'ancien moteur.

Trouvé par Patrick le 16/09/2026 : ce calcul existait déjà pour
départager des marchés redondants du même match dans l'ancien moteur
-- remplace la première version de `selection_edv_directe.py`, qui
utilisait une liste de paires figées à la main (Double Chance /
Handicap uniquement). Ce calcul-ci généralise automatiquement à
N'IMPORTE QUELLE paire de marchés, déterminé par le modèle lui-même,
jamais par un jugement sémantique sur les noms des marchés.
"""

from __future__ import annotations

from typing import Callable


def correlation_marches(
    matrice: list[list[float]],
    condition_a: Callable[[int, int], bool],
    condition_b: Callable[[int, int], bool],
) -> float:
    """
    Corrélation de Pearson EXACTE entre deux indicatrices de marché,
    calculée sur la matrice jointe Poisson/Dixon-Coles du match -- un
    calcul mécanique déterminé par le modèle, jamais une estimation ni
    un jugement sémantique sur ce que "veulent dire" les deux marchés.

    `condition_a`/`condition_b` : fonctions (buts_domicile, buts_exterieur)
    -> bool, décrivant la condition de gain de chaque marché sur un
    scoreline donné.

    Retourne 0.0 si l'une des deux indicatrices est constante sur toute
    la matrice (variance nulle -- corrélation mathématiquement non
    définie, jamais une exception).
    """
    n_x = len(matrice)
    n_y = len(matrice[0]) if n_x else 0

    a_vals = []
    b_vals = []
    probs = []
    for x in range(n_x):
        for y in range(n_y):
            p = matrice[x][y]
            probs.append(p)
            a_vals.append(1.0 if condition_a(x, y) else 0.0)
            b_vals.append(1.0 if condition_b(x, y) else 0.0)

    ea = sum(p * ai for p, ai in zip(probs, a_vals))
    eb = sum(p * bi for p, bi in zip(probs, b_vals))
    cov = sum(p * (ai - ea) * (bi - eb) for p, ai, bi in zip(probs, a_vals, b_vals))
    var_a = sum(p * (ai - ea) ** 2 for p, ai in zip(probs, a_vals))
    var_b = sum(p * (bi - eb) ** 2 for p, bi in zip(probs, b_vals))

    if var_a <= 0 or var_b <= 0:
        return 0.0
    return cov / (var_a * var_b) ** 0.5
