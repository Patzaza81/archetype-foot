"""Re-gèle SEULEMENT « X1 + moins de 4,5 » à 70 % (version B), décision de Patrick du 24/11/2026 ; les autres marchés restent tels quels."""
import sys, json, math
sys.path.insert(0, '/home/claude/etude_n')
from cover import couvrir, union
from search import charger, mesure, FEAT_P, FEAT_X, SPLIT_V, SPLIT_T
m, s, ver, cat = 'X1 + moins de 4,5', 0.70, 'B', '1N&total_moins_4.5'
t = charger(); feats = FEAT_P + FEAT_X; g = t['grand']
L, V, T = g[g.date < SPLIT_V], g[(g.date >= SPLIT_V) & (g.date < SPLIT_T)], g[g.date >= SPLIT_T]
fin = lambda x: None if not math.isfinite(x) else float(x)
regles = couvrir(L, V, feats, m, s, nbs=(10,), strict=True)
row = dict(marche=cat, seuil=s, version=ver, intervalles=[])
for z in regles:
    r = dict(conditions=[[f, fin(lo), fin(hi)] for f, lo, hi in z], stats={})
    for nom, d in (('recherche_2000_2016', g[g.date < SPLIT_T]), ('test_2017_2020', T), ('bloc_2025_26', t['bloc'])):
        mk = union(d, [z]); r['stats'][nom] = {k: (int(v) if k in ('n', 's') else None) for k, v in mesure(d, mk, m).items() if k in ('n', 's')}
    row['intervalles'].append(r)
row['stats'] = {}
for nom, d in (('recherche_2000_2016', g[g.date < SPLIT_T]), ('test_2017_2020', T), ('bloc_2025_26', t['bloc'])):
    mk = union(d, regles); r = mesure(d, mk, m); row['stats'][nom] = dict(matchs=r['n'], reussis=r['s'], part_des_matchs=round(float(mk.mean()), 4))
Z = json.load(open('categories_zones.json')); Z['marches'][m] = row; Z['regele'] = {cat: '2026-11-24'}
json.dump(Z, open('categories_zones.json', 'w'), ensure_ascii=False, indent=1)
print(row['stats']); print(row['intervalles'][0]['conditions'], row['intervalles'][0]['stats'])
