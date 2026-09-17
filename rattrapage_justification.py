"""rattrapage_justification.py — recalcule UNIQUEMENT les textes de
justification (bibliotheque_justification.py) sur les données déjà
scrapées du dernier run réel, sans relancer le scraping (plusieurs
heures) ni aucun autre calcul (cotes, probabilités, sélection P1/P2/P3
restent strictement inchangées).

Contexte (17/09/2026, demande de Patrick) : bibliotheque_justification.py
a été branché après le dernier run réel (15:42 UTC) -- le site affiche
donc encore les anciens textes, gelés dans precalcul_leger.json, alors
que le code est à jour depuis plusieurs heures. Attendre le prochain run
complet prendrait 1h30 à 4h. Ce script ne recalcule QUE la justification
affichée, à partir des données déjà présentes dans precalcul.json (les
historiques de matchs bruts, fenetres.A/B.matchs_retenus, survivent déjà
dans ce fichier -- pas besoin de rescraper).

LIMITE ASSUMÉE ET EXPLICITE : le H2H brut (confrontations_h2h, la liste
match par match) n'est PAS conservé dans precalcul.json (seul un résumé
-- statut par marché -- l'est). Les preuves basées sur le H2H
(h2h_unbeaten_count, h2h_over_rate, etc.) ne peuvent donc pas être
recalculées ici et resteront absentes pour ce rattrapage -- le reste
(Avantage Statistique, forme, séries, moyennes) est recalculé
normalement. Le prochain run complet (avec scraping réel) recalculera
tout correctement, H2H compris.

N'écrit PAS dans data/, config/, archive/ ni aucun autre fichier
touché par le pipeline nocturne -- uniquement precalcul.json et
precalcul_leger.json, exactement les deux fichiers que le site lit.
"""
import json
import sys

import justification

FICHIER_COMPLET = "precalcul.json"
FICHIER_LEGER = "precalcul_leger.json"


def _leger_pour_site(s):
    """Copie exacte de precalcul.py::_leger_pour_site -- reproduite ici
    pour ne pas importer precalcul.py (effets de bord potentiels au
    chargement du module), voir sa docstring pour le détail."""
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


def recalcule_justifications(signaux):
    nb_matchs = 0
    nb_candidats = 0
    nb_sans_fenetres = 0

    for s in signaux:
        am = s.get("archetype_model")
        if not isinstance(am, dict) or am.get("statut") != "OK":
            continue
        selection = am.get("selection") or {}
        fenetres = am.get("fenetres") or {}
        matchs_a = (fenetres.get("A") or {}).get("matchs_retenus")
        matchs_b = (fenetres.get("B") or {}).get("matchs_retenus")
        if not matchs_a or not matchs_b:
            nb_sans_fenetres += 1
            continue

        match_touche = False
        for rang in ("P1", "P2", "P3"):
            candidat = selection.get(rang)
            if not isinstance(candidat, dict):
                continue
            cote = candidat.get("cote")
            proba = candidat.get("probabilite")
            candidat["justification"] = justification.construit_justification(
                candidat.get("marche"), matchs_a, matchs_b, h2h=None,
                nom_domicile=s.get("domicile") or "", nom_exterieur=s.get("exterieur") or "",
                odds_scraped=cote if isinstance(cote, (int, float)) else None,
                market_prob_pct=proba * 100.0 if isinstance(proba, (int, float)) else None,
            )
            nb_candidats += 1
            match_touche = True
        if match_touche:
            nb_matchs += 1

    return {"matchs_recalcules": nb_matchs, "candidats_recalcules": nb_candidats, "matchs_sans_fenetres": nb_sans_fenetres}


def main():
    with open(FICHIER_COMPLET, encoding="utf-8") as f:
        d = json.load(f)

    bilan = recalcule_justifications(d["signaux"])
    print(f"[rattrapage] {bilan}", file=sys.stderr)

    with open(FICHIER_COMPLET, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)

    leger = {k: v for k, v in d.items()}
    leger["signaux"] = [_leger_pour_site(s) for s in d["signaux"]]
    with open(FICHIER_LEGER, "w", encoding="utf-8") as f:
        json.dump(leger, f, ensure_ascii=False)

    print(f"[rattrapage] {FICHIER_COMPLET} et {FICHIER_LEGER} réécrits.", file=sys.stderr)


if __name__ == "__main__":
    main()
