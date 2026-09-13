"""
tickets/cycle.py — Cadence de génération des tickets.

Pourquoi ce module existe : produire jusqu'à MAX_TICKETS tickets par
cycle, sans jamais dégrader les critères de builder.py pour "remplir le
quota" -- 0 ticket est un résultat normal et honnête si aucune
combinaison de jambes ne satisfait la Règle C ce jour-là.

Chaque candidat n'est utilisé que dans UN SEUL ticket par cycle -- une
fois un ticket construit, ses jambes sont retirées du pool avant de
tenter le ticket suivant, pour ne jamais répéter la même jambe dans deux
tickets différents le même jour.

Ce module n'a aucune autorité sur le calibrage ni sur la sélection
P1/P2/P3 -- il ne fait que consommer des candidats déjà décidés ailleurs.
"""

from __future__ import annotations

from typing import Any

from tickets import builder

TAILLE_TICKET = builder.TAILLE_TICKET
MAX_TICKETS = 5


def generer_tickets(
    candidats_du_jour: list[dict[str, Any]],
    records_resolus: list[dict[str, Any]],
    max_tickets: int = MAX_TICKETS,
    taille: int = TAILLE_TICKET,
) -> list[dict[str, Any]]:
    """Retourne entre 0 et `max_tickets` tickets -- jamais plus, jamais
    un ticket incomplet pour atteindre le quota. `records_resolus` :
    l'archive SELECTED résolue, utilisée pour construire la matrice de
    dépendance (voir builder.construire_marginal_et_matrice) -- recalculée
    une seule fois par cycle, jamais par ticket."""
    marginal, matrice = builder.construire_marginal_et_matrice(records_resolus)

    tickets: list[dict[str, Any]] = []
    disponibles = list(candidats_du_jour)

    for _ in range(max_tickets):
        ticket = builder.construire_ticket(disponibles, marginal, matrice, taille=taille)
        if ticket is None:
            break  # jamais insister avec des critères dégradés
        tickets.append(ticket)
        match_ids_utilises = {c.get("match_id") for c in ticket["jambes"]}
        disponibles = [c for c in disponibles if c.get("match_id") not in match_ids_utilises]

    return tickets
