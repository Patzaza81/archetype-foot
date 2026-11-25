import unittest

from megapower10.model import MatchResult
from megapower10.football_data import HistoricalPrice
from megapower10.walk_forward import enrich_prices, chronological_edge_study


class TestPriceJoin(unittest.TestCase):
    def test_devig_is_same_bookmaker_and_stage(self):
        matches = [
            MatchResult("m1", "2026-01-01", "L1", "A", "B", 2, 0),
            MatchResult("m2", "2026-01-08", "L1", "C", "A", 1, 1),
            MatchResult("m3", "2026-01-15", "L1", "B", "C", 0, 1),
            MatchResult("target", "2026-02-01", "L1", "A", "C", 1, 0),
        ]
        prices = [
            HistoricalPrice("target", "2026-02-01", "L1", "2526", "1X2", "H", "Book", "opening", 2.0, True, "test"),
            HistoricalPrice("target", "2026-02-01", "L1", "2526", "1X2", "D", "Book", "opening", 3.0, False, "test"),
            HistoricalPrice("target", "2026-02-01", "L1", "2526", "1X2", "A", "Book", "opening", 4.0, False, "test"),
        ]
        rows, meta = enrich_prices(matches, prices)
        self.assertEqual(len(rows), 3)
        self.assertAlmostEqual(sum(r["market_probability"] for r in rows), 1.0)
        self.assertEqual(meta["priced_selections"], 3)

    def test_validation_threshold_is_frozen_before_test(self):
        rows = []
        for i in range(60):
            rows.append({"date": "2026-02-01" if i < 30 else "2026-04-01",
                         "competition": "L1", "market": "1X2", "bookmaker": "Book",
                         "price_stage": "opening", "odds": 12.0, "edge": .1,
                         "result": i % 2 == 0})
        report = chronological_edge_study(rows, train_end="2026-01-01",
                                          validation_end="2026-03-01", min_support=10)
        result = report["results"][0]
        self.assertEqual(result["status"], "threshold_frozen_on_validation")
        self.assertEqual(result["test"]["n"], 30)


if __name__ == "__main__":
    unittest.main()
