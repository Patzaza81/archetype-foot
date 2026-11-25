"""Recherche, marché par marché, de la meilleure zone des piliers (apprentissage -> validation -> test jamais vu).
Usage : python3 -I search.py [jeu]   jeu = P (piliers seuls, défaut) ou PL (piliers + moyenne du championnat)"""
import json, sys, itertools
import numpy as np, pandas as pd

Z = 1.96
SPLIT_V, SPLIT_T = '2013-01-01', '2017-01-01'
MARCHES = {
    'Victoire domicile': lambda h, a: h > a, 'Victoire extérieur': lambda h, a: a > h,
    'X1': lambda h, a: h >= a, 'X2': lambda h, a: a >= h,
    'Plus de 1,5': lambda h, a: h + a >= 2, 'Moins de 3,5': lambda h, a: h + a <= 3, 'Double chance 12': lambda h, a: h != a, 'Plus de 2,5': lambda h, a: h + a >= 3,
    'Domicile marque 1+': lambda h, a: h >= 1, 'Domicile marque 2+': lambda h, a: h >= 2,
    'Extérieur marque 1+': lambda h, a: a >= 1, 'Extérieur marque 2+': lambda h, a: a >= 2,
    'X1 + plus de 1,5': lambda h, a: (h >= a) & (h + a >= 2), 'X2 + plus de 1,5': lambda h, a: (a >= h) & (h + a >= 2),
    'X1 + moins de 4,5': lambda h, a: (h >= a) & (h + a <= 4), 'X2 + moins de 4,5': lambda h, a: (a >= h) & (h + a <= 4),
}
FEAT_X = ['EH', 'EA', 'ET', 'dE', 'rE', 'mu', 'EHm', 'EAm', 'gH', 'gA']   # xG estimé tous lieux + xG du championnat
FEAT_P = ['hM', 'hC', 'aM', 'aC', 'dM', 'dC', 'A1', 'A2', 'X1g', 'X2g', 'SM', 'SC', 'TG', 'rM', 'rC', 'rX']


def wilson(s, n):
    if n == 0:
        return (float('nan'),) * 3
    p = s / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    w = Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return p, c - w, c + w


def lb(s, n):
    n = np.maximum(n, 1)
    p = np.clip(s / n, 0, 1)
    d = 1 + Z * Z / n
    return ((p + Z * Z / (2 * n)) - Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))) / d


def charger():
    t = {k: pd.read_csv('/home/claude/etude_n/t_%s.csv' % k) for k in ('grand', 'bloc', 'flux')}
    for k, d in t.items():
        for nom, f in MARCHES.items():
            d[nom] = f(d.bd, d.be).astype(int)
    return t


def ajouter_ligue(d):
    d['LT'] = d.LH + d.LA
    d['aH'] = d.hM / d.LH; d['dH'] = d.hC / d.LA   # attaque et défense à domicile relatives au championnat
    d['aA'] = d.aM / d.LA; d['dA'] = d.aC / d.LH
    d['XH'] = d.aH * d.dA * d.LH                  # buts attendus domicile (force relative x moyenne du championnat)
    d['XA'] = d.aA * d.dH * d.LA
    return d


def bins(x, edges):
    b = np.searchsorted(edges, x, side='right')
    return np.where(np.isnan(x), -1, b)


