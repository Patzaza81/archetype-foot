"""
archetype_model/learning/validation.py — Validation historique et hors
échantillon.

Pourquoi ce module existe : une amélioration mesurée sur TOUT l'historique
peut n'être qu'un sur-ajustement au bruit. Ce module sépare les
enregistrements en deux zones AVANT tout test contrefactuel :
- zone d'APPRENTISSAGE : sert à repérer une amélioration candidate ;
- zone de VALIDATION (hors échantillon) : ne sert JAMAIS à choisir la
  modification, uniquement à confirmer qu'elle tient aussi sur des
  données qu'elle n'a pas "vues".

Une modification n'est retenue que si elle améliore le comportement dans
les DEUX zones -- le garde-fou statistique le plus important selon le
bureau d'étude (rapport du 12/09/2026, §12).

Découpage retenu : CHRONOLOGIQUE, jamais aléatoire -- les enregistrements
les plus ANCIENS (par date_match) forment la zone d'apprentissage, les
plus récents la zone de validation. Un découpage aléatoire mélangerait
des observations d'une même période (mêmes compétitions, même contexte)
entre les deux zones, ce qui romprait justement l'indépendance
recherchée.

Ce module ne décide jamais seul si une proposition doit être promue --
il produit un verdict d'amélioration constatée dans chaque zone,
calibration.py (pas encore construit) décide quoi en faire, sous les
garde-fous de garde_fous.py.
"""

from __future__ import annotations

from typing import Any

from archetype_model.learning import contrefactuel

PROPORTION_APPRENTISSAGE = 0.7  # 70% le plus ancien -- valeur de départ, non calibrée


def _cle_tri(record: dict[str, Any]) -> str:
    return str(record.get("date_match") or "")


def decoupe_apprentissage_validation(
    records: list[dict[str, Any]],
    proportion_apprentissage: float = PROPORTION_APPRENTISSAGE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Trie par date_match croissante, coupe aux `proportion_apprentissage`
    premiers enregistrements. Ne mélange jamais les deux zones -- un même
    enregistrement n'apparaît jamais dans les deux. La zone de validation
    peut être vide si trop peu d'enregistrements (jamais une exception
    pour ce cas, juste un résultat honnête plus loin dans la chaîne)."""
    if not 0 < proportion_apprentissage < 1:
        raise ValueError("proportion_apprentissage doit être strictement entre 0 et 1")
    tries = sorted(records, key=_cle_tri)
    coupure = int(len(tries) * proportion_apprentissage)
    return tries[:coupure], tries[coupure:]


def _ameliore(resultat: contrefactuel.ResultatContrefactuel) -> bool:
    return (
        resultat.roi_actuel is not None
        and resultat.roi_contrefactuel is not None
        and resultat.roi_contrefactuel > resultat.roi_actuel
    )


def valide_hors_echantillon(
    parametre: str,
    valeur_actuelle: float,
    valeur_proposee: float,
    selections_resolues: list[dict[str, Any]],
    contrefactuels_resolus: list[dict[str, Any]],
    proportion_apprentissage: float = PROPORTION_APPRENTISSAGE,
) -> dict[str, Any]:
    """Teste `parametre` -> `valeur_proposee` séparément sur la zone
    d'apprentissage et sur la zone de validation (découpées
    indépendamment pour les SELECTED et pour les COUNTERFACTUAL,
    chronologiquement, avec la même proportion).

    Retourne un dict avec les deux résultats contrefactuels détaillés et
    un booléen `ameliore_les_deux_zones` -- True SEULEMENT si le ROI
    contrefactuel dépasse le ROI actuel dans LES DEUX zones. Si une zone
    n'a aucune observation résolue (ROI indéterminé), elle compte comme
    "n'améliore pas" -- jamais une absence de preuve traitée comme une
    preuve favorable.
    """
    sel_appr, sel_val = decoupe_apprentissage_validation(selections_resolues, proportion_apprentissage)
    cf_appr, cf_val = decoupe_apprentissage_validation(contrefactuels_resolus, proportion_apprentissage)

    resultat_apprentissage = contrefactuel.tester_parametre(
        parametre, valeur_actuelle, valeur_proposee, sel_appr, cf_appr
    )
    resultat_validation = contrefactuel.tester_parametre(
        parametre, valeur_actuelle, valeur_proposee, sel_val, cf_val
    )

    ameliore_apprentissage = _ameliore(resultat_apprentissage)
    ameliore_validation = _ameliore(resultat_validation)

    return {
        "apprentissage": resultat_apprentissage,
        "validation": resultat_validation,
        "ameliore_apprentissage": ameliore_apprentissage,
        "ameliore_validation": ameliore_validation,
        "ameliore_les_deux_zones": ameliore_apprentissage and ameliore_validation,
    }
