import importlib.util, json, numpy as np, pickle
exec(open("etage2.py").read().split("print(\"lignes\",len(R))")[0])   # recharge R (lignes avec pc, ps)
ids=json.load(open("jeu_reglage_ids.json")); D="/home/claude/patzaza81/archetype-foot/data/archive_test"
# (b) cotes réellement parieés par le moteur complet
for t in (.72,.76):
    r=c.rejouer(D,ids,t,True,True,True,True); cs=sorted(x["cote"] for x in r)
    print(f"seuil {t}: {len(r)} paris, cotes min {cs[0]} médiane {cs[len(cs)//2]} max {cs[-1]}; >1.30: {sum(x>1.30 for x in cs)}; hit {np.mean([x['gagne'] for x in r]):.1%}; wilson {c.mv.wilson(sum(x['gagne'] for x in r),len(r))}")
# (a) ps apporte-t-il quelque chose en plus de la cote ?
cl=lambda p: np.clip(p,1e-3,1-1e-3); lg=lambda p: np.log(cl(p)/(1-cl(p)))
y=np.array([r["gagne"] for r in R]); q=np.array([1/r["cote"] for r in R]); ps=np.array([r["ps"] for r in R]); pc=np.array([r["pc"] for r in R])
ms=sorted({r["match"] for r in R}); rng=np.random.default_rng(3); fo={m:i%5 for i,m in enumerate(rng.permutation(ms))}; f=np.array([fo[r["match"]] for r in R])
def fit(x,y):
    w=np.zeros(x.shape[1])
    for _ in range(60):
        p=1/(1+np.exp(-x@w)); w+=np.linalg.solve((x.T*(p*(1-p)))@x+1e-2*np.eye(len(w)),x.T@(y-p)-1e-2*w)
    return w
def cv(x):
    p=np.zeros(len(y))
    for k in range(5):
        t=f!=k; w=fit(x[t],y[t]); p[~t]=1/(1+np.exp(-x[~t]@w))
    return p
ll=lambda p: -np.mean(y*np.log(cl(p))+(1-y)*np.log(1-cl(p)))
one=np.ones(len(y)); Lq=lg(q)
print("log-loss cote %.4f | cote+calcul simple %.4f | cote+force %.4f | cote+force+simple %.4f"%(ll(cv(np.c_[one,Lq])),ll(cv(np.c_[one,Lq,lg(ps)])),ll(cv(np.c_[one,Lq,lg(pc)])),ll(cv(np.c_[one,Lq,lg(pc),lg(ps)]))))
mm=np.array([r["match"] for r in R]); um=np.unique(mm); ix={m:np.where(mm==m)[0] for m in um}; ws=[]
for _ in range(200):
    s=np.concatenate([ix[m] for m in rng.choice(um,len(um))]); ws.append(fit(np.c_[one,Lq,lg(ps)][s],y[s])[2])
print("coef calcul simple, IC95:",np.round(np.percentile(ws,[2.5,50,97.5]),2))
# bande 1.45-1.85 : coefficient du calcul simple dans la bande seulement
b=[i for i,r in enumerate(R) if 1.45<=r["cote"]<=1.85]; yb=y[b]; xb=np.c_[one[b],Lq[b],lg(ps)[b]]
mb=mm[b]; ub=np.unique(mb); ixb={m:np.where(mb==m)[0] for m in ub}; wb=[]
for _ in range(300):
    s=np.concatenate([ixb[m] for m in rng.choice(ub,len(ub))]); wb.append(fit(xb[s],yb[s])[2])
print("bande 1.45-1.85 : coef calcul simple IC95:",np.round(np.percentile(wb,[2.5,50,97.5]),2),"lignes",len(b))
# (c) test de permutation de la règle étage 2 (ps>=75, bande 1.45-1.85, un pari par match) : ROI observé vs hasard
def regle(rows):
    best={}
    for r in rows:
        if 1.45<=r["cote"]<=1.85 and r["ps"]>=.75 and (r["match"] not in best or r["ps"]>best[r["match"]]["ps"]): best[r["match"]]=r
    return list(best.values())
b0=regle(R); roi0=np.mean([(x["cote"]-1) if x["gagne"] else -1 for x in b0]); print("règle: n",len(b0),"ROI",round(roi0,3))
# hasard : même nombre de paris tirés au hasard dans la bande de cotes (1 par match)
band={}
for r in R:
    if 1.45<=r["cote"]<=1.85: band.setdefault(r["match"],[]).append(r)
keys=list(band); sims=[]
for _ in range(2000):
    ch=[band[k][rng.integers(len(band[k]))] for k in rng.choice(len(keys),len(b0),replace=False) for k in [keys[k]]]
    sims.append(np.mean([(x["cote"]-1) if x["gagne"] else -1 for x in ch]))
print("hasard dans la bande: ROI moyen %.3f, p(hasard >= règle) = %.3f"%(np.mean(sims),np.mean(np.array(sims)>=roi0)))
# nombre de combinaisons essayées pour correction de comparaisons multiples
print("combinaisons testées étage 2: 3 x 4 = 12")
