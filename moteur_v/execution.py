"""Exécution quotidienne autonome de v. Lit UNIQUEMENT data/archive_test (alimentée par le scraping existant) et écrit UNIQUEMENT dans
data/v/. Chaque jour : 1) fige les pronostics dont le coup d'envoi est passé et règle ceux dont le match est fini 2) écrit les
pronostics (principal + autres) des matchs à venir, avant le coup d'envoi. Usage : python -m moteur_v.execution [--dossier data/v]"""
import argparse
import datetime
import json
import os

from . import carnet as K, historique as H, modele as M, pronostics as P
from .donnees import charge

AVERTISSEMENT = "Chiffres calculés sur 440 matchs passés, pas encore confirmés par les paris de v. Attends 100 paris réglés."


def _allege(l):
    """Version pour la page : sans le détail de tous les marchés, mais avec deux repères lisibles par un parieur :
    « attendus » = buts attendus (moyenne des deux estimations), « lecture » = fréquence du pari principal chez chaque équipe au lieu."""
    d = {k: v for k, v in l.items() if k not in ("marches", "lambdas")}
    lam = l.get("lambdas")
    if lam:
        d["attendus"] = [round((lam["force"][i] + lam["simple"][i]) / 2, 2) for i in (0, 1)]
    mm = next((x for x in l.get("marches", []) if x["m"] == l["principal"]["marche"]), None)
    if mm:
        d["lecture"] = [mm["sh"], mm["sa"]]
    return d


def execute(matchs, entrees, dossier, maintenant):
    """matchs: sortie de donnees.charge(a_venir=True)[0] ; entrees: archive brute (pour forces et classements). Retourne le dict publié."""
    carnet = K.charge(dossier)
    K.fige(carnet, maintenant)
    scores = {m["id"]: (m["h"], m["a"]) for m in matchs if m["h"] is not None}
    regles = K.regle(carnet, scores)
    forces, classements = M.Forces(entrees), M.Classements(entrees)
    sans, retraits = [], []
    for m in matchs:
        if m["h"] is not None or not m.get("kickoff"):
            continue
        l = P.proposer(m, forces, classements)
        if l and l.get("sans_pronostic"):
            if K.avant_coup_d_envoi(l, maintenant):
                sans.append(l)
                if K.retire(carnet, l["match_id"]):
                    retraits.append(l)
            continue
        K.enregistre(carnet, l, maintenant)
    K.sauve(carnet, dossier)
    b = K.bilan(carnet)
    ajouts = H.enregistre(dossier, carnet, b, maintenant, M.PARAMETRES_VERSION, retraits)   # historique : on ajoute, on ne réécrit jamais
    allege = lambda l: _allege(l)
    cle = lambda l: (l["coup_d_envoi_utc"], l["match_id"])
    sortie = dict(genere_le=maintenant.isoformat(), statut=b["statut"],
                  avertissement=AVERTISSEMENT if b["statut"] != "controle_ok" else None,
                  parametres_version=M.PARAMETRES_VERSION, zones=[dict(cote_min=a, cote_max=b_, fiabilite=p, niveau=n) for a, b_, p, n in M.FIABILITE_ZONES],
                  reglees_aujourdhui=regles, bilan=b, historique_ajouts=ajouts, plancher_principal=M.PLANCHER_PRINCIPAL,
                  sans_pronostic=sorted(sans, key=cle),
                  a_venir=sorted([allege(l) for l in carnet.values() if not l["fige"]], key=cle),
                  en_cours=sorted([allege(l) for l in carnet.values() if l["fige"] and l["resultat"] is None], key=cle),
                  reglees=sorted([allege(l) for l in carnet.values() if l["resultat"] is not None], key=cle, reverse=True)[:150])
    os.makedirs(dossier, exist_ok=True)
    json.dump(sortie, open(os.path.join(dossier, "pronostics_v.json"), "w"), ensure_ascii=False, indent=1)
    return sortie


def passage_nocturne(dossier=os.path.join("data", "v")):
    """Appelé chaque nuit par enregistre_scores_historique.py (après l'archive de test). Ne doit JAMAIS faire échouer l'appelant :
    toute erreur est renvoyée sous forme de texte."""
    try:
        matchs, entrees = charge(a_venir=True)
        s = execute(matchs, entrees, dossier, datetime.datetime.now(datetime.timezone.utc))
        return {"statut": s["statut"], "a_venir": len(s["a_venir"]), "regles": s["bilan"]["principal"]["regles"]}
    except Exception as e:  # noqa: BLE001
        return f"v indisponible : {type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossier", default="data/v")
    a = ap.parse_args()
    matchs, entrees = charge(a_venir=True)
    s = execute(matchs, entrees, a.dossier, datetime.datetime.now(datetime.timezone.utc))
    print(json.dumps({k: s[k] for k in ("statut", "parametres_version", "reglees_aujourdhui")}, ensure_ascii=False))
    print("pronostics à venir:", len(s["a_venir"]), "| en cours:", len(s["en_cours"]), "| réglés:", s["bilan"]["principal"]["regles"])


if __name__ == "__main__":
    main()
