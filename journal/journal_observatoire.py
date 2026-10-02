from __future__ import annotations
import glob, gzip, json, os
from .journal_memoire import construire_historique, resolve
from .journal_regimes import regime

def charger_archives(dossier="data/archive_test"):
    records = []
    for path in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            doc = json.load(f)
        if isinstance(doc, dict): records.extend(doc.values())
    return records

def construire_fiche(match, records, historique=None):
    target = str(match.get("date") or "")
    hist = historique if historique is not None else construire_historique(records, target)

    # Une absence de cote ne supprime jamais l'observation : on construit
    # l'univers des marchés à partir des marchés historiques des deux équipes,
    # puis on enrichit avec les marchés éventuellement cotés aujourd'hui.
    current_markets = set(
        (match.get("cotes_observees") or match.get("cotes_betpawa") or {}).keys()
    )
    teams = {str(match.get("domicile") or ""), str(match.get("exterieur") or "")} - {""}
    historical_markets = {
        r.marche for r in hist
        if r.equipe in teams
    }
    markets = sorted(current_markets | historical_markets)

    observations = []
    for team, ctx in ((match.get("domicile"), "DOMICILE"), (match.get("exterieur"), "EXTERIEUR")):
        if not team: continue
        for market in markets:
            level, rows = resolve(hist, str(team), market, match.get("competition"), ctx)
            observations.append({
                "equipe_reference": team,
                "contexte": ctx,
                "marche": market,
                "niveau_repli": level,
                **regime(rows),
            })
    return {
        "match_id": match.get("match_id"),
        "date": target,
        "competition": match.get("competition"),
        "domicile": match.get("domicile"),
        "exterieur": match.get("exterieur"),
        "observations": observations,
    }
