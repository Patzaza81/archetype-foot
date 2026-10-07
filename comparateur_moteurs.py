from __future__ import annotations
import datetime as dt, json
from pathlib import Path
from typing import Any
V2="moteur_v2_6_10"; V3="moteur_v3"
V2_FILE=Path("precalcul_leger.json"); V3_FILE=Path("data/v3/pronostics_v3.json"); JOURNAL=Path("journal.json"); OUT=Path("data/comparaison_moteurs.json")
def load(p:Path)->dict[str,Any]:
    if not p.exists() or not p.stat().st_size:return {}
    x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
def key(m):
    mid=str(m.get("match_id") or "").strip()
    return "id:"+mid if mid else "match:{d}|{h}|{a}|{b}".format(d=str(m.get("date") or "").strip(),h=str(m.get("heure_cameroun") or m.get("heure") or "").strip(),a=str(m.get("domicile") or "").strip().lower(),b=str(m.get("exterieur") or "").strip().lower())
def sels(b):
    return ((b or {}).get("selection") or {}) if isinstance(b,dict) else {}
def market(c):
    for k in ("marche","market","market_id","libelle"):
        if isinstance(c,dict) and c.get(k) not in (None,""): return str(c[k])
    return ""
def summary(rows,engine):
    counts={}; matches=choices=0
    for m in rows:
        s=sels(m.get(engine))
        if s: matches+=1
        for c in s.values():
            choices+=1; q=market(c)
            if q: counts[q]=counts.get(q,0)+1
    return {"matchs_avec_selection":matches,"choix":choices,"marches":dict(sorted(counts.items(),key=lambda x:(-x[1],x[0])))}
def compare(v2,v3):
    a={key(x):x for x in v2}; b={key(x):x for x in v3}; common=sorted(set(a)&set(b)); agree=div=0; agreements=[]; divergences=[]
    for k in common:
        s2=sels(a[k].get(V2)); s3=sels(b[k].get(V3))
        m2={market(x) for x in s2.values() if isinstance(x,dict)}-{""}
        m3={market(x) for x in s3.values() if isinstance(x,dict)}-{""}
        overlap=sorted(m2&m3)
        if overlap: agree+=1; agreements.append({"match_id":k,"marches_communs":overlap})
        elif s2 or s3: div+=1; divergences.append({"match_id":k,"v2":sorted(m2),"v3":sorted(m3)})
    return {"matchs_communs":len(common),"matchs_v2_seulement":len(set(a)-set(b)),"matchs_v3_seulement":len(set(b)-set(a)),"accord_marche":agree,"divergence_marche":div,"taux_accord_sur_matchs_communs":round(agree/len(common),4) if common else None,"accords":agreements[:100],"divergences":divergences[:100]}
def main():
    a=load(V2_FILE); b=load(V3_FILE); v2=[x for x in a.get("signaux",[]) if isinstance(x,dict)]; v3=[x for x in b.get("signaux",[]) if isinstance(x,dict)]; j=load(JOURNAL)
    result={"genere_le":dt.datetime.now(dt.timezone.utc).isoformat(),"statut":"PRODUCTION_PARALLELE","moteur_actif":V2,"moteur_candidat":V3,"regle_promotion":"Aucune promotion automatique : la V3 doit démontrer un avantage réel sur des données hors échantillon.","v2":summary(v2,V2),"v3":summary(v3,V3),"comparaison":compare(v2,v3),"journal":{"disponible":bool(j),"moteurs":j.get("moteurs",{}),"pronostics":{k:{"selections":len((j.get("pronostics",{}).get(k,{}) or {}).get("selections",[]))} for k in (V2,V3) if k in (j.get("pronostics",{}) or {})}},"calibration_v3":b.get("calibration") or {}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"v2_choix":result["v2"]["choix"],"v3_choix":result["v3"]["choix"],"accord":result["comparaison"]["accord_marche"],"divergence":result["comparaison"]["divergence_marche"]},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
