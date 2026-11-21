# -*- coding: utf-8 -*-
"""Étude « le double des buts marqués + une meilleure défense » (21/11/2026), pour l'onglet « Étude » d'Analyse Verdict.

Condition (règle de Patrick) : une équipe marque au moins le double des buts par match de son adversaire ET en encaisse moins (moyennes de la saison en cours, avant le match ;
au moins 4 matchs au même lieu pour chaque équipe). Elle est mesurée sur les matchs DÉJÀ JOUÉS (data/bloc_saisons), jamais sur des matchs à venir.
Défense : trois catégories d'écart (buts encaissés par l'adversaire moins ceux de l'équipe) :
  mince = de 0 à 0,8 but (seuil donné par Patrick) ; moyen = de 0,8 au seuil « grand » ; grand = au-delà. Le seuil « grand » est la médiane des écarts supérieurs ou égaux à 0,8 dans l'étude (il vient des données).
Pour chaque case (lieu × catégorie × marché), l'étude donne le taux de réussite. Un marché n'est retenu que s'il dépasse 70 % dans l'étude (seuil de Patrick) ; sinon : pas de preuve, pas de pari (NO DATA -> NO GO).
Marchés étudiés : victoire, double chance, l'équipe marque +0,5 / +1,5, double chance + plus de 1,5 buts, double chance + moins de 4,5 buts. Aucun autre marché n'est affiché par l'onglet.
Commande : python verif_etude.py  (relit l'étude et réécrit data/verif_pronostics/etude_regles.json)."""
import gzip, json, os, statistics, sys
from collections import defaultdict

RACINE = os.path.dirname(os.path.abspath(__file__))
BLOC = os.path.join(RACINE, "data", "bloc_saisons", "bloc_2526_2627.json.gz")
CHEMIN = os.path.join(RACINE, "data", "verif_pronostics", "etude_regles.json")
NMIN = 4                    # règle de Patrick : 4 matchs au même lieu minimum pour chaque équipe
ECART_MINCE_MAX = 0.8       # donné par Patrick (21/11/2026)
RETENU_MIN = 0.70           # donné par Patrick : seuil sur les résultats de l'étude
DOUBLE = 2.0                # « le double des buts marqués » : condition de Patrick
CATEGORIES = ("mince", "moyen", "grand")
LIEUX = ("dom", "ext")

# marché de l'étude -> (condition sur le score vu par l'équipe : buts marqués gf, encaissés ga, marché de la page si elle joue à domicile, à l'extérieur)
MARCHES = {
    "victoire": (lambda gf, ga: gf > ga, "1", "2"),
    "double_chance": (lambda gf, ga: gf >= ga, "1N", "N2"),
    "equipe_plus_0.5": (lambda gf, ga: gf >= 1, "dom_plus_0.5", "ext_plus_0.5"),
    "equipe_plus_1.5": (lambda gf, ga: gf >= 2, "dom_plus_1.5", "ext_plus_1.5"),
    "dc_plus_1.5": (lambda gf, ga: gf >= ga and gf + ga >= 2, "1N&total_plus_1.5", "N2&total_plus_1.5"),
    "dc_moins_4.5": (lambda gf, ga: gf >= ga and gf + ga <= 4, "1N&total_moins_4.5", "N2&total_moins_4.5"),
}
MARCHE_PAGE = {(lieu, m): MARCHES[m][1 if lieu == "dom" else 2] for m in MARCHES for lieu in LIEUX}
ETUDE_DE_MARCHE = {(lieu, MARCHES[m][1 if lieu == "dom" else 2]): m for m in MARCHES for lieu in LIEUX}

def condition(gf_a, ga_a, gf_b, ga_b):
    """L'équipe A a-t-elle le double des buts marqués de B et une meilleure défense (strictement moins de buts encaissés) ? Une moyenne nulle ou absente ne qualifie pas."""
    if None in (gf_a, ga_a, gf_b, ga_b) or gf_a <= 0: return False
    return gf_a >= DOUBLE * gf_b and ga_a < ga_b

def categorie(ecart, grand_min):
    """Catégorie de l'écart de défense (buts encaissés de l'adversaire - ceux de l'équipe) ; None s'il n'y a pas d'écart en faveur de l'équipe."""
    if ecart is None or ecart <= 0: return None
    return "mince" if ecart < ECART_MINCE_MAX else ("moyen" if ecart < grand_min else "grand")

def cas_joues(liste):
    """Cas de l'étude sur les matchs joués, dans l'ordre du temps : moyennes de la saison AVANT chaque match (aucune fuite). -> liste de {lieu, ecart, gf, ga}"""
    L = sorted((m for m in liste if m.get("buts_dom") is not None and m.get("buts_ext") is not None), key=lambda m: m["date"])
    H = defaultdict(list); cas = []
    def moy(k):
        h = H[k]
        if not h: return (0, 0.0, 0.0, 0, 0)
        return (len(h), sum(x[0] for x in h) / len(h), sum(x[1] for x in h) / len(h), sum(1 for x in h if x[2]), sum(1 for x in h if not x[2]))
    for m in L:
        s, a, b, gd, ge = m["saison"], m["domicile"], m["exterieur"], m["buts_dom"], m["buts_ext"]
        A, B = moy((s, a)), moy((s, b))
        if A[3] >= NMIN and B[4] >= NMIN:
            for lieu, T, O, gf, ga in (("dom", A, B, gd, ge), ("ext", B, A, ge, gd)):
                if condition(T[1], T[2], O[1], O[2]): cas.append({"lieu": lieu, "ecart": round(O[2] - T[2], 9), "gf": gf, "ga": ga})   # arrondi : 1,4 - 0,6 doit valoir 0,8 et non 0,7999999
        H[(s, a)].append((gd, ge, True)); H[(s, b)].append((ge, gd, False))
    return cas

