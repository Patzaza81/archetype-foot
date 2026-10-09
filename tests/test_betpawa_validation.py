import unittest

from betpawa_validation import build_manifest, validate_ticket


def leg(home="Atl. Nacional", away="Dep. Tolima", odds=1.61):
    return {
        "cle_match": "match:2026-10-09|atl nacional|dep tolima",
        "date": "2026-10-09",
        "heure": "02:20",
        "competition": "Colombie : Première A",
        "domicile": home,
        "exterieur": away,
        "marche": "Victoire domicile",
        "cote": odds,
        "betpawa_url": "https://www.betpawa.cm/event/35836265?filter=all",
    }


class BetpawaValidationTests(unittest.TestCase):
    def test_valid_ticket_is_ready_for_manual_review(self):
        ticket = {"scenario": "TEST", "selection": [leg()]}
        result = validate_ticket(ticket, 1)
        self.assertEqual(result["status"], "READY_FOR_REVIEW")
        self.assertTrue(result["human_validation_required"])
        self.assertFalse(result["submission_automated"])
        self.assertAlmostEqual(result["total_odds_snapshot"], 1.61)

    def test_duplicate_match_is_rejected(self):
        a = leg()
        b = leg()
        b["cote"] = 1.70
        result = validate_ticket({"selection": [a, b]}, 1)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("DUPLICATE_MATCH", result["errors"])

    def test_bad_url_is_rejected(self):
        a = leg()
        a["betpawa_url"] = "https://example.com/event/1"
        result = validate_ticket({"selection": [a]}, 1)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("LEG_1_INVALID_BETPAWA_URL", result["errors"])

    def test_odds_mismatch_is_rejected(self):
        result = validate_ticket(
            {"cote_totale": 2.00, "selection": [leg()]}, 1
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("TOTAL_ODDS_MISMATCH", result["errors"])

    def test_no_selection_is_rejected(self):
        result = validate_ticket({"selection": []}, 1)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("NO_SELECTION", result["errors"])

    def test_daily_cap_is_fifteen(self):
        raw = {"tickets": [{"selection": [leg(home=f"Home {i}", away=f"Away {i}")]} 
                            for i in range(20)]}
        manifest = build_manifest(raw)
        self.assertEqual(manifest["tickets_checked"], 15)
        self.assertEqual(manifest["max_tickets_per_day"], 15)


if __name__ == "__main__":
    unittest.main()
