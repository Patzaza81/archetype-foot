"""Module 4 du moteur DC : sélecteur (option B de Patrick, 30/10/2026). Aucune cote.

Pour chaque marché du match (P = probabilité du modèle, Base = fréquence du marché dans le championnat cette saison avant le match,
k/n = réussites/essais sur les matchs comparables : A à domicile + B à l'extérieur, score orienté) :
- ordre de Patrick (30/10/2026) : 1. Edge = P − Base ≥ 10 % (et ≥ EMAC) ; 2. P ≥ seuil CALIBRÉ du marché (calibrage.seuils_par_marche) ;
- Bonferroni et Z supprimés comme filtre (le Z reste affiché) ;
- 3. intervalle de Wilson à 95 % de p̂, sur les seuls marchés validés : simple AVERTISSEMENT si P en sort (confiance réduite, classé après les paris sans avertissement) ;
- une seule issue par marché (la plus probable) et jamais deux fois le même événement (même ensemble de scores gagnants).
Sortie : paris sans avertissement d'abord, puis par PROBABILITÉ décroissante ; pari principal = le premier.

EMAC = erreur de calibration du modèle par dixième de probabilité (calibrage hors échantillon, puis 30 derniers jours du journal gelé).
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

from . import marches as M

ALPHA = 0.05                 # risque de l'intervalle de Wilson (95 %)
P_MIN = 0.60                 # Patrick : plancher P ≥ 60 %
EDGE_MIN = 0.10              # Patrick : Edge ≥ 10 %
REUSSITE_CIBLE = 0.70        # Patrick (30/10/2026) : seuil d'un marché = plus petite probabilité à partir de laquelle la réussite observée atteint 70 %
Z_WILSON = NormalDist().inv_cdf(1 - ALPHA / 2)     # intervalle de Wilson à 95 % (même risque α)


def wilson(k: int, n: int, z: float = Z_WILSON) -> tuple[float, float]:
    if not n:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - r), min(1.0, c + r)


def z_seuil(m: int) -> float:
    return NormalDist().inv_cdf(1 - ALPHA / max(m, 1))


def z_score(p_hat: float, base: float, n: int) -> float | None:
    if not n or base is None or not 0 < base < 1:
        return None
    return (p_hat - base) / math.sqrt(base * (1 - base) / n)


def tester(l: dict[str, Any], emac: float, zs: float | None = None, seuil: float | None = P_MIN) -> tuple[bool, str]:
    """1. Edge = P − Base ≥ 10 % ; 2. P ≥ seuil calibré du marché (None = le marché n'a jamais atteint 70 % de réussite sur l'échantillon) ;
    3. Wilson = avertissement sur les validés."""
    pr, base, p = l.get("preuve"), l.get("base"), l["p"]
    l["avertissement"] = None
    l["seuil"] = seuil
    if base is None:
        return False, "pas de base du championnat"
    edge = round(p - base, 9)                      # arrondi : 0,75 − 0,65 doit valoir 0,10, pas 0,0999…
    if edge < max(EDGE_MIN, emac):
        return False, f"Edge {edge:+.1%} < {max(EDGE_MIN, emac):.0%}"
    if seuil is None:
        return False, f"P sans seuil : ce marché n'atteint jamais {REUSSITE_CIBLE:.0%} de réussite sur l'échantillon"
    if p < seuil:
        return False, f"P {p:.0%} < seuil du marché {seuil:.0%}"
    if pr:
        bas, haut = wilson(pr["k"], pr["n"])
        pr["wilson"] = [round(bas, 4), round(haut, 4)]
        if not bas <= p <= haut:
            l["avertissement"] = f"confiance réduite : modèle {p:.0%} hors de l'intervalle de Wilson des données [{bas:.0%} ; {haut:.0%}] (p̂ = {pr['p_hat']:.0%}, n = {pr['n']})"
    return True, "validé" + (" (avertissement)" if l["avertissement"] else "")


def selectionner(a: dict[str, Any], emac: float, seuils: dict[str, Any] | None = None) -> dict[str, Any]:
    """`seuils` = seuils calibrés par marché ({"groupe|sélection": {"seuil": …}}) ; absent : plancher commun P_MIN."""
    if a["statut"] != "analyse":
        return {"principal": None, "autres": [], "raison": a.get("raison"), "m": 0, "z_seuil": None, "emac": emac}
    testes = [l for l in a["marches"] if l.get("preuve") and l.get("base") is not None]
    m = len(testes)
    zs = None
    ok = []
    for l in a["marches"]:
        pr = l.get("preuve")
        l["edge"] = round(l["p"] - l["base"], 4) if l.get("base") is not None else None
        if pr:
            z = z_score(pr["p_hat"], l["base"], pr["n"]) if l.get("base") is not None else None
            pr["z"] = round(z, 2) if z is not None else None
        seuil = P_MIN if seuils is None else (seuils.get(f"{l['cle'][0]}|{l['cle'][1]}") or {}).get("seuil")
        bon, raison = tester(l, emac, zs, seuil)
        l["decision"] = raison
        if bon:
            ok.append(l)
    ok.sort(key=lambda l: (l.get("avertissement") is not None, -l["p"], -l["edge"]))
    garde, groupes, vus = [], {}, {}
    for l in ok:
        g = l["cle"][0]
        if g in groupes:
            l["decision"] = f"exclusion : issue dominée par « {groupes[g]} » (même marché, plus probable)"
            continue
        sig = M.signature(tuple(l["cle"]))
        if sig in vus:
            l["decision"] = f"exclusion : même événement que « {vus[sig]} »"
            continue
        groupes[g] = vus[sig] = l["marche"]
        garde.append(l)
    base = {"m": m, "z_seuil": None, "emac": emac}
    if not garde:
        return {"principal": None, "autres": [], "raison": "aucun marché ne passe le Module 4", **base}
    return {"principal": garde[0], "autres": garde[1:], "raison": None, **base}
