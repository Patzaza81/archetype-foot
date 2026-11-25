import unittest

from megapower10.model import MatchResult, predict_one, walk_forward, tune_parameters


class TestWalkForwardModel(unittest.TestCase):
    def test_no_future_data_used(self):
        history = [
            MatchResult("1", "2026-01-01", "L1", "A", "B", 2, 0),
            MatchResult("2", "2026-01-08", "L1", "C", "A", 1, 1),
            MatchResult("future", "2026-03-01", "L1", "A", "B", 8, 0),
        ]
        target = MatchResult("target", "2026-02-01", "L1", "A", "C", 0, 0)
        pred = predict_one(history, target)
        self.assertEqual(pred["n_league"], 2)

    def test_leagues_are_not_pooled(self):
        history = [MatchResult("1", "2026-01-01", "L1", "A", "B", 3, 0)]
        target = MatchResult("2", "2026-02-01", "L2", "C", "D", 1, 0)
        pred = predict_one(history, target)
        self.assertEqual(pred["status"], "no_prior_league_data")

    def test_probabilities_sum_to_one(self):
        history = [
            MatchResult("1", "2026-01-01", "L1", "A", "B", 2, 0),
            MatchResult("2", "2026-01-08", "L1", "C", "A", 1, 1),
            MatchResult("3", "2026-01-15", "L1", "B", "C", 0, 1),
        ]
        target = MatchResult("4", "2026-02-01", "L1", "A", "C", 0, 0)
        p = predict_one(history, target)["probabilities"]
        self.assertAlmostEqual(p["H"] + p["D"] + p["A"], 1.0, places=8)
        self.assertAlmostEqual(p["over_2_5"] + p["under_2_5"], 1.0, places=8)

    def test_tuning_falls_back_when_train_support_is_too_small(self):
        matches = [MatchResult("1", "2026-01-01", "L1", "A", "B", 1, 0)]
        tuned = tune_parameters(matches, train_end="2026-02-01", min_training_forecasts=30)
        self.assertEqual(tuned["status"], "fallback_insufficient_training_history")

    def test_first_match_is_not_predicted(self):
        first = MatchResult("1", "2026-01-01", "L1", "A", "B", 1, 0)
        result = walk_forward([first])
        self.assertEqual(result[0]["status"], "no_prior_league_data")


if __name__ == "__main__":
    unittest.main()
