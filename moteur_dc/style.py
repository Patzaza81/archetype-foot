"""Style par la fréquence des scores (branche moteur-dc-style, demande de Patrick du 31/10/2026).

Idée : le style d'une équipe se lit dans la répétition de ses scores au lieu du match. On construit une matrice de scores EMPIRIQUE à partir
des matchs réels des deux équipes (contrat 1.5 : historique à domicile du domicile, historique à l'extérieur de l'extérieur, saison en cours,
matchs strictement antérieurs), puis on la mélange case par case avec la grille Dixon-Coles :

    P = (1 − w) × P_DC + w × P_empirique        w = n / (n + k) = c·n / (1 + c·n)

- Buts du domicile : moitié de la loi de ses buts marqués à domicile, moitié de la loi des buts encaissés par l'extérieur à l'extérieur.
  Buts de l'extérieur : même croisement dans l'autre sens. Matrice = produit des deux lois (aucune corrélation inventée entre les deux).
- n = nombre de matchs de l'équipe qui en a le moins (échantillon limitant). Plus n est petit, plus Dixon-Coles domine.
- k n'est posé nulle part : c = 1/k est appris hors échantillon (Football-Data 2025-26, marche avant), validé sur 2026-27 (calibrage.py style).
  c = 0 : aucun effet (Dixon-Coles pur).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from . import modele as MO

TAILLE = MO.N_BUTS + 1


def loi(buts: list[int]) -> np.ndarray:
    """Fréquence de chaque nombre de buts (0..N_BUTS, au-delà regroupé sur la dernière case)."""
    v = np.zeros(TAILLE)
    for b in buts:
        v[min(int(b), MO.N_BUTS)] += 1
    return v / v.sum()


def matrice_empirique(c: dict[str, Any]) -> tuple[np.ndarray, int]:
    """(matrice des scores empirique 11×11, n) à partir du contrat 1.5 `c`. Ligne = buts du domicile, colonne = buts de l'extérieur."""
    hd = c["equipe_domicile"]["historique_matchs_dom"]
    he = c["equipe_exterieur"]["historique_matchs_ext"]
    p_dom = 0.5 * (loi([x["buts_pour"] for x in hd]) + loi([x["buts_contre"] for x in he]))
    p_ext = 0.5 * (loi([x["buts_pour"] for x in he]) + loi([x["buts_contre"] for x in hd]))
    return np.outer(p_dom, p_ext), min(len(hd), len(he))


def poids(n: int | np.ndarray, force: float) -> float | np.ndarray:
    """w = n / (n + k) avec force = c = 1/k ; force 0 → w = 0 (aucun effet)."""
    return force * n / (1.0 + force * n)


def melanger(g: np.ndarray, e: np.ndarray, w: float | np.ndarray) -> np.ndarray:
    """Mélange case par case. Les deux grilles somment à 1 : le mélange somme à 1 (convexe)."""
    w = np.asarray(w, dtype=float)
    if g.ndim == 3:
        w = w.reshape(-1, 1, 1)
    return (1.0 - w) * g + w * e


def force_du(params: dict[str, Any]) -> float:
    return float((params.get("style_freq") or {}).get("c", 0.0) or 0.0)
