"""Etape 6c: carte des facteurs predictifs reels, par competition et marche (aucun melange).
Pour chaque variable (32) isolement: regression logistique a 2 parametres [logit P1, variable] ajustee sur les matchs STRICTEMENT anterieurs a la saison test (2324, 2425, 2526), comparee a P1 (et a P1 recalibre seul).
Gain = perte log P1 - perte du modele, par match; z, saisons gagnantes, signe du coefficient stable. Seuil de Bonferroni sur l'ensemble des tests. Aucune correction deployee.
Statistiques d'archive: pas une performance de moteur."""
import json, math, os, sys, warnings
import numpy as np
from multiprocessing import Pool
from statistics import NormalDist
from sklearn.linear_model import LogisticRegression
import pouvoir_predictif as pp
import pouvoir_predictif_v3 as v3
import regles_durables as rd
warnings.filterwarnings("ignore")
RACINE = pp.RACINE; SAISONS = pp.SAISONS; EVT = pp.EVT; EPS = 1e-9; TESTS = [2, 3, 4]; VARS = [n for n in rd.NOMS if n != "logit_P1"]

def analyser(code):
    PR = rd.preparer(code)
    if PR is None: return None
    S, D, Y, valide, X, P1, start = PR["S"], PR["D"], PR["Y"], PR["valide"], PR["X"], PR["P1"], PR["start"]; out = {}
    for e in range(7):
        y = Y[:, e]; p = P1[:, e]; lp = v3.lg(p); res = {}
        # recalibrage seul (reference supplementaire)
        cal = {}
        for t in TESTS:
            tr = valide & (D < start[t]); te = valide & (S == t)
            m = LogisticRegression(C=1e3, max_iter=200).fit(lp[tr, None], y[tr]); cal[t] = (te, np.clip(m.predict_proba(lp[te, None])[:, 1], EPS, 1 - EPS))
        for j, nom in enumerate(VARS):
            g = {}; coefs = []; gc = {}
            for t in TESTS:
                tr = valide & (D < start[t]); te = valide & (S == t); mu, sd = X[tr, j].mean(), X[tr, j].std() + 1e-9
                A = np.column_stack([lp, (X[:, j] - mu) / sd]); m = LogisticRegression(C=1e3, max_iter=200).fit(A[tr], y[tr]); pc = np.clip(m.predict_proba(A[te])[:, 1], EPS, 1 - EPS)
                g[t] = v3.lb(p[te], y[te]) - v3.lb(pc, y[te]); gc[t] = v3.lb(cal[t][1], y[te]) - v3.lb(pc, y[te]); coefs.append(float(m.coef_[0, 1]))
            d = np.concatenate([g[t] for t in TESTS]); dc = np.concatenate([gc[t] for t in TESTS]); n = len(d); se = d.std(ddof=1) / math.sqrt(n); sc = dc.std(ddof=1) / math.sqrt(n)
            res[nom] = {"gain": round(float(d.mean()), 5), "z": round(float(d.mean() / se), 2), "gain_vs_recalibre": round(float(dc.mean()), 5), "z_vs_recalibre": round(float(dc.mean() / sc), 2) if sc > 0 else None,
                        "saisons_gagnantes": sum(1 for t in TESTS if g[t].mean() > 0), "signe_stable": bool(len(set(np.sign(coefs))) == 1), "coef": [round(c, 3) for c in coefs]}
        d0 = np.concatenate([v3.lb(p[te], y[te]) - v3.lb(c, y[te]) for t in TESTS for te, c in [cal[t]]])
        out[EVT[e]] = {"n_test": int(len(d0)), "recalibrage_seul": {"gain": round(float(d0.mean()), 5), "z": round(float(d0.mean() / (d0.std(ddof=1) / math.sqrt(len(d0)))), 2)}, "facteurs": res}
    return out

def _un(c):
    try: return c, analyser(c)
    except Exception as ex: return c, {"erreur": repr(ex)}

def main(codes=None):
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    codes = codes or sorted(cl)
    with Pool(2) as pool: R = dict(pool.map(_un, codes, chunksize=1))
    R = {c: r for c, r in R.items() if r}
    n = sum(len(m["facteurs"]) for r in R.values() if "erreur" not in r for m in r.values()); zb = NormalDist().inv_cdf(1 - 0.05 / n)
    for r in R.values():
        if "erreur" in r: continue
        for m in r.values():
            for f in m["facteurs"].values():
                f["verdict"] = "robuste" if (f["gain_vs_recalibre"] > 0 and f["z_vs_recalibre"] and f["z_vs_recalibre"] > zb and f["saisons_gagnantes"] == 3 and f["signe_stable"]) else ("avantage" if (f["gain_vs_recalibre"] > 0 and f["z_vs_recalibre"] and f["z_vs_recalibre"] > 1.96 and f["saisons_gagnantes"] >= 2 and f["signe_stable"]) else "non")
    json.dump({"description": "Etape 6c: facteurs predictifs isoles (voir facteurs_predictifs.py).", "tests_total": n, "z_bonferroni": round(zb, 2), "competitions": R}, open(os.path.join(RACINE, "data", "inventaire", "facteurs_predictifs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return R

if __name__ == "__main__":
    main(sys.argv[1:] or None)
