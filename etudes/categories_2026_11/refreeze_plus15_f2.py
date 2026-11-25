"""Re-gel du marché « Plus de 1,5 » (25/11/2026) : règle de Patrick « chaque équipe a marqué 2 buts ou plus dans au moins 40 % de ses matchs à son lieu (2 sur 5, 3 sur 6, 4 sur 8...), 5 matchs minimum au même lieu »,
croisée avec les buts encaissés de chaque équipe à son lieu (intervalles sur déciles, apprentissage 2000-2012, vérification 2013-2016, jamais vu : 2017-2020 et 2025-26), couverture visée 5 % des matchs.
Usage : (depuis le dossier de travail de l'étude, après build3_plus15.py) python3 refreeze_plus15_f2.py <chemin categories_zones.json>"""
import sys, json, itertools, math
import numpy as np, pandas as pd
D = '/home/claude/etude_n/'
VARS = ['F2h', 'F2a', 'hC', 'aC']; COUV = 0.05; NB = 10
g = pd.read_pickle(D + 't6_grand.pkl'); b = pd.read_pickle(D + 't6_bloc.pkl')
for d in (g, b):
    d['y'] = ((d.bd + d.be) >= 2).astype(int); d['F2h'] = d.h_ps2_t; d['F2a'] = d.a_ps2_t; d['hC'] = d.h_mc_t; d['aC'] = d.a_mc_t
g['an'] = g.date.str[:4].astype(int)
tot = {'app': (g.an <= 2012).sum(), 'val': ((g.an >= 2013) & (g.an <= 2016)).sum(), 'test': (g.an >= 2017).sum()}
R = lambda d: d[(d.F2h >= 0.4) & (d.F2a >= 0.4)].reset_index(drop=True)
L, V, T = R(g[g.an <= 2012]), R(g[(g.an >= 2013) & (g.an <= 2016)]), R(g[g.an >= 2017]); B = R(b)
edges = {v: np.unique(np.nanpercentile(L[v], np.linspace(0, 100, NB + 1)[1:-1])) for v in VARS}; nb = [len(edges[v]) + 1 for v in VARS]
def cube(d):
    idx = tuple(np.searchsorted(edges[v], d[v].values, side='right') for v in VARS); N = np.zeros(nb); S = np.zeros(nb)
    np.add.at(N, idx, 1); np.add.at(S, idx, d.y.values); return N, S
def prefix(A):
    P = np.zeros([n + 1 for n in nb]); P[1:, 1:, 1:, 1:] = A
    for ax in range(4): P = np.cumsum(P, axis=ax)
    return P
ivs = [[(lo, hi) for lo in range(n) for hi in range(lo + 1, n + 1)] for n in nb]; I = [(np.array([a for a, _ in iv]), np.array([h for _, h in iv])) for iv in ivs]
def tot_(P):
    out = 0
    for c in itertools.product((0, 1), repeat=4): out = out + ((-1) ** (4 - sum(c))) * P[np.ix_(*[I[k][c[k]] for k in range(4)])]
    return out
res = {k: tuple(tot_(prefix(x)) for x in cube(d)) for k, d in (('app', L), ('val', V))}
(nL, sL), (nV, sV) = res['app'], res['val']
rob = np.minimum(sL / np.maximum(nL, 1), sV / np.maximum(nV, 1)); ok = (nL >= COUV * tot['app']) & (nV >= COUV * 0.5 * tot['val'])
ix = np.unravel_index(np.argmax(np.where(ok, rob, -1)), rob.shape)
cond = [['n_dom', 5.0, None], ['n_ext', 5.0, None]]
for k, v in enumerate(VARS):
    lo, hi = ivs[k][ix[k]]; cond.append([v, None if lo == 0 else float(edges[v][lo - 1]), None if hi == nb[k] else float(edges[v][hi - 1])])
print('conditions', cond, '| réussite apprentissage / vérification : %.1f %% / %.1f %%' % (100 * sL[ix] / nL[ix], 100 * sV[ix] / nV[ix]))
def masque(d):
    m = np.ones(len(d), bool)
    for f, lo, hi in cond[2:]:
        x = d[f].values; m &= ~np.isnan(x)
        if lo is not None: m &= x >= lo
        if hi is not None: m &= x < hi
    return m
st = lambda d: (int(masque(d).sum()), int(d.y.values[masque(d)].sum()))
rech = (st(L)[0] + st(V)[0], st(L)[1] + st(V)[1]); tt = st(T); bb = st(B)
print('apprentissage', st(L), 'vérification', st(V), 'test 2017-20', tt, 'bloc 2025-26', bb)
if len(sys.argv) > 1:
    # parts de matchs : référence = nombre de matchs de l'échantillon à 4 matchs minimum (même dénominateur que les autres marchés)
    t4 = {k: pd.read_csv(D + 't_%s.csv' % k, usecols=['date']) for k in ('grand', 'bloc')}
    n_rech = int((t4['grand'].date < '2017-01-01').sum()); n_test = int((t4['grand'].date >= '2017-01-01').sum()); n_bloc = len(t4['bloc'])
    S = lambda n, s, tot_: dict(matchs=n, reussis=s, part_des_matchs=round(n / tot_, 4))
    row = dict(marche='total_plus_1.5', seuil=0.77, version='B', intervalles=[dict(conditions=cond, stats={'recherche_2000_2016': dict(n=rech[0], s=rech[1]), 'test_2017_2020': dict(n=tt[0], s=tt[1]), 'bloc_2025_26': dict(n=bb[0], s=bb[1])})],
               stats={'recherche_2000_2016': S(*rech, n_rech), 'test_2017_2020': S(*tt, n_test), 'bloc_2025_26': S(*bb, n_bloc)})
    Z = json.load(open(sys.argv[1])); Z.setdefault('regele', {}); Z['marches']['Plus de 1,5'] = row; Z['regele']['total_plus_1.5'] = '2026-11-25'
    json.dump(Z, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1); print('écrit', sys.argv[1])
