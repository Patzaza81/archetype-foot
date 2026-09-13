"""
archetype_model/learning/matrice.py — Matrice comportementale hiérarchique.

Pourquoi ce module existe : accumuler les observations (observations.py) en
statistiques agrégées, pour que calibration.py ait quelque chose à analyser
plus tard. Purement mécanique -- ce module ne juge jamais si un segment a
"assez" de données pour être exploitable : c'est le rôle futur de
garde_fous.py, jamais celui-ci.

Hiérarchie retenue (cahier des charges v2 §7, réponse du bureau d'étude à
la Question 6) : GLOBAL -> FAMILLE -> NIVEAU. Pas de croisement plus fin
pour l'instant (compétition, tranche de cote) -- à ajouter plus tard si
justifié, jamais improvisé ici.

Une famille ou un niveau absent d'une observation est classé sous
"INCONNUE"/"INCONNU" -- jamais silencieusement ignoré, jamais fusionné avec
une vraie catégorie par approximation.
"""

from __future__ import annotations

from typing import Any, Iterable

FAMILLE_INCONNUE = "INCONNUE"
NIVEAU_INCONNU = "INCONNU"


def _nouveau_bucket() -> dict[str, Any]:
    return {
        "observations": 0,
        "gagnes": 0,
        "perdus": 0,
        "somme_gains_flat_stake": 0.0,
        "roi_flat": None,
    }


def _accumule(bucket: dict[str, Any], observation: dict[str, Any]) -> None:
    bucket["observations"] += 1
    if observation["resultat"] == "WIN":
        bucket["gagnes"] += 1
    elif observation["resultat"] == "LOSS":
        bucket["perdus"] += 1
    bucket["somme_gains_flat_stake"] += observation["gain_flat_stake"]
    bucket["roi_flat"] = bucket["somme_gains_flat_stake"] / bucket["observations"]


def construire_matrice(observations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Retourne {"global": bucket, "par_famille": {famille: {"resume":
    bucket, "par_niveau": {niveau: bucket}}}}."""
    matrice: dict[str, Any] = {"global": _nouveau_bucket(), "par_famille": {}}

    for observation in observations:
        _accumule(matrice["global"], observation)

        famille = observation.get("market_family") or FAMILLE_INCONNUE
        bucket_famille = matrice["par_famille"].setdefault(
            famille, {"resume": _nouveau_bucket(), "par_niveau": {}}
        )
        _accumule(bucket_famille["resume"], observation)

        niveau = observation.get("niveau") or NIVEAU_INCONNU
        bucket_niveau = bucket_famille["par_niveau"].setdefault(niveau, _nouveau_bucket())
        _accumule(bucket_niveau, observation)

    return matrice
