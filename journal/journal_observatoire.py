from __future__ import annotations
import glob, gzip, json, os
from collections import defaultdict
from .journal_memoire import construire_historique, resolve
from .journal_regimes import regime

def _lire_json(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)

def _normaliser_archives_model(records):
    """Convertit les lignes d'archive moteur en fiches match sans perdre les marchés."""
    groupes = {}
    for r in records:
        if not isinstance(r, dict) or not r.get("match_id"):
            continue
        # Déjà au format fiche match (archives de test / fixtures).
        if "domicile" in r and "exterieur" in r:
            yield r
            continue
        mid = str(r["match_id"])
        g = groupes.setdefault(mid, {
            "match_id": mid,
            "date": str(r.get("date_match") or "")[:10],
            "heure": r.get("heure_match"),
            "competition": " ".join(str(r.get("competition") or "").split()),
            "domicile": r.get("equipe_dom"),
            "exterieur": r.get("equipe_ext"),
            "score": None,
            "cotes_observees": {},
            "resultats_marches": {},
        })
        market = r.get("marche")
        if market:
            if r.get("cote") is not None:
                try:
                    g["cotes_observees"][market] = float(r["cote"])
                except (TypeError, ValueError):
                    pass
            if r.get("resultat_statut") == "RESOLVED":
                outcome = r.get("resultat_marche")
                if outcome in {"WIN", "LOSS"}:
                    g["resultats_marches"][market] = outcome == "WIN"
        if r.get("buts_marques") is not None and r.get("buts_encaisses") is not None:
            g["score"] = {
                "buts_dom": r.get("buts_marques"),
                "buts_ext": r.get("buts_encaisses"),
            }
    yield from groupes.values()

def charger_archives(dossier="archive"):
    records = []
    paths = sorted(glob.glob(os.path.join(dossier, "*.json")) + glob.glob(os.path.join(dossier, "*.json.gz")))
    for path in paths:
        try:
            doc = _lire_json(path)
        except (OSError, ValueError, EOFError):
            continue
        if isinstance(doc, dict):
            raw = list(doc.values()) if all(isinstance(v, dict) for v in doc.values()) else [doc]
        elif isinstance(doc, list):
            raw = doc
        else:
            raw = []
        records.extend(_normaliser_archives_model(raw))
    return records

def construire_fiche(match, records, historique=None):
    target = str(match.get("date") or "")
    hist = historique if historique is not None else construire_historique(records, target)

    current_markets = set(
        (match.get("cotes_observees") or match.get("cotes_betpawa") or {}).keys()
    )
    teams = {str(match.get("domicile") or ""), str(match.get("exterieur") or "")} - {""}
    historical_markets = {r.marche for r in hist if r.equipe in teams}
    markets = sorted(current_markets | historical_markets)

    observations = []
    for team, ctx in ((match.get("domicile"), "DOMICILE"), (match.get("exterieur"), "EXTERIEUR")):
        if not team:
            continue
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
        "heure": match.get("heure"),
        "competition": match.get("competition"),
        "domicile": match.get("domicile"),
        "exterieur": match.get("exterieur"),
        "observations": observations,
    }
