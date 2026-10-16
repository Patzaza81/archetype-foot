import pickle, gzip, glob, json, math, importlib.util, numpy as np
from collections import defaultdict
spec=importlib.util.spec_from_file_location("mv","moteur_v_test.py"); mv=importlib.util.module_from_spec(spec); spec.loader.exec_module(mv)
arch={}
for f in glob.glob("/home/claude/patzaza81/archetype-foot/data/archive_test/*.json.gz"): arch.update(json.load(gzip.open(f,"rt")))
# tous les matchs connus (dédoublonnés) : (date, dom, ext, bd, be)
M={}
for e in arch.values():
    for t,dom in (("equipe_dom",True),("equipe_ext",False)):
        q=e[t]
        for m in q.get("matchs") or []:
            if not (isinstance(m.get("buts_marques"),int) and isinstance(m.get("buts_encaisses"),int)): continue
            h,a=(q["nom"],m["adversaire"]) if m["domicile"] else (m["adversaire"],q["nom"])
            g=(m["buts_marques"],m["buts_encaisses"]) if m["domicile"] else (m["buts_encaisses"],m["buts_marques"])
            M[(m["date"],h,a)]=g
L=sorted((d,h,a,g[0],g[1]) for (d,h,a),g in M.items())
print("matchs distincts:",len(L),"équipes:",len({x[1] for x in L}|{x[2] for x in L}))
PRIOR=3.0
def ajuste(avant, it=60):
    ms=[x for x in L if x[0]<avant]
    if not ms: return {},{},1.0,1.0
    mu=sum(x[3]+x[4] for x in ms)/(2*len(ms)); gam=1.2
    att=defaultdict(lambda:1.0); dfn=defaultdict(lambda:1.0)
    for _ in range(it):
        na=defaultdict(float); da=defaultdict(float); nd=defaultdict(float); dd=defaultdict(float)
        for d,h,a,gh,ga in ms:
            na[h]+=gh; da[h]+=mu*gam*dfn[a]; na[a]+=ga; da[a]+=mu*dfn[h]
            nd[a]+=gh; dd[a]+=mu*gam*att[h]; nd[h]+=ga; dd[h]+=mu*att[a]
        att=defaultdict(lambda:1.0,{t:(na[t]+PRIOR)/(da[t]+PRIOR) for t in na})
        dfn=defaultdict(lambda:1.0,{t:(nd[t]+PRIOR)/(dd[t]+PRIOR) for t in nd})
        gam=sum(x[3] for x in ms)/max(1e-9,sum(mu*att[x[1]]*dfn[x[2]] for x in ms))
    return att,dfn,mu,gam
def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def proba(pred,lh,la,N=10):
    ph=[pois(lh,k) for k in range(N+1)]; pa=[pois(la,k) for k in range(N+1)]
    return sum(ph[i]*pa[j] for i in range(N+1) for j in range(N+1) if pred(i,j))
if __name__=="__main__":
    rows=[r for r in pickle.load(open("rows2.pkl","rb")) if r["cote"]>1.01]
    fits={}; feat=[]; ok=[]
    for r in rows:
        e=arch[r["match"]]; d=e["date"]
        if d not in fits: fits[d]=ajuste(d)
        att,dfn,mu,gam=fits[d]; h,a=e["domicile"],e["exterieur"]
        if h not in att or a not in att: continue
        lh=mu*gam*att[h]*dfn[a]; la=mu*att[a]*dfn[h]
        md=mv.market_def(r["marche"])
        if md is None: continue
        ok.append(r); feat.append(proba(md[0],lh,la))
    print("lignes avec forces connues:",len(ok),"sur",len(rows))
    cl=lambda p: np.clip(p,1e-3,1-1e-3); lg=lambda p: np.log(cl(p)/(1-cl(p)))
    y=np.array([r["gagne"] for r in ok]); q=np.array([1/r["cote"] for r in ok]); pp=np.array(feat); fin=np.array([r["final"] for r in ok])
    ms=sorted({r["match"] for r in ok}); rng=np.random.default_rng(3); fo={m:i%5 for i,m in enumerate(rng.permutation(ms))}; f=np.array([fo[r["match"]] for r in ok])
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
    one=np.ones(len(y)); Lq=lg(q); Lp=lg(pp)
    print("cote brute %.4f | proba Poisson force-adversaires seule %.4f | pourcentage v brut %.4f"%(ll(q),ll(pp),ll(fin)))
    for nom,x in {"cote recalibrée":np.c_[one,Lq],"cote + force adversaires":np.c_[one,Lq,Lp],"cote + force + pct v":np.c_[one,Lq,Lp,lg(fin)]}.items(): print(f"{nom:<28}{ll(cv(x)):.4f}")
    w=fit(np.c_[one,Lq,Lp],y); print("coefs (const, cote, force):",np.round(w,2))
    mm=np.array([r["match"] for r in ok]); um=np.unique(mm); ix={m:np.where(mm==m)[0] for m in um}; ws=[]
    for _ in range(200):
        s=np.concatenate([ix[m] for m in rng.choice(um,len(um))]); ws.append(fit(np.c_[one,Lq,Lp][s],y[s])[2])
    print("coef force adversaires IC95:",np.round(np.percentile(ws,[2.5,50,97.5]),2))
    pickle.dump((ok,feat),open("force_feat.pkl","wb"))
