import json, subprocess, sys, collections
R="/home/claude/archetype-foot"; sys.path.insert(0,R)
from moteur_dc import donnees as D
git=lambda *a: subprocess.run(["git",*a],capture_output=True,text=True,cwd=R).stdout
short=lambda s: s.split("/equipe/")[1].split("_")[0] if "/equipe/" in str(s) else str(s).split("|")[-1]
out={}
for c in ("6068a9d","1dc1035"):
    doc=json.loads(git("show",f"{c}:data/assemblage/equipes.json"))
    L=D.Ligues(doc); cles={x["cle_cache"] for x in doc["equipes"]}
    noms=collections.defaultdict(dict)
    for x in doc["equipes"]:
        for n in (x.get("nom_football_data"),x.get("nom_matchendirect")):
            if n: noms[x["competition"]][D.norm(n)]=x["cle_cache"]
        s=D._slug(x["cle_cache"])
        if s: noms[x["competition"]].setdefault(s,x["cle_cache"])
    bloc={x["cle_cache"]:x for x in doc["equipes"]}
    cit=collections.defaultdict(list)
    for x in doc["equipes"]:
        for m in x["matchs"]:
            if m.get("date") and m.get("adversaire") and isinstance(m.get("buts_marques"),int) and isinstance(m.get("buts_encaisses"),int):
                al=D.norm(m["adversaire"])
                if al not in noms[x["competition"]] and al not in {D.norm(n) for n in (x.get("nom_football_data"),x.get("nom_matchendirect")) if n}:
                    cit[(x["competition"],al)].append((m["date"][:10],x["cle_cache"],bool(m["domicile"]),m["buts_marques"],m["buts_encaisses"],m["adversaire"]))
    rows=[]
    for (lg,al),recs in cit.items():
        idn=L._uf.trouve(f"?{lg}|{al}")
        if idn in cles:  # alias rattaché par le strict à un club du cache
            ncit=len(recs); dates={r[0] for r in recs}
            # citations nommées explicitement : le bloc du club cible liste l'équipe citante, même date, score inverse
            nomm=0
            for d,t,dom,g,cn,_ in recs:
                nomm+=any(str(m.get("date"))[:10]==d and noms[lg].get(D.norm(m["adversaire"]))==t and m["buts_marques"]==cn and m["buts_encaisses"]==g and bool(m["domicile"])!=dom for m in bloc[idn]["matchs"])
            # concurrents : autre club dont le bloc contredit ?
            rows.append(dict(ligue=lg,alias=recs[0][5],club=short(idn),citations=ncit,dates=len(dates),citations_prouvees=nomm,
                             citants=sorted({short(r[1]) for r in recs})))
    n=len(rows); un=[r for r in rows if r["citations"]==1]; part=[r for r in rows if r["citations_prouvees"]<r["citations"]]
    print(c,"alias rattachés par le STRICT à un club du cache:",n,"| 1 seule citation:",len(un),"| preuve partielle:",len(part))
    for r in un: print("   1cit",r)
    for r in part[:15]: print("   part",r)
    out[c]=rows
json.dump(out,open(sys.argv[1],"w"),ensure_ascii=False,indent=1)
