"""Étude des indicateurs AFFICHÉS sur le site (indice x/4, pourcentage, étoiles) et des résultats obtenus, V2 et V3 (22/10/2026).
Paris GELÉS avant le match, joints au score final. Lecture seule. Racine du dépôt : python evaluation/etude_affichage_v2_v3.py
Écrit docs/ETUDE_AFFICHAGE_V2_V3.md et docs/etude_affichage_v2_v3_paris.csv."""
import csv, glob, gzip, json, math, os, sys, collections
sys.path.insert(0, os.getcwd())
from moteur_v3.markets import gagne
from moteur_v3.model import _latest
from moteur_v3.performance import indice_performance
from v2_indice import marche_v3
from moteur_v2_6_10.noyau import categorie_value, artefacts_marche

ARCH = {}
for f in sorted(glob.glob("data/archive_test/*.json.gz")):
    for k, m in json.load(gzip.open(f)).items():
        ARCH[str(m.get("match_id") or k)] = m
def score(m):
    s = m.get("score") or {}
    return (s["buts_dom"], s["buts_ext"]) if isinstance(s.get("buts_dom"), int) and isinstance(s.get("buts_ext"), int) else None
def series(m, jour):
    return (_latest([x for x in (m.get("equipe_dom") or {}).get("matchs") or [] if str(x.get("date"))[:10] < jour], True),
            _latest([x for x in (m.get("equipe_ext") or {}).get("matchs") or [] if str(x.get("date"))[:10] < jour], False))
def etoiles_v3(n_min):    # moteur_v3_pipeline.niveau_echantillon -> traduction_marches.js / archetype_v3.js
    return 1 if n_min < 5 else 2 if n_min < 8 else 3 if n_min < 10 else 4
ETOILES_V2 = {"A": 3, "B": 2, "C": 1}   # CAT_A -> 3, CAT_B -> 2, CAT_C -> 1 (traduction_marches.js)

rows = []
dern = {}
for f in sorted(glob.glob("data/v3/journal/*.json")):
    for mid, m in json.load(open(f)).items():
        dern[mid] = m
for mid, m in dern.items():
    a = ARCH.get(mid); sc = score(a) if a else None
    if sc is None: continue
    for s in m.get("selections") or []:
        g = gagne(s["marche"], *sc)
        if g is None: continue
        dom, ext = series(a, m["date"])
        ip = s.get("indice_performance") or indice_performance(s["marche"], dom, ext)
        nmin = min(m.get("n_dom") or len(dom), m.get("n_ext") or len(ext))
        rows.append(dict(moteur="V3", date=m["date"], match=f'{m["domicile"]} - {m["exterieur"]}', marche=s["libelle"], pct=s["probabilite"],
                         cote=s.get("cote"), indice=(ip or {}).get("indice"), sur=(ip or {}).get("sur"), etoiles=etoiles_v3(nmin),
                         matchs_min=nmin, gagne=int(g), score=f"{sc[0]}-{sc[1]}"))
for mid, a in ARCH.items():
    mep = a.get("moteur_en_production") or {}
    sc = score(a)
    if sc is None or not mep.get("choix"): continue
    dom, ext = series(a, a["date"])
    for rang, c in mep["choix"].items():
        mk3 = marche_v3(str(c.get("marche_moteur") or ""))
        g = gagne(mk3, *sc) if mk3 else None
        if g is None: continue
        ligne = {"marche": c["marche_moteur"], "proba_modele": c["probabilite"], "cote": c["cote"], "ev": c.get("edv") or 0.0}
        cat = categorie_value(ligne["ev"], ligne["proba_modele"], len(artefacts_marche(ligne)))
        if cat not in ETOILES_V2: continue            # catégorie D : jamais affichée
        ip = indice_performance(mk3, dom, ext)
        rows.append(dict(moteur="V2", date=a["date"], match=f'{a["domicile"]} - {a["exterieur"]}', marche=c["marche"], pct=c["probabilite"],
                         cote=c["cote"], indice=(ip or {}).get("indice"), sur=(ip or {}).get("sur"), etoiles=ETOILES_V2[cat],
                         matchs_min=min(len(dom), len(ext)), gagne=int(g), score=f"{sc[0]}-{sc[1]}"))

