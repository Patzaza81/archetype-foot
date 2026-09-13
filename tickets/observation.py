"""
tickets/observation.py — Tickets fictifs (mode observation).

Pourquoi ce module existe : Patrick a demandé un retour rapide sur la
question des tickets, sans attendre les mois nécessaires pour atteindre
SEUIL_OBSERVATIONS_CONJOINTES=100 sur de vraies paires de signatures
(builder.py, jamais modifié par ce fichier). Décision du 13/09/2026 :
construire des tickets FICTIFS avec un seuil abaissé, les enregistrer
séparément, suivre si leur probabilité annoncée tient réellement sur la
durée -- sans jamais les présenter comme de vrais tickets jouables, et
sans jamais abaisser le seuil réel de builder.py.

Un ticket fictif combine des jambes déjà réellement sélectionnées et déjà
réellement archivées par archive.py -- ce module ne recalcule ni ne
réévalue rien, il applique juste builder.construire_ticket() avec un
seuil d'observations plus permissif, et journalise le résultat.

GARDE-FOU NON NÉGOCIABLE : ce fichier n'écrit jamais dans archive/ ni
dans un chemin lu par le site public -- uniquement dans
tickets_observes/YYYY-MM.json, un espace de données entièrement séparé.
Un ticket fictif ne doit jamais pouvoir être confondu avec un vrai
ticket ni apparaître comme tel nulle part.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tickets import builder

# Seuil délibérément abaissé par rapport à builder.SEUIL_OBSERVATIONS_CONJOINTES
# (100) -- UNIQUEMENT pour les tickets fictifs de ce module. Valeur de
# départ non validée, comme les autres constantes non calibrées du
# projet -- à ajuster si l'expérience le justifie.
SEUIL_OBSERVATION = 10

REPERTOIRE_DEFAUT = "tickets_observes"


def chemin_tickets_observes(date_construction: str, repertoire: str = REPERTOIRE_DEFAUT) -> str:
    annee_mois = str(date_construction)[:7]  # "2026-09-13" -> "2026-09"
    return str(Path(repertoire) / f"{annee_mois}.json")


def _charge(chemin: str) -> list[dict[str, Any]]:
    path = Path(chemin)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _sauve_atomique(chemin: str, tickets: list[dict[str, Any]]) -> None:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def construire_ticket_observation(
    candidats: list[dict[str, Any]],
    marginal: dict[tuple, dict[str, int]],
    matrice: dict[tuple, dict[str, int]],
    taille: int = builder.TAILLE_TICKET,
    seuil_observations: int = SEUIL_OBSERVATION,
) -> dict[str, Any] | None:
    """Identique à builder.construire_ticket(), avec le seuil
    d'observations abaissé -- jamais les bornes D, qui restent celles de
    builder.py (BORNES_D_ACCEPTABLE) : seule la TAILLE de l'échantillon
    requis change ici, jamais ce qui définit une dépendance acceptable."""
    return builder.construire_ticket(
        candidats, marginal, matrice, taille=taille, seuil_observations=seuil_observations,
    )


def enregistrer_ticket_observe(
    ticket: dict[str, Any],
    date_construction: str,
    repertoire: str = REPERTOIRE_DEFAUT,
) -> None:
    """Ajoute un ticket fictif au fichier du mois -- toujours en statut
    PENDING à l'écriture, jamais un résultat inventé avant que toutes ses
    jambes ne soient réellement résolues."""
    chemin = chemin_tickets_observes(date_construction, repertoire)
    tickets = _charge(chemin)
    tickets.append({
        "date_construction": date_construction,
        "jambes": [
            {"match_id": j.get("match_id"), "marche": j.get("marche"), "probabilite": j.get("probabilite")}
            for j in ticket["jambes"]
        ],
        "probabilite_annoncee": ticket["probabilite_ticket"],
        "statut_resolution": "PENDING",
        "resultat_reel": None,
    })
    _sauve_atomique(chemin, tickets)


def resoudre_tickets_observes(
    chemin: str,
    records_resolus: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pour chaque ticket PENDING du fichier, vérifie si TOUTES ses
    jambes ont désormais un résultat réel connu (via records_resolus --
    l'archive SELECTED+RESOLVED). Si oui, fige le résultat : WIN
    seulement si TOUTES les jambes ont gagné, LOSS sinon. Un ticket déjà
    RESOLVED n'est jamais retouché. Retourne la liste complète mise à
    jour (et la sauvegarde sur disque si au moins un ticket a changé)."""
    index = {(r.get("match_id"), r.get("marche")): r.get("resultat_marche") for r in records_resolus}
    tickets = _charge(chemin)
    modifie = False

    for ticket in tickets:
        if ticket.get("statut_resolution") == "RESOLVED":
            continue

        resultats_jambes = []
        toutes_connues = True
        for jambe in ticket["jambes"]:
            resultat = index.get((jambe.get("match_id"), jambe.get("marche")))
            if resultat not in ("WIN", "LOSS"):
                toutes_connues = False
                break
            resultats_jambes.append(resultat)

        if toutes_connues:
            ticket["statut_resolution"] = "RESOLVED"
            ticket["resultat_reel"] = "WIN" if all(r == "WIN" for r in resultats_jambes) else "LOSS"
            modifie = True

    if modifie:
        _sauve_atomique(chemin, tickets)
    return tickets
