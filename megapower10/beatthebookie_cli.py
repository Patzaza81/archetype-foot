"""Run MEGAPOWER 10+ on the 479k-match Beat The Bookie archive.

Usage: python -m megapower10.beatthebookie_cli --input /path/closing_odds.csv.gz
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .beatthebookie import load_beat_the_bookie
from .core import evaluate
from .model import MatchResult, tune_parameters
from .walk_forward import enrich_prices, chronological_edge_study, forecast_quality_report


def main() -> int:
    p = argparse.ArgumentParser(description="MEGAPOWER 10+ — Beat The Bookie historical archive")
    p.add_argument("--input", required=True, help="closing_odds.csv.gz")
    p.add_argument("--min-odds", type=float, default=10.0)
    p.add_argument("--max-odds", type=float, default=1000.0)
    p.add_argument("--min-support", type=int, default=30)
    p.add_argument("--train-end", default=None)
    p.add_argument("--validation-end", default=None)
    p.add_argument("--output", default="-")
    args = p.parse_args()

    matches, prices, source = load_beat_the_bookie(args.input)
    model_matches = [MatchResult(m.event_id, m.date, m.competition, m.home, m.away, m.home_goals, m.away_goals) for m in matches]
    dates = sorted({m.date for m in model_matches})
    if len(dates) < 10:
        raise SystemExit("Pas assez de dates distinctes pour un découpage chronologique exploitable.")
    train_end = args.train_end or dates[int(len(dates) * .60)]
    validation_end = args.validation_end or dates[int(len(dates) * .80)]

    tuning = tune_parameters(model_matches, train_end=train_end)
    params = tuning["selected"]
    enriched, join_report = enrich_prices(model_matches, prices,
                                          window=params["window"],
                                          prior_matches=params["prior_matches"])
    edge_report = chronological_edge_study([r for r in enriched if r["bookmaker"] == "BTB_best_available"], train_end=train_end,
                                           validation_end=validation_end,
                                           min_support=args.min_support)
    report = {
        "engine": "MEGAPOWER 10+",
        "source": source,
        "model_tuning": tuning,
        "forecast_join": join_report,
        "reference_average_price_10plus_non_executable": evaluate([q for q in prices if q.bookmaker == "BTB_average"], min_odds=args.min_odds, max_odds=args.max_odds),
        "best_observed_price_10plus_hypothetical_execution": evaluate([q for q in prices if q.bookmaker == "BTB_best_available"], min_odds=args.min_odds, max_odds=args.max_odds),
        "forecast_quality": forecast_quality_report(enriched, train_end=train_end, validation_end=validation_end),
        "edge_study": edge_report,
        "average_price_note": "Le prix moyen est un repère statistique non exécutable ; aucun ROI moyen n’est utilisé pour sélectionner une stratégie.",
        "interpretation": "Les probabilités de référence sont calculées à partir des cotes moyennes du marché ; le ROI du portefeuille best_available utilise la meilleure cote observée par issue et indique le bookmaker déclaré pour cette issue. Il ne s'agit pas d'un arbitrage simultané. Les prix sont des clôtures historiques non horodatées à la seconde.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output == "-":
        print(rendered)
    else:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
