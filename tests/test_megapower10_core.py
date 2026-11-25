from datetime import datetime, timezone
import unittest

from megapower10.core import from_dict, validate_quotes, odds_band, wilson, evaluate, chronological_split, decision_snapshot, discovery_report, MIN_RECOMMENDATION_ODDS, is_recommendation_odds

BASE = {
    "event_id": "e1", "kickoff_utc": "2026-12-01T20:00:00Z", "competition": "L1",
    "market": "1X2", "selection": "2", "bookmaker": "BookA",
    "captured_at_utc": "2026-12-01T19:00:00Z", "odds": 12.0,
    "result": True, "source": "unit-test"
}

class TestMegaPower10(unittest.TestCase):
    def test_timezone_required(self):
        with self.assertRaises(ValueError): from_dict(dict(BASE, kickoff_utc="2026-12-01T20:00:00"))

    def test_invalid_price(self):
        with self.assertRaises(ValueError): from_dict(dict(BASE, odds=1.0))

    def test_kickoff_leakage_excluded(self):
        q = from_dict(dict(BASE, captured_at_utc="2026-12-01T20:00:00Z"))
        r = validate_quotes([q])
        self.assertEqual(len(r["usable"]), 0)
        self.assertEqual(r["errors"][0]["reason"], "quote_at_or_after_kickoff")

    def test_inplay_excluded(self):
        q = from_dict(dict(BASE, phase="inplay"))
        self.assertEqual(len(validate_quotes([q])["usable"]), 0)

    def test_unsettled_quote_is_valid(self):
        q = from_dict(dict(BASE, result=None))
        self.assertIsNone(q.result)

    def test_archive_stage_may_have_no_capture_timestamp(self):
        row = dict(BASE, price_stage="opening")
        row.pop("captured_at_utc")
        q = from_dict(row)
        self.assertIsNone(q.captured_at_utc)
        self.assertEqual(len(validate_quotes([q])["usable"]), 1)
        self.assertEqual(decision_snapshot([q])["selected"], 0)

    def test_bands(self):
        self.assertEqual(odds_band(10), "10-15")
        self.assertEqual(odds_band(15), "15-20")
        self.assertEqual(odds_band(50), "50+")

    def test_roi_at_odds_12_win(self):
        m = evaluate([from_dict(BASE)], min_odds=10, max_odds=15)["overall"]
        self.assertAlmostEqual(m["roi"], 11.0)
        self.assertEqual(m["n"], 1)

    def test_recommendation_floor_is_hard_and_inclusive(self):
        for price in (9.99, 8.0, 1.5):
            self.assertEqual(evaluate([from_dict(dict(BASE, odds=price))])["overall"]["n"], 0)
        for price in (10.0, 10.01):
            self.assertEqual(evaluate([from_dict(dict(BASE, odds=price))])["overall"]["n"], 1)
        self.assertEqual(MIN_RECOMMENDATION_ODDS, 10.0)

    def test_recommendation_price_must_be_finite(self):
        for price in (float('nan'), float('inf'), float('-inf'), 0, -1):
            self.assertFalse(is_recommendation_odds(price))
        self.assertTrue(is_recommendation_odds(10.0))

    def test_evaluate_cannot_weaken_floor(self):
        with self.assertRaises(ValueError): evaluate([from_dict(BASE)], min_odds=9.0)

    def test_discovery_never_promotes_sub_ten_prices(self):
        self.assertEqual(discovery_report([from_dict(dict(BASE, odds=9.99))])["groups"], 0)

    def test_wilson(self):
        lo, hi = wilson(4, 10)
        self.assertLess(lo, .4)
        self.assertGreater(hi, .4)

    def test_snapshot_one_price_per_bookmaker_and_market(self):
        rows = [
            from_dict(dict(BASE, captured_at_utc="2026-12-01T18:30:00Z", odds=13.0)),
            from_dict(dict(BASE, captured_at_utc="2026-12-01T18:55:00Z", odds=12.0)),
            from_dict(dict(BASE, captured_at_utc="2026-12-01T19:05:00Z", odds=11.0)),
        ]
        snap = decision_snapshot(rows, lead_minutes=60, tolerance_minutes=40)
        self.assertEqual(snap["selected"], 1)
        self.assertEqual(snap["quotes"][0].odds, 12.0)

    def test_snapshot_does_not_stitch_bookmakers(self):
        a = from_dict(BASE)
        b = from_dict(dict(BASE, bookmaker="BookB", odds=14.0))
        snap = decision_snapshot([a,b])
        self.assertEqual(len(snap["quotes"]), 2)
        self.assertEqual({q.bookmaker for q in snap["quotes"]}, {"BookA", "BookB"})

    def test_chronological_split(self):
        q1 = from_dict(BASE)
        q2 = from_dict(dict(BASE, event_id="e2", kickoff_utc="2027-01-01T20:00:00Z"))
        s = chronological_split([q1,q2], datetime(2026,12,15,tzinfo=timezone.utc), datetime(2027,2,1,tzinfo=timezone.utc))
        self.assertEqual(len(s["train"]), 1)
        self.assertEqual(len(s["validation"]), 1)
        self.assertEqual(len(s["test"]), 0)

    def test_discovery_keeps_small_samples_flagged(self):
        q = from_dict(BASE)
        report = discovery_report([q], min_support=30)
        self.assertEqual(report["results"][0]["status"], "support_insufficient")

if __name__ == "__main__": unittest.main()
