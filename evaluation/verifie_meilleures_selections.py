"""Vérification INDÉPENDANTE de l'onglet « Meilleures sélections » (22/10/2026). Racine du dépôt : python evaluation/verifie_meilleures_selections.py
Réimplémente l'admission autrement (pandas + scipy, aucune fonction de meilleures_selections.regles) et compare ; rejoue le suivi nocturne
jour par jour ; mesure les fausses admissions quand on remplace les résultats réels par du hasard pur (probabilité = 1 / cote)."""
import os, random, sys
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
from scipy.stats import binom
from meilleures_selections import donnees, regles, suivi

tous = donnees.paris_resolus()
df0 = pd.DataFrame(tous)
v2 = df0[df0.moteur == "V2"]
version = v2.loc[v2.date.idxmax(), "version"]                       # version du pari V2 le plus récent
paris = [p for p in tous if p["moteur"] != "V2" or p.get("version") == version]
print(f"0) Version V2 retenue : {version} ; paris V2 retirés : {len(tous) - len(paris)}")
df = pd.DataFrame(paris)
df["fam"] = df["marche"].map(regles.famille)
df = df[df.fam.notna() & df.indice.notna() & df.cote.gt(1)].copy()
df["probabilite"] = df.probabilite.fillna(0.0)
df = df.sort_values(["probabilite", "marche", "cote"], ascending=[False, True, True]).drop_duplicates(["moteur", "match_id", "fam"])  # un pari par match et famille
df["niv"] = df.indice / df.sur
df["gain"] = np.where(df.gagne == 1, df.cote - 1, -1.0)
echecs = []

def independant(d, m):
    """Mêmes règles écrites autrement. Retourne {(moteur, famille): (statut, palier, n)}."""
    sorties = {}
    for (mot, fam), lot in d.groupby(["moteur", "fam"]):
        retenus = {"confirme": [], "observation": []}
        for palier in sorted(lot.niv.unique()):
            e = lot[lot.niv >= palier]
            n, g, base = len(e), int(e.gagne.sum()), (1 / e.cote).mean()
            p = float(binom.sf(g - 1, n, min(max(base, 1e-12), 1 - 1e-12)))
            jours = sorted(e.date.unique())
            if len(jours) < 2:
                continue
            coupe = jours[len(jours) // 2]
            moitie_ok = all(len(h) and h.gagne.mean() >= (1 / h.cote).mean() for h in (e[e.date < coupe], e[e.date >= coupe]))
            if e.gain.mean() > 0 and g / n > base and moitie_ok:
                if p <= 1 / m: retenus["confirme"].append((palier, n))
                elif p <= 1 / m ** 0.5: retenus["observation"].append((palier, n))
        for st in ("confirme", "observation"):
            if retenus[st]:
                sorties[(mot, fam)] = (st, *min(retenus[st]))
                break
    return sorties

m = 2 * (7 * 5 + 3 * 3)   # 2 moteurs x (7 familles à 2 équipes x 5 paliers + 3 familles à 1 équipe x 3 paliers), écrit à la main
ref = independant(df, m)
mod = {(g["moteur"], g["famille"]): (g["statut"], g["palier"], g["n"]) for g in regles.calibrer(paris)["groupes"]}
print("1) Admission indépendante vs module :", "IDENTIQUE" if ref == mod else f"DIFFÉRENT\n   indépendant={ref}\n   module={mod}")
if ref != mod: echecs.append("admission")
print("   groupes :", mod)

# 2) rejeu du suivi nocturne jour par jour (sans fichiers)
jours = sorted(df.date.unique()); hist = []; recal = []
j0 = pd.Timestamp(jours[0]) + pd.Timedelta(days=7)
j = j0
while j <= pd.Timestamp(jours[-1]) + pd.Timedelta(days=3):
    iso = j.date().isoformat()
    avant = len(hist)
    hist, sortie = suivi.construire(iso, paris, [], hist)
    if len(hist) > avant: recal.append(iso)
    j += pd.Timedelta(days=1)
ecarts = [(pd.Timestamp(b) - pd.Timestamp(a)).days for a, b in zip(recal, recal[1:])]
print("2) Rejeu nocturne :", len(hist), "instantanés aux dates", recal, "| écarts en jours :", ecarts)
if not all(e == 7 for e in ecarts) or recal[0] != j0.date().isoformat(): echecs.append("cadence hebdomadaire")
for h in hist: print("   ", h["calibre_le"], h["nb_paris"], "paris →", [(g["moteur"], g["famille"], g["statut"]) for g in h["groupes"]])

# 3) hasard pur : combien de groupes admis quand les résultats sont tirés au sort avec la probabilité 1/cote ?
rnd = random.Random(2026); essais = 300; conf = obs = avec_conf = 0
for _ in range(essais):
    fake = [{**p, "gagne": int(rnd.random() < 1 / p["cote"])} for p in paris]
    gr = regles.calibrer(fake)["groupes"]
    c = sum(g["statut"] == "confirme" for g in gr); conf += c; obs += len(gr) - c; avec_conf += c > 0
print(f"3) Hasard pur ({essais} essais) : confirmés par recalibrage {conf/essais:.2f} (attendu <= 1) ; en observation {obs/essais:.2f} ; essais avec au moins un confirmé {avec_conf/essais:.0%}")
if conf / essais > 1: echecs.append("fausses admissions confirmées")

# 4) avantage réel injecté : un groupe qui gagne vraiment doit être trouvé, et un groupe qui s'effondre doit sortir
def rate(r, f): return int(r.random() < f)
g1 = [{**p, "gagne": rate(rnd, 0.93) if p["marche"] == "under_2_5" and p["moteur"] == "V3" else p["gagne"]} for p in paris]
trouve = ("V3", "total_moins") in {(g["moteur"], g["famille"]) for g in regles.calibrer(g1)["groupes"]}
print("4) Avantage injecté (V3 moins de 2,5 à 93 %) retrouvé :", trouve)
if not trouve: echecs.append("avantage injecté non trouvé")
dernier = max(p["date"] for p in paris)
cible = [g for g in regles.calibrer(paris)["groupes"]]
effondre = [{**p, "gagne": 0 if (p["date"] > sorted({q["date"] for q in paris})[-8] and (p["moteur"], regles.famille(p["marche"])) in {(g["moteur"], g["famille"]) for g in cible}) else p["gagne"]} for p in paris]
reste = {(g["moteur"], g["famille"]) for g in regles.calibrer(effondre)["groupes"]} & {(g["moteur"], g["famille"]) for g in cible}
print("   Groupes actuels après 7 derniers jours à 0 % de réussite : encore admis =", reste or "aucun (remplacés)")
if reste: echecs.append("groupe effondré toujours admis")

print("\nRÉSULTAT :", "TOUT EST CONFORME" if not echecs else "ÉCHEC → " + ", ".join(echecs))
sys.exit(1 if echecs else 0)
