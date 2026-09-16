"""
archetype_model/signals/rapport.py — Rapport JSON structuré par match,
format proposé par Patrick le 16/09/2026 (conçu ailleurs, adapté ici
aux vraies données du système).

Champs directement mappés sur des données réelles déjà calculées :
    market_name        <- candidat["marche"]
    odds                <- candidat["cote"]
    p_poisson           <- candidat["probabilite"]
    edv                 <- candidat["edv"]
    h2h_reliability     <- candidat["h2h_palier"]
    final_status        <- "SELECTED" si P1/P2/P3, sinon "REJECTED"
    rank                <- "P1"/"P2"/"P3" ou None
    rejection_reason    <- convergence.MotifRejet (déjà existant, codes
                           réutilisés tels quels : DONNEES_INSUFFISANTES,
                           COTE_HORS_INTERVALLE, EDV_INSUFFISANTE, etc.)
                           + 3 nouveaux codes pour les étapes après
                           convergence (dédup/corrélation/sélection),
                           qui n'avaient pas encore de code de rejet
                           tracé explicitement avant ce rapport.

UN SEUL CHAMP N'EST PAS UNE DONNÉE DÉJÀ CALCULÉE PAR LE SYSTÈME :
    score_pondere       <- PROPOSÉ ici (voir _score_pondere_propose),
                           n'existe nulle part ailleurs pour les
                           candidats du moteur Poisson (le concept
                           existait uniquement dans
                           statistics.matrice_croisement, un système
                           séparé, pas encore branché). Formule
                           proposée pour ne pas bloquer : à valider ou
                           remplacer, jamais présentée comme déjà
                           établie.
"""

from __future__ import annotations

import datetime
from typing import Any

from . import selection_edv_directe as sel


# CODES DE REJET AJOUTÉS ICI (16/09/2026) -- convergence.MotifRejet
# couvre déjà tout ce qui se passe AVANT qu'un marché devienne un
# candidat. Ces 3 codes couvrent les étapes D'APRÈS, qui n'avaient
# jamais eu besoin d'un code de rejet tracé avant ce rapport (les
# fonctions elles-mêmes se contentent de ne pas inclure l'élément
# rejeté dans leur liste de sortie, sans dire pourquoi).
ELIMINE_PAR_DEDUPLICATION_FAMILLE = "ELIMINE_PAR_DEDUPLICATION_FAMILLE"
ELIMINE_PAR_CORRELATION = "ELIMINE_PAR_CORRELATION"
NON_SELECTIONNE = "NON_SELECTIONNE"


def _score_pondere_propose(candidat: dict[str, Any]) -> float | None:
    """PROPOSITION, pas une valeur déjà établie dans le système --
    combine probabilité et EDV en un seul nombre : une probabilité
    haute ET un EDV positif donnent un score au-dessus de la
    probabilité seule ; un EDV négatif le fait redescendre en dessous.
    Formule volontairement simple pour rester lisible et débattable
    facilement -- Patrick peut la remplacer sans casser le reste du
    rapport (seule cette fonction serait à changer)."""
    p, edv = candidat.get("probabilite"), candidat.get("edv")
    if p is None or edv is None:
        return None
    return round(p * (1 + edv), 4)


def _rang_pour(candidat: dict[str, Any], selection: dict[str, Any]) -> str | None:
    for rang in ("P1", "P2", "P3"):
        if selection.get(rang) is candidat:
            return rang
    return None


def construit_rapport(
    match_id: str,
    diagnostics: list[dict[str, Any]],
    candidats: list[dict[str, Any]],
    candidats_dedupliques: list[dict[str, Any]],
    matrice: list[list[float]] | None,
    selection: dict[str, Any],
) -> dict[str, Any]:
    """Construit le rapport JSON complet pour un match, format proposé
    par Patrick. `diagnostics`, `candidats`, `candidats_dedupliques`,
    `matrice` et `selection` sont exactement ce que retourne déjà
    `main.analyse_match_complet()` -- aucune donnée recalculée en
    double, seulement réorganisée."""
    resultats: list[dict[str, Any]] = []

    # 1. Marchés rejetés AVANT de devenir candidats (convergence.py) --
    # motif_rejet déjà calculé, jamais recalculé ici.
    ids_devenus_candidats = {id_c["marche"] for id_c in candidats}
    for diag in diagnostics:
        if diag["marche"] in ids_devenus_candidats:
            continue
        filtre = diag.get("filtre", {})
        resultats.append({
            "market_name": diag["marche"],
            "odds": None, "score_pondere": None, "p_poisson": None, "edv": None,
            "h2h_reliability": diag.get("h2h_statut"),
            "final_status": "REJECTED", "rank": None,
            "rejection_reason": filtre.get("motif_rejet") or filtre.get("motif"),
        })

    # 2. Candidats éliminés par la déduplication (même famille, edge plus faible)
    dedupliques_marches = {c["marche"] for c in candidats_dedupliques}
    for c in candidats:
        if c["marche"] in dedupliques_marches:
            continue
        resultats.append({
            "market_name": c["marche"], "odds": c.get("cote"),
            "score_pondere": _score_pondere_propose(c), "p_poisson": c.get("probabilite"),
            "edv": c.get("edv"), "h2h_reliability": c.get("h2h_palier"),
            "final_status": "REJECTED", "rank": None,
            "rejection_reason": ELIMINE_PAR_DEDUPLICATION_FAMILLE,
        })

    # 3. Survivants après corrélation réelle (recalculé ici à l'identique
    # de ce que selection_edv_directe.selectionner() fait en interne --
    # jamais exposé séparément avant ce rapport)
    if matrice is not None:
        tries = sorted(candidats_dedupliques, key=lambda c: c["edv"] if c.get("edv") is not None else float("-inf"), reverse=True)
        survivants = sel.elimine_marches_correles(tries, matrice)
    else:
        survivants = list(candidats_dedupliques)
    survivants_marches = {c["marche"] for c in survivants}
    for c in candidats_dedupliques:
        if c["marche"] in survivants_marches:
            continue
        resultats.append({
            "market_name": c["marche"], "odds": c.get("cote"),
            "score_pondere": _score_pondere_propose(c), "p_poisson": c.get("probabilite"),
            "edv": c.get("edv"), "h2h_reliability": c.get("h2h_palier"),
            "final_status": "REJECTED", "rank": None,
            "rejection_reason": ELIMINE_PAR_CORRELATION,
        })

    # 4. Survivants finaux : SELECTED (P1/P2/P3) ou NON_SELECTIONNE
    for c in survivants:
        rang = _rang_pour(c, selection)
        resultats.append({
            "market_name": c["marche"], "odds": c.get("cote"),
            "score_pondere": _score_pondere_propose(c), "p_poisson": c.get("probabilite"),
            "edv": c.get("edv"), "h2h_reliability": c.get("h2h_palier"),
            "final_status": "SELECTED" if rang else "REJECTED",
            "rank": rang,
            "rejection_reason": None if rang else NON_SELECTIONNE,
        })

    return {
        "match_id": match_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scan_summary": {
            "total_markets_scanned": len(diagnostics),
            "admissible_count": len(candidats_dedupliques),
            "selected_p1": selection["P1"]["marche"] if selection.get("P1") else None,
            "selected_p2": selection["P2"]["marche"] if selection.get("P2") else None,
        },
        "results": resultats,
    }
