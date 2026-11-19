"""E20 : intervalles de cote (cote de clôture moyenne du bloc, utilisée seulement APRÈS coup pour décrire, jamais dans un modèle) et nature des championnats.
Cotes dérivées : 1N = 1/(1/c1+1/cN), N2, 12 de même. Éligible = cote >= 1,26. Bandes par quantiles. Réussite réelle, IC Wilson 95 %, sur tous les matchs puis sur C (>= 13/04/2026)."""
import numpy as np, collections
import commun as C
from commun import *
T = np.load("sorties/table3_bloc.npz", allow_pickle=True); O, Y, Pc, comp, jr = T["odds"], T["Y"], T["P"], T["comp"], T["jour"]
D = lambda s: int(np.datetime64(s, "D").astype(int)); isC = np.array([D(str(j)) >= D("2026-04-13") for j in jr])
c1, cn, c2 = O[:, 0], O[:, 1], O[:, 2]; inv = lambda *a: 1 / sum(1 / x for x in a)
COTE = {"1": c1, "N": cn, "2": c2, "1N": inv(c1, cn), "N2": inv(cn, c2), "12": inv(c1, c2)}
def wil(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return ((c - r) / d, (c + r) / d)
print("== A. Réussite par intervalle de cote (cote >= 1,26), tous matchs 2 saisons | dont C ==")
for nm in ("1", "2", "1N", "N2", "12"):
    j = C.IDX[nm]; y = Y[:, j]; c = COTE[nm]; ok = ~np.isnan(c) & (c >= 1.26)
    qs = np.unique(np.quantile(c[ok], [0, .2, .4, .6, .8, 1])); print(f"\n{nm} : {int(ok.sum())} matchs éligibles, réussite globale {y[ok].mean():.3f}")
    for lo, hi in zip(qs[:-1], qs[1:]):
        m = ok & (c >= lo) & (c <= hi if hi == qs[-1] else c < hi); mc = m & isC; k, n = int(y[m].sum()), int(m.sum()); a, b = wil(k, n)
        print(f"  cote {lo:.2f}-{hi:.2f}: n={n:5d} réussite {k/n:.3f} [{a:.3f};{b:.3f}] | C: n={int(mc.sum()):4d} {y[mc].mean():.3f}")
print("\n== B. Réussite par pronostic du modèle actuel (P >= seuil) ET intervalle de cote : 12, 1N, N2 sur C ==")
for nm in ("1N", "N2", "12", "1", "2"):
    j = C.IDX[nm]; y = Y[:, j]; c = COTE[nm]; p = Pc[:, j]; ok = ~np.isnan(c) & (c >= 1.26) & isC
    for lo, hi in ((1.26, 1.35), (1.35, 1.5), (1.5, 1.8), (1.8, 2.5), (2.5, 99)):
        m = ok & (c >= lo) & (c < hi)
        if m.sum() < 60: continue
        t = np.median(p[m]); top = m & (p >= t); a, b = wil(int(y[top].sum()), int(top.sum()))
        print(f"  {nm:2s} cote {lo}-{hi}: n={int(m.sum()):4d} réussite {y[m].mean():.3f} | moitié haute du modèle n={int(top.sum()):4d} {y[top].mean():.3f} [{a:.3f};{b:.3f}]")
print("\n== C. Nature du championnat : réussite 12 / 1N / N2 / +1,5 / BTTS par division (2 saisons, tous matchs, n >= 300) ==")
cnt = collections.Counter(comp); rows = []
for d, n in cnt.items():
    if n < 300: continue
    m = comp == d; rows.append((d, n, *[Y[m, C.IDX[k]].mean() for k in ("12", "1N", "N2", "total_plus_1.5", "btts_oui", "total_plus_2.5")]))
rows.sort(key=lambda r: -r[2 + 3]); print("div    n    12    1N    N2   +1.5  BTTS  +2.5")
for r in rows: print(f"{r[0]:5s} {r[1]:4d} " + " ".join(f"{x:.3f}" for x in r[2:]))
# hétérogénéité : écart entre divisions plus grand que le hasard ?
print("\nTest d'hétérogénéité (khi-deux, divisions n>=300) :")
from scipy.stats import chi2_contingency
for k in ("12", "1N", "N2", "total_plus_1.5", "btts_oui", "total_plus_2.5"):
    tab = np.array([[Y[comp == d, C.IDX[k]].sum(), (comp == d).sum() - Y[comp == d, C.IDX[k]].sum()] for d, n in cnt.items() if n >= 300]); chi, p, *_ = chi2_contingency(tab); print(f"  {k:15s} khi2={chi:6.1f} p={p:.2g} ; min {tab[:,0].sum() and (tab[:,0]/tab.sum(1)).min():.3f} max {(tab[:,0]/tab.sum(1)).max():.3f}")
