import pickle, numpy as np
from collections import defaultdict
rows = pickle.load(open("rows2.pkl","rb"))
rows = [r for r in rows if r["cote"]>1.01]
ms = sorted({r["match"] for r in rows}); rng=np.random.default_rng(3); fold={m:i%5 for i,m in enumerate(rng.permutation(ms))}
cl=lambda p: np.clip(p,1e-3,1-1e-3); lg=lambda p: np.log(cl(p)/(1-cl(p)))
y=np.array([r["gagne"] for r in rows]); q=np.array([1/r["cote"] for r in rows])
sH=np.array([r["sH"] for r in rows]); sA=np.array([r["sA"] for r in rows]); nd=np.array([r["n_dom"] for r in rows]); ne=np.array([r["n_ext"] for r in rows])
fin=np.array([r["final"] for r in rows]); F=np.array([r["fam"] for r in rows]); f_=np.array([fold[r["match"]] for r in rows])
fams=sorted(set(F))
def fit(x,y,lam=1e-2):
    w=np.zeros(x.shape[1])
    for _ in range(60):
        p=1/(1+np.exp(-x@w)); g=x.T@(y-p)-lam*w; H=(x.T*(p*(1-p)))@x+lam*np.eye(len(w)); w+=np.linalg.solve(H,g)
    return w
def cv(Xf):
    x=Xf; p=np.zeros(len(y))
    for k in range(5):
        tr=f_!=k; w=fit(x[tr],y[tr]); p[~tr]=1/(1+np.exp(-x[~tr]@w))
    return p
ll=lambda p: -np.mean(y*np.log(cl(p))+(1-y)*np.log(1-cl(p)))
one=np.ones(len(y)); L=lg(q)
res={}
res["cote brute (sans calibrage)"]=ll(q)
res["M0 cote recalibrée (pente+const)"]=ll(cv(np.c_[one,L]))
res["M1 + pourcentage v (final)"]=ll(cv(np.c_[one,L,lg(fin)]))
for m in (0,5,20,60):
    s=(sH*nd+sA*ne+m*q)/(nd+ne+m)
    res[f"M2 fréquence rétrécie vers la cote (m={m})"]=ll(cv(np.c_[one,L,lg(s)]))
D=np.c_[[F==f for f in fams]].T.astype(float)
res["M3 cote + famille"]=ll(cv(np.c_[one,L,D[:,1:]]))
res["M4 cote×famille (pente par famille)"]=ll(cv(np.c_[one,L,D[:,1:],D[:,1:]*L[:,None]]))
res["M5 cote + sH + sA séparés"]=ll(cv(np.c_[one,L,lg(sH),lg(sA)]))
for k,v in res.items(): print(f"{k:<46}{v:.4f}")
# diag: pente M0 sur tout
w=fit(np.c_[one,L],y); print("M0 pente/const:",np.round(w,2))
# M1 coefficient bootstrap par match
w1=[];mm=np.array([r["match"] for r in rows]); um=np.unique(mm); ix={m:np.where(mm==m)[0] for m in um}
for _ in range(200):
    s=np.concatenate([ix[m] for m in rng.choice(um,len(um))]); w1.append(fit(np.c_[one,L,lg(fin)][s],y[s])[2])
print("coef pourcentage v, IC95 bootstrap:",np.round(np.percentile(w1,[2.5,50,97.5]),2))
# calibration par famille de la cote seule (favori/outsider)
print("\nBiais de la cote par famille (réel - 1/cote, toutes lignes cote 1.26-3):")
for f in fams:
    s=(F==f)&(q>=1/3)&(q<=1/1.26)
    if s.sum()>200: print(f"  {f:<22}{s.sum():>6} lignes  réel {y[s].mean():.1%}  1/cote {q[s].mean():.1%}  écart {y[s].mean()-q[s].mean():+.1%}")
