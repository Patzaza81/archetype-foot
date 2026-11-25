"""MEGAPOWER 10+: immutable quote records, leakage controls and auditable evaluation.

Canonical JSONL: one row per bookmaker quote for one event/market/selection.
Required: event_id, kickoff_utc, competition, market, selection, bookmaker,
captured_at_utc (required for snapshot quotes; absent only for price_stage opening/closing),\n odds, result (bool or null), source. Optional: phase,
model_probability, closing_odds, season, quote_id.
All timestamps must be ISO-8601 with timezone. No inferred prices/results.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class Quote:
    event_id: str
    kickoff_utc: datetime
    competition: str
    market: str
    selection: str
    bookmaker: str
    captured_at_utc: datetime | None
    odds: float
    result: bool | None
    source: str
    phase: str = "prematch"
    model_probability: float | None = None
    closing_odds: float | None = None
    season: str = ""
    quote_id: str = ""
    price_stage: str = "snapshot"

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.event_id, self.market, self.selection, self.bookmaker


def _dt(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: horodatage manquant")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: ISO-8601 invalide: {value!r}") from exc
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError(f"{field}: fuseau horaire obligatoire")
    return d.astimezone(timezone.utc)


def from_dict(row: dict[str, Any]) -> Quote:
    required = ("event_id", "kickoff_utc", "competition", "market", "selection", "bookmaker", "odds", "source")
    missing = [k for k in required if k not in row or row[k] is None or row[k] == ""]
    if missing:
        raise ValueError("champs manquants: " + ", ".join(missing))
    if "result" not in row:
        raise ValueError("champ manquant: result")
    odds = float(row["odds"])
    if not math.isfinite(odds) or odds <= 1.0:
        raise ValueError("cote décimale invalide (doit être > 1)")
    result = row["result"]
    if result not in (True, False, None, 0, 1):
        raise ValueError("result doit être true, false ou null")
    result = None if result is None else bool(result)
    p = row.get("model_probability")
    p = None if p is None else float(p)
    if p is not None and (not math.isfinite(p) or not 0.0 <= p <= 1.0):
        raise ValueError("model_probability hors [0,1]")
    close = row.get("closing_odds")
    close = None if close is None else float(close)
    if close is not None and (not math.isfinite(close) or close <= 1.0):
        raise ValueError("closing_odds invalide")
    stage = str(row.get("price_stage", "snapshot")).lower()
    captured_raw = row.get("captured_at_utc")
    captured = None if captured_raw in (None, "") and stage in ("opening", "closing") else _dt(captured_raw, "captured_at_utc")
    return Quote(
        event_id=str(row["event_id"]), kickoff_utc=_dt(row["kickoff_utc"], "kickoff_utc"),
        competition=str(row["competition"]), market=str(row["market"]), selection=str(row["selection"]),
        bookmaker=str(row["bookmaker"]), captured_at_utc=captured,
        odds=odds, result=result, source=str(row["source"]), phase=str(row.get("phase", "prematch")),
        model_probability=p, closing_odds=close, season=str(row.get("season", "")), quote_id=str(row.get("quote_id", "")), price_stage=stage,
    )


def load_jsonl(path: str | Path) -> list[Quote]:
    out: list[Quote] = []
    with Path(path).open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                out.append(from_dict(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"{path}:{n}: {exc}") from exc
    return out


def validate_quotes(quotes: Iterable[Quote], *, prematch_only: bool = True) -> dict[str, Any]:
    rows = list(quotes)
    errors: list[dict[str, str]] = []
    seen: set[tuple] = set()
    usable: list[Quote] = []
    for q in rows:
        if q.captured_at_utc is None:
            if q.price_stage not in ("opening", "closing"):
                errors.append({"event_id": q.event_id, "reason": "capture_time_missing_without_archive_stage"})
                continue
        elif q.captured_at_utc >= q.kickoff_utc:
            errors.append({"event_id": q.event_id, "reason": "quote_at_or_after_kickoff"})
            continue
        if prematch_only and q.phase.lower() != "prematch":
            errors.append({"event_id": q.event_id, "reason": "inplay_excluded"})
            continue
        ident = (q.key, q.captured_at_utc, q.odds, q.source, q.price_stage)
        if ident in seen:
            errors.append({"event_id": q.event_id, "reason": "duplicate_quote"})
            continue
        seen.add(ident)
        usable.append(q)
    return {"input": len(rows), "usable": usable, "errors": errors, "excluded": len(rows) - len(usable)}


def decision_snapshot(quotes: Iterable[Quote], *, lead_minutes: int = 60, tolerance_minutes: int = 20) -> dict[str, Any]:
    """One executable quote per event/market/selection/bookmaker near a fixed pre-kickoff decision time.

    Selects the closest quote to kickoff-lead, never a quote after that decision time.
    No best-price stitching across bookmakers. Quotes outside tolerance are omitted.
    """
    if lead_minutes < 0 or tolerance_minutes < 0:
        raise ValueError("lead_minutes et tolerance_minutes doivent être >= 0")
    groups: dict[tuple, list[Quote]] = defaultdict(list)
    excluded = 0
    for q in quotes:
        if q.price_stage != "snapshot" or q.phase.lower() != "prematch" or q.captured_at_utc is None or q.captured_at_utc >= q.kickoff_utc:
            excluded += 1
            continue
        groups[q.key].append(q)
    chosen: list[Quote] = []
    missing = 0
    tolerance = timedelta(minutes=tolerance_minutes)
    for rows in groups.values():
        kickoff = rows[0].kickoff_utc
        target = kickoff - timedelta(minutes=lead_minutes)
        eligible = [q for q in rows if q.captured_at_utc is not None and q.captured_at_utc <= target]
        if not eligible:
            missing += 1
            continue
        q = max(eligible, key=lambda x: x.captured_at_utc)
        if target - q.captured_at_utc > tolerance:
            missing += 1
            continue
        chosen.append(q)
    chosen.sort(key=lambda q: (q.kickoff_utc, q.competition, q.market, q.event_id, q.selection, q.bookmaker))
    return {"quotes": chosen, "groups": len(groups), "selected": len(chosen), "missing_snapshot": missing, "excluded": excluded,
            "decision_rule": {"lead_minutes": lead_minutes, "tolerance_minutes": tolerance_minutes}}


def odds_band(odds: float) -> str:
    if odds < 5: return "<5"
    if odds < 8: return "5-8"
    if odds < 10: return "8-10"
    if odds < 15: return "10-15"
    if odds < 20: return "15-20"
    if odds < 30: return "20-30"
    if odds < 50: return "30-50"
    return "50+"


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if n == 0: return None
    p = successes / n
    den = 1 + z*z/n
    mid = (p + z*z/(2*n)) / den
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return max(0.0, mid-half), min(1.0, mid+half)


def _metrics(rows: list[Quote]) -> dict[str, Any]:
    settled = [q for q in rows if q.result is not None]
    n = len(settled)
    wins = sum(q.result is True for q in settled)
    profit = sum((q.odds - 1.0) if q.result else -1.0 for q in settled)
    prices = [q.odds for q in settled]
    return {
        "n": n, "wins": wins, "hit_rate": wins/n if n else None,
        "wilson_95": wilson(wins, n), "roi": profit/n if n else None,
        "profit_units": profit, "mean_odds": sum(prices)/n if n else None,
        "mean_implied_break_even_rate": sum(1/q.odds for q in settled)/n if n else None,
        "mean_clv_odds_ratio": (sum(q.odds/q.closing_odds - 1.0 for q in settled if q.closing_odds is not None) / sum(q.closing_odds is not None for q in settled)) if any(q.closing_odds is not None for q in settled) else None,
    }


def evaluate(quotes: Iterable[Quote], *, min_odds: float = 1.01, max_odds: float = float("inf"),
             competition: str | None = None, market: str | None = None,
             min_model_edge: float | None = None) -> dict[str, Any]:
    """Descriptive evaluation only. Selection thresholds must be learned on train, never test."""
    chosen = []
    for q in quotes:
        if q.result is None or q.odds < min_odds or q.odds >= max_odds: continue
        if competition is not None and q.competition != competition: continue
        if market is not None and q.market != market: continue
        if min_model_edge is not None:
            if q.model_probability is None or q.model_probability - 1.0/q.odds < min_model_edge: continue
        chosen.append(q)
    groups: dict[str, list[Quote]] = defaultdict(list)
    for q in chosen: groups[odds_band(q.odds)].append(q)
    return {"overall": _metrics(chosen), "by_odds_band": {k: _metrics(v) for k,v in sorted(groups.items())},
            "scope": {"min_odds_inclusive": min_odds, "max_odds_exclusive": max_odds,
                      "competition": competition, "market": market, "min_model_edge": min_model_edge}}


def discovery_report(quotes: Iterable[Quote], *, min_support: int = 30) -> dict[str, Any]:
    """Rank descriptive pockets by competition × market × odds band; no automatic promotion."""
    groups: dict[tuple[str, str, str], list[Quote]] = defaultdict(list)
    for q in quotes:
        if q.result is not None:
            groups[(q.competition, q.market, odds_band(q.odds))].append(q)
    rows = []
    for (competition, market, band), sample in groups.items():
        m = _metrics(sample)
        if m["n"] < min_support:
            status = "support_insufficient"
        elif m["roi"] is not None and m["roi"] > 0 and m["wilson_95"][0] > 0:
            status = "positive_historical_roi_requires_holdout"
        else:
            status = "no_positive_evidence"
        rows.append({"competition": competition, "market": market, "price_stage": stage, "odds_band": band, **m, "status": status})
    rows.sort(key=lambda r: (r["status"] != "positive_historical_roi_requires_holdout",
                             -(r["roi"] if r["roi"] is not None else -999), -r["n"]))
    return {"groups": len(rows), "min_support": min_support, "results": rows}


def chronological_split(quotes: Iterable[Quote], train_end: datetime, validation_end: datetime) -> dict[str, list[Quote]]:
    """Split by kickoff, strict chronological cutoffs; callers must fit only on train."""
    a, b = train_end.astimezone(timezone.utc), validation_end.astimezone(timezone.utc)
    if b <= a: raise ValueError("validation_end doit suivre train_end")
    parts = {"train": [], "validation": [], "test": []}
    for q in quotes:
        if q.kickoff_utc < a: parts["train"].append(q)
        elif q.kickoff_utc < b: parts["validation"].append(q)
        else: parts["test"].append(q)
    return parts
