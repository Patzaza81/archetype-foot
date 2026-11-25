"""25/11 - Bibliothèque de variables (plusieurs centaines) pour le marché +1,5 : min. 5 matchs au même lieu par équipe, sans fuite.
Par équipe et par lieu : moyennes, parts de matchs (0 but, 2+, sans encaisser, 2+ encaissés, total 0/<=1/2+/3+/4+, deux équipes marquent), écart-type,
sur 4 fenêtres (tous les matchs, 3, 5, 8 derniers) ; combinaisons des deux équipes (somme, min, max, écart, produit, croisés attaque x défense) ; tous lieux ; xG ; championnat."""
import csv, sys
from collections import defaultdict
import numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/etude_n')
import build as B
NM = 5; D = B.D
WIN = {'t': None, 'w3': 3, 'w5': 5, 'w8': 8}

def stats(a):
    """a : tableau (n,2) [marqués, encaissés] -> dict de 15 statistiques."""
    s, c = a[:, 0], a[:, 1]; t = s + c
    return {'ms': s.mean(), 'mc': c.mean(), 'mt': t.mean(), 'sd': t.std(), 'ps0': (s == 0).mean(), 'ps2': (s >= 2).mean(), 'pc0': (c == 0).mean(), 'pc2': (c >= 2).mean(),
            'pt0': (t == 0).mean(), 'ple1': (t <= 1).mean(), 'pt2': (t >= 2).mean(), 'pt3': (t >= 3).mean(), 'pt4': (t >= 4).mean(), 'pbt': ((s >= 1) & (c >= 1)).mean(), 'md': (s - c).mean()}
STAT = ['ms', 'mc', 'mt', 'sd', 'ps0', 'ps2', 'pc0', 'pc2', 'pt0', 'ple1', 'pt2', 'pt3', 'pt4', 'pbt', 'md']
ALLV = ['ms', 'mc', 'mt', 'ple1', 'pt2', 'pt3']

def ligne(hv, av, ha, aa):
    r = {}
    for wn, w in WIN.items():
        H = stats(np.asarray(hv[-w:] if w else hv, float)); A = stats(np.asarray(av[-w:] if w else av, float))
        for k in STAT:
            h, a = H[k], A[k]
            r[f'h_{k}_{wn}'] = h; r[f'a_{k}_{wn}'] = a; r[f'sum_{k}_{wn}'] = h + a; r[f'min_{k}_{wn}'] = min(h, a); r[f'max_{k}_{wn}'] = max(h, a)
            r[f'dif_{k}_{wn}'] = abs(h - a); r[f'prd_{k}_{wn}'] = h * a
        for nom, (x, y) in {'s2c2': ('ps2', 'pc2'), 's0c0': ('ps0', 'pc0'), 'msc': ('ms', 'mc')}.items():
            x1, x2 = (H[x] + A[y]) / 2, (A[x] + H[y]) / 2
            r[f'cr1_{nom}_{wn}'] = x1; r[f'cr2_{nom}_{wn}'] = x2; r[f'crs_{nom}_{wn}'] = x1 + x2; r[f'crm_{nom}_{wn}'] = min(x1, x2); r[f'crx_{nom}_{wn}'] = max(x1, x2)
    if len(ha) and len(aa):
        H = stats(np.asarray(ha, float)); A = stats(np.asarray(aa, float))
        for k in ALLV:
            r[f'th_{k}'] = H[k]; r[f'ta_{k}'] = A[k]; r[f'tsum_{k}'] = H[k] + A[k]; r[f'tmin_{k}'] = min(H[k], A[k]); r[f'tmax_{k}'] = max(H[k], A[k])
    return r

def un(out, m, hv, av, ha, aa, mid, g, d, bd, be, L, lp2):
    hh = (len(hv), sum(x[0] for x in hv), sum(x[1] for x in hv)); aa_ = (len(av), sum(x[0] for x in av), sum(x[1] for x in av))
    ta = (len(ha), sum(x[0] for x in ha), sum(x[1] for x in ha)); tb = (len(aa), sum(x[0] for x in aa), sum(x[1] for x in aa))
    r = B.mesures(hh, aa_, ta, tb, L)
    r.update(ligne(hv, av, ha, aa)); r.update(id=mid, groupe=g, date=d, bd=bd, be=be, mu=L, LP2=lp2)
    return r

