import unittest

from megapower10.model import MatchResult
from megapower10.football_data import HistoricalPrice
from megapower10.walk_forward import enrich_prices, chronological_edge_study, forecast_quality_report, evaluate_edge


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

    def test_negative_validation_does_not_select_a_test_strategy(self):
        rows = [{"event_id": f"n{i}", "date": "2026-02-01" if i < 30 else "2026-04-01",
                 "competition": "L1", "market": "1X2", "bookmaker": "Book",
                 "price_stage": "opening", "odds": 10.2, "edge": .1,
                 "result": False} for i in range(60)]
        report = chronological_edge_study(rows, train_end="2026-01-01",
                                          validation_end="2026-03-01", min_support=10)
        self.assertEqual(report["results"][0]["status"], "no_validation_candidate")
        self.assertIsNone(report["results"][0]["test"])

    def test_edge_evaluation_rejects_below_ten_and_accepts_exact_ten(self):
        base = {"event_id": "e", "date": "2026-01-01", "competition": "L1", "market": "1X2", "bookmaker": "Book", "price_stage": "closing", "edge": .2, "result": True}
        report = evaluate_edge([dict(base, odds=9.99), dict(base, event_id="e2", odds=10.0)])
        self.assertEqual(report["overall"]["n"], 1)
        self.assertEqual(report["overall"]["mean_odds"], 10.0)
        with self.assertRaises(ValueError): evaluate_edge([dict(base, odds=10)], min_odds=9.0)

    def test_chronological_study_filters_every_price_below_ten(self):
        rows = [{"event_id": f"e{i}", "date": "2026-02-01", "competition": "L1", "market": "1X2", "bookmaker": "Book", "price_stage": "closing", "odds": 9.99, "edge": .5, "result": True} for i in range(50)]
        report = chronological_edge_study(rows, train_end="2026-01-01", validation_end="2026-03-01", min_support=1)
        self.assertEqual(report["counts"]["all"], 0)
        self.assertEqual(report["recommendation_policy"]["minimum_odds_inclusive"], 10.0)
        self.assertEqual(report["results"], [])

    def test_probability_quality_compares_model_and_market(self):
        rows = [
            {"competition": "L1", "market": "1X2", "bookmaker": "Book", "price_stage": "opening",
             "event_id": "e1", "model_probability": .6, "market_probability": .4, "result": True},
            {"competition": "L1", "market": "1X2", "bookmaker": "Book", "price_stage": "opening",
             "event_id": "e1", "model_probability": .2, "market_probability": .3, "result": False},
            {"competition": "L1", "market": "1X2", "bookmaker": "Book", "price_stage": "opening",
             "event_id": "e1", "model_probability": .2, "market_probability": .3, "result": False},
        ]
        report = forecast_quality_report(rows)
        self.assertEqual(report["by_competition_market_bookmaker_stage"][0]["events"], 1)
        self.assertLess(report["by_competition_market_bookmaker_stage"][0]["model_brier"],
                        report["by_competition_market_bookmaker_stage"][0]["market_brier"])

    def test_validation_threshold_is_frozen_before_test(self):
        rows = []
        for i in range(60):
            rows.append({"event_id": f"e{i}", "date": "2026-02-01" if i < 30 else "2026-04-01",
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
