# -*- coding: utf-8 -*-
"""Règle de buts de Patrick (21/11/2026), pour l'onglet « +1,5 buts » d'Analyse Verdict.

Règle (ses valeurs) : au moins 4 matchs au même lieu pour chaque équipe (domicile pour l'une, extérieur pour l'autre) ;
somme des buts MARQUÉS par match des deux équipes (chacune à son lieu, saison en cours, avant le match) >= 3,5
ET somme des buts ENCAISSÉS par match >= 2,8. Le marché de l'onglet est « plus de 1,5 buts » seulement, à cote >= 1,24 (sa décision).
Étude sur les matchs DÉJÀ JOUÉS (data/bloc_saisons) : taux réel de +1,5 quand la règle est remplie, comparé au taux hors règle ;
la cote minimale 1,24 vient de la borne basse de l'intervalle de confiance (cote d'équilibre prudente).
Filtre du championnat (22/11/2026) : le match n'est retenu que si, dans son championnat, au moins SEUIL des matchs PRÉCÉDENTS ont compté 2 buts ou plus (taux lissé vers le taux général
pour les championnats peu joués). Le seuil n'est pas posé à la main : il est CHOISI sur la première moitié de la période (meilleure borne basse de l'intervalle, au moins 100 matchs de la règle)
puis VÉRIFIÉ sur la seconde moitié, jamais vue pour ce choix. Il vaut uniquement pour le marché « plus de 1,5 buts » du match.
Commande : python verif_regle_buts.py  (relit l'étude et réécrit data/verif_pronostics/regle_buts.json)."""
import gzip, json, math, os
from collections import defaultdict

RACINE = os.path.dirname(os.path.abspath(__file__))
BLOC = os.path.join(RACINE, "data", "bloc_saisons", "bloc_2526_2627.json.gz")
CHEMIN = os.path.join(RACINE, "data", "verif_pronostics", "regle_buts.json")
NMIN = 4              # règle de Patrick : 4 matchs minimum au même lieu pour chaque équipe
MARQUES_MIN = 3.5     # Patrick (21/11/2026) : somme des buts marqués par match des deux équipes
ENCAISSES_MIN = 2.8   # Patrick (21/11/2026) : somme des buts encaissés par match des deux équipes
COTE_MIN = 1.24       # Patrick (21/11/2026) : cote minimale du +1,5 de cet onglet
MARCHE = "total_plus_1.5"
Z95 = 1.96
POIDS = 10            # poids (en matchs) du taux général dans le taux d'un championnat : évite un taux extrême quand le championnat compte peu de matchs
GRILLE = [x / 100 for x in range(50, 96)]   # seuils essayés pour le championnat
N_SEUIL = 100         # au moins 100 matchs de la règle pour qu'un seuil soit retenu sur la première moitié

def remplie(marques, encaisses, n_dom, n_ext):
    """La règle est-elle remplie ? marques/encaisses : sommes des moyennes des deux équipes. Valeur absente ou moins de 4 matchs = non."""
    if None in (marques, encaisses) or min(n_dom or 0, n_ext or 0) < NMIN: return False
    return marques >= MARQUES_MIN and encaisses >= ENCAISSES_MIN

def taux_champ(k, n, base, poids=POIDS):
    """Taux de matchs à 2 buts ou plus d'un championnat : k matchs sur n précédents, lissé vers le taux général `base` (poids `poids` matchs)."""
    return (k + base * poids) / (n + poids)

def evaluer(A, B, champ=None, regle=None):
    """A (domicile) et B (extérieur) : dictionnaires de constat() avec n, buts_marques, buts_encaisses (même lieu). -> dict si la règle est remplie, sinon None.
    champ = (k, n) : matchs à 2 buts ou plus et matchs précédents du championnat ; regle = le fichier de l'étude. Si l'étude a un seuil de championnat, il est exigé (pas de donnée = pas de pari)."""
    if not A or not B or A.get("buts_marques") is None or B.get("buts_marques") is None or A.get("buts_encaisses") is None or B.get("buts_encaisses") is None: return None
    S, E = A["buts_marques"] + B["buts_marques"], A["buts_encaisses"] + B["buts_encaisses"]
    if not remplie(S, E, A.get("n"), B.get("n")): return None
    out = {"marques": round(S, 3), "encaisses": round(E, 3), "n_dom": A["n"], "n_ext": B["n"]}
    ch = (regle or {}).get("championnat")
    if ch:
        if not champ or not champ[1]: return None
        t = taux_champ(champ[0], champ[1], ch["base"], ch.get("poids", POIDS))
        if t < ch["seuil"]: return None
        out.update(taux_championnat=round(t, 4), n_championnat=champ[1])
    return out

def wilson(k, n, z=Z95):
    if n == 0: return (0.0, 0.0)
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)

