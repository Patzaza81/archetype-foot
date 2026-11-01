# usage: python rejeu_commit.py <worktree> <ids.json> <sortie.json>   (exécuté DANS le worktree du commit qui a gelé la fiche)
import sys, json, gzip, glob, importlib.util, types, datetime, copy, traceback
import re as _re
wt, ids_f, out_f = sys.argv[1:4]
import types as _t
S="/tmp/claude-0/-home-claude/afbb0763-2a9f-5585-8d9a-c1e00b70e6af/scratchpad"
sys.path.insert(0, wt)
import moteur_dc.donnees as D0
def _mod(src,nom):
    m=types.ModuleType("moteur_dc."+nom); m.__package__="moteur_dc"; m.__file__=wt+"/moteur_dc/donnees.py"; exec(compile(src,nom,"exec"),m.__dict__); return m
D=_mod(open(S+"/donnees_ancien.py").read(),"anc")
from moteur_dc import suivi, coeur
from pathlib import Path
src=open(S+"/donnees_strict.py").read()
STR=types.ModuleType("moteur_dc.donnees_strict"); STR.__package__="moteur_dc"; STR.__file__=wt+"/moteur_dc/donnees.py"; exec(compile(src,"strict","exec"),STR.__dict__)
ids=json.load(open(ids_f))      # {match_id: {"emac":..}}
ARCH="/home/claude/archetype-foot/data/archive_test"
_src=_re.sub(r"if joue and \(not pris or not ko or str\(pris\) >= str\(ko\)\):\n\s+continue","pass",open(S+"/donnees_strict.py").read())
assert _src!=open(S+"/donnees_strict.py").read()
DP=_mod(_src,"prod")
def ARCH_SANS_FILTRE(L): return DP.charger_archive(L, Path(ARCH))
res={}
CAP={}
_f=suivi.fiche
def _fw(m_,a_,s_,matchs_):
    CAP['marches']=[{'cle':l['cle'],'p':l['p'],'base':l.get('base'),'edge':l.get('edge'),'seuil':l.get('seuil'),'cote':l.get('cote'),'decision':l.get('decision')} for l in (a_.get('marches') or [])]
    return _f(m_,a_,s_,matchs_)
suivi.fiche=_fw
for v in ["435dd1f","64675df","1dc1035","2c80acc","6068a9d","dc700f3"]:
    doc=json.load(open(f"{S}/asm/{v}.json"))
    for nom,mod in (("ancien",D),("strict",STR)):
        L=mod.Ligues(doc)
        # le chargeur de l'archive vient du worktree mais lit l'archive actuelle ; `ligues.equipe` identique
        matchs=[m for m in ARCH_SANS_FILTRE(L) if m["id"] in ids]
        for m in matchs:
            m=dict(m); m["h"]=None; m["a"]=None; m["cotes"]=ids[m["id"]]["cotes"]; m["coup_d_envoi_utc"]=m.get("coup_d_envoi_utc") or ids[m["id"]]["ko"]
            params=suivi.charger_parametres(); params=dict(params); params["emac"]=ids[m["id"]]["emac"]
            import tempfile, os
            jp=Path(tempfile.mkdtemp())/"j.jsonl"
            CAP.clear()
            try:
                suivi.geler(maintenant=datetime.datetime(2020,1,1,tzinfo=datetime.timezone.utc), journal=jp, ligues=L, matchs=[m], params=params)
                l=[json.loads(x) for x in jp.read_text().splitlines()]
                f_=l[0]["fiche"] if l else None
                if f_: f_["_marches_gel"]=[x for x in CAP.get("marches",[]) if list(x["cle"]) in ids[m["id"]]["cles"]]
                res.setdefault(m["id"],{}).setdefault(v,{})[nom]=f_
            except Exception as e:
                res.setdefault(m["id"],{}).setdefault(v,{})[nom]={"erreur":repr(e)+traceback.format_exc()[-600:]}
json.dump(res,open(out_f,"w"),ensure_ascii=False)
print(wt,len(res))
