import copy
import json
import unittest
from pathlib import Path
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from betpawa_validation import _cache_team_name, build_manifest, validate_ticket


# Horloge figée : les jambes de test ont des dates en dur (11/10/2026) ; sans cela le coup d'envoi passe dans le passé
# dès le lendemain et le ticket est rejeté (EVENT_EXPIRED) alors que le code est correct.
def _horloge(instant):
    class Fige(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    return mock.patch("betpawa_validation.datetime", Fige)


AVANT_MATCHS = datetime(2026, 10, 9, 12, 0, tzinfo=ZoneInfo("Africa/Douala"))


def _sous_horloge(f):
    def enveloppe(*a, **k):
        with _horloge(AVANT_MATCHS):
            return f(*a, **k)
    enveloppe.__name__ = f.__name__
    return enveloppe


def leg(home="Atl. Nacional", away="Dep. Tolima", odds=1.61):
    return {
        "cle_match": "match:test|atl nacional|dep tolima",
        "date": "2026-10-11",
        "heure": "23:59",
        "competition": "Colombie : Première A",
        "domicile": home,
        "exterieur": away,
        "marche": "Victoire domicile",
        "cote": odds,
        "betpawa_url": "https://www.betpawa.cm/event/35836265?filter=all",
    }


class BetpawaValidationTests(unittest.TestCase):
    @_sous_horloge
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

    def test_same_fixture_different_markets_is_rejected_without_explicit_key(self):
        a = leg()
        b = leg()
        a.pop("cle_match")
        b.pop("cle_match")
        b["marche"] = "Match à plus de 2,5 buts"
        result = validate_ticket({"selection": [a, b]}, 1)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("DUPLICATE_MATCH", result["errors"])

    def test_kickoff_in_the_past_is_rejected(self):
        a = leg()
        a["date"] = "2026-10-09"
        a["heure"] = "15:00"
        now = datetime(2026, 10, 9, 20, 0, tzinfo=ZoneInfo("Africa/Douala"))
        result = validate_ticket({"selection": [a]}, 1, now=now)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("LEG_1_EVENT_EXPIRED", result["errors"])

    def test_invalid_odds_are_rejected(self):
        result = validate_ticket({"selection": [leg(odds=1.0)]}, 1)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("LEG_1_INVALID_ODDS", result["errors"])

    @_sous_horloge
    def test_missing_ticket_url_is_resolved_from_verified_scraping_cache(self):
        candidate = leg(home="Toronto", away="Montreal")
        candidate["date"] = "2026-10-10"
        candidate["betpawa_url"] = None
        cache = {"toronto||montreal||2026-10-10": {
            "home_source": "Toronto", "away_source": "Montreal", "date": "2026-10-10", "confidence": "certain",
            "event_id": "https://www.betpawa.cm/event/36682856?filter=all"}}
        with mock.patch("betpawa_validation._load_betpawa_cache", return_value=cache):
            result = validate_ticket({"scenario": "CACHE_TEST", "selection": [candidate]}, 1)
        self.assertEqual(result["selection"][0]["betpawa_url"],
                         "https://www.betpawa.cm/event/36682856?filter=all")
        self.assertEqual(result["selection"][0]["betpawa_url_source"], "scraping_cache")

    @_sous_horloge
    def test_url_not_resolved_when_cache_entry_is_not_certain_or_date_differs(self):
        base = {"home_source": "Toronto", "away_source": "Montreal", "date": "2026-10-10", "confidence": "certain",
                "event_id": "https://www.betpawa.cm/event/36682856?filter=all"}
        cas = {
            "incertain": {"toronto||montreal||2026-10-10": {**base, "confidence": "probable"}},
            "autre_date": {"toronto||montreal||2026-10-10": {**base, "date": "2026-10-11"}},
            "autre_equipe": {"toronto||montreal||2026-10-10": {**base, "away_source": "Chicago"}},
        }
        for nom, cache in cas.items():
            candidate = leg(home="Toronto", away="Montreal")
            candidate["date"], candidate["betpawa_url"] = "2026-10-10", None
            with mock.patch("betpawa_validation._load_betpawa_cache", return_value=cache):
                result = validate_ticket({"selection": [candidate]}, 1)
            self.assertEqual(result["selection"][0]["betpawa_url"], "", nom)
            self.assertEqual(result["selection"][0]["betpawa_url_source"], "missing", nom)

    @_sous_horloge
    def test_pool_candidates_are_wrapped_for_review(self):
        manifest = build_manifest({"pool": [leg()]})
        self.assertEqual(manifest["tickets_checked"], 1)
        self.assertEqual(manifest["tickets"][0]["scenario"], "POOL_CANDIDATE")
        self.assertEqual(manifest["tickets"][0]["status"], "READY_FOR_REVIEW")

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

    def test_real_generator_file_is_accepted_without_modifying_it(self):
        source = Path(__file__).resolve().parents[1] / "data" / "tickets.json"
        self.assertTrue(source.is_file(), "data/tickets.json must exist for integration test")
        original = json.loads(source.read_text(encoding="utf-8"))
        intact = copy.deepcopy(original)
        scenarios = original["scenarios"]
        # Le fichier est réécrit chaque nuit et le cache BetPawa ne garde que les matchs à venir : l'horloge est donc
        # figée à la génération du fichier et le cache est synthétique (une entrée certaine par jambe sans adresse).
        genere = datetime.fromisoformat(original["genere_le"])
        cache = {}
        for sc in scenarios:
            for l in sc["selection"]:
                if not (l.get("betpawa_url") or "").startswith("https://www.betpawa.cm/event/"):
                    cle = f"{_cache_team_name(l['domicile'])}||{_cache_team_name(l['exterieur'])}||{l['date']}"
                    cache[cle] = {"home_source": l["domicile"], "away_source": l["exterieur"], "date": l["date"],
                                  "confidence": "certain", "event_id": f"https://www.betpawa.cm/event/{len(cache) + 1}?filter=all"}
        # Une jambe sans adresse, retrouvée dans le cache : prouve la récupération quelle que soit la donnée du jour.
        premiere = scenarios[0]["selection"][0]
        premiere["betpawa_url"] = None
        cle = f"{_cache_team_name(premiere['domicile'])}||{_cache_team_name(premiere['exterieur'])}||{premiere['date']}"
        cache[cle] = {"home_source": premiere["domicile"], "away_source": premiere["exterieur"], "date": premiere["date"],
                      "confidence": "certain", "event_id": "https://www.betpawa.cm/event/1?filter=all"}
        with _horloge(genere), mock.patch("betpawa_validation._load_betpawa_cache", return_value=cache):
            manifest = build_manifest(original)
            # Horloge après tous les matchs : tout coup d'envoi est expiré, donc chaque ticket doit être rejeté.
            with _horloge(datetime(2030, 1, 1, tzinfo=ZoneInfo("Africa/Douala"))):
                tard = build_manifest(original)
        # The real file contains both the assembled scenarios and a candidate pool. The gateway must validate the
        # assembled scenarios first, not silently reinterpret every pool item as a ticket.
        self.assertEqual(manifest["tickets_requested"], len(scenarios))
        self.assertEqual(manifest["tickets_checked"], min(15, len(scenarios)))
        self.assertEqual(
            [t["selection_count"] for t in manifest["tickets"]],
            [len(s["selection"]) for s in scenarios[:15]],
        )
        self.assertTrue(all(t["human_validation_required"] for t in manifest["tickets"]))
        self.assertTrue(all(not t["submission_automated"] for t in manifest["tickets"]))
        self.assertTrue(all(
            leg["betpawa_url"].startswith("https://www.betpawa.cm/event/")
            for ticket in manifest["tickets"] for leg in ticket["selection"]
        ), "All real generator selections should resolve to existing scraper URLs")
        self.assertTrue(any(
            leg["betpawa_url_source"] == "scraping_cache"
            for ticket in manifest["tickets"] for leg in ticket["selection"]
        ), "Missing ticket URLs must be recovered from the verified scraping cache")
        self.assertTrue(all(t["status"] == "REJECTED" for t in tard["tickets"]))
        self.assertEqual(
            [s["selection"][1:] for s in original["scenarios"]], [s["selection"][1:] for s in intact["scenarios"]],
            "le validateur ne doit jamais modifier les jambes du fichier")

    def test_daily_cap_is_fifteen(self):
        raw = {"tickets": [{"selection": [leg(home=f"Home {i}", away=f"Away {i}")]} 
                            for i in range(20)]}
        manifest = build_manifest(raw)
        self.assertEqual(manifest["tickets_checked"], 15)
        self.assertEqual(manifest["max_tickets_per_day"], 15)


if __name__ == "__main__":
    unittest.main()
