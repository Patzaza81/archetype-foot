# -*- coding: utf-8 -*-
"""Règle « plus de 2,5 buts » (étude du 23/11/2026, refaite le 24/11/2026 sur un grand échantillon, demande de Patrick), pour l'onglet « +2,5 buts » d'Analyse Verdict.

Paramètres de Patrick : buts marqués et encaissés de chaque équipe (au même lieu et sur la saison), comparés entre les deux équipes, et la moyenne de buts du championnat.
Un modèle (régression logistique, 29 mesures tirées de ces paramètres, valeurs extrêmes ramenées aux bornes 0,5 % - 99,5 % de l'apprentissage) donne la probabilité de 3 buts ou plus. Il est appris UNE FOIS sur 49 000 matchs (2000 à 2012), gelé dans
data/verif_pronostics/modele_plus25.json, puis le seuil de probabilité est le plus petit dont la précision sur 2013-2016 atteint 70 % (cible de Patrick, comme le moteur Gamma).
Vérifié sur des matchs jamais vus : 2017-2021 et saisons 2025-2026 (voir le fichier du modèle et regle_plus25.json).
Un match est retenu si : 4 matchs au même lieu pour chaque équipe, 10 matchs de championnat, probabilité >= seuil. La cote vient à la fin : de COTE_MIN (1,26) à COTE_MAX (1,45).
Aucun seuil n'est posé à la main. Commande : python verif_regle_plus25.py  (relit les matchs joués et réécrit data/verif_pronostics/regle_plus25.json)."""
import gzip, json, math, os
from collections import defaultdict

RACINE = os.path.dirname(os.path.abspath(__file__))
BLOC = os.path.join(RACINE, "data", "bloc_saisons", "bloc_2526_2627.json.gz")
CHEMIN = os.path.join(RACINE, "data", "verif_pronostics", "regle_plus25.json")
CHEMIN_MODELE = os.path.join(RACINE, "data", "verif_pronostics", "modele_plus25.json")
MARCHE = "total_plus_2.5"
NMIN = 4              # règle de Patrick : 4 matchs minimum au même lieu pour chaque équipe
NCHAMP_MIN = 10       # moyenne du championnat lue sur au moins 10 matchs précédents (comme dans l'étude)
COTE_MAX = 1.45       # 24/11/2026 : cote maximale (le marché est d'accord) ; fixée sur l'étude 2025-2026 (rupture de précision entre 1,35-1,45 et 1,45-1,6), reconfirmée avec le modèle sur des matchs jamais vus (74,5 % sous 1,45, 43,1 % au-dessus) ; cotes Betpawa = Football-Data (rapport médian 1,00 sur 177 matchs communs)
COTE_MIN = 1.26
Z95 = 1.96
EPS = 1e-9

_MODELE = {}
def modele():
    """Le modèle gelé (coefficients, moyennes, échelles, seuil) ou None s'il manque."""
    if "m" not in _MODELE:
        try:
            with open(CHEMIN_MODELE, encoding="utf-8") as f: _MODELE["m"] = json.load(f)
        except (OSError, ValueError): _MODELE["m"] = None
    return _MODELE["m"]

def _part(L, f):
    return sum(1 for m, e in L if f(m, e)) / len(L)