def calculer(chemin_bloc=BLOC):
    d = json.load(gzip.open(chemin_bloc)); liste = d["liste"]; cas = cas_joues(liste)
    grand_min = statistics.median(sorted(c["ecart"] for c in cas if c["ecart"] >= ECART_MINCE_MAX))
    cell = {lieu: {cat: {"n": 0, "marches": {m: {"reussis": 0} for m in MARCHES}} for cat in CATEGORIES} for lieu in LIEUX}
    for c in cas:
        g = cell[c["lieu"]][categorie(c["ecart"], grand_min)]; g["n"] += 1
        for m, (f, _, _) in MARCHES.items(): g["marches"][m]["reussis"] += bool(f(c["gf"], c["ga"]))
    for lieu in LIEUX:
        for cat in CATEGORIES:
            g = cell[lieu][cat]
            for m, x in g["marches"].items():
                x["taux"] = round(x["reussis"] / g["n"], 4) if g["n"] else None; x["retenu"] = bool(g["n"] and x["reussis"] / g["n"] > RETENU_MIN)
    jours = [m["date"] for m in liste if m.get("buts_dom") is not None]
    return {"version": 1, "source": {"fichier": "data/bloc_saisons/bloc_2526_2627.json.gz", "matchs_joues": len(jours), "du": min(jours), "au": max(jours), "cas": len(cas)},
            "condition": "une équipe marque au moins le double des buts par match de son adversaire et encaisse moins (saison en cours, avant le match, 4 matchs minimum au même lieu)",
            "seuils": {"ecart_mince_max": ECART_MINCE_MAX, "ecart_grand_min": round(grand_min, 4), "retenu_min": RETENU_MIN,
                       "origine": "0,8 et 70 % : décisions de Patrick (21/11/2026) ; seuil « grand » = médiane des écarts >= 0,8 dans l'étude"},
            "cellules": cell}

def ecrire(chemin=CHEMIN, chemin_bloc=BLOC):
    r = calculer(chemin_bloc); os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f: json.dump(r, f, ensure_ascii=False, indent=1)
    return r

def charger(chemin=CHEMIN):
    try:
        with open(chemin, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return None

def evaluer(SA, SB, n_dom, n_ext, etude):
    """Match A (domicile) - B (extérieur) : la condition est-elle remplie, pour qui, avec quelle catégorie d'écart ? -> dict ou None.
    SA, SB : moyennes de saison (buts_marques, buts_encaisses) ; n_dom, n_ext : matchs au même lieu."""
    if not etude or min(n_dom or 0, n_ext or 0) < NMIN: return None
    gm = etude["seuils"]["ecart_grand_min"]
    for lieu, T, O, nom in (("dom", SA, SB, None), ("ext", SB, SA, None)):
        if condition(T.get("buts_marques"), T.get("buts_encaisses"), O.get("buts_marques"), O.get("buts_encaisses")):
            ecart = round(O["buts_encaisses"] - T["buts_encaisses"], 9); cat = categorie(ecart, gm)
            if cat: return {"lieu": lieu, "ecart": cat, "valeur_ecart": round(ecart, 3), "marques": [round(T["buts_marques"], 3), round(O["buts_marques"], 3)],
                            "encaisses": [round(T["buts_encaisses"], 3), round(O["buts_encaisses"], 3)]}
    return None

def marquer(paris, info, etude):
    """Marque (clé « etude ») les paris de la page qui sont retenus par l'étude pour ce match : marché étudié, dans la case (lieu, catégorie) où son taux dépasse 70 %. -> nombre de paris marqués."""
    if not info: return 0
    case = etude["cellules"][info["lieu"]][info["ecart"]]; n = 0
    for famille in paris.values():
        for p in famille:
            m = ETUDE_DE_MARCHE.get((info["lieu"], p["marche"]))
            if m and case["marches"][m]["retenu"]:
                p["etude"] = {"taux": case["marches"][m]["taux"], "n": case["n"], "ecart": info["ecart"], "lieu": info["lieu"]}; n += 1
    return n

def resume(etude):
    """Ce que la page affiche de l'étude : sources, seuils et, pour chaque case, les marchés retenus (du plus au moins réussi)."""
    if not etude: return None
    L = []
    for lieu in LIEUX:
        for cat in CATEGORIES:
            c = etude["cellules"][lieu][cat]
            L.append({"lieu": lieu, "ecart": cat, "n": c["n"], "marches": sorted(({"marche": MARCHE_PAGE[(lieu, m)], "etude": m, "taux": x["taux"]} for m, x in c["marches"].items() if x["retenu"]), key=lambda x: -x["taux"])})
    return {"source": etude["source"], "seuils": etude["seuils"], "cases": L}

if __name__ == "__main__":
    r = ecrire(); print(json.dumps({"cas": r["source"]["cas"], "seuil_grand": r["seuils"]["ecart_grand_min"], "retenus": sum(x["retenu"] for l in r["cellules"].values() for c in l.values() for x in c["marches"].values())}, ensure_ascii=False))
