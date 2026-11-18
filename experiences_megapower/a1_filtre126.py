"""A1 : que devient la réussite de Megapower v2 (marche avant) une fois le filtre opérationnel « cote >= 1,26 » appliqué ?
Les cotes ne servent qu'à ce filtre, lu APRÈS le choix du pronostic : elles n'entrent dans aucun calcul prédictif ni apprentissage."""
import sys, glob, gzip, json, collections, numpy as np
sys.path.insert(0, "/home/claude/archetype-foot")
from megapower import donnees as D, modele as M, calibration as C, suivi as SV
import verif_pronostic as V
ROOT = D.ROOT
matchs, sc = D.lire_flux(), D.scores()
ids = {m["id"] for m in matchs}; cot = {}
for f in sorted(glob.glob(str(D.FLUX / "*.json.gz"))):
    for k, x in json.load(gzip.open(f)).items():
        if k in ids: cot[k] = V.cotes_betpawa(x.get("cotes_betpawa") or {})
R = M.ajuster(matchs, sc); F = SV.prevoir(matchs, R["parametres"]); joue, Y = SV._resultats(F, sc)
jours = np.array([m["jour"] for m in F["matchs"]]); dj = sorted(set(jours[joue])); test = dj[len(dj) // 2:]
K = F["pn"].shape[1]; seuil = SV.fiabilite_demandee()
tous = []   # (match, marché, réussi, cote ou None)
for d in test:
    cal = C.apprendre(*SV._lignes(F, joue, Y, joue & (jours < d)))
    for t in np.nonzero(joue & (jours == d))[0]:
        q, bas = C.predire(cal, F["pn"][t], F["pc"][t], np.arange(K))
        for k in SV.retenus(bas, q, seuil):
            tous.append((F["matchs"][t]["id"], V.NOMS[k], float(Y[t, k]), cot.get(F["matchs"][t]["id"], {}).get(V.NOMS[k])))
n = len(tous); av = [x for x in tous if x[3] is not None]; ok = [x for x in av if x[3] >= 1.26]
print(f"pronostics v2 {n} ; avec cote connue {len(av)} ({len(av)/n:.1%}) ; cote >= 1,26 : {len(ok)} ({len(ok)/n:.1%})")
print(f"réussite tous {np.mean([x[2] for x in tous]):.4f} | cote connue {np.mean([x[2] for x in av]):.4f} | cote >= 1,26 {np.mean([x[2] for x in ok]):.4f} | cote < 1,26 {np.mean([x[2] for x in av if x[3]<1.26]):.4f}")
print("matchs ayant au moins un pronostic >= 1,26 :", len({x[0] for x in ok}), "sur", len({x[0] for x in tous}), "; période", test[0], "→", test[-1])
par = collections.defaultdict(lambda: [0, 0, 0, 0])
for m, k, y, c in av:
    a = par[k]; a[0] += 1; a[1] += y
    if c >= 1.26: a[2] += 1; a[3] += y
print("marché | picks | réussite | picks>=1,26 | réussite>=1,26")
for k, a in sorted(par.items(), key=lambda x: -x[1][2]):
    print(f"{k:20s} {a[0]:5d} {a[1]/a[0]:.3f} {a[2]:5d} {(a[3]/a[2] if a[2] else float('nan')):.3f}")
