"""Piste A : criblage des paramètres du Module 1 sur les résidus de Dixon-Coles pur. Protocole : docs/DC_CRIBLAGE_PROTOCOLE.md (fixé avant le calcul).

Usage : python -m moteur_dc.criblage [--placebos N] [--cache fichier.pkl]
Ne modifie ni le moteur ni ses paramètres. Sorties : docs/dc_criblage_resultats.json et docs/DC_CRIBLAGE_RESULTATS.md.
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as CAL, donnees as D, modele as MO
from .module1 import SCORES_FAIBLES_NULS

ROOT = Path(__file__).resolve().parent.parent
SORTIE_JSON = ROOT / "docs" / "dc_criblage_resultats.json"
SORTIE_MD = ROOT / "docs" / "DC_CRIBLAGE_RESULTATS.md"
SORTIE_JSON_CENTRE = ROOT / "docs" / "dc_criblage_resultats_centre.json"
SORTIE_MD_CENTRE = ROOT / "docs" / "DC_CRIBLAGE_RESULTATS_CENTRE.md"
TIRAGES = 4000          # précision du bootstrap (pas un paramètre du modèle)
NIVEAU = 0.025          # unilatéral : la borne basse d'un intervalle à 95 % est > 0 si et seulement si p < 2,5 %


# ----------------------------------------------------------------------------- variables
def groupes(p: dict[str, Any]) -> dict[str, dict[str, float | None]]:
    """Paramètres numériques d'une équipe : {paramètre: {colonne: valeur}}. Les clés textuelles sont encodées (voir le protocole)."""
    out: dict[str, dict[str, float | None]] = {}
    for k, v in p.items():
        if k == "profil":                                    # doublon de profil_id
            continue
        if k.startswith("score_modal"):
            out[k] = {k: None if v is None else (1.0 if v in SCORES_FAIBLES_NULS else 0.0)}
        elif k == "serie":
            out[k] = {"serie_len": float(int(v[:-1])), **{f"serie_{c}": float(v[-1] == c) for c in "VND"}}
        elif k == "profil_id":
            out[k] = {f"profil_{i}": float(v == i) for i in range(1, 6)}
        elif k == "style_tag":
            out[k] = {f"style_{s}": float(v == s) for s in ("Defensive", "Offensive_Volatile", "Balanced")}
        elif k == "rangs":
            for nom, x in v.items():
                out[f"rang_{nom}"] = {f"rang_{nom}": float(x)}
        elif v is None:
            out[k] = {k: None}
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = {k: float(v)}
    return out


def extra(t: dict[str, Any], m: dict[str, Any]) -> tuple:
    return groupes(t["equipes"][m["dom"]]), groupes(t["equipes"][m["ext"]])


def construire_lignes(res: list[dict[str, Any]]) -> dict[str, Any]:
    """Deux lignes par match : les n premières sont les équipes à domicile, les n suivantes les équipes à l'extérieur (match i = lignes i et n + i)."""
    noms = list(res[0]["z"][0])
    cols = {g: list(res[0]["z"][0][g]) for g in noms}
    n = len(res)
    index: dict[str, list[int]] = {}
    nc = 0
    for g in noms:
        index[g] = list(range(nc, nc + 2 * len(cols[g])))            # [propres..., adverses...]
        nc += 2 * len(cols[g])
    X = np.full((2 * n, nc), np.nan)
    for i, r in enumerate(res):
        gd, ge = r["z"]
        for g in noms:
            c = len(cols[g])
            for j, col in enumerate(cols[g]):
                for ligne, own, opp in ((i, gd, ge), (n + i, ge, gd)):
                    a, b = own[g][col], opp[g][col]
                    X[ligne, index[g][j]] = np.nan if a is None else a
                    X[ligne, index[g][c + j]] = np.nan if b is None else b
    lam = np.concatenate([[r["lh"] for r in res], [r["la"] for r in res]])
    y = np.concatenate([[r["h"] for r in res], [r["a"] for r in res]]).astype(float)
    mois = np.array([r["date"][:7] for r in res])
    return {"X": X, "index": index, "colonnes": cols, "lam": lam, "y": y, "n": n, "mois": mois,
            "lh": np.array([r["lh"] for r in res]), "la": np.array([r["la"] for r in res]), "rho": np.array([r["rho"] for r in res]),
            "h": np.minimum([r["h"] for r in res], MO.N_BUTS), "a": np.minimum([r["a"] for r in res], MO.N_BUTS),
            "dates": (min(r["date"] for r in res), max(r["date"] for r in res))}


