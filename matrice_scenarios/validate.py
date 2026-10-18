"""Validation statistique complète de la matrice (lecture seule, aucune règle activée).

    python -m matrice_scenarios.validate --output rapport_validation.json

Trois analyses indépendantes puis un verdict à critères fixés d'avance (`validation.decide_verdict`) :
  1. walk-forward sur l'archive de test (cotes archivées du run), avec permutations imbriquées ;
  2. walk-forward mensuel sur Football-Data (résultats seulement) contre le taux de base ;
  3. règles gelées sur Football-Data AVANT le premier jour de l'archive, évaluées sur l'archive (jamais vue)
     avec correction max-T et portefeuille un-pari-par-match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from . import core, validation
from .football_data import load_football_data


def _day_before(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()


def _test_months(records: list[dict], min_pre: int, min_test: int) -> list[str]:
    months: dict[str, int] = {}
    for r in records:
        months[str(r["date"])[:7]] = months.get(str(r["date"])[:7], 0) + 1
    chosen, seen = [], 0
    for month in sorted(months):
        if seen >= min_pre and months[month] >= min_test:
            chosen.append(month)
        seen += months[month]
    return chosen


def rules_digest(frozen: list[dict]) -> str:
    payload = json.dumps([{"conditions": f["conditions"], "target": f["target"]} for f in frozen], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validation statistique de la matrice de scénarios (lecture seule)")
    parser.add_argument("--archive", default="data/archive_test")
    parser.add_argument("--football-data", default="data/football_data")
    parser.add_argument("--output", default="rapport_validation_matrice.json")
    parser.add_argument("--max-candidates", type=int, default=core.DEFAULT_MAX_CANDIDATES)
    parser.add_argument("--repetitions-archive", type=int, default=1000)
    parser.add_argument("--repetitions-football-data", type=int, default=200)
    parser.add_argument("--repetitions-transfer", type=int, default=2000)
    parser.add_argument("--skip-football-data-walk-forward", action="store_true")
    parser.add_argument("--freeze-forward", metavar="FICHIER", help="écrit les règles gelées (Football-Data jusqu'à sa dernière date) pour un test futur")
    parser.add_argument("--evaluate-frozen", metavar="FICHIER", help="évalue un fichier de règles gelées sur l'archive (voir --from-date)")
    parser.add_argument("--from-date", help="ne garde que les matchs de l'archive à cette date ou après (AAAA-MM-JJ)")
    args = parser.parse_args(argv)

    def log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    archive_records, loading = core.load_dataset(args.archive)
    if args.from_date:
        archive_records = [r for r in archive_records if str(r["date"])[:10] >= args.from_date]
    first_day = min(str(r["date"])[:10] for r in archive_records)
    football, football_diag = load_football_data(args.football_data)

    if args.evaluate_frozen:
        stored = json.loads(Path(args.evaluate_frozen).read_text(encoding="utf-8"))
        if rules_digest(stored["frozen"]) != stored["sha256"]:
            raise SystemExit("Le fichier de règles gelées a été modifié : empreinte SHA-256 différente.")
        if first_day <= stored["cutoff"]:
            raise SystemExit(f"L'échantillon commence le {first_day}, avant ou à la date de gel {stored['cutoff']} : utilisez --from-date.")
        transfer = validation.evaluate_frozen(stored["frozen"], archive_records, repetitions=args.repetitions_transfer)
        report = {"mode": "EVALUATION_REGLES_GELEES", "frozen_file": args.evaluate_frozen, "frozen_sha256": stored["sha256"],
                  "cutoff": stored["cutoff"], "transfer": transfer, "decision": validation.decide_verdict(transfer)}
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"verdict: {report['decision']['verdict']}")
        return 0

    if args.freeze_forward:
        cutoff = football_diag["last_date"]
        frozen = validation.freeze_rules(football, cutoff=cutoff, max_candidates=args.max_candidates)
        payload = {"cutoff": cutoff, "created_for": "test futur ; aucune donnée postérieure au gel ne doit servir à modifier ces règles",
                   "sha256": rules_digest(frozen["frozen"]), "frozen": frozen["frozen"],
                   "provenance": {k: v for k, v in frozen.items() if k != "frozen"}}
        Path(args.freeze_forward).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"{len(frozen['frozen'])} scénarios gelés au {cutoff}; empreinte {payload['sha256'][:16]}")
        return 0

    log("1/3 walk-forward archive avec permutations imbriquées")
    archive_wf = validation.archive_walk_forward(archive_records, max_candidates=args.max_candidates, repetitions=args.repetitions_archive)

    football_wf = None
    if not args.skip_football_data_walk_forward:
        months = _test_months(football, min_pre=3000, min_test=400)
        log(f"2/3 walk-forward Football-Data sur {len(months)} mois : {months[0]} à {months[-1]}")
        football_wf = validation.football_data_walk_forward(football, test_months=months, max_candidates=args.max_candidates,
                                                            repetitions=args.repetitions_football_data, progress=log)

    cutoff = _day_before(first_day)
    log(f"3/3 règles gelées sur Football-Data jusqu'au {cutoff}, évaluées sur l'archive à partir du {first_day}")
    frozen = validation.freeze_rules(football, cutoff=cutoff, max_candidates=args.max_candidates)
    transfer = validation.evaluate_frozen(frozen["frozen"], archive_records, repetitions=args.repetitions_transfer)
    report = {
        "schema_version": 1, "mode": "VALIDATION_STATISTIQUE_READ_ONLY", "promotion_allowed": False,
        "data": {"archive_loading": loading, "football_data": {k: v for k, v in football_diag.items() if k != "matches_by_month"},
                 "football_data_matches_by_month": football_diag["matches_by_month"],
                 "archive_first_day": first_day, "freeze_cutoff": cutoff},
        "archive_walk_forward": archive_wf, "football_data_walk_forward": football_wf,
        "frozen_rules": {k: v for k, v in frozen.items() if k != "frozen"} | {"scenarios_frozen": len(frozen["frozen"]),
                                                                              "sha256": rules_digest(frozen["frozen"])},
        "transfer_to_archive": transfer, "decision": validation.decide_verdict(transfer),
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"verdict: {report['decision']['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
