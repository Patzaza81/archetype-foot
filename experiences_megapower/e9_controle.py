"""E9 : contrôle de E7/E8. Les gains viennent-ils de la SIMILARITÉ des profils, ou simplement du niveau récent du championnat ?
Comparaison sur C, par marché, de : (a) M0 + fréquence récente du marché dans le championnat (300 jours), (b) M0 + voisins similaires du championnat, (c) les deux, (d) M0 + variables de croisements (L1) + fréquence du championnat."""
import sys, warnings, numpy as np
src = open("e8_similarite.py").read().split("res = {}")[0]
sys.argv = ["e8", "bloc"]; exec(src)
from sklearn.linear_model import LogisticRegression as LR
# fréquence récente du marché dans le même championnat (300 jours, strictement avant le jour du match)
ligf = np.full(Y.shape, np.nan, np.float32); ligN = np.zeros(n, int)
for c in np.unique(comp):
    ix = np.where(comp == c)[0]
    for t, i in enumerate(ix):
        w = ix[(d[ix] < d[i]) & (d[ix] >= d[i] - 300)]
        ligN[i] = len(w)
        if len(w) >= MIN_VOIS: ligf[i] = Y[w].mean(0)
freq, dist, nv = voisins("champ")
ok = (nv >= MIN_VOIS) & (ligN >= MIN_VOIS)
sA = np.where(ok & (np.arange(n) < iA))[0]; sB = np.where(ok & (np.arange(n) >= iA) & (np.arange(n) < iB))[0]; sC = np.where(ok & (np.arange(n) >= iB))[0]; sAB = np.concatenate([sA, sB])
print(f"matchs retenus A={len(sA)} B={len(sB)} C={len(sC)}")
lo_, hi_ = np.percentile(X[:iA], 1, axis=0), np.percentile(X[:iA], 99, axis=0); Xc = np.clip(X, lo_, hi_); Zx = (Xc - Xc[:iA].mean(0)) / (Xc[:iA].std(0) + 1e-9)
def L1(F, y, c): return LR(penalty="l1", solver="liblinear", C=c, max_iter=2000).fit(F, y)
print("marché | (a) fréq. championnat | (b) voisins | (c) a+b | (d) croisements+fréq. champ. | (c) vs (a) : apport propre de la similarité | blocs C de (a)")
tab = {}
for j, k in enumerate(C.CLES):
    y, lp = Y[:, j], lg(P[:, j]); lf = lg((ligf[:, j] * 50 + 2 * P[:, j]) / 52)
    best = None
    for q in range(len(KS)):
        f = lg((freq[:, q, j] * KS[q] + 2 * P[:, j]) / (KS[q] + 2)); Fm = np.c_[lp, f]
        l = ll(LR(C=1e6, max_iter=1000).fit(Fm[sA], y[sA]).predict_proba(Fm[sB])[:, 1], y[sB]).mean()
        if best is None or l < best[0]: best = (l, q, f)
    f = best[2]; yc = y[sC]
    def ev(F):
        m = LR(C=1e6, max_iter=1000).fit(F[sAB], y[sAB]); return ll(m.predict_proba(F[sC])[:, 1], yc)
    l0 = ev(lp[:, None]); la = ev(np.c_[lp, lf]); lb = ev(np.c_[lp, f]); lc = ev(np.c_[lp, lf, f])
    F4 = np.c_[10 * lp, 10 * lf, Zx]; bb = None
    for c in (0.003, 0.01, 0.03, 0.1, 0.3):
        l = ll(L1(F4[sA], y[sA], c).predict_proba(F4[sB])[:, 1], y[sB]).mean()
        if bb is None or l < bb[0]: bb = (l, c)
    ld = ll(L1(F4[sAB], y[sAB], bb[1]).predict_proba(F4[sC])[:, 1], yc)
    se = lambda x: x.std(ddof=1) / np.sqrt(len(x)); g = lambda l: (l0 - l)
    tab[k] = (g(la).mean(), g(lb).mean(), g(lc).mean(), g(ld).mean())
    own = la - lc
    st = [g(la)[t].mean() for t in np.array_split(np.arange(len(yc)), 3)]
    print(f"{k:19s} {1e4*g(la).mean():+6.1f}±{1e4*se(g(la)):4.1f} | {1e4*g(lb).mean():+6.1f} | {1e4*g(lc).mean():+6.1f} | {1e4*g(ld).mean():+6.1f}±{1e4*se(g(ld)):4.1f} | {1e4*own.mean():+6.1f}±{1e4*se(own):4.1f} | " + " ".join(f"{1e4*s:+.0f}" for s in st))