def standardiser(X: np.ndarray, mu: np.ndarray | None = None, sd: np.ndarray | None = None):
    """Statistiques de l'apprentissage seulement ; une valeur manquante vaut la moyenne d'apprentissage (0 après standardisation)."""
    if mu is None:
        mu = np.nanmean(np.where(np.isfinite(X), X, np.nan), axis=0)
        mu = np.where(np.isfinite(mu), mu, 0.0)
        sd = np.nanstd(np.where(np.isfinite(X), X, np.nan), axis=0)
        sd = np.where(np.isfinite(sd) & (sd > 0), sd, np.inf)             # colonne constante : devient 0
    Z = (X - mu) / sd
    return np.where(np.isfinite(Z), Z, 0.0), mu, sd


# ----------------------------------------------------------------------------- ridge et choix de α
def ridge(Z: np.ndarray, r: np.ndarray, alpha: float) -> np.ndarray:
    """Colonnes centrées sur leur moyenne d'apprentissage, aucun intercept dans la prédiction."""
    Zc = Z - Z.mean(axis=0)
    return np.linalg.solve(Zc.T @ Zc + alpha * np.eye(Z.shape[1]), Zc.T @ r)


def _erreur_blocs(Z: np.ndarray, r: np.ndarray, blocs: np.ndarray, alpha: float) -> float:
    tot = 0.0
    for b in np.unique(blocs):
        te = blocs == b
        th = ridge(Z[~te], r[~te], alpha)
        tot += float(np.sum((r[te] - (Z[te] - Z[~te].mean(axis=0)) @ th) ** 2))
    return tot / len(r)


def choisir_alpha(Z: np.ndarray, r: np.ndarray, blocs: np.ndarray, depart: float = 1.0, max_pas: int = 12) -> float:
    """α par validation croisée en blocs temporels ; la grille (facteur 10) s'étend tant que l'optimum n'est pas intérieur."""
    cache: dict[float, float] = {}

    def e(a: float) -> float:
        if a not in cache:
            cache[a] = _erreur_blocs(Z, r, blocs, a)
        return cache[a]

    a = depart
    for sens in (10.0, 0.1):
        for _ in range(max_pas):
            if e(a * sens) < e(a):
                a *= sens
            else:
                break
    return a


# ----------------------------------------------------------------------------- mesure
def gain_ll(L: dict[str, Any], s: np.ndarray, ll0: np.ndarray | None = None) -> np.ndarray:
    """Écart apparié par match : log-vraisemblance du score avec λ̃ = λ·exp(ŝ/√λ) moins celle du Dixon-Coles pur (mêmes ρ)."""
    n = L["n"]
    idx = np.arange(n)
    lh2 = L["lh"] * np.exp(s[:n] / np.sqrt(L["lh"]))
    la2 = L["la"] * np.exp(s[n:] / np.sqrt(L["la"]))
    g1 = MO.grilles(lh2, la2, L["rho"])
    if ll0 is None:
        ll0 = ll_pur(L)
    return np.log(np.maximum(g1[idx, L["h"], L["a"]], 1e-12)) - ll0


def ll_pur(L: dict[str, Any]) -> np.ndarray:
    g0 = MO.grilles(L["lh"], L["la"], L["rho"])
    return np.log(np.maximum(g0[np.arange(L["n"]), L["h"], L["a"]], 1e-12))


def bootstrap(d: np.ndarray, rng: np.random.Generator, tirages: int = TIRAGES) -> dict[str, float]:
    idx = rng.integers(0, len(d), (tirages, len(d)))
    moy = d[idx].mean(axis=1)
    return {"moyenne": float(d.mean()), "bas": float(np.percentile(moy, 2.5)), "haut": float(np.percentile(moy, 97.5)),
            "p": float((1 + np.sum(moy <= 0)) / (tirages + 1)), "mde": float(1.96 * d.std(ddof=1) / np.sqrt(len(d))), "sd": float(d.std(ddof=1))}


def retenu(bas: float) -> bool:
    """Règle de Patrick : retenu seulement si la borne basse de l'intervalle à 95 % est strictement positive."""
    return bool(np.isfinite(bas) and bas > 0)


