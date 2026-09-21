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
                # AJOUT 21/09/2026 : les statistiques exactes de la bibliothèque (forme domicile /
                # extérieur, H2H, métriques combinées) alimentent les tableaux de « Détails de
                # l'analyse ». Quelques dizaines de nombres par choix retenu : négligeable pour le
                # fichier allégé. Absentes = les tableaux concernés ne s'affichent pas (jamais de « — »).
                if isinstance(j.get("bibliotheque"), dict):
                    c["justification"]["bibliotheque"] = j["bibliotheque"]
            selection_legere[rang] = c
        d["archetype_model"] = {"statut": am.get("statut"), "selection": selection_legere}
    return d


def _recupere_fenetres(s, am):
    """Retrouve la structure réelle des fenêtres sans imposer un emplacement."""
    for conteneur in (s, am):
        if not isinstance(conteneur, dict):
            continue
        fenetres = conteneur.get("fenetres")
        if isinstance(fenetres, dict):
            return fenetres
    return {}


def _recupere_h2h(fenetres, s, am):
    """Récupère un H2H déjà présent, sans reconstruire d'historique."""
    for conteneur in (fenetres, s, am):
        if not isinstance(conteneur, dict):
            continue
        for cle in ("h2h", "confrontations_directes", "matchs_h2h"):
            valeur = conteneur.get(cle)
            if isinstance(valeur, list):
                return valeur
    return None


def _preuves_specifiques(justification):
    """Retourne uniquement les preuves métier, hors preuve EV de secours."""
    preuves = (justification or {}).get("preuves") or []
    return [p for p in preuves if isinstance(p, dict) and p.get("type") != "ev_percentage"]


def recalcule_justifications(signaux):
    nb_matchs = 0
    nb_candidats = 0
    nb_avec_preuve_specifique = 0
    nb_ev_seul = 0
    nb_sans_preuve = 0
    nb_sans_fenetres = 0
    nb_fenetres_trouvees = 0
    types_preuves = {}

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
        h2h = _recupere_h2h(fenetres, s, am)

        match_touche = False
        for rang in ("P1", "P2", "P3"):
            candidat = selection.get(rang)
            if not isinstance(candidat, dict):
                continue
            cote = candidat.get("cote")
            proba = candidat.get("probabilite")
            j = justification.construit_justification(
                candidat.get("marche"),
                matchs_a,
                matchs_b,
                h2h=h2h,
                nom_domicile=s.get("domicile") or "",
                nom_exterieur=s.get("exterieur") or "",
                odds_scraped=cote if isinstance(cote, (int, float)) else None,
                market_prob_pct=proba * 100.0 if isinstance(proba, (int, float)) else None,
            )
            candidat["justification"] = j
            nb_candidats += 1
            match_touche = True

            specifiques = _preuves_specifiques(j)
            if specifiques:
                nb_avec_preuve_specifique += 1
                for preuve in specifiques:
                    typ = preuve.get("type") or "inconnu"
                    types_preuves[typ] = types_preuves.get(typ, 0) + 1
            elif any(isinstance(p, dict) and p.get("type") == "ev_percentage" for p in (j.get("preuves") or [])):
                nb_ev_seul += 1
            else:
                nb_sans_preuve += 1

        if match_touche:
            nb_matchs += 1

    return {
        "matchs_recalcules": nb_matchs,
        "candidats_recalcules": nb_candidats,
        "candidats_avec_preuve_specifique": nb_avec_preuve_specifique,
        "candidats_ev_seul": nb_ev_seul,
        "candidats_sans_preuve": nb_sans_preuve,
        "matchs_sans_fenetres": nb_sans_fenetres,
        "fenetres_trouvees": nb_fenetres_trouvees,
        "types_preuves_specifiques": types_preuves,
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
