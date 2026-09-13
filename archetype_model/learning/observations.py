"""
archetype_model/learning/observations.py — Observations exploitables.

Pourquoi ce module existe : resultats.py sait désormais dire GAGNE/PERDU
pour un marché, mais rien ne calcule encore le gain réel en mise flat, et
rien ne sépare les vrais paris (SELECTED) des marchés qui n'ont jamais été
joués (COUNTERFACTUAL, catégorie A) pour la mesure de performance réelle.

Règle non négociable, vérifiée avec Patrick le 12/09/2026 : les
COUNTERFACTUAL ne sont JAMAIS mélangés aux observations de performance --
ils servent uniquement au futur mécanisme de test contrefactuel
(contrefactuel.py, pas encore construit), qui les lira séparément depuis
l'archive. Les inclure ici fausserait le ROI réel en y ajoutant des paris
qui n'ont jamais été pris.

Aucune donnée n'est jamais devinée : un enregistrement sans cote, ou dont
le statut n'est ni WIN ni LOSS (PENDING, NON_RESOLU_DEFINITIF), ne produit
aucune observation -- jamais un gain à zéro ou une estimation par défaut.
"""

from __future__ import annotations

import glob
import os
from typing import Any, Iterable

from archetype_model.learning import archive

GAGNE = "WIN"
PERDU = "LOSS"


def calcule_gain_flat_stake(resultat_marche: str | None, cote: float | None) -> float | None:
    """mise = 1.0 -- GAIN = cote - 1 si gagné, -1 si perdu. Retourne None si
    le résultat ou la cote sont absents/invalides : jamais une valeur
    inventée pour un cas qui ne devrait normalement pas se produire."""
    if resultat_marche == GAGNE:
        if not isinstance(cote, (int, float)) or cote <= 1:
            return None
        return float(cote) - 1.0
    if resultat_marche == PERDU:
        return -1.0
    return None


def construire_observations(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ne garde que les enregistrements SELECTED et RESOLVED. Les
    COUNTERFACTUAL, les PENDING et les NON_RESOLU_DEFINITIF ne produisent
    jamais d'observation ici."""
    observations: list[dict[str, Any]] = []
    for record in records:
        if record.get("categorie") != archive.CATEGORIE_SELECTED:
            continue
        if record.get("resultat_statut") != archive.STATUT_RESOLVED:
            continue

        gain = calcule_gain_flat_stake(record.get("resultat_marche"), record.get("cote"))
        if gain is None:
            continue  # cote/résultat invalide -- ne doit normalement jamais arriver

        observations.append({
            "match_id": record.get("match_id"),
            "date_match": record.get("date_match"),
            "marche": record.get("marche"),
            "market_family": record.get("market_family"),
            "exposure_group": record.get("exposure_group"),
            "niveau": record.get("niveau"),
            "robustesse": record.get("robustesse"),
            "probabilite": record.get("probabilite"),
            "cote": record.get("cote"),
            "edge": record.get("edge"),
            "edv": record.get("edv"),
            "h2h_palier": record.get("h2h_palier"),
            "signal_direction": record.get("signal_direction"),
            "resultat": record.get("resultat_marche"),
            "gain_flat_stake": gain,
        })
    return observations


def charge_toutes_les_archives(repertoire: str = "archive") -> list[dict[str, Any]]:
    """Concatène les enregistrements de tous les fichiers archive/YYYY-MM.json
    présents -- y compris ceux déjà condensés par le rollup mensuel, tant
    qu'ils restent au format d'enregistrement standard."""
    records: list[dict[str, Any]] = []
    for chemin in sorted(glob.glob(os.path.join(repertoire, "*.json"))):
        records.extend(archive.charger_archive(chemin))
    return records
