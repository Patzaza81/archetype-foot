"""Calibrage du moteur DC — protocole fixé AVANT le calcul. Usage : python -m moteur_dc.calibrage [tout|reprise|seuils]

1. HYPERPARAMÈTRES du Dixon-Coles (σ de la pénalité, xi, ρ commun) : Football-Data 2025-26, vraisemblance PRÉDICTIVE hors échantillon
   (marche avant : ajustement avec les matchs d'avant chaque semaine, notation des scores de la semaine). Recherche par coordonnées sur une grille
   de candidats. `reprise` réutilise ceux déjà appris (docs/dc_validation.json).
2. FORCES DES EFFETS du Module 1 branchés dans le Module 2 (ajustements.py : forme, ie, amplitude, modal, style), même marche avant sur 2025-26 :
   recherche par coordonnées (deux passages) ; chaque force part de 0 (sans effet) et la grille s'étend tant que la vraisemblance s'améliore
   (aucune borne posée à la main). Seuls les matchs qui passent le contrat 1.5 (Filtre 0 compris) sont notés.
3. VALIDATION sur Football-Data 2026-27 (jamais utilisé pour régler) : vraisemblance avec et sans chaque effet. Règle fixée avant le calcul :
   un effet dont le retrait AMÉLIORE la vraisemblance 2026-27 est remis à 0 (il n'a pas tenu hors échantillon). Perte logarithmique par famille
   contre le taux de base ; erreur de calibration par dixième de probabilité.
4. EMAC (Module 4) = erreur de calibration pondérée par tranche, mesurée sur 2026-27 avec le modèle final.
5. CONTRÔLE du Module 4 sur l'archive ARCHETYPE (coupée au 14/10/2026 : développement / réserve) : nombre de paris, réussite, étape où les
   marchés tombent. Ce n'est PAS un bilan de performance : le bilan réel vient du journal gelé (bilan_reel.py).
Sorties : moteur_dc/parametres.json, docs/dc_validation.json.
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from . import ajustements as AJ, coeur, contrat as C, donnees as D, marches as M, modele as MO, module1 as M1, selecteur as S

ROOT = Path(__file__).resolve().parent.parent
PARAMS = Path(__file__).with_name("parametres.json")
VALIDATION = ROOT / "docs" / "dc_validation.json"
COUPE_ARCHIVE = "2026-10-14"
SIGMAS = (0.15, 0.25, 0.4, 0.6, 1.0, 2.0)
RHOS = (-0.12, -0.08, -0.04, 0.0, 0.04)
XIS = (0.0, 0.002, 0.004, 0.008, 0.016)
PAS = {"forme": 0.5, "ie": 0.1, "amplitude": 0.01, "modal": 0.02, "style": 0.05}   # pas de recherche (la grille s'étend sans borne)
VERSION = "2.0.0"


def _regrouper(matchs: list[dict]) -> dict[str, list[dict]]:
    d: dict[str, list[dict]] = defaultdict(list)
    for m in matchs:
        d[m["ligue"]].append(m)
    return d


def marche_avant(par_ligue: dict[str, list[dict]], p: dict[str, Any], avec_facteurs: bool = True, pas_jours: int = 7) -> list[dict[str, Any]]:
    """Prédictions hors échantillon semaine par semaine. Chaque ligne : λ et ρ AVANT effets, variables des effets, score réel."""
    out: list[dict[str, Any]] = []
    k = p.get("effets") or AJ.NEUTRES
    for lg, ms in par_ligue.items():
        ms = sorted(ms, key=lambda m: m["date"])
        depart = date.fromisoformat(ms[0]["date"])
        semaines: dict[date, list[dict]] = defaultdict(list)
        for m in ms:
            semaines[depart + timedelta(days=((date.fromisoformat(m["date"]) - depart).days // pas_jours) * pas_jours)].append(m)
        fit = None
        passe: list[dict] = []
        for debut in sorted(semaines):
            jour = debut.isoformat()
            if passe:
                t = M1.tableau(passe, jour)
                dom, ext = [m["dom"] for m in passe], [m["ext"] for m in passe]
                cible = any("hf" in m for m in passe)                    # cibles d'ajustement non entières (xG, harnais xG) : 'hf'/'af'
                fit = MO.ajuster(dom, ext, np.array([m.get("hf", m["h"]) for m in passe]), np.array([m.get("af", m["a"]) for m in passe]),
                                 np.array([D.jours(m["date"], jour) for m in passe]), p["sigma"], p["xi"], fit, p["rho"],
                                 AJ.mult_xi(dom, ext, AJ.dynamique(t), k.get("forme", 0.0)),
                                 (np.array([m["h"] for m in passe]), np.array([m["a"] for m in passe])) if cible else None)
                for m in semaines[debut]:
                    try:
                        c = C.construire(passe, m["dom"], m["ext"], jour, t, m["id"])
                    except ValueError:
                        continue
                    lh, la = fit.lambdas(m["dom"], m["ext"])
                    r = {"ligue": lg, "saison": m.get("saison"), "date": m["date"], "id": m["id"], "h": m["h"], "a": m["a"], "lh": lh, "la": la, "rho": fit.rho}
                    if avec_facteurs:
                        r["f"] = AJ.facteurs(c, t, AJ.excedents(passe, m["dom"], m["ext"], jour, t, fit))
                    out.append(r)
            passe.extend(semaines[debut])
    return out


def _tableaux(res: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, np.ndarray], np.ndarray, np.ndarray]:
    lh = np.array([r["lh"] for r in res])
    la = np.array([r["la"] for r in res])
    rho = np.array([r["rho"] for r in res])
    F = {k: np.array([r["f"][k] for r in res]) for k in res[0]["f"]}
    return lh, la, rho, F, np.minimum([r["h"] for r in res], MO.N_BUTS), np.minimum([r["a"] for r in res], MO.N_BUTS)


def ll_moyenne(T: tuple, k: dict[str, float]) -> float:
    lh, la, rho, F, h, a = T
    g = MO.grilles(*AJ.appliquer_vect(lh, la, rho, F, k))
    return float(np.mean(np.log(np.maximum(g[np.arange(len(h)), h, a], 1e-12))))


def recherche_1d(score, k: dict[str, float], nom: str) -> dict[str, float]:
    """Meilleure force pour un effet, les autres fixées : on part de la valeur courante et on avance par pas tant que ça s'améliore."""
    pas = PAS[nom]
    cache: dict[float, float] = {}

    def s(v: float) -> float:
        v = round(v, 6)
        if v not in cache:
            cache[v] = score({**k, nom: v})
        return cache[v]

    v = k.get(nom, 0.0)
    for sens in (1, -1):
        while s(v + sens * pas) > s(v):
            v += sens * pas
    return {**k, nom: round(v, 6)}


