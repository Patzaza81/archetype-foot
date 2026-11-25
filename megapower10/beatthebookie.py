"""Adapter for the public Beat The Bookie closing-odds archive.

The archive contains closing averages and best observed odds per 1X2 outcome,
not timestamped individual quotes for every bookmaker. The best price is kept
separate from the average market reference; it is never described as an
arbitrage or as a guaranteed currently executable price.
"""
from __future__ import annotations

import csv
import gzip
from datetime import datetime
from pathlib import Path

from .football_data import HistoricalMatch, HistoricalPrice, _price, _price_score


def _date(value: str) -> str | None:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value[:19], fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def load_beat_the_bookie(path: str | Path) -> tuple[list[HistoricalMatch], list[HistoricalPrice], dict]:
    """Load closing_odds.csv.gz; retain consensus reference and best observed execution quote."""
    source_path = Path(path)
    opener = gzip.open if source_path.suffix == ".gz" else open
    matches: list[HistoricalMatch] = []
    prices: list[HistoricalPrice] = []
    seen: set[str] = set()
    rejected = 0
    with opener(source_path, "rt", encoding="latin1", newline="") as fh:
        for row in csv.DictReader(fh):
            date = _date(row.get("match_date") or row.get("date") or "")
            home = (row.get("home_team") or "").strip()
            away = (row.get("away_team") or "").strip()
            hg = _price_score(row.get("home_score"))
            ag = _price_score(row.get("away_score"))
            match_id = str(row.get("match_id") or row.get("id") or "").strip()
            league = (row.get("league") or "").strip()
            if not date or not home or not away or hg is None or ag is None or not league:
                rejected += 1
                continue
            event_id = f"beatthebookie:{match_id or date + ':' + home + ':' + away}"
            if event_id in seen:
                continue
            seen.add(event_id)
            competition = f"beatthebookie:{league}"
            result = "H" if hg > ag else "A" if hg < ag else "D"
            matches.append(HistoricalMatch(event_id, date, competition, home, away, hg, ag,
                                            "2005-2015", f"BeatTheBookie/{source_path.name}"))
            outcomes = (
                ("H", "avg_odds_home_win", "max_odds_home_win", "top_bookie_home_win", "n_odds_home_win"),
                ("D", "avg_odds_draw", "max_odds_draw", "top_bookie_draw", "n_odds_draw"),
                ("A", "avg_odds_away_win", "max_odds_away_win", "top_bookie_away_win", "n_odds_away_win"),
            )
            for selection, avg_col, max_col, book_col, count_col in outcomes:
                avg = _price(row.get(avg_col))
                best = _price(row.get(max_col))
                bookmaker_count = _price_score(row.get(count_col))
                settled = selection == result
                if avg is not None:
                    prices.append(HistoricalPrice(
                        event_id, date, competition, "2005-2015", "1X2", selection,
                        "BTB_average", "closing", avg, settled,
                        f"BeatTheBookie/{source_path.name}", avg, "average_of_bookmakers", bookmaker_count,
                    ))
                if best is not None and avg is not None:
                    top_bookie = (row.get(book_col) or "").strip() or "unknown_bookmaker"
                    prices.append(HistoricalPrice(
                        event_id, date, competition, "2005-2015", "1X2", selection,
                        "BTB_best_available", "closing", best, settled,
                        f"BeatTheBookie/{source_path.name}", avg, top_bookie, bookmaker_count,
                    ))

    matches.sort(key=lambda m: (m.date, m.competition, m.event_id))
    prices.sort(key=lambda q: (q.kickoff_date, q.competition, q.market, q.selection, q.bookmaker))
    summary = {
        "source": "Beat The Bookie — Kaggle austro/beat-the-bookie-worldwide-football-dataset",
        "dataset_url": "https://www.kaggle.com/datasets/austro/beat-the-bookie-worldwide-football-dataset",
        "research_paper_url": "https://arxiv.org/abs/1710.02824",
        "license": "CC BY-SA 4.0; attribute source and preserve share-alike obligations",
        "matches": len(matches), "price_rows": len(prices),
        "competitions": len({m.competition for m in matches}),
        "first_date": matches[0].date if matches else None,
        "last_date": matches[-1].date if matches else None,
        "rejected_rows": rejected,
        "price_stages": ["closing"],
        "markets": ["1X2"],
        "price_types": ["average_market_reference", "best_observed_closing_price"],
        "limitations": [
            "closing archive only; no exact quote capture timestamps",
            "best price and top bookmaker are reported per outcome; not a simultaneous multi-outcome arbitrage",
            "average odds are used for de-vig; best observed odds are used for hypothetical execution ROI",
            "historical coverage ends in 2015; this source is a long-range research archive, not a current price feed",
        ],
    }
    return matches, prices, summary
