"""Harnais de test xG du moteur DC (branche moteur-dc-xg-prep, ordre de Patrick du 31/10/2026). NE MODIFIE PAS le moteur en production.

Question testée : ajuster les forces de Dixon-Coles sur des cibles mélangées  y = (1 − β)·buts + β·xG  améliore-t-il les prédictions ?
β = 0 : Dixon-Coles sur les buts (production). β = 1 : sur les xG. β est APPRIS, jamais posé. Le score final reste une grille de BUTS
(la correction τ des petits scores lit les buts réels, `modele.ajuster(buts_tau=…)`).

Données : Football-Data normalisé (`data/football_data/normalized/2627/*.jsonl`), ligues dont ≥ 80 % des matchs joués ont un xG (règle de Patrick).
Protocole (walk-forward, chaque match prédit avec les seuls matchs d'avant) : matchs prédits triés par date, 60 % calibrage / 20 % validation / 20 % test.
1. calibrage : β maximise la log-vraisemblance du score réel (grille 0 ; 0,25 ; … ; 1 puis dichotomie) ;
2. validation : si β n'améliore pas la log-vraisemblance de la validation par rapport à β = 0, il est remis à 0 (règle du calibrage de Gamma) ;
3. test : log-loss du score et des 103 marchés (en millièmes), paris validés simplifiés, intervalles à 95 % (bootstrap par match).
Paris validés (simplifiés, dit clairement) : seuil de probabilité par marché appris sur le calibrage (méthode de `calibrage.seuils_par_marche`),
un pari principal par match (le plus probable parmi les marchés au-dessus de leur seuil). Sans Edge, sans Wilson, SANS filtre de cote : Football-Data
n'a aucune cote BetPawa. Ce n'est donc pas le Module 4 complet.

Usage :  python -m moteur_dc.xg_harnais essai      essai à blanc sur les données actuelles (résultat NON significatif, écrit docs/dc_xg_harnais_essai.json)
         python -m moteur_dc.xg_harnais verifier   compte les matchs xG, recalcule le seuil avec la variance courante et dit s'il est atteint (écrit data/dc/xg_volume.json)
         python -m moteur_dc.xg_harnais lancer     test complet, REFUSÉ tant que le seuil n'est pas atteint
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from . import ajustements as AJ, calibrage as CAL, coeur, modele as MO

ROOT = CAL.ROOT
NORMALISE = ROOT / "data" / "football_data" / "normalized" / "2627"
ESSAI = ROOT / "docs" / "dc_xg_harnais_essai.json"
VOLUME = ROOT / "data" / "dc" / "xg_volume.json"
COUVERTURE_MIN = 0.80
PART_CALIBRAGE, PART_VALIDATION = 0.60, 0.20
GRILLE_BETA = (0.0, 0.25, 0.5, 0.75, 1.0)
Z95 = 1.96
# Variance observée à l'essai « style » (31/10/2026, réserve de 586 matchs, 60 paris, filtre de cote 1,26) : écart de réussite avant/après
# entre −11,1 et +5,1 points (bootstrap par match) → demi-largeur 8,1 points pour 60 paris et 0,1024 pari par match.
STYLE_PARIS, STYLE_DEMI_LARGEUR_PTS, STYLE_MATCHS = 60, 8.1, 586
EFFET_REUSSITE_PATRICK_PTS, EFFET_REUSSITE_REALISTE_PTS = 0.5, 2.0
EFFET_LOGLOSS = 0.001                                            # « millième » de Patrick : plus petite amélioration de log-loss qui compte


# --- Données ------------------------------------------------------------------------------------------------------
def charger(dossier: Path = NORMALISE) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Matchs joués avec xG des ligues couvertes à ≥ 80 %, au format du bloc de calibrage (+ xh, xa). Renvoie aussi le tableau de couverture."""
    matchs: list[dict[str, Any]] = []
    couv: dict[str, Any] = {}
    for f in sorted(glob.glob(str(dossier / "*.jsonl"))):
        code = os.path.basename(f)[:-6]
        joues, avec = [], []
        for ligne in open(f, encoding="utf-8"):
            r = json.loads(ligne)
            if r.get("full_time_home_goals") is None or r.get("full_time_away_goals") is None:
                continue
            joues.append(r)
            if r.get("home_xg") not in (None, "") and r.get("away_xg") not in (None, ""):
                avec.append(r)
        taux = len(avec) / len(joues) if joues else 0.0
        couv[code] = {"joues": len(joues), "avec_xg": len(avec), "couverture": round(taux, 4), "retenue": taux >= COUVERTURE_MIN and bool(avec),
                      "du": min((r["date"] for r in avec), default=None), "au": max((r["date"] for r in avec), default=None)}
        if couv[code]["retenue"]:
            for r in avec:
                matchs.append({"id": f"2627|{code}|{r['date']}|{r['home_team']}|{r['away_team']}", "ligue": f"fd|2627|{code}", "saison": "2627",
                               "date": r["date"], "dom": r["home_team"], "ext": r["away_team"], "h": int(r["full_time_home_goals"]),
                               "a": int(r["full_time_away_goals"]), "xh": float(r["home_xg"]), "xa": float(r["away_xg"])})
    return matchs, couv


