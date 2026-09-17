"""Compatibilité de justification + traduction de la raison réelle de sélection.

La justification marketing est désormais déléguée exclusivement à
bibliotheque_justification.py. Ce module conserve les API historiques
utilisées par le moteur et la raison réelle P1/P2/P3.
"""
from __future__ import annotations

import inspect

from bibliotheque_justification import (
    construit_justification_bibliotheque,
    construit_donnees,
    confirmation_historique_bibliotheque,
)


def _valeurs_marche_appelant():
    """Récupère les deux valeurs déjà calculées par le moteur appelant.

    Compatibilité temporaire : le moteur historique appelle encore
    construit_justification() sans exposer explicitement les deux paramètres
    du nouveau contrat.
    """
    frame = inspect.currentframe()
    try:
        caller = frame.f_back if frame else None
        local = caller.f_locals if caller else {}
        cote = local.get("cote")
        if not isinstance(cote, (int, float)):
            cote = local.get("cote_reelle")

        probabilite = local.get("p_repr")
        if not isinstance(probabilite, (int, float)):
            probabilite = local.get("p")

        odds_scraped = cote if isinstance(cote, (int, float)) else None
        market_prob_pct = (
            probabilite * 100.0
            if isinstance(probabilite, (int, float))
            else None
        )
        return odds_scraped, market_prob_pct
    finally:
        del frame


def construit_justification(
    marche, matchs_a, matchs_b, h2h=None,
    nom_domicile="", nom_exterieur="",
    *, odds_scraped=None, market_prob_pct=None,
):
    """API historique : la nouvelle bibliothèque est prioritaire."""
    if odds_scraped is None or market_prob_pct is None:
        auto_odds, auto_prob = _valeurs_marche_appelant()
        if odds_scraped is None:
            odds_scraped = auto_odds
        if market_prob_pct is None:
            market_prob_pct = auto_prob

    return construit_justification_bibliotheque(
        marche,
        matchs_a,
        matchs_b,
        h2h=h2h,
        nom_domicile=nom_domicile,
        nom_exterieur=nom_exterieur,
        odds_scraped=odds_scraped,
        market_prob_pct=market_prob_pct,
    )


def confirmation_historique(marche, matchs_a, matchs_b, h2h=None):
    """Compatibilité moteur : lit exclusivement la nouvelle bibliothèque."""
    return confirmation_historique_bibliotheque(marche, matchs_a, matchs_b, h2h=h2h)


# ============================================================================
# RAISON RÉELLE DE LA SÉLECTION
# Cette partie ne choisit rien : elle traduit uniquement le diagnostic déjà
# produit après P1/P2/P3. Elle n'alimente plus le texte marketing affiché.
# ============================================================================
LIBELLES_NIVEAU = {
    "PREMIUM": "le niveau d'éligibilité le plus élevé (PREMIUM)",
    "TRES_FORT": "un niveau d'éligibilité très fort",
    "FORT": "un niveau d'éligibilité fort",
    "ELIGIBLE": "un niveau d'éligibilité suffisant",
    "ELIGIBLE_PLUS": "un niveau d'éligibilité de base",
}

LIBELLES_H2H = {
    "TRES_FIABLE": "très fiables",
    "FIABLE": "fiables",
    "INDICATIF": "indicatives",
    "INSUFFISANT": "insuffisantes",
}


def construit_raison_selection(candidat, diagnostic):
    """Compatibilité historique, conservée hors de la justification affichée."""
    if candidat is None:
        return None

    niveau = candidat.get("niveau")
    lib_niveau = LIBELLES_NIVEAU.get(niveau)
    base = "Le marché a été retenu par le moteur."
    if lib_niveau:
        base = f"Le marché présente {lib_niveau}."

    critere = (diagnostic or {}).get("critere")
    if critere == "aucun_concurrent":
        return base
    if critere == "egalite_totale":
        return base + " Les marchés restants étaient à égalité sur les critères de sélection."
    if critere == "niveau":
        return base + " Le niveau d'éligibilité a servi au départage."
    if critere == "robustesse":
        return base + " La robustesse a servi au départage."
    if critere == "signal":
        return base + " Le signal de forme récente a servi au départage."
    if critere == "h2h":
        lib_h2h = LIBELLES_H2H.get(candidat.get("h2h_palier"))
        return base + (f" La fiabilité H2H ({lib_h2h}) a servi au départage." if lib_h2h else " La fiabilité H2H a servi au départage.")
    if critere == "edv":
        edv = candidat.get("edv")
        return base + (f" Le gain potentiel ({edv * 100:.1f} %) a servi au départage." if isinstance(edv, (int, float)) else " Le gain potentiel a servi au départage.")
    if critere == "probabilite":
        p = candidat.get("probabilite")
        return base + (f" La probabilité ({p * 100:.1f} %) a servi au départage." if isinstance(p, (int, float)) else " La probabilité a servi au départage.")
    if critere == "cote":
        cote = candidat.get("cote")
        return base + (f" La cote ({cote:.2f}) a servi au départage." if isinstance(cote, (int, float)) else " La cote a servi au départage.")
    return base


def enrichit_justification_selection(candidat, diagnostic):
    """Conserve exclusivement la justification produite par la bibliothèque.

    Le diagnostic P1/P2/P3 reste disponible dans le candidat pour la logique
    interne, mais son ancien texte n'est plus injecté dans ``justification``.
    """
    if candidat is None:
        return None

    justification_actuelle = candidat.get("justification") or {}
    bibliotheque = dict(justification_actuelle.get("bibliotheque") or {})
    preuves_marketing = list(justification_actuelle.get("preuves") or [])
    resume_marketing = justification_actuelle.get("resume")
    donnees_suffisantes = bool(justification_actuelle.get("donnees_suffisantes"))

    nouvelle_justification = {
        "resume": resume_marketing,
        "preuves": preuves_marketing[:3],
        "donnees_suffisantes": donnees_suffisantes,
        "bibliotheque": bibliotheque,
    }

    candidat["justification"] = nouvelle_justification
    return nouvelle_justification
