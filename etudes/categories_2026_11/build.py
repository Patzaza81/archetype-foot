"""Construit les tables de mesures (4 piliers au lieu du match, sans fuite) pour les 3 échantillons.
Usage : python3 -I build.py   (lit /home/claude/neutre/*.csv, écrit /home/claude/etude_n/t_*.csv)"""
import csv, math, sys
from collections import defaultdict
import pandas as pd

D = '/home/claude/neutre/'
NMIN = 4  # règle de Patrick


def calibrer():
    """xG estimé = a + b * buts moyens (tous lieux), droite apprise par équipe sur les lignes à xG réel."""
    import numpy as np
    h = pd.read_csv(D + 'flux_historiques_equipes.csv').dropna(subset=['xg_cree', 'xg_concede'])
    t = h.groupby('equipe').agg(n=('xg_cree', 'size'), m=('buts_marques', 'mean'), xm=('xg_cree', 'mean'),
                                e=('buts_encaisses', 'mean'), xe=('xg_concede', 'mean'))
    t = t[t.n >= 8]
    bm, am = np.polyfit(t.m, t.xm, 1)
    be, ae = np.polyfit(t.e, t.xe, 1)
    return dict(am=am, bm=bm, ae=ae, be=be, n=len(t))


CAL = calibrer()


def mesures(h, a, ta=None, tb=None, mu=None):
    """ta, tb = (n, marqués, encaissés) de l'équipe à domicile / à l'extérieur sur TOUS ses matchs de la saison
    (domicile et extérieur confondus) ; mu = buts par équipe et par match du championnat en cours (tous matchs)."""
    """h = (n, sM, sC) de l'équipe à domicile À DOMICILE ; a = idem pour l'extérieur À L'EXTÉRIEUR."""
    hM, hC = h[1] / h[0], h[2] / h[0]
    aM, aC = a[1] / a[0], a[2] / a[0]
    X1, X2 = hM + aC, aM + hC
    xg = {}
    if ta is not None and tb is not None and ta[0] > 0 and tb[0] > 0 and mu is not None:
        sMh, sCh, sMa, sCa = ta[1] / ta[0], ta[2] / ta[0], tb[1] / tb[0], tb[2] / tb[0]
        xAh, xDh = CAL['am'] + CAL['bm'] * sMh, CAL['ae'] + CAL['be'] * sCh   # xG créé / concédé estimé, tous lieux
        xAa, xDa = CAL['am'] + CAL['bm'] * sMa, CAL['ae'] + CAL['be'] * sCa
        EH, EA = (xAh + xDa) / 2, (xAa + xDh) / 2                          # xG attendu de chaque équipe
        xg = dict(sMh=sMh, sCh=sCh, sMa=sMa, sCa=sCa, EH=EH, EA=EA, ET=EH + EA, dE=EH - EA, rE=EH / EA,
                  mu=mu, EHm=EH - mu, EAm=EA - mu, gH=X1 / 2 - EH, gA=X2 / 2 - EA, nta=ta[0], ntb=tb[0])
    return dict(**xg, nh=h[0], na=a[0], hM=hM, hC=hC, aM=aM, aC=aC,
                dM=hM - aM, dC=hC - aC, A1=hM - aC, A2=aM - hC,
                X1g=X1, X2g=X2, SM=hM + aM, SC=hC + aC, TG=X1 + X2,
                rM=(hM / aM if aM > 0 else float('nan')),
                rC=(hC / aC if aC > 0 else float('nan')),
                rX=(X1 / X2 if X2 > 0 else float('nan')))


def parcourir(matchs):
    """matchs : liste (groupe, date, dom, ext, bd, be, id) ; une saison/ligue = un groupe.
    Mesures calculées uniquement avec les matchs STRICTEMENT antérieurs (même groupe, même lieu)."""
    out = []
    groupes = defaultdict(list)
    for m in matchs:
        groupes[m[0]].append(m)
    for g, lst in groupes.items():
        lst.sort(key=lambda m: m[1])
        dom = defaultdict(lambda: [0, 0, 0])  # équipe -> n, marqués, encaissés (à domicile)
        ext = defaultdict(lambda: [0, 0, 0])
        tout = defaultdict(lambda: [0, 0, 0])   # tous lieux confondus
        L = [0, 0, 0]  # n, buts dom, buts ext
        i = 0
        while i < len(lst):
            j = i
            while j < len(lst) and lst[j][1] == lst[i][1]:
                j += 1
            jour = lst[i:j]
            for (_, d, A, B, bd, be, mid) in jour:
                if dom[A][0] >= NMIN and ext[B][0] >= NMIN and L[0] > 0:
                    r = mesures(dom[A], ext[B], tout[A], tout[B], (L[1] + L[2]) / (2 * L[0]))
                    r.update(id=mid, groupe=g, date=d, bd=bd, be=be,
                             LH=L[1] / L[0], LA=L[2] / L[0], nL=L[0])
                    out.append(r)
            for (_, d, A, B, bd, be, mid) in jour:  # mise à jour APRÈS le jour entier
                dom[A][0] += 1; dom[A][1] += bd; dom[A][2] += be
                ext[B][0] += 1; ext[B][1] += be; ext[B][2] += bd
                tout[A][0] += 1; tout[A][1] += bd; tout[A][2] += be
                tout[B][0] += 1; tout[B][1] += be; tout[B][2] += bd
                L[0] += 1; L[1] += bd; L[2] += be
            i = j
    return pd.DataFrame(out)


