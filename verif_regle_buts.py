# -*- coding: utf-8 -*-
"""Règle de buts de Patrick (21/11/2026), pour l'onglet « +1,5 buts » d'Analyse Verdict.

Règle (ses valeurs) : au moins 4 matchs au même lieu pour chaque équipe (domicile pour l'une, extérieur pour l'autre) ;
somme des buts MARQUÉS par match des deux équipes (chacune à son lieu, saison en cours, avant le match) >= 3,5
ET somme des buts ENCAISSÉS par match >= 2,8. Le marché de l'onglet est « plus de 1,5 buts » seulement, à cote >= 1,24 (sa décision).
Étude sur les matchs DÉJÀ JOUÉS (data/bloc_saisons) : taux réel de +1,5 quand la règle est remplie, comparé au taux hors règle ;
la cote minimale 1,24 vient de la borne basse de l'intervalle de confiance (cote d'équilibre prudente).
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

def remplie(marques, encaisses, n_dom, n_ext):
    """La règle est-elle remplie ? marques/encaisses : sommes des moyennes des deux équipes. Valeur absente ou moins de 4 matchs = non."""
    if None in (marques, encaisses) or min(n_dom or 0, n_ext or 0) < NMIN: return False
    return marques >= MARQUES_MIN and encaisses >= ENCAISSES_MIN

def evaluer(A, B):
    """A (domicile) et B (extérieur) : dictionnaires de constat() avec n, buts_marques, buts_encaisses (même lieu). -> dict si la règle est remplie, sinon None."""
    if not A or not B or A.get("buts_marques") is None or B.get("buts_marques") is None or A.get("buts_encaisses") is None or B.get("buts_encaisses") is None: return None
    S, E = A["buts_marques"] + B["buts_marques"], A["buts_encaisses"] + B["buts_encaisses"]
    if not remplie(S, E, A.get("n"), B.get("n")): return None
    return {"marques": round(S, 3), "encaisses": round(E, 3), "n_dom": A["n"], "n_ext": B["n"]}

def wilson(k, n, z=Z95):
    if n == 0: return (0.0, 0.0)
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)

def cas_joues(liste):
    """Matchs joués avec >= 4 matchs au même lieu pour chaque équipe, dans l'ordre du temps : sommes de la saison AVANT chaque match (aucune fuite). -> [{marques, encaisses, total, date}]"""
    L = sorted((m for m in liste if m.get("buts_dom") is not None and m.get("buts_ext") is not None), key=lambda m: m["date"])
    H = defaultdict(list); cas = []
    def moy(k):
        h = H[k]; n = len(h)
        return (n, sum(x[0] for x in h) / n, sum(x[1] for x in h) / n) if n else (0, 0.0, 0.0)
    for m in L:
        s, a, b, gd, ge = m["saison"], m["domicile"], m["exterieur"], m["buts_dom"], m["buts_ext"]
        A, B = moy((s, a, "d")), moy((s, b, "e"))
        if A[0] >= NMIN and B[0] >= NMIN: cas.append({"marques": A[1] + B[1], "encaisses": A[2] + B[2], "total": gd + ge, "date": m["date"]})
        H[(s, a, "d")].append((gd, ge)); H[(s, b, "e")].append((ge, gd))
    return cas

def calculer(chemin_bloc=BLOC):
    d = json.load(gzip.open(chemin_bloc)); liste = d["liste"]; cas = cas_joues(liste)
    R = [c for c in cas if remplie(c["marques"], c["encaisses"], NMIN, NMIN)]; H = [c for c in cas if not remplie(c["marques"], c["encaisses"], NMIN, NMIN)]
    kr, kh = sum(c["total"] >= 2 for c in R), sum(c["total"] >= 2 for c in H)
    lo, hi = wilson(kr, len(R)); jours = [m["date"] for m in liste if m.get("buts_dom") is not None]
    return {"version": 1, "source": {"fichier": "data/bloc_saisons/bloc_2526_2627.json.gz", "matchs_joues": len(jours), "du": min(jours), "au": max(jours), "matchs_evaluables": len(cas)},
            "regle": {"n_min": NMIN, "marques_min": MARQUES_MIN, "encaisses_min": ENCAISSES_MIN, "marche": MARCHE, "cote_min": COTE_MIN,
                      "origine": "3,5, 2,8, 4 matchs et cote 1,24 : décisions de Patrick (21/11/2026)"},
            "etude": {"matchs": len(R), "reussis": kr, "taux": round(kr / len(R), 4) if R else None, "borne_basse": round(lo, 4), "borne_haute": round(hi, 4),
                      "cote_equilibre": round(len(R) / kr, 3) if kr else None, "cote_equilibre_prudente": round(1 / lo, 3) if lo else None,
                      "hors_regle": {"matchs": len(H), "reussis": kh, "taux": round(kh / len(H), 4) if H else None}}}

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
