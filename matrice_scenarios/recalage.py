"""Recalage des probabilités par famille de marché (régression isotone), appris sur des résultats réels.

Pourquoi : choisir le maximum sur des dizaines de marchés retient ceux que le modèle surestime (« malédiction du vainqueur »).
Le recalage corrige la probabilité de chaque famille (double chance, totaux, handicaps…) d'après la fréquence réellement observée.
Aucune valeur posée à la main : les points de la courbe viennent des données (voir backtest_comportement.py).
"""
from __future__ import annotations

import re
from bisect import bisect_right


def famille(groupe: str) -> str:
    """Famille d'un groupe de marché, sans la ligne : over_under_2.5 -> over_under ; handicap_-1.5 -> handicap."""
    g = re.sub(r"_-?\d+(\.\d+)?$", "", groupe)
    return g


def isotone(paires: list[tuple[float, int]], blocs: int = 40) -> list[tuple[float, float]]:
    """Courbe croissante probabilité annoncée -> fréquence réelle (PAV sur `blocs` groupes de taille égale)."""
    if not paires:
        return []
    paires = sorted(paires)
    n = len(paires)
    taille = max(1, n // blocs)
    pts = []   # [somme_p, somme_y, poids]
    for i in range(0, n, taille):
        ch = paires[i:i + taille]
        pts.append([sum(p for p, _ in ch), sum(y for _, y in ch), len(ch)])
    pile: list[list[float]] = []
    for b in pts:
        pile.append(b)
        while len(pile) > 1 and pile[-2][1] / pile[-2][2] > pile[-1][1] / pile[-1][2]:
            b2 = pile.pop()
            pile[-1] = [pile[-1][0] + b2[0], pile[-1][1] + b2[1], pile[-1][2] + b2[2]]
    return [(b[0] / b[2], b[1] / b[2]) for b in pile]


def appliquer(courbe: list[tuple[float, float]] | list[list[float]], p: float) -> float:
    """Interpolation linéaire sur la courbe ; hors bornes, on garde l'écart de la borne. Sans courbe : p inchangé."""
    if not courbe:
        return p
    xs = [c[0] for c in courbe]
    ys = [c[1] for c in courbe]
    if p <= xs[0]:
        return min(1.0, max(0.0, ys[0] + (p - xs[0])))
    if p >= xs[-1]:
        return min(1.0, max(0.0, ys[-1] + (p - xs[-1])))
    i = bisect_right(xs, p)
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 if x1 == x0 else y0 + (y1 - y0) * (p - x0) / (x1 - x0)