def cas_joues(liste):
    """Matchs joués avec >= 4 matchs au même lieu pour chaque équipe, dans l'ordre du temps : sommes de la saison AVANT chaque match (aucune fuite).
    -> [{marques, encaisses, total, date, comp, k_champ, n_champ}] ; k_champ / n_champ = matchs à 2 buts ou plus / matchs du championnat joués les jours PRÉCÉDENTS."""
    L = sorted((m for m in liste if m.get("buts_dom") is not None and m.get("buts_ext") is not None), key=lambda m: m["date"])
    H = defaultdict(list); C = defaultdict(lambda: [0, 0]); attente = []; jour = None; cas = []
    def moy(k):
        h = H[k]; n = len(h)
        return (n, sum(x[0] for x in h) / n, sum(x[1] for x in h) / n) if n else (0, 0.0, 0.0)
    for m in L:
        if m["date"] != jour:                                  # le championnat ne compte que les jours PRÉCÉDENTS : on l'met à jour à chaque nouveau jour
            for comp, tot in attente: C[comp][0] += tot >= 2; C[comp][1] += 1
            attente = []; jour = m["date"]
        s, a, b, gd, ge, comp = m["saison"], m["domicile"], m["exterieur"], m["buts_dom"], m["buts_ext"], m.get("competition")
        A, B = moy((s, a, "d")), moy((s, b, "e"))
        if A[0] >= NMIN and B[0] >= NMIN: cas.append({"marques": A[1] + B[1], "encaisses": A[2] + B[2], "total": gd + ge, "date": m["date"], "comp": comp, "k_champ": C[comp][0], "n_champ": C[comp][1]})
        H[(s, a, "d")].append((gd, ge)); H[(s, b, "e")].append((ge, gd)); attente.append((comp, gd + ge))
    return cas

def _stats(Z):
    k = sum(c["total"] >= 2 for c in Z); n = len(Z); lo, hi = wilson(k, n)
    return {"matchs": n, "reussis": k, "taux": round(k / n, 4) if n else None, "borne_basse": round(lo, 4), "borne_haute": round(hi, 4)}

def calculer(chemin_bloc=BLOC):
    d = json.load(gzip.open(chemin_bloc)); liste = d["liste"]; cas = cas_joues(liste)
    jours = [m["date"] for m in liste if m.get("buts_dom") is not None]
    coupure = cas[len(cas) // 2]["date"]                                                  # 1re moitié : choix du seuil ; 2e moitié : vérification
    base = sum(c["total"] >= 2 for c in cas if c["date"] < coupure) / max(1, sum(c["date"] < coupure for c in cas))
    for c in cas: c["taux_champ"] = taux_champ(c["k_champ"], c["n_champ"], base)
    R = [c for c in cas if remplie(c["marques"], c["encaisses"], NMIN, NMIN)]; H = [c for c in cas if not remplie(c["marques"], c["encaisses"], NMIN, NMIN)]
    R1 = [c for c in R if c["date"] < coupure]; seuil, meilleur = None, -1.0
    for t in GRILLE:
        S = [c for c in R1 if c["taux_champ"] >= t]
        if len(S) >= N_SEUIL:
            lo = wilson(sum(c["total"] >= 2 for c in S), len(S))[0]
            if lo > meilleur: seuil, meilleur = t, lo
    F = [c for c in R if seuil is not None and c["taux_champ"] >= seuil]
    et = _stats(F if seuil is not None else R); et["hors_regle"] = {k: v for k, v in _stats(H).items() if k in ("matchs", "reussis", "taux")}
    et["regle_seule"] = _stats(R)
    et["cote_equilibre"] = round(et["matchs"] / et["reussis"], 3) if et["reussis"] else None; et["cote_equilibre_prudente"] = round(1 / et["borne_basse"], 3) if et["borne_basse"] else None
    et["verification"] = {"coupure": coupure, "choix_du_seuil": _stats([c for c in F if c["date"] < coupure]), "seconde_moitie_non_vue": _stats([c for c in F if c["date"] >= coupure]),
                          "regle_seule_seconde_moitie": _stats([c for c in R if c["date"] >= coupure])}
    out = {"version": 2, "source": {"fichier": "data/bloc_saisons/bloc_2526_2627.json.gz", "matchs_joues": len(jours), "du": min(jours), "au": max(jours), "matchs_evaluables": len(cas)},
           "regle": {"n_min": NMIN, "marques_min": MARQUES_MIN, "encaisses_min": ENCAISSES_MIN, "marche": MARCHE, "cote_min": COTE_MIN,
                     "origine": "3,5, 2,8, 4 matchs et cote 1,24 : décisions de Patrick (21/11/2026)"},
           "etude": et}
    if seuil is not None:
        out["championnat"] = {"seuil": seuil, "base": round(base, 4), "poids": POIDS, "n_min_choix": N_SEUIL,
                              "origine": "seuil choisi sur la première moitié de la période (meilleure borne basse, >= 100 matchs de la règle), vérifié sur la seconde ; Patrick demande un filtre de championnat (22/11/2026)"}
    return out

def ecrire(chemin=CHEMIN, chemin_bloc=BLOC):
    r = calculer(chemin_bloc); os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f: json.dump(r, f, ensure_ascii=False, indent=1)
    return r

def charger(chemin=CHEMIN):
    try:
        with open(chemin, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return None

if __name__ == "__main__":
    r = ecrire(); print(json.dumps({"etude": r["etude"], "matchs_evaluables": r["source"]["matchs_evaluables"]}, ensure_ascii=False))