def hyperparametres(bloc: list[dict], log=print) -> dict[str, Any]:
    par_ligue = _regrouper([m for m in bloc if m["saison"] == "2526"])
    essais: dict[tuple, float] = {}

    def score(s: float, x: float, r: float) -> float:
        if (s, x, r) not in essais:
            res = marche_avant(par_ligue, {"sigma": s, "xi": x, "rho": r}, avec_facteurs=False)
            essais[(s, x, r)] = float(np.mean([math.log(max(MO.grille(q["lh"], q["la"], q["rho"])[min(q["h"], 10), min(q["a"], 10)], 1e-12)) for q in res]))
            log(f"  sigma={s} xi={x} rho={r} : {essais[(s, x, r)]:.5f}")
        return essais[(s, x, r)]

    s_b, x_b, r_b = SIGMAS[2], XIS[0], RHOS[2]
    s_b = max(SIGMAS, key=lambda s: score(s, x_b, r_b))
    x_b = max(XIS, key=lambda x: score(s_b, x, r_b))
    r_b = max(RHOS, key=lambda r: score(s_b, x_b, r))
    s_b = max(SIGMAS, key=lambda s: score(s, x_b, r_b))
    return {"sigma": s_b, "xi": x_b, "rho": r_b, "ll": essais[(s_b, x_b, r_b)], "essais": {f"{s}|{x}|{r}": v for (s, x, r), v in essais.items()}}


def apprendre_effets(bloc: list[dict], hp: dict[str, Any], log=print) -> tuple[dict[str, float], dict[str, Any]]:
    par_ligue = _regrouper([m for m in bloc if m["saison"] == "2526"])
    traces: dict[str, Any] = {"essais_forme": {}}
    runs: dict[float, tuple] = {}

    def run(c_forme: float) -> tuple:
        c_forme = round(c_forme, 6)
        if c_forme not in runs:
            t0 = time.time()
            res = marche_avant(par_ligue, {**hp, "effets": {"forme": c_forme}})
            runs[c_forme] = _tableaux(res)
            log(f"  forme={c_forme} : marche avant {len(res)} matchs ({time.time() - t0:.0f} s)")
        return runs[c_forme]

    k = dict(AJ.NEUTRES)
    for passage in (1, 2):
        k = recherche_1d(lambda kk: ll_moyenne(run(kk["forme"]), kk), k, "forme")
        traces["essais_forme"].update({str(c): None for c in runs})
        for nom in ("ie", "amplitude", "modal", "style"):
            T = run(k["forme"])
            k = recherche_1d(lambda kk: ll_moyenne(T, kk), k, nom)
        log(f"  passage {passage} : {k} → {ll_moyenne(run(k['forme']), k):.5f} (sans effet : {ll_moyenne(run(0.0), AJ.NEUTRES):.5f})")
    traces["ll_dev_sans_effet"] = round(ll_moyenne(run(0.0), AJ.NEUTRES), 5)
    traces["ll_dev_avec_effets"] = round(ll_moyenne(run(k["forme"]), k), 5)
    traces["matchs_dev"] = int(len(run(0.0)[0]))
    return k, traces


