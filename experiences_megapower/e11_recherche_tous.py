"""E11b : recherche exhaustive « dans tous les sens » : toutes les variables seules, tous les produits de deux variables (croisements, rapports, interactions), marché par marché.
Base = modèle actuel recalibré + fréquence récente du marché dans le championnat. Test de score (z) sur A et sur B ; une configuration n'est retenue que si Z=(zA+zB)/√2 dépasse le seuil de Bonferroni sur TOUTES les configurations testées ;
les retenues sont ensuite jugées sur C, jamais utilisé. Aucune cote."""
import sys, warnings, numpy as np
from scipy.stats import norm
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression as LR
import commun as C
from commun import *
T = np.load("sorties/table2_bloc_tous.npz", allow_pickle=True)
o = np.argsort(T["jour"], kind="stable"); X, P, Y, jour, comp, names = T["X"][o], T["P"][o], T["Y"][o], T["jour"][o], T["comp"][o], list(T["names"])
STAT = ("ht_", "sh_", "sot_", "co_", "yc_")
V = [i for i, n in enumerate(names) if not any(n[2:].startswith(s) for s in STAT)]
# fréquence récente du marché dans le championnat (tous les matchs connus, 300 jours)
mb, sb, _ = C.charger_bloc(); cols = list(range(len(C.NOMS))); par = {}
for m in mb:
    if m["id"] in sb: par.setdefault(m["competition"], []).append((np.datetime64(m["jour"], "D").astype(int), C.TAB[min(sb[m["id"]][0], 10), min(sb[m["id"]][1], 10)][cols]))
LF = np.full(Y.shape, np.nan, np.float32)
for i, (c, j) in enumerate(zip(comp, jour)):
    dj = np.datetime64(j, "D").astype(int); L = [y for d, y in par.get(c, []) if dj - 300 <= d < dj]
    if len(L) >= 20: LF[i] = np.mean(L, axis=0)
ok = ~np.isnan(LF[:, 0]); X, P, Y, jour, LF = X[ok], P[ok], Y[ok], jour[ok], LF[ok]
n = len(X); iA, iB = int(n * .5), int(n * .75); sA, sB, sC = slice(0, iA), slice(iA, iB), slice(iB, n)
print(f"n={n} A={iA} B={iB-iA} C={n-iB} ({jour[0]}→{jour[iA-1]} | {jour[iA]}→{jour[iB-1]} | {jour[iB]}→{jour[-1]}) ; variables de base {len(V)}")
Xv = X[:, V]; nm = [names[i] for i in V]
lo, hi = np.nanpercentile(Xv[sA], 1, axis=0), np.nanpercentile(Xv[sA], 99, axis=0); Xv = np.clip(Xv, lo, hi)
mu, sd = np.nanmean(Xv[sA], axis=0), np.nanstd(Xv[sA], axis=0) + 1e-9; Z = np.nan_to_num((Xv - mu) / sd).astype(np.float32)
iu = np.triu_indices(len(V)); Q = np.hstack([Z, (Z[:, iu[0]] * Z[:, iu[1]])]).astype(np.float32)
qn = nm + [f"{nm[a]}*{nm[b]}" for a, b in zip(*iu)]
Q = (Q - Q[sA].mean(0)) / (Q[sA].std(0) + 1e-9); Ncand = Q.shape[1]
thr = norm.isf(0.05 / (2 * Ncand)); print(f"configurations testées par marché : {Ncand} ; seuil de Bonferroni Z ≥ {thr:.2f}")
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def ll(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
DIST0 = ["1", "N", "2", "12", "total_plus_0.5", "total_plus_1.5", "total_plus_2.5", "total_moins_3.5", "total_moins_4.5", "btts_oui", "dom_plus_0.5", "ext_plus_0.5",
        "multibuts_1-3", "multibuts_2-4", "multibuts_1-4", "1N&total_plus_1.5", "N2&total_plus_1.5", "1N&total_moins_3.5", "N2&total_moins_3.5"]
seen = {}; DIST = []
for jj, nm_ in enumerate(C.NOMS):
    yv = Y[:, jj]; rate = yv.mean()
    if rate < 0.08 or rate > 0.95: continue
    h1, h2 = hash(yv.tobytes()), hash((1 - yv).tobytes())
    if h1 in seen or h2 in seen: continue
    seen[h1] = nm_; DIST.append(nm_)
print(len(DIST), "marchés distincts (taux entre 8 % et 95 %, sans doublon ni complément)")
def zscore(D, w, r, Qs):
    W = D.T @ (D * w[:, None]); beta = np.linalg.solve(W, D.T @ (Qs * w[:, None])); Qt = Qs - D @ beta
    return (Qt.T @ r) / np.sqrt(((Qt ** 2) * w[:, None]).sum(0) + 1e-9)
print("marché | qualifiées (Z≥seuil) | retenues (non redondantes) | Δ sur C vs base (±se) | Δ base vs modèle actuel sur C | blocs de C | configurations retenues (Z)")
for k in DIST:
    j = C.IDX[k]; y = Y[:, j]; lp = lg(P[:, j]); lf = lg((LF[:, j] * 50 + 2 * P[:, j]) / 52); D = np.c_[np.ones(n), lp, lf]
    b0 = LR(C=1e6, max_iter=1000, fit_intercept=False).fit(D[sA], y[sA]); p0 = b0.predict_proba(D)[:, 1]; w = p0 * (1 - p0); r = y - p0
    zA = zscore(D[sA], w[sA], r[sA], Q[sA]); zB = zscore(D[sB], w[sB], r[sB], Q[sB]); Zs = (zA + zB) / np.sqrt(2)
    qual = np.where((np.abs(Zs) >= thr) & (np.sign(zA) == np.sign(zB)))[0]; qual = qual[np.argsort(-np.abs(Zs[qual]))]
    chosen = []
    for q in qual:
        if all(abs(np.corrcoef(Q[sA, q], Q[sA, c])[0, 1]) < 0.8 for c in chosen): chosen.append(q)
        if len(chosen) >= 5: break
    yc = y[sC]; Dab = D[:iB]
    mb_ = LR(C=1e6, max_iter=1000, fit_intercept=False).fit(Dab, y[:iB]); pb = mb_.predict_proba(D[sC])[:, 1]
    m00 = LR(C=1e6, max_iter=1000).fit(lp[:iB, None], y[:iB]); pm = m00.predict_proba(lp[sC, None])[:, 1]
    if chosen:
        F = np.c_[10 * lp, 10 * lf, Q[:, chosen]]; mm = LR(C=1.0, max_iter=2000).fit(F[:iB], y[:iB]); pn = mm.predict_proba(F[sC])[:, 1]
        d = ll(pb, yc) - ll(pn, yc); se = d.std(ddof=1) / np.sqrt(len(d)); st = [d[t].mean() for t in np.array_split(np.arange(len(d)), 3)]
        r_ = f"{1e4*d.mean():+6.1f}±{1e4*se:4.1f} | " + " ".join(f"{1e4*s:+.0f}" for s in st)
    else: r_ = "     —       | "
    base = ll(pm, yc) - ll(pb, yc)
    print(f"{k:19s} {len(qual):3d} | {len(chosen)} | {r_} | {1e4*base.mean():+6.1f} | " + ", ".join(f"{qn[c]} ({Zs[c]:+.1f})" for c in chosen))
