"""Backtest V3 : candidats V3 vs prix du marche (1/cote) vs hasard, sur les matchs deja joues.

Anti-fuite : on n'utilise que probabilite/cote ecrites AVANT le match dans data/v3/journal/*.json ;
le score vient de data/archive_test (champ score, ecrit apres le match). Lecture seule, ne modifie rien.
Limites : echantillon de ~13 jours ; paris d'un meme match non independants ; probabilites V3 brutes
(la plupart des candidats sont ecartes par V3 lui-meme, voir 'raisons').
Lancer : python3 -I evaluation/backtest_v3_vs_marche.py
"""
import json,gzip,glob,sys,collections,os,math,random
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,R); os.chdir(R)
from moteur_v3.markets import gagne
scores={}
for f in sorted(glob.glob('data/archive_test/*.json.gz')):
    for k,m in json.load(gzip.open(f)).items():
        s=m.get('score')
        if s and s.get('buts_dom') is not None: scores[k]=(s['buts_dom'],s['buts_ext'],m['date'])
rows=[]
for f in sorted(glob.glob('data/v3/journal/*.json')):
    for k,m in json.load(open(f)).items():
        if m.get('statut')!='EVALUE' or k not in scores: continue
        h,a,d=scores[k]
        for c in m['candidats']:
            g=gagne(c['marche'],h,a)
            if g is None or c['marche'].startswith(('score_','exact_goals')): continue
            rows.append(dict(mid=k,date=d,marche=c['marche'],p=c['probabilite'],cote=c['cote'],win=g,raisons=c['raisons'],cal=c['calibree']))
def wil(w,n,z=1.96):
    if n==0: return (0,0)
    p=w/n; d=1+z*z/n; c=p+z*z/(2*n); a=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return (c-a)/d,(c+a)/d
def rep(nom,S):
    n=len(S); w=sum(r['win'] for r in S)
    if not n: print(f'{nom:55s} n=0'); return
    lo,hi=wil(w,n); mp=sum(r['p'] for r in S)/n; mi=sum(1/r['cote'] for r in S)/n
    print(f'{nom:55s} n={n:4d} matchs={len({r["mid"] for r in S}):3d} reel={w/n:.3f} [{lo:.2f}-{hi:.2f}] V3 dit={mp:.3f} marche dit={mi:.3f}')
print('=== Pool: candidats V3 (hors scores exacts/total exact), matchs avec score ===')
rep('tous',rows)
for t in (0.6,0.7,0.8): rep(f'V3 p>={t}',[r for r in rows if r['p']>=t])
rep('V3 p>=0.6 et cote 1.26-1.56',[r for r in rows if r['p']>=0.6 and 1.26<=r['cote']<=1.56])
rep('MARCHE seul: cote<=1.56 (favoris du marche)',[r for r in rows if r['cote']<=1.56])
rep('MARCHE seul: cote 1.26-1.56',[r for r in rows if 1.26<=r['cote']<=1.56])
rep('V3 p>=0.6 ET cote<=1.56',[r for r in rows if r['p']>=0.6 and r['cote']<=1.56])
elig=[r for r in rows if not [x for x in r['raisons'] if x not in ('CALIBRATION_ABSENTE',)]]
rep('V3 sans aucune raison de rejet (hors calibration)',elig)
print('\n=== Simulation top-N par jour de match (N=15) ===')
random.seed(7)
def topn(key,pool,N=15,rev=True):
    out=[]
    byd=collections.defaultdict(list)
    for r in pool: byd[r['date']].append(r)
    for d,L in byd.items():
        seen=set(); L=sorted(L,key=key,reverse=rev); 
        for r in L:
            if r['mid'] in seen: continue
            seen.add(r['mid']); out.append(r)
            if len(seen)>=N: break
    return out
pool=[r for r in rows if r['cote']>=1.26]
rep('V3: top15/jour par probabilite',topn(lambda r:r['p'],pool))
rep('MARCHE: top15/jour par 1/cote (favoris)',topn(lambda r:1/r['cote'],pool))
rs=[]
for i in range(500):
    x=random.sample(pool,len(pool)); byd=collections.defaultdict(list)
    for r in x: byd[r['date']].append(r)
    sel=[]
    for d,L in byd.items():
        seen=set()
        for r in L:
            if r['mid'] in seen: continue
            seen.add(r['mid']); sel.append(r)
            if len(seen)>=15: break
    rs.append(sum(r['win'] for r in sel)/len(sel))
rs.sort(); print(f'HASARD (500 tirages): taux moyen={sum(rs)/len(rs):.3f}  5%-95%=[{rs[25]:.3f}-{rs[475]:.3f}]')
print('\n=== Brier (plus bas = mieux) ===')
def brier(S,f): return sum((f(r)-r['win'])**2 for r in S)/len(S)
S=[r for r in rows if r['p']>=0.5]
print('n',len(S),'V3',round(brier(S,lambda r:r['p']),4),'1/cote',round(brier(S,lambda r:min(1,1/r['cote'])),4),'taux de base',round(brier(S,lambda r:sum(x['win'] for x in S)/len(S)),4))
print('\n=== Par marche (V3 p>=0.6, n>=8) ===')
bm=collections.defaultdict(list)
for r in rows:
    if r['p']>=0.6: bm[r['marche']].append(r)
for k,v in sorted(bm.items(),key=lambda kv:-len(kv[1])):
    if len(v)>=8: rep(k,v)
print('\n=== Par jour (V3 p>=0.6) ===')
bd=collections.defaultdict(list)
for r in rows:
    if r['p']>=0.6: bd[r['date']].append(r)
for k in sorted(bd): rep(k,bd[k])
print('\n=== Sous-ensembles calibres / avec raisons ===')
rep('calibree=True',[r for r in rows if r['cal']])
print(collections.Counter(len(r['raisons']) for r in rows if r['p']>=0.6).most_common(6))
print(collections.Counter(x for r in rows if r['p']>=0.6 for x in r['raisons']).most_common(8))