def holm(p: dict[str, float], niveau: float = NIVEAU) -> dict[str, bool]:
    """Holm (famille entière à `niveau`) : les p triés par ordre croissant sont comparés à niveau / (m − rang)."""
    ordre = sorted(p, key=lambda k: p[k])
    m = len(ordre)
    out = {k: False for k in ordre}
    for rang, k in enumerate(ordre):
        if p[k] <= niveau / (m - rang):
            out[k] = True
        else:
            break
    return out


def cribler(App: dict[str, Any], Test: dict[str, Any], rng: np.random.Generator, melange: bool = False, centrer: bool = False) -> dict[str, Any]:
    """Un test par paramètre + un test de l'ensemble. `melange` : placebo, lignes de variables permutées (apprentissage et test séparément).
    `centrer` (variante du 31/10, décidée après le premier run, voir le protocole) : la sortie ŝ est centrée sur sa moyenne du test, ce qui retire le décalage
    de niveau entre les deux saisons ; les buts du test n'interviennent pas dans ce centrage."""
    XA, XT = App["X"], Test["X"]
    if melange:
        XA, XT = XA[rng.permutation(len(XA))], XT[rng.permutation(len(XT))]
    ZA, mu, sd = standardiser(XA)
    ZT, _, _ = standardiser(XT, mu, sd)                                    # statistiques de l'apprentissage, figées
    rA = (App["y"] - App["lam"]) / np.sqrt(App["lam"])
    blocs = np.concatenate([App["mois"], App["mois"]])
    ll0 = ll_pur(Test)
    res: dict[str, Any] = {}
    for g, cols in App["index"].items():
        Zg = ZA[:, cols]
        alpha = choisir_alpha(Zg, rA, blocs)
        th = ridge(Zg, rA, alpha)
        s = (ZT[:, cols] - ZA[:, cols].mean(axis=0)) @ th
        s = s - s.mean() if centrer else s
        d = gain_ll(Test, s, ll0)
        b = bootstrap(d, rng)
        res[g] = {**b, "alpha": alpha, "coef": [round(float(x), 5) for x in th], "retenu": retenu(b["bas"]),
                  "manquants_app": int(np.sum(~np.isfinite(XA[:, cols])))}
    h = holm({g: v["p"] for g, v in res.items()})
    for g in res:
        res[g]["retenu_holm"] = h[g]
    alpha = choisir_alpha(ZA, rA, blocs)
    th = ridge(ZA, rA, alpha)
    s_ens = (ZT - ZA.mean(axis=0)) @ th
    d = gain_ll(Test, s_ens - s_ens.mean() if centrer else s_ens, ll0)
    ens = {**bootstrap(d, rng), "alpha": alpha, "colonnes": int(ZA.shape[1])}
    return {"parametres": res, "ensemble": ens}


# ----------------------------------------------------------------------------- exécution
def lignes_saison(bloc: list[dict], saison: str, hp: dict[str, Any], log=print) -> dict[str, Any]:
    t0 = time.time()
    par_ligue = CAL._regrouper([m for m in bloc if m["saison"] == saison])
    res = CAL.marche_avant(par_ligue, {k: hp[k] for k in ("sigma", "xi", "rho")}, avec_facteurs=False, extra=extra)
    log(f"  {saison} : {len(res)} matchs passent le contrat 1.5 ({time.time() - t0:.0f} s)")
    return construire_lignes(res)


