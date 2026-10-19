"""CLI en lecture seule pour explorer un jeu de matchs normalisé."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import DEFAULT_MAX_CANDIDATES, load_dataset, run_experiment, walk_forward


def main() -> int:
    parser = argparse.ArgumentParser(description="Découverte expérimentale de scénarios ARCHETYPE Foot")
    parser.add_argument("dataset", help="JSON array, objet {matches:[...]}, JSONL ou dossier data/archive_test")
    parser.add_argument("--output", default="rapport_matrice_scenarios.json")
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    parser.add_argument("--walk-forward", action="store_true",
                        help="ajoute une validation chronologique glissante (3 origines croissantes)")
    args = parser.parse_args()
    if args.max_candidates < 1 or args.max_candidates > 100000:
        parser.error("--max-candidates doit être compris entre 1 et 100000")
    records, loading = load_dataset(args.dataset)
    report = run_experiment(records, max_candidates=args.max_candidates)
    report["loading"] = loading
    if args.walk_forward:
        report["walk_forward"] = walk_forward(records, max_candidates=args.max_candidates)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Matches uniques: {report['dataset']['matches']}; candidats testés: {report['scenarios_tested']}")
    print(f"Train/validation/test: {report['dataset']['train_n']}/{report['dataset']['validation_n']}/{report['dataset']['test_n']}")
    print(f"Rapport: {args.output}; aucune règle n'est activée en production.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
