"""Join walk-forward forecasts to same-bookmaker historical prices and test edges.

The bookmaker probability is de-vigged within the same event/bookmaker/market/
price stage. No cross-bookmaker best-price stitching. Opening and closing
archives remain separate because exact capture times are unavailable.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Iterable

from .core import odds_band, wilson
from .model import MatchResult, walk_forward


REQUIRED_OUTCOMES = {"1X2": {"H", "D", "A"},
                     "total_2_5": {"over_2_5", "under_2_5"}}


def enrich_prices(matches: Iterable[MatchResult], prices: Iterable, *,
                  window: int = 8, prior_matches: float = 4.0) -> tuple[list[dict], dict]:
    match_rows = list(matches)
    price_rows = list(prices)
    forecasts = walk_forward(match_rows, window=window, prior_matches=prior_matches)
    forecast_by_id = {p["event_id"]: p for p in forecasts}
    groups: dict[tuple, list] = defaultdict(list)
    for q in price_rows:
        groups[(q.event_id, q.bookmaker, q.market, q.price_stage)].append(q)

    enriched = []
    price_by_stage = {(q.event_id, q.bookmaker, q.market, q.selection, q.price_stage): q.odds for q in price_rows}
    skipped_no_forecast = skipped_incomplete_market = 0
    for key, group in groups.items():
        event_id, bookmaker, market, stage = key
        forecast = forecast_by_id.get(event_id)
        if not forecast or forecast["probabilities"] is None:
            skipped_no_forecast += len(group)
            continue
        required = REQUIRED_OUTCOMES.get(market)
        if required is None:
            continue
        by_selection = {q.selection: q for q in group}
        if not required.issubset(by_selection):
            skipped_incomplete_market += len(group)
            continue
        implied = {s: 1.0 / (by_selection[s].reference_odds or by_selection[s].odds) for s in required}
        overround = sum(implied.values())
        if overround <= 0:
            continue
        for selection in required:
            q = by_selection[selection]
            p_model = forecast["probabilities"].get(selection)
            if p_model is None:
                continue
            p_market = implied[selection] / overround
            enriched.append({
                "event_id": q.event_id, "date": q.kickoff_date, "competition": q.competition,
                "season": q.season, "market": q.market, "selection": q.selection,
                "bookmaker": q.bookmaker, "execution_bookmaker": getattr(q, "execution_bookmaker", "") or q.bookmaker,
                "price_stage": q.price_stage, "odds": q.odds, "reference_odds": getattr(q, "reference_odds", None) or q.odds,
                "bookmaker_count": getattr(q, "bookmaker_count", None),
                "result": q.result, "model_probability": p_model,
                "market_probability": p_market, "edge": p_model - p_market, "market_overround": overround,
                "opening_to_closing_odds_change": (price_by_stage.get((q.event_id, q.bookmaker, q.market, q.selection, "closing")) / q.odds - 1.0) if q.price_stage == "opening" and price_by_stage.get((q.event_id, q.bookmaker, q.market, q.selection, "closing")) else None,
                "n_league_before_match": forecast["n_league"], "source": q.source,
            })
    enriched.sort(key=lambda r: (r["date"], r["competition"], r["market"], r["event_id"], r["selection"], r["bookmaker"], r["price_stage"]))
    return enriched, {
        "forecasts": len(forecasts), "priced_selections": len(enriched),
        "skipped_no_forecast": skipped_no_forecast,
        "skipped_incomplete_market": skipped_incomplete_market,
        "model": {"type": "league-specific Poisson", "window": window, "prior_matches": prior_matches},
        "de_vig": "normalisation des probabilités implicites par événement + bookmaker + marché + phase de prix",
    }


def _stats(rows: list[dict]) -> dict:
    ordered = sorted(rows, key=lambda r: (r["date"], r["event_id"]))
    n = len(ordered)
    wins = sum(bool(r["result"]) for r in ordered)
    profits = [(r["odds"] - 1.0) if r["result"] else -1.0 for r in ordered]
    profit = sum(profits)
    daily_profit: dict[str, float] = defaultdict(float)
    for row, delta in zip(ordered, profits):
        daily_profit[row["date"]] += delta
    cumulative = peak = max_drawdown = 0.0
    losing_day_streak = max_losing_day_streak = 0
    for day in sorted(daily_profit):
        delta = daily_profit[day]
        cumulative += delta
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
        losing_day_streak = losing_day_streak + 1 if delta < 0 else 0
        max_losing_day_streak = max(max_losing_day_streak, losing_day_streak)
    execution_counts = Counter(r.get("execution_bookmaker") for r in ordered if r.get("execution_bookmaker"))
    return {
        "n": n, "wins": wins, "hit_rate": wins/n if n else None,
        "wilson_95": wilson(wins, n), "roi": profit/n if n else None,
        "profit_units": profit, "max_daily_drawdown_units": max_drawdown,
        "max_consecutive_losing_days": max_losing_day_streak,
        "execution_bookmakers": len(execution_counts),
        "top_execution_bookmakers": execution_counts.most_common(10),
        "mean_odds": sum(r["odds"] for r in ordered)/n if n else None,
        "mean_edge": sum(r["edge"] for r in ordered)/n if n else None,
        "mean_bookmaker_count": (sum(r["bookmaker_count"] for r in ordered if r.get("bookmaker_count") is not None) / sum(r.get("bookmaker_count") is not None for r in ordered)) if any(r.get("bookmaker_count") is not None for r in ordered) else None,
    }


def evaluate_edge(rows: Iterable[dict], *, min_edge: float = 0.0,
                  min_odds: float = 1.01, max_odds: float = float("inf")) -> dict:
    chosen = [r for r in rows if r["edge"] >= min_edge and min_odds <= r["odds"] < max_odds]
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in chosen:
        groups[odds_band(r["odds"])].append(r)
    return {"overall": _stats(chosen), "by_odds_band": {k: _stats(v) for k, v in sorted(groups.items())},
            "rule": {"min_edge": min_edge, "min_odds": min_odds, "max_odds_exclusive": max_odds}}


def _depth_band(value) -> str:
    if value is None: return "unknown"
    if value < 5: return "1-4"
    if value < 10: return "5-9"
    return "10+"


def chronological_edge_study(rows: Iterable[dict], *, train_end: str, validation_end: str,
                             min_support: int = 30,
                             thresholds: tuple[float, ...] = (0.0, .01, .02, .03, .05, .08, .10, .15, .20, .25)) -> dict:
    """Choose positive-ROI edge thresholds on validation only; final test remains untouched."""
    rows = list(rows)
    train_groups: dict[tuple, list[dict]] = defaultdict(list)
    validation_groups: dict[tuple, list[dict]] = defaultdict(list)
    test_groups: dict[tuple, list[dict]] = defaultdict(list)
    best_by_event: dict[tuple, dict] = {}
    for r in rows:
        key = (r["competition"], r["market"], r["bookmaker"], r["price_stage"], odds_band(r["odds"]), _depth_band(r.get("bookmaker_count")))
        period = "train" if r["date"] < train_end else "validation" if r["date"] < validation_end else "test"
        event_key = (period, key, r["event_id"])
        previous = best_by_event.get(event_key)
        if previous is None or r["edge"] > previous["edge"]:
            best_by_event[event_key] = r
    for (period, key, _event_id), r in best_by_event.items():
        if period == "train":
            train_groups[key].append(r)
        elif period == "validation":
            validation_groups[key].append(r)
        else:
            test_groups[key].append(r)
    keys = sorted(set(train_groups) | set(validation_groups) | set(test_groups))
    results = []
    for competition, market, bookmaker, stage, band, depth in keys:
        key = (competition, market, bookmaker, stage, band, depth)
        v = validation_groups.get(key, [])
        t = test_groups.get(key, [])
        candidates = []
        for threshold in thresholds:
            scored = [r for r in v if r["edge"] >= threshold]
            m = _stats(scored)
            if m["n"] >= min_support and m["roi"] is not None and m["roi"] > 0:
                candidates.append((m["roi"], threshold, m))
        if not candidates:
            results.append({"competition": competition, "market": market, "bookmaker": bookmaker,
                            "price_stage": stage, "odds_band": band, "bookmaker_depth": depth, "status": "no_validation_candidate",
                            "validation": _stats(v), "test": None})
            continue
        _, chosen_threshold, vm = max(candidates, key=lambda x: (x[0], x[2]["n"], x[1]))
        tm = _stats([r for r in t if r["edge"] >= chosen_threshold])
        results.append({"competition": competition, "market": market, "bookmaker": bookmaker,
                        "price_stage": stage, "odds_band": band, "bookmaker_depth": depth, "status": "threshold_frozen_on_validation",
                        "min_edge": chosen_threshold, "validation": vm, "test": tm})
    results.sort(key=lambda r: (r["status"] != "threshold_frozen_on_validation",
                                -(r["test"]["roi"] if r.get("test") and r["test"]["roi"] is not None else -999),
                                -(r["test"]["n"] if r.get("test") else 0)))
    return {
        "cutoffs": {"train_before": train_end, "validation_before": validation_end},
        "counts": {"all": len(rows), "train": sum(map(len, train_groups.values())),
                   "validation": sum(map(len, validation_groups.values())),
                   "test": sum(map(len, test_groups.values()))},
        "method": "walk-forward forecasts; bookmaker-specific de-vig; validation-only positive-ROI threshold selection; frozen final test",
        "results": results,
    }


def forecast_quality_report(rows: Iterable[dict], *, train_end: str | None = None,
                            validation_end: str | None = None) -> dict:
    """Compare model and de-vigged bookmaker probabilities separately by time block."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    calibration: dict[tuple, list[tuple[float, int]]] = defaultdict(list)
    for r in rows:
        if train_end is None or validation_end is None:
            period = "all_walk_forward"
        elif r["date"] < train_end:
            period = "train"
        elif r["date"] < validation_end:
            period = "validation"
        else:
            period = "test"
        groups[(period, r["competition"], r["market"], r["bookmaker"], r["price_stage"], r["event_id"])].append(r)

    aggregate: dict[tuple, list[tuple[float, float, float, float]]] = defaultdict(list)
    for (period, competition, market, bookmaker, stage, _event), sample in groups.items():
        settled = [r for r in sample if r["result"] is not None]
        if not settled:
            continue
        model_brier = sum((r["model_probability"] - int(r["result"]))**2 for r in settled) / len(settled)
        market_brier = sum((r["market_probability"] - int(r["result"]))**2 for r in settled) / len(settled)
        model_logloss = -sum((int(r["result"]) * math.log(max(1e-12, r["model_probability"])) +
                              (1-int(r["result"])) * math.log(max(1e-12, 1-r["model_probability"]))) for r in settled) / len(settled)
        market_logloss = -sum((int(r["result"]) * math.log(max(1e-12, r["market_probability"])) +
                               (1-int(r["result"])) * math.log(max(1e-12, 1-r["market_probability"]))) for r in settled) / len(settled)
        key = (period, competition, market, bookmaker, stage)
        aggregate[key].append((model_brier, market_brier, model_logloss, market_logloss))
        for r in settled:
            decile = min(9, int(r["model_probability"] * 10))
            calibration[(period, competition, market, bookmaker, stage, decile)].append((r["model_probability"], int(r["result"])))

    quality = []
    for key, vals in aggregate.items():
        n = len(vals)
        quality.append({
            "period": key[0], "competition": key[1], "market": key[2], "bookmaker": key[3],
            "price_stage": key[4], "events": n,
            "model_brier": sum(v[0] for v in vals)/n,
            "market_brier": sum(v[1] for v in vals)/n,
            "model_logloss": sum(v[2] for v in vals)/n,
            "market_logloss": sum(v[3] for v in vals)/n,
        })
    quality.sort(key=lambda r: (r["period"], r["competition"], r["market"], r["bookmaker"], r["price_stage"]))
    bins = []
    for key, vals in sorted(calibration.items()):
        bins.append({"period": key[0], "competition": key[1], "market": key[2], "bookmaker": key[3],
                     "price_stage": key[4], "model_probability_decile": key[5],
                     "n": len(vals), "mean_probability": sum(x[0] for x in vals)/len(vals),
                     "observed_rate": sum(x[1] for x in vals)/len(vals)})
    return {"method": "mean per-selection Brier and log loss on fully priced settled events",
            "by_period_competition_market_bookmaker_stage": quality, "model_calibration_deciles": bins}
