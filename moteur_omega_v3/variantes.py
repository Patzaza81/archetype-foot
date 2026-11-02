"""Variantes EXPÉRIMENTALES du score d'un scénario (audit du 02/11/2026, demande de Patrick). Ne sont PAS utilisées par la production (`coeur.py`, variante A).

Une variante donne, pour les quatre séquences, une distribution de poids W[i, j] sur les scores (i buts du domicile, j buts de l'extérieur), de somme 1.
La fréquence d'un marché est alors la somme des poids des scores qui le font gagner (les remboursements ne sont pas comptés gagnés, comme en production).

A. « Offensive seule » (production) : score d'un scénario = (attA_i, attB_k). Les défenses ne servent qu'à mesurer la compatibilité.
   W = pmf(attA) ⊗ pmf(attB). Les 625 scénarios répètent chacun des 25 couples (attA_i, attB_k) 25 fois (une fois par couple de défenses) : fréquence identique.
B. « Mélange explicite attaque / défense » : les buts du domicile sont lus dans les DEUX séquences qui les décrivent (les buts que A marque à domicile, attA, et les buts que B
   encaisse à l'extérieur, defB), à poids égal ; de même pour l'extérieur (attB et defA). Chacun des 625 scénarios donne quatre scores
   (attA_i | defB_j) × (attB_k | defA_l), chacun de poids 1/4 : toute observation intervient exactement une fois par couple, sans coefficient posé à la main.
   W = (½ pmf(attA) + ½ pmf(defB)) ⊗ (½ pmf(attB) + ½ pmf(defA)).
C. « Confrontation complète » : pour chaque scénario, les buts attendus du domicile sont la moyenne de ce que A marque et de ce que B encaisse, λA = (attA_i + defB_j) / 2,
   ceux de l'extérieur λB = (attB_k + defA_l) / 2 ; le score suit deux lois de Poisson indépendantes de ces moyennes ; W = moyenne des 625 scénarios.
   Hypothèses : indépendance des deux scores, loi de Poisson, poids égaux attaque / défense (aucun ajustement). C'est un MODÈLE (probabilité modélisée), pas une fréquence.
   Les quatre indices étant indépendants, W se factorise : W = (moyenne sur (i, j) de Poisson(λA_ij)) ⊗ (moyenne sur (k, l) de Poisson(λB_kl)).

Retrait d'une observation à la fois (§8.1) : la fréquence robuste g de la variante est la plus basse des fréquences obtenues en retirant, une à une, chacune des observations
des quatre séquences (comme `coeur.analyser`).
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np

from . import marches as M

GRILLE = 22                    # scores 0 … 21 : la loi de Poisson est tronquée là (masse perdue < 1e-6 pour λ ≤ 9) puis renormalisée
VARIANTES = ("A", "B", "C")


def _victoires() -> np.ndarray:
    """Matrice (GRILLE² × marchés) : 1 si le score fait GAGNER le marché (un remboursement n'est pas un gain)."""
    return np.stack([M.vecteur(i, j) == 1 for i in range(GRILLE) for j in range(GRILLE)]).astype(np.float64)


VICT = _victoires()


def pmf(obs: list[int]) -> np.ndarray:
    p = np.zeros(GRILLE)
    for x in obs:
        p[x] += 1
    return p / len(obs)


def poisson(lam: float) -> np.ndarray:
    if lam <= 0:
        p = np.zeros(GRILLE)
        p[0] = 1.0
        return p
    k = np.arange(GRILLE)
    logp = -lam + k * math.log(lam) - np.array([math.lgamma(x + 1) for x in k])
    p = np.exp(logp)
    return p / p.sum()


def poids(variante: str, att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int]) -> np.ndarray:
    """Distribution W (GRILLE × GRILLE) des scores selon la variante."""
    if variante == "A":
        return np.outer(pmf(att_a), pmf(att_b))
    if variante == "B":
        return np.outer(0.5 * pmf(att_a) + 0.5 * pmf(def_b), 0.5 * pmf(att_b) + 0.5 * pmf(def_a))
    if variante == "C":
        pa = np.mean([poisson((a + d) / 2) for a in att_a for d in def_b], axis=0)
        pb = np.mean([poisson((b + d) / 2) for b in att_b for d in def_a], axis=0)
        return np.outer(pa, pb)
    raise ValueError(f"variante inconnue : {variante}")


def poids_par_scenarios(variante: str, att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int]) -> np.ndarray:
    """MÊME distribution calculée scénario par scénario, sans factorisation : sert à prouver l'absence de double comptage (chaque scénario pèse 1/N)."""
    W = np.zeros((GRILLE, GRILLE))
    N = len(att_a) * len(def_a) * len(att_b) * len(def_b)
    for a in att_a:
        for da in def_a:
            for b in att_b:
                for db in def_b:
                    if variante == "A":
                        W[a, b] += 1 / N
                    elif variante == "B":
                        for x in (a, db):
                            for y in (b, da):
                                W[x, y] += 1 / (4 * N)
                    else:
                        W += np.outer(poisson((a + db) / 2), poisson((b + da) / 2)) / N
    return W


def frequences(W: np.ndarray) -> np.ndarray:
    """Fréquence (ou probabilité modélisée pour C) de chaque marché."""
    return W.ravel() @ VICT


def robuste(variante: str, seqs: list[list[int]]) -> tuple[np.ndarray, np.ndarray]:
    """(f brute, g robuste) de tous les marchés pour une variante : g = min(f, f après retrait d'une observation, pour chacune des observations des quatre séquences)."""
    f = frequences(poids(variante, *seqs))
    g = f.copy()
    for s in range(4):
        if len(seqs[s]) < 2:
            continue
        for r in range(len(seqs[s])):
            red = [list(x) for x in seqs]
            del red[s][r]
            g = np.minimum(g, frequences(poids(variante, *red)))
    return f, g


def fenetre(seq_complete: dict, taille: int) -> list[list[int]]:
    """Fenêtre élargie (variante expérimentale de couverture) : les `taille` derniers matchs au lieu, quand ils existent."""
    return [list(seq_complete[k][-taille:]) for k in ("att_a", "def_a", "att_b", "def_b")]


Poids = Callable[..., np.ndarray]
