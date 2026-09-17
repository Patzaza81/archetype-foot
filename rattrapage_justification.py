"""rattrapage_justification.py — recalcule UNIQUEMENT les textes de
justification (bibliotheque_justification.py) sur les données déjà
scrapées du dernier run réel, sans relancer le scraping ni aucun autre
calcul. Cotes, probabilités et sélection P1/P2/P3 restent inchangées.

Le script ne réécrit que precalcul.json et precalcul_leger.json.
"""
import json
import sys

import justification

FICHIER_COMPLET = "precalcul.json"
FICHIER_LEGER = "precalcul_leger.json"


def _leger_pour_site(s):
    """Copie de precalcul.py::_leger_pour_site sans importer precalcul.py."""
    d = dict(s)
    d.pop("marches", None)
    d.pop("lambda", None)
    am = d.get("archetype_model")
    if isinstance(am, dict):
        selection = am.get("selection") or {}
        selection_legere = {}
        for rang, candidat in selection.items():
            if not isinstance(candidat, dict):
                continue
            c = dict(candidat)
            if isinstance(c.get("justification"), dict):
                j = c["justification"]
                c["justification"] = {
                    "resume": j.get("resume"),
                    "preuves": j.get("preuves") or [],
                    "donnees_suffisantes": bool(j.get("donnees_suffisantes")),
                }
            selection_legere[rang] = c
        d["archetype_model"] = {"statut": am.get("statut"), "selection": selection_legere}
    return d


def _recupere_fenetres(s, am):
    """Retrouve la structure réelle des fenêtres sans imposer un emplacement.

    Selon la version ayant produit le fichier, les fenêtres peuvent être
    portées directement par le signal ou par archetype_model. On privilégie
    le conteneur du signal, puis celui du modèle. Aucun historique n'est
    reconstruit et aucune donnée de sélection n'est modifiée.
    """
    for conteneur in (s, am):
        if not isinstance(conteneur, dict):
            continue
        fenetres = conteneur.get("fenetres")
        if isinstance(fenetres, dict):
            return fenetres
    return {}


def recalcule_justifications(signaux):
    nb_matchs = 0
    nb_candidats = 0
    nb_sans_fenetres = 0
    nb_fenetres_trouvees = 0

    for s in signaux:
        am = s.get("archetype_model")
        if not isinstance(am, dict) or am.get("statut") != "OK":
            continue
        selection = am.get("selection") or {}
        fenetres = _recupere_fenetres(s, am)
        matchs_a = (fenetres.get("A") or {}).get("matchs_retenus")
        matchs_b = (fenetres.get("B") or {}).get("matchs_retenus")
        if not matchs_a or not matchs_b:
            nb_sans_fenetres += 1
            continue
        nb_fenetres_trouvees += 1

        match_touche = False
        for rang in ("P1", "P2", "P3"):
            candidat = selection.get(rang)
            if not isinstance(candidat, dict):
                continue
            cote = candidat.get("cote")
            proba = candidat.get("probabilite")
            candidat["justification"] = justification.construit_justification(
                candidat.get("marche"),
                matchs_a,
                matchs_b,
                h2h=None,
                nom_domicile=s.get("domicile") or "",
                nom_exterieur=s.get("exterieur") or "",
                odds_scraped=cote if isinstance(cote, (int, float)) else None,
                market_prob_pct=proba * 100.0 if isinstance(proba, (int, float)) else None,
            )
            nb_candidats += 1
            match_touche = True
        if match_touche:
            nb_matchs += 1

    return {
        "matchs_recalcules": nb_matchs,
        "candidats_recalcules": nb_candidats,
        "matchs_sans_fenetres": nb_sans_fenetres,
        "fenetres_trouvees": nb_fenetres_trouvees,
    }


def main():
    with open(FICHIER_COMPLET, encoding="utf-8") as f:
        d = json.load(f)

    bilan = recalcule_justifications(d["signaux"])
    print(f"[rattrapage] {bilan}", file=sys.stderr)

    with open(FICHIER_COMPLET, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)

    leger = dict(d)
    leger["signaux"] = [_leger_pour_site(s) for s in d["signaux"]]
    with open(FICHIER_LEGER, "w", encoding="utf-8") as f:
        json.dump(leger, f, ensure_ascii=False)

    print(f"[rattrapage] {FICHIER_COMPLET} et {FICHIER_LEGER} réécrits.", file=sys.stderr)


if __name__ == "__main__":
    main()
