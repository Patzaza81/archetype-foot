#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construit le fichier de référence FIGÉ d'une évaluation du moteur (à lancer UNE fois, avant de connaître les résultats).

Il reprend les entrées exactes du moteur (export_moteur/matchs_moteur_AAAA-MM-JJ.json) et le precalcul.json du même run,
rejoue le moteur sur ces entrées (déterministe : `moteur_v2_6_9.py --autotest`), vérifie que l'inventaire rejoué est
IDENTIQUE à celui publié, puis écrit le fichier avec son empreinte SHA-256.

    python evaluation/construit_snapshot.py ENTREES.json PRECALCUL.json SORTIE.json "<origine>" [AAAA-MM-JJ HH:MM UTC]
"""
import datetime
import hashlib
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import branchement_moteur as bm
import moteur_v2_6_9 as moteur


def construit_match(entree, signal, publie, maintenant):
    """Un match du snapshot : entrées exactes du moteur + inventaire complet + choix publiés. Le moteur est REJOUÉ sur
    les entrées et son inventaire doit être identique à celui publié (sinon SystemExit : jamais de snapshot approximatif)."""
    res = moteur.analyser_match(entree, entree["date_match"], maintenant)
    rejoue = sorted((bm.nom_canonique(l["marche"]), round(l["proba_modele"], 9), round(l["ev"], 9)) for l in res["inventaire"])
    attendu = sorted((l["marche"], round(l["probabilite"], 9), round(l["ev"], 9)) for l in publie["inventaire"])
    if rejoue != attendu:
        raise SystemExit(f"Inventaire rejoué différent de l'inventaire publié pour {entree['id']} : snapshot refusé")
    inventaire = []
    for l in res["inventaire"]:
        canon = bm.nom_canonique(l["marche"])
        famille = bm.famille_et_groupe(canon)[0] if canon else "AUTRE"
        inventaire.append({"marche": canon, "marche_moteur": l["marche"], "famille": famille, "probabilite": l["proba_modele"],
                           "p_juste": l["p_juste"], "cote": l["cote"], "edge": l["edge"], "ev": l["ev"], "push": l.get("push", 0.0),
                           "statut": l["statut"], "is_value": l["is_value"], "categorie": l["categorie"]})
    choix = []
    for rang, c in (publie.get("selection") or {}).items():
        if c:
            choix.append({"rang": rang, "marche": c["marche"], "cote": c["cote"], "probabilite": c["probabilite"], "edv": c["edv"],
                          "niveau": c["niveau"], "resume": (c.get("justification") or {}).get("resume"),
                          "preuves": [{"type": p["type"], "texte": p["texte"]} for p in (c.get("justification") or {}).get("preuves", [])],
                          "points_de_vigilance": c.get("points_de_vigilance", [])})
    return {
        "id": entree["id"], "date": signal["date"], "heure": signal["heure"], "domicile": signal["domicile"], "exterieur": signal["exterieur"],
        "competition": " ".join(signal["competition"].split()), "url_match": signal.get("url_match"),
        "effectifs": {"domicile": publie["n_matchs_dom"], "exterieur": publie["n_matchs_ext"]},
        "lambda_dom": publie["lambda_dom"], "lambda_ext": publie["lambda_ext"], "statut_global": publie["statut_global"], "verdict": publie["verdict"],
        "entree_moteur": entree, "inventaire": inventaire, "choix_publies": choix, "rejets": publie.get("rejets", []),
    }


def construit(chemin_entrees, chemin_precalcul, origine, maintenant):
    entrees = json.load(open(chemin_entrees, encoding="utf-8"))
    precalcul = json.load(open(chemin_precalcul, encoding="utf-8"))
    signaux = {s["match_id"]: s for s in precalcul["signaux"] if (s.get(bm.CLE_BLOC) or {}).get("statut") == "OK"}
    matchs = [construit_match(e, signaux[e["id"]], signaux[e["id"]][bm.CLE_BLOC], maintenant) for e in entrees["matchs"] if e["id"] in signaux]
    return {"schema": 1, "moteur": {"nom": bm.NOM_MOTEUR, "version": bm.VERSION_MOTEUR}, "origine": origine,
            "construit_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "nb_matchs": len(matchs), "matchs": matchs}


if __name__ == "__main__":
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    t = datetime.datetime.strptime(sys.argv[5] if len(sys.argv) > 5 else "2026-09-20 00:18", "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc)
    snap = construit(sys.argv[1], sys.argv[2], sys.argv[4], t)
    texte = json.dumps(snap, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    open(sys.argv[3], "w", encoding="utf-8").write(texte)
    open(sys.argv[3] + ".sha256", "w").write(hashlib.sha256(texte.encode("utf-8")).hexdigest() + "\n")
    print(f"{snap['nb_matchs']} matchs écrits dans {sys.argv[3]} ({len(texte)//1024} Ko) ; sha256 : {hashlib.sha256(texte.encode('utf-8')).hexdigest()}")
