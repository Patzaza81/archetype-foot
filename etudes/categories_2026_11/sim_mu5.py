import sys, json, csv, random
sys.path.insert(0,'/home/claude/etude_n')
from collections import defaultdict
import numpy as np, pandas as pd
import build
from search import charger, masque
from cover import union
NMIN=4; K=int(sys.argv[1]) if len(sys.argv)>1 else 5
random.seed(7)
def parcourir5(matchs, depuis):
    out=[]; groupes=defaultdict(list)
    for m in matchs: groupes[m[0]].append(m)
    for g,lst in groupes.items():
        lst.sort(key=lambda m:m[1]); dom=defaultdict(lambda:[0,0,0]); ext=defaultdict(lambda:[0,0,0]); tout=defaultdict(lambda:[0,0,0]); tot=[]; i=0
        while i<len(lst):
            j=i
            while j<len(lst) and lst[j][1]==lst[i][1]: j+=1
            jour=lst[i:j]
            for (_,d,A,B,bd,be,mid) in jour:
                if d>=depuis and dom[A][0]>=NMIN and ext[B][0]>=NMIN and len(tot)>=K:
                    mu=sum(random.sample(tot,K))/(2*K)
                    r=build.mesures(dom[A],ext[B],tout[A],tout[B],mu); r.update(id=mid,bd=bd,be=be,date=d); out.append(r)
            for (_,d,A,B,bd,be,mid) in jour:
                dom[A][0]+=1;dom[A][1]+=bd;dom[A][2]+=be; ext[B][0]+=1;ext[B][1]+=be;ext[B][2]+=bd
                tout[A][0]+=1;tout[A][1]+=bd;tout[A][2]+=be; tout[B][0]+=1;tout[B][1]+=be;tout[B][2]+=bd; tot.append(bd+be)
            i=j
    return pd.DataFrame(out)
ms=[]
with open(build.D+'grand_echantillon_2000_2021.csv',encoding='utf-8') as f:
    for k,r in enumerate(csv.DictReader(f)):
        if r['buts_dom']=='' or r['buts_ext']=='': continue
        ms.append(((r['ligue'],r['saison']),r['date'],r['domicile'],r['exterieur'],int(r['buts_dom']),int(r['buts_ext']),'g%d'%k))
G=parcourir5(ms,'2017-01-01')
mb=[]
with open(build.D+'bloc_matchs_footballdata.csv',encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r['buts_dom']=='' or r['buts_ext']=='': continue
        mb.append(((r['division'],r['saison']),r['date'],r['domicile'],r['exterieur'],int(r['buts_dom']),int(r['buts_ext']),r['id']))
Bq=parcourir5(mb,'0000')
D=pd.concat([G,Bq]); from search import MARCHES
for nom,f in MARCHES.items(): D[nom]=f(D.bd.values,D.be.values).astype(int)
Z=json.load(open('categories_zones.json'))['marches']; conv=lambda z:[(f,-np.inf if lo is None else lo,np.inf if hi is None else hi) for f,lo,hi in z['conditions']]
print('K=%d, %d matchs'%(K,len(D)))
for nom,M in Z.items():
    mk=np.zeros(len(D),bool)
    for z in M['intervalles']: mk|=masque(D,conv(z))
    n=int(mk.sum()); s=int(D[nom].values[mk].sum()); print('%-22s seuil %2d%% | mu sur %d matchs : %d/%d = %.1f%%'%(nom,round(100*M['seuil']),K,s,n,100*s/n if n else float('nan')))
