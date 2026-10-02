from __future__ import annotations

def construire_radar(fiches):
    items = []
    for fiche in fiches:
        ident = fiche.get("identification", {})
        obs_list = fiche.get("observations", [])
        for obs in obs_list:
            if not isinstance(obs, dict):
                continue
            key = f"{obs.get('equipe_reference')}|{obs.get('contexte')}|{obs.get('marche')}"
            ant = fiche.get("anticipations", {}).get(key, {})
            items.append({
                "match_id": ident.get("match_id"),
                "date": ident.get("date"),
                "championnat": ident.get("competition"),
                "domicile": ident.get("domicile"),
                "exterieur": ident.get("exterieur"),
                "equipe_reference": obs.get("equipe_reference"),
                "contexte": obs.get("contexte"),
                "marche": obs.get("marche"),
                "regime": obs.get("regime"),
                "niveau": obs.get("niveau"),
                "statut": ant.get("statut", "EN_ATTENTE"),
                "prix": ant.get("prix", "EN_ATTENTE_DU_PRIX"),
                "cote": ant.get("cote"),
            })
    priority = {
        "COMPORTEMENT_EN_RENFORCEMENT": 0,
        "A_SURVEILLER": 1,
        "COMPORTEMENT_EN_AFFAIBLISSEMENT": 2,
        "INSUFFISANT": 3,
    }
    items.sort(key=lambda x: (priority.get(x["statut"], 9), str(x["date"]), str(x["match_id"])))
    return {
        "matchs": len({x["match_id"] for x in items}),
        "observations": len(items),
        "items": items,
    }