def avec_cible(matchs: list[dict[str, Any]], beta: float) -> list[dict[str, Any]]:
    """Copie des matchs avec les cibles d'ajustement hf/af = (1 − β)·buts + β·xG. β = 0 : aucune cible ajoutée (Dixon-Coles d'origine)."""
    if beta <= 0:
        return [{k: v for k, v in m.items() if k not in ("xh", "xa")} for m in matchs]
    return [{**{k: v for k, v in m.items() if k not in ("xh", "xa")}, "hf": (1 - beta) * m["h"] + beta * m["xh"], "af": (1 - beta) * m["a"] + beta * m["xa"]}
            for m in matchs]


# --- Prédictions et scores ---------------------------------------------------------------------------------------------
def prevoir(matchs: list[dict[str, Any]], params: dict[str, Any], beta: float) -> list[dict[str, Any]]:
    res = CAL.marche_avant(CAL._regrouper(avec_cible(matchs, beta)), params)
    return sorted(res, key=lambda r: (r["date"], r["id"]))


def scores(res: list[dict[str, Any]], effets: dict[str, float]) -> dict[str, np.ndarray]:
    lh, la, rho, F, h, a = CAL._tableaux(res)
    G = MO.grilles(*AJ.appliquer_vect(lh, la, rho, F, effets))
    ll = np.log(np.maximum(G[np.arange(len(h)), h, a], 1e-12))
    P = np.einsum("nij,kij->nk", G, coeur.MASQUES)
    Y = CAL._resultats(h, a)
    q = np.clip(P, 1e-6, 1 - 1e-6)
    return {"ll": ll, "lm": -np.mean(Y * np.log(q) + (1 - Y) * np.log(1 - q), axis=1), "P": P, "Y": Y}


def decoupe(n: int) -> tuple[int, int]:
    return int(PART_CALIBRAGE * n), int((PART_CALIBRAGE + PART_VALIDATION) * n)


def chercher_beta(matchs: list[dict[str, Any]], params: dict[str, Any], effets: dict[str, float], log=print) -> tuple[float, dict[float, Any]]:
    """β sur le calibrage seulement (60 % premiers matchs prédits). Grille puis dichotomie autour du meilleur."""
    cache: dict[float, Any] = {}
    n_cal: list[int] = []

    def ev(b: float) -> float:
        b = round(b, 6)
        if b not in cache:
            res = prevoir(matchs, params, b)
            cache[b] = (res, scores(res, effets))
            if not n_cal:
                n_cal.append(decoupe(len(res))[0])
            log(f"  beta={b} : log-vraisemblance calibrage {cache[b][1]['ll'][:n_cal[0]].mean():.6f}")
        return float(cache[b][1]["ll"][:n_cal[0]].mean())

    for b in GRILLE_BETA:
        ev(b)
    for _ in range(4):
        ordre = sorted(cache)
        i = ordre.index(max(cache, key=lambda b: cache[b][1]["ll"][:n_cal[0]].mean()))
        for v in (ordre[i - 1] if i > 0 else None, ordre[i + 1] if i + 1 < len(ordre) else None):
            if v is not None:
                ev((ordre[i] + v) / 2)
    best = max(cache, key=lambda b: cache[b][1]["ll"][:n_cal[0]].mean())
    return best, cache


