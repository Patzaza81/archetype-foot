import json,math,collections,numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
R=json.load(open('scen.json'));F0=json.load(open('rep1x2_feat.json'))
fx={r['id']:r for r in F0}
mean=lambda l:sum(l)/len(l);sd=lambda l:(sum((x-mean(l))**2 for x in l)/len(l))**.5
for r in R:
    f=fx[r['id']];r.update({k:f[k] for k in ('ph','pe','wh','lh','dh','wa','la','dd')})
    r['dh_gap']=r['gfh']-r['gah'];r['da_gap']=r['gfa']-r['gaa'];r['D']=r['dh_gap']-r['da_gap']
    r['sup']=r['xh']-r['xa']                        # supériorité offensive attendue (buts)
    r['tot']=r['xh']+r['xa']
    dgh=[a-c for a,c in zip(r['hm'],r['hc'])];dga=[a-c for a,c in zip(r['am'],r['ac'])]
    r['reg_h']=sd(dgh);r['reg_a']=sd(dga)            # irrégularité (écart-type de la différence de buts)
    r['nul_h']=r['dh'];r['nul_a']=sum(a==c for a,c in zip(r['am'],r['ac']))/len(r['am'])
    r['y']={'H':0,'N':1,'A':2}[r['res']]
FE=[('sup','Supériorité offensive (buts attendus dom − ext)'),('gah','Solidité défensive du domicile (buts encaissés)'),('gaa','Solidité défensive de l\'extérieur (buts encaissés)'),
    ('D','Écart de niveau D'),('ph','Paires favorables au domicile'),('pe','Paires favorables à l\'extérieur'),('reg_h','Irrégularité du domicile'),('reg_a','Irrégularité de l\'extérieur'),
    ('nul_h','Nuls du domicile à domicile'),('nul_a','Nuls de l\'extérieur à l\'extérieur'),('tot','Total de buts attendu')]
A=[r for r in R if r['jour']<'2026-01-01'];B=[r for r in R if '2026-01-01'<=r['jour']<'2026-04-01'];C=[r for r in R if r['jour']>='2026-04-01']
X=lambda S:np.array([[r[k] for k,_ in FE] for r in S]);Y=lambda S:np.array([r['y'] for r in S])
mu,sg=X(A).mean(0),X(A).std(0)
Z=lambda S:(X(S)-mu)/sg
print('Matchs : A(2025) %d | B(janv–mars 2026) %d | C réservée (depuis 01/04/2026) %d'%(len(A),len(B),len(C)))
print('\n== 1. Ce que les victoires ont en commun (moyennes par issue, tous matchs)')
g=collections.defaultdict(list)
for r in R: g[r['res']].append(r)
print('  %-52s %9s %9s %9s'%('caractéristique','vic.dom','nul','vic.ext'))
for k,l in FE: print('  %-52s %9.2f %9.2f %9.2f'%(l,mean([r[k] for r in g['H']]),mean([r[k] for r in g['N']]),mean([r[k] for r in g['A']])))
for C_ in (1e-1,1.0):
    m=LogisticRegression(max_iter=3000,C=C_).fit(Z(A),Y(A))
    print('\n  C=%.1f log-loss B %.4f | C réservée %.4f | (hasard 3 classes %.4f ; fréquences seules %.4f)'%(C_,log_loss(Y(B),m.predict_proba(Z(B)),labels=[0,1,2]),log_loss(Y(C),m.predict_proba(Z(C)),labels=[0,1,2]),math.log(3),log_loss(Y(C),np.tile(np.bincount(Y(A))/len(A),(len(C),1)))))
m=LogisticRegression(max_iter=3000,C=1.0).fit(Z(A+B),Y(A+B))
print('\n== 2. Poids des points de cohérence (régression apprise sur 2025–mars 2026, variables centrées-réduites)')
print('  %-52s %12s %12s'%('point','pour vic.dom','pour vic.ext'))
for i,(k,l) in enumerate(FE): print('  %-52s %+12.2f %+12.2f'%(l,m.coef_[0][i]-m.coef_[1][i]*0,m.coef_[2][i]))
P=m.predict_proba(Z(C));days=len({r['jour'] for r in C})
print('\n== 3. Échelle : probabilité annoncée par le modèle → réussite réelle sur la période RÉSERVÉE (%d jours)'%days)
for cl,nm,idx in ((0,'VICTOIRE DOMICILE',0),(2,'VICTOIRE EXTÉRIEUR',2)):
    print(' ',nm)
    p=P[:,idx];y=np.array([r['y']==cl for r in C])
    for lo,hi in ((0.70,1),(0.65,0.70),(0.60,0.65),(0.55,0.60),(0.50,0.55),(0.45,0.50)):
        mk=(p>=lo)&(p<hi)
        if mk.sum()<15: continue
        print('    annoncé %d–%d%% : n=%4d | réel %.1f%% | %.2f/jour'%(100*lo,100*hi,mk.sum(),100*y[mk].mean(),mk.sum()/days))
    for lo in (0.70,0.65,0.60):
        mk=p>=lo
        if mk.sum(): print('    cumulé >= %d%% : n=%4d | réel %.1f%% | %.2f/jour'%(100*lo,mk.sum(),100*y[mk].mean(),mk.sum()/days))
json.dump({'coef':m.coef_.tolist(),'mu':(mu).tolist(),'sg':sg.tolist()},open('coh_model.json','w'))

print('\n== 4. Risque de nul : probabilité de nul annoncée → nuls réels (période réservée)')
pn=P[:,1];yn=np.array([r['y']==1 for r in C]);q=np.quantile(pn,[0,.2,.4,.6,.8,1])
for lo,hi in zip(q,q[1:]): 
    mk=(pn>=lo)&(pn<=hi);print('   annoncé %.1f–%.1f%% : n=%d | nuls réels %.1f%%'%(100*lo,100*hi,mk.sum(),100*yn[mk].mean()))
# victoire dom annoncée >=65% : le risque de nul change-t-il la réussite ?
p=P[:,0];y0=np.array([r['y']==0 for r in C]);mk=p>=0.65;med=np.median(pn[mk])
print('   dom >= 65%% : nul annoncé bas (<=%.1f%%) -> réel %.1f%% (n=%d) | nul annoncé haut -> réel %.1f%% (n=%d)'%(100*med,100*y0[mk&(pn<=med)].mean(),(mk&(pn<=med)).sum(),100*y0[mk&(pn>med)].mean(),(mk&(pn>med)).sum()))
