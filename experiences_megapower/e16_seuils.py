"""E16 : sélection par seuil de fiabilité (comme Mega Power) : on retient les pronostics dont la probabilité calibrée ≥ τ. M0 = modèle actuel recalibré sur V ; M2 = empilement (actuel + équipes tous résultats + championnat).
Période T. On compare le nombre de pronostics, la réussite réelle, la réussite annoncée (écart = calibration) et la borne basse de Wilson."""
import warnings, numpy as np
warnings.filterwarnings("ignore")
exec(open("e14_empilement.py").read().split('print("marché | taux T')[0])
cibles = ["12", "1N", "N2", "total_moins_3.5", "total_moins_4.5", "total_moins_5.5", "dom_moins_2.5", "ext_moins_2.5", "ext_moins_1.5", "dom_moins_1.5", "total_plus_0.5", "1N&total_moins_4.5", "12&total_moins_4.5"]
print("marché | seuil | M0 : n, réussite, annoncée | M2 : n, réussite, annoncée | borne basse M0 → M2")
S = {0.70: [], 0.75: [], 0.80: [], 0.85: []}
for nm in cibles:
    if nm not in C.IDX: continue
    j = C.IDX[nm]; y = Y[:, j]
    f0 = lambda s: np.c_[lg(Pc[s, j])]; lf = lambda s: lg((LF[s, j] * 50 + 2 * Pc[s, j]) / 52); f2 = lambda s: np.c_[lg(Pc[s, j]), lg(Pdf[s, j]), lf(s)]
    p0 = LR(C=1e6, max_iter=1000).fit(f0(goodV), y[goodV]).predict_proba(f0(good))[:, 1]; p2 = LR(C=1e6, max_iter=1000).fit(f2(goodV), y[goodV]).predict_proba(f2(good))[:, 1]; yt = y[good]
    for tau in (0.70, 0.75, 0.80, 0.85):
        a, b = p0 >= tau, p2 >= tau
        if a.sum() < 30 and b.sum() < 30: continue
        r = lambda m, p: (int(m.sum()), yt[m].mean() if m.sum() else np.nan, p[m].mean() if m.sum() else np.nan)
        ra, rb = r(a, p0), r(b, p2); wa, wb = wilson(yt[a].sum(), a.sum())[0] if a.sum() else np.nan, wilson(yt[b].sum(), b.sum())[0] if b.sum() else np.nan
        print(f"{nm:19s} {tau:.2f} | {ra[0]:5d} {ra[1]:.3f} {ra[2]:.3f} | {rb[0]:5d} {rb[1]:.3f} {rb[2]:.3f} | {wa:.3f} → {wb:.3f}")
        S[tau].append((ra[0], ra[1] * ra[0], ra[2] * ra[0], rb[0], rb[1] * rb[0], rb[2] * rb[0]))
print("\nTOTAL sur ces marchés (somme des pronostics) : seuil | M0 n, réussite, annoncée | M2 n, réussite, annoncée")
for tau, L in S.items():
    L = np.array(L); 
    if len(L): print(f"{tau:.2f} | {int(L[:,0].sum())} {L[:,1].sum()/L[:,0].sum():.3f} {L[:,2].sum()/L[:,0].sum():.3f} | {int(L[:,3].sum())} {L[:,4].sum()/L[:,3].sum():.3f} {L[:,5].sum()/L[:,3].sum():.3f}")
