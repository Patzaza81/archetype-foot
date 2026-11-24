"""Fige les intervalles retenus (24/11/2026) : un seuil et une version (A/B) par marché. Écrit categories_zones.json."""
import sys, json, math
sys.path.insert(0, '/home/claude/etude_n')
import numpy as np
from cover import couvrir, union
from search import charger, mesure, FEAT_P, FEAT_X, SPLIT_V, SPLIT_T
import build
# marché de l'étude, seuil (Patrick), version, marché du catalogue de la page, nbs
CHOIX = [('Victoire domicile', 0.70, 'B', '1', (10, 20)), ('Victoire extérieur', 0.60, 'A', '2', (10, 20)), ('Plus de 1,5', 0.80, 'B', 'total_plus_1.5', (10,)),
         ('X1', 0.90, 'A', '1N', (10,)), ('X2', 0.75, 'B', 'N2', (10,)), ('Domicile marque 1+', 0.90, 'B', 'dom_plus_0.5', (10,)),
         ('Extérieur marque 1+', 0.80, 'B', 'ext_plus_0.5', (10,)), ('X1 + plus de 1,5', 0.70, 'B', '1N&total_plus_1.5', (10,)),
         ('X2 + plus de 1,5', 0.60, 'B', 'N2&total_plus_1.5', (10,)), ('X1 + moins de 4,5', 0.74, 'A', '1N&total_moins_4.5', (10,)),
         ('X2 + moins de 4,5', 0.65, 'B', 'N2&total_moins_4.5', (10,))]
t = charger(); feats = FEAT_P + FEAT_X; g = t['grand']
L, V, T = g[g.date < SPLIT_V], g[(g.date >= SPLIT_V) & (g.date < SPLIT_T)], g[g.date >= SPLIT_T]
fin = lambda x: None if not math.isfinite(x) else float(x)
out = {}
for m, s, ver, cat, nbs in CHOIX:
    regles = couvrir(L, V, feats, m, s, nbs=nbs, strict=(ver == 'B'))
    row = dict(marche=cat, seuil=s, version=ver, intervalles=[])
    for z in regles:
        r = dict(conditions=[[f, fin(lo), fin(hi)] for f, lo, hi in z], stats={})
        for nom, d in (('recherche_2000_2016', g[g.date < SPLIT_T]), ('test_2017_2020', T), ('bloc_2025_26', t['bloc'])):
            mk = union(d, [z]); r['stats'][nom] = {k: (int(v) if k in ('n', 's') else None) for k, v in mesure(d, mk, m).items() if k in ('n', 's')}
        row['intervalles'].append(r)
    row['stats'] = {}
    for nom, d in (('recherche_2000_2016', g[g.date < SPLIT_T]), ('test_2017_2020', T), ('bloc_2025_26', t['bloc'])):
        mk = union(d, regles); r = mesure(d, mk, m); row['stats'][nom] = dict(matchs=r['n'], reussis=r['s'], part_des_matchs=round(float(mk.mean()), 4))
    out[m] = row
    print('%-22s %.2f %s %d interv. | 2017-20 %s | bloc %s' % (m, s, ver, len(regles), row['stats']['test_2017_2020'], row['stats']['bloc_2025_26']), flush=True)
cal = {k: float(v) for k, v in build.CAL.items()}
json.dump(dict(version=1, gele_le='2026-11-24', calibration_xg=cal, marches=out), open('categories_zones.json', 'w'), ensure_ascii=False, indent=1)
print(cal)