def _resultats(h: np.ndarray, a: np.ndarray) -> np.ndarray:
    return np.stack([MO.masque(c, coeur.TESTS[c])[h, a] for c in coeur.CLES], axis=1)


def tranches(p: np.ndarray, y: np.ndarray) -> list[dict[str, Any]]:
    out = []
    for k in range(10):
        m = (p >= k / 10) & ((p < (k + 1) / 10) if k < 9 else (p <= 1))
        if m.sum():
            out.append({"tranche": f"{k * 10}-{(k + 1) * 10}%", "n": int(m.sum()), "annonce": round(float(p[m].mean()), 4),
                        "observe": round(float(y[m].mean()), 4), "ecart": round(float(p[m].mean() - y[m].mean()), 4)})
    return out


def emac(p: np.ndarray, y: np.ndarray) -> float:
    """Erreur de calibration : |annoncé − observé| par dixième de probabilité, pondéré par le nombre de prédictions."""
    tr = tranches(p, y)
    n = sum(t["n"] for t in tr)
    return round(sum(t["n"] * abs(t["ecart"]) for t in tr) / n, 4) if n else 0.0


def _perte(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))), float(np.mean((p - y) ** 2))


def valider(bloc: list[dict], hp: dict[str, Any], k: dict[str, float], log=print) -> tuple[dict[str, float], dict[str, Any]]:
    par_ligue = _regrouper([m for m in bloc if m["saison"] == "2627"])
    T = _tableaux(marche_avant(par_ligue, {**hp, "effets": k}))
    T0 = T if not k.get("forme") else _tableaux(marche_avant(par_ligue, {**hp, "effets": {"forme": 0.0}}))
    val: dict[str, Any] = {"matchs": int(len(T[0])), "ll_sans_effet": round(ll_moyenne(T0, AJ.NEUTRES), 5), "ll_avec_effets": round(ll_moyenne(T, k), 5),
                           "retrait": {}}
    final = dict(k)
    for nom in AJ.NOMS:
        if not k[nom]:
            continue
        sans = dict(k, **{nom: 0.0})
        ll = ll_moyenne(T0 if nom == "forme" else T, sans)
        val["retrait"][nom] = round(ll, 5)
        if ll > val["ll_avec_effets"]:                   # règle fixée avant le calcul
            final[nom] = 0.0
    if final != k:
        Tf = T0 if not final.get("forme") else T
        val["ll_final"] = round(ll_moyenne(Tf, final), 5)
    else:
        Tf = T
        val["ll_final"] = val["ll_avec_effets"]
    lh, la, rho, F, h, a = Tf
    P = np.einsum("nij,kij->nk", MO.grilles(*AJ.appliquer_vect(lh, la, rho, F, final)), coeur.MASQUES)
    Y = _resultats(h, a)
    dev = [m for m in bloc if m["saison"] == "2526"]
    base = np.einsum("ij,kij->k", coeur.comptes([(m["h"], m["a"]) for m in dev]), coeur.MASQUES) / len(dev)
    par_famille = {}
    for fam in sorted({M.famille(c) for c in coeur.CLES}):
        idx = [i for i, c in enumerate(coeur.CLES) if M.famille(c) == fam]
        lb, bb = _perte(P[:, idx].ravel(), Y[:, idx].ravel())
        lk, bk = _perte(np.broadcast_to(base[idx], (len(P), len(idx))).ravel(), Y[:, idx].ravel())
        par_famille[fam] = {"modele": {"perte_log": round(lb, 5), "brier": round(bb, 5)}, "taux_de_base": {"perte_log": round(lk, 5), "brier": round(bk, 5)}}
    val["par_famille"] = par_famille
    val["tranches"] = tranches(P.ravel(), Y.ravel())
    val["emac"] = emac(P.ravel(), Y.ravel())
    val["emac_par_famille"] = {fam: emac(P[:, [i for i, c in enumerate(coeur.CLES) if M.famille(c) == fam]].ravel(),
                                         Y[:, [i for i, c in enumerate(coeur.CLES) if M.famille(c) == fam]].ravel()) for fam in par_famille}
    log(f"  validation 2026-27 : {val['matchs']} matchs, sans effet {val['ll_sans_effet']}, avec {val['ll_avec_effets']}, final {val['ll_final']}, EMAC {val['emac']}")
    return final, val


