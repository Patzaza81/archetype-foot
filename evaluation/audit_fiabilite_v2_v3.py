"""Audit de fiabilité V2 / V3 (22/10/2026) : réussite réelle des paris GELÉS avant match, par probabilité, indice et échantillon.
Lecture seule. Lancer depuis la racine du dépôt : python evaluation/audit_fiabilite_v2_v3.py"""
import sys, json, glob, gzip, math, collections, os
sys.path.insert(0, os.getcwd())
from moteur_v3.markets import gagne
from moteur_v3.model import _latest
from v2_indice import marche_v3, indice_du_marche
from moteur_v3.performance import indice_performance

# ---- archive (scores + séries d'avant-match) ----
ARCH = {}
for f in sorted(glob.glob("data/archive_test/*.json.gz")):
    for k, m in json.load(gzip.open(f)).items():
        ARCH[str(m.get("match_id") or k)] = m
def score(m):
    s = m.get("score") or {}
    return (s["buts_dom"], s["buts_ext"]) if isinstance(s.get("buts_dom"), int) and isinstance(s.get("buts_ext"), int) else None
def series(m, jour):
    dom = _latest([x for x in (m.get("equipe_dom") or {}).get("matchs") or [] if str(x.get("date"))[:10] < jour], True)
    ext = _latest([x for x in (m.get("equipe_ext") or {}).get("matchs") or [] if str(x.get("date"))[:10] < jour], False)
    return dom, ext

rows = []   # une ligne par pari gelé
# ---- V3 : journal gelé ----
dern = {}
for f in sorted(glob.glob("data/v3/journal/*.json")):
    for mid, m in json.load(open(f)).items():
        dern[mid] = m           # dernier calcul avant le coup d'envoi
for mid, m in dern.items():
    for s in m.get("selections") or []:
        a = ARCH.get(mid); sc = score(a) if a else None
        if sc is None: continue
        g = gagne(s["marche"], *sc)
        if g is None: continue
        dom, ext = series(a, m["date"])
        ip = s.get("indice_performance") or indice_performance(s["marche"], dom, ext)
        rows.append(dict(moteur="V3", match=mid, date=m["date"], marche=s["marche"], p=s["probabilite"], cote=s.get("cote"),
                         gagne=bool(g), indice=(ip or {}).get("indice"), sur=(ip or {}).get("sur"), ndom=len(dom), next=len(ext),
                         nmin=min(len(dom), len(ext))))
# ---- V2 : choix gelés dans l'archive ----
for mid, a in ARCH.items():
    mep = a.get("moteur_en_production") or {}
    sc = score(a)
    if sc is None or not mep.get("choix"): continue
    dom, ext = series(a, a["date"])
    for rang, c in mep["choix"].items():
        mk3 = marche_v3(str(c.get("marche_moteur") or ""))
        if mk3 is None: continue
        g = gagne(mk3, *sc)
        if g is None: continue
        ip = indice_performance(mk3, dom, ext)
        rows.append(dict(moteur="V2", match=mid, date=a["date"], marche=c["marche_moteur"], p=c["probabilite"], cote=c.get("cote"),
                         gagne=bool(g), indice=(ip or {}).get("indice"), sur=(ip or {}).get("sur"), ndom=len(dom), next=len(ext),
                         nmin=min(len(dom), len(ext)), rang=rang, version=mep.get("version")))


def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); r = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c-r)/d, (c+r)/d)
def tab(titre, lignes, cle):
    g = collections.defaultdict(list)
    for r in lignes: g[cle(r)].append(r)
    print(f"\n{titre}")
    print(f"{'groupe':<22}{'n':>5}{'réussite':>10}{'IC95%':>16}{'p moyenne':>11}{'écart':>8}")
    for k in sorted(g, key=str):
        l = g[k]; n = len(l); w = sum(r['gagne'] for r in l); pm = sum(r['p'] for r in l)/n
        lo, hi = wilson(w, n)
        print(f"{str(k):<22}{n:>5}{w/n*100:>9.1f}%{f'[{lo*100:.0f}–{hi*100:.0f}]':>16}{pm*100:>10.1f}%{(w/n-pm)*100:>+7.1f}")
def bande(p): return "≥90 %" if p>=.9 else "80–90 %" if p>=.8 else "70–80 %" if p>=.7 else "60–70 %" if p>=.6 else "<60 %"
for mo in ("V2", "V3"):
    L = [r for r in rows if r["moteur"] == mo]
    print("\n" + "="*70 + f"\n{mo} : {len(L)} paris gelés avec résultat, {len({r['match'] for r in L})} matchs, du {min(r['date'] for r in L)} au {max(r['date'] for r in L)}")
    w = sum(r['gagne'] for r in L); print(f"Réussite globale {w/len(L)*100:.1f} % ; probabilité annoncée moyenne {sum(r['p'] for r in L)/len(L)*100:.1f} %")
    tab(f"{mo} par bande de probabilité annoncée", L, lambda r: bande(r['p']))
    tab(f"{mo} par indice de performance", L, lambda r: f"{r['indice']}/{r['sur']}" if r['indice'] is not None else "sans indice")
    tab(f"{mo} par taille d'échantillon (matchs au même lieu, équipe la moins fournie)", L, lambda r: "≤3" if r['nmin']<=3 else "4" if r['nmin']==4 else "5" if r['nmin']==5 else "6+")
    S = [r for r in L if r['indice'] is not None and r['indice'] == r['sur']]
    tab(f"{mo} : indice max (4/4 ou 2/2 une équipe) × probabilité", S, lambda r: bande(r['p']))
    tab(f"{mo} : indice max × échantillon", S, lambda r: "≤3" if r['nmin']<=3 else "4–5" if r['nmin']<=5 else "6+")
    H = [r for r in L if r['p'] >= .8]
    tab(f"{mo} : probabilité ≥ 80 % × indice", H, lambda r: f"{r['indice']}/{r['sur']}" if r['indice'] is not None else "sans indice")
    tab(f"{mo} : probabilité ≥ 80 % × échantillon", H, lambda r: "≤3" if r['nmin']<=3 else "4–5" if r['nmin']<=5 else "6+")
    tab(f"{mo} par type de marché", L, lambda r: r['marche'].split('_')[0] if mo=="V3" else r['marche'].split('_')[0])
