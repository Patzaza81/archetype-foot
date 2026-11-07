"""Apprentissage quotidien de P1 (mode parallele, couche ajoutee AU-DESSUS de P1, rien n'est modifie en dessous).
Chaque nuit : on relit le journal gele (predictions figees AVANT le coup d'envoi) et les scores reels deja ecrits par le flux (data/archive_test),
puis on mesure, marche par marche (plus de 1,5 / 2,5 / 3,5 buts, les deux marquent), l'ecart entre la probabilite de P1 et la frequence reelle,
sur TOUS les championnats ensemble (un seul championnat n'a pas assez de matchs par jour pour apprendre seul).
Correction apprise = decalage b sur l'echelle logit : p' = sigmoide(logit(p) + b), b = maximum de vraisemblance sur les matchs termines. Aucune constante inventee.
Une correction n'est VALIDEE que si, selon le protocole du depot (gain > 0 et z > 1,645) :
  1. le decalage b est significatif (|b| / erreur-type > 1,645), ET
  2. elle aurait ameliore la perte logarithmique en PROSPECTIF : chaque jour est evalue avec un b appris uniquement sur les jours precedents (jamais de fuite),
     gain moyen > 0 et z du gain moyen > 1,645.
Sinon le marche reste « EN OBSERVATION » et la probabilite n'est pas modifiee. Sortie : data/calibration_p1/apprentissage/etat.json (recalcule de zero, deterministe)."""
import datetime, json, math, os

import integration_calibration as ic

RACINE = ic.RACINE
DOSSIER = os.path.join(RACINE, "data", "calibration_p1", "apprentissage")
SORTIE = os.path.join(DOSSIER, "etat.json")
MARCHES = ("o15", "o25", "o35", "btts")
Z_SEUIL = 1.645      # seuil unilateral a 95 % deja exige par le protocole de calibration du depot (calibration_finale.py : gain > 0 et z > 1,645)
EPS = 1e-9

def _logit(p): p = min(max(p, EPS), 1 - EPS); return math.log(p / (1 - p))
def _sigm(z): return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))

def decalage(ps, ys):
    """Decalage b (echelle logit) qui rend la somme des probabilites corrigees egale au nombre d'evenements observes (maximum de vraisemblance).
    -> (b, erreur_type) ou None si non identifiable (aucun match, ou tous les resultats identiques)."""
    if not ps or all(y == ys[0] for y in ys): return None
    z = [_logit(p) for p in ps]; cible = sum(ys); lo, hi = -30.0, 30.0
    for _ in range(200):                                   # somme des p corrigees croit avec b : dichotomie
        mi = (lo + hi) / 2
        if sum(_sigm(a + mi) for a in z) < cible: lo = mi
        else: hi = mi
    b = (lo + hi) / 2; info = sum(_sigm(a + b) * (1 - _sigm(a + b)) for a in z)
    return b, (1 / math.sqrt(info) if info > 0 else float("inf"))

def _perte(p, y): p = min(max(p, EPS), 1 - EPS); return -math.log(p if y else 1 - p)

def evaluer_marche(obs):
    """obs : liste de (jour 'AAAA-MM-JJ', probabilite P1, resultat 0/1). -> bilan du marche (decalage, prospectif, statut)."""
    obs = sorted(obs, key=lambda o: o[0]); n = len(obs); freq = sum(o[2] for o in obs) / n if n else None
    res = {"n": n, "frequence_reelle": freq, "probabilite_moyenne": sum(o[1] for o in obs) / n if n else None, "b": None, "erreur_type_b": None, "z_b": None,
           "n_prospectif": 0, "gain_prospectif_moyen": None, "z_gain": None, "statut": "EN OBSERVATION", "raison": ""}
    d = decalage([o[1] for o in obs], [o[2] for o in obs]) if n else None
    if d is None: res["raison"] = "aucun match termine" if not n else "tous les resultats identiques : decalage non identifiable"; return res
    res["b"], res["erreur_type_b"] = d; res["z_b"] = d[0] / d[1]
    gains = []
    for jour in sorted({o[0] for o in obs}):
        passe = [o for o in obs if o[0] < jour]; dp = decalage([o[1] for o in passe], [o[2] for o in passe]) if passe else None
        if dp is None: continue                            # aucun entrainement possible avant ce jour : non compte
        for o in (o for o in obs if o[0] == jour): gains.append(_perte(o[1], o[2]) - _perte(_sigm(_logit(o[1]) + dp[0]), o[2]))
    m = len(gains); res["n_prospectif"] = m
    if m >= 1: res["gain_prospectif_moyen"] = sum(gains) / m
    if m >= 2:
        moy = res["gain_prospectif_moyen"]; var = sum((g - moy) ** 2 for g in gains) / (m - 1)
        res["z_gain"] = moy / math.sqrt(var / m) if var > 0 else (float("inf") if moy > 0 else None)
    if res["z_gain"] is None: res["raison"] = "pas assez de jours pour mesurer un gain prospectif"
    elif abs(res["z_b"]) <= Z_SEUIL: res["raison"] = "decalage non significatif"
    elif not (res["gain_prospectif_moyen"] > 0 and res["z_gain"] > Z_SEUIL): res["raison"] = "gain prospectif non significatif"
    else: res["statut"] = "CORRECTION VALIDEE"; res["raison"] = "decalage significatif et gain prospectif significatif"
    return res