def paris_principaux(S: dict[str, np.ndarray], res: list[dict[str, Any]], i_cal: int, idx: np.ndarray) -> np.ndarray:
    """Un pari principal par match de `idx` (1 = gagné, 0 = perdu, nan = aucun pari). Seuils par marché appris sur le calibrage seulement."""
    an = [{"a": {"p_marches": S["P"][i]}, "m": {"h": res[i]["h"], "a": res[i]["a"]}} for i in range(i_cal)]
    seuils = CAL.seuils_par_marche(an)
    sv = np.array([seuils[coeur.cle_txt(c)]["seuil"] if seuils[coeur.cle_txt(c)]["seuil"] is not None else np.inf for c in coeur.CLES])
    out = np.full(len(idx), np.nan)
    for j, i in enumerate(idx):
        ok = S["P"][i] >= sv
        if ok.any():
            k = int(np.argmax(np.where(ok, S["P"][i], -1.0)))
            out[j] = S["Y"][i, k]
    return out


def bootstrap(d_paires: np.ndarray, n: int = 2000, graine: int = 1) -> list[float]:
    """Intervalle à 95 % de la moyenne d'écarts par match (rééchantillonnage des matchs)."""
    r = np.random.default_rng(graine)
    m = [float(np.mean(d_paires[r.integers(0, len(d_paires), len(d_paires))])) for _ in range(n)]
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def bootstrap_reussite(b0: np.ndarray, b1: np.ndarray, n: int = 2000, graine: int = 1) -> list[float] | None:
    r = np.random.default_rng(graine)
    d = []
    for _ in range(n):
        s = r.integers(0, len(b0), len(b0))
        x0, x1 = b0[s][~np.isnan(b0[s])], b1[s][~np.isnan(b1[s])]
        if len(x0) and len(x1):
            d.append((x1.mean() - x0.mean()) * 100)
    return [round(float(np.percentile(d, 2.5)), 1), round(float(np.percentile(d, 97.5)), 1)] if d else None


# --- Pouvoir statistique et seuil de déclenchement ----------------------------------------------------------------
def paris_necessaires(effet_pts: float) -> int:
    """Paris validés nécessaires sur la réserve pour que l'intervalle à 95 % de l'écart de réussite exclue 0 quand le vrai gain vaut `effet_pts` :
    la demi-largeur observée à l'essai « style » (8,1 points pour 60 paris) décroît en 1/√n."""
    return math.ceil(STYLE_PARIS * (STYLE_DEMI_LARGEUR_PTS / effet_pts) ** 2)


def matchs_necessaires_reussite(effet_pts: float) -> int:
    return math.ceil(paris_necessaires(effet_pts) / (STYLE_PARIS / STYLE_MATCHS))


def matchs_necessaires_logloss(sd_ecart: float, effet: float = EFFET_LOGLOSS) -> int:
    """Matchs de test nécessaires pour que l'intervalle à 95 % de l'écart moyen de log-vraisemblance par match exclue 0 : (1,96·σ/effet)²."""
    return math.ceil((Z95 * sd_ecart / effet) ** 2)


EFFETS_LOGLOSS = (0.001, 0.005, 0.01)                              # 1, 5 et 10 millièmes
EFFET_DECLENCHEMENT = 0.005                                         # niveau retenu pour le suivi mensuel (hypothèse à valider par Patrick, une seule constante)


