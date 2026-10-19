"""Comprendre le comportement d'un match (SANS cote), puis en déduire la probabilité de TOUS les marchés.

Étape 1 (profil) : à partir des derniers matchs des deux équipes (croisement marqués / encaissés), de la robustesse aux scores
extrêmes et, en option, du classement, on estime les buts attendus de chaque équipe, puis on décrit le match :
favori, niveau de buts (offensif / défensif / équilibré), match ouvert ou fermé, présence de scores extrêmes.
Étape 2 (distribution) : buts attendus -> distribution des scores (Poisson) -> probabilité de n'importe quel marché.
Aucune cote n'intervient ici. Lecture seule, aucune règle activée.
"""
from __future__ import annotations

import math
from typing import Any

MU_DOM, MU_EXT = 1.50, 1.20      # moyennes de référence (buts par match à domicile / à l'extérieur) ; ajustées par `calibrer_parametres`
SHRINK = 2.0                     # poids (en matchs) de la moyenne de référence : peu de matchs -> on se rapproche de la référence
CAP = 4                          # un score extrême est plafonné à CAP buts par match
RANK_K = 0.0                     # effet du classement (0 = désactivé) ; activé seulement si les chiffres le justifient
RHO = 0.0                        # correction Dixon-Coles des petits scores (0 = aucun)
GRID = 11                        # scores de 0 à 10 buts par équipe


def _moyenne_robuste(valeurs: list[int], mu: float, shrink: float, cap: int) -> float:
    capped = [min(v, cap) for v in valeurs]
    return (sum(capped) + shrink * mu) / (len(capped) + shrink)


def buts_attendus(dom: list[tuple[int, int]], ext: list[tuple[int, int]], rang_dom: int | None = None, rang_ext: int | None = None, *,
                  mu_dom: float = MU_DOM, mu_ext: float = MU_EXT, shrink: float = SHRINK, cap: int = CAP, rank_k: float = RANK_K) -> tuple[float, float]:
    """Croisement : le domicile marque ~ (ce qu'il marque + ce que l'extérieur encaisse) / 2, et réciproquement."""
    att_d = _moyenne_robuste([g for g, _ in dom], mu_dom, shrink, cap)
    def_d = _moyenne_robuste([c for _, c in dom], mu_ext, shrink, cap)   # buts que le domicile encaisse (référence : buts de l'extérieur)
    att_e = _moyenne_robuste([g for g, _ in ext], mu_ext, shrink, cap)
    def_e = _moyenne_robuste([c for _, c in ext], mu_dom, shrink, cap)   # buts que l'extérieur encaisse (référence : buts du domicile)
    lam_d, lam_e = (att_d + def_e) / 2.0, (att_e + def_d) / 2.0
    if rank_k and rang_dom and rang_ext:
        ecart = max(-1.0, min(1.0, (rang_ext - rang_dom) / 20.0))      # > 0 : le domicile est mieux classé
        lam_d, lam_e = lam_d * math.exp(rank_k * ecart), lam_e * math.exp(-rank_k * ecart)
    return lam_d, lam_e


def grille(lam_d: float, lam_e: float, rho: float = RHO, n: int = GRID) -> list[list[float]]:
    def pois(k: int, lam: float) -> float:
        return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1)) if lam > 0 else float(k == 0)
    g = [[pois(i, lam_d) * pois(j, lam_e) for j in range(n)] for i in range(n)]
    if rho:
        g[0][0] *= 1 - lam_d * lam_e * rho
        g[0][1] *= 1 + lam_d * rho
        g[1][0] *= 1 + lam_e * rho
        g[1][1] *= 1 - rho
    total = sum(map(sum, g))
    return [[v / total for v in row] for row in g]


def proba(g: list[list[float]], test) -> float:
    """Probabilité que le score (i, j) vérifie `test(i, j)`."""
    return sum(p for i, row in enumerate(g) for j, p in enumerate(row) if test(i, j))


def profil(dom: list[tuple[int, int]], ext: list[tuple[int, int]], rang_dom: int | None = None, rang_ext: int | None = None, **params) -> dict[str, Any]:
    lam_d, lam_e = buts_attendus(dom, ext, rang_dom, rang_ext, **params)
    g = grille(lam_d, lam_e, params.get("rho", RHO))
    p1, pn, p2 = proba(g, lambda i, j: i > j), proba(g, lambda i, j: i == j), proba(g, lambda i, j: i < j)
    total = lam_d + lam_e
    if p1 >= 0.50 and p1 - p2 >= 0.25:
        favori = "domicile"
    elif p2 >= 0.45 and p2 - p1 >= 0.20:
        favori = "extérieur"
    else:
        favori = "équilibré"
    extremes = [f"{team} {g_}-{c}" for team, rows in (("domicile", dom), ("extérieur", ext)) for g_, c in rows if g_ >= 5 or c >= 5 or abs(g_ - c) >= 4]
    return {
        "buts_attendus": (round(lam_d, 2), round(lam_e, 2)), "total_attendu": round(total, 2),
        "victoire_dom": round(p1, 3), "nul": round(pn, 3), "victoire_ext": round(p2, 3), "favori": favori,
        "buts": "offensif" if total >= 3.0 else ("défensif" if total <= 2.2 else "équilibré"),
        "deux_marquent": round(proba(g, lambda i, j: i >= 1 and j >= 1), 3),
        "scores_extremes": extremes, "grille": g,
    }
