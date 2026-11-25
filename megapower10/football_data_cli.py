"""Run the Football-Data walk-forward price study.

Usage: python -m megapower10.football_data_cli --root data/football_data
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import evaluate
from .football_data import load_football_data, load_football_data_matches
from .model import MatchResult, tune_parameters
from .walk_forward import enrich_prices, chronological_edge_study, forecast_quality_report


def main() -> int:
    p = argparse.ArgumentParser(description="MEGAPOWER 10+ — walk-forward historical odds study")
    p.add_argument("--root", default="data/football_data")
    p.add_argument("--min-odds", type=float, default=10.0)
    p.add_argument("--max-odds", type=float, default=1000.0)
    p.add_argument("--min-support", type=int, default=30)
    p.add_argument("--train-end", default=None, help="date ISO exclusive; default 60%% of distinct dates")
    p.add_argument("--validation-end", default=None, help="date ISO exclusive; default 80%% of distinct dates")
    p.add_argument("--output", default="-")
    args = p.parse_args()

    prices, price_source = load_football_data(args.root)
    matches, match_source = load_football_data_matches(args.root)
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
    edge_report = chronological_edge_study(enriched, train_end=train_end,
                                           validation_end=validation_end,
                                           min_support=args.min_support)
    report = {
        "engine": "MEGAPOWER 10+",
        "model_tuning": tuning,
        "match_source": match_source,
        "price_source": price_source,
        "forecast_join": join_report,
        "raw_10plus_opening": evaluate([q for q in prices if q.price_stage == "opening"], min_odds=args.min_odds, max_odds=args.max_odds),
        "raw_10plus_closing": evaluate([q for q in prices if q.price_stage == "closing"], min_odds=args.min_odds, max_odds=args.max_odds),
        "forecast_quality": forecast_quality_report(enriched),
        "edge_study": edge_report,
        "interpretation": "Le modèle et ses paramètres sont appris en marche avant sur le seul bloc train. Chaque match est prédit avec les seuls résultats strictement antérieurs du même championnat. Les seuils d'écart sont choisis sur validation puis évalués sur un test chronologique séparé. Les prix Football-Data ouverture/clôture n'ont pas d'horodatage de capture : cette étude mesure un signal historique, pas un prix exécutable à une minute précise.",
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
