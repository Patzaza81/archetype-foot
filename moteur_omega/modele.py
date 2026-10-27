"""Modèle de buts du moteur omega : buts attendus, Poisson corrigé par Dixon-Coles, probabilités des marchés, calibrage.

Buts attendus (deux formes testées sur les données, la meilleure est retenue par le calibrage) :
- « moyenne » (méthode de Patrick, croisements 3 et 4) : buts attendus de A = (buts marqués par A à domicile + buts encaissés par B à
  l'extérieur) / 2, et symétrique pour B ;
- « multiplicative » (forme classique) : force offensive × faiblesse défensive adverse ÷ moyenne du championnat.
Dans les deux cas, chaque moyenne d'équipe est rapprochée de la moyenne du championnat d'autant plus que l'échantillon est petit
(pseudo-matchs `m_equipe`, appris), et la moyenne du championnat est elle-même rapprochée de la moyenne générale en début de saison
(pseudo-matchs `m_ligue`, appris). L'avantage du domicile est porté par les moyennes domicile/extérieur du championnat.
Aucun de ces nombres n'est fixé à la main : tous sont estimés sur Football-Data 2025-26 (`calibrage.py`).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from . import marches as M
from .donnees import References, serie_lieu, MIN_MATCHS

N_BUTS = 10                       # grille des scores 0..10 (au-delà : masse négligeable, la grille est renormalisée)
_I = np.arange(N_BUTS + 1)
_LOGFACT = np.array([math.lgamma(k + 1) for k in _I])
_MASQUES: dict[tuple, np.ndarray] = {}


def masque(cle: M.Cle) -> np.ndarray:
    if cle not in _MASQUES:
        t = M.test_du_marche(*cle)
        _MASQUES[cle] = np.array([[bool(t(i, j)) for j in _I] for i in _I], dtype=float)
    return _MASQUES[cle]


def _pmf(lam: np.ndarray) -> np.ndarray:
    lam = np.maximum(np.asarray(lam, dtype=float), 1e-6)[..., None]
    return np.exp(_I * np.log(lam) - lam - _LOGFACT)


def grilles(la: np.ndarray, lb: np.ndarray, rho: float) -> np.ndarray:
    """Distribution des scores P(i, j) pour chaque couple (λA, λB) ; correction Dixon-Coles sur 0-0, 1-0, 0-1, 1-1 ; renormalisée."""
    la, lb = np.atleast_1d(np.asarray(la, float)), np.atleast_1d(np.asarray(lb, float))
    g = _pmf(la)[:, :, None] * _pmf(lb)[:, None, :]
    g[:, 0, 0] *= np.maximum(1 - la * lb * rho, 0)
    g[:, 0, 1] *= np.maximum(1 + la * rho, 0)
    g[:, 1, 0] *= np.maximum(1 + lb * rho, 0)
    g[:, 1, 1] *= max(1 - rho, 0)
    return g / g.sum(axis=(1, 2), keepdims=True)


def log_vraisemblance(la: np.ndarray, lb: np.ndarray, h: np.ndarray, a: np.ndarray, rho: float) -> float:
    g = grilles(la, lb, rho)
    hh, aa = np.minimum(h, N_BUTS), np.minimum(a, N_BUTS)
    p = g[np.arange(len(la)), hh, aa]
    return float(np.log(np.maximum(p, 1e-12)).sum())


def probas(g: np.ndarray, cles: list[M.Cle]) -> np.ndarray:
    """Probabilités brutes des marchés (agrégation exacte de la distribution des scores) : tableau (matchs, marchés)."""
    mats = np.stack([masque(c) for c in cles])            # (marchés, i, j)
    return np.einsum("nij,kij->nk", g, mats)


# --- Séries d'un match ---------------------------------------------------------------------------------------------
def series(m: dict[str, Any], fenetre: int | None) -> dict[str, list[int]]:
    hm, hc = serie_lieu(m["dom_matchs"], True, m["jour"], fenetre)
    am, ac = serie_lieu(m["ext_matchs"], False, m["jour"], fenetre)
    return {"dom_marques": hm, "dom_encaisses": hc, "ext_marques": am, "ext_encaisses": ac}


def admissible(s: dict[str, list[int]]) -> bool:
    return len(s["dom_marques"]) >= MIN_MATCHS and len(s["ext_marques"]) >= MIN_MATCHS


def reference(refs: References, m: dict[str, Any], p: dict[str, Any]) -> tuple[float, float, int]:
    k, sh, sa = refs.avant(m["ligue"], m["jour"])
    ml = p["m_ligue"]
    return (sh + ml * p["global_dom"]) / (k + ml), (sa + ml * p["global_ext"]) / (k + ml), k


def _rapproche(moyenne: float, n: int, ref: float, m_eq: float) -> float:
    return (n * moyenne + m_eq * ref) / (n + m_eq)


def buts_attendus(s: dict[str, list[int]], ref_dom: float, ref_ext: float, p: dict[str, Any]) -> tuple[float, float]:
    me = p["m_equipe"]
    nd, ne = len(s["dom_marques"]), len(s["ext_marques"])
    md, cd = float(np.mean(s["dom_marques"])), float(np.mean(s["dom_encaisses"]))
    mx, cx = float(np.mean(s["ext_marques"])), float(np.mean(s["ext_encaisses"]))
    if p["forme"] == "moyenne":
        la = _rapproche((md + cx) / 2, (nd + ne) / 2, ref_dom, me)
        lb = _rapproche((mx + cd) / 2, (nd + ne) / 2, ref_ext, me)
    else:
        la = _rapproche(md, nd, ref_dom, me) * _rapproche(cx, ne, ref_dom, me) / ref_dom
        lb = _rapproche(mx, ne, ref_ext, me) * _rapproche(cd, nd, ref_ext, me) / ref_ext
    return max(la, 0.05), max(lb, 0.05)


# --- Calibrage des probabilités (régression isotone, apprise par marché) ------------------------------------------
def isotone(x: np.ndarray, y: np.ndarray) -> tuple[list[float], list[float]]:
    """Régression isotone (pool adjacent violators) : points (probabilité brute moyenne, fréquence observée) de chaque bloc."""
    o = np.argsort(x)
    xs, ys = x[o], y[o]
    blocs: list[list[float]] = []                    # [somme x, somme y, poids]
    for xi, yi in zip(xs, ys):
        blocs.append([xi, yi, 1.0])
        while len(blocs) > 1 and blocs[-2][1] / blocs[-2][2] >= blocs[-1][1] / blocs[-1][2]:
            b = blocs.pop()
            blocs[-1] = [blocs[-1][0] + b[0], blocs[-1][1] + b[1], blocs[-1][2] + b[2]]
    return [round(b[0] / b[2], 6) for b in blocs], [round(b[1] / b[2], 6) for b in blocs]


def calibrer(p_brut: float | np.ndarray, points: list[list[float]] | None) -> float | np.ndarray:
    """Probabilité calibrée (interpolation entre les blocs isotones) ; sans points appris, la probabilité brute est rendue telle quelle."""
    if not points:
        return p_brut
    return np.interp(p_brut, points[0], points[1])
