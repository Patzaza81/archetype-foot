import csv
import gzip
import tempfile
import unittest
from pathlib import Path

from megapower10.beatthebookie import load_beat_the_bookie
from megapower10.model import MatchResult
from megapower10.walk_forward import enrich_prices


class TestBeatTheBookieAdapter(unittest.TestCase):
    def test_closing_average_reference_and_best_price_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "closing_odds.csv.gz"
            fields = ["match_id", "league", "match_date", "home_team", "away_team",
                      "home_score", "away_score",
                      "avg_odds_home_win", "avg_odds_draw", "avg_odds_away_win",
                      "max_odds_home_win", "max_odds_draw", "max_odds_away_win",
                      "top_bookie_home_win", "top_bookie_draw", "top_bookie_away_win"]
            row = {"match_id": "42", "league": "Test League", "match_date": "2015-06-30 20:00:00",
                   "home_team": "Alpha", "away_team": "Beta", "home_score": "0.0", "away_score": "2.0",
                   "avg_odds_home_win": "3.0", "avg_odds_draw": "3.2", "avg_odds_away_win": "2.4",
                   "max_odds_home_win": "3.4", "max_odds_draw": "3.8", "max_odds_away_win": "2.8",
                   "top_bookie_home_win": "BookA", "top_bookie_draw": "BookB", "top_bookie_away_win": "Pinnacle"}
            with gzip.open(path, "wt", encoding="latin1", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            matches, prices, summary = load_beat_the_bookie(path)
            self.assertEqual(len(matches), 1)
            self.assertEqual(len(prices), 6)
            best_away = next(q for q in prices if q.bookmaker == "BTB_best_available" and q.selection == "A")
            self.assertEqual(best_away.odds, 2.8)
            self.assertEqual(best_away.reference_odds, 2.4)
            self.assertEqual(best_away.execution_bookmaker, "Pinnacle")
            self.assertTrue(best_away.result)
            self.assertEqual(summary["license"], "CC BY-SA 4.0; attribute source and preserve share-alike obligations")

            prior = MatchResult("prior", "2015-06-20", matches[0].competition, "Alpha", "Gamma", 2, 0)
            target = MatchResult(matches[0].event_id, matches[0].date, matches[0].competition,
                                 matches[0].home, matches[0].away, matches[0].home_goals, matches[0].away_goals)
            enriched, _ = enrich_prices([prior, target], prices)
            best_home = next(r for r in enriched if r["bookmaker"] == "BTB_best_available" and r["selection"] == "H")
            expected = (1/3.0) / (1/3.0 + 1/3.2 + 1/2.4)
            self.assertAlmostEqual(best_home["market_probability"], expected)
            self.assertEqual(best_home["odds"], 3.4)
            self.assertEqual(best_home["execution_bookmaker"], "BookA")


if __name__ == "__main__":
    unittest.main()
