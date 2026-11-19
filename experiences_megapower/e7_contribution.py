"""E7b : contribution marginale des croisements de buts, marché par marché. Découpage chronologique A (50 %) / B (25 %, choix de la régularisation) / C (25 %, test jamais utilisé).
M0 = probabilité du modèle de base recalibrée (a + b·logit P). M1 = M0 + variables de croisements (régression L1, variables inutiles éliminées). M2 = arbres peu profonds (interactions)."""
import sys, warnings, numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
import commun as C
nom = sys.argv[1] if len(sys.argv) > 1 else "bloc"
T = np.load(f"sorties/table_{nom}.npz", allow_pickle=True)
X, P, Y, jour, names = T["X"], T["P"], T["Y"], T["jour"], list(T["names"])
o = np.argsort(jour, kind="stable"); X, P, Y, jour = X[o], P[o], Y[o], jour[o]
n = len(X); iA, iB = int(n * .5), int(n * .75)
sA, sB, sC = slice(0, iA), slice(iA, iB), slice(iB, n)
lo, hi = np.percentile(X[sA], 1, axis=0), np.percentile(X[sA], 99, axis=0)
Xc = np.clip(X, lo, hi); mu, sd = Xc[sA].mean(0), Xc[sA].std(0) + 1e-9; Z = (Xc - mu) / sd
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def ll(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
def fit(Zs, y, c): 
    m = LogisticRegression(penalty="l1", solver="liblinear", C=c, max_iter=2000); m.fit(Zs, y); return m
print(f"{nom} : n={n} A={iA} B={iB-iA} C={n-iB} ({jour[0]}→{jour[iA-1]} | {jour[iA]}→{jour[iB-1]} | {jour[iB]}→{jour[-1]})")
print("marché | taux C | M0 logloss C | Δ M1 (±se) | Δ M2 (±se) | stab. M1 (3 blocs de C) | variables retenues (coef sur A+B, par |coef|)")
res = {}
for j, k in enumerate(C.CLES):
    y, lp = Y[:, j], lg(P[:, j])
    F0 = (10 * lp)[:, None]
    F1 = np.hstack([F0, Z])
    # M0 : ajusté sur A, réajusté sur A+B pour C
    m0 = LogisticRegression(C=1e6, max_iter=1000).fit(F0[:iB], y[:iB]); p0 = m0.predict_proba(F0[sC])[:, 1]
    # M1 : régularisation choisie sur B
    best = None
    for c in (0.003, 0.01, 0.03, 0.1, 0.3, 1.0):
        mm = fit(F1[sA], y[sA], c); l = ll(mm.predict_proba(F1[sB])[:, 1], y[sB]).mean()
        if best is None or l < best[0]: best = (l, c)
    m1 = fit(F1[:iB], y[:iB], best[1]); p1 = m1.predict_proba(F1[sC])[:, 1]
    # M2 : arbres de profondeur 2, arrêt précoce sur B
    best2 = None
    for lr, it in ((0.03, 60), (0.03, 150), (0.03, 300)):
        g = HistGradientBoostingClassifier(max_depth=2, learning_rate=lr, max_iter=it, min_samples_leaf=80, l2_regularization=5.0, random_state=0).fit(np.hstack([lp[:, None], X])[sA], y[sA])
        l = ll(g.predict_proba(np.hstack([lp[:, None], X])[sB])[:, 1], y[sB]).mean()
        if best2 is None or l < best2[0]: best2 = (l, lr, it)
    g = HistGradientBoostingClassifier(max_depth=2, learning_rate=best2[1], max_iter=best2[2], min_samples_leaf=80, l2_regularization=5.0, random_state=0).fit(np.hstack([lp[:, None], X])[:iB], y[:iB])
    p2 = g.predict_proba(np.hstack([lp[:, None], X])[sC])[:, 1]
    yc = y[sC]; d1 = ll(p0, yc) - ll(p1, yc); d2 = ll(p0, yc) - ll(p2, yc)     # >0 = gain
    se = lambda d: d.std(ddof=1) / np.sqrt(len(d))
    th = np.array_split(np.arange(len(yc)), 3); st = [d1[t].mean() for t in th]
    co = m1.coef_[0][1:]; sel = [(names[i], co[i]) for i in np.argsort(-np.abs(co)) if abs(co[i]) > 1e-6][:6]
    res[k] = (d1.mean(), se(d1), d2.mean(), se(d2))
    print(f"{k:19s} {yc.mean():.3f} {ll(p0,yc).mean():.4f} | {1e4*d1.mean():+6.1f}±{1e4*se(d1):4.1f} | {1e4*d2.mean():+6.1f}±{1e4*se(d2):4.1f} | {' '.join(f'{1e4*s:+.0f}' for s in st)} | " + ", ".join(f"{a}:{b:+.2f}" for a, b in sel))
print("(Δ en 1e-4 de log-loss par match ; >0 = la variable ajoute de l'information sur C)")
