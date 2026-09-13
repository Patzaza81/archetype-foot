"""
archetype_model/learning/extraction.py — Marchés proches du seuil.

Pourquoi ce module existe : quand un match n'a produit aucune sélection
(P1/P2/P3 tous None), archive.py doit pouvoir enregistrer les marchés qui
ont FAILLI passer le filtre de convergence -- c'est la mémoire nécessaire
au futur contrefactuel.py ("et si le seuil était légèrement différent ?").
Sans cette extraction, seuls les marchés réellement sélectionnés seraient
archivés, et le contrefactuel n'aurait jamais de matière sur les marchés
qui échouent aujourd'hui.

Source des données : diagnostics[i]["filtre"], produit par
convergence.filtre_marche_convergent().as_dict() -- jamais recalculé ici,
uniquement relu. Ce module ne fait aucun calcul de probabilité, d'EDV ou
de robustesse : il se contente de lire ce que le moteur a déjà décidé et
de retenir les cas proches du seuil.

Ne retient que les motifs de rejet NUMÉRIQUES (PROBABILITE_TROP_FAIBLE,
EDV_INSUFFISANTE, COTE_HORS_INTERVALLE) -- les motifs structurels
(DONNEES_INSUFFISANTES, COTE_INVALIDE, ROBUSTESSE_*) ne sont jamais
"proches d'un seuil" au sens numérique, donc jamais retenus ici, quelle
que soit la fenêtre choisie.

CORRECTIF 13/09/2026 : COTE_HORS_INTERVALLE ajouté aux motifs numériques.
Sans lui, contrefactuel.py n'aurait jamais pu tester un ÉLARGISSEMENT de
COTE_MIN/COTE_MAX (seul un rétrécissement, sur les SELECTED déjà archivés,
aurait été possible) -- oubli identifié en concevant contrefactuel.py, pas
un choix délibéré au départ. COTE_MIN/COTE_MAX relus directement depuis
convergence.py, jamais dupliqués en dur ici.

Fenêtres retenues (proposées dans l'audit du 12/09/2026, à raffiner si
l'expérience le justifie -- même statut que les autres constantes non
calibrées du projet) : 0.03 de probabilité, 0.02 d'EDV, 0.05 de cote.
"""

from __future__ import annotations

from typing import Any

from archetype_model.signals.convergence import COTE_MIN, COTE_MAX

SEUIL_PROBABILITE_MINIMAL = 0.63  # borne ELIGIBLE_PLUS, la plus basse -- convergence.py
FENETRE_PROBABILITE = 0.03
FENETRE_EDV = 0.02
FENETRE_COTE = 0.05

_MOTIFS_NUMERIQUES = frozenset({
    "PROBABILITE_TROP_FAIBLE", "EDV_INSUFFISANTE", "COTE_HORS_INTERVALLE",
})


def extraire_marche_proche(
    diagnostic: dict[str, Any],
    fenetre_probabilite: float = FENETRE_PROBABILITE,
    fenetre_edv: float = FENETRE_EDV,
    fenetre_cote: float = FENETRE_COTE,
) -> dict[str, Any] | None:
    """Retourne un dict prêt pour archive.enregistrer_contrefactuel() si ce
    marché rejeté est proche du seuil qui l'a fait échouer, sinon None.

    `diagnostic` : un élément de la liste `diagnostics` retournée par
    analyse_match_complet() -- {"marche": ..., "filtre": {...}, ...}.
    """
    filtre = diagnostic.get("filtre") or {}
    if filtre.get("eligible"):
        return None  # marché accepté -- pas un "marché proche du seuil rejeté"

    scenario_en_echec = filtre.get("scenario_en_echec")
    motif = filtre.get("motif_rejet")
    if scenario_en_echec is None or motif not in _MOTIFS_NUMERIQUES:
        return None

    detail = (filtre.get("resultats_par_scenario") or {}).get(scenario_en_echec) or {}
    probabilite = detail.get("probabilite_centrale")
    edv = detail.get("edv")
    edv_min_requis = detail.get("edv_min_requis")
    cote = detail.get("cote")

    proche = False
    if motif == "EDV_INSUFFISANTE" and edv is not None and edv_min_requis is not None:
        proche = (edv_min_requis - edv) <= fenetre_edv
    elif motif == "PROBABILITE_TROP_FAIBLE" and probabilite is not None:
        proche = (SEUIL_PROBABILITE_MINIMAL - probabilite) <= fenetre_probabilite
    elif motif == "COTE_HORS_INTERVALLE" and cote is not None:
        proche = 0 <= (COTE_MIN - cote) <= fenetre_cote or 0 <= (cote - COTE_MAX) <= fenetre_cote

    if not proche:
        return None

    return {
        "marche": diagnostic.get("marche") or detail.get("marche"),
        "market_family": detail.get("market_family"),
        "exposure_group": detail.get("exposure_group"),
        "scenario": scenario_en_echec,
        "probabilite": probabilite,
        "cote": cote,
        "edge": None,
        "edv": edv,
        "edv_min_requis": edv_min_requis,
        "robustesse": detail.get("robustesse"),
        "motif_rejet": motif,
    }


def extraire_marches_proches(
    diagnostics: list[dict[str, Any]],
    fenetre_probabilite: float = FENETRE_PROBABILITE,
    fenetre_edv: float = FENETRE_EDV,
    fenetre_cote: float = FENETRE_COTE,
) -> list[dict[str, Any]]:
    """Applique extraire_marche_proche() à toute la liste, ne garde que les
    marchés effectivement proches (jamais None dans le résultat)."""
    resultats = []
    for diagnostic in diagnostics:
        marche_proche = extraire_marche_proche(
            diagnostic, fenetre_probabilite, fenetre_edv, fenetre_cote
        )
        if marche_proche is not None:
            resultats.append(marche_proche)
    return resultats
