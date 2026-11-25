"""Run the Football-Data historical odds study without inventing capture timestamps.

Usage: python -m megapower10.football_data --root data/football_data --output data/megapower10/football_data_report.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import evaluate, discovery_report
from .football_data import load_football_data


def main() -> int:
    p = argparse.ArgumentParser(description="MEGAPOWER 10+ — historical Football-Data study")
    p.add_argument("--root", default="data/football_data")
    p.add_argument("--min-odds", type=float, default=10.0)
    p.add_argument("--max-odds", type=float, default=1000.0)
    p.add_argument("--min-support", type=int, default=30)
    p.add_argument("--output", default="-")
    args = p.parse_args()
    rows, source = load_football_data(args.root)
    report = {
        "engine": "MEGAPOWER 10+",
        "source": source,
        "odds_ge_10": {
            "opening": evaluate([q for q in rows if q.price_stage == "opening"], min_odds=args.min_odds, max_odds=args.max_odds),
            "closing": evaluate([q for q in rows if q.price_stage == "closing"], min_odds=args.min_odds, max_odds=args.max_odds),
        },
        "discovery_by_competition_market_band_stage": discovery_report(rows, min_support=args.min_support),
        "interpretation": "Étude historique descriptive. Les prix d'ouverture/clôture ne sont pas des prix horodatés à un instant de décision ; aucun ROI prospectif ni CLV exécutable ne peut en être déduit.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(rendered)
    else:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
