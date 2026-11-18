"""E3 : seuils et intervalles par marché (choisis sur B, confirmés sur C), récurrence hebdomadaire, championnats, corrélations."""
import csv, pickle, math, json
import numpy as np
from commun import *
choix, sortie, wf, jour, comp, YY, dA, dB = pickle.load(open("/tmp/e2.pkl", "rb"))
from datetime import date, timedelta
sem = np.array([(date.fromisoformat(j) - timedelta(days=date.fromisoformat(j).weekday())).isoformat() for j in jour])
iB = (jour >= dA) & (jour < dB); iC = jour >= dB
GRILLE = np.round(np.arange(0.50, 0.981, 0.02), 2)
BINS = [(.5, .6), (.6, .7), (.7, .75), (.75, .8), (.8, .85), (.85, .9), (.9, .95), (.95, 1.01)]
print("=== Brier / log-loss sur C (période de test) : base | moyenne simple | Megapower brut | Megapower calibré | méthode du marché")
for mk, o in sortie.items():
    print(f"{mk:20s} n={o['n_C']:4d} taux={o['taux_C']:.3f} | " + " | ".join(f"{o[k][0]:.4f}/{o[k][1]:.3f}" for k in ("base", "moyenne_simple", "megapower_brut", "megapower_calibre", "methode_marche")) +
          f" | Δ méthode-vs-calibré {o['delta_brier_methode_vs_calibre'][0]*1e4:+.1f}±{o['delta_brier_methode_vs_calibre'][1]*1e4:.1f}e-4 vars={o['cols'][1:]}")
res, csvrows = {}, []
print("\n=== Points de fonctionnement par marché (choisis sur B : borne basse de Wilson maximale, n_B>=30) et confirmation sur C")
for mk in CLES:
    k = IDX[mk]; q = wf[mk]; y = YY[:, k]
    best = None
    for t in GRILLE:
        m = iB & (q >= t); n = int(m.sum())
        if n < 30:
            continue
        h = int(y[m].sum()); lo = wilson(h, n)[0]
        if best is None or lo > best[0]:
            best = (lo, t, n, h / n)
    for (a, b) in BINS:
        for nom, I in (("B", iB), ("C", iC)):
            m = I & (q >= a) & (q < b) & ~np.isnan(q)
            if m.sum():
                lo, hi = wilson(int(y[m].sum()), int(m.sum()))
                csvrows.append([mk, nom, a, min(b, 1.0), int(m.sum()), int(y[m].sum()), round(float(y[m].mean()), 4), round(lo, 4), round(hi, 4)])
    if best is None:
        print(f"{mk:20s} aucun seuil avec 30 picks sur B"); res[mk] = None; continue
    lo, t, nB, rB = best
    mC = iC & (q >= t); nC = int(mC.sum()); hC = int(y[mC].sum()) if nC else 0
    loC, hiC = wilson(hC, nC)
    # récurrence : taux par semaine sur B∪C au seuil t (semaines avec >=10 picks)
    sw = []
    for s in sorted(set(sem[iB | iC])):
        m = (iB | iC) & (q >= t) & (sem == s)
        if m.sum() >= 10:
            sw.append((s, int(m.sum()), round(float(y[m].mean()), 3)))
    tx = [x[2] for x in sw]
    # championnats : au seuil t sur B∪C
    ligues = {}
    m = (iB | iC) & (q >= t) & ~np.isnan(q)
    for c in set(comp[m]):
        mm = m & (comp == c)
        if mm.sum() >= 30:
            ligues[c] = (int(mm.sum()), float(y[mm].mean()))
    pool = float(y[m].mean()) if m.sum() else float("nan")
    faibles = [c for c, (n_, r_) in ligues.items() if wilson(int(round(r_ * n_)), n_)[1] < pool]
    res[mk] = {"seuil": float(t), "B": (nB, rB, lo), "C": (nC, (hC / nC if nC else None), loC, hiC), "semaines": sw, "ligues_n30": len(ligues), "ligues_faibles": faibles, "taux_pool": pool,
               "ligues": ligues}
    print(f"{mk:20s} t*={t:.2f} | B n={nB:4d} taux={rB:.3f} LB={lo:.3f} | C n={nC:4d} taux={(hC/nC if nC else float('nan')):.3f} IC=[{loC:.3f};{hiC:.3f}] | semaines {len(sw)} min={min(tx) if tx else float('nan'):.3f} max={max(tx) if tx else float('nan'):.3f} | ligues≥30: {len(ligues)} faibles: {len(faibles)}")
with open("/tmp/e3_intervalles.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["marche", "periode", "q_min", "q_max", "pronostics", "reussis", "taux", "ic_bas", "ic_haut"]); w.writerows(csvrows)
pickle.dump(res, open("/tmp/e3_res.pkl", "wb"))
# corrélations entre marchés (résultat), pour ne pas compter plusieurs fois le même événement
Y = np.column_stack([YY[:, IDX[m]] for m in CLES]); ok = ~np.isnan(Y).any(axis=1)
C = np.corrcoef(Y[ok].T)
paires = sorted([(C[i, j], CLES[i], CLES[j]) for i in range(len(CLES)) for j in range(i + 1, len(CLES)) if abs(C[i, j]) >= 0.7], key=lambda x: -abs(x[0]))
print("\n=== Paires de marchés très corrélées (|phi| >= 0,7)")
for c, a, b in paires:
    print(f"{c:+.2f} {a} / {b}")
