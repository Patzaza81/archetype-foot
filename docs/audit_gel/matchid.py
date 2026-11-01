import json, subprocess, sys, re, collections, types
R="/home/claude/archetype-foot"; sys.path.insert(0,R)
S="/tmp/claude-0/-home-claude/afbb0763-2a9f-5585-8d9a-c1e00b70e6af/scratchpad"
def mod(p,n):
    m=types.ModuleType("moteur_dc."+n); m.__package__="moteur_dc"; m.__file__=R+"/moteur_dc/donnees.py"; exec(compile(open(p).read(),n,"exec"),m.__dict__); return m
A=mod(S+"/donnees_ancien.py","a"); N=mod(S+"/donnees_strict.py","n"); norm=N.norm
git=lambda *a: subprocess.run(["git",*a],capture_output=True,text=True,cwd=R).stdout
idm=lambda u: (re.search(r"_([a-z0-9]{20,})\.html",u or "") or [None,None])[1]
out={}
for c in ("6068a9d","1dc1035"):
    doc=json.loads(git("show",f"{c}:data/assemblage/equipes.json"))
    LA,LN=A.Ligues(doc),N.Ligues(doc)
    tot=sum(len(x["matchs"]) for x in doc["equipes"]); avec=sum(1 for x in doc["equipes"] for m in x["matchs"] if idm(m.get("url_match")))
    noms=collections.defaultdict(dict)
    for x in doc["equipes"]:
        for n in (x.get("nom_football_data"),x.get("nom_matchendirect")):
            if n: noms[x["competition"]][norm(n)]=x["cle_cache"]
        s=N._slug(x["cle_cache"])
        if s: noms[x["competition"]].setdefault(s,x["cle_cache"])
    byid=collections.defaultdict(list)     # (ligue,id) -> [(équipe, adversaire, domicile, score)]
    for x in doc["equipes"]:
        for m in x["matchs"]:
            i=idm(m.get("url_match"))
            if i and m.get("adversaire"): byid[(x["competition"],i)].append((x["cle_cache"],m["adversaire"],bool(m["domicile"]),m["buts_marques"],m["buts_encaisses"],m.get("date")))
    # preuve par identifiant de match : alias cité par t sur le match i = équipe u qui a aussi ce match i dans son bloc
    preuves=collections.defaultdict(lambda: collections.defaultdict(set))   # (ligue,alias) -> club -> {ids}
    incoh=0
    for (lg,i),recs in byid.items():
        cles={r[0] for r in recs}
        if len(recs)<2 or len(cles)<2: continue
        for r in recs:
            for r2 in recs:
                if r2[0]==r[0]: continue
                al=norm(r[1]); 
                if noms[lg].get(al) is None: preuves[(lg,al)][r2[0]].add(i)
                elif noms[lg][al]!=r2[0]: incoh+=1
    # comparaison avec chaque chargeur
    def rattache(L,lg,al):
        i=L._uf.trouve(f"?{lg}|{al}"); return i if i in {x["cle_cache"] for x in doc["equipes"]} else None
    rows=collections.Counter(); detail=[]
    for (lg,al),cl in preuves.items():
        cible=max(cl,key=lambda k:len(cl[k])) if len(cl)==1 else None
        ra,rn=rattache(LA,lg,al),rattache(LN,lg,al)
        etat=lambda r: "aucun" if r is None else ("accord" if r==cible else "DESACCORD")
        if cible is None: rows[("preuve ambiguë",)]+=1; continue
        rows[("ancien",etat(ra),"strict",etat(rn))]+=1
        if etat(ra)=="DESACCORD" or etat(rn)=="DESACCORD": detail.append((lg,al,cible.split('/equipe/')[1][:25],ra and ra.split('/equipe/')[1][:25],rn and rn.split('/equipe/')[1][:25]))
    print(c,"matchs",tot,"avec url_match",avec,f"({avec/tot:.1%})","| ids vus par ≥2 équipes:",sum(1 for r in byid.values() if len({x[0] for x in r})>=2),"| incohérences nom résolu≠équipe:",incoh)
    print("   alias non résolus avec preuve par identifiant de match:",len(preuves))
    for k,v in sorted(rows.items(),key=lambda kv:-kv[1]): print("   ",k,v)
    for d in detail[:10]: print("   désaccord:",d)
    # alias non couverts par la preuve par id : combien l'un ou l'autre en rattache ?
    nonprouves_ancien=[(lg,al) for (lg,al) in [(a,b) for (a,b) in {(x["competition"],norm(m["adversaire"])) for x in doc["equipes"] for m in x["matchs"] if m.get("adversaire") and norm(m["adversaire"]) not in noms[x["competition"]]}] if rattache(LA,lg,al) and (lg,al) not in preuves]
    nonprouves_strict=[(lg,al) for (lg,al) in [(a,b) for (a,b) in {(x["competition"],norm(m["adversaire"])) for x in doc["equipes"] for m in x["matchs"] if m.get("adversaire") and norm(m["adversaire"]) not in noms[x["competition"]]}] if rattache(LN,lg,al) and (lg,al) not in preuves]
    print("   rattachés SANS preuve par identifiant de match: ancien",len(nonprouves_ancien),"| strict",len(nonprouves_strict))
    out[c]=dict(matchs=tot,avec_url=avec,alias_prouves_par_id=len(preuves),rows={"|".join(k):v for k,v in rows.items()},ancien_sans_preuve_id=len(nonprouves_ancien),strict_sans_preuve_id=len(nonprouves_strict))
json.dump(out,open(S+"/matchid.json","w"),ensure_ascii=False,indent=1)

print("=== détails 6068a9d ===")
c="6068a9d"; doc=json.loads(git("show",f"{c}:data/assemblage/equipes.json")); LA,LN=A.Ligues(doc),N.Ligues(doc)
cles={x["cle_cache"] for x in doc["equipes"]}
noms=collections.defaultdict(dict)
for x in doc["equipes"]:
    for n in (x.get("nom_football_data"),x.get("nom_matchendirect")):
        if n: noms[x["competition"]][norm(n)]=x["cle_cache"]
    s=N._slug(x["cle_cache"])
    if s: noms[x["competition"]].setdefault(s,x["cle_cache"])
byid=collections.defaultdict(list)
for x in doc["equipes"]:
    for m in x["matchs"]:
        i=idm(m.get("url_match"))
        if i and m.get("adversaire"): byid[(x["competition"],i)].append((x["cle_cache"],m["adversaire"],m.get("date"),m["buts_marques"],m["buts_encaisses"],m["domicile"]))
sh=lambda k: k.split("/equipe/")[1][:22]
for (lg,i),recs in byid.items():
    if len({r[0] for r in recs})<2: continue
    for r in recs:
        for r2 in recs:
            if r2[0]==r[0]: continue
            al=norm(r[1]); o=noms[lg].get(al)
            if o is None:
                if N.Ligues.__name__ and LN._uf.trouve(f"?{lg}|{al}") not in cles and LA._uf.trouve(f"?{lg}|{al}") in cles: print("id prouve, strict non:",lg,"| alias",r[1],"=",sh(r2[0]),"| match",i[:8],r[2],r[3:5],"| citants",sh(r[0]))
            elif o!=r2[0]: print("INCOHERENCE:",lg,"| ",sh(r[0]),"cite",r[1],"(résolu en",sh(o),") mais le match",i[:8],r[2],"figure aussi chez",sh(r2[0]),r2[1:])