def rapport_md(out: dict[str, Any]) -> str:
    p = out["parametres"]
    L = [f"# Piste A : criblage des paramètres du Module 1 (résultats, variante {'centrée sur le test' if out.get('variante') == 'centree' else 'sans centrage'})", "",
         f"Protocole : `docs/DC_CRIBLAGE_PROTOCOLE.md` (commité avant le calcul). Apprentissage : Football-Data 2025-26, {out['apprentissage']['matchs']} matchs "
         f"({out['apprentissage']['periode'][0]} au {out['apprentissage']['periode'][1]}). Test : Football-Data 2026-27, {out['test']['matchs']} matchs "
         f"({out['test']['periode'][0]} au {out['test']['periode'][1]}). Aucun match de l'archive ni aucun pari : mesure sur la log-vraisemblance du score.", "",
         f"Décalage moyen du résidu de Pearson (Dixon-Coles pur) : {out['biais_residu']['apprentissage']:+.4f} en apprentissage, {out['biais_residu']['test']:+.4f} en test.", "",
         f"**Retenus selon la règle de Patrick (borne basse > 0) : {out['nb_retenus']} sur {len(p)}.** Après Holm : {out['nb_retenus_holm']}. "
         f"Placebos ({out['placebo']['tirages']} tirages, variables permutées) : {out['placebo']['passent_par_tirage']} paramètres « retenus » par tirage "
         f"(attendu par le hasard : environ {len(p) * 0.025:.1f}).", "",
         "| Paramètre | Coef. propre / adverse | Gain moyen (×10⁻⁴) | Intervalle 95 % (×10⁻⁴) | MDE (×10⁻⁴) | p | Règle | Holm |", "|---|---|---|---|---|---|---|---|"]
    for g, v in sorted(p.items(), key=lambda kv: -kv[1]["moyenne"]):
        c = v["coef"]
        coef = f"{c[0]:+.3f} / {c[1]:+.3f}" if len(c) == 2 else f"{len(c)} colonnes"
        L.append(f"| {g} | {coef} | {v['moyenne'] * 1e4:+.2f} | [{v['bas'] * 1e4:+.2f} ; {v['haut'] * 1e4:+.2f}] | {v['mde'] * 1e4:.2f} | {v['p']:.4f} | "
                 f"{'retenu' if v['retenu'] else 'retiré'} | {'oui' if v['retenu_holm'] else 'non'} |")
    e = out["ensemble"]
    L += ["", f"Ensemble (toutes les colonnes, {e['colonnes']}, ridge commun, α = {e['alpha']:g}) : gain moyen {e['moyenne'] * 1e4:+.2f}×10⁻⁴, "
              f"intervalle [{e['bas'] * 1e4:+.2f} ; {e['haut'] * 1e4:+.2f}]×10⁻⁴, MDE {e['mde'] * 1e4:.2f}×10⁻⁴."]
    return "\n".join(L) + "\n"


def lancer(placebos: int, cache: Path | None, centrer: bool = False, log=print) -> dict[str, Any]:
    bloc = D.charger_bloc()
    hp = json.loads(CAL.PARAMS.read_text())
    if cache and cache.exists():
        App, Test = pickle.loads(cache.read_bytes())
    else:
        App, Test = lignes_saison(bloc, "2526", hp, log), lignes_saison(bloc, "2627", hp, log)
        if cache:
            cache.write_bytes(pickle.dumps((App, Test)))
    rng = np.random.default_rng(20261031)
    log("criblage réel…")
    reel = cribler(App, Test, rng, centrer=centrer)
    passent = []
    for k in range(placebos):
        pl = cribler(App, Test, np.random.default_rng(1000 + k), melange=True, centrer=centrer)
        passent.append(sum(v["retenu"] for v in pl["parametres"].values()))
        log(f"  placebo {k + 1}/{placebos} : {passent[-1]} paramètres retenus")
    p = reel["parametres"]
    out = {"variante": "centree" if centrer else "sans_centrage", "apprentissage": {"matchs": App["n"], "periode": App["dates"]}, "test": {"matchs": Test["n"], "periode": Test["dates"]},
           "biais_residu": {"apprentissage": float(np.mean((App["y"] - App["lam"]) / np.sqrt(App["lam"]))),
                            "test": float(np.mean((Test["y"] - Test["lam"]) / np.sqrt(Test["lam"])))},
           "hyperparametres": {k: hp[k] for k in ("sigma", "xi", "rho")}, "parametres": p, "ensemble": reel["ensemble"],
           "nb_retenus": sum(v["retenu"] for v in p.values()), "nb_retenus_holm": sum(v["retenu_holm"] for v in p.values()),
           "placebo": {"tirages": placebos, "passent_par_tirage": passent}}
    (SORTIE_JSON_CENTRE if centrer else SORTIE_JSON).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (SORTIE_MD_CENTRE if centrer else SORTIE_MD).write_text(rapport_md(out))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--placebos", type=int, default=10)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--centrer", action="store_true")
    a = ap.parse_args()
    o = lancer(a.placebos, a.cache, a.centrer)
    print(f"retenus (règle) : {o['nb_retenus']} / {len(o['parametres'])} ; après Holm : {o['nb_retenus_holm']} ; placebos : {o['placebo']['passent_par_tirage']}")
