# -*- coding: utf-8 -*-
"""Onglet « Catégories » d'Analyse Verdict (24/11/2026, demande de Patrick) : à partir de la fiche des deux équipes, dire pour quels marchés le match tombe dans un intervalle favorable.

Fiche : les 4 piliers AU LIEU DU MATCH (buts marqués et encaissés par match de l'équipe à domicile À DOMICILE, de l'équipe à l'extérieur À L'EXTÉRIEUR, 4 matchs minimum au même lieu)
et le xG calculé sur TOUS les lieux de la saison en cours, rapporté à la moyenne de buts du championnat en cours (au moins 10 matchs précédents du championnat).
Intervalles : `data/verif_pronostics/categories_zones.json`, figés le 24/11/2026. Chaque marché a son seuil (décision de Patrick) et son propre ensemble d'intervalles, jamais généralisé.
Les intervalles ont été cherchés sur les matchs de 2000 à 2016 (apprentissage 2000-2012, validation 2013-2016) puis mesurés sur des matchs jamais vus (2017-2020 et saison 2025-26). Un intervalle d'un marché
n'est retenu que s'il atteint le seuil du marché ; version « B » = avec certitude (borne basse de Wilson 95 %) sur chacune des deux moitiés de la période de recherche, version « A » = sur l'ensemble.
La cote n'entre PAS dans la catégorisation : elle vient à la fin, cote >= cote minimale de la page (1,26), et un marché sans cote n'est jamais proposé.
Le xG de la saison (buts attendus par équipe) est estimé par une droite apprise sur 316 équipes à xG réel : xG créé = am + bm x buts marqués par match ; xG concédé = ae + be x buts encaissés par match.
Commande de test : python -m pytest tests/test_verif_categories.py"""
import json, math, os

RACINE = os.path.dirname(os.path.abspath(__file__))
CHEMIN = os.path.join(RACINE, "data", "verif_pronostics", "categories_zones.json")
NMIN = 4            # règle de Patrick : 4 matchs minimum au même lieu pour chaque équipe
NCHAMP_MIN = 10     # moyenne du championnat lue sur au moins 10 matchs précédents ; sinon les intervalles qui utilisent le xG ou le championnat ne s'appliquent pas
Z95 = 1.96
VARIABLES_XG = ("sMh", "sCh", "sMa", "sCa", "EH", "EA", "ET", "dE", "rE", "mu", "EHm", "EAm", "gH", "gA")

# nom lisible de chaque variable, pour la page (les valeurs viennent de la fiche, aucun calcul côté page)
LIBELLES = {
    "hM": "Buts marqués par match du domicile, à domicile", "hC": "Buts encaissés par match du domicile, à domicile",
    "aM": "Buts marqués par match de l'extérieur, dehors", "aC": "Buts encaissés par match de l'extérieur, dehors",
    "dM": "Buts marqués : domicile moins extérieur", "dC": "Buts encaissés : domicile moins extérieur",
    "A1": "Buts marqués du domicile moins buts encaissés de l'extérieur", "A2": "Buts marqués de l'extérieur moins buts encaissés du domicile",
    "X1g": "Buts marqués du domicile plus buts encaissés de l'extérieur", "X2g": "Buts marqués de l'extérieur plus buts encaissés du domicile",
    "SM": "Buts marqués par match des deux équipes réunies", "SC": "Buts encaissés par match des deux équipes réunies", "TG": "Total des quatre moyennes",
    "rM": "Rapport des buts marqués (domicile / extérieur)", "rC": "Rapport des buts encaissés (domicile / extérieur)", "rX": "Rapport X1g / X2g",
    "EH": "xG attendu du domicile", "EA": "xG attendu de l'extérieur", "ET": "xG attendu du match (total)", "dE": "xG attendu : domicile moins extérieur",
    "rE": "xG attendu : rapport domicile / extérieur", "mu": "Buts par équipe et par match du championnat",
    "EHm": "xG attendu du domicile moins la moyenne du championnat", "EAm": "xG attendu de l'extérieur moins la moyenne du championnat",
    "gH": "Buts attendus du domicile moins son xG", "gA": "Buts attendus de l'extérieur moins son xG"}

def charger(chemin=CHEMIN):
    try:
        with open(chemin, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return None

def wilson(k, n, z=Z95):
    if n <= 0: return (0.0, 1.0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n)))
    return ((c - r) / d, (c + r) / d)

def caracteristiques(hM, hC, aM, aC, sMh=None, sCh=None, sMa=None, sCa=None, mu=None, cal=None):
    """Toutes les mesures de la fiche (mêmes formules que l'étude). hM, hC : buts marqués / encaissés par match du domicile À DOMICILE ; aM, aC : de l'extérieur À L'EXTÉRIEUR ;
    sMh, sCh, sMa, sCa : buts marqués / encaissés par match de chaque équipe sur TOUS les lieux de la saison ; mu : buts par équipe et par match du championnat ; cal : droite du xG.
    Les mesures de xG ne sont données que si toutes ces valeurs existent."""
    X1, X2 = hM + aC, aM + hC
    nan = float("nan")
    c = {"hM": hM, "hC": hC, "aM": aM, "aC": aC, "dM": hM - aM, "dC": hC - aC, "A1": hM - aC, "A2": aM - hC, "X1g": X1, "X2g": X2, "SM": hM + aM, "SC": hC + aC, "TG": X1 + X2,
         "rM": hM / aM if aM > 0 else nan, "rC": hC / aC if aC > 0 else nan, "rX": X1 / X2 if X2 > 0 else nan}
    if cal and None not in (sMh, sCh, sMa, sCa, mu):
        xAh, xDh = cal["am"] + cal["bm"] * sMh, cal["ae"] + cal["be"] * sCh
        xAa, xDa = cal["am"] + cal["bm"] * sMa, cal["ae"] + cal["be"] * sCa
        EH, EA = (xAh + xDa) / 2, (xAa + xDh) / 2
        c.update(sMh=sMh, sCh=sCh, sMa=sMa, sCa=sCa, EH=EH, EA=EA, ET=EH + EA, dE=EH - EA, rE=EH / EA if EA > 0 else nan, mu=mu, EHm=EH - mu, EAm=EA - mu, gH=X1 / 2 - EH, gA=X2 / 2 - EA)
    return c

