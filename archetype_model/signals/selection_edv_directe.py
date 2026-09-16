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
    3. Élimination des marchés redondants du même match -- CORRECTIF
       16/09/2026 : la première version de ce fichier utilisait une
       liste de paires figées à la main (Double Chance/Handicap
       uniquement). Patrick a signalé, à raison, que ce calcul existait
       déjà dans l'ancien moteur sous une forme plus générale
       (`calculs.py::correlation_marches`, Pearson exact sur la
       matrice Poisson jointe, seuil 0.70) -- porté ici tel quel
       (`poisson/correlation.py`), et vérifié donner un résultat
       identique à 1e-9 près sur plusieurs paires de marchés testées.
       Généralise à N'IMPORTE QUELLE paire de marchés du match, pas
       seulement Double Chance/Handicap -- et le seuil dépend des λ du
       match, pas d'une règle fixe (vérifié : Double Chance 1X et
       Handicap domicile +1 sont corrélés à 0.56 avec λ=1.6/1.1, donc
       EN DESSOUS du seuil 0.70 pour ce match précis -- l'ancienne
       liste figée aurait éliminé cette paire à tort ici).
    4. P1 = EDV le plus élevé parmi les survivants (profit maximal).
    5. P2 = probabilité la plus élevée parmi ce qui reste (le plus
       évident).
    6. P3 = cote la plus élevée parmi ce qui reste (le complémentaire).

