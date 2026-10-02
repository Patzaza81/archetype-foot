from __future__ import annotations

def construire_radar(fiches):
    items = []
    for fiche in fiches:
        ident = fiche.get("identification", {})
        for market, obs in fiche.get("observations_marches", fiche.get("observations", {})).items():
            if not isinstance(obs, dict):
                continue
            ant = fiche.get("anticipations", {}).get(market, {})
            items.append({
                "match_id": ident.get("match_id"),
                "date": ident.get("date"),
                "championnat": ident.get("championnat"),
                "domicile": ident.get("equipe_domicile"),
                "exterieur": ident.get("equipe_exterieure"),
                "marche": market,
                "regime": obs.get("regime") or obs.get("regime_detecte"),
                "niveau": obs.get("niveau") or obs.get("niveau_observation"),
                "statut": ant.get("statut", "EN_ATTENTE"),
                "prix": ant.get("prix", "EN_ATTENTE_DU_PRIX"),
            })
    priority = {
        "COMPORTEMENT_EN_RENFORCEMENT": 0,
        "A_SURVEILLER": 1,
        "COMPORTEMENT_EN_AFFAIBLISSEMENT": 2,
        "INSUFFISANT": 3,
    }
    items.sort(key=lambda x: priority.get(x["statut"], 9))
    return {
        "matchs": len({x["match_id"] for x in items}),
        "observations": len(items),
        "items": items,
    }