def bande(p):  # pourcentage affiché, arrondi comme sur le site
    x = round(p * 100)
    return "90 % et +" if x >= 90 else "80–89 %" if x >= 80 else "70–79 %" if x >= 70 else "60–69 %" if x >= 60 else "moins de 60 %"
ORD_B = ["moins de 60 %", "60–69 %", "70–79 %", "80–89 %", "90 % et +"]
def lbl_i(r): return "sans indice" if r["indice"] is None else f'{r["indice"]}/{r["sur"]}'
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); r = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)); return (c-r)/d*100, (c+r)/d*100
def table(lignes, cle, ordre=None, titre_cle="Groupe"):
    g = collections.defaultdict(list)
    for r in lignes: g[cle(r)].append(r)
    ks = ordre or sorted(g, key=str)
    out = [f"| {titre_cle} | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |", "|---|---:|---:|---:|---:|---:|"]
    for k in ks:
        l = g.get(k, [])
        if not l: continue
        n = len(l); w = sum(r["gagne"] for r in l); lo, hi = wil(w, n)
        out.append(f"| {k} | {n} | {w} | {n-w} | {w/n*100:.1f} % | {lo:.0f}–{hi:.0f} % |")
    return "\n".join(out)

md = ["# Étude des indicateurs affichés — V2 et V3\n",
      "Date : 22/10/2026. Pour chaque pari proposé par le moteur (gelé avant le match) : l'indice de performance affiché (x/4), le pourcentage affiché, le nombre d'étoiles affiché, et le résultat réel (gagné / perdu).\n",
      "**Sources** : V2 = `moteur_en_production.choix` de `data/archive_test` ; V3 = `data/v3/journal` (dernier calcul avant le coup d'envoi) ; scores finaux de l'archive. Reproductible : `python evaluation/etude_affichage_v2_v3.py`. Liste complète des paris : `docs/etude_affichage_v2_v3_paris.csv`.\n",
      "**Indice** : calcul du moteur (`moteur_v3/performance.py`) sur les séries d'avant-match ; 4/4 pour un marché à deux équipes, 2/2 pour un marché d'une seule équipe (le maximum dans les deux cas, regroupé ci-dessous sous « indice maximal »).",
      "**Pourcentage** : la probabilité affichée du pari. **Étoiles V2** : catégorie du moteur (A = 3, B = 2, C = 1) recalculée avec la règle exacte `categorie_value` ; l'artefact « données issues du classement uniquement » n'est pas archivé et n'est pas pris en compte. **Étoiles V3** : taille de l'échantillon au même lieu de l'équipe la moins fournie (moins de 5 matchs = 1 ; 5 à 7 = 2 ; 8 à 9 = 3 ; 10 et plus = 4).\n"]
