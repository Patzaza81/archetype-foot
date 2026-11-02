import sys,json,re,types,gzip,glob
sys.path.insert(0,'/home/claude/archetype-foot')
from pathlib import Path
S="/tmp/claude-0/-home-claude/afbb0763-2a9f-5585-8d9a-c1e00b70e6af/scratchpad"
def mod(p,n):
    m=types.ModuleType("moteur_dc."+n); m.__package__="moteur_dc"; m.__file__="/home/claude/archetype-foot/moteur_dc/donnees.py"; exec(compile(open(p).read(),n,"exec"),m.__dict__); return m
A=mod(S+"/donnees_ancien.py","a"); N=mod(S+"/donnees_strict.py","n")
R=json.load(open(S+"/classement2.json"))
arch={}
for f in sorted(glob.glob('/home/claude/archetype-foot/data/archive_test/*.json.gz')):
    for k,x in json.load(gzip.open(f)).items():
        if x.get("match_id"): arch[str(x["match_id"])]=x
cache={}
out=[]
for r in R:
    if r["classe"].startswith("non") or r["classe"].startswith("indét"): continue
    v=r["version_assemblage"]
    if v not in cache:
        doc=json.load(open(f"{S}/asm/{v}.json")); cache[v]=(A.Ligues(doc),N.Ligues(doc))
    LA,LN=cache[v]; x=arch[r["match_id"]]; comp=x["competition"]
    res={"match":f'{r["dom"]} - {r["ext"]}',"jour":r["jour"],"classe":r["classe"],"version":v,"termine":r["termine"]}
    for role,e in (("dom","equipe_dom"),("ext","equipe_ext")):
        cle=f"{x[e]['url_equipe']}||{str(comp).lower()}"
        ia,inn=LA.equipe(cle),LN.equipe(cle)
        lg=str(comp).lower()
        def hist(L,i): return {(m["date"],m["dom_nom"],m["ext_nom"],m["h"],m["a"]) for m in L.matchs[lg] if i in (m["dom"],m["ext"]) and m["date"]<r["jour"]}
        ha,hn=hist(LA,ia),hist(LN,inn)
        res[role]={"equipe":r["dom"] if role=="dom" else r["ext"],"matchs_ancien":len(ha),"matchs_strict":len(hn),
                   "retires_(venaient_d_autres_clubs)":sorted(ha-hn),"ajoutes":sorted(hn-ha)}
    out.append(res)
json.dump(out,open(S+"/causes.json","w"),ensure_ascii=False,indent=1)
for o in out:
    print(o["jour"],o["match"],o["classe"][:22])
    for role in ("dom","ext"):
        d=o[role]
        if d["retires_(venaient_d_autres_clubs)"] or d["ajoutes"]:
            print("   ",d["equipe"],d["matchs_ancien"],"->",d["matchs_strict"],"| retirés:",[(a,b,c,e,f) for a,b,c,e,f in d["retires_(venaient_d_autres_clubs)"]][:6],"| ajoutés:",d["ajoutes"][:4])
