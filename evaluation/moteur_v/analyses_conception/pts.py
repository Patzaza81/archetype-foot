import pickle, gzip, glob, numpy as np
rows = pickle.load(open("rows2.pkl","rb"))
arch={}
for f in glob.glob("/home/claude/patzaza81/archetype-foot/data/archive_test/*.json.gz"):
    arch.update(gzip.open(f,"rt") and __import__("json").load(gzip.open(f,"rt")))
def ppm(eq, d):
    ms=[m for m in eq.get("matchs",[]) if m["date"]<d and m.get("buts_marques") is not None]
    if len(ms)<3: return None
    pts=sum(3 if m["buts_marques"]>m["buts_encaisses"] else 1 if m["buts_marques"]==m["buts_encaisses"] else 0 for m in ms)
    return pts/len(ms), len(ms)
cache={}
def pp(mid):
    if mid not in cache:
        e=arch[mid]; cache[mid]=(ppm(e["equipe_dom"],e["date"]),ppm(e["equipe_ext"],e["date"]))
    return cache[mid]
S={"1X2 - 1":1,"1X2 - 2":-1,"Double chance - 1X":1,"Double chance - X2":-1}
R=[r for r in rows if r["marche"] in S and 1.01<r["cote"]]
X=[]
for r in R:
    h,a=pp(r["match"])
    if h is None or a is None: continue
    X.append((r,S[r["marche"]]*(h[0]-a[0])/3))   # écart de points par match, normalisé sur 3, orienté vers le côté du pari
print(len(X),"lignes", len({r['match'] for r,_ in X}),"matchs")
cl=lambda p: np.clip(p,1e-3,1-1e-3); lg=lambda p: np.log(cl(p)/(1-cl(p)))
y=np.array([r["gagne"] for r,_ in X]); q=np.array([1/r["cote"] for r,_ in X]); d=np.array([v for _,v in X])
ms=sorted({r["match"] for r,_ in X}); rng=np.random.default_rng(1); fo={m:i%5 for i,m in enumerate(rng.permutation(ms))}
f=np.array([fo[r["match"]] for r,_ in X])
def fit(x,y):
    w=np.zeros(x.shape[1])
    for _ in range(60):
        p=1/(1+np.exp(-x@w)); g=x.T@(y-p)-1e-2*w; H=(x.T*(p*(1-p)))@x+1e-2*np.eye(len(w)); w+=np.linalg.solve(H,g)
    return w
def cv(x):
    p=np.zeros(len(y))
    for k in range(5):
        t=f!=k; w=fit(x[t],y[t]); p[~t]=1/(1+np.exp(-x[~t]@w))
    return p
ll=lambda p: -np.mean(y*np.log(cl(p))+(1-y)*np.log(1-cl(p)))
one=np.ones(len(y)); L=lg(q)
print("cote brute %.4f | cote recalibrée %.4f | + écart de points %.4f"%(ll(q),ll(cv(np.c_[one,L])),ll(cv(np.c_[one,L,d]))))
mm=np.array([r["match"] for r,_ in X]); um=np.unique(mm); ix={m:np.where(mm==m)[0] for m in um}; ws=[]
for _ in range(300):
    s=np.concatenate([ix[m] for m in rng.choice(um,len(um))]); ws.append(fit(np.c_[one,L,d][s],y[s])[2])
print("coef écart de points, IC95:",np.round(np.percentile(ws,[2.5,50,97.5]),2))
# calibration par tranche d'écart de points (réel vs 1/cote)
print("\nécart de pts/match (côté parié) | lignes | réel | 1/cote | écart")
for a,b in [(-1,-.3),(-.3,-.1),(-.1,.1),(.1,.3),(.3,1)]:
    s=(d>=a)&(d<b)
    if s.sum()>30: print(f"  {a:+.1f}..{b:+.1f}  {s.sum():>5}  {y[s].mean():.1%}  {q[s].mean():.1%}  {y[s].mean()-q[s].mean():+.1%}")