def traits(lieu_dom, lieu_ext, saison_dom, saison_ext, champ):
    """Les 29 mesures du modèle. lieu_dom : [(marqués, encaissés)] de l'équipe à domicile À DOMICILE ; lieu_ext : idem pour l'équipe à l'extérieur À L'EXTÉRIEUR ;
    saison_* : {"buts_marques", "buts_encaisses"} (moyennes par match, toute la saison) ; champ = (total de buts, matchs, matchs à 3 buts ou plus) du championnat avant le match.
    -> dict, ou None si une donnée manque."""
    if not lieu_dom or not lieu_ext or not champ or len(champ) < 3 or not champ[1]: return None
    S = [saison_dom, saison_ext]
    if any(not x or x.get("buts_marques") is None or x.get("buts_encaisses") is None for x in S): return None
    nd, ne = len(lieu_dom), len(lieu_ext)
    hM, hC = sum(m for m, _ in lieu_dom) / nd, sum(e for _, e in lieu_dom) / nd
    aM, aC = sum(m for m, _ in lieu_ext) / ne, sum(e for _, e in lieu_ext) / ne
    t3 = lambda m, e: m + e >= 3; sc = lambda m, e: m >= 1; cn = lambda m, e: e >= 1; bt = lambda m, e: m >= 1 and e >= 1
    pool = lambda f: (sum(1 for m, e in lieu_dom if f(m, e)) + sum(1 for m, e in lieu_ext if f(m, e))) / (nd + ne)
    hgd = S[0]["buts_marques"] - S[0]["buts_encaisses"]; agd = S[1]["buts_marques"] - S[1]["buts_encaisses"]
    return {"L": champ[0] / champ[1], "pL": champ[2] / champ[1], "hM": hM, "hC": hC, "aM": aM, "aC": aC, "SM": hM + aM, "SC": hC + aC, "X1": hM + aC, "X2": aM + hC,
            "hf3": _part(lieu_dom, t3), "af3": _part(lieu_ext, t3), "f3": pool(t3), "hsc": _part(lieu_dom, sc), "asc": _part(lieu_ext, sc), "hcn": _part(lieu_dom, cn), "acn": _part(lieu_ext, cn),
            "hbt": _part(lieu_dom, bt), "abt": _part(lieu_ext, bt), "bt": pool(bt), "hgd": hgd, "agd": agd, "hsM": S[0]["buts_marques"], "hsC": S[0]["buts_encaisses"],
            "asM": S[1]["buts_marques"], "asC": S[1]["buts_encaisses"], "gdd": hgd - agd, "dM": hM - aM, "dC": aC - hC}

def proba(t):
    """Probabilité (modèle gelé) de 3 buts ou plus à partir des traits ; None si les traits ou le modèle manquent."""
    M = modele()
    if not t or not M: return None
    lo, hi = M.get("bornes_bas") or [-math.inf] * len(M["F"]), M.get("bornes_haut") or [math.inf] * len(M["F"])      # valeurs extrêmes ramenées aux bornes de l'apprentissage (0,5 % et 99,5 %)
    z = M["intercept"] + sum(c * (min(max(t[f], b), h) - mu) / sd for f, c, mu, sd, b, h in zip(M["F"], M["coef"], M["mean"], M["scale"], lo, hi))
    return 1 / (1 + math.exp(-z))

def mesures(lieu_dom, lieu_ext, saison_dom, saison_ext, champ):
    """-> dict : nombre de matchs, probabilité du modèle et quelques mesures lisibles. Ne juge pas la règle (remplie() juge)."""
    nd, ne = len(lieu_dom or []), len(lieu_ext or [])
    tot, nc = (champ[0], champ[1]) if champ else (0, 0)
    t = traits(lieu_dom, lieu_ext, saison_dom, saison_ext, champ) if nd and ne else None
    p = proba(t)
    r = {"n_dom": nd, "n_ext": ne, "n_championnat": nc, "championnat": round(tot / nc, 3) if nc else None, "proba": None if p is None else round(p, 6)}
    if t:
        k = sum(1 for m, e in list(lieu_dom) + list(lieu_ext) if m + e >= 3)
        r.update({"dom_marques": round(t["hM"], 2), "dom_encaisses": round(t["hC"], 2), "ext_marques": round(t["aM"], 2), "ext_encaisses": round(t["aC"], 2), "plus25_matchs": [k, nd + ne]})
    return r

def remplie(x):
    """4 matchs au même lieu de chaque côté, 10 matchs de championnat, probabilité du modèle >= seuil. Donnée absente = non."""
    M = modele()
    if not x or not M or min(x.get("n_dom") or 0, x.get("n_ext") or 0) < NMIN or (x.get("n_championnat") or 0) < NCHAMP_MIN or x.get("proba") is None: return False
    return x["proba"] >= M["seuil"] - EPS

def wilson(k, n, z=Z95):
    if n == 0: return (0.0, 0.0)
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)

