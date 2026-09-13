"""
archetype_model/learning/constat_majeur.py — File d'événements notables.

Pourquoi ce module existe : Patrick a explicitement demandé (13/09/2026)
un signal actif quand un événement mérite son attention -- jusqu'ici,
tout restait dans des fichiers qu'il fallait aller consulter lui-même,
ce qui contredisait sa demande initiale de ne pas avoir à suivre le
système au quotidien.

Ce module n'a AUCUNE autorité de jugement -- il accumule ce que les
autres scripts (calibre_archetype_model.py,
genere_tickets_reels_archetype_model.py) lui signalent, dans un fichier
simple (constat_majeur.json). C'est notifie_constat_majeur.py, une étape
séparée et toujours DERNIÈRE du pipeline, qui transforme ce fichier en
Issue GitHub s'il n'est pas vide, puis le vide.

Format volontairement plat : une liste de {"titre", "details"} -- pas de
catégorisation ni de priorité pour l'instant, un seul niveau d'alerte
("ça mérite ton attention"), cohérent avec la demande de Patrick.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FICHIER_DEFAUT = "constat_majeur.json"


def signaler(titre: str, details: str, chemin: str = FICHIER_DEFAUT) -> None:
    """Ajoute un événement à la file -- jamais une réécriture qui
    effacerait un événement déjà signalé plus tôt dans le même cycle
    (ex. par un autre script)."""
    path = Path(chemin)
    evenements: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            evenements = json.load(f)
    evenements.append({"titre": titre, "details": details})
    with path.open("w", encoding="utf-8") as f:
        json.dump(evenements, f, ensure_ascii=False, indent=2)


def charger_et_vider(chemin: str = FICHIER_DEFAUT) -> list[dict[str, Any]]:
    """Lit tous les événements accumulés puis supprime le fichier --
    jamais un événement notifié deux fois. Liste vide si le fichier
    n'existe pas (cas normal : rien à signaler cette nuit)."""
    path = Path(chemin)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        evenements = json.load(f)
    path.unlink()
    return evenements
