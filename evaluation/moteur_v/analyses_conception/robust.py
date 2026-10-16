import pickle, numpy as np
rows=[r for r in pickle.load(open("rows2.pkl","rb")) if r["cote"]>1.01]
cut="2026-10-10"
A=[r for r in rows if r["date"]<=cut]; B=[r for r in rows if r["date"]>cut]
cl=lambda p: np.clip(p,1e-3,1-1e-3); lg=lambda p: np.log(cl(p)/(1-cl(p)))
def fit(R):
    x=np.c_[np.ones(len(R)),lg(np.array([1/r["cote"] for r in R]))]; y=np.array([r["gagne"] for r in R]); w=np.zeros(2)
    for _ in range(50):
        p=1/(1+np.exp(-x@w)); w+=np.linalg.solve((x.T*(p*(1-p)))@x+1e-3*np.eye(2),x.T@(y-p)-1e-3*w)
    return w
def pcal(R,w): return 1/(1+np.exp(-(w[0]+w[1]*lg(np.array([1/r["cote"] for r in R])))))
def wil(k,n,z=1.96):
    if n==0: return 0
    p=k/n; return (p+z*z/2/n-z*np.sqrt(p*(1-p)/n+z*z/4/n/n))/(1+z*z/n)
def ece(p,y,bins=(0,.5,.6,.7,.8,1.01)):
    e=0
    for a,b in zip(bins[:-1],bins[1:]):
        s=(p>=a)&(p<b)
        if s.sum(): e+=s.sum()*abs(p[s].mean()-y[s].mean())
    return e/len(p)
for nom,(T,V) in {"A→B":(A,B),"B→A":(B,A)}.items():
    w=fit(T); y=np.array([r["gagne"] for r in V]); pv=np.array([r["final"] for r in V]); pc=pcal(V,w)
    s=pv>=.6
    print(f"\n[{nom}] erreur de calibration (écart annoncé/réel, lignes annoncées ≥60 %):  v brut {ece(pv[s],y[s]):.1%}  |  v calibré sur cote {ece(pc[pc>=.6],y[pc>=.6]):.1%}")
    print("  pourcentage CALIBRÉ : seuil | paris(1/match) | annoncé | réel | borne basse 95 %")
    for t in (.6,.65,.7,.75,.8):
        best={}
        for r,p in zip(V,pc):
            if p>=t and (r["match"] not in best or p>best[r["match"]][0]): best[r["match"]]=(p,r)
        if len(best)<10: print(f"   ≥{t:.0%}: {len(best)} paris"); continue
        ps=np.array([b[0] for b in best.values()]); g=np.array([b[1]["gagne"] for b in best.values()])
        print(f"   ≥{t:.0%}: {len(g):>4} paris | {ps.mean():.1%} | {g.mean():.1%} | {wil(g.sum(),len(g)):.1%}")