def cas_joues(liste):
    """Matchs joués, dans l'ordre du temps, avec les valeurs de la règle calculées sur les matchs des JOURS PRÉCÉDENTS seulement (aucune fuite).
    -> [{date, total, cote (plus de 2,5, moyenne clôture ou None), **mesures}] pour les matchs où chaque équipe a 4 matchs au même lieu."""
    L = sorted((m for m in liste if m.get("buts_dom") is not None and m.get("buts_ext") is not None), key=lambda m: (m["date"], m.get("id", "")))
    LIEU = defaultdict(list); TOUS = defaultdict(list); CH = defaultdict(lambda: [0, 0, 0]); attente = []; jour = None; cas = []
    for m in L:
        if m["date"] != jour:
            for k, h, a, g1, g2 in attente:
                LIEU[k + (h, "d")].append((g1, g2)); LIEU[k + (a, "e")].append((g2, g1)); TOUS[k + (h,)].append((g1, g2)); TOUS[k + (a,)].append((g2, g1)); CH[k][0] += g1 + g2; CH[k][1] += 1; CH[k][2] += int(g1 + g2 >= 3)
            attente = []; jour = m["date"]
        k = (m.get("division"), m.get("saison")); h, a, g1, g2 = m["domicile"], m["exterieur"], m["buts_dom"], m["buts_ext"]
        attente.append((k, h, a, g1, g2))
        ld, le = LIEU[k + (h, "d")], LIEU[k + (a, "e")]
        if len(ld) < NMIN or len(le) < NMIN: continue
        sa = lambda T: {"buts_marques": sum(x[0] for x in T) / len(T), "buts_encaisses": sum(x[1] for x in T) / len(T)}
        x = mesures(ld, le, sa(TOUS[k + (h,)]), sa(TOUS[k + (a,)]), tuple(CH[k]))
        ou = (((m.get("cotes") or {}).get("plus_moins_2_5_cloture") or {}).get("moy") or [None])[0]
        cas.append({"date": m["date"], "total": g1 + g2, "cote": ou, **x})
    return cas

def _stats(Z, cote_min=None):
    if cote_min is not None: Z = [c for c in Z if c["cote"] is not None and cote_min <= c["cote"] <= COTE_MAX + EPS]
    k = sum(c["total"] >= 3 for c in Z); n = len(Z); lo, hi = wilson(k, n); C = [c["cote"] for c in Z if c["cote"] is not None]
    return {"matchs": n, "reussis": k, "taux": round(k / n, 4) if n else None, "borne_basse": round(lo, 4), "borne_haute": round(hi, 4), "cote_moyenne": round(sum(C) / len(C), 3) if C else None}

def calculer(chemin_bloc=BLOC, cote_min=COTE_MIN):
    """Matchs 2025-2026 du bloc : AUCUN n'a servi à apprendre le modèle (appris sur 2000-2012), tous sont donc des matchs jamais vus."""
    d = json.load(gzip.open(chemin_bloc)); liste = d["liste"]; cas = cas_joues(liste)
    jours = [m["date"] for m in liste if m.get("buts_dom") is not None]
    R = [c for c in cas if remplie(c)]; H = [c for c in cas if not remplie(c)]; M = modele() or {}
    et = _stats(R)
    et.update(non_vus=_stats(R), non_vus_cote_min=_stats(R, cote_min), hors_regle={k: v for k, v in _stats(H).items() if k in ("matchs", "reussis", "taux")},
              tous_non_vus={k: v for k, v in _stats(cas).items() if k in ("matchs", "reussis", "taux")}, grands_echantillons=M.get("validation"))
    return {"version": 4, "source": {"fichier": "data/bloc_saisons/bloc_2526_2627.json.gz", "matchs_joues": len(jours), "du": min(jours), "au": max(jours), "matchs_evaluables": len(cas)},
            "regle": {"marche": MARCHE, "n_min": NMIN, "n_championnat_min": NCHAMP_MIN, "seuil_proba": M.get("seuil"), "cote_min": cote_min, "cote_max": COTE_MAX,
                      "origine": "modèle appris sur 2000-2012 (49 000 matchs), seuil = plus petit dont la précision sur 2013-2016 atteint 70 % (cible de Patrick), vérifié sur 2017-2021 et 2025-2026 ; cote à la fin (Patrick, 23/11/2026)"},
            "etude": et}

def ecrire(chemin=CHEMIN, chemin_bloc=BLOC):
    r = calculer(chemin_bloc); os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f: json.dump(r, f, ensure_ascii=False, indent=1)
    return r

def charger(chemin=CHEMIN):
    try:
        with open(chemin, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return None

if __name__ == "__main__":
    r = ecrire(); print(json.dumps(r["etude"], ensure_ascii=False))
