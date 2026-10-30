"""Module 4 du moteur DC : sélecteur statistique (spécification de Patrick, version corrigée). Aucune cote, aucun seuil de probabilité.

Pour chaque marché du match (P = probabilité du modèle, Base = fréquence du marché dans le championnat cette saison avant le match,
k/n = réussites/essais sur les matchs comparables : A à domicile + B à l'extérieur, score orienté) :
- Étape 0, cohérence (corrigée par Patrick le 30/10/2026) : rejeté si P sort de l'intervalle de Wilson à 95 % de p̂ = k/n (l'erreur
  d'échantillonnage de p̂ est prise en compte ; l'ancienne règle |P − p̂| ≤ 2 × EMAC = 0,011 rejetait tout) ;
- Étape 1, significativité : Z = (p̂ − Base) / √(Base(1 − Base)/n) ; admis si Z > Z_seuil, Z_seuil = quantile normal de 1 − 0,05/m,
  m = nombre de marchés testés sur le match (correction de Bonferroni) ;
- Étapes 2 et 3 : Edge = P − Base ; admis si Edge > EMAC ;
- Étape 4 : une seule issue par marché (groupe de la clé : 1N2, double chance, chaque ligne de buts, BTTS, Multigoal…), la plus probable ;
  en plus, jamais deux fois le même événement (même ensemble de scores gagnants, ex. « handicap +0,5 » et « ne perd pas »).
Sortie : marchés validés par PROBABILITÉ décroissante (réussite d'abord, Patrick 30/10/2026) ; pari principal = le plus probable.

EMAC = erreur de calibration du modèle : écart moyen |probabilité annoncée − fréquence observée| par dixième de probabilité, pondéré par le nombre
de prédictions (la formule reçue, moyenne de |P − Y| avec Y = 0 ou 1, vaut toujours 0,4 à 0,5 : elle ne mesure pas la calibration).
Mesurée hors échantillon au calibrage, puis sur les 30 derniers jours du journal gelé dès qu'il contient des matchs terminés (suivi.py).
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

from . import marches as M

ALPHA = 0.05                 # risque global de Patrick (Module 4) ; le seuil par marché en découle (Bonferroni)
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


def tester(l: dict[str, Any], emac: float, zs: float) -> tuple[bool, str]:
    pr, base, p = l.get("preuve"), l.get("base"), l["p"]
    if not pr or base is None:
        return False, "pas de matchs comparables ou pas de base du championnat"
    ph, n = pr["p_hat"], pr["n"]
    bas, haut = wilson(pr["k"], n)
    pr["wilson"] = [round(bas, 4), round(haut, 4)]
    if not bas <= p <= haut:
        return False, f"étape 0 : modèle {p:.0%} hors de l'intervalle de Wilson des données [{bas:.0%} ; {haut:.0%}] (p̂ = {ph:.0%}, n = {n})"
    z = z_score(ph, base, n)
    if z is None or z <= zs:
        return False, f"étape 1 : Z = {z if z is None else round(z, 2)} ≤ {zs:.2f} (Bonferroni)"
    edge = p - base
    if edge <= emac:
        return False, f"étape 3 : Edge {edge:+.3f} ≤ EMAC {emac:.3f}"
    return True, "validé"


def selectionner(a: dict[str, Any], emac: float) -> dict[str, Any]:
    if a["statut"] != "analyse":
        return {"principal": None, "autres": [], "raison": a.get("raison"), "m": 0, "z_seuil": None, "emac": emac}
    testes = [l for l in a["marches"] if l.get("preuve") and l.get("base") is not None]
    m = len(testes)
    zs = z_seuil(m)
    ok = []
    for l in a["marches"]:
        pr = l.get("preuve")
        l["edge"] = round(l["p"] - l["base"], 4) if l.get("base") is not None else None
        if pr:
            z = z_score(pr["p_hat"], l["base"], pr["n"]) if l.get("base") is not None else None
            pr["z"] = round(z, 2) if z is not None else None
        bon, raison = tester(l, emac, zs)
        l["decision"] = raison
        if bon:
            ok.append(l)
    ok.sort(key=lambda l: (-l["p"], -l["edge"]))
    garde, groupes, vus = [], {}, {}
    for l in ok:
        g = l["cle"][0]
        if g in groupes:
            l["decision"] = f"étape 4 : issue dominée par « {groupes[g]} » (même marché, plus probable)"
            continue
        sig = M.signature(tuple(l["cle"]))
        if sig in vus:
            l["decision"] = f"étape 4 : même événement que « {vus[sig]} »"
            continue
        groupes[g] = vus[sig] = l["marche"]
        garde.append(l)
    base = {"m": m, "z_seuil": round(zs, 3), "emac": emac}
    if not garde:
        return {"principal": None, "autres": [], "raison": "aucun marché ne passe le Module 4", **base}
    return {"principal": garde[0], "autres": garde[1:], "raison": None, **base}