def parcourir(matchs):
    out = []; groupes = defaultdict(list)
    for m in matchs: groupes[m[0]].append(m)
    for g, lst in groupes.items():
        lst.sort(key=lambda m: m[1])
        dom = defaultdict(list); ext = defaultdict(list); tout = defaultdict(list); nL = 0; sL = 0; p2 = 0
        i = 0
        while i < len(lst):
            j = i
            while j < len(lst) and lst[j][1] == lst[i][1]: j += 1
            jour = lst[i:j]
            for (_, d, A, Bq, bd, be, mid) in jour:
                if len(dom[A]) >= NM and len(ext[Bq]) >= NM and nL > 0:
                    out.append(un(out, None, dom[A], ext[Bq], tout[A], tout[Bq], mid, g, d, bd, be, sL / (2 * nL), p2 / nL))
            for (_, d, A, Bq, bd, be, mid) in jour:
                dom[A].append((bd, be)); ext[Bq].append((be, bd)); tout[A].append((bd, be)); tout[Bq].append((be, bd)); nL += 1; sL += bd + be; p2 += (bd + be >= 2)
            i = j
    return pd.DataFrame(out)

def lire(fichier, cl, cs, idf):
    ms = []
    with open(D + fichier, encoding='utf-8') as f:
        for k, r in enumerate(csv.DictReader(f)):
            if r['buts_dom'] == '' or r['buts_ext'] == '': continue
            ms.append(((r[cl], r[cs]), r['date'], r['domicile'], r['exterieur'], int(r['buts_dom']), int(r['buts_ext']), idf(r, k)))
    return ms

def flux():
    h = pd.read_csv(D + 'flux_historiques_equipes.csv').dropna(subset=['buts_marques', 'buts_encaisses'])
    idx = defaultdict(list); allr = defaultdict(list); comp = defaultdict(list)
    for r in h.itertuples():
        idx[(r.equipe, r.competition, int(r.a_domicile))].append((r.date, r.buts_marques, r.buts_encaisses)); allr[(r.equipe, r.competition)].append((r.date, r.buts_marques, r.buts_encaisses)); comp[r.competition].append((r.date, r.buts_marques + r.buts_encaisses, r.buts_marques))
    for d in (idx, allr, comp):
        for k in d: d[k].sort()
    f = pd.read_csv(D + 'flux_matchs_betpawa.csv'); out = []
    for r in f.itertuples():
        if pd.isna(r.buts_dom) or pd.isna(r.buts_ext): continue
        a = [(x[1], x[2]) for x in idx.get((r.domicile, r.competition, 1), []) if x[0] < r.date]; b = [(x[1], x[2]) for x in idx.get((r.exterieur, r.competition, 0), []) if x[0] < r.date]
        if len(a) < NM or len(b) < NM: continue
        ta = [(x[1], x[2]) for x in allr.get((r.domicile, r.competition), []) if x[0] < r.date]; tb = [(x[1], x[2]) for x in allr.get((r.exterieur, r.competition), []) if x[0] < r.date]
        cc = [x for x in comp.get(r.competition, []) if x[0] < r.date]
        mu = sum(x[2] for x in cc) / len(cc) if cc else None
        if mu is None: continue
        rr = un(out, None, a, b, ta, tb, r.match_id, r.competition, r.date, int(r.buts_dom), int(r.buts_ext), mu, sum(x[1] >= 2 for x in cc) / len(cc))
        for c in f.columns:
            if c.startswith('bp_'): rr[c] = getattr(r, c)
        out.append(rr)
    return pd.DataFrame(out)

if __name__ == '__main__':
    g = parcourir(lire('grand_echantillon_2000_2021.csv', 'ligue', 'saison', lambda r, k: 'g%d' % k)); g.to_pickle('t6_grand.pkl'); print('grand', g.shape, flush=True)
    b = parcourir(lire('bloc_matchs_footballdata.csv', 'division', 'saison', lambda r, k: r['id']))
    c = pd.read_csv(D + 'bloc_matchs_footballdata.csv').set_index('id'); b = b.join(c[['cote_1_cloture', 'cote_N_cloture', 'cote_2_cloture', 'cote_plus_2_5_cloture', 'cote_moins_2_5_cloture']], on='id'); b.to_pickle('t6_bloc.pkl'); print('bloc', b.shape, flush=True)
    x = flux(); x.to_pickle('t6_flux.pkl'); print('flux', x.shape)
