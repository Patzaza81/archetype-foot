"""Exécution quotidienne autonome de v2r. Lit UNIQUEMENT data/archive_test (alimentée par le scraping existant :
cotes BetPawa + historiques Matchendirect/Football-Data + scores). Écrit UNIQUEMENT dans data/v2r/.

Chaque jour : 1) règle les paris dont le match est fini  2) choisit les paris des matchs à venir avec les règles
figées  3) le lundi, réentraîne APRÈS avoir réglé (les anciennes règles ont donc été jugées sur les nouveaux matchs
sans être retouchées) et fige une nouvelle version. Usage : python -m moteur_v2r.execution [--dossier data/v2r]"""
import argparse
import datetime
import json
import os

from . import carnet as K, modere as MOD, pronostics as P, regles as R
from .donnees import charge


def execute(matchs, dossier, maintenant):
    """matchs: sortie de donnees.charge(a_venir=True). Retourne le dict publié."""
    aujourdhui = maintenant.date()
    regles = R.derniere(dossier)
    carnet = K.charge(dossier)

    # 1) figer / régler avec les scores connus
    K.fige(carnet, maintenant)
    scores = {m["id"]: (m["h"], m["a"]) for m in matchs if m["h"] is not None}
    reglés = K.regle(carnet, scores)

    # 3) réentraînement (après le réglage), jamais sur des matchs du jour ou à venir
    nouvelle = False
    if R.doit_reentrainer(aujourdhui, regles):
        joues = [m for m in matchs if m["h"] is not None]
        nv = R.entraine(joues, aujourdhui.isoformat())
        if nv is not None and (regles is None or nv["version"] != regles["version"]):
            R.ecrit(nv, dossier)
            regles, nouvelle = nv, True

    # 2) paris des matchs à venir
    propositions = []
    if regles is not None:
        tab = R.table(regles)
        for m in matchs:
            if m["h"] is not None:
                continue
            pick = P.proposer(m, regles, tab)
            if pick and K.enregistre(carnet, pick, maintenant):
                propositions.append(carnet[pick["match_id"]])
    K.sauve(carnet, dossier)

    # 4) variantes « marché modéré » (carnets séparés, ne modifient ni le carnet officiel ni les règles). Une erreur
    # est écrite dans le fichier publié (jamais masquée) et ne bloque pas v2r.
    try:
        modere = MOD.met_a_jour(matchs, carnet, dossier, maintenant)
    except Exception as e:  # noqa: BLE001
        modere = dict(erreur=f"{type(e).__name__}: {e}")

    bilan = K.bilan(carnet)
    sortie = dict(genere_le=maintenant.isoformat(), statut=bilan["statut"],
                  avertissement=("OBSERVATION : ne pas miser avant %d paris réglés avec borne basse IC95 > 0" % K.SEUIL_PARIS)
                  if bilan["statut"] != "actif" else None,
                  regles_version=regles["version"] if regles else None, regles_nouvelles=nouvelle,
                  regles_cellules=len(regles["cellules"]) if regles else 0, regles_reglees_aujourdhui=reglés,
                  bilan=bilan, modere=modere,
                  a_venir=sorted([l for l in carnet.values() if not l["fige"]], key=lambda l: (l["coup_d_envoi_utc"], l["match_id"])),
                  en_cours=sorted([l for l in carnet.values() if l["fige"] and l["resultat"] is None], key=lambda l: (l["coup_d_envoi_utc"], l["match_id"])),
                  reglees=sorted([l for l in carnet.values() if l["resultat"] is not None], key=lambda l: (l["coup_d_envoi_utc"], l["match_id"]), reverse=True)[:150])
    os.makedirs(dossier, exist_ok=True)
    json.dump(sortie, open(os.path.join(dossier, "pronostics_v2r.json"), "w"), ensure_ascii=False, indent=1)
    return sortie


def passage_nocturne(dossier=os.path.join("data", "v2r")):
    """Appelé chaque nuit par enregistre_scores_historique.py (après l'archive de test). Ne doit JAMAIS faire échouer
    l'appelant : toute erreur est renvoyée sous forme de texte."""
    try:
        s = execute(charge(a_venir=True), dossier, datetime.datetime.now(datetime.timezone.utc))
        return {"statut": s["statut"], "a_venir": len(s["a_venir"]), "regles": s["bilan"]["regles"]}
    except Exception as e:  # noqa: BLE001
        return f"v2r indisponible : {type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossier", default="data/v2r")
    a = ap.parse_args()
    s = execute(charge(a_venir=True), a.dossier, datetime.datetime.now(datetime.timezone.utc))
    print(json.dumps({k: s[k] for k in ("statut", "regles_version", "regles_nouvelles", "regles_cellules",
                                        "regles_reglees_aujourdhui", "bilan")}, ensure_ascii=False))
    print("paris à venir:", len(s["a_venir"]))


if __name__ == "__main__":
    main()
