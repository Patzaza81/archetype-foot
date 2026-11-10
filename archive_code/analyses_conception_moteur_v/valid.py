import pickle, numpy as np
from collections import defaultdict
rows = pickle.load(open("rows2.pkl","rb"))
dates = sorted({r["date"] for r in rows})
# coupure chronologique par nombre de matchs (moitié/moitié)
cnt = defaultdict(set)
for r in rows: cnt[r["date"]].add(r["match"])
tot = sum(len(v) for v in cnt.values()); acc=0; cut=None
for d in dates:
    acc += len(cnt[d])
    if acc >= tot/2: cut = d; break
A = [r for r in rows if r["date"] <= cut]; B = [r for r in rows if r["date"] > cut]
print("coupure", cut, "| A:", len({r['match'] for r in A}), "matchs", len(A), "lignes | B:", len({r['match'] for r in B}), "matchs", len(B), "lignes")
lg = lambda p: np.log(np.clip(p,1e-4,1-1e-4)/(1-np.clip(p,1e-4,1-1e-4)))
def X(R): return np.array([[1, lg(1/r["cote"]), lg(min(max(r["final"],.01),.99))] for r in R])
def fit(R):
    x = X(R); y = np.array([r["gagne"] for r in R]); w = np.zeros(3)
    for _ in range(50):
        p = 1/(1+np.exp(-x@w)); g = x.T@(y-p)-1e-3*w; H = (x.T*(p*(1-p)))@x+1e-3*np.eye(3); w += np.linalg.solve(H,g)
    return w
def ll(R,p):
    y=np.array([r["gagne"] for r in R]); p=np.clip(p,1e-4,1-1e-4); return -np.mean(y*np.log(p)+(1-y)*np.log(1-p))
for nom,(T,V) in {"A→B":(A,B),"B→A":(B,A)}.items():
    w = fit(T); pv = 1/(1+np.exp(-X(V)@w))
    print(f"\n[{nom}] coeffs (const, cote, final) = {np.round(w,2)}")
    print("  log-loss test : cote seule %.4f | pourcentage v brut %.4f | calibré %.4f" % (
        ll(V,np.array([1/r['cote'] for r in V])), ll(V,np.array([r['final'] for r in V])), ll(V,pv)))
    # pari si p calibré - 1/cote >= m
    for m in (0.0,0.03,0.05,0.08):
        pick=[(r,p) for r,p in zip(V,pv) if p-1/r["cote"]>=m and r["cote"]>=1.26]
        # un pari par match : meilleur écart
        best={}
        for r,p in pick:
            e=p-1/r["cote"]
            if r["match"] not in best or e>best[r["match"]][0]: best[r["match"]]=(e,r)
        bets=[b[1] for b in best.values()]
        if bets:
            roi=np.mean([b["gagne"]*b["cote"]-1 for b in bets]); hit=np.mean([b["gagne"] for b in bets]); imp=np.mean([1/b["cote"] for b in bets])
            print(f"  marge>={m:.0%}: {len(bets)} paris, réussite {hit:.1%} vs cote→ {imp:.1%}, ROI {roi:+.1%}")
        else: print(f"  marge>={m:.0%}: 0 pari")
# règles simples issues du diagnostic, évaluées sur A et B séparément
def bets(R,f):
    best={}
    for r in R:
        if f(r) and (r["match"] not in best or r["final"]>best[r["match"]]["final"]): best[r["match"]]=r
    return list(best.values())
def line(nom,f):
    out=[]
    for lab,R in (("A",A),("B",B)):
        b=bets(R,f)
        if len(b)<15: out.append(f"{lab}: {len(b)} paris"); continue
        out.append(f"{lab}: {len(b)} paris, réussite {np.mean([x['gagne'] for x in b]):.0%}/cote→ {np.mean([1/x['cote'] for x in b]):.0%}, ROI {np.mean([x['gagne']*x['cote']-1 for x in b]):+.1%}")
    print(f"{nom:<44}"+" | ".join(out))
print("\nRÈGLES SIMPLES (A = première moitié, B = seconde moitié)")
base=lambda r: r["final"]>=r["seuil"] and r["cote"]>=1.26
line("moteur actuel (seuils du client)", base)
line("+ cote <= 1.50", lambda r: base(r) and r["cote"]<=1.5)
line("+ cote 1.26-1.37 seulement", lambda r: base(r) and r["cote"]<=1.37)
line("+ hors Handicap/Double chance/1X2", lambda r: base(r) and r["fam"] not in {"Handicap","Double chance","1X2"})
line("+ final <= 85 %", lambda r: base(r) and r["final"]<=.85)
line("+ écart côtés >= 0.2", lambda r: base(r) and r["ecart"]>=.2)
line("+ n_min >= 6", lambda r: base(r) and r["n_min"]>=6)
line("cote<=1.5 et hors Handicap/DC/1X2", lambda r: base(r) and r["cote"]<=1.5 and r["fam"] not in {"Handicap","Double chance","1X2"})
