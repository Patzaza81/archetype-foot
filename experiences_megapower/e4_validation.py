"""E4 : lift sur le taux de base (un marché n'est « validé » que s'il fait mieux que jouer ce marché au hasard), championnats, intervalles types."""
import pickle, csv, math
import numpy as np
from commun import *
choix, sortie, wf, jour, comp, YY, dA, dB = pickle.load(open("/tmp/e2.pkl", "rb"))
res = pickle.load(open("/tmp/e3_res.pkl", "rb"))
jou = ~np.isnan(YY[:, 0]); iB = (jour >= dA) & (jour < dB) & jou; iC = (jour >= dB) & jou
print("marché | seuil B | taux de base C | C : n, réussis, taux, IC95 | lift | verdict")
valides = []
for mk in CLES:
    r = res.get(mk)
    if not r:
        print(f"{mk:20s} | aucun seuil exploitable"); continue
    k = IDX[mk]; y = YY[:, k]; q = wf[mk]; t = r["seuil"]
    mC = iC & (q >= t); n = int(mC.sum())
    if n == 0:
        continue
    h = int(y[mC].sum()); base = float(y[iC].mean())
    lo, hi = wilson(h, n)
    # taux de base sur les mêmes matchs que ceux retenus par le moteur sert de repère : le marché joué au hasard sur toute la période C
    z = (h / n - base) / math.sqrt(base * (1 - base) / n)
    ok = lo > base and (h / n) >= r["B"][2]
    if ok: valides.append(mk)
    print(f"{mk:20s} | t={t:.2f} | base={base:.3f} | n={n:3d} h={h:3d} taux={h/n:.3f} IC=[{lo:.3f};{hi:.3f}] | lift={(h/n-base)*100:+.1f} pts z={z:+.1f} | {'VALIDÉ' if ok else 'non validé'}")
print("validés:", valides)
# intervalles types
rows = list(csv.DictReader(open("/tmp/e3_intervalles.csv")))
for mk in ("1N", "12", "total_plus_1.5", "dom_plus_0.5", "total_moins_3.5", "multibuts_1-4", "1"):
    print("\n--", mk)
    for r in rows:
        if r["marche"] == mk:
            print(f"  {r['periode']} [{float(r['q_min']):.2f};{float(r['q_max']):.2f}) n={r['pronostics']:>4} rate={r['taux']} IC=[{r['ic_bas']};{r['ic_haut']}]")
# championnats : pronostics des marchés validés à leur seuil, B∪C, par championnat
print("\n== Championnats (marchés validés, au seuil retenu, B∪C) : championnat | matchs | pronostics | réussite | réussite annoncée")
agg = {}
for mk in valides:
    k = IDX[mk]; q = wf[mk]; t = res[mk]["seuil"]; y = YY[:, k]
    m = (iB | iC) & (q >= t)
    for c in set(comp[m]):
        mm = m & (comp == c)
        a = agg.setdefault(c, [0, 0, 0.0]); a[0] += int(mm.sum()); a[1] += int(y[mm].sum()); a[2] += float(q[mm].sum())
tot = [sum(a[0] for a in agg.values()), sum(a[1] for a in agg.values())]
print("total", tot)
for c, (n, h, s) in sorted(agg.items(), key=lambda x: -x[1][0])[:14]:
    lo, hi = wilson(h, n)
    print(f"{c[:42]:42s} n={n:4d} réussite={h/n:.3f} IC=[{lo:.3f};{hi:.3f}] annoncé={s/n:.3f}")
pickle.dump(valides, open("/tmp/e4_valides.pkl", "wb"))