def seuil_declenchement(sd_ecart: float) -> dict[str, Any]:
    """Seuils N (matchs PRÉDITS au total, test = 20 % finaux) et X (paris sur la réserve). Le test complet n'a de pouvoir que si le volume les atteint."""
    part_test = 1 - PART_CALIBRAGE - PART_VALIDATION
    ll = {f"{round(e * 1000)}_millièmes": {"effet": e, "matchs_de_test": matchs_necessaires_logloss(sd_ecart, e),
                                           "matchs_predits_total": math.ceil(matchs_necessaires_logloss(sd_ecart, e) / part_test)} for e in EFFETS_LOGLOSS}
    return {"critere_logloss": {"sd_ecart_par_match": round(sd_ecart, 6), "par_effet": ll, "effet_de_suivi": EFFET_DECLENCHEMENT,
                                "matchs_predits_total": ll[f"{round(EFFET_DECLENCHEMENT * 1000)}_millièmes"]["matchs_predits_total"]},
            "critere_reussite_patrick_0_5": {"effet_pts": EFFET_REUSSITE_PATRICK_PTS, "paris_reserve": paris_necessaires(EFFET_REUSSITE_PATRICK_PTS),
                                             "matchs_de_test": matchs_necessaires_reussite(EFFET_REUSSITE_PATRICK_PTS),
                                             "matchs_predits_total": math.ceil(matchs_necessaires_reussite(EFFET_REUSSITE_PATRICK_PTS) / part_test)},
            "critere_reussite_2_pts": {"effet_pts": EFFET_REUSSITE_REALISTE_PTS, "paris_reserve": paris_necessaires(EFFET_REUSSITE_REALISTE_PTS),
                                       "matchs_de_test": matchs_necessaires_reussite(EFFET_REUSSITE_REALISTE_PTS),
                                       "matchs_predits_total": math.ceil(matchs_necessaires_reussite(EFFET_REUSSITE_REALISTE_PTS) / part_test)},
            "base": f"{STYLE_PARIS} paris, demi-largeur {STYLE_DEMI_LARGEUR_PTS} points, {STYLE_PARIS / STYLE_MATCHS:.4f} pari par match (essai style) ; "
                    "écart-type du log-loss par match mesuré entre xG pur (β = 1) et buts purs (β = 0), donc borne haute"}


# --- Exécution --------------------------------------------------------------------------------------------------------
def executer(log=print) -> dict[str, Any]:
    t0 = time.time()
    params = json.loads(CAL.PARAMS.read_text(encoding="utf-8"))
    effets = params["effets"]
    matchs, couv = charger()
    log(f"xG : {len(matchs)} matchs dans {sum(c['retenue'] for c in couv.values())} ligues (couverture ≥ {COUVERTURE_MIN:.0%})")
    beta, cache = chercher_beta(matchs, params, effets, log)
    res0, S0 = cache[0.0]
    n = len(res0)
    i_cal, i_val = decoupe(n)
    sl_val, sl_test = slice(i_cal, i_val), slice(i_val, n)
    resb, Sb = cache[beta]
    gain_val = float(Sb["ll"][sl_val].mean() - S0["ll"][sl_val].mean())
    retenu = beta if gain_val > 0 else 0.0                                     # règle fixée avant le calcul
    log(f"beta appris {beta} ; gain en validation {gain_val * 1000:+.3f} millièmes ; beta retenu {retenu}")
    idx_test = np.arange(i_val, n)
    b0 = paris_principaux(S0, res0, i_cal, idx_test)
    b1 = paris_principaux(Sb, resb, i_cal, idx_test)
    d_ll, d_lm = (Sb["ll"] - S0["ll"])[sl_test], (S0["lm"] - Sb["lm"])[sl_test]
    # écart type par match de la différence entre xG pur (β = 1) et buts purs : borne de variabilité pour le seuil de déclenchement
    sd = float(np.std(cache[1.0][1]["ll"] - S0["ll"], ddof=1))
    taux = lambda b: None if np.isnan(b).all() else round(float(np.nanmean(b)) * 100, 1)
    out = {"genere_le": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "matchs_xg": len(matchs), "matchs_predits": n,
           "decoupe": {"calibrage": i_cal, "validation": i_val - i_cal, "test": n - i_val, "periode": [res0[0]["date"], res0[-1]["date"]]},
           "couverture": couv, "beta_appris": beta, "beta_retenu": retenu, "gain_validation_milliemes": round(gain_val * 1000, 3),
           "courbe_calibrage": {str(b): round(float(cache[b][1]["ll"][:i_cal].mean()), 6) for b in sorted(cache)},
           "test": {"matchs": n - i_val,
                    "logloss_score_millièmes_gain_beta_appris": round(float(d_ll.mean()) * 1000, 3), "ic95_millièmes": [round(v * 1000, 3) for v in bootstrap(d_ll)],
                    "logloss_marches_millièmes_gain_beta_appris": round(float(d_lm.mean()) * 1000, 3), "ic95_marches_millièmes": [round(v * 1000, 3) for v in bootstrap(d_lm)],
                    "paris_buts_purs": int((~np.isnan(b0)).sum()), "reussite_buts_purs_%": taux(b0),
                    "paris_beta_appris": int((~np.isnan(b1)).sum()), "reussite_beta_appris_%": taux(b1), "ic95_ecart_reussite_pts": bootstrap_reussite(b0, b1)},
           "seuil_declenchement": seuil_declenchement(sd), "duree_s": round(time.time() - t0)}
    return out