STRUCTURE D'ENTRÉE ATTENDUE : liste de candidats déjà filtrés par
signals.convergence (donc déjà dans la fourchette de cote et au-dessus
de l'EDV minimum), chacun portant au moins "market_family",
"probabilite", "cote", "edv", et "condition" (fonction (buts_dom,
buts_ext) -> bool, nécessaire pour l'étape de corrélation -- un
candidat sans "condition" est gardé sans comparaison, jamais rejeté
par défaut). `selectionner()` prend aussi la matrice Poisson jointe du
match (`poisson.distribution.matrice_scores(lambda_dom, lambda_ext)`).
"""

from __future__ import annotations

from typing import Any, Optional

from ..poisson.correlation import correlation_marches

# Seuil de corrélation au-delà duquel deux marchés du même match sont
# jugés redondants -- repris TEL QUEL de l'ancien moteur
# (calculs.py::SEUIL_CORRELATION = 0.70, Module 3 v6.3 Étape 4), pas
# réinventé. Documenté là-bas comme "implémenté seulement" -- même
# statut V1/non recalibré que les autres seuils du projet.
SEUIL_CORRELATION = 0.70


def elimine_marches_correles(
    candidats: list[dict[str, Any]],
    matrice: list[list[float]],
    seuil_correlation: float = SEUIL_CORRELATION,
) -> list[dict[str, Any]]:
    """Réduit `candidats` en excluant tout candidat dont la corrélation
    de Pearson (calculée sur `matrice`, la matrice Poisson jointe du
    match) avec un candidat DÉJÀ retenu dépasse `seuil_correlation` --
    remplace une liste de paires figées à la main (Double Chance /
    Handicap uniquement) par le calcul mathématique déjà existant dans
    l'ancien moteur (`calculs.py::correlation_marches`/
    `construit_liste_b`), qui généralise à N'IMPORTE QUELLE paire de
    marchés sans jugement sémantique sur leurs noms.

    Parcourt `candidats` dans l'ordre reçu (l'appelant doit les avoir
    déjà triés dans l'ordre de priorité voulu -- EDV décroissant pour
    rester fidèle à l'ancien moteur) et garde un candidat seulement
    s'il n'est corrélé à AUCUN candidat déjà retenu. Chaque candidat
    doit porter une clé "condition" : fonction (buts_dom, buts_ext) ->
    bool. Un candidat sans "condition" est gardé sans jamais être
    comparé (corrélation indéterminable, jamais un rejet par défaut).
    """
    retenus: list[dict[str, Any]] = []
    for candidat in candidats:
        cond = candidat.get("condition")
        if cond is None:
            retenus.append(candidat)
            continue
        correle_a_un_retenu = any(
            r.get("condition") is not None
            and abs(correlation_marches(matrice, cond, r["condition"])) > seuil_correlation
            for r in retenus
        )
        if not correle_a_un_retenu:
            retenus.append(candidat)
    return retenus


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


def selectionner(candidats: list[dict[str, Any]], matrice: list[list[float]]) -> dict[str, Optional[dict[str, Any]]]:
    """Orchestrateur complet : élimination des marchés corrélés (Pearson
    exact sur `matrice`, seuil 0.70), candidats parcourus par EDV
    décroissant (fidèle à l'ancien moteur), puis P1 (EDV) -> P2
    (probabilité) -> P3 (cote), dans cet ordre. Retourne
    {"P1":..., "P2":..., "P3":...}, chaque valeur pouvant être None."""
    tries_par_edv = sorted(
        candidats,
        key=lambda c: c["edv"] if c.get("edv") is not None else float("-inf"),
        reverse=True,
    )
    survivants = elimine_marches_correles(tries_par_edv, matrice)
    p1 = selectionne_p1(survivants)
    p2 = selectionne_p2(survivants, p1)
    p3 = selectionne_p3(survivants, p1, p2)
    return {"P1": p1, "P2": p2, "P3": p3}


# ============================================================================
# DIAGNOSTIC DE DIFFÉRENCIATION -- même principe que selector.py (débranché
# le 16/09/2026, gardé de côté au cas où, jamais supprimé) : PUREMENT
# DIAGNOSTIC, appelé après coup, ne modifie ni ne recalcule la sélection.
# Nécessaire pour que justification.py puisse continuer à écrire une
# phrase vraie sur la raison du choix -- sans ça, la sélection
# fonctionne mais l'explication donnée à l'utilisateur redevient
# générique (voir justification.py::construit_raison_selection, repli
# "aucune_selection, critère absent ou inconnu" déjà prévu pour ce cas,
# mais moins informatif que d'avoir le vrai diagnostic).
# ============================================================================


def diagnostique_p1(candidats: list[dict[str, Any]], p1: Optional[dict[str, Any]]) -> dict[str, Any]:
    """P1 est choisi par EDV -- le diagnostic est donc toujours "edv"
    s'il y a au moins un concurrent, sans ambiguïté possible (un seul
    critère de choix, pas une cascade à départager)."""
    if p1 is None:
        return {"critere": "aucune_selection"}
    concurrents = [c for c in candidats if c is not p1 and c.get("edv") is not None]
    if not concurrents:
        return {"critere": "aucun_concurrent"}
    return {"critere": "edv", "valeur_gagnant": p1.get("edv"), "valeur_concurrent": max(c["edv"] for c in concurrents)}


def diagnostique_p2(candidats: list[dict[str, Any]], p1: Optional[dict[str, Any]], p2: Optional[dict[str, Any]]) -> dict[str, Any]:
    """P2 est choisi par probabilité -- même logique, un seul critère."""
    if p2 is None:
        return {"critere": "aucune_selection"}
    concurrents = [c for c in candidats if c is not p1 and c is not p2 and c.get("probabilite") is not None]
    if not concurrents:
        return {"critere": "aucun_concurrent"}
    return {"critere": "probabilite", "valeur_gagnant": p2.get("probabilite"), "valeur_concurrent": max(c["probabilite"] for c in concurrents)}


def diagnostique_p3(candidats: list[dict[str, Any]], p1: Optional[dict[str, Any]], p2: Optional[dict[str, Any]], p3: Optional[dict[str, Any]]) -> dict[str, Any]:
    """P3 est choisi par cote -- même logique, un seul critère."""
    if p3 is None:
        return {"critere": "aucune_selection"}
    exclus = {id(p1), id(p2)}
    concurrents = [c for c in candidats if id(c) not in exclus and c.get("cote") is not None]
    if not concurrents:
        return {"critere": "aucun_concurrent"}
    return {"critere": "cote", "valeur_gagnant": p3.get("cote"), "valeur_concurrent": max(c["cote"] for c in concurrents)}


def diagnostique_selection(candidats: list[dict[str, Any]], selection: dict[str, Optional[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Calcule le diagnostic des 3 rangs à partir du résultat déjà figé
    de `selectionner()` -- même contrat que selector.diagnostique_selection,
    pour rester une simple substitution du côté de main.py/justification.py."""
    p1, p2, p3 = selection.get("P1"), selection.get("P2"), selection.get("P3")
    return {
        "P1": diagnostique_p1(candidats, p1),
        "P2": diagnostique_p2(candidats, p1, p2),
        "P3": diagnostique_p3(candidats, p1, p2, p3),
    }
