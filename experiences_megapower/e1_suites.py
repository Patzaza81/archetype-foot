"""E1 : suites arithmétique / géométrique et variantes de tendance (A à E), par marché, chronologique A (choix) / B (validation) / C (test)."""
import json, pickle, itertools, time
import numpy as np
from commun import *

t0 = time.time()
matchs, sc, lig = charger()
rows = []
for m in matchs:
    F = features(m, lig)
    if F is not None:
        F["y"] = sc.get(m["id"])
        rows.append(F)
J = [r for r in rows if r["y"] is not None]
jours = sorted(r["jour"] for r in J)
dA, dB = jours[len(jours) // 2], jours[(3 * len(jours)) // 4]
P = {"A": [r for r in J if r["jour"] < dA], "B": [r for r in J if dA <= r["jour"] < dB], "C": [r for r in J if r["jour"] >= dB]}
print({k: len(v) for k, v in P.items()}, "coupes", dA, dB, round(time.time() - t0))
pickle.dump((rows, dA, dB), open("/tmp/audit_rows.pkl", "wb"))


def evalue(R, sp, beta=BETA_GD):
    la, lb = zip(*(lambdas(r, sp, beta) for r in R))
    h, a = zip(*(r["y"] for r in R))
    return perte_scores(la, lb, h, a)


# 1. recherche sur A du meilleur réglage pour chaque type de suite, normalisée (E) ou brute (B, C, D)
types = ["arith", "geo", "both", "ols", "ewma"]
best = {}
for tp, norm in itertools.product(types, (False, True)):
    cands = [dict(type=tp, theta=th, win=w, norm=norm, decay=dc) for th in (0.1, 0.25, 0.5, 1.0) for w in (3, 6, 10) for dc in ((0.6, 0.85) if tp == "ewma" else (0.8,))]
    pert = [(evalue(P["A"], c), c) for c in cands]
    best[(tp, norm)] = min(pert, key=lambda x: x[0])
base = {k: evalue(P[k], None) for k in "ABC"}
print("sans suite", base, round(time.time() - t0))
res = {"sans_suite": {k: base[k] for k in "ABC"}}
for (tp, norm), (pa, c) in best.items():
    res[f"{tp}|{'normalisee' if norm else 'brute'}"] = {"reglage": c, "perte": {"A": pa, "B": evalue(P["B"], c), "C": evalue(P["C"], c)}}
json.dump(res, open("/tmp/e1_pertes.json", "w"), indent=1, default=float)
for k, v in res.items():
    print(k, v if k == "sans_suite" else {kk: (round(vv, 5) if isinstance(vv, float) else vv) for kk, vv in v["perte"].items()}, v.get("reglage") if k != "sans_suite" else "")

# 2. par marché : Brier de chaque variante vs sans suite, sur B et C (écart apparié par match, erreur-type)
VAR = {"A_sans": None, "B_arith_brute": best[("arith", False)][1], "C_geo_brute": best[("geo", False)][1], "D_both_brute": best[("both", False)][1],
       "E_norm_arith": best[("arith", True)][1], "E_norm_geo": best[("geo", True)][1], "E_norm_both": best[("both", True)][1],
       "ols_norm": best[("ols", True)][1], "ewma_norm": best[("ewma", True)][1], "ols_brute": best[("ols", False)][1], "ewma_brute": best[("ewma", False)][1]}
def Y(R):
    return np.array([V.TABLE[0, 0, 0] * 0 + TAB[min(r["y"][0], 10), min(r["y"][1], 10)] for r in R])
sortie = {}
for per in ("A", "B", "C"):
    R = P[per]; y = Y(R)
    for nom, sp in VAR.items():
        la, lb = zip(*(lambdas(r, sp) for r in R))
        p = probas(np.array(la), np.array(lb))
        sortie[(per, nom)] = (p, y)
tab = {}
for mk in CLES:
    k = IDX[mk]
    tab[mk] = {}
    for nom in VAR:
        if nom == "A_sans":
            continue
        d = {}
        for per in ("B", "C"):
            p0, y = sortie[(per, "A_sans")]; p1, _ = sortie[(per, nom)]
            e0, e1 = (p0[:, k] - y[:, k]) ** 2, (p1[:, k] - y[:, k]) ** 2
            diff = e1 - e0
            d[per] = (float(diff.mean()), float(diff.std(ddof=1) / np.sqrt(len(diff))), float(e0.mean()))
        tab[mk][nom] = d
pickle.dump((tab, res, {k: len(v) for k, v in P.items()}), open("/tmp/e1_tab.pkl", "wb"))
# synthèse : une suite « utile » pour un marché = améliore le Brier (écart < 0) sur B ET sur C, au moins un écart significatif à 1,96
print("\\nMarché | meilleure variante sur B (choisie) | écart B (±se) | écart C (±se) | verdict")
verd = {}
for mk, v in tab.items():
    nom = min(v, key=lambda n: v[n]["B"][0])
    b, c = v[nom]["B"], v[nom]["C"]
    utile = b[0] < 0 and c[0] < 0 and (b[0] < -1.96 * b[1] or c[0] < -1.96 * c[1])
    verd[mk] = (nom, b, c, utile)
    print(f"{mk:22s}|{nom:15s}| {b[0]*1e4:+.2f} ±{b[1]*1e4:.2f} | {c[0]*1e4:+.2f} ±{c[1]*1e4:.2f} | {'UTILE' if utile else 'inutile'}")
pickle.dump(verd, open("/tmp/e1_verd.pkl", "wb"))
print(round(time.time() - t0), "s")
