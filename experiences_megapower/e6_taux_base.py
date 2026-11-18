"""E6 : la réussite de Megapower v2 (marche avant) comparée à celle des MÊMES marchés joués sans aucune analyse (taux de base)."""
import sys, numpy as np
sys.path.insert(0, "/home/claude/archetype-foot")
from megapower import donnees as D, modele as M, calibration as C, suivi as SV
import verif_pronostic as V
matchs, sc = D.lire_flux(), D.scores()
R = M.ajuster(matchs, sc); F = SV.prevoir(matchs, R["parametres"]); joue, Y = SV._resultats(F, sc)
jours = np.array([m["jour"] for m in F["matchs"]]); dj = sorted(set(jours[joue])); test = dj[len(dj) // 2:]
K = F["pn"].shape[1]; seuil = SV.fiabilite_demandee()
base_test = np.nanmean(Y[joue & np.isin(jours, test)], axis=0)             # taux de base de chaque marché sur la période de test
n = h = 0; hn = 0.0; par = {}
for d in test:
    cal = C.apprendre(*SV._lignes(F, joue, Y, joue & (jours < d)))
    for t in np.nonzero(joue & (jours == d))[0]:
        q, bas = C.predire(cal, F["pn"][t], F["pc"][t], np.arange(K))
        for k in SV.retenus(bas, q, seuil):
            n += 1; h += Y[t, k]; hn += base_test[k]
            a = par.setdefault(V.NOMS[k], [0, 0, base_test[k]]); a[0] += 1; a[1] += Y[t, k]
print(f"pronostics {n}, réussite {h/n:.4f}, réussite des mêmes marchés joués sans analyse {hn/n:.4f}, apport {100*(h-hn)/n:+.2f} points")
for k, (a, b, bt) in sorted(par.items(), key=lambda x: -x[1][0])[:14]:
    print(f"{k:22s} n={a:5d} réussite={b/a:.3f} taux de base={bt:.3f} apport={100*(b/a-bt):+.1f}")
