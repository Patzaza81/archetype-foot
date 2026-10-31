"""Règle n°1 du moteur Gamma (Patrick, 31/10/2026) : compatibilité des comportements historiques. Protocole : docs/DC_COMPATIBILITE_PROTOCOLE.md.

Ce module extrait, en marche avant strict (mêmes ajustements que calibrage.marche_avant), pour chaque match du bloc et chacun des 103 marchés :
- P (Dixon-Coles avec les effets en vigueur de parametres.json) ;
- k_dom/n_dom : réussites du marché sur les matchs passés de A à domicile ; k_ext/n_ext : idem pour B à l'extérieur (score orienté du point de vue du match).
Aucune probabilité Dixon-Coles n'entre dans la compatibilité (pas de circularité).
Usage : python -m moteur_dc.compatibilite extraire  → data/dc/compat_lignes.pkl (ignoré par git)
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from . import ajustements as AJ, coeur, contrat as C, donnees as D, modele as MO, module1 as M1

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "data" / "dc" / "compat_lignes.pkl"


def effectifs_cotes(c: dict[str, Any]) -> tuple[np.ndarray, int, np.ndarray, int]:
    """(k_dom, n_dom, k_ext, n_ext) par marché ; mêmes matchs comparables que coeur.effectifs, séparés par équipe."""
    sd = [(x["buts_pour"], x["buts_contre"]) for x in c["equipe_domicile"]["historique_matchs_dom"]]
    se = [(x["buts_contre"], x["buts_pour"]) for x in c["equipe_exterieur"]["historique_matchs_ext"]]
    kd = np.einsum("ij,kij->k", coeur.comptes(sd), coeur.MASQUES) if sd else np.zeros(len(coeur.CLES))
    ke = np.einsum("ij,kij->k", coeur.comptes(se), coeur.MASQUES) if se else np.zeros(len(coeur.CLES))
    return kd.astype(np.int16), len(sd), ke.astype(np.int16), len(se)


def extraire(par_ligue: dict[str, list[dict]], p: dict[str, Any], pas_jours: int = 7, log=print) -> list[dict[str, Any]]:
    k = p.get("effets") or AJ.NEUTRES
    out: list[dict[str, Any]] = []
    for nl, (lg, ms) in enumerate(par_ligue.items()):
        ms = sorted(ms, key=lambda m: m["date"])
        depart = date.fromisoformat(ms[0]["date"])
        semaines: dict[date, list[dict]] = defaultdict(list)
        for m in ms:
            semaines[depart + timedelta(days=((date.fromisoformat(m["date"]) - depart).days // pas_jours) * pas_jours)].append(m)
        fit, passe = None, []
        for debut in sorted(semaines):
            jour = debut.isoformat()
            if passe:
                t = M1.tableau(passe, jour)
                dom, ext = [m["dom"] for m in passe], [m["ext"] for m in passe]
                fit = MO.ajuster(dom, ext, np.array([m["h"] for m in passe]), np.array([m["a"] for m in passe]),
                                 np.array([D.jours(m["date"], jour) for m in passe]), p["sigma"], p["xi"], fit, p["rho"],
                                 AJ.mult_xi(dom, ext, AJ.dynamique(t), k.get("forme", 0.0)))
                for m in semaines[debut]:
                    try:
                        c = C.construire(passe, m["dom"], m["ext"], jour, t, m["id"])
                    except ValueError:
                        continue
                    lh, la = fit.lambdas(m["dom"], m["ext"])
                    f = AJ.facteurs(c, t, AJ.excedents(passe, m["dom"], m["ext"], jour, t, fit))
                    lh2, la2, rho = AJ.appliquer(lh, la, fit.rho, f, k)
                    P = np.einsum("ij,kij->k", MO.grille(lh2, la2, rho), coeur.MASQUES)
                    kd, nd, ke, ne = effectifs_cotes(c)
                    out.append({"ligue": lg, "saison": m["saison"], "date": m["date"], "id": m["id"], "h": m["h"], "a": m["a"],
                                "P": P.astype(np.float32), "kd": kd, "nd": nd, "ke": ke, "ne": ne})
            passe.extend(semaines[debut])
        if nl % 20 == 0:
            log(f"  {nl + 1}/{len(par_ligue)} ligues, {len(out)} lignes")
    return out


def main() -> None:
    t0 = time.time()
    p = json.loads((Path(__file__).with_name("parametres.json")).read_text(encoding="utf-8"))
    bloc = D.charger_bloc()
    par: dict[str, list[dict]] = defaultdict(list)
    for m in bloc:
        par[m["ligue"]].append(m)
    lignes = extraire(par, p)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(lignes, open(SORTIE, "wb"))
    print(f"{len(lignes)} matchs ({sorted({l['saison'] for l in lignes})}) en {time.time() - t0:.0f} s → {SORTIE}")


if __name__ == "__main__":
    if sys.argv[1:] == ["extraire"]:
        main()
    else:
        print(__doc__)
