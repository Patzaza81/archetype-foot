import json, glob, collections
from datetime import datetime
S="/tmp/claude-0/-home-claude/afbb0763-2a9f-5585-8d9a-c1e00b70e6af/scratchpad"
L=[json.loads(l) for l in open('/home/claude/archetype-foot/data/dc/journal.jsonl')]
ko=lambda x: datetime.fromisoformat(str(x).replace("Z","+00:00"))
fin={}
for l in L:
    if l['type']=='pronostic' and ko(l['gele_le'])<ko(l['fiche']['coup_d_envoi_utc']): fin[l['match_id']]=l
resu={l['match_id']:l for l in L if l['type']=='resultat'}
rej={}
for f in glob.glob(S+"/rejeu_*.json"): rej.update(json.load(open(f)))
bets=lambda f: ([f["principal"]] if f.get("principal") else [])+(f.get("autres") or [])
K=lambda b: tuple(b["cle"])
def sig(f):
    if not f or "erreur" in f: return None
    if f.get("statut")!="analyse": return ("statut",f.get("statut"))
    return (f["n_domicile"],f["n_exterieur"],f["buts_attendus"]["dom"],f["buts_attendus"]["ext"],f["modele"]["n_matchs_ligue"],tuple(f["p_marches"]))
rows=[]; manquants=[]
for mid,l in fin.items():
    fr=l["fiche"]
    if not bets(fr): continue
    base=dict(match_id=mid,jour=fr["jour"],comp=fr["competition"],dom=fr["domicile"],ext=fr["exterieur"],commit=l["commit"],gele_le=l["gele_le"],termine=mid in resu,
              paris_geles=[dict(cle=list(K(b)),marche=b["marche"],cote=b["cote"],p=b["p"],role="principal" if b is fr.get("principal") else "autre") for b in bets(fr)])
    if mid not in rej:
        base.update(classe="indéterminé",motif="match absent de l'archive actuelle : entrées non reconstituables"); rows.append(base); continue
    r=rej[mid]
    # version d'assemblage = celle où l'ancien chargeur reproduit la fiche gelée (effectifs, buts attendus, taille du championnat) ET les paris
    def reproduit(a):
        if not a or "erreur" in a or a.get("statut")!="analyse": return False
        return (a["n_domicile"],a["n_exterieur"],a["buts_attendus"]["dom"],a["buts_attendus"]["ext"],a["modele"]["n_matchs_ligue"])==(fr["n_domicile"],fr["n_exterieur"],fr["buts_attendus"]["dom"],fr["buts_attendus"]["ext"],fr["modele"]["n_matchs_ligue"])
    ok=[v for v,x in r.items() if reproduit(x.get("ancien"))]
    if not ok:
        base.update(classe="indéterminé",motif="aucune version d'assemblage ne permet à l'ancien chargeur de reproduire la fiche gelée"); rows.append(base); continue
    v=ok[0]; a=r[v]["ancien"]; n=r[v]["strict"]
    base["version_assemblage"]=v; base["versions_equivalentes"]=ok
    base["ancien_reproduit_paris"]=sorted(map(K,bets(a)))==sorted(map(K,bets(fr)))
    base["effectifs"]={"gele":[fr["n_domicile"],fr["n_exterieur"]],"strict":[n.get("n_domicile"),n.get("n_exterieur")]}
    if n.get("statut")!="analyse":
        base["strict_statut"]=n.get("statut"); base["strict_raison"]=n.get("raison")
        base["buts_attendus"]={"gele":[fr["buts_attendus"]["dom"],fr["buts_attendus"]["ext"]],"strict":None}
        base["paris_strict"]=[]; base["classe"]="affecté : match exclu par le chargeur strict (effectifs < 4)"
        base["verdict_paris"]={f"{b['cle'][0]}|{b['cle'][1]}":"perdu : match non analysable" for b in base["paris_geles"]}
        base["dp_max"]=None
    else:
        pm0,pm1=fr["p_marches"],n["p_marches"]
        base["buts_attendus"]={"gele":[fr["buts_attendus"]["dom"],fr["buts_attendus"]["ext"]],"strict":[n["buts_attendus"]["dom"],n["buts_attendus"]["ext"]]}
        base["n_matchs_ligue"]={"gele":fr["modele"]["n_matchs_ligue"],"strict":n["modele"]["n_matchs_ligue"]}
        base["dp_max"]=round(max(abs(x-y) for x,y in zip(pm0,pm1)),4)
        sk={K(b):b for b in bets(n)}; ska={K(b):b for b in bets(a)}
        mg={tuple(x["cle"]):x for x in n.get("_marches_gel",[])}
        vd={}
        for b in base["paris_geles"]:
            k=tuple(b["cle"]); lab=f"{k[0]}|{k[1]}"
            pn=sk[k]["p"] if k in sk else (mg[k]["p"] if k in mg else None)
            d={"p_gele":b["p"],"p_strict":pn and round(pn,4),"dp":pn is not None and round(pn-b["p"],4),"ancien_maintient":k in ska,"strict_maintient":k in sk}
            if k in ska and k in sk: d["statut"]="maintenu"
            elif k in ska and k not in sk: d["statut"]="retiré par le chargeur strict"; d["raison"]=mg.get(k,{}).get("decision")
            elif k not in ska and k in sk: d["statut"]="maintenu (l'ancien rejeu ne le retrouve pas : règle ou données différentes)"
            else: d["statut"]="non reproductible : retiré aussi avec l'ancien chargeur"; d["raison"]=mg.get(k,{}).get("decision")
            vd[lab]=d
        base["verdict_paris"]=vd
        ident=(sig(n)==sig(fr)) 
        base["classe"]="non affecté" if ident else ("affecté : paris retirés par le chargeur" if any(v_["statut"].startswith("retiré") for v_ in vd.values()) else "affecté : probabilités modifiées, paris maintenus")
        base["paris_strict"]=[dict(cle=list(K(b)),p=b["p"]) for b in bets(n)]
    rows.append(base)
json.dump(rows,open(S+"/classement2.json","w"),ensure_ascii=False,indent=1)
c=collections.Counter(r["classe"] for r in rows); print(c)
print("paris:",sum(len(r["paris_geles"]) for r in rows),"| ancien reproduit les paris:",sum(1 for r in rows if r.get("ancien_reproduit_paris")),"/",sum(1 for r in rows if "version_assemblage" in r))
print("versions:",collections.Counter(r.get("version_assemblage") for r in rows))
tot=collections.Counter()
for r in rows:
    for k,v in (r.get("verdict_paris") or {}).items(): tot[(r["termine"],v if isinstance(v,str) else v["statut"][:30])]+=1
print(tot)
for r in rows:
    if not r["classe"].startswith("non") and not r["classe"].startswith("indét"):
        vd=r.get("verdict_paris") or {}
        print(r["jour"],r["dom"],"-",r["ext"],"|",r["classe"][:28],"| n",r.get("effectifs",{}).get("gele"),"->",r.get("effectifs",{}).get("strict"),"| lam",r.get("buts_attendus",{}).get("gele"),"->",r.get("buts_attendus",{}).get("strict"),"| dP",r.get("dp_max"),"|",[(k.split('|')[1][:14],v["statut"][:9] if isinstance(v,dict) else v[:5],v.get("dp") if isinstance(v,dict) else None) for k,v in vd.items()],"fini" if r["termine"] else "",r.get("motif",""))
