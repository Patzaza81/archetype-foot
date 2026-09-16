"""
archetype_model/signals/selection_edv_directe.py — Second sélecteur
P1/P2/P3, construit à la demande explicite de Patrick le 16/09/2026,
en PARALLÈLE de la cascade existante (`selector.py`, décision du
09/09/2026) -- ne la remplace pas, ne la modifie pas. Les deux
sélecteurs pourront être comparés plus tard sur des résultats réels
(même logique que le "tournoi de sélecteurs" discuté avec l'autre IA
dans DIALOGUE_IA_MATRICE.md) plutôt que d'écraser silencieusement une
décision déjà prise et documentée.

LOGIQUE DEMANDÉE PAR PATRICK (verbatim reformulé) :
    1. Filtre cote [COTE_MIN, COTE_MAX] -- déjà fait par
       signals.convergence, pas refait ici.
    2. Filtre EDV minimum -- déjà fait par signals.convergence (table
       graduée par probabilité, PAS le seuil fixe 5% évoqué par
       Patrick -- voir DIALOGUE_IA_MATRICE.md pour la discussion ;
       gardé gradué ici par choix de robustesse, réversible si Patrick
       confirme vouloir le seuil fixe après coup).
    3. Élimination des marchés CONCORDANTS (économiquement redondants,
       ex. Double Chance et Handicap) -- garder celui à la cote la
       plus élevée. NOUVEAU : ne réutilise PAS exposure_group de
       main.py (qui met DOUBLE_CHANCE et HANDICAP dans des groupes
       DIFFÉRENTS aujourd'hui) -- une notion de concordance séparée,
       propre à ce sélecteur, pour ne pas modifier le comportement de
       l'ancien sélecteur qui dépend de exposure_group tel quel.
    4. P1 = EDV le plus élevé parmi les survivants (profit maximal).
    5. P2 = probabilité la plus élevée parmi ce qui reste (le plus
       évident).
    6. P3 = cote la plus élevée parmi ce qui reste (le complémentaire).

STRUCTURE D'ENTRÉE ATTENDUE : liste de candidats déjà filtrés par
signals.convergence (donc déjà dans la fourchette de cote et au-dessus
de l'EDV minimum), chacun portant au moins "market_family",
"probabilite", "cote", "edv".
"""

from __future__ import annotations

from typing import Any, Optional

# Groupes de concordance -- DISTINCTS de exposure_group (main.py).
# Liste FERMÉE, même principe que config/adaptive_parameters.json :
# toute extension est une décision humaine documentée, jamais une
# initiative du système. Contient pour l'instant uniquement la paire
# explicitement citée par Patrick (16/09/2026) ; toute famille absente
# de cette table est considérée comme son propre groupe (pas
# concordante avec une autre par défaut -- sécurité, pas une
# supposition d'équivalence non demandée).
GROUPES_CONCORDANCE: dict[str, str] = {
    "DOUBLE_CHANCE": "CONCORDANT_RESULTAT_HANDICAP",
    "HANDICAP": "CONCORDANT_RESULTAT_HANDICAP",
}


def _groupe_concordance(market_family: str) -> str:
    """Le groupe de concordance d'une famille -- son propre nom si elle
    n'est dans aucun groupe explicite (jamais fusionnée par défaut)."""
    return GROUPES_CONCORDANCE.get(market_family, market_family)


def elimine_marches_concordants(candidats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Réduit `candidats` à au plus UN par groupe de concordance --
    celui avec la cote la plus élevée est gardé (demande explicite de
    Patrick). Ne modifie pas `candidats`, retourne une nouvelle liste.
    Un candidat sans "cote" numérique est traité comme le moins
    prioritaire de son groupe (jamais une exception)."""
    par_groupe: dict[str, dict[str, Any]] = {}
    for c in candidats:
        groupe = _groupe_concordance(c["market_family"])
        cote = c.get("cote")
        cote_valeur = cote if cote is not None else float("-inf")
        actuel = par_groupe.get(groupe)
        if actuel is None or cote_valeur > (actuel.get("cote") if actuel.get("cote") is not None else float("-inf")):
            par_groupe[groupe] = c
    return list(par_groupe.values())


def selectionne_p1(candidats: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """P1 = EDV le plus élevé. None si `candidats` est vide."""
    if not candidats:
        return None
    avec_edv = [c for c in candidats if c.get("edv") is not None]
    if not avec_edv:
        return None
    return max(avec_edv, key=lambda c: c["edv"])


def selectionne_p2(candidats: list[dict[str, Any]], p1: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """P2 = probabilité la plus élevée parmi ce qui reste après P1.
    None si P1 est None ou si rien ne reste."""
    if p1 is None:
        return None
    reste = [c for c in candidats if c is not p1 and c.get("probabilite") is not None]
    if not reste:
        return None
    return max(reste, key=lambda c: c["probabilite"])


def selectionne_p3(candidats: list[dict[str, Any]], p1: Optional[dict[str, Any]], p2: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """P3 = cote la plus élevée parmi ce qui reste après P1 et P2.
    None si P1 est None (pas de P3 sans P1/P2 déjà posés), ou si rien
    ne reste -- résultat normal, pas une erreur (même principe que
    l'ancien sélecteur, CORRECTIF 10)."""
    if p1 is None:
        return None
    exclus = {id(p1)} | ({id(p2)} if p2 is not None else set())
    reste = [c for c in candidats if id(c) not in exclus and c.get("cote") is not None]
    if not reste:
        return None
    return max(reste, key=lambda c: c["cote"])


def selectionner(candidats: list[dict[str, Any]]) -> dict[str, Optional[dict[str, Any]]]:
    """Orchestrateur complet : élimination des marchés concordants,
    puis P1 (EDV) -> P2 (probabilité) -> P3 (cote), dans cet ordre.
    Retourne {"P1":..., "P2":..., "P3":...}, chaque valeur pouvant être
    None (voir les fonctions individuelles pour les conditions)."""
    survivants = elimine_marches_concordants(candidats)
    p1 = selectionne_p1(survivants)
    p2 = selectionne_p2(survivants, p1)
    p3 = selectionne_p3(survivants, p1, p2)
    return {"P1": p1, "P2": p2, "P3": p3}