def observations(dossier=ic.DOSSIER, flux=ic.FLUX):
    """Matchs du journal gele ayant un score reel : -> {marche: [(jour, p, y)]}. Probabilite = P1 calibre (celui que le journal a gele)."""
    import p1_page_donnees as pd
    S = pd.scores(flux); out = {k: [] for k in MARCHES}; n = 0
    for r in ic.lire_journal(dossier):
        sc = S.get(r["match_id"])
        if r.get("statut") != "OK" or sc is None: continue
        o = pd.realise(sc); n += 1
        for k in MARCHES: out[k].append((r["date"], float(r["p1_calibre"][k]), int(o[k])))
    return out, n

def construire(dossier=ic.DOSSIER, flux=ic.FLUX):
    anom = ic.verifier_journal(dossier)
    if anom: raise RuntimeError(f"journal gele non intact, apprentissage refuse : {anom[:3]}")
    obs, n = observations(dossier, flux); J = ic.lire_journal(dossier); jours = sorted({o[0] for k in MARCHES for o in obs[k]})
    marches = {k: evaluer_marche(obs[k]) for k in MARCHES}; valides = [k for k, v in marches.items() if v["statut"] == "CORRECTION VALIDEE"]
    return {"description": "Apprentissage quotidien de P1 : decalage logit par marche appris sur les matchs termines du journal gele, tous championnats ensemble ; valide seulement si significatif ET gagnant en prospectif.",
            "seuil_z": Z_SEUIL, "matchs_termines": n, "periode": [jours[0], jours[-1]] if jours else None, "derniere_empreinte_journal": J[-1]["empreinte"] if J else None,
            "marches": marches, "corrections_validees": valides,
            "texte": "Aucune correction validee : P1 inchange." if not valides else "Corrections validees : " + ", ".join(valides)}

def charger_etat(chemin=SORTIE):
    return json.load(open(chemin, encoding="utf-8")) if os.path.exists(chemin) else None

def corriger(etat, p):
    """Applique les corrections VALIDEES de l'etat a un dict de probabilites P1 (copie). Marches non valides et dom/nul/ext : inchanges.
    Les marches de buts gardent l'ordre logique plus de 1,5 >= plus de 2,5 >= plus de 3,5."""
    q = dict(p); touche = False
    for k, v in ((etat or {}).get("marches") or {}).items():
        if v["statut"] == "CORRECTION VALIDEE" and k in q: q[k] = _sigm(_logit(q[k]) + v["b"]); touche = True
    if touche and all(k in q for k in ("o15", "o25", "o35")): q["o25"] = min(q["o25"], q["o15"]); q["o35"] = min(q["o35"], q["o25"])
    return q

def ecrire(etat=None, chemin=SORTIE):
    etat = etat or construire(); os.makedirs(os.path.dirname(chemin), exist_ok=True); json.dump(etat, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True); return etat

if __name__ == "__main__":
    e = ecrire(); print(json.dumps({"matchs_termines": e["matchs_termines"], "periode": e["periode"], "corrections_validees": e["corrections_validees"], "statuts": {k: v["raison"] for k, v in e["marches"].items()}}, ensure_ascii=False))
