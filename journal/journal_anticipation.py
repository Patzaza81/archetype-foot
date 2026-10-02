from __future__ import annotations

def _status(regime, niveau, n1=None):
    if regime in {"RUPTURE", "AFFAIBLISSEMENT"}:
        return "COMPORTEMENT_EN_AFFAIBLISSEMENT"
    if regime in {"RENFORCEMENT", "REPRISE"}:
        return "COMPORTEMENT_EN_RENFORCEMENT"
    if regime in {"PERSISTANT", "RECURRENT"} and niveau in {"EXPLOITABLE", "SOLIDE"}:
        return "A_SURVEILLER"
    if regime == "EMERGENCE":
        return "A_SURVEILLER"
    return "INSUFFISANT"

def anticiper(observation, n1=None, cote=None):
    regime = observation.get("regime", "INSUFFISANT")
    niveau = observation.get("niveau", "INSUFFISANT")
    status = _status(regime, niveau, n1)
    prix = "EN_ATTENTE_DU_PRIX"
    if cote is not None:
        prix = "PRIX_OBSERVE_COMPATIBLE" if cote.get("compatible") else "PRIX_OBSERVE_NON_COMPATIBLE"
    return {
        "statut": status,
        "prix": prix,
        "sans_cote": True,
        "regime": regime,
        "niveau": niveau,
        "base": {
            "echantillon": observation.get("echantillon", 0),
            "frequence": observation.get("frequence"),
            "frequence_recente": observation.get("frequence_recente"),
            "tendance": observation.get("tendance"),
            "n1_disponible": bool(n1 and n1.get("disponible")),
        },
        "formulation": (
            "comportement historique susceptible de se poursuivre"
            if status in {"A_SURVEILLER", "COMPORTEMENT_EN_RENFORCEMENT"}
            else "signal comportemental insuffisant ou en affaiblissement"
        ),
    }

def construire_anticipations(observations, n1_by_market=None, cote_by_market=None):
    n1_by_market = n1_by_market or {}
    cote_by_market = cote_by_market or {}
    return {
        market: anticiper(obs, n1_by_market.get(market), cote_by_market.get(market))
        for market, obs in observations.items()
    }
