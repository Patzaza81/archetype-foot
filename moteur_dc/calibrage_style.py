"""Calibrage et validation de la matrice « fréquence des scores » (branche moteur-dc-style). Usage : python -m moteur_dc.calibrage_style apprendre

Protocole fixé AVANT le calcul (ordre de Patrick, 31/10/2026) :
1. APPRENTISSAGE de c = 1/k sur Football-Data 2025-26, marche avant (chaque match est prédit avec les seuls matchs d'avant). Critère :
   log-vraisemblance moyenne du score réel sous la grille mélangée. On part de c = 0 (Dixon-Coles pur) et on avance en doublant tant que
   la vraisemblance s'améliore (aucune borne posée à la main), puis on affine entre les deux meilleurs voisins.
2. VALIDATION sur Football-Data 2026-27 (jamais utilisé pour régler) : si le retrait de l'effet (c = 0) améliore ou égale la vraisemblance, c est remis à 0.
3. Sorties : docs/dc_style_validation.json ; moteur_dc/parametres.json ne reçoit `style_freq` que par l'option `ecrire`.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any

import numpy as np

from . import ajustements as AJ, calibrage as CAL, donnees as D, modele as MO, style as ST

SORTIE = CAL.ROOT / "docs" / "dc_style_validation.json"
N_TABLE = (4, 5, 6, 7, 10, 15, 20)


def _tableaux_style(res: list[dict]) -> dict[str, Any]:
    lh, la, rho, F, h, a = CAL._tableaux(res)
    return {"lh": lh, "la": la, "rho": rho, "F": F, "h": h, "a": a,
            "E": np.stack([r["E"] for r in res]), "n": np.array([r["n_style"] for r in res], dtype=float)}


def grilles_dc(T: dict[str, Any], effets: dict[str, float]) -> np.ndarray:
    return MO.grilles(*AJ.appliquer_vect(T["lh"], T["la"], T["rho"], T["F"], effets))


def ll_force(T: dict[str, Any], G: np.ndarray, c: float) -> float:
    g = ST.melanger(G, T["E"], ST.poids(T["n"], c))
    return float(np.mean(np.log(np.maximum(g[np.arange(len(T["h"])), T["h"], T["a"]], 1e-12))))


def chercher_force(T: dict[str, Any], G: np.ndarray, log=print) -> tuple[float, dict[float, float]]:
    """c = 0 (Dixon-Coles pur), puis doublement depuis 0,001 jusqu'à deux baisses consécutives (aucune borne posée à la main) ;
    affinage par dichotomie entre les voisins du meilleur."""
    cache: dict[float, float] = {}

    def s(c: float) -> float:
        c = round(c, 9)
        if c not in cache:
            cache[c] = ll_force(T, G, c)
            log(f"  c={c} (k={'inf' if c == 0 else round(1 / c, 3)}) : {cache[c]:.6f}")
        return cache[c]

    s(0.0)
    c, baisses, record = 0.001, 0, s(0.0)
    while baisses < 2:
        v = s(c)
        baisses = 0 if v > record else baisses + 1
        record = max(record, v)
        c *= 2
    for _ in range(10):
        ordre = sorted(cache)
        i = ordre.index(max(cache, key=cache.get))
        bas = ordre[i - 1] if i > 0 else None
        haut = ordre[i + 1] if i + 1 < len(ordre) else None
        for voisin in (bas, haut):
            if voisin is not None:
                s((ordre[i] + voisin) / 2)
    return max(cache, key=cache.get), cache


def table_poids(c: float) -> dict[str, float]:
    return {str(n): round(float(ST.poids(n, c)), 4) for n in N_TABLE}


def apprendre(ecrire: bool = False, log=print) -> dict[str, Any]:
    t0 = time.time()
    params = json.loads(CAL.PARAMS.read_text(encoding="utf-8"))
    bloc = D.charger_bloc()
    base = {"sigma": params["sigma"], "xi": params["xi"], "rho": params["rho"], "effets": params["effets"]}
    log(f"bloc Football-Data : {len(bloc)} matchs ; effets du Module 1 retenus : {params['effets']}")
    log("1. apprentissage de c sur 2025-26 (marche avant)")
    dev = _tableaux_style(CAL.marche_avant(CAL._regrouper([m for m in bloc if m["saison"] == "2526"]), base, avec_style=True))
    G_dev = grilles_dc(dev, params["effets"])
    c, courbe = chercher_force(dev, G_dev, log)
    log(f"   c appris = {c} (k = {'inf' if c == 0 else round(1 / c, 3)}) sur {len(dev['h'])} matchs")
    log("2. validation sur 2026-27")
    val = _tableaux_style(CAL.marche_avant(CAL._regrouper([m for m in bloc if m["saison"] == "2627"]), base, avec_style=True))
    G_val = grilles_dc(val, params["effets"])
    ll0, llc = ll_force(val, G_val, 0.0), ll_force(val, G_val, c)
    final = c if llc > ll0 else 0.0                      # règle fixée avant le calcul : le retrait qui égale ou améliore remet l'effet à 0
    log(f"   2026-27 ({len(val['h'])} matchs) : sans effet {ll0:.6f} ; avec c={c} {llc:.6f} ; retenu c={final}")
    out = {"c_appris": c, "k_appris": None if c == 0 else round(1 / c, 4), "c_retenu": final,
           "dev_2526": {"matchs": int(len(dev["h"])), "ll_sans_effet": round(float(courbe[0.0]), 6), "ll_avec": round(float(courbe[c]), 6),
                        "courbe": {str(x): round(v, 6) for x, v in sorted(courbe.items())}},
           "val_2627": {"matchs": int(len(val["h"])), "ll_sans_effet": round(ll0, 6), "ll_avec": round(llc, 6), "gain_par_match": round(llc - ll0, 6)},
           "w_appris": table_poids(c), "w_retenu": table_poids(final), "n_moyen_dev": round(float(dev["n"].mean()), 2),
           "n_median_dev": float(np.median(dev["n"])), "duree_s": round(time.time() - t0)}
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if ecrire:
        params["style_freq"] = {"c": final, "k": None if final == 0 else round(1 / final, 4), "appris": "Football-Data 2025-26, validé 2026-27"}
        CAL.PARAMS.write_text(json.dumps(params, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "apprendre"
    if mode == "apprendre":
        apprendre(ecrire="ecrire" in sys.argv[2:])
    else:
        print(__doc__)
