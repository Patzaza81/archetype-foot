from __future__ import annotations
import datetime, json, os
from .journal_observatoire import charger_archives, construire_fiche
from .journal_memoire import construire_historique
from .journal_cotes import statistiques_prix, tranche_cote
from .journal_n1 import charger_n1, stats_equipe_marche
from .journal_sequences import analyser_sequences
from .journal_anticipation import anticiper
from .journal_persistance import taux_persistance
from .journal_validation import resume_validation

def _price_compatibility(rows, cote):
    if cote is None or not rows:
        return None
    band = tranche_cote(cote)
    same = [r for r in rows if r.cote is not None and tranche_cote(r.cote) == band]
    if len(same) < 3:
        return None
    freq = sum(r.resultat for r in same) / len(same)
    overall = sum(r.resultat for r in rows) / len(rows)
    return freq >= overall

def _group(hist):
    grouped = {}
    for r in hist:
        grouped.setdefault((r.equipe, r.marche), []).append(r)
    return grouped

def historique_avant(records, target_date):
    """Construit exclusivement l'information disponible avant target_date."""
    return construire_historique(records, target_date=str(target_date))

def run(archive_dir="archive", out_dir="data", n1_dir="data/football_data/snapshots"):
    records = charger_archives(archive_dir)
    scored = [r for r in records if isinstance(r.get("score"), dict)]
    upcoming = [r for r in records if r.get("score") is None]
    n1_rows = charger_n1(n1_dir)

    # Mémoire globale : uniquement pour les sorties historiques déjà produites.
    hist = construire_historique(scored)
    grouped = _group(hist)

    fiches = []
    for match in sorted(upcoming, key=lambda x: (str(x.get("date")), str(x.get("match_id")))):
        target_date = str(match.get("date") or "")
        hist_before = historique_avant(scored, target_date)
        grouped_before = _group(hist_before)
        fiche = construire_fiche(match, records, historique=hist_before)
        anticipations = {}
        for obs in fiche["observations"]:
            key = f"{obs.get('equipe_reference')}|{obs.get('contexte')}|{obs.get('marche')}"
            rows = grouped_before.get((obs["equipe_reference"], obs["marche"]), [])
            obs["sequence"] = analyser_sequences(rows)
            obs["n1"] = stats_equipe_marche(
                n1_rows,
                obs["equipe_reference"],
                obs["marche"],
                obs["contexte"],
                target_date=target_date,
            )
            market_odds = (match.get("cotes_observees") or match.get("cotes_betpawa") or {})
            raw_cote = market_odds.get(obs["marche"])
            try:
                cote = float(raw_cote) if raw_cote is not None else None
            except (TypeError, ValueError):
                cote = None
            compatible = _price_compatibility(rows, cote)
            ant = anticiper(
                obs,
                obs["n1"],
                {"compatible": compatible} if compatible is not None else None,
            )
            ant["cote"] = cote
            ant["tranche_cote"] = tranche_cote(cote) if cote is not None else None
            ant["prix"] = (
                "PRIX_OBSERVE_COMPATIBLE" if compatible is True
                else "PRIX_OBSERVE_NON_COMPATIBLE" if compatible is False
                else "PRIX_OBSERVE_SANS_REFERENCE" if cote is not None
                else "EN_ATTENTE_DU_PRIX"
            )
            ant["persistance"] = {
                "historique": taux_persistance(rows) if rows else {}
            }
            obs["statut_n1"] = "REFERENCE_DISPONIBLE" if obs["n1"]["disponible"] else "INDISPONIBLE"
            anticipations[key] = ant
        fiche["anticipations"] = anticipations
        fiches.append(fiche)

    memory = {}
    for (team, market), rows in sorted(grouped.items()):
        memory[f"{team}|{market}"] = {
            "equipe": team,
            "marche": market,
            "echantillon": len(rows),
            "frequence": round(sum(r.resultat for r in rows) / len(rows), 4),
            "sequence": analyser_sequences(rows),
            "prix": statistiques_prix(rows),
            "persistance": taux_persistance(rows),
        }

    validations = {}
    for key, rows in grouped.items():
        if len(rows) >= 5:
            validations[f"{key[0]}|{key[1]}"] = resume_validation(rows, min_history=5)

    # Les validations sont des relectures walk-forward : aucune observation
    # future n'entre dans le signal à la date simulée.
    radar_items = []
    for fiche in fiches:
        ident = fiche
        for obs in fiche["observations"]:
            key = f"{obs.get('equipe_reference')}|{obs.get('contexte')}|{obs.get('marche')}"
            ant = fiche.get("anticipations", {}).get(key, {})
            radar_items.append({
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
                "frequence": obs.get("frequence"),
                "frequence_recente": obs.get("frequence_recente"),
                "sequence": obs.get("sequence"),
                "n1": obs.get("n1"),
                "statut": ant.get("statut", "EN_ATTENTE"),
                "formulation": ant.get("formulation"),
                "prix": ant.get("prix", "EN_ATTENTE_DU_PRIX"),
                "cote": ant.get("cote"),
                "tranche_cote": ant.get("tranche_cote"),
                "persistance": ant.get("persistance", {}),
            })
    radar_items.sort(key=lambda x: (str(x["date"]), str(x["match_id"]), str(x["marche"])))
    radar = {
        "matchs": len({x["match_id"] for x in radar_items}),
        "observations": len(radar_items),
        "items": radar_items,
    }

    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    intelligence = {
        "schema_version": 1,
        "genere_le": generated,
        "source": archive_dir,
        "anti_fuite": "strictement_avant_date_du_match",
        "n1_disponible": bool(n1_rows),
        "n1_source": "data/football_data/snapshots/*/raw/*.csv" if n1_rows else None,
        "resume": {
            "archives": len(records),
            "scores": len(scored),
            "matchs_a_venir": len(upcoming),
            "fiches": len(fiches),
            "observations_n1": sum(1 for f in fiches for o in f["observations"] if o["n1"]["disponible"]),
            "anticipations": sum(len(f["anticipations"]) for f in fiches),
            "radar_observations": radar["observations"],
            "groupes_valides": len(validations),
        },
        "fiches": fiches,
        "radar": radar,
    }
    memory_doc = {
        "schema_version": 1,
        "genere_le": generated,
        "source": "data/archive_test",
        "observations": len(hist),
        "team_market": memory,
    }
    validation_doc = {
        "schema_version": 1,
        "genere_le": generated,
        "methode": "walk_forward",
        "anti_fuite": True,
        "groupes": validations,
    }
    os.makedirs(out_dir, exist_ok=True)
    for name, doc in (
        ("journal_intelligence.json", intelligence),
        ("journal_memoire.json", memory_doc),
        ("journal_validation.json", validation_doc),
    ):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    return intelligence["resume"]

if __name__ == "__main__":
    print(run())
