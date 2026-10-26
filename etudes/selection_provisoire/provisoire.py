"""Sélection provisoire : pour chaque marché, niveau normal (= pronostic publié par alpha) ou maximal (+ au plus 1 échec passé), jugé sur les publiables."""
import json, math, pickle, sys
from pathlib import Path
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1])); sys.path.insert(0, str(ICI))
from collections import defaultdict
from alpha_serie.etude_marches import wilson, rendement
import niveaux as N
CIBLE = 0.70                     # objectif le plus bas déjà fixé par Patrick (bandes 1X2) ; 80 % = objectif du Plus de 1,5
_, L = pickle.load(open(ICI / 'niveaux_lignes.pkl', 'rb'))
v2 = json.load(open(ICI.parents[1] / 'data/etudes/decouverte_marches_v2_2026-10-26.json'))["etude_S"]
par = defaultdict(list)
for x in L: par[x["eid"]].append(x)
MG = lambda e: e.startswith("multigoals")
mx = lambda x: x["echecs"] is not None and x["echecs"] <= 1

def mesure(sel, eid):
    st = {k: N.stats([x for x in sel if x["per"] in v]) for k, v in (("A", (0,)), ("B", (1,)), ("R", (0, 1)), ("C", (2,)), ("D", (3,)))}
    D = [x for x in sel if x["per"] == 3]
    pub = D if MG(eid) else [x for x in D if x["cote"] and x["cote"] >= 1.25]
    g = sum(x["y"] for x in pub)
    st["pub"] = {"n": len(pub), "g": g, "taux": g / len(pub) if pub else None, "wil": wilson(g, len(pub)) if pub else None, "par_jour": len(pub) / 28,
                 "rend": rendement([(x["y"], x["cote"]) for x in pub if x["cote"]]), "cote_med": sorted(x["cote"] for x in pub if x["cote"])[len(pub)//2] if pub and not MG(eid) else None}
    st["requis_j"] = (N.n_requis(st["R"]["taux"], CIBLE) or math.inf) / 28 if st["R"]["n"] else math.inf
    return st

def ok(s):
    return s["R"]["n"] > 0 and s["R"]["taux"] >= CIBLE and s["C"]["n"] > 0 and s["C"]["taux"] >= CIBLE and s["pub"]["n"] > 0 and s["pub"]["taux"] >= CIBLE and s["pub"]["par_jour"] >= s["requis_j"]

def plus_haut(a, b):   # le taux publiable de a est-il significativement plus haut que celui de b ? (deux proportions, 5 % unilatéral)
    n1, g1, n2, g2 = a["n"], a["g"], b["n"], b["g"]
    if not n1 or not n2: return False
    p = (g1 + g2) / (n1 + n2); se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return se > 0 and (g1 / n1 - g2 / n2) / se > 1.645

out = {}
for eid, Ls in par.items():
    nor = mesure(Ls, eid)                       # niveau normal = tous les pronostics publiés (le maximal en fait partie)
    maxi = mesure([x for x in Ls if mx(x)], eid)
    if ok(nor) and ok(maxi):
        niv = "maximal" if plus_haut(maxi["pub"], nor["pub"]) else "normal"
    elif ok(nor): niv = "normal"
    elif ok(maxi): niv = "maximal"
    else: niv = "exclu"
    out[eid] = {"niveau": niv, "normal": nor, "maximal": maxi, "naturel": v2[eid]["protocole"]["taux_de_base_reglage"]}
json.dump(out, open(ICI.parents[1] / 'data/etudes/selection_provisoire_2026-10-26.json', 'w'), ensure_ascii=False, indent=1, default=str)
pc = lambda x: "-" if x is None else f"{100*x:.1f}"
for eid, r in out.items():
    print(f"\n{eid} -> {r['niveau'].upper()} (naturel {pc(r['naturel'])})")
    for lev in ("normal", "maximal"):
        s = r[lev]; p = s["pub"]; rd = p["rend"]
        print(f"  {lev:7s} R {s['R']['g']}/{s['R']['n']}={pc(s['R']['taux'])} (A {pc(s['A']['taux'])} B {pc(s['B']['taux'])}) C {s['C']['g']}/{s['C']['n']}={pc(s['C']['taux'])} D {s['D']['g']}/{s['D']['n']}={pc(s['D']['taux'])} | publiables {p['g']}/{p['n']}={pc(p['taux'])} [{pc(p['wil'][0]) if p['wil'] else '-'}-{pc(p['wil'][1]) if p['wil'] else '-'}] {p['par_jour']:.1f}/j requis {s['requis_j']:.1f}/j cote méd {p['cote_med']} rend {('%+.0f[%+.0f;%+.0f]'%(100*rd['rendement'],100*rd['ic95'][0],100*rd['ic95'][1])) if rd.get('paris') else '-'} ok={ok(s)}")
