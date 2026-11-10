import pickle, gzip, glob, json, numpy as np
from collections import defaultdict
arch={}
for f in glob.glob("/home/claude/patzaza81/archetype-foot/data/archive_test/*.json.gz"): arch.update(json.load(gzip.open(f,"rt")))
teams=defaultdict(dict)   # comp -> nom -> liste matchs
for e in arch.values():
    for t in ("equipe_dom","equipe_ext"):
        q=e[t]; 
        if q.get("matchs"): teams[e["competition"]][q["nom"]]=q["matchs"]
print("championnats:",len(teams),"| équipes connues par championnat (médiane):",int(np.median([len(v) for v in teams.values()])))
def table(comp,d):
    T=[]
    for n,ms in teams[comp].items():
        ms=[m for m in ms if m["date"]<d and isinstance(m.get("buts_marques"),int)]
        if len(ms)<3: continue
        pts=sum(3 if m["buts_marques"]>m["buts_encaisses"] else 1 if m["buts_marques"]==m["buts_encaisses"] else 0 for m in ms)
        gd=sum(m["buts_marques"]-m["buts_encaisses"] for m in ms)
        T.append((n,pts/len(ms),gd/len(ms)))
    T.sort(key=lambda t:(-t[1],-t[2])); return T
rows=pickle.load(open("rows2.pkl","rb"))
S={"1X2 - 1":1,"1X2 - 2":-1,"Double chance - 1X":1,"Double chance - X2":-1}
X=[];tc={}
for r in rows:
    if r["marche"] not in S or r["cote"]<=1.01: continue
    e=arch[r["match"]]; key=(e["competition"],e["date"])
    if key not in tc: tc[key]=table(*key)
    T=tc[key]; names=[t[0] for t in T]
    if len(T)<8 or e["domicile"] not in names or e["exterieur"] not in names: continue
    N=len(T); rh=names.index(e["domicile"]); ra=names.index(e["exterieur"]); ph=T[rh][1]; pa=T[ra][1]
    X.append((r, S[r["marche"]]*(ph-pa)/3, S[r["marche"]]*(ra-rh)/N))
print("lignes",len(X),"matchs",len({r['match'] for r,_,_ in X}))
cl=lambda p: np.clip(p,1e-3,1-1e-3); lg=lambda p: np.log(cl(p)/(1-cl(p)))
y=np.array([r["gagne"] for r,_,_ in X]); q=np.array([1/r["cote"] for r,_,_ in X]); dp=np.array([a for _,a,_ in X]); dr=np.array([b for _,_,b in X])
print("corrélation écart de points / écart de rang: %.2f"%np.corrcoef(dp,dr)[0,1])
ms=sorted({r["match"] for r,_,_ in X}); rng=np.random.default_rng(1); fo={m:i%5 for i,m in enumerate(rng.permutation(ms))}; f=np.array([fo[r["match"]] for r,_,_ in X])
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
one=np.ones(len(y)); L=lg(q)
for nom,x in {"cote":np.c_[one,L],"+ points":np.c_[one,L,dp],"+ rang":np.c_[one,L,dr],"+ points + rang":np.c_[one,L,dp,dr]}.items(): print(f"{nom:<18}{ll(cv(x)):.4f}")
print("\ntranche d'écart de RANG (côté parié, normalisé) : lignes | réel | 1/cote | écart")
for a,b in [(-1,-.4),(-.4,-.15),(-.15,.15),(.15,.4),(.4,1.01)]:
    s=(dr>=a)&(dr<b)
    if s.sum()>30: print(f"  {a:+.2f}..{b:+.2f} {s.sum():>5}  {y[s].mean():.1%}  {q[s].mean():.1%}  {y[s].mean()-q[s].mean():+.1%}")
