"""Compatibilité de justification + traduction de la raison réelle de sélection.

La justification marketing est désormais déléguée exclusivement à
bibliotheque_justification.py. Ce module conserve les API historiques
utilisées par le moteur et la raison réelle P1/P2/P3.
"""
from bibliotheque_justification import (
    construit_justification_bibliotheque,
    construit_donnees,
    confirmation_historique_bibliotheque,
)


def construit_justification(
    marche, matchs_a, matchs_b, h2h=None,
    nom_domicile="", nom_exterieur="",
    *, odds_scraped=None, market_prob_pct=None,
):
    """API historique : la nouvelle bibliothèque est prioritaire."""
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
    """Remplace la justification marketing par la bibliothèque stricte puis
    ajoute la raison réelle de sélection sans influencer la sélection."""
    if candidat is None:
        return None

    justification_actuelle = candidat.get("justification") or {}
    bibliotheque = justification_actuelle.get("bibliotheque") or {}
    odds = candidat.get("cote")
    prob = candidat.get("probabilite")

    # Recalcule la couche marketing avec les données exactes du candidat.
    # Les historiques ne sont pas forcément conservés dans le candidat ; la
    # justification initiale reste donc la source de ses preuves historiques.
    if odds is not None and prob is not None:
        justification_actuelle["bibliotheque"] = dict(bibliotheque)
        justification_actuelle["bibliotheque"]["odds_scraped"] = odds
        justification_actuelle["bibliotheque"]["market_prob_pct"] = prob * 100.0
        justification_actuelle["bibliotheque"]["ev_percentage"] = round((prob * odds - 1.0) * 100.0, 1)
        # Le calcul est strictement celui de la bibliothèque ; aucune autre
        # définition de l'EDV/edge n'est substituée ici.
        ev = justification_actuelle["bibliotheque"]["ev_percentage"]
        preuve_ev = {
            "texte": f"Avantage Statistique : +{ev:.1f}%",
            "type": "ev_percentage",
            "valeur": ev,
            "explication": f"La cote actuelle est supérieure de {ev:.1f}% à ce que nos calculs jugent équitable.",
        }
        preuves = [p for p in (justification_actuelle.get("preuves") or []) if p.get("type") != "ev_percentage"]
        preuves.insert(0, preuve_ev)
        justification_actuelle["preuves"] = preuves[:3]
        justification_actuelle["resume"] = preuve_ev["texte"]

    raison = construit_raison_selection(candidat, diagnostic)
    preuves = list(justification_actuelle.get("preuves") or [])
    if raison:
        preuves.insert(0, {"titre": "Raison de sélection", "texte": raison, "type": "selection_reason"})

    nouvelle_justification = {
        "resume": raison or justification_actuelle.get("resume"),
        "preuves": preuves[:3],
        "donnees_suffisantes": bool(justification_actuelle.get("donnees_suffisantes")),
        "bibliotheque": justification_actuelle.get("bibliotheque") or {},
    }
    candidat["justification"] = nouvelle_justification
    return nouvelle_justification
