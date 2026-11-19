"""E15 : effet sur les PRONOSTICS RETENUS (pas seulement la log-loss). Période T (2026-02 → 2026-10), modèles appris sur V.
Pour chaque marché : on garde les q % de matchs les mieux classés (même volume pour M0 et M2) ; on compare la réussite. IC95 par rééchantillonnage."""
import sys, warnings, numpy as np
warnings.filterwarnings("ignore")
src = open("e14_empilement.py").read().split('print("marché | taux T')[0]
exec(src)
rng = np.random.default_rng(0)
cibles = ["12", "1N", "N2", "1", "2", "total_moins_1.5", "total_moins_2.5", "total_moins_3.5", "total_moins_4.5", "total_moins_5.5", "btts_non", "dom_moins_1.5", "dom_moins_2.5",
          "ext_moins_1.5", "ext_moins_2.5", "1N&total_plus_1.5", "1N&btts_oui", "N2&btts_non", "12&total_plus_1.5", "N2&total_moins_1.5", "total_plus_0.5"]
print("marché | part gardée | n | réussite M0 | réussite M2 | écart ±IC95 (rééchantillonnage) | taux de base T")
for nm in cibles:
    if nm not in C.IDX: continue
    j = C.IDX[nm]; y = Y[:, j]
    f0 = lambda s: np.c_[lg(Pc[s, j])]; lf = lambda s: lg((LF[s, j] * 50 + 2 * Pc[s, j]) / 52); f2 = lambda s: np.c_[lg(Pc[s, j]), lg(Pdf[s, j]), lf(s)]
    m0 = LR(C=1e6, max_iter=1000).fit(f0(goodV), y[goodV]); m2 = LR(C=1e6, max_iter=1000).fit(f2(goodV), y[goodV])
    p0 = m0.predict_proba(f0(good))[:, 1]; p2 = m2.predict_proba(f2(good))[:, 1]; yt = y[good]; N = len(yt)
    for q in (0.1, 0.25):
        k = int(q * N); a = np.argsort(-p0, kind="stable")[:k]; b = np.argsort(-p2, kind="stable")[:k]
        ha, hb = yt[a], yt[b]
        d = [rng.choice(hb, k).mean() - rng.choice(ha, k).mean() for _ in range(400)]
        print(f"{nm:19s} {q:.0%} {k:5d} | {ha.mean():.3f} | {hb.mean():.3f} | {100*(hb.mean()-ha.mean()):+5.1f} pts [{100*np.percentile(d,2.5):+.1f} ; {100*np.percentile(d,97.5):+.1f}] | {yt.mean():.3f}")
