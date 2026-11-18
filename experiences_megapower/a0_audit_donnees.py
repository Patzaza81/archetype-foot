"""Audit des données historiques de la phase d'apprentissage rétrospectif (18/11/2026).
Les cotes Betpawa ne servent ICI qu'à mesurer le filtre opérationnel (cote >= 1,26) ; aucune n'entre dans un calcul prédictif."""
import glob, gzip, json, collections
import numpy as np
import commun as C
from commun import *
SEUIL = 1.26
matchs, sc, lig = C.charger()
ids = {m["id"] for m in matchs}
cot, var = {}, collections.Counter(); nobs = 0
for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
    for k, x in json.load(gzip.open(f)).items():
        if k in ids:
            cot[k] = V.cotes_betpawa(x.get("cotes_betpawa") or {})
for m in matchs:
    for r in m["md"] + m["me"]:
        nobs += 1
jou = [m for m in matchs if m["id"] in sc]
print("matchs flux", len(matchs), "joués", len(jou), "avec cotes", sum(1 for m in jou if cot.get(m["id"])))
# couverture des variables dans les fiches d'équipes brutes
champs = ["xg", "xg_concede", "tirs", "tirs_cadres", "corners", "buts_marques_mi_temps", "cartons_jaunes"]
tot = collections.Counter(); ok = collections.Counter()
for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz")))[-1:]:
    for k, x in json.load(gzip.open(f)).items():
        for side in ("equipe_dom", "equipe_ext"):
            for r in ((x.get("assemblage") or {}).get(side) or {}).get("matchs") or []:
                tot["n"] += 1
                for c in champs:
                    ok[c] += isinstance(r.get(c), (int, float))
print("couverture variables (dernier fichier, observations équipe)", tot["n"], {c: round(ok[c] / tot["n"], 3) for c in champs})
# filtre cote >= 1,26 : par marché, nombre de (match, marché) disponibles, part >= 1,26, taux de réussite des marchés qui passent
y = {}
for m in jou:
    h, a = sc[m["id"]]
    y[m["id"]] = TAB[min(h, 10), min(a, 10), :NB]
rows = []
for n in V.NOMS:
    i = V.NOMS.index(n); N = P = H = 0; c1 = []
    for m in jou:
        c = cot.get(m["id"], {}).get(n)
        if c is None: continue
        N += 1
        if c >= SEUIL:
            P += 1; H += y[m["id"]][i]; c1.append(c)
    if N >= 100: rows.append((n, N, P, H / P if P else float("nan"), float(np.median(c1)) if c1 else float("nan")))
rows.sort(key=lambda r: -r[2])
print("\nmarché | matchs avec cote | cote>=1,26 | réussite de ces cas (sans analyse) | cote médiane")
for r in rows: print(f"{r[0]:24s} {r[1]:5d} {r[2]:5d} {r[3]:.3f} {r[4]:.2f}")
