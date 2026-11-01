"""Module 4 du moteur DC : sélecteur (option B de Patrick, 30/10/2026). Aucune cote.

Pour chaque marché du match (P = probabilité du modèle, Base = fréquence du marché dans le championnat cette saison avant le match,
k/n = réussites/essais sur les matchs comparables : A à domicile + B à l'extérieur, score orienté) :
- ordre de Patrick (30/10/2026) : 1. Edge = P − Base ≥ 10 % (et ≥ EMAC) ; 2. P ≥ seuil CALIBRÉ du marché (calibrage.seuils_par_marche) ;
- Bonferroni et Z supprimés comme filtre (le Z reste affiché) ;
- 3. cote BetPawa ≥ 1,26 ; cote absente = rejet ;
- 3 bis (audit du 01/11/2026, ordre de Patrick) : EV = P × cote − 1 > 0 (un pari à l'espérance négative selon le modèle est rejeté) ;
- 4. AVERTISSEMENT (affiché, ne change ni la décision ni l'ordre) si P sort de l'intervalle de l'ESTIMATION COMBINÉE des matchs comparables.
  Les deux populations (A à domicile, B à l'extérieur) ne sont JAMAIS additionnées en un k/n : chacune garde son k/n et son intervalle de Wilson ;
  l'estimation combinée est une moyenne pondérée par l'inverse de la variance (Agresti-Coull), présentée comme une estimation, pas comme une fréquence ;
- une seule issue par marché (la plus rentable) et jamais deux fois le même événement (même ensemble de scores gagnants).
Sortie : TOUS les paris validés, par EV décroissante (à EV égale, par probabilité) ; pari principal = celui de plus forte EV. Tous sont gelés et réglés (suivi.py).

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
COTE_MIN = 1.26              # Module 5 de Patrick : cote BetPawa minimale (EV et Kelly restent écartés) ; cote absente = pari injouable
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


def ev(p: float, cote: float | None) -> float | None:
    """Espérance de gain d'une mise de 1 selon le modèle : P × cote − 1."""
    return None if cote is None else p * cote - 1


def estimation_combinee(pr: dict[str, Any]) -> dict[str, Any]:
    """Estimation (PAS une fréquence observée) du taux de l'événement à partir des deux populations séparées : moyenne pondérée par l'inverse
    de la variance de chacune (proportion corrigée Agresti-Coull : (k + 2) / (n + 4), variance p(1 − p) / (n + 4), définie même si k = 0 ou k = n)."""
    def ac(x: dict[str, Any]) -> tuple[float, float]:
        q = (x["k"] + 2) / (x["n"] + 4)
        return q, q * (1 - q) / (x["n"] + 4)
    (pd, vd), (pe, ve) = ac(pr["dom"]), ac(pr["ext"])
    wd, we = 1 / vd, 1 / ve
    se = math.sqrt(1 / (wd + we))
    p = (wd * pd + we * pe) / (wd + we)
    return {"p": round(p, 4), "se": round(se, 4), "ic": [round(max(0.0, p - Z_WILSON * se), 4), round(min(1.0, p + Z_WILSON * se), 4)],
            "methode": "moyenne pondérée par l'inverse de la variance des deux populations (Agresti-Coull)"}


def z_score(est: dict[str, Any] | None, base: float) -> float | None:
    """Écart de l'estimation combinée à la base du championnat, en erreurs-types de l'estimation."""
    if not est or base is None or not est["se"]:
        return None
    return (est["p"] - base) / est["se"]


def tester(l: dict[str, Any], emac: float, zs: float | None = None, seuil: float | None = P_MIN, filtre_ev: bool = True) -> tuple[bool, str]:
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
    cote = l.get("cote")
    if cote is None:
        return False, "cote BetPawa absente : pari injouable"
    if cote < COTE_MIN:
        return False, f"cote {cote:.2f} < {COTE_MIN:.2f}".replace(".", ",")
    gain = ev(p, cote)
    l["ev"] = round(gain, 4)
    if filtre_ev and gain <= 0:                      # filtre_ev=False : comparaison « avant l'audit » (audit.py) seulement
        return False, f"EV {gain:+.1%} ≤ 0 (P {p:.0%} × cote {cote:.2f} − 1)"
    if pr:
        est = pr.get("estimation")
        if est and not est["ic"][0] <= p <= est["ic"][1]:
            l["avertissement"] = (f"confiance réduite : modèle {p:.0%} hors de l'intervalle de l'estimation combinée des matchs comparables "
                                  f"[{est['ic'][0]:.0%} ; {est['ic'][1]:.0%}] (estimation {est['p']:.0%})")
    return True, "validé" + (" (avertissement)" if l["avertissement"] else "")


def selectionner(a: dict[str, Any], emac: float, seuils: dict[str, Any] | None = None, regle: str = "ev") -> dict[str, Any]:
    """`seuils` = seuils calibrés par marché ({"groupe|sélection": {"seuil": …}}) ; absent : plancher commun P_MIN.
    `regle` : « ev » (production depuis le 01/11/2026) ; « probabilite » = ancienne règle (sans filtre EV, tri par probabilité), gardée pour mesurer l'audit."""
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
            for pop in ("dom", "ext"):
                bas, haut = wilson(pr[pop]["k"], pr[pop]["n"])
                pr[pop]["wilson"] = [round(bas, 4), round(haut, 4)]
            pr["estimation"] = estimation_combinee(pr)
            z = z_score(pr["estimation"], l["base"]) if l.get("base") is not None else None
            pr["z"] = round(z, 2) if z is not None else None
        l["ev"] = round(ev(l["p"], l.get("cote")), 4) if l.get("cote") is not None else None
        seuil = P_MIN if seuils is None else (seuils.get(f"{l['cle'][0]}|{l['cle'][1]}") or {}).get("seuil")
        bon, raison = tester(l, emac, zs, seuil, regle == "ev")
        l["decision"] = raison
        if bon:
            ok.append(l)
    if regle == "ev":
        ok.sort(key=lambda l: (-l["ev"], -l["p"]))               # audit du 01/11/2026 : EV décroissante
    else:
        ok.sort(key=lambda l: (-l["p"], -l["edge"]))             # ancienne règle : le plus probable en tête
    garde, groupes, vus = [], {}, {}
    for l in ok:
        g = l["cle"][0]
        if g in groupes:
            l["decision"] = f"exclusion : issue dominée par « {groupes[g]} » (même marché, EV plus forte)"
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
