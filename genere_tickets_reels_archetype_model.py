"""
genere_tickets_reels_archetype_model.py -- (13/09/2026) tente la
construction de VRAIS tickets chaque nuit.

Utilise tickets/builder.py et tickets/cycle.py avec leurs valeurs PAR
DÉFAUT uniquement (SEUIL_OBSERVATIONS_CONJOINTES=100,
BORNES_D_ACCEPTABLE) -- jamais le seuil abaissé de
tickets/observation.py. Un résultat vide chaque nuit est NORMAL et
ATTENDU pendant probablement plusieurs mois (voir tickets/builder.py) --
ce script existe précisément pour détecter, sans que Patrick ait à
vérifier lui-même, le jour où ça cesse d'être vrai.

Écrit les vrais tickets, s'il y en a, dans vrais_tickets/YYYY-MM.json --
jamais mélangé à tickets_observes/ (fictifs) ni à archive/. Signale un
constat majeur (archetype_model/learning/constat_majeur.py) la première
fois qu'au moins un vrai ticket est construit -- c'est le seul événement
que ce script signale, jamais un résultat vide.

Usage : python genere_tickets_reels_archetype_model.py
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from archetype_model.learning import constat_majeur, observations
from tickets import cycle

REPERTOIRE_VRAIS_TICKETS = "vrais_tickets"


def chemin_vrais_tickets(date_cycle: str, repertoire: str = REPERTOIRE_VRAIS_TICKETS) -> str:
    return str(Path(repertoire) / f"{str(date_cycle)[:7]}.json")


def executer_cycle(
    date_cycle: str | None = None,
    repertoire_archive: str = "archive",
) -> dict[str, Any]:
    date_cycle = date_cycle or datetime.date.today().isoformat()

    selections_resolues = observations.selections_resolues(repertoire_archive)
    candidats_du_jour = observations.candidats_selected_pending(repertoire_archive)

    tickets_reels = cycle.generer_tickets(candidats_du_jour, selections_resolues)

    if tickets_reels:
        chemin = chemin_vrais_tickets(date_cycle)
        path = Path(chemin)
        path.parent.mkdir(parents=True, exist_ok=True)
        existants: list[dict[str, Any]] = []
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                existants = json.load(f)
        existants.extend({"date_construction": date_cycle, **t} for t in tickets_reels)
        with path.open("w", encoding="utf-8") as f:
            json.dump(existants, f, ensure_ascii=False, indent=2)

        constat_majeur.signaler(
            "Premier(s) vrai(s) ticket(s) construit(s) !",
            f"{len(tickets_reels)} ticket(s) réel(s) construit(s) le {date_cycle} -- "
            "au moins une paire de signatures a atteint le seuil de 100 observations "
            f"conjointes requis. Détail dans {chemin}.",
        )

    return {"date_cycle": date_cycle, "nb_tickets_reels": len(tickets_reels)}


def main():
    resume = executer_cycle()
    print(
        f"[tickets réels] {resume['date_cycle']} -- "
        f"{resume['nb_tickets_reels']} vrai(s) ticket(s) construit(s)."
    )


if __name__ == "__main__":
    main()
