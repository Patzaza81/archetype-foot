"""E2 : une méthode par marché (variables retenues par sélection sur A->B), seuils/intervalles par marché (choisis sur B, confirmés sur C), récurrence, championnats."""
import csv, json, pickle, time, math
import numpy as np
from scipy.optimize import minimize
from commun import *

t0 = time.time()
rows, dA, dB = pickle.load(open("/tmp/audit_rows.pkl", "rb"))
Z = lambda v: np.clip(v, 1e-4, 1 - 1e-4)
lg = lambda p: np.log(Z(p) / (1 - Z(p)))
# base : modèle actuel (sans suite) -> probabilités des trois scénarios
la, lb, sa, sb = [], [], [], []
for r in rows:
    x, y = lambdas(r)
    la.append(x); lb.append(y)
    sa.append(math.hypot(r["attA"]["se"] / r["attA"]["idx"], r["defB"]["se"] / r["defB"]["idx"]))
    sb.append(math.hypot(r["attB"]["se"] / r["attB"]["idx"], r["defA"]["se"] / r["defA"]["idx"]))
la, lb, sa, sb = map(np.array, (la, lb, sa, sb))
PN = probas(la, lb)
coins = [probas(la * np.exp(i * sa), lb * np.exp(j * sb)) for i in (-1, 1) for j in (-1, 1)]
PC, PF = np.min(coins, axis=0), np.max(coins, axis=0)
jour = np.array([r["jour"] for r in rows]); comp = np.array([r["comp"] for r in rows])
joue = np.array([r["y"] is not None for r in rows])
YY = np.full(PN.shape, np.nan)
for t, r in enumerate(rows):
    if r["y"] is not None:
        YY[t] = TAB[min(r["y"][0], 10), min(r["y"][1], 10)]
g = lambda r, k: 0.0 if r["ecarts"].get(k) is None else r["ecarts"][k]
FE = {"ppm": np.array([g(r, "ppm") for r in rows]), "gd": np.array([g(r, "gd") for r in rows]), "xgd": np.array([g(r, "xgd") for r in rows]),
      "xpts": np.array([g(r, "xpts") for r in rows]), "surperf": np.array([g(r, "surperf") for r in rows]),
      "att_att": np.array([math.log(r["attA"]["idx"] / r["attB"]["idx"]) for r in rows]),        # branche 1 : attaque A contre attaque B
      "def_def": np.array([math.log(r["defA"]["idx"] / r["defB"]["idx"]) for r in rows]),        # branche 2 : défense A contre défense B
      "lam_A": np.log(la), "lam_B": np.log(lb),                                                  # branches 3 et 4 : attaque A / défense B, attaque B / défense A
      "disp": np.array([np.std(r["attA"]["z"]) + np.std(r["attB"]["z"]) for r in rows])}        # stabilité des deux attaques
dA_i, dB_i = np.array(jour < dA), np.array(jour >= dB)
iA, iB, iC = joue & (jour < dA), joue & (jour >= dA) & (jour < dB), joue & (jour >= dB)


def matrice(k, cols, idx):
    X = [np.ones(idx.sum())]
    for c in cols:
        v = lg(PN[idx, k]) if c == "pn" else lg(PC[idx, k]) if c == "pc" else FE[c][idx]
        X.append(v)
    return np.column_stack(X)


def fit(X, y, ridge=1e-2):
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0) + 1e-9
    Xs = np.column_stack([X[:, 0], (X[:, 1:] - mu) / sd])
    w0 = np.zeros(Xs.shape[1]); w0[1] = 1.0
    f = lambda w: float(np.logaddexp(0, Xs @ w).sum() - (y * (Xs @ w)).sum() + ridge * (w[1:] ** 2).sum())
    gr = lambda w: Xs.T @ (1 / (1 + np.exp(-(Xs @ w))) - y) + 2 * ridge * np.r_[0, w[1:]]
    w = minimize(f, w0, jac=gr, method="BFGS").x
    return (w, mu, sd)


def pred(m, X):
    w, mu, sd = m
    Xs = np.column_stack([X[:, 0], (X[:, 1:] - mu) / sd])
    return 1 / (1 + np.exp(-(Xs @ w)))


CAND = ["pc", "ppm", "gd", "xgd", "xpts", "surperf", "att_att", "def_def", "lam_A", "lam_B", "disp"]
choix, sortie, wf = {}, {}, {}
for mk in CLES:
    k = IDX[mk]
    yA, yB, yC = YY[iA, k], YY[iB, k], YY[iC, k]
    cols = ["pn"]
    while len(cols) < 4:
        m0 = fit(matrice(k, cols, iA), yA); e0 = -(yB * np.log(Z(pred(m0, matrice(k, cols, iB)))) + (1 - yB) * np.log(1 - Z(pred(m0, matrice(k, cols, iB)))))
        best = None
        for c in CAND:
            if c in cols:
                continue
            m1 = fit(matrice(k, cols + [c], iA), yA); p1 = Z(pred(m1, matrice(k, cols + [c], iB)))
            e1 = -(yB * np.log(p1) + (1 - yB) * np.log(1 - p1)); d = e1 - e0
            if d.mean() < -1.0 * d.std(ddof=1) / math.sqrt(len(d)) and (best is None or d.mean() < best[0]):
                best = (d.mean(), c)
        if best is None:
            break
        cols.append(best[1])
    choix[mk] = cols
    # test C : modèle choisi, ajusté sur A+B, comparé aux références
    iAB = iA | iB
    mS = fit(matrice(k, cols, iAB), YY[iAB, k]); mP = fit(matrice(k, ["pn"], iAB), YY[iAB, k])
    pS, pP, pR = pred(mS, matrice(k, cols, iC)), pred(mP, matrice(k, ["pn"], iC)), PN[iC, k]
    base_rate = float(YY[iAB, k].mean())
    sm = probas(np.array([r["simple"][0] for r in np.array(rows, dtype=object)[iC]]), np.array([r["simple"][1] for r in np.array(rows, dtype=object)[iC]]))[:, k]
    out = {"cols": cols, "taux_base": base_rate, "n_C": int(iC.sum()), "taux_C": float(yC.mean())}
    for nom, p in (("base", np.full(len(yC), base_rate)), ("moyenne_simple", sm), ("megapower_brut", pR), ("megapower_calibre", pP), ("methode_marche", pS)):
        out[nom] = (brier(p, yC), logloss(p, yC))
    d = (pS - yC) ** 2 - (pP - yC) ** 2
    out["delta_brier_methode_vs_calibre"] = (float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d))))
    sortie[mk] = out
    # prédictions marche avant (jour par jour) sur B et C avec le jeu de variables choisi
    P_ = np.full(len(rows), np.nan)
    for d_ in sorted(set(jour[iB | iC])):
        tr = joue & (jour < d_); te = joue & (jour == d_)
        if tr.sum() < 200 or not te.any():
            continue
        mm = fit(matrice(k, cols, tr), YY[tr, k]); P_[te] = pred(mm, matrice(k, cols, te))
    wf[mk] = P_
    print(mk, cols, round(time.time() - t0), flush=True)
pickle.dump((choix, sortie, wf, jour, comp, YY, dA, dB), open("/tmp/e2.pkl", "wb"))
