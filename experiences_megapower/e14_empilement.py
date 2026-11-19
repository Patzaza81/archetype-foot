"""E14 : le modèle d'équipes « tous résultats » (E13) apporte-t-il de l'information en plus du modèle actuel ? Empilement par marché : M0 = modèle actuel recalibré ;
M1 = M0 + modèle d'équipes ; M2 = M1 + fréquence récente du marché dans le championnat. Appris sur V (2025-09 → 2026-01), jugé sur T (2026-02 → 2026-10), jamais utilisé."""
import warnings, numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression as LR
import commun as C
from commun import *
Z = np.load("sorties/e13_dc_lambdas.npz", allow_pickle=True); T = np.load("sorties/table2_bloc_tous.npz", allow_pickle=True)
la, lb, cur, jr = Z["la"], Z["lb"], Z["cur"], Z["jr"]; Y, Pc, comp, jour = T["Y"], T["P"], T["comp"], T["jour"]
D = lambda s: int(np.datetime64(s, "D").astype(int)); d0, dV = D("2025-09-01"), D("2026-02-01")
ok = ~np.isnan(la) & (jr >= d0); sV = ok & (jr < dV); sT = ok & (jr >= dV)
Pd = C.probas(la[ok & True].astype(float).clip(0.05), lb[ok & True].astype(float).clip(0.05)); Pdf = np.full(Y.shape, np.nan); Pdf[ok] = Pd
Pm = np.full(Y.shape, np.nan); Pm[ok] = C.probas(((la + cur[:, 0]) / 2)[ok].clip(0.05), ((lb + cur[:, 1]) / 2)[ok].clip(0.05))
# fréquence récente du marché dans le championnat (300 jours, tous les matchs connus)
mb, sb, _ = C.charger_bloc(); par = {}
for m in mb:
    if m["id"] in sb: par.setdefault(m["competition"], []).append((D(m["jour"]), C.TAB[min(sb[m["id"]][0], 10), min(sb[m["id"]][1], 10)]))
LF = np.full(Y.shape, np.nan, np.float32)
for i in np.where(ok)[0]:
    L = [y for d, y in par.get(comp[i], []) if jr[i] - 300 <= d < jr[i]]
    if len(L) >= 20: LF[i] = np.mean(L, axis=0)
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def ll(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
seen, names = {}, []
for j, nm in enumerate(C.NOMS):
    y = Y[:, j]; r = y[sT].mean()
    if r < 0.08 or r > 0.95: continue
    h1, h2 = hash(y.tobytes()), hash((1 - y).tobytes())
    if h1 in seen or h2 in seen: continue
    seen[h1] = nm; names.append(nm)
good = sT & ~np.isnan(LF[:, 0]); goodV = sV & ~np.isnan(LF[:, 0])
print(f"V={int(goodV.sum())} T={int(good.sum())} ; marchés distincts {len(names)}")
print("marché | taux T | Δ M1−M0 (±se) | Δ mélange des λ | Δ M2−M0 (±se) | blocs T de M2 | coefficients M1 (actuel, équipes)")
tot = {"m1": [], "m2": []}
for nm in names:
    j = C.IDX[nm]; y = Y[:, j]
    f0 = lambda s: np.c_[lg(Pc[s, j])]; f1 = lambda s: np.c_[lg(Pc[s, j]), lg(Pdf[s, j])]
    lf = lambda s: lg((LF[s, j] * 50 + 2 * Pc[s, j]) / 52); f2 = lambda s: np.c_[lg(Pc[s, j]), lg(Pdf[s, j]), lf(s)]
    m0 = LR(C=1e6, max_iter=1000).fit(f0(goodV), y[goodV]); m1 = LR(C=1e6, max_iter=1000).fit(f1(goodV), y[goodV]); m2 = LR(C=1e6, max_iter=1000).fit(f2(goodV), y[goodV])
    p0 = m0.predict_proba(f0(good))[:, 1]; p1 = m1.predict_proba(f1(good))[:, 1]; p2 = m2.predict_proba(f2(good))[:, 1]; yt = y[good]
    d1 = ll(p0, yt) - ll(p1, yt); d2 = ll(p0, yt) - ll(p2, yt); dm = ll(p0, yt) - ll(np.clip(Pm[good, j], 1e-6, 1 - 1e-6), yt)
    se = lambda d: d.std(ddof=1) / np.sqrt(len(d)); st = [d2[t].mean() for t in np.array_split(np.arange(len(d2)), 3)]
    tot["m1"].append(d1.mean()); tot["m2"].append(d2.mean())
    print(f"{nm:19s} {yt.mean():.3f} | {1e4*d1.mean():+6.1f}±{1e4*se(d1):4.1f} | {1e4*dm.mean():+6.1f} | {1e4*d2.mean():+6.1f}±{1e4*se(d2):4.1f} | " + " ".join(f"{1e4*s:+.0f}" for s in st) + f" | {m1.coef_[0][0]:+.2f} {m1.coef_[0][1]:+.2f}")
print("moyenne sur les marchés : M1", f"{1e4*np.mean(tot['m1']):+.1f}", "M2", f"{1e4*np.mean(tot['m2']):+.1f}", "(1e-4 de log-loss ; >0 = gain)")
