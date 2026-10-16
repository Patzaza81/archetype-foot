import importlib.util, json, collections
s=importlib.util.spec_from_file_location("c","moteur_v_calibre.py"); c=importlib.util.module_from_spec(s); s.loader.exec_module(c); mv=c.mv
D="/home/claude/patzaza81/archetype-foot/data/archive_test"; ids=json.load(open("jeu_reglage_ids.json")); vus=mv.charger(D); frc=c.Forces(vus)
res=collections.defaultdict(list)
for mid in ids:
    e=vus.get(mid)
    if not e: continue
    sc=mv.score_reel(e); cotes=e.get("cotes_observees") or {}
    if sc is None or not cotes: continue
    rh=mv.lignes(e["equipe_dom"],True,e["date"]); ra=mv.lignes(e["equipe_ext"],False,e["date"]); n,cd=mv.analyse(rh,ra,cotes)
    if cd is None: continue
    b=c.choisir_modele(cd,frc.lambdas(e),c.lambdas_simples(rh[-12:],ra[-12:]))
    if b: res[b["niveau"]].append(bool(b["pred"](*sc)) )
for k,v in res.items(): print(k, len(v),"paris, réussite %.1f%%"%(100*sum(v)/len(v)))
