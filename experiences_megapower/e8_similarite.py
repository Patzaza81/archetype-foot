"""E8 : similarité de profils entre MATCHS (profil des deux équipes ensemble + rapports de force + lieux), marché par marché. Buts seulement, aucune cote.
Pour chaque match : voisins = matchs déjà joués (jour strictement antérieur) au profil le plus proche ; fréquence de chaque marché chez les voisins = information supplémentaire.
Gain mesuré sur C (jamais utilisé), par rapport à M0 (modèle de base recalibré). Deux réservoirs : « championnat » (même compétition, 300 derniers jours) et « tous championnats »."""
import sys, warnings, numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
import commun as C
nom = sys.argv[1] if len(sys.argv) > 1 else "bloc"
T = np.load(f"sorties/table_{nom}.npz", allow_pickle=True)
o = np.argsort(T["jour"], kind="stable")
X, P, Y, jour, comp, names = T["X"][o], T["P"][o], T["Y"][o], T["jour"][o], T["comp"][o], list(T["names"])
n = len(X); iA, iB = int(n * .5), int(n * .75)
PROF = ["hgf", "hga", "bgf_a", "bga_a", "sd_hgf", "sd_hga", "sd_bgf", "sd_bga", "p0f_h", "p0a_h", "p0f_a", "p0a_a", "ppm_h", "ppm_a", "gap_ga", "gd_gap", "lig_tot"]
Z = X[:, [names.index(v) for v in PROF]]
lo, hi = np.percentile(Z[:iA], 1, axis=0), np.percentile(Z[:iA], 99, axis=0); Z = np.clip(Z, lo, hi)
Z = ((Z - Z[:iA].mean(0)) / (Z[:iA].std(0) + 1e-9)).astype(np.float32)
d = np.array(jour, dtype="datetime64[D]").astype(int)
start = np.searchsorted(d, d, side="left")            # premier indice du même jour : voisins = indices < start
KS = (20, 50, 100, 300); KM = max(KS); MIN_VOIS = 20
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def ll(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
def voisins(mode):
    """Retourne pour chaque match : fréquences (n, len(KS), 23), distance moyenne des k=20 plus proches, nombre de voisins valides."""
    freq = np.full((n, len(KS), Y.shape[1]), np.nan, np.float32); dist = np.full(n, np.nan, np.float32); nv = np.zeros(n, int)
    PAS = 400
    for a in range(0, n, PAS):
        b = min(n, a + PAS); hi_ = start[a:b].max()
        if hi_ < MIN_VOIS: continue
        D2 = ((Z[a:b, None, :] - Z[None, :hi_, :]) ** 2).sum(-1)
        jj = np.arange(hi_)[None, :]
        D2[jj >= start[a:b, None]] = np.inf
        if mode == "champ":
            D2[(comp[None, :hi_] != comp[a:b, None]) | (d[None, :hi_] < d[a:b, None] - 300)] = np.inf
        km = min(KM, hi_)
        idx = np.argpartition(D2, km - 1, axis=1)[:, :km]
        dd = np.take_along_axis(D2, idx, 1); so = np.argsort(dd, axis=1); idx = np.take_along_axis(idx, so, 1); dd = np.take_along_axis(dd, so, 1)
        for r in range(b - a):
            v = np.isfinite(dd[r]); m = int(v.sum()); nv[a + r] = m
            if m < MIN_VOIS: continue
            for q, k in enumerate(KS):
                kk = min(k, m); freq[a + r, q] = Y[idx[r, :kk]].mean(0)
            dist[a + r] = np.sqrt(dd[r, :min(20, m)]).mean()
    return freq, dist, nv
res = {}
for mode in ("champ", "tous"):
    freq, dist, nv = voisins(mode)
    ok = nv >= MIN_VOIS
    print(f"\n=== réservoir « {mode} » : matchs avec ≥{MIN_VOIS} voisins {ok.sum()}/{n} ; distance moyenne des 20 plus proches : médiane {np.nanmedian(dist):.2f}")
    sA = np.where(ok & (np.arange(n) < iA))[0]; sB = np.where(ok & (np.arange(n) >= iA) & (np.arange(n) < iB))[0]; sC = np.where(ok & (np.arange(n) >= iB))[0]
    sAB = np.concatenate([sA, sB]); print(f"A={len(sA)} B={len(sB)} C={len(sC)}")
    print("marché | Δ log-loss sur C (k choisi sur B) ±se | gain si voisins proches (1/3) | gain si voisins lointains (1/3) | blocs de C")
    out = {}
    for j, k in enumerate(C.CLES):
        y, lp = Y[:, j], lg(P[:, j])
        best = None
        for q in range(len(KS)):
            f = lg((freq[:, q, j] * KS[q] + 2 * P[:, j]) / (KS[q] + 2)) if True else None
            Fm = np.c_[lp, f]
            m1 = LogisticRegression(C=1e6, max_iter=1000).fit(Fm[sA], y[sA]); l = ll(m1.predict_proba(Fm[sB])[:, 1], y[sB]).mean()
            if best is None or l < best[0]: best = (l, q, Fm)
        q, Fm = best[1], best[2]
        m0 = LogisticRegression(C=1e6, max_iter=1000).fit(lp[sAB, None], y[sAB]); p0 = m0.predict_proba(lp[sC, None])[:, 1]
        m1 = LogisticRegression(C=1e6, max_iter=1000).fit(Fm[sAB], y[sAB]); p1 = m1.predict_proba(Fm[sC])[:, 1]
        dl = ll(p0, y[sC]) - ll(p1, y[sC]); se = dl.std(ddof=1) / np.sqrt(len(dl))
        dd = dist[sC]; t1, t2 = np.nanpercentile(dd, [33, 67])
        near, far = dl[dd <= t1].mean(), dl[dd >= t2].mean()
        st = [dl[t].mean() for t in np.array_split(np.arange(len(dl)), 3)]
        out[k] = (dl.mean(), se)
        print(f"{k:19s} k={KS[q]:3d} coef_voisins={m1.coef_[0][1]:+.2f} | {1e4*dl.mean():+6.1f}±{1e4*se:4.1f} | {1e4*near:+6.1f} | {1e4*far:+6.1f} | " + " ".join(f"{1e4*s:+.0f}" for s in st))
    res[mode] = out
