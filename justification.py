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

    Le moteur historique appelle construit_justification() sans encore
    exposer les deux paramètres du nouveau contrat. On conserve donc son
    API publique tout en branchant exactement les variables locales déjà
    calculées au même point : la cote réelle du marché et sa probabilité
    représentative. Aucun calcul parallèle ni alias métier n'est introduit.
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
# produit après P1/P2/P3. Elle reste volontairement indépendante de la
# bibliothèque marketing.
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
    if candidat is None:
        return None

    niveau = candidat.get("niveau")
    lib_niveau = LIBELLES_NIVEAU.get(niveau)
    if lib_niveau:
        base = f"Ce marché a été validé dans les 4 scénarios du modèle, avec {lib_niveau}."
    else:
        base = "Ce marché a été validé dans les 4 scénarios du modèle."

    critere = (diagnostic or {}).get("critere")
    if critere == "aucun_concurrent":
        return base + " Aucun autre marché ne concourait dans son groupe -- il a été retenu par défaut, sans concurrent à départager."
    if critere == "egalite_totale":
        return base + " Il était à égalité parfaite avec le meilleur marché concurrent sur tous les critères du modèle."
    if critere == "niveau":
        return base + " C'est ce niveau d'éligibilité, supérieur à celui du meilleur marché concurrent, qui l'a distingué."
    if critere == "robustesse":
        return base + " Sa stabilité sur les 4 scénarios était supérieure à celle du meilleur marché concurrent, ce qui l'a distingué."
    if critere == "signal":
        direction = candidat.get("signal_direction")
        if direction == "favorable":
            return base + " Le signal de forme récente, favorable, l'a distingué du meilleur marché concurrent."
        if direction == "defavorable":
            return base + " La faiblesse du signal de forme récente sur le marché concurrent l'a distingué."
        return base + " Le signal de forme récente l'a distingué du meilleur marché concurrent."
    if critere == "h2h":
        lib_h2h = LIBELLES_H2H.get(candidat.get("h2h_palier"))
        if lib_h2h:
            return base + f" La fiabilité des confrontations directes ({lib_h2h}) l'a distingué du meilleur marché concurrent."
        return base + " La fiabilité des confrontations directes l'a distingué du meilleur marché concurrent."
    if critere == "edv":
        edv = candidat.get("edv")
        if isinstance(edv, (int, float)):
            return base + f" À critères équivalents par ailleurs, son gain potentiel ({edv * 100:.1f} %) l'a départagé du meilleur marché concurrent."
        return base + " À critères équivalents par ailleurs, son gain potentiel l'a départagé du meilleur marché concurrent."
    if critere == "probabilite":
        p = candidat.get("probabilite")
        if isinstance(p, (int, float)):
            return base + f" C'est le marché le plus probable ({p * 100:.1f} %) parmi ceux restant après le premier choix."
        return base + " C'est le marché le plus probable parmi ceux restant après le premier choix."
    if critere == "cote":
        cote = candidat.get("cote")
        if isinstance(cote, (int, float)):
            return base + f" C'est la cote la plus élevée ({cote:.2f}) parmi les marchés restants, en complément des deux premiers choix."
        return base + " C'est la cote la plus élevée parmi les marchés restants, en complément des deux premiers choix."
    return base


def enrichit_justification_selection(candidat, diagnostic):
    """Conserve la bibliothèque marketing comme couche prioritaire.

    La raison réelle P1/P2/P3 reste disponible séparément et ne remplace
    plus le résumé ni les preuves de la bibliothèque.
    """
    if candidat is None:
        return None

    justification_actuelle = candidat.get("justification") or {}
    bibliotheque = dict(justification_actuelle.get("bibliotheque") or {})
    preuves_marketing = list(justification_actuelle.get("preuves") or [])
    resume_marketing = justification_actuelle.get("resume")
    donnees_suffisantes = bool(justification_actuelle.get("donnees_suffisantes"))

    raison = construit_raison_selection(candidat, diagnostic)
    selection_reason = None
    if raison:
        selection_reason = {
            "titre": "Raison de sélection",
            "texte": raison,
            "type": "selection_reason",
        }

    nouvelle_justification = {
        "resume": resume_marketing,
        "preuves": preuves_marketing[:3],
        "donnees_suffisantes": donnees_suffisantes,
        "bibliotheque": bibliotheque,
    }
    if selection_reason:
        nouvelle_justification["raison_selection"] = selection_reason

    candidat["justification"] = nouvelle_justification
    return nouvelle_justification