def analyses_archive(params: dict[str, Any], log=print) -> list[dict[str, Any]]:
    ligues = D.charger_ligues()
    matchs = [m for m in D.charger_archive(ligues) if m["h"] is not None]
    par_jour: dict[tuple, list[dict]] = defaultdict(list)
    for m in matchs:
        par_jour[(m["ligue"], m["jour"])].append(m)
    out = []
    for (lg, jour), ms in sorted(par_jour.items(), key=lambda kv: kv[0][1]):
        liste = ligues.matchs.get(lg)
        if not liste:
            continue
        t = M1.tableau(liste, jour)
        fit = coeur.ajuster_ligue(liste, jour, params, t)
        if fit is None:
            continue
        bases = coeur.bases_ligue(liste, jour)
        for m in ms:
            a = coeur.analyser(m, liste, params, fit, t, bases)
            if a["statut"] == "analyse":
                out.append({"m": m, "a": a})
    log(f"  archive : {len(out)} matchs joués analysables")
    return out


def controle_archive(params: dict[str, Any], log=print) -> dict[str, Any]:
    an = analyses_archive(params, log)
    out: dict[str, Any] = {"coupe": COUPE_ARCHIVE}
    for nom, groupe in (("developpement", [x for x in an if x["m"]["jour"] < COUPE_ARCHIVE]), ("reserve", [x for x in an if x["m"]["jour"] >= COUPE_ARCHIVE])):
        etapes: Counter = Counter()
        principaux, tous = [], []
        for x in groupe:
            s = coeur.selectionner(x["a"], params)
            for l in x["a"]["marches"]:
                etapes[l["decision"].split(" :")[0]] += 1
            for q, l in enumerate(([s["principal"]] if s["principal"] else []) + s["autres"]):
                g = bool(coeur.TESTS[tuple(l["cle"])](x["m"]["h"], x["m"]["a"]))
                tous.append((g, l["p"]))
                if q == 0:
                    principaux.append((g, l["p"], l["cote"]))
        out[nom] = {"matchs": len(groupe), "paris_principaux": len(principaux), "tous_paris": len(tous), "etapes": dict(etapes)}
        if principaux:
            out[nom]["principal"] = {"reussite": round(sum(g for g, _, _ in principaux) / len(principaux), 4),
                                     "p_moyenne": round(float(np.mean([p for _, p, _ in principaux])), 4),
                                     "cotes_connues": sum(c is not None for _, _, c in principaux)}
        if tous:
            out[nom]["tous"] = {"reussite": round(sum(g for g, _ in tous) / len(tous), 4), "p_moyenne": round(float(np.mean([p for _, p in tous])), 4)}
        log(f"  {nom} : {out[nom]}")
    return out


PAS_SEUIL = 0.05                       # tranches de Patrick : [0,50-0,55], [0,55-0,60] … [0,95-1,00]
MIN_PARIS = 30                         # minimum de prédictions pour lire une réussite (règle déjà utilisée par ce moteur)


def _pav(n: list[int], k: list[float]) -> list[float]:
    """Réussite par tranche rendue croissante avec la probabilité (fusion des tranches voisines qui se contredisent, pondérée par n)."""
    blocs: list[list[float]] = []
    for ni, ki in zip(n, k):
        blocs.append([ni, ki, 1])
        while len(blocs) > 1 and blocs[-2][1] / blocs[-2][0] >= blocs[-1][1] / blocs[-1][0]:
            x = blocs.pop()
            blocs[-1] = [blocs[-1][0] + x[0], blocs[-1][1] + x[1], blocs[-1][2] + x[2]]
    out: list[float] = []
    for bl in blocs:
        out += [bl[1] / bl[0]] * int(bl[2])
    return out


