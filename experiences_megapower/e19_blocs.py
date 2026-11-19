"""E19 : contribution marginale de chaque famille de paramètres, marché par marché (log-loss, matchs futurs). Blocs ajoutés dans l'ordre :
B0 modèle actuel | B1 + modèle d'équipes tous résultats | B2 + classement réel (points, écart de points, points par match, rang, forme) | B3 + goal-average (global et par lieu)
| B4 + attaque/défense réciproques au même lieu (corrigées de l'adversaire) + croisements | B5 + nature du championnat (buts, avantage du terrain, nuls, BTTS, +2,5, équilibre, niveau, continent).
A = 01/09/2025→31/01/2026 (apprentissage), B = 01/02→12/04/2026 (réglage de la régularisation), C = 13/04→16/10/2026 (test jamais utilisé). Aucune cote."""
import warnings, numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression as LR
import commun as C
from commun import *
T = np.load("sorties/table3_bloc.npz", allow_pickle=True); Z = np.load("sorties/e13_dc_lambdas.npz", allow_pickle=True)
ids3 = list(T["ids"]); ids = list(Z["id"]); p = {i: k for k, i in enumerate(ids)}; sel = np.array([p[i] for i in ids3])
la, lb, jr = Z["la"][sel], Z["lb"][sel], Z["jr"][sel]
X3, n3, X2, n2, Pc, Y = T["X3"], list(T["names3"]), T["X2"], list(T["names2"]), T["P"], T["Y"]
D = lambda s: int(np.datetime64(s, "D").astype(int)); d0, dB, dC = D("2025-09-01"), D("2026-02-01"), D("2026-04-13")
ok = ~np.isnan(la) & (jr >= d0) & ~np.isnan(X3).any(1); idx = np.where(ok)[0]
Pd = np.full(Pc.shape, np.nan); Pd[ok] = C.probas(la[ok].clip(0.05), lb[ok].clip(0.05))
sA, sB, sC = ok & (jr < dB), ok & (jr >= dB) & (jr < dC), ok & (jr >= dC)
print(f"lignes {int(ok.sum())} : A={int(sA.sum())} B={int(sB.sum())} C={int(sC.sum())}")
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def ll(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
g3 = lambda ns: np.c_[[X3[:, n3.index(k)] for k in ns]].T
g2 = lambda ns: np.c_[[X2[:, n2.index(k)] for k in ns]].T
B2 = ["ppg_gap", "pts_gap", "ppg_A", "ppg_B", "rank_gap_n", "rank_A", "rank_B", "stage", "form5_A", "form5_B", "form5_gap", "vppg_A", "vppg_B", "vppg_gap"]
B3 = ["ga_ratio_A", "ga_ratio_B", "ga_ratio_gap", "gdpg_A", "gdpg_B", "gdpg_gap", "vga_ratio_A", "vga_ratio_B", "vga_ratio_gap", "vgdpg_A", "vgdpg_B", "vgdpg_gap"]
B4a = ["idx_attA", "idx_defA", "idx_attB", "idx_defB", "recip_1", "recip_2", "recip_diff", "recip_lratio", "recip_sum"]; B4b = ["hgf", "hga", "bgf_a", "bga_a", "x1", "x2", "d12", "ld12", "r_att", "r_def", "gap_ga", "x3", "x4", "d34", "sd34"]
B5 = ["lg_goals", "lg_hgoals", "lg_agoals", "lg_homewin", "lg_draw", "lg_btts", "lg_o25", "lg_o15", "lg_balance", "lg_tier", "lg_cont"]
blocs = {"B2": g3(B2), "B3": g3(B3), "B4": np.c_[g3(B4a), g2(B4b)], "B5": g3(B5)}
def std(M): 
    lo, hi = np.percentile(M[sA], 1, axis=0), np.percentile(M[sA], 99, axis=0); M = np.clip(M, lo, hi); return (M - M[sA].mean(0)) / (M[sA].std(0) + 1e-9)
S = {k: std(v) for k, v in blocs.items()}
MARCHES = ["1", "N", "2", "1N", "N2", "12", "total_plus_1.5", "total_plus_2.5", "total_moins_3.5", "total_moins_4.5", "btts_oui", "dom_plus_0.5", "ext_plus_0.5", "dom_moins_1.5", "dom_moins_2.5", "ext_moins_1.5", "ext_moins_2.5", "cage_dom_non", "cage_ext_non",
           "1N&total_plus_1.5", "N2&total_plus_1.5", "1N&total_moins_3.5", "N2&total_moins_3.5", "12&total_plus_1.5", "12&total_moins_4.5", "1N&btts_oui", "N2&btts_non"]
MARCHES = [m for m in MARCHES if m in C.IDX]
def ajuste(F, y):
    best = None
    for c in (0.0003, 0.001, 0.003, 0.01, 0.03, 0.1):
        m = LR(C=c, max_iter=3000).fit(F[sA], y[sA]); l = ll(m.predict_proba(F[sB])[:, 1], y[sB]).mean()
        if best is None or l < best[0]: best = (l, c)
    m = LR(C=best[1], max_iter=3000).fit(F[sA | sB], y[sA | sB]); return m.predict_proba(F[sC])[:, 1]
print("marché | taux C | gain cumulé (1e-4 de log-loss, >0 = mieux) : +équipes | +classement | +goal-average | +réciproques | +nature | total ±se")
tot = {k: [] for k in ("B1", "B2", "B3", "B4", "B5")}; sig = {k: 0 for k in tot}
for nm in MARCHES:
    j = C.IDX[nm]; y = Y[:, j]; lp = lg(Pc[:, j]); lpd = np.nan_to_num(lg(Pd[:, j]))
    F = [np.c_[lp]]; F.append(np.c_[lp, lpd])
    for k in ("B2", "B3", "B4", "B5"): F.append(np.c_[F[-1], S[k]])
    # M0 : recalibrage simple sur A+B ; ensuite chaque bloc ajouté
    m0 = LR(C=1e6, max_iter=1000).fit(F[0][sA | sB], y[sA | sB]); p = [m0.predict_proba(F[0][sC])[:, 1]]
    for f in F[1:]: p.append(ajuste(f, y))
    yc = y[sC]; L = [ll(q, yc) for q in p]; inc = [L[i - 1] - L[i] for i in range(1, 6)]; se = lambda d: d.std(ddof=1) / np.sqrt(len(d))
    for k, d in zip(tot, inc): tot[k].append(d.mean()); sig[k] += d.mean() / se(d) >= 2
    cum = [(L[0] - L[i]).mean() for i in range(1, 6)]; tt = L[0] - L[5]
    print(f"{nm:19s} {yc.mean():.3f} | " + " ".join(f"{1e4*c:+6.1f}" for c in cum) + f" | {1e4*tt.mean():+6.1f}±{1e4*se(tt):4.1f}")
print("\nbloc | gain moyen apporté PAR le bloc (1e-4) | nombre de marchés où le bloc apporte ≥ 2 erreurs-types | sur", len(MARCHES), "marchés")
for k, v in tot.items(): print(f"{k} {1e4*np.mean(v):+6.1f} | {sig[k]}")
