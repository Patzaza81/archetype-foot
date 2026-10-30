"""Calibrage du moteur DC — protocole fixé AVANT le calcul (30/10/2026). Usage : python -m moteur_dc.calibrage [tout|reprise|hyper]

Leçon des moteurs précédents (omega) : un réglage appris sur peu de matchs ne tient pas hors échantillon. Donc, dans l'ordre :
1. HYPERPARAMÈTRES (σ de la pénalité, xi de la décroissance, ρ commun à tous les championnats) : Football-Data 2025-26, vraisemblance PRÉDICTIVE hors échantillon
   (marche avant : on ajuste le championnat avec les matchs d'avant la semaine, on note les scores de la semaine). Recherche par coordonnées
   (σ, xi, ρ puis σ) sur une grille de candidats ; les valeurs de la grille sont des candidats de recherche, pas des réglages posés à la main.
   Un match n'est noté que si chaque équipe a au moins 4 matchs au même lieu avant la semaine (règle de Patrick) ; saison courante seulement.
2. CALIBRATION par marché (isotone) et taux de base par marché : appris sur 2025-26 seulement ; gardée pour une famille de marchés SEULEMENT si, sur 2026-27,
   elle améliore à la fois la perte logarithmique et le Brier du modèle brut (règle fixée avant le calcul, comme omega pour ses filtres).
3. VALIDATION sur Football-Data 2026-27, jamais utilisé pour régler : perte logarithmique et Brier du modèle brut, calibré et du taux de base ;
   erreur de calibration PAR TRANCHE (écart entre probabilité annoncée et fréquence observée, par dixième de probabilité).
4. SÉLECTION (seuil, accord avec la cote) : archive ARCHETYPE (cotes BetPawa prises avant le coup d'envoi), coupée au 14/10/2026 comme omega :
   développement (avant) pour apprendre le seuil (meilleure borne basse de Wilson à 95 % de la réussite du pari principal, seuils candidats 50 à 75 %,
   au moins 30 paris) et décider l'accord avec la cote ; réserve (à partir du 14/10) = contrôle. Ce n'est PAS un bilan de performance du moteur :
   le bilan réel vient du journal gelé (bilan_dc.py).
Sorties : moteur_dc/parametres.json, docs/dc_validation.json.
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from . import coeur, donnees as D, marches as M, modele as MO

ROOT = Path(__file__).resolve().parent.parent
PARAMS = Path(__file__).with_name("parametres.json")
VALIDATION = ROOT / "docs" / "dc_validation.json"
COUPE_ARCHIVE = "2026-10-14"
SIGMAS = (0.15, 0.25, 0.4, 0.6, 1.0, 2.0)
RHOS = (-0.12, -0.08, -0.04, 0.0, 0.04)
XIS = (0.0, 0.002, 0.004, 0.008, 0.016)
SEUILS = [x / 100 for x in range(50, 76)]
MIN_PARIS = 30
VERSION = "1.0.0"


def semaine(d: str, depart: date) -> date:
    return depart + timedelta(days=((date.fromisoformat(d) - depart).days // 7) * 7)


def marche_avant(par_ligue: dict[str, list[dict]], sigma: float, xi: float, rho: float, avec_probas: bool = False, saisons: set[str] | None = None,
                 pas_jours: int = 7) -> list[dict[str, Any]]:
    """Prédictions hors échantillon : pour chaque semaine, ajustement avec les matchs d'AVANT la semaine, puis notation des matchs de la semaine."""
    out: list[dict[str, Any]] = []
    for lg, ms in par_ligue.items():
        ms = sorted(ms, key=lambda m: m["date"])
        if saisons and ms[0].get("saison") not in saisons:
            continue
        depart = date.fromisoformat(ms[0]["date"])
        semaines: dict[date, list[dict]] = defaultdict(list)
        for m in ms:
            semaines[depart + timedelta(days=((date.fromisoformat(m["date"]) - depart).days // pas_jours) * pas_jours)].append(m)
        fit = None
        compte_dom: dict[str, int] = defaultdict(int)
        compte_ext: dict[str, int] = defaultdict(int)
        passe: list[dict] = []
        for debut in sorted(semaines):
            jour = debut.isoformat()
            if passe:
                fit = MO.ajuster([m["dom"] for m in passe], [m["ext"] for m in passe], np.array([m["h"] for m in passe]),
                                 np.array([m["a"] for m in passe]), np.array([D.jours(m["date"], jour) for m in passe]), sigma, xi, fit, rho)
                for m in semaines[debut]:
                    if compte_dom[m["dom"]] < D.MIN_MATCHS or compte_ext[m["ext"]] < D.MIN_MATCHS:
                        continue
                    lh, la = fit.lambdas(m["dom"], m["ext"])
                    r = {"ligue": lg, "saison": m.get("saison"), "date": m["date"], "id": m["id"], "h": m["h"], "a": m["a"], "lh": lh, "la": la}
                    g = MO.grille(lh, la, fit.rho)
                    r["ll"] = math.log(max(g[min(m["h"], MO.N_BUTS), min(m["a"], MO.N_BUTS)], 1e-12))
                    if avec_probas:
                        r["p"] = np.einsum("ij,kij->k", g, coeur.MASQUES)
                    out.append(r)
            for m in semaines[debut]:
                passe.append(m)
                compte_dom[m["dom"]] += 1
                compte_ext[m["ext"]] += 1
    return out


def _regrouper(matchs: list[dict]) -> dict[str, list[dict]]:
    d: dict[str, list[dict]] = defaultdict(list)
    for m in matchs:
        d[m["ligue"]].append(m)
    return d


def hyperparametres(bloc: list[dict], log=print) -> dict[str, Any]:
    par_ligue = _regrouper([m for m in bloc if m["saison"] == "2526"])
    essais: dict[tuple, float] = {}

    def score(s: float, x: float, r: float) -> float:
        if (s, x, r) not in essais:
            t = time.time()
            res = marche_avant(par_ligue, s, x, r)
            essais[(s, x, r)] = float(np.mean([q["ll"] for q in res]))
            log(f"  sigma={s} xi={x} rho={r} : vraisemblance prédictive {essais[(s, x, r)]:.5f} par match ({len(res)} matchs, {time.time() - t:.0f} s)")
        return essais[(s, x, r)]

    s_b, x_b, r_b = SIGMAS[2], XIS[0], RHOS[2]            # point de départ de la recherche par coordonnées
    s_b = max(SIGMAS, key=lambda s: score(s, x_b, r_b))
    x_b = max(XIS, key=lambda x: score(s_b, x, r_b))
    r_b = max(RHOS, key=lambda r: score(s_b, x_b, r))
    s_b = max(SIGMAS, key=lambda s: score(s, x_b, r_b))
    return {"sigma": s_b, "xi": x_b, "rho": r_b, "ll": essais[(s_b, x_b, r_b)], "essais": {f"{s}|{x}|{r}": v for (s, x, r), v in essais.items()}}


def _resultats(r: dict) -> np.ndarray:
    h, a = r["h"], r["a"]
    return np.array([float(t(h, a)) for t in (coeur.TESTS[c] for c in coeur.CLES)])


def predictions_marches(bloc: list[dict], sigma: float, xi: float, rho: float, saisons: set[str]) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    r = marche_avant(_regrouper([m for m in bloc if m["saison"] in saisons]), sigma, xi, rho, avec_probas=True)
    P = np.stack([q["p"] for q in r])
    Y = np.stack([_resultats(q) for q in r])
    return P, Y, r


def tranches(p: np.ndarray, y: np.ndarray) -> list[dict[str, Any]]:
    """Erreur de calibration par dixième de probabilité annoncée : écart moyen entre ce que le moteur annonce et ce qui arrive."""
    out = []
    for k in range(10):
        m = (p >= k / 10) & ((p < (k + 1) / 10) if k < 9 else (p <= 1))
        if m.sum():
            out.append({"tranche": f"{k * 10}-{(k + 1) * 10}%", "n": int(m.sum()), "annonce": round(float(p[m].mean()), 4),
                        "observe": round(float(y[m].mean()), 4), "ecart": round(float(p[m].mean() - y[m].mean()), 4)})
    return out


def _perte(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))), float(np.mean((p - y) ** 2))


def calibration_et_validation(bloc: list[dict], hp: dict[str, Any], log=print) -> tuple[dict, dict]:
    sigma, xi, rho = hp["sigma"], hp["xi"], hp["rho"]
    P1, Y1, r1 = predictions_marches(bloc, sigma, xi, rho, {"2526"})
    P2, Y2, r2 = predictions_marches(bloc, sigma, xi, rho, {"2627"})
    log(f"prédictions : développement {len(r1)} matchs (2025-26), validation {len(r2)} matchs (2026-27)")
    cal: dict[str, list] = {}
    bases: dict[str, float] = {}
    tout = [m for m in bloc if m["saison"] == "2526"]
    for k, c in enumerate(coeur.CLES):
        cal[coeur.cle_txt(c)] = [list(v) for v in MO.isotone(P1[:, k], Y1[:, k])]
        bases[coeur.cle_txt(c)] = round(float(np.mean([coeur.TESTS[c](m["h"], m["a"]) for m in tout])), 4)
    # validation
    brut, calib, constante = np.zeros_like(P2), np.zeros_like(P2), np.zeros_like(P2)
    for k, c in enumerate(coeur.CLES):
        calib[:, k] = MO.calibrer(P2[:, k], cal[coeur.cle_txt(c)])
        constante[:, k] = bases[coeur.cle_txt(c)]
    brut = P2
    par_famille: dict[str, dict] = {}
    gardee: dict[str, bool] = {}
    for fam in sorted({M.famille(c) for c in coeur.CLES}):
        idx = [k for k, c in enumerate(coeur.CLES) if M.famille(c) == fam]
        ll_b, br_b = _perte(brut[:, idx].ravel(), Y2[:, idx].ravel())
        ll_c, br_c = _perte(calib[:, idx].ravel(), Y2[:, idx].ravel())
        ll_k, br_k = _perte(constante[:, idx].ravel(), Y2[:, idx].ravel())
        # règle fixée avant le calcul : la calibration n'est gardée pour une famille que si elle améliore HORS ÉCHANTILLON la perte logarithmique ET le Brier
        gardee[fam] = bool(ll_c < ll_b and br_c < br_b)
        par_famille[fam] = {"brut": {"perte_log": round(ll_b, 5), "brier": round(br_b, 5)}, "calibre": {"perte_log": round(ll_c, 5), "brier": round(br_c, 5)},
                            "taux_de_base": {"perte_log": round(ll_k, 5), "brier": round(br_k, 5)}, "calibration_gardee": gardee[fam]}
    utilise = np.stack([calib[:, k] if gardee[M.famille(c)] else brut[:, k] for k, c in enumerate(coeur.CLES)], axis=1)
    cal = {coeur.cle_txt(c): v for c, v in zip(coeur.CLES, (cal[coeur.cle_txt(c)] for c in coeur.CLES)) if gardee[M.famille(c)]}
    val = {"matchs": len(r2), "ll_exact_par_match": round(float(np.mean([q["ll"] for q in r2])), 5),
           "ll_exact_par_match_dev": round(float(np.mean([q["ll"] for q in r1])), 5),
           "par_famille": par_famille, "tranches_utilisees": tranches(utilise.ravel(), Y2.ravel()),
           "tranches_calibre": tranches(calib.ravel(), Y2.ravel()), "tranches_brut": tranches(brut.ravel(), Y2.ravel())}
    return {"calibration": cal, "bases": bases}, val


def wilson_bas(k: int, n: int, z: float = 1.959964) -> float:
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


def analyses_archive(params: dict[str, Any], log=print) -> list[dict[str, Any]]:
    """Analyse de chaque match JOUÉ de l'archive avec le championnat tel qu'il était la veille (un ajustement par championnat et par jour)."""
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
        fit = coeur.ajuster_ligue(liste, jour, params["sigma"], params["xi"], params.get("rho"))
        if fit is None:
            continue
        for m in ms:
            a = coeur.analyser(m, liste, params, fit)
            if a["statut"] == "analyse":
                out.append({"m": m, "a": a})
    log(f"archive : {len(out)} matchs joués analysables")
    return out


def _paris_principaux(analyses: list[dict], sel: dict) -> list[tuple[bool, float]]:
    res = []
    for x in analyses:
        s = coeur.selectionner(json.loads(json.dumps(x["a"])), sel)          # copie : selectionner annote les lignes
        if s["principal"]:
            p = s["principal"]
            res.append((bool(coeur.TESTS[tuple(p["cle"])](x["m"]["h"], x["m"]["a"])), p["cote"]))
    return res


def apprendre_selection(params: dict[str, Any], log=print) -> dict[str, Any]:
    an = analyses_archive(params, log)
    dev = [x for x in an if x["m"]["jour"] < COUPE_ARCHIVE]
    res = [x for x in an if x["m"]["jour"] >= COUPE_ARCHIVE]
    out: dict[str, Any] = {"matchs_dev": len(dev), "matchs_reserve": len(res), "coupe": COUPE_ARCHIVE, "essais": []}
    meilleur = None
    for accord in (False, True):
        for s in SEUILS:
            sel = {"seuil": s, "cote_min": coeur.COTE_MIN, "exiger_accord_cote": accord}
            pr = _paris_principaux(dev, sel)
            if len(pr) < MIN_PARIS:
                continue
            k = sum(g for g, _ in pr)
            b = wilson_bas(k, len(pr))
            out["essais"].append({"accord": accord, "seuil": s, "paris": len(pr), "reussite": round(k / len(pr), 4), "wilson_bas": round(b, 4)})
            if meilleur is None or b > meilleur[0]:
                meilleur = (b, accord, s, len(pr), k / len(pr))
    if meilleur is None:
        out["selection"] = None
        return out
    _, accord, s, n, r = meilleur
    sel = {"seuil": s, "cote_min": coeur.COTE_MIN, "exiger_accord_cote": accord}
    out["selection"] = sel
    out["developpement"] = {"paris": n, "reussite": round(r, 4)}
    for nom, groupe in (("reserve", res), ("reserve_sans_accord", res), ("reserve_avec_accord", res)):
        sel2 = dict(sel, exiger_accord_cote={"reserve": accord, "reserve_sans_accord": False, "reserve_avec_accord": True}[nom])
        pr = _paris_principaux(groupe, sel2)
        if pr:
            k = sum(g for g, _ in pr)
            out[nom] = {"paris": len(pr), "reussite": round(k / len(pr), 4), "cote_moyenne": round(float(np.mean([c for _, c in pr])), 3)}
    return out


def tout(log=print, reprise: bool = False) -> None:
    t0 = time.time()
    bloc = D.charger_bloc()
    log(f"bloc Football-Data : {len(bloc)} matchs")
    log("1. hyperparamètres (prédictif hors échantillon, 2025-26)")
    if reprise:                                         # hyperparamètres déjà appris (docs/dc_validation.json) : seules les étapes 2 à 4 sont refaites
        hp = json.loads(VALIDATION.read_text(encoding="utf-8"))["hyperparametres"]
        log("   repris du fichier de validation")
    else:
        hp = hyperparametres(bloc, log)
    log(f"   retenu : sigma={hp['sigma']} xi={hp['xi']} rho={hp['rho']}")
    log("2-3. calibration (2025-26) et validation (2026-27)")
    cal, val = calibration_et_validation(bloc, hp, log)
    params = {"version": VERSION, "sigma": hp["sigma"], "xi": hp["xi"], "rho": hp["rho"], **cal,
              "selection": {"seuil": 0.62, "cote_min": coeur.COTE_MIN, "exiger_accord_cote": False}}
    PARAMS.write_text(json.dumps(params, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log("4. sélection (archive, développement avant le 14/10 / réserve après)")
    sel = apprendre_selection(params, log)
    if sel.get("selection"):
        params["selection"] = sel["selection"]
    params["regle_le"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    PARAMS.write_text(json.dumps(params, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION.write_text(json.dumps({"version": VERSION, "hyperparametres": hp, "validation_fd_2627": val, "selection_archive": sel},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"terminé en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if mode == "tout":
        tout()
    elif mode == "reprise":
        tout(reprise=True)
    elif mode == "hyper":
        print(hyperparametres(D.charger_bloc()))
    else:
        print(__doc__)