def seuils_par_marche(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    """Pour chaque marché, sur les matchs JOUÉS de l'échantillon (archive, prédictions faites avec les seuls matchs d'avant) :
    tranches de 5 points à partir de 50 % et réussite observée par tranche. La réussite d'une tranche est lissée pour croître avec la
    probabilité (tranches voisines contradictoires fusionnées) : sans ce lissage, une moyenne cumulée laisse passer des tranches à 55-60 %
    de réussite noyées dans les tranches hautes. Seuil = début de la première tranche dont la réussite lissée atteint 70 %, avec au moins
    30 prédictions au-dessus. Aucun seuil : le marché n'est jamais validé."""
    out: dict[str, Any] = {}
    bornes = [round(0.5 + PAS_SEUIL * k, 2) for k in range(int(0.5 / PAS_SEUIL))]
    for i, c in enumerate(coeur.CLES):
        P = np.array([x["a"]["p_marches"][i] for x in analyses])
        Y = np.array([float(coeur.TESTS[c](x["m"]["h"], x["m"]["a"])) for x in analyses])
        tr = []
        for b in bornes:
            m = (P >= b) & ((P < b + PAS_SEUIL) if b < bornes[-1] else (P <= 1))
            if m.sum():
                tr.append({"debut": b, "tranche": f"{b:.2f}-{b + PAS_SEUIL:.2f}", "n": int(m.sum()), "gagnes": int(Y[m].sum()),
                           "p_moyenne": round(float(P[m].mean()), 4), "reussite": round(float(Y[m].mean()), 4)})
        lisse = _pav([t["n"] for t in tr], [t["gagnes"] for t in tr])
        seuil = None
        for t, r in zip(tr, lisse):
            t["reussite_lissee"] = round(r, 4)
            m = P >= t["debut"]
            if seuil is None and r >= S.REUSSITE_CIBLE and m.sum() >= MIN_PARIS:
                seuil = {"seuil": t["debut"], "reussite": round(float(Y[m].mean()), 4), "n": int(m.sum()), "p_moyenne": round(float(P[m].mean()), 4)}
        out[coeur.cle_txt(c)] = {**(seuil or {"seuil": None}), "marche": M.libelle(c), "predictions": len(P), "tranches": tr}
    return out


def calibrer_seuils(log=print) -> dict[str, Any]:
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    an = analyses_archive(params, log)
    seuils = seuils_par_marche(an)
    params["seuils_marche"] = {k: {kk: v[kk] for kk in ("seuil", "reussite", "n")} for k, v in seuils.items() if v["seuil"] is not None}
    params["seuils_echantillon"] = {"matchs": len(an), "du": min(x["m"]["jour"] for x in an), "au": max(x["m"]["jour"] for x in an)}
    PARAMS.write_text(json.dumps(params, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    val = json.loads(VALIDATION.read_text(encoding="utf-8"))
    val["seuils_par_marche"] = {"echantillon": params["seuils_echantillon"], "reussite_cible": S.REUSSITE_CIBLE, "min_predictions": MIN_PARIS, "marches": seuils}
    VALIDATION.write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  seuils : {len(params['seuils_marche'])} marchés sur {len(seuils)} ont un seuil ({len(an)} matchs)")
    return seuils


def tout(log=print, reprise: bool = False) -> None:
    t0 = time.time()
    bloc = D.charger_bloc()
    log(f"bloc Football-Data : {len(bloc)} matchs")
    if reprise:
        hp = json.loads(VALIDATION.read_text(encoding="utf-8"))["hyperparametres"]
        log(f"1. hyperparamètres repris : sigma={hp['sigma']} xi={hp['xi']} rho={hp['rho']}")
    else:
        log("1. hyperparamètres")
        hp = hyperparametres(bloc, log)
    base = {"sigma": hp["sigma"], "xi": hp["xi"], "rho": hp["rho"]}
    log("2. forces des effets du Module 1 (2025-26)")
    k, traces = apprendre_effets(bloc, base, log)
    log("3-4. validation 2026-27 et EMAC")
    final, val = valider(bloc, base, k, log)
    params = {"version": VERSION, **base, "effets": final, "effets_appris_2526": k, "emac": val["emac"]}
    log("5. contrôle du Module 4 sur l'archive")
    ctl = controle_archive(params, log)
    params["regle_le"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    PARAMS.write_text(json.dumps(params, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    VALIDATION.write_text(json.dumps({"version": VERSION, "hyperparametres": hp, "effets": {"appris_2526": k, "traces": traces, "final": final},
                                      "validation_fd_2627": val, "controle_module4_archive": ctl}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"terminé en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if mode in ("tout", "reprise"):
        tout(reprise=mode == "reprise")
    elif mode == "seuils":
        calibrer_seuils()
    else:
        print(__doc__)
