"""
tickets/rapport_calibration.py — Probabilité annoncée vs réalité.

Pourquoi ce module existe : c'est la preuve, pas la promesse. Compare,
sur tous les tickets fictifs RESOLVED (tickets/observation.py), la
probabilité annoncée moyenne (produit des probabilités individuelles) au
taux de réussite réellement observé. Si l'écart est systématiquement
optimiste (annoncé > réel), c'est le signe qu'une dépendance existe
malgré le contrôle par paire -- exactement le biais que le seuil réel de
100 observations (builder.py) est censé éviter.

Ce rapport ne décide jamais rien seul -- il ne modifie ni
SEUIL_OBSERVATIONS_CONJOINTES (builder.py) ni SEUIL_OBSERVATION
(observation.py). C'est une lecture pour Patrick, pas un déclencheur
automatique.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from tickets import observation


def charge_tous_les_tickets_observes(repertoire: str = observation.REPERTOIRE_DEFAUT) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for chemin in sorted(glob.glob(str(Path(repertoire) / "*.json"))):
        tickets.extend(observation._charge(chemin))
    return tickets


def construit_rapport(tickets_observes: list[dict[str, Any]]) -> dict[str, Any]:
    """Ne considère que les tickets RESOLVED -- un PENDING n'a pas encore
    de résultat à comparer. Retourne une structure honnête même à 0
    ticket résolu (jamais une division par zéro, jamais un écart inventé)."""
    resolus = [t for t in tickets_observes if t.get("statut_resolution") == "RESOLVED"]
    n = len(resolus)
    if n == 0:
        return {
            "nb_tickets_resolus": 0,
            "probabilite_annoncee_moyenne": None,
            "taux_reussite_reel": None,
            "ecart": None,
        }

    proba_moyenne = sum(t["probabilite_annoncee"] for t in resolus) / n
    taux_reel = sum(1 for t in resolus if t["resultat_reel"] == "WIN") / n

    return {
        "nb_tickets_resolus": n,
        "probabilite_annoncee_moyenne": proba_moyenne,
        "taux_reussite_reel": taux_reel,
        "ecart": taux_reel - proba_moyenne,
    }
