"""
construit_etat_systeme.py -- (13/09/2026) consolide en UN SEUL fichier
tout ce qu'affiche la nouvelle page systeme.html : bilan comportemental,
configuration active, dernier cycle de calibration, rapport des tickets
fictifs.

Pourquoi un fichier consolidé plutôt que plusieurs petits fetch() côté
navigateur : JavaScript ne peut pas lister le contenu d'un dossier sur un
hébergement statique (impossible de découvrir tout seul les fichiers
tickets_observes/YYYY-MM.json existants), et parcourir un fichier JSONL
(config/journal_promotion.jsonl) côté client ajoute de la complexité pour
rien. Ce script fait tout le travail une fois par nuit, le navigateur n'a
plus qu'à lire un seul fichier simple.

Lecture seule, aucun calcul nouveau -- relit ce que les autres scripts ont
déjà produit cette nuit. Doit tourner APRÈS calibre_archetype_model.py (a
besoin de la config et du journal à jour) et
observe_tickets_archetype_model.py (a besoin du rapport de calibration
des tickets à jour) -- placé en toute dernière position avant la
notification, pour être sûr que tout le reste a déjà tourné.

Usage : python construit_etat_systeme.py
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from archetype_model.learning import calibration, journal
from tickets import rapport_calibration

FICHIER_ETAT = "etat_systeme.json"
FICHIER_BILAN = "bilan_archetype_model.json"
NB_PROMOTIONS_RECENTES = 20


def _charge_json_ou_vide(chemin: str, defaut: Any) -> Any:
    path = Path(chemin)
    if not path.exists():
        return defaut
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def construit_etat() -> dict[str, Any]:
    bilan = _charge_json_ou_vide(FICHIER_BILAN, {})

    try:
        parametres = calibration.charger_parametres().get("parametres", {})
    except calibration.CalibrationError:
        parametres = {}

    etat_calibration = calibration.charger_etat()

    promotions = journal.charger_journal("config/journal_promotion.jsonl")
    dernieres_promotions = list(reversed(promotions[-NB_PROMOTIONS_RECENTES:]))

    tickets_observes = rapport_calibration.charge_tous_les_tickets_observes()
    rapport_tickets = rapport_calibration.construit_rapport(tickets_observes)
    nb_tickets_pending = sum(
        1 for t in tickets_observes if t.get("statut_resolution") == "PENDING"
    )

    return {
        "genere_le": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bilan_comportemental": bilan,
        "parametres_actifs": parametres,
        "etat_calibration": etat_calibration,
        "dernieres_promotions": dernieres_promotions,
        "rapport_tickets_observation": rapport_tickets,
        "nb_tickets_observation_pending": nb_tickets_pending,
    }


def main() -> None:
    etat = construit_etat()
    with open(FICHIER_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)
    print(f"[etat systeme] {FICHIER_ETAT} généré -- {len(etat['parametres_actifs'])} paramètre(s), "
          f"{len(etat['dernieres_promotions'])} promotion(s) récente(s), "
          f"{etat['rapport_tickets_observation']['nb_tickets_resolus']} ticket(s) fictif(s) résolu(s).")


if __name__ == "__main__":
    main()