def mesures(lieu_dom, lieu_ext, saison_dom, saison_ext, champ, zones=None):
    """lieu_dom : [(marqués, encaissés)] de l'équipe à domicile À DOMICILE ; lieu_ext : idem pour l'équipe à l'extérieur À L'EXTÉRIEUR (saison en cours, avant le match) ;
    saison_dom / saison_ext : {"buts_marques", "buts_encaisses"} moyennes sur TOUTE la saison (tous lieux) ; champ = (total de buts, nombre de matchs) du championnat avant le match.
    -> dict des mesures, ou None s'il manque 4 matchs au même lieu pour l'une des équipes. Sans xG ou sans 10 matchs de championnat, seuls les piliers sont donnés."""
    zones = zones or charger()
    if not lieu_dom or not lieu_ext or len(lieu_dom) < NMIN or len(lieu_ext) < NMIN: return None
    nd, ne = len(lieu_dom), len(lieu_ext)
    hM, hC = sum(m for m, _ in lieu_dom) / nd, sum(c for _, c in lieu_dom) / nd
    aM, aC = sum(m for m, _ in lieu_ext) / ne, sum(c for _, c in lieu_ext) / ne
    tot, nc = champ if champ else (0, 0)
    sd, se = saison_dom or {}, saison_ext or {}
    xg = zones and zones.get("calibration_xg") and nc >= NCHAMP_MIN and None not in (sd.get("buts_marques"), sd.get("buts_encaisses"), se.get("buts_marques"), se.get("buts_encaisses"))
    c = caracteristiques(hM, hC, aM, aC, *( (sd["buts_marques"], sd["buts_encaisses"], se["buts_marques"], se["buts_encaisses"], tot / (2 * nc)) if xg else (None,) * 5), cal=zones.get("calibration_xg") if zones else None)
    return {**c, "n_dom": nd, "n_ext": ne, "n_championnat": nc}

def dans(c, conditions):
    """Le match est dans l'intervalle si chaque condition [variable, bas, haut] est vraie : bas <= valeur < haut (None = sans borne). Valeur absente ou non numérique = non."""
    for f, lo, hi in conditions:
        x = (c or {}).get(f)
        if x is None or not isinstance(x, (int, float)) or x != x: return False
        if lo is not None and x < lo: return False
        if hi is not None and x >= hi: return False
    return True

def _vus(stats):
    """Réussis et matchs jamais vus pendant la recherche (2017-2020 et saison 2025-26 ensemble)."""
    s = sum((stats.get(j) or {}).get("s", 0) for j in ("test_2017_2020", "bloc_2025_26")); n = sum((stats.get(j) or {}).get("n", 0) for j in ("test_2017_2020", "bloc_2025_26"))
    return s, n

def evaluer(c, zones=None):
    """Marchés pour lesquels la fiche tombe dans au moins un intervalle retenu. -> liste triée du plus sûr au moins sûr (borne basse de Wilson sur les matchs jamais vus de l'intervalle).
    Chaque entrée : marche, seuil, version, conditions (de l'intervalle le plus sûr), valeurs, vus [réussis, matchs], taux_vu, marge, nb_intervalles."""
    zones = zones or charger(); out = []
    if not zones or not c: return out
    for nom, M in zones["marches"].items():
        bons = [z for z in M["intervalles"] if dans(c, z["conditions"])]
        if not bons: continue
        def cle(z): s, n = _vus(z["stats"]); return wilson(s, n)[0]
        z = max(bons, key=cle); s, n = _vus(z["stats"]); lo = wilson(s, n)[0]
        out.append({"etude": nom, "marche": M["marche"], "seuil": M["seuil"], "version": M["version"], "nb_intervalles": len(bons),
                    "conditions": [{"variable": f, "libelle": LIBELLES.get(f, f), "bas": lo_, "haut": hi_, "valeur": round(c[f], 3)} for f, lo_, hi_ in z["conditions"]],
                    "vus": [s, n], "taux_vu": round(s / n, 4) if n else None, "marge": round(lo, 4)})
    out.sort(key=lambda e: (-e["marge"], e["marche"]))
    return out

def resume(zones=None):
    """Résumé écrit dans la page : par marché, seuil, version, nombre d'intervalles et réussite de l'ensemble sur les matchs jamais vus."""
    zones = zones or charger()
    if not zones: return None
    out = {}
    for nom, M in zones["marches"].items():
        st = M["stats"]; vus = [[st[j]["reussis"], st[j]["matchs"]] for j in ("test_2017_2020", "bloc_2025_26")]
        out[nom] = {"marche": M["marche"], "seuil": M["seuil"], "version": M["version"], "intervalles": len(M["intervalles"]), "test_2017_2020": vus[0], "bloc_2025_26": vus[1],
                    "part_test_2017_2020": st["test_2017_2020"]["part_des_matchs"]}
    return {"gele_le": zones.get("gele_le"), "marches": out}
