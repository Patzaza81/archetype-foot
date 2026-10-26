import sys,json,math,collections,numpy as np
sys.path.insert(0,'/home/claude/archetype-foot')
from sklearn.linear_model import LogisticRegression
from alpha_serie import robustesse as RB
exec(open('coh.py').read().split("A=[r for r")[0].split("R=json.load")[0])  # imports only
R=json.load(open('scen.json'));F0=json.load(open('rep1x2_feat.json'));fx={r['id']:r for r in F0}
mean=lambda l:sum(l)/len(l);sd=lambda l:(sum((x-mean(l))**2 for x in l)/len(l))**.5
for r in R:
    f=fx[r['id']];r.update({k:f[k] for k in ('ph','pe','wh','lh','dh','wa','la','dd')})
    r['dh_gap']=r['gfh']-r['gah'];r['da_gap']=r['gfa']-r['gaa'];r['D']=r['dh_gap']-r['da_gap'];r['sup']=r['xh']-r['xa'];r['tot']=r['xh']+r['xa']
    r['y']={'H':0,'N':1,'A':2}[r['res']]
FE=['sup','D']   # seuls points à poids non nul (étude précédente)
# cotes
cot={}
for m in RB.charger_bloc():
    ps=(m['cotes_fd'].get('1x2_cloture') or {}).get('ps')
    if ps and len(ps)==3 and all(isinstance(x,(int,float)) and x>1 for x in ps): cot[m['id']]=('PIN',ps[0],ps[2])
for m in RB.charger_archive_archetype():
    c=(m.get('cotes') or {}).get('1x2')
    if c and all(isinstance(c.get(k),(int,float)) and c[k]>1 for k in('1','2')): cot[m['id']]=('BP',c['1'],c['2'])
for r in R:
    c=cot.get(r['id']); r['src'],r['c1'],r['c2']=(c if c else (None,None,None))
A=[r for r in R if r['jour']<'2026-01-01'];B=[r for r in R if '2026-01-01'<=r['jour']<'2026-04-01'];C=[r for r in R if r['jour']>='2026-04-01']
X=lambda S:np.array([[r[k] for k in FE] for r in S]);Y=lambda S:np.array([r['y'] for r in S])
mu,sg=X(A).mean(0),X(A).std(0);Z=lambda S:(X(S)-mu)/sg
mA=LogisticRegression(max_iter=3000).fit(Z(A),Y(A));mAB=LogisticRegression(max_iter=3000).fit(Z(A+B),Y(A+B))
for r,p in zip(B,mA.predict_proba(Z(B))): r['p']=p
for r,p in zip(A,mA.predict_proba(Z(A))): r['p']=p
for r,p in zip(C,mAB.predict_proba(Z(C))): r['p']=p
print('A',len(A),'B',len(B),'C',len(C))
print('cotes PIN: A %d B %d C %d | BP (ARCH): %d'%tuple([sum(r['src']=='PIN' for r in S) for S in(A,B,C)]+[sum(r['src']=='BP' for r in R)]))
ARCH=[r for r in C if r['id'].startswith('archetype|')]
print('C dont archive:',len(ARCH),'avec cote BP:',sum(r['src']=='BP' for r in ARCH),'jours',len({r['jour'] for r in ARCH}))
import pickle;pickle.dump((A,B,C),open('odds_sets.pkl','wb'))
