import sys, json
sys.path.insert(0, '/home/claude/etude_n')
from cover import couvrir, union
from search import charger, mesure, decrire, FEAT_P, FEAT_X, SPLIT_V, SPLIT_T
m='X1 + moins de 4,5'; s=0.70
t = charger(); feats = FEAT_P + FEAT_X; g = t['grand']
L, V, T = g[g.date < SPLIT_V], g[(g.date >= SPLIT_V) & (g.date < SPLIT_T)], g[g.date >= SPLIT_T]
out={}
for nom,strict in (('A',False),('B',True)):
    regles = couvrir(L, V, feats, m, s, nbs=(10,), strict=strict)
    print(nom, len(regles), 'intervalles')
    row={'regles':[[list(x) for x in z] for z in regles]}
    for jn, d in (('rech_2000_2016', g[g.date < SPLIT_T]), ('test_2017_2020', T), ('bloc_2025_26', t['bloc']), ('flux', t['flux'])):
        mk = union(d, regles); r = mesure(d, mk, m); r['part']=float(mk.mean()); row[jn]=r
        print('  ', jn, r['n'], '%.1f%%' % (100*r['taux']) if r['n'] else '-', '(%.1f%% des matchs)' % (100*r['part']))
    for z in regles: print('   ', decrire(z) if callable(decrire) else z)
    out[nom]=row
json.dump(out, open('x1_moins45_70.json','w'), ensure_ascii=False, indent=1, default=float)
