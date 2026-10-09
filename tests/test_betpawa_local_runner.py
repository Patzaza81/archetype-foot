import unittest

from betpawa_validation import validate_ticket
from tools.betpawa_local_runner import UnsafeSelection, selection_target, plan_ticket


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


class LocalBetPawaRunnerTests(unittest.TestCase):
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