def prefixes(b1, b2, y, K1, K2):
    ok = (b1 >= 0) & (b2 >= 0)
    idx = b1[ok] * K2 + b2[ok]
    N = np.bincount(idx, minlength=K1 * K2).reshape(K1, K2).astype(float)
    S = np.bincount(idx, weights=y[ok], minlength=K1 * K2).reshape(K1, K2)
    P = lambda M: np.pad(M.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    return P(N), P(S)


def rect(P, K1, K2):
    i1, i2, j1, j2 = np.meshgrid(np.arange(K1), np.arange(K1), np.arange(K2), np.arange(K2), indexing='ij')
    v = (i2 >= i1) & (j2 >= j1)
    val = P[i2 + 1, j2 + 1] - P[i1, j2 + 1] - P[i2 + 1, j1] + P[i1, j1]
    return val, v, (i1, i2, j1, j2)


COUV = (0.01, 0.02, 0.05, 0.10, 0.20)   # parts de matchs retenues : le menu de la courbe volume / fiabilité


def chercher(L, V, feats, marche, nbs=(5, 10, 20)):
    """Pour chaque niveau de volume : la zone (1 ou 2 piliers/écarts, intervalles en quantiles) qui maximise
    min(borne basse de Wilson sur l'apprentissage, borne basse sur la validation), avec au moins ce volume
    dans l'apprentissage ET dans la validation."""
    yL, yV = L[marche].values.astype(float), V[marche].values.astype(float)
    baseL = yL.mean()
    meilleur = {c: None for c in COUV}
    for nb in nbs:
        E = {}
        for f in feats:
            x = L[f].values
            E[f] = np.unique(np.quantile(x[~np.isnan(x)], np.arange(1, nb) / nb))
        BL = {f: bins(L[f].values, E[f]) for f in feats}
        BV = {f: bins(V[f].values, E[f]) for f in feats}
        for f, g in [(f, None) for f in feats] + list(itertools.combinations(feats, 2)):
            K1 = len(E[f]) + 1
            if g is None:
                K2 = 1; bl2, bv2 = np.zeros(len(L), dtype=int), np.zeros(len(V), dtype=int)
            else:
                K2 = len(E[g]) + 1; bl2, bv2 = BL[g], BV[g]
            PnL, PsL = prefixes(BL[f], bl2, yL, K1, K2)
            PnV, PsV = prefixes(BV[f], bv2, yV, K1, K2)
            nL, vv, ix = rect(PnL, K1, K2); sL, _, _ = rect(PsL, K1, K2)
            nV, _, _ = rect(PnV, K1, K2); sV, _, _ = rect(PsV, K1, K2)
            lL, lV = lb(sL, nL), lb(sV, nV)
            score = np.minimum(lL, lV)
            for c in COUV:
                ok = vv & (nL >= c * len(L)) & (nV >= c * len(V)) & (lL > baseL)
                if not ok.any():
                    continue
                sc = np.where(ok, score, -1)
                k = np.unravel_index(np.argmax(sc), sc.shape)
                if meilleur[c] is None or sc[k] > meilleur[c]['score']:
                    i1, i2, j1, j2 = [a[k] for a in ix]
                    def borne(e, a, b):
                        return (e[a - 1] if a > 0 else -np.inf, e[b] if b < len(e) else np.inf)
                    zone = [(f,) + borne(E[f], i1, i2)]
                    if g is not None:
                        zone.append((g,) + borne(E[g], j1, j2))
                    meilleur[c] = dict(score=float(sc[k]), nb=nb, zone=zone)
    return meilleur


def masque(d, zone):
    m = np.ones(len(d), dtype=bool)
    for f, lo, hi in zone:
        x = d[f].values
        m &= (x >= lo) & (x < hi)   # NaN -> faux
    return m


def mesure(d, m, marche):
    n = int(m.sum()); s = int(d[marche].values[m].sum())
    p, lo, hi = wilson(s, n) if n else (float('nan'),) * 3
    return dict(n=n, s=s, taux=p, lo=lo, hi=hi)


def decrire(zone):
    out = []
    for f, lo, hi in zone:
        a = '' if lo == -np.inf else '%.3f ≤ ' % lo
        b = '' if hi == np.inf else ' < %.3f' % hi
        out.append('%s%s%s' % (a, f, b))
    return ' et '.join(out)


if __name__ == '__main__':
    jeu = sys.argv[1] if len(sys.argv) > 1 else 'P'
    t = charger()
    feats = list(FEAT_P)
    if jeu == 'PX':
        feats += FEAT_X
    if jeu == 'PL':
        for k in ('grand', 'bloc'):
            ajouter_ligue(t[k])
        feats += ['LT', 'aH', 'dH', 'aA', 'dA', 'XH', 'XA']
    g = t['grand']
    L, V, T = g[g.date < SPLIT_V], g[(g.date >= SPLIT_V) & (g.date < SPLIT_T)], g[g.date >= SPLIT_T]
    res = {}
    echs = (('appr', L), ('valid', V), ('test_grand', T), ('bloc', t['bloc'])) + ((('flux', t['flux']),) if jeu in ('P', 'PX') else ())
    print('tailles', {n: len(d) for n, d in echs})
    for marche in MARCHES:
        zs = chercher(L, V, feats, marche)
        res[marche] = {}
        for c, z in zs.items():
            if not z:
                continue
            r = dict(zone=[(f, float(lo), float(hi)) for f, lo, hi in z['zone']], nb=z['nb'], score=z['score'],
                     texte=decrire(z['zone']))
            for nom, d in echs:
                r[nom] = mesure(d, masque(d, z['zone']), marche)
                r[nom]['base'] = float(d[marche].mean())
            res[marche]['%.2f' % c] = r
            tg, bl = r['test_grand'], r['bloc']
            print('%-22s c=%.2f | %-48s | test %4d/%4d %.3f | bloc %4d/%4d %.3f | base %.3f' % (
                marche, c, r['texte'][:48], tg['s'], tg['n'], tg['taux'], bl['s'], bl['n'], bl['taux'], tg['base']), flush=True)
    json.dump(res, open('/home/claude/etude_n/zones_%s.json' % jeu, 'w'), ensure_ascii=False, indent=1, default=float)
