# -*- coding: utf-8 -*-
"""Règles par marché du verdict (09/11/2026). Un pari dont la condition de marché n'est pas remplie perd un cran :
TIENT -> TIENT AVEC RÉSERVE -> NE TIENT PAS. Les seuils viennent des données réelles (config/verif_regles.json) ; seules les règles « actif » s'appliquent.
Commande d'audit : python verif_pronostic.py regles  (mesure chaque règle sur les deux moitiés des journées ; elle ne change rien seule : activer ou couper une règle est une décision, dans config/verif_regles.json)."""
import json, os

CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "verif_regles.json")
BAS = {"TIENT": "TIENT AVEC RÉSERVE", "TIENT AVEC RÉSERVE": "NE TIENT PAS"}
NOMS_TRAITS = {"xa": "xG attendu du domicile", "x_diff": "avance de xG du domicile", "champ_buts": "buts par équipe du championnat", "b_tot": "buts attendus au total",
               "tA": "réussite du domicile à domicile", "x_tot": "xG attendu au total", "x_min": "xG attendu du moins offensif", "tmin": "réussite de l'équipe la moins fiable"}

def charger(chemin=CHEMIN):
    try:
        with open(chemin, encoding="utf-8") as f: return json.load(f)["regles"]
    except (OSError, ValueError, KeyError): return {}

def traits(A, B, bm, xa, champ):
    """Valeurs mesurables d'un pari (None quand elles manquent) : mêmes définitions que celles de l'audit."""
    ok = lambda *v: all(t is not None for t in v)
    return {"xa": xa[0] if ok(*xa) else None, "x_diff": xa[0] - xa[1] if ok(*xa) else None, "x_tot": xa[0] + xa[1] if ok(*xa) else None, "x_min": min(xa) if ok(*xa) else None,
            "champ_buts": champ.get("buts"), "b_tot": bm[0] + bm[1] if ok(*bm) else None,
            "tA": A["reussi"] / A["n"], "tmin": min(A["reussi"] / A["n"], B["reussi"] / B["n"])}

def appliquer(marche, verdict, T, regles=None):
    """-> (verdict, détail ou None). Pas de règle active, valeur absente ou verdict déjà bas : rien ne change."""
    r = (charger() if regles is None else regles).get(marche)
    if not r or not r.get("actif") or verdict not in BAS or T.get(r["trait"]) is None: return verdict, None
    v = T[r["trait"]]; remplie = v >= r["seuil"] if r["sens"] > 0 else v <= r["seuil"]
    d = {"trait": r["trait"], "valeur": v, "seuil": r["seuil"], "sens": r["sens"], "remplie": remplie,
         "phrase": None if remplie else f"Condition du marché non remplie : {NOMS_TRAITS.get(r['trait'], r['trait'])} {v:.2f} (il faut {'au moins' if r['sens'] > 0 else 'au plus'} {r['seuil']:.2f})."}
    return (verdict if remplie else BAS[verdict]), d


def _lignes(flux=None):
    """Paris « tient » (cote minimale, résultat connu) de toutes les journées du flux, jugés SANS règles : base de l'audit."""
    import glob, gzip, re, verif_pronostic as V
    flux = flux or V.FLUX; cfg = {**V.config(), "sans_regles": True}; S = {}
    for j in json.load(open(os.path.join(os.path.dirname(CHEMIN), "..", "historique_pronostics.json"), encoding="utf-8")):
        for m in j["matchs"]:
            if re.fullmatch(r"\d+-\d+", str(m.get("score"))): S[m["match_id"]] = tuple(map(int, m["score"].split("-")))
    L, vus = [], set()
    for f in sorted(glob.glob(os.path.join(flux, "*.json.gz"))):
        for k, m in json.load(gzip.open(f)).items():
            if k not in S or k in vus: continue
            vus.add(k); h, a = S[k]
            for mk, c in V.cotes_betpawa(m.get("cotes_betpawa")).items():
                if c < cfg["cote_min"]: continue
                r = V.constat(m, mk, c, cfg)
                if r["verdict"] not in BAS: continue
                L.append({"jour": f[-18:-8], "marche": mk, "gagne": bool(V.TABLE[min(h, V.CAP), min(a, V.CAP), V.IDX[mk]]),
                          "T": traits(r["A"], r["B"], r["buts_attendus"], r["xg_attendus"], r["championnat"])})
    return L

def auditer(lignes, regles=None, gain_min=0.05, garde_min=50):
    """Pour chaque règle : réussite des paris retenus moins celle de tous les paris du marché, sur chaque moitié des journées où le marché existe.
    La règle tient si le gain atteint gain_min dans les DEUX moitiés avec au moins garde_min paris retenus dans chacune."""
    regles = regles or charger(); out = {}
    for mk, r in regles.items():
        jours = sorted({l["jour"] for l in lignes if l["marche"] == mk}) or [""]; coupure = jours[len(jours) // 2]     # moitiés propres au marché (les combos n'existent que depuis le 25/10)
        moitie = []
        for nom, sel in (("1ere", lambda j: j < coupure), ("2e", lambda j: j >= coupure)):
            S = [l for l in lignes if l["marche"] == mk and sel(l["jour"])]
            K = [l for l in S if l["T"].get(r["trait"]) is not None and ((l["T"][r["trait"]] >= r["seuil"]) if r["sens"] > 0 else (l["T"][r["trait"]] <= r["seuil"]))]
            moitie.append({"periode": nom, "paris_marche": len(S), "retenus": len(K), "gain": round(sum(l["gagne"] for l in K) / len(K) - sum(l["gagne"] for l in S) / len(S), 3) if K else None})
        out[mk] = {"moitiés": moitie, "tient": all(m["gain"] is not None and m["gain"] >= gain_min and m["retenus"] >= garde_min for m in moitie), "actif": bool(r.get("actif"))}
    return out