def grand():
    ms = []
    with open(D + 'grand_echantillon_2000_2021.csv', encoding='utf-8') as f:
        for k, r in enumerate(csv.DictReader(f)):
            if r['buts_dom'] == '' or r['buts_ext'] == '':
                continue
            ms.append(((r['ligue'], r['saison']), r['date'], r['domicile'], r['exterieur'],
                       int(r['buts_dom']), int(r['buts_ext']), 'g%d' % k))
    return parcourir(ms)


def bloc():
    ms = []
    cotes = {}
    with open(D + 'bloc_matchs_footballdata.csv', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['buts_dom'] == '' or r['buts_ext'] == '':
                continue
            ms.append(((r['division'], r['saison']), r['date'], r['domicile'], r['exterieur'],
                       int(r['buts_dom']), int(r['buts_ext']), r['id']))
            cotes[r['id']] = {k: (float(r[k]) if r[k] else float('nan')) for k in
                              ('cote_1_cloture', 'cote_N_cloture', 'cote_2_cloture',
                               'cote_plus_2_5_cloture', 'cote_moins_2_5_cloture')}
    t = parcourir(ms)
    c = pd.DataFrame.from_dict(cotes, orient='index')
    return t.join(c, on='id')


def flux():
    h = pd.read_csv(D + 'flux_historiques_equipes.csv')
    h = h.dropna(subset=['buts_marques', 'buts_encaisses'])
    idx = defaultdict(list)  # (equipe, competition, lieu) -> [(date, marqués, encaissés)]
    for r in h.itertuples():
        idx[(r.equipe, r.competition, int(r.a_domicile))].append((r.date, r.buts_marques, r.buts_encaisses))
    for k in idx:
        idx[k].sort()
    allr = defaultdict(list)   # (equipe, competition) -> tous lieux
    comp = defaultdict(list)   # competition -> (date, buts marqués d'une équipe)
    for r in h.itertuples():
        allr[(r.equipe, r.competition)].append((r.date, r.buts_marques, r.buts_encaisses))
        comp[r.competition].append((r.date, r.buts_marques))
    for k in allr:
        allr[k].sort()
    for k in comp:
        comp[k].sort()
    f = pd.read_csv(D + 'flux_matchs_betpawa.csv')
    out = []
    for r in f.itertuples():
        if pd.isna(r.buts_dom) or pd.isna(r.buts_ext):
            continue
        a = [x for x in idx.get((r.domicile, r.competition, 1), []) if x[0] < r.date]
        b = [x for x in idx.get((r.exterieur, r.competition, 0), []) if x[0] < r.date]
        if len(a) < NMIN or len(b) < NMIN:
            continue
        hh = (len(a), sum(x[1] for x in a), sum(x[2] for x in a))
        aa = (len(b), sum(x[1] for x in b), sum(x[2] for x in b))
        ta = [x for x in allr.get((r.domicile, r.competition), []) if x[0] < r.date]
        tb = [x for x in allr.get((r.exterieur, r.competition), []) if x[0] < r.date]
        cc = [x[1] for x in comp.get(r.competition, []) if x[0] < r.date]
        mu = sum(cc) / len(cc) if cc else None
        m = mesures(hh, aa, (len(ta), sum(x[1] for x in ta), sum(x[2] for x in ta)),
                    (len(tb), sum(x[1] for x in tb), sum(x[2] for x in tb)), mu)
        m.update(id=r.match_id, groupe=r.competition, date=r.date, bd=int(r.buts_dom), be=int(r.buts_ext),
                 LH=mu if mu else float('nan'), LA=mu if mu else float('nan'), nL=len(cc))
        for c in f.columns:
            if c.startswith('bp_'):
                m[c] = getattr(r, c)
        out.append(m)
    return pd.DataFrame(out)


if __name__ == '__main__':
    g = grand(); g.to_csv('/home/claude/etude_n/t_grand.csv', index=False)
    b = bloc(); b.to_csv('/home/claude/etude_n/t_bloc.csv', index=False)
    x = flux(); x.to_csv('/home/claude/etude_n/t_flux.csv', index=False)
    print(len(g), len(b), len(x)); print(CAL)
