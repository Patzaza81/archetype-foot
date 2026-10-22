"""Vérification INDÉPENDANTE de l'onglet « Meilleures sélections » (22/10/2026). Racine du dépôt : python evaluation/verifie_meilleures_selections.py
Réimplémente la règle autrement (pandas + scipy, aucune fonction de meilleures_selections.regles) et compare ; rejoue le suivi nocturne jour
par jour ; mesure les fausses admissions quand les résultats sont mélangés au hasard ; vérifie qu'un avantage injecté est retrouvé et qu'une
règle qui s'effondre est remplacée. Seuls comptent les indicateurs affichés (indice, pourcentage, étoiles) et les résultats."""
import os, random, sys
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
from scipy.stats import hypergeom
from meilleures_selections import donnees, regles, suivi

tous = donnees.paris_resolus()
df0 = pd.DataFrame(tous)
v2 = df0[df0.moteur == "V2"]
version = v2.loc[v2.date.idxmax(), "version"]
paris = [p for p in tous if p["moteur"] != "V2" or p.get("version") == version]
echecs = []
print(f"0) Version V2 retenue : {version} ; paris V2 retirés : {len(tous) - len(paris)}")

def prepare(lst):
    d = pd.DataFrame(lst)
    d["fam"] = d["marche"].map(regles.famille)
    d = d[d.fam.notna() & d.indice.notna() & d.pct.notna() & d.etoiles.notna()].copy()
    d = d.sort_values(["pct", "marche"], ascending=[False, True]).drop_duplicates(["moteur", "match_id", "fam"])   # un pari par match et famille
    d["niv"] = d.indice / d.sur
    return d

def wilson_bas(g, n, z=1.96):
    p = g / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return (c - r) / d

def independant(d):
    m = 5 * 5 * 3 + 5 * 5 * 4
    sorties = {}
    for mot, dm in d.groupby("moteur"):
        emax = 3 if mot == "V2" else 4
        trouves = {"confirme": [], "observation": []}
        for i in (0, .25, .5, .75, 1):
            for pc in (0, 60, 70, 80, 90):
                for e in range(1, emax + 1):
                    sel = (dm.niv >= i - 1e-12) & (dm.pct >= pc) & (dm.etoiles >= e)
                    ens, reste = dm[sel], dm[~sel]
                    if ens.empty or reste.empty:
                        continue
                    ref = reste.gagne.mean(); n = len(ens); g = int(ens.gagne.sum())
                    p = float(hypergeom.sf(g - 1, len(dm), int(dm.gagne.sum()), n))
                    jours = sorted(ens.date.unique())
                    if len(jours) < 2:
                        continue
                    coupe = jours[len(jours) // 2]
                    stable = all(len(h) and h.gagne.mean() >= ref for h in (ens[ens.date < coupe], ens[ens.date >= coupe]))
                    if g / n > ref and stable:
                        if p <= .05 / m: trouves["confirme"].append((wilson_bas(g, n), n, -i, -pc, -e))
                        elif p <= 1 / m: trouves["observation"].append((wilson_bas(g, n), n, -i, -pc, -e))
        for st in ("confirme", "observation"):
            if trouves[st]:
                b = max(trouves[st]); sorties[mot] = (st, -b[2], -b[3], -b[4], b[1]); break
    return sorties

ref = independant(prepare(paris))
mod = {g["moteur"]: (g["statut"], g["indice_min"], g["pct_min"], g["etoiles_min"], g["n"]) for g in regles.calibrer(paris)["groupes"]}
print("1) Règle indépendante vs module :", "IDENTIQUE" if ref == mod else f"DIFFÉRENT\n   indépendant={ref}\n   module={mod}")
if ref != mod: echecs.append("règle")
print("   règle retenue :", mod)

jours = sorted({p["date"] for p in paris}); hist = []; recal = []
j = pd.Timestamp(jours[0]) + pd.Timedelta(days=7)
j0 = j
while j <= pd.Timestamp(jours[-1]) + pd.Timedelta(days=3):
    iso = j.date().isoformat(); avant = len(hist)
    hist, _ = suivi.construire(iso, paris, [], hist)
    if len(hist) > avant: recal.append(iso)
    j += pd.Timedelta(days=1)
ecarts = [(pd.Timestamp(b) - pd.Timestamp(a)).days for a, b in zip(recal, recal[1:])]
print("2) Rejeu nocturne :", len(hist), "instantanés aux dates", recal, "| écarts en jours :", ecarts)
if not all(e == 7 for e in ecarts) or recal[0] != j0.date().isoformat(): echecs.append("cadence hebdomadaire")
for h in hist: print("   ", h["calibre_le"], h["nb_paris"], "paris →", [(g["moteur"], g["indice_min"], g["pct_min"], g["etoiles_min"], g["statut"]) for g in h["groupes"]])

rnd = random.Random(2026); essais = 200; conf = obs = avec = 0
for _ in range(essais):
    fake = []
    for mot in ("V2", "V3"):
        lot = [p for p in paris if p["moteur"] == mot]
        res = [p["gagne"] for p in lot]; rnd.shuffle(res)
        fake += [{**p, "gagne": r} for p, r in zip(lot, res)]
    gr = regles.calibrer(fake)["groupes"]
    c = sum(g["statut"] == "confirme" for g in gr); conf += c; obs += len(gr) - c; avec += c > 0
print(f"3) Hasard pur ({essais} essais) : confirmés par recalibrage {conf/essais:.2f} (attendu <= 0,05) ; en observation {obs/essais:.2f} ; essais avec au moins un confirmé {avec/essais:.0%}")
if conf / essais > .05 * 1.5 + 0.05: echecs.append("fausses admissions confirmées")

g1 = [{**p, "gagne": int(rnd.random() < .95) if p["moteur"] == "V3" and p["pct"] >= 80 else p["gagne"]} for p in paris]
tr = {g["moteur"]: g for g in regles.calibrer(g1)["groupes"]}.get("V3")
trouve = bool(tr) and tr["pct_min"] >= 70
print("4) Avantage injecté (V3, pourcentage affiché >= 80 : 95 % de réussite) retrouvé :", trouve, "→", tr and (tr["indice_min"], tr["pct_min"], tr["etoiles_min"]))
if not trouve: echecs.append("avantage injecté non trouvé")
cible = {g["moteur"]: g for g in regles.calibrer(paris)["groupes"]}
milieu = sorted({p["date"] for p in paris})[len({p["date"] for p in paris}) // 2]
eff = [{**p, "gagne": 0 if (p["date"] >= milieu and p["moteur"] in cible and regles.dans_la_regle(p, cible[p["moteur"]])) else p["gagne"]} for p in paris]
nouv = {g["moteur"]: g for g in regles.calibrer(eff)["groupes"]}
restes = [m for m in cible if m in nouv and (nouv[m]["indice_min"], nouv[m]["pct_min"], nouv[m]["etoiles_min"]) == (cible[m]["indice_min"], cible[m]["pct_min"], cible[m]["etoiles_min"])]
print("5) Seconde moitié de la période à 0 % sur la règle retenue : règle encore identique pour", restes or "aucun moteur (remplacée)")
if restes: echecs.append("règle effondrée toujours retenue")
print("\nRÉSULTAT :", "TOUT EST CONFORME" if not echecs else "ÉCHEC → " + ", ".join(echecs))
sys.exit(1 if echecs else 0)
