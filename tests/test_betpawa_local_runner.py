import unittest

from betpawa_validation import validate_ticket
from tools.betpawa_local_runner import (
    UnsafeSelection,
    selection_target,
    plan_ticket,
    read_coupon_status,
)


def leg(market, **extra):
    base = {
        "domicile": "Atl. Nacional",
        "exterieur": "Dep. Tolima",
        "marche": market,
        "cote": 1.61,
        "betpawa_url": "https://www.betpawa.cm/event/35836265?filter=all",
    }
    base.update(extra)
    return base


class FakeLocator:
    def __init__(self, text):
        self.text = text

    def inner_text(self, timeout=None):
        return self.text


class FakePage:
    def __init__(self, text):
        self.text = text

    def locator(self, selector):
        return FakeLocator(self.text)


class LocalBetPawaRunnerTests(unittest.TestCase):
    def test_coupon_status_reads_betpawa_displayed_prices_without_writing(self):
        page = FakePage(
            "Coupon de pari\n"
            "8/8 sélections\n"
            "Cote totale 12,84\n"
            "Mise minimale : 100 FCFA\n"
            "Mise : 500 FCFA\n"
            "Gain potentiel : 6 420 FCFA\n"
            "Mise maximale : 10 000 FCFA"
        )
        status = read_coupon_status(page)
        self.assertEqual(status["selection_count"], 8)
        self.assertAlmostEqual(status["total_odds"], 12.84)
        self.assertEqual(status["minimum_stake"]["value"], 100.0)
        self.assertEqual(status["minimum_stake"]["currency"], "FCFA")
        self.assertEqual(status["current_stake"]["value"], 500.0)
        self.assertEqual(status["potential_win"]["value"], 6420.0)
        self.assertEqual(status["maximum_stake"]["value"], 10000.0)

    def test_coupon_status_does_not_invent_missing_values(self):
        status = read_coupon_status(FakePage("Coupon de pari\n3 sélections"))
        self.assertEqual(status["selection_count"], 3)
        self.assertIsNone(status["total_odds"])
        self.assertIsNone(status["minimum_stake"])
        self.assertIsNone(status["current_stake"])
        self.assertIsNone(status["potential_win"])

    def test_home_win_maps_to_1x2_home(self):
        markets, outcomes, label = selection_target(leg("Victoire domicile"))
        self.assertIn("1x2", markets)
        self.assertIn("home", outcomes)
        self.assertIn("Atl. Nacional", label)

    def test_away_win_maps_to_1x2_away(self):
        markets, outcomes, label = selection_target(leg("Victoire extérieur"))
        self.assertIn("1x2", markets)
        self.assertIn("away", outcomes)
        self.assertIn("Dep. Tolima", label)

    def test_canonical_generator_markets_are_translated(self):
        cases = [
            ("1x2_domicile", "Victoire domicile"),
            ("1x2_nul", "Match nul"),
            ("1x2_exterieur", "Victoire extérieur"),
            ("double_chance_1X", "Double chance 1X"),
            ("double_chance_X2", "Double chance X2"),
            ("double_chance_12", "Double chance 12"),
            ("btts_oui", "Les deux équipes marquent : oui"),
            ("btts_non", "Les deux équipes marquent : non"),
            ("over_under_total_2.5_over", "plus de 2.5 buts"),
            ("over_under_total_3.5_under", "moins de 3.5 buts"),
        ]
        for market, expected in cases:
            _, _, label = selection_target(leg(market))
            self.assertEqual(label.lower(), expected.lower())

    def test_total_under_line_is_explicit(self):
        markets, outcomes, label = selection_target(leg("Match à moins de 3,5 buts"))
        self.assertIn("total goals", markets)
        self.assertIn("under 3.5", outcomes)
        self.assertIn("moins de 3.5", label)

    def test_double_chance_uses_explicit_target_team(self):
        markets, outcomes, _ = selection_target(
            leg("Ne perd pas (victoire ou nul)", journal_team="Atl. Nacional")
        )
        self.assertEqual(markets, ["double chance"])
        self.assertIn("1x", outcomes)

    def test_double_chance_without_target_fails_closed(self):
        with self.assertRaises(UnsafeSelection):
            selection_target(leg("Ne perd pas (victoire ou nul)"))

    def test_unsupported_market_fails_closed(self):
        with self.assertRaises(UnsafeSelection):
            selection_target(leg("Handicap asiatique -0,5"))

    def test_validation_manifest_preserves_journal_team_for_double_chance(self):
        result = validate_ticket({
            "selection": [leg(
                "Ne perd pas (victoire ou nul)",
                journal_team="Atl. Nacional",
            )]
        }, 1)
        self.assertEqual(result["selection"][0]["journal_team"], "Atl. Nacional")

    def test_plan_rejects_non_betpawa_url(self):
        ticket = {"selection": [leg("Victoire domicile", betpawa_url="https://example.com/event/1")]}
        with self.assertRaises(UnsafeSelection):
            plan_ticket(ticket)

    def test_plan_does_not_accept_unsupported_market(self):
        ticket = {"selection": [leg("Score exact")]}
        with self.assertRaises(UnsafeSelection):
            plan_ticket(ticket)


if __name__ == "__main__":
    unittest.main()