for mo in ("V2", "V3"):
    L = [r for r in rows if r["moteur"] == mo]
    d0, d1 = min(r["date"] for r in L), max(r["date"] for r in L)
    w = sum(r["gagne"] for r in L)
    md += [f"\n---\n\n## {mo}\n", f"**{len(L)} paris**, {len({r['match'] for r in L})} matchs, du {d0} au {d1}. Gagnés : {w}. Perdus : {len(L)-w}. Réussite : {w/len(L)*100:.1f} %.\n"]
    md += ["### 1. Par indice affiché\n", table(L, lbl_i, titre_cle="Indice") + "\n"]
    md += ["### 2. Par pourcentage affiché\n", table(L, lambda r: bande(r["pct"]), ORD_B, "Pourcentage") + "\n"]
    md += ["### 3. Par nombre d'étoiles affiché\n", table(L, lambda r: f'{r["etoiles"]} ★', None, "Étoiles") + "\n"]
    md += ["### 4. Indice × pourcentage\n"]
    for i in sorted({lbl_i(r) for r in L}, reverse=True):
        S = [r for r in L if lbl_i(r) == i]
        md += [f"**Indice {i}**\n", table(S, lambda r: bande(r["pct"]), ORD_B, "Pourcentage") + "\n"]
    md += ["### 5. Étoiles × pourcentage\n"]
    for e in sorted({r["etoiles"] for r in L}, reverse=True):
        S = [r for r in L if r["etoiles"] == e]
        md += [f"**{e} ★**\n", table(S, lambda r: bande(r["pct"]), ORD_B, "Pourcentage") + "\n"]
    md += ["### 6. Indice × étoiles\n"]
    for e in sorted({r["etoiles"] for r in L}, reverse=True):
        S = [r for r in L if r["etoiles"] == e]
        md += [f"**{e} ★**\n", table(S, lbl_i, None, "Indice") + "\n"]
    md += ["### 7. Combinaisons les plus regardées\n"]
    def comb(nom, f):
        S = [r for r in L if f(r)]
        if not S: return f"| {nom} | 0 | 0 | 0 | — | — |"
        n = len(S); w = sum(r["gagne"] for r in S); lo, hi = wil(w, n)
        return f"| {nom} | {n} | {w} | {n-w} | {w/n*100:.1f} % | {lo:.0f}–{hi:.0f} % |"
    mx = lambda r: r["indice"] is not None and r["indice"] == r["sur"]
    md += ["| Combinaison | Paris | Gagnés | Perdus | Réussite | Intervalle 95 % |", "|---|---:|---:|---:|---:|---:|",
           comb("Indice maximal (4/4 ou 2/2)", mx), comb("Indice 4/4", lambda r: r["indice"] == 4 and r["sur"] == 4),
           comb("Pourcentage 80 % et +", lambda r: round(r["pct"]*100) >= 80),
           comb("Indice maximal et pourcentage 80 % et +", lambda r: mx(r) and round(r["pct"]*100) >= 80),
           comb("Indice maximal et 3 étoiles", lambda r: mx(r) and r["etoiles"] == 3),
           comb("Pourcentage 80 % et + et 3 étoiles", lambda r: round(r["pct"]*100) >= 80 and r["etoiles"] == 3),
           comb("Indice maximal, 80 % et +, 3 étoiles", lambda r: mx(r) and round(r["pct"]*100) >= 80 and r["etoiles"] == 3),
           comb("Indice maximal, 80 % et +, 3 étoiles ou plus", lambda r: mx(r) and round(r["pct"]*100) >= 80 and r["etoiles"] >= 3), ""]
    md += ["### 8. Par type de marché\n"]
    fam = lambda r: ("Handicap" if "andicap" in r["marche"] else "Moins de buts" if r["marche"].startswith(("Moins", "Under")) else
                     "Plus de buts" if r["marche"].startswith(("Plus", "Over")) else "Double chance" if "ouble chance" in r["marche"] or "ne perd pas" in r["marche"] else
                     "Victoire" if r["marche"].startswith(("Victoire", "Domicile", "Extérieur")) else "Les deux équipes marquent" if "deux" in r["marche"].lower() else "Autres")
    md += [table(L, fam, None, "Marché") + "\n"]
md += ["\n---\n\n## Limites de lecture\n",
       "- Période courte (V2 : 24 jours, V3 : 17 jours) : les sous-groupes de moins de 30 paris sont à lire avec prudence ; l'intervalle 95 % (Wilson) donne la marge.",
       "- Plusieurs paris d'un même match sont possibles : les intervalles réels sont un peu plus larges.",
       "- Les paris V2 sont ceux du moteur de production de l'archive (versions 2.6.9 et 2.6.10).",
       "- Archive de test : aucun pari réel n'est engagé.\n"]
open("docs/ETUDE_AFFICHAGE_V2_V3.md", "w", encoding="utf-8").write("\n".join(md))
with open("docs/etude_affichage_v2_v3_paris.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["moteur", "date", "match", "marche", "pourcentage", "cote", "indice", "sur", "etoiles", "matchs_min", "score", "gagne"])
    for r in sorted(rows, key=lambda r: (r["moteur"], r["date"])):
        w.writerow([r["moteur"], r["date"], r["match"], r["marche"], round(r["pct"]*100), r["cote"], r["indice"], r["sur"], r["etoiles"], r["matchs_min"], r["score"], r["gagne"]])
print(len(rows), "paris")
