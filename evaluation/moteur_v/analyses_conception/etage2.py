import pickle, gzip, glob, json, math, importlib.util, numpy as np
spec=importlib.util.spec_from_file_location("c","moteur_v_calibre.py"); c=importlib.util.module_from_spec(spec); spec.loader.exec_module(c); mv=c.mv
arch={}
for f in glob.glob("/home/claude/patzaza81/archetype-foot/data/archive_test/*.json.gz"): arch.update(json.load(gzip.open(f,"rt")))
ok,feat=pickle.load(open("force_feat.pkl","rb"))
cache={}
def lam(mid):
    if mid not in cache:
        e=arch[mid]; d=e["date"]
        rh=mv.lignes(e["equipe_dom"],True,d)[-12:]; ra=mv.lignes(e["equipe_ext"],False,d)[-12:]
        if len(rh)<4 or len(ra)<4: cache[mid]=None
        else:
            sH=np.mean([x[0] for x in rh]); cH=np.mean([x[1] for x in rh]); sA=np.mean([x[0] for x in ra]); cA=np.mean([x[1] for x in ra])
            cache[mid]=((sH+cA)/2,(sA+cH)/2, sH-cH, sA-cA)   # lambda dom, lambda ext, solde dom, solde ext
    return cache[mid]
R=[]
for r,pf in zip(ok,feat):
    l=lam(r["match"])
    if l is None: continue
    md=mv.market_def(r["marche"])
    pc=c.p_cal2(r["cote"],pf); ps=c.proba_marche(md[0],max(l[0],.05),max(l[1],.05))
    R.append(dict(r,pc=pc,ps=ps,solde=l[2]-l[3]))
print("lignes",len(R))
cut="2026-10-10"
def un_par_match(rows):
    best={}
    for r in rows:
        if r["match"] not in best or r["pc"]>best[r["match"]]["pc"]: best[r["match"]]=r
    return list(best.values())
def st(b):
    if not b: return "—"
    n=len(b); w=sum(x["gagne"] for x in b); roi=sum((x["cote"]-1) if x["gagne"] else -1 for x in b)/n
    return f"{n:>3} paris, réussite {w/n:.1%} (borne basse {mv.wilson(w,n)[0]:.0%}), annoncé {np.mean([x['pc'] for x in b]):.1%}, ROI {roi:+.1%}"
for T1 in (.58,.65):
    S1=un_par_match([r for r in R if r["pc"]>=T1 and r["fam"]!="1X2" or (r["pc"]>=T1 and r["fam"]=="1X2")])
    S1=un_par_match([r for r in R if r["pc"]>=T1])
    print(f"\n=== ÉTAGE 1 : probabilité calibrée >= {T1:.0%} (cote jusqu'à ~{c.cote_max_pour_seuil(T1):.2f}) ===")
    print("  tout       :",st(S1)); print("  1ère moitié:",st([x for x in S1 if x["date"]<=cut])); print("  2e moitié  :",st([x for x in S1 if x["date"]>cut]))
    print(" ÉTAGE 2 : on garde le pari seulement si la probabilité du calcul simple (buts marqués/encaissés au même lieu) >= T2")
    for T2 in (.55,.60,.65,.70,.75):
        K=[x for x in S1 if x["ps"]>=T2]
        print(f"  T2={T2:.0%}: tout {st(K)}")
        print(f"          1ère moitié {st([x for x in K if x['date']<=cut])}  | 2e moitié {st([x for x in K if x['date']>cut])}")

print("\n\n######## COTES VISÉES 1,45-1,85 : un pari par match = celui dont le calcul simple (étage 2) est le plus fort ########")
def un_ps(rows):
    best={}
    for r in rows:
        if r["match"] not in best or r["ps"]>best[r["match"]]["ps"]: best[r["match"]]=r
    return list(best.values())
def st2(b):
    if len(b)<10: return f"{len(b)} paris"
    n=len(b); w=sum(x["gagne"] for x in b); roi=sum((x["cote"]-1) if x["gagne"] else -1 for x in b)/n
    return f"{n:>3} paris, réussite {w/n:.1%} vs seuil de rentabilité {np.mean([1/x['cote'] for x in b]):.1%}, ROI {roi:+.1%}"
band=[r for r in R if 1.45<=r["cote"]<=1.85]
for T1 in (.0,.50,.58):
    for T2 in (.0,.65,.75,.85):
        K=un_ps([r for r in band if r["pc"]>=T1 and r["ps"]>=T2])
        print(f"étage1 pc>={T1:.0%} | étage2 ps>={T2:.0%}: {st2(K)}  || 1ère moitié: {st2([x for x in K if x['date']<=cut])} || 2e: {st2([x for x in K if x['date']>cut])}")
