"""Pour UN marché et SON seuil : on teste des intervalles (1 ou 2 mesures : rapports, écarts, xG) et on cumule, un par un,
ceux qui atteignent le seuil sur la période de recherche (apprentissage ET validation), jusqu'à épuisement.
Le résultat est mesuré sur des matchs jamais vus (2017-2020, bloc 2025-26, flux)."""
import json, sys, itertools
import numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/etude_n')
from search import charger, masque, mesure, decrire, lb, bins, wilson, prefixes, rect, MARCHES, FEAT_P, FEAT_X, SPLIT_V, SPLIT_T


def couvrir(L, V, feats, marche, seuil, nbs=(10, 20), max_regles=40, strict=False):
    yL, yV = L[marche].values.astype(float), V[marche].values.astype(float)
    cL, cV = np.zeros(len(L), bool), np.zeros(len(V), bool)       # déjà couverts
    tabs = []
    for nb in nbs:
        E = {f: np.unique(np.quantile(L[f].values[~np.isnan(L[f].values)], np.arange(1, nb) / nb)) for f in feats}
        tabs.append((nb, E, {f: bins(L[f].values, E[f]) for f in feats}, {f: bins(V[f].values, E[f]) for f in feats}))
    regles = []
    while len(regles) < max_regles:
        best = None
        uL, uV = ~cL, ~cV
        for nb, E, BL, BV in tabs:
            for f, g in [(f, None) for f in feats] + list(itertools.combinations(feats, 2)):
                K1 = len(E[f]) + 1
                if g is None:
                    K2 = 1; bl2 = np.zeros(len(L), int); bv2 = np.zeros(len(V), int)
                else:
                    K2 = len(E[g]) + 1; bl2, bv2 = BL[g], BV[g]
                bf_l = np.where(uL, BL[f], -1); bf_v = np.where(uV, BV[f], -1)
                PnL, PsL = prefixes(bf_l, bl2, yL, K1, K2)
                PnV, PsV = prefixes(bf_v, bv2, yV, K1, K2)
                nL, vv, ix = rect(PnL, K1, K2); sL, _, _ = rect(PsL, K1, K2)
                nV, _, _ = rect(PnV, K1, K2); sV, _, _ = rect(PsV, K1, K2)
                n, s = nL + nV, sL + sV
                ok = vv & (nL > 0) & (nV > 0) & (lb(s, n) >= seuil) & (sL / np.maximum(nL, 1) >= seuil) & (sV / np.maximum(nV, 1) >= seuil)
                if strict:   # l'intervalle doit atteindre le seuil, avec certitude, sur CHACUNE des deux périodes
                    ok = ok & (lb(sL, nL) >= seuil) & (lb(sV, nV) >= seuil)
                if not ok.any():
                    continue
                k = np.unravel_index(np.argmax(np.where(ok, n, -1)), n.shape)
                if best is None or n[k] > best['n']:
                    i1, i2, j1, j2 = [a[k] for a in ix]
                    def borne(e, a, b):
                        return (float(e[a - 1]) if a > 0 else -np.inf, float(e[b]) if b < len(e) else np.inf)
                    zone = [(f,) + borne(E[f], i1, i2)]
                    if g is not None:
                        zone.append((g,) + borne(E[g], j1, j2))
                    best = dict(n=float(n[k]), zone=zone, nb=nb)
        if best is None:
            break
        z = best['zone']
        mL, mV = masque(L, z) & uL, masque(V, z) & uV
        cL |= mL; cV |= mV
        regles.append(z)
    return regles


def union(d, regles):
    m = np.zeros(len(d), bool)
    for z in regles:
        m |= masque(d, z)
    return m


if __name__ == '__main__':
    marche = sys.argv[1]; seuil = float(sys.argv[2])
    t = charger()
    feats = FEAT_P + FEAT_X
    g = t['grand']
    L, V, T = g[g.date < SPLIT_V], g[(g.date >= SPLIT_V) & (g.date < SPLIT_T)], g[g.date >= SPLIT_T]
    regles = couvrir(L, V, feats, marche, seuil)
    print(marche, 'seuil', seuil, '- nombre d\'intervalles retenus :', len(regles))
    for z in regles:
        print('  ', decrire(z))
    out = {}
    for nom, d in (('appr', L), ('valid', V), ('test_grand', T), ('bloc', t['bloc']), ('flux', t['flux'])):
        m = union(d, regles)
        r = mesure(d, m, marche); r['part'] = float(m.mean()); r['base'] = float(d[marche].mean())
        out[nom] = r
        print('%-10s %5d matchs retenus (%.1f %% des matchs) réussis %5d = %.1f %% [%.1f - %.1f] | tous les matchs %.1f %%' % (
            nom, r['n'], 100 * r['part'], r['s'], 100 * r['taux'], 100 * r['lo'], 100 * r['hi'], 100 * r['base']))
    json.dump(dict(marche=marche, seuil=seuil, regles=[[list(x) for x in z] for z in regles], mesures=out),
              open('/home/claude/etude_n/cover_%s_%d.json' % (marche.replace(' ', '_'), round(100 * seuil)), 'w'), ensure_ascii=False, indent=1, default=float)
