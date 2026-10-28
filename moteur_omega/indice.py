"""Indice de réserve d'un pari (moteur omega) — idée de Patrick du 28/10/2026.

Pour chaque match passé d'une équipe au même lieu, on mesure la DISTANCE AU BASCULEMENT du pari : le nombre minimal de buts à changer
dans le score pour que le pari change d'issue (distance L1 sur la grille des scores). Elle est positive si le pari passait, négative
sinon. Elle s'adapte seule à chaque marché (totaux, buts d'une équipe, résultats, handicaps, combinés) puisqu'elle s'appuie sur la
règle du marché elle-même (`marches.test_du_marche`) et sur les scores réels : aucun seuil choisi à la main.

Indice d'une équipe = moyenne de deux fréquences : part des matchs où le pari passait (distance >= 1) et part des matchs où il passait
avec au moins un but de réserve (distance >= 2). Indice du pari = moyenne des indices des deux équipes (même poids).
Les scores sont vus du côté du domicile : domicile = (marqués, encaissés), extérieur = (encaissés, marqués).
Affichage seulement : ne modifie ni la sélection ni les pronostics gelés.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from . import marches as M

N = 10   # grille 0..N ; les scores plus grands sont ramenés à N (même issue pour tous les marchés du catalogue)


@lru_cache(maxsize=None)
def table_distances(cle: tuple[str, str]) -> tuple[tuple[int, ...], ...] | None:
    """table[i][j] = distance signée au basculement du score (i, j) pour ce marché (None si marché inconnu)."""
    t = M.test_du_marche(*cle)
    if t is None:
        return None
    ok = [[bool(t(i, j)) for j in range(N + 1)] for i in range(N + 1)]
    lignes = []
    for i in range(N + 1):
        ligne = []
        for j in range(N + 1):
            d = min((abs(i - x) + abs(j - y) for x in range(N + 1) for y in range(N + 1) if ok[x][y] != ok[i][j]), default=2 * N + 1)
            ligne.append(d if ok[i][j] else -d)
        lignes.append(tuple(ligne))
    return tuple(lignes)


def distance(cle: tuple[str, str], h: int, a: int) -> int | None:
    tb = table_distances(tuple(cle))
    return None if tb is None else tb[min(int(h), N)][min(int(a), N)]


def indice_equipe(cle: tuple[str, str], scores: list[tuple[int, int]]) -> dict[str, Any] | None:
    """scores = [(buts domicile, buts extérieur), ...] des matchs passés de l'équipe au même lieu, vus du côté du domicile."""
    d = [distance(cle, h, a) for h, a in scores]
    if not d or any(x is None for x in d):
        return None
    f1 = sum(x >= 1 for x in d) / len(d)
    f2 = sum(x >= 2 for x in d) / len(d)
    return {"passe": f1, "passe_avec_reserve": f2, "indice": (f1 + f2) / 2, "n": len(d)}


def scores_series(s: dict[str, list[int]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """(scores des matchs à domicile du domicile, scores des matchs à l'extérieur de l'extérieur), tous vus du côté du domicile."""
    dom = list(zip(s["dom_marques"], s["dom_encaisses"]))
    ext = [(e, m) for m, e in zip(s["ext_marques"], s["ext_encaisses"])]
    return dom, ext


def indice_pari(cle: tuple[str, str], s: dict[str, list[int]]) -> dict[str, Any] | None:
    dom, ext = scores_series(s)
    a, b = indice_equipe(cle, dom), indice_equipe(cle, ext)
    if a is None or b is None:
        return None
    return {"indice": round((a["indice"] + b["indice"]) / 2, 4), "passe": round((a["passe"] + b["passe"]) / 2, 4),
            "passe_avec_reserve": round((a["passe_avec_reserve"] + b["passe_avec_reserve"]) / 2, 4),
            "dom": {k: round(v, 4) if isinstance(v, float) else v for k, v in a.items()},
            "ext": {k: round(v, 4) if isinstance(v, float) else v for k, v in b.items()}}
