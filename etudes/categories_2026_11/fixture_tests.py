import sys, json, math
sys.path.insert(0, '/home/claude/etude_n')
import numpy as np, pandas as pd
from search import charger, masque
t = charger(); g = t['grand']; g = g[g.EH.notna() & g.hM.notna()]
Z = json.load(open('categories_zones.json'))['marches']
conv = lambda z: [(f, -np.inf if lo is None else lo, np.inf if hi is None else hi) for f, lo, hi in z]
IN = ['hM', 'hC', 'aM', 'aC', 'sMh', 'sCh', 'sMa', 'sCa', 'mu']
SORTIE = ['EH', 'EA', 'ET', 'dE', 'rE', 'EHm', 'EAm', 'X1g', 'SM', 'rM', 'A1', 'dC']
rng = np.random.RandomState(24)
mem = {m: np.zeros(len(g), bool) for m in Z}
for m, M in Z.items():
    for z in M['intervalles']: mem[m] |= masque(g, conv([c for c in z['conditions']]))
choix = set()
for m in Z:
    p = np.where(mem[m])[0]; f = np.where(~mem[m])[0]
    choix |= set(rng.choice(p, min(4, len(p)), replace=False)); choix |= set(rng.choice(f, 4, replace=False))
# lignes proches d'un bord (juste dedans / juste dehors) pour chaque intervalle à 1 condition de seuil
choix = sorted(choix); out = []
for i in choix:
    r = g.iloc[i]
    out.append(dict(entrees={k: float(r[k]) for k in IN}, attendu={k: float(r[k]) for k in SORTIE if math.isfinite(r[k])}, marches=[Z[m]['marche'] for m in Z if mem[m][i]]))
json.dump(dict(calibration=json.load(open('categories_zones.json'))['calibration_xg'], lignes=out), open('categories_exemples.json', 'w'), indent=0)
print(len(out), sum(1 for o in out if o['marches']), 'lignes avec au moins un marché')
from collections import Counter
print(Counter(x for o in out for x in o['marches']))
