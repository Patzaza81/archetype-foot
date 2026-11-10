import numpy as np
exec(open("etage2.py").read().split("print(\"lignes\",len(R))")[0])
# pf = proba Poisson avec forces ajustées aux adversaires (force_feat.pkl), alignée sur 'ok' ; R est filtré (>=4 matchs) -> on la recolle
pf_by={(r["match"],r["marche"]):p for r,p in zip(ok,feat)}
for r in R: r["pf"]=pf_by[(r["match"],r["marche"])]; r["pm"]=(r["pf"]+r["ps"])/2   # modèle seul = moyenne force + calcul simple
cut="2026-10-10"
def choisir(rows,cle,seuil):
    best={}
    for r in rows:
        if r[cle]>=seuil and (r["match"] not in best or r[cle]>best[r["match"]][cle]): best[r["match"]]=r
    return list(best.values())
def st(b):
    if len(b)<8: return f"{len(b)} paris"
    n=len(b); w=sum(x["gagne"] for x in b)
    return f"{n:>3} paris | réussite {w/n:.1%} (borne basse {mv.wilson(w,n)[0]:.0%}) | modèle annonçait {np.mean([x['pm'] for x in b]):.1%} | seuil rentab. {np.mean([1/x['cote'] for x in b]):.1%} | ROI {sum((x['cote']-1) if x['gagne'] else -1 for x in b)/n:+.1%}"
bands=[(1.26,1.37),(1.37,1.49),(1.49,1.81),(1.81,2.5)]
for seuil in (.0,.70,.75,.80):
    S=choisir(R,"pm",seuil)
    print(f"\n=== MODÈLE SEUL (la cote ne sert pas à choisir), probabilité modèle >= {seuil:.0%} | {len(S)} matchs ===")
    for a,b in bands:
        B=[x for x in S if a<=x["cote"]<b]
        print(f"  cote {a}-{b}: {st(B)}")
    B=[x for x in S if 1.49<=x["cote"]<=1.81]
    print(f"  >> zone 1,49-1,81 : 1ère moitié {st([x for x in B if x['date']<=cut])} || 2e {st([x for x in B if x['date']>cut])}")
