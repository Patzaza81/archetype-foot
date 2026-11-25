"""Football-Data.co.uk adapter for retrospective price studies.

Important: source archives provide opening/closing columns but no exact capture
timestamps or timezone-aware kickoff timestamps. This adapter therefore emits
HistoricalPrice, never Quote. These records can be used for price-band and
market studies, but NEVER for a timestamped executable-price or CLV-at-decision
claim. Aggregate Max/Avg columns are deliberately excluded because they may
combine prices that were not concurrently available.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class HistoricalPrice:
    event_id: str
    kickoff_date: str
    competition: str
    season: str
    market: str
    selection: str
    bookmaker: str
    price_stage: str
    odds: float
    result: bool
    source: str


BOOKS_1X2 = {
    "Bet365": ("B365H", "B365D", "B365A", "B365CH", "B365CD", "B365CA"),
    "Betfair": ("BFDH", "BFDD", "BFDA", "BFDCH", "BFDCD", "BFDCA"),
    "BetVictor": ("BVH", "BVD", "BVA", "BVCH", "BVCD", "BVCA"),
    "Betway": ("BWH", "BWD", "BWA", "BWCH", "BWCD", "BWCA"),
    "PaddyPower": ("PPH", "PPD", "PPA", "PPCH", "PPCD", "PPCA"),
    "SkyBet": ("SKBH", "SKBD", "SKBA", "SKBCH", "SKBCD", "SKBCA"),
    "BetfairExchange": ("BFEH", "BFED", "BFEA", "BFECH", "BFECD", "BFECA"),
    "Pinnacle": ("PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA"),
}
BOOKS_TOTALS = {
    "Bet365": ("B365>2.5", "B365<2.5", "B365C>2.5", "B365C<2.5"),
    "BetfairExchange": ("BFE>2.5", "BFE<2.5", "BFEC>2.5", "BFEC<2.5"),
}


def _date(value: str) -> str | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except (ValueError, AttributeError):
            pass
    return None


def _price(value: str | None) -> float | None:
    try:
        x = float(str(value).strip())
        return x if x > 1.0 else None
    except (TypeError, ValueError):
        return None


def _result_1x2(ftr: str, selection: str) -> bool | None:
    return None if ftr not in ("H", "D", "A") else ftr == selection


def load_football_data(root: str | Path = "data/football_data") -> tuple[list[HistoricalPrice], dict]:
    """Read raw CSVs only; preserve season, competition, bookmaker and price stage."""
    base = Path(root)
    paths = sorted(base.glob("snapshots/*/raw/*.csv"))
    paths += sorted(base.glob("snapshots/*/nouvelles_ligues/raw/*.csv"))
    paths += sorted(base.glob("raw/*/*.csv"))
    paths += sorted(base.glob("raw/*/nouvelles_ligues/*.csv"))
    output: list[HistoricalPrice] = []
    errors: dict[str, int] = {}
    seen: set[tuple] = set()

    for path in paths:
        parts = path.parts
        try:
            i = parts.index("snapshots") if "snapshots" in parts else parts.index("raw")
            season = parts[i + 1]
        except (ValueError, IndexError):
            season = "unknown"
        code = path.stem
        is_new = "nouvelles_ligues" in parts
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
            for row_num, row in enumerate(csv.DictReader(fh), 2):
                date = _date(row.get("Date", ""))
                home = (row.get("HomeTeam") or row.get("Home") or "").strip()
                away = (row.get("AwayTeam") or row.get("Away") or "").strip()
                fthg = _price_score(row.get("FTHG") if not is_new else row.get("HG"))
                ftag = _price_score(row.get("FTAG") if not is_new else row.get("AG"))
                ftr = (row.get("FTR") or "").strip()
                if not date or not home or not away or fthg is None or ftag is None:
                    errors["incomplete_result_or_identity"] = errors.get("incomplete_result_or_identity", 0) + 1
                    continue
                if ftr not in ("H", "D", "A"):
                    ftr = "H" if fthg > ftag else "A" if fthg < ftag else "D"
                league_name = (row.get("League") or row.get("Div") or code).strip()
                competition = f"{code}:{league_name}"
                event_id = f"football-data:{season}:{code}:{date}:{home}:{away}"
                source = f"Football-Data.co.uk/{path.as_posix()}"
                for book, cols in BOOKS_1X2.items():
                    for stage, offset in (("opening", 0), ("closing", 3)):
                        for selection, col in zip(("H", "D", "A"), cols[offset:offset+3]):
                            price = _price(row.get(col))
                            if price is None:
                                continue
                            item = HistoricalPrice(event_id, date, competition, season, "1X2", selection,
                                                   book, stage, price, _result_1x2(ftr, selection), source)
                            ident = (item.event_id, item.market, item.selection, item.bookmaker, item.price_stage)
                            if ident not in seen:
                                seen.add(ident); output.append(item)
                total = fthg + ftag
                for book, cols in BOOKS_TOTALS.items():
                    for stage, offset in (("opening", 0), ("closing", 2)):
                        for selection, col in zip(("over_2_5", "under_2_5"), cols[offset:offset+2]):
                            price = _price(row.get(col))
                            if price is None:
                                continue
                            won = total >= 3 if selection == "over_2_5" else total <= 2
                            item = HistoricalPrice(event_id, date, competition, season, "total_2_5", selection,
                                                   book, stage, price, won, source)
                            ident = (item.event_id, item.market, item.selection, item.bookmaker, item.price_stage)
                            if ident not in seen:
                                seen.add(ident); output.append(item)

    output.sort(key=lambda q: (q.kickoff_date, q.competition, q.market, q.selection, q.bookmaker, q.price_stage))
    summary = {
        "csv_files": len(paths), "price_rows": len(output), "events": len({q.event_id for q in output}),
        "competitions": len({(q.season, q.competition) for q in output}),
        "seasons": sorted({q.season for q in output}),
        "markets": sorted({q.market for q in output}),
        "bookmakers": sorted({q.bookmaker for q in output}),
        "price_stages": sorted({q.price_stage for q in output}),
        "missing_rows": errors,
        "limitations": [
            "aucun horodatage exact de capture fourni par la source",
            "aucun fuseau/heure de coup d'envoi fiable dans cet adaptateur",
            "Max et Avg exclus : prix agrégés non nécessairement simultanés",
            "seuls 1X2 et total 2.5 sont couverts ici",
        ],
    }
    return output, summary


def _price_score(value: str | None) -> int | None:
    try:
        x = int(str(value).strip())
        return x if x >= 0 else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class HistoricalMatch:
    event_id: str
    date: str
    competition: str
    home: str
    away: str
    home_goals: int
    away_goals: int
    season: str
    source: str


def load_football_data_matches(root: str | Path = "data/football_data") -> tuple[list[HistoricalMatch], dict]:
    """Load match outcomes for the walk-forward model; no odds are read here."""
    base = Path(root)
    paths = sorted(base.glob("snapshots/*/raw/*.csv"))
    paths += sorted(base.glob("snapshots/*/nouvelles_ligues/raw/*.csv"))
    paths += sorted(base.glob("raw/*/*.csv"))
    paths += sorted(base.glob("raw/*/nouvelles_ligues/*.csv"))
    rows: dict[tuple, HistoricalMatch] = {}
    rejected = 0
    for path in paths:
        parts = path.parts
        try:
            i = parts.index("snapshots") if "snapshots" in parts else parts.index("raw")
            season = parts[i + 1]
        except (ValueError, IndexError):
            season = "unknown"
        code = path.stem
        is_new = "nouvelles_ligues" in parts
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                date = _date(row.get("Date", ""))
                home = (row.get("HomeTeam") or row.get("Home") or "").strip()
                away = (row.get("AwayTeam") or row.get("Away") or "").strip()
                hg = _price_score(row.get("FTHG") if not is_new else row.get("HG"))
                ag = _price_score(row.get("FTAG") if not is_new else row.get("AG"))
                if not date or not home or not away or hg is None or ag is None:
                    rejected += 1
                    continue
                league_name = (row.get("League") or row.get("Div") or code).strip()
                competition = f"{code}:{league_name}"
                event_id = f"football-data:{season}:{code}:{date}:{home}:{away}"
                match = HistoricalMatch(event_id, date, competition, home, away, hg, ag, season,
                                        f"Football-Data.co.uk/{path.as_posix()}")
                rows[(season, code, date, home, away)] = match
    matches = sorted(rows.values(), key=lambda m: (m.date, m.competition, m.event_id))
    summary = {
        "matches": len(matches), "csv_files": len(paths), "rejected_incomplete": rejected,
        "competitions": len({m.competition for m in matches}), "seasons": sorted({m.season for m in matches}),
        "first_date": matches[0].date if matches else None, "last_date": matches[-1].date if matches else None,
        "source": "Football-Data.co.uk raw results only",
    }
    return matches, summary
