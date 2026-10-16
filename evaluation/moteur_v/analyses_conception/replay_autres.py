import importlib.util, json, collections, numpy as np
s=importlib.util.spec_from_file_location("c","moteur_v_calibre.py"); c=importlib.util.module_from_spec(s); s.loader.exec_module(c); mv=c.mv
D="/home/claude/patzaza81/archetype-foot/data/archive_test"; ids=json.load(open("jeu_reglage_ids.json")); vus=mv.charger(D); frc=c.Forces(vus)
P=collections.defaultdict(list); nA=[]; ex=None
for mid in ids:
    e=vus.get(mid)
    if not e: continue
    sc=mv.score_reel(e); cotes=e.get("cotes_observees") or {}
    if sc is None or not cotes: continue
    rh=mv.lignes(e["equipe_dom"],True,e["date"]); ra=mv.lignes(e["equipe_ext"],False,e["date"]); n,cd=mv.analyse(rh,ra,cotes)
    if cd is None: continue
    r=c.proposer(cd,frc.lambdas(e),c.lambdas_simples(rh[-12:],ra[-12:]))
    if not r: continue
    nA.append(len(r["autres"]))
    P[("principal",r["principal"]["niveau"])].append(bool(r["principal"]["pred"](*sc)))
    for d in r["autres"]: P[("autres",d["niveau"])].append(bool(d["pred"](*sc)))
    if ex is None and len(r["autres"])>=3 and r["principal"]["niveau"]=="RISQUÉ": ex=(e["domicile"],e["exterieur"],c.formater(r))
print("matchs",len(nA),"| autres par match: moyenne %.1f, aucun autre: %d matchs"%(np.mean(nA),sum(x==0 for x in nA)))
for k in sorted(P): v=P[k]; print(k,len(v),"réussite %.1f%%"%(100*np.mean(v)))
print("\nEXEMPLE :",ex[0],"-",ex[1]); print(ex[2])