def compter() -> dict[str, Any]:
    """Matchs avec xG (couverture ≥ 80 %), matchs réellement PRÉDICTIBLES (≥ 4 matchs au lieu pour chaque équipe : temps de chauffe de chaque saison)
    et écart-type courant du log-loss par match entre xG pur (β = 1) et buts purs (β = 0), recalculé à chaque passage : il baisse quand l'échantillon grossit."""
    matchs, couv = charger()
    params = json.loads(CAL.PARAMS.read_text(encoding="utf-8"))
    r0, r1 = prevoir(matchs, params, 0.0), prevoir(matchs, params, 1.0)
    sd = float(np.std(scores(r1, params["effets"])["ll"] - scores(r0, params["effets"])["ll"], ddof=1)) if len(r0) > 1 else float("nan")
    return {"date": date.today().isoformat(), "matchs_xg": len(matchs), "matchs_predits": len(r0), "sd_ecart_par_match": round(sd, 6),
            "ligues": {k: v["avec_xg"] for k, v in couv.items() if v["retenue"]}}


def verifier(log=print) -> dict[str, Any]:
    v = compter()
    seuil = seuil_declenchement(v["sd_ecart_par_match"])
    n_need = seuil["critere_logloss"]["matchs_predits_total"]
    v.update(seuil_matchs_predits=n_need, effet_de_suivi_millièmes=EFFET_DECLENCHEMENT * 1000, atteint=v["matchs_predits"] >= n_need,
             manque=max(0, n_need - v["matchs_predits"]), seuils=seuil)
    VOLUME.parent.mkdir(parents=True, exist_ok=True)
    VOLUME.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"matchs prédits avec xG : {v['matchs_predits']} (sur {v['matchs_xg']} avec xG) / seuil {n_need} : "
        f"{'ATTEINT' if v['atteint'] else 'non atteint, il manque ' + str(v['manque'])}")
    if v["atteint"]:
        log(f"::notice title=Seuil xG atteint::{v['matchs_predits']} matchs prédits avec xG (seuil {n_need}). Test possible : python -m moteur_dc.xg_harnais lancer")
    return v


def lancer(log=print) -> dict[str, Any]:
    v = verifier(log)
    if not v["atteint"]:
        raise SystemExit(f"Refusé : {v['matchs_predits']} matchs prédits avec xG, seuil {v['seuil_matchs_predits']}. Le test ne sera pas lancé sous le seuil.")
    out = executer(log)
    chemin = ROOT / "docs" / f"dc_xg_rapport_{date.today().isoformat()}.json"
    chemin.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "essai":
        r = executer()
        r["avertissement"] = "ESSAI À BLANC sur le volume actuel : résultat non significatif, ne décide rien."
        ESSAI.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: r[k] for k in ("matchs_xg", "decoupe", "beta_appris", "beta_retenu", "test", "seuil_declenchement")}, ensure_ascii=False, indent=1))
    elif mode == "verifier":
        verifier()
    elif mode == "lancer":
        lancer()
    else:
        print(__doc__)
