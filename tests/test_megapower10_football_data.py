import csv
import tempfile
import unittest
from pathlib import Path

from megapower10.football_data import load_football_data
from megapower10.core import evaluate, discovery_report, odds_band


class TestFootballDataAdapter(unittest.TestCase):
    def test_opening_closing_prices_and_settlement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "snapshots" / "2526" / "raw"
            root.mkdir(parents=True)
            path = root / "E0.csv"
            fields = ["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
                      "B365H", "B365D", "B365A", "B365CH", "B365CD", "B365CA",
                      "B365>2.5", "B365<2.5", "B365C>2.5", "B365C<2.5", "P>2.5", "P<2.5", "PC>2.5", "PC<2.5",
                      "MaxH", "MaxD", "MaxA", "AvgH", "AvgD", "AvgA"]
            row = {"Div": "E0", "Date": "01/08/2025", "HomeTeam": "A", "AwayTeam": "B",
                   "FTHG": "0", "FTAG": "3", "FTR": "A",
                   "B365H": "4.0", "B365D": "3.5", "B365A": "1.8",
                   "B365CH": "5.0", "B365CD": "3.8", "B365CA": "1.6",
                   "B365>2.5": "2.1", "B365<2.5": "1.7",
                   "B365C>2.5": "1.9", "B365C<2.5": "1.8",
                   "P>2.5": "2.0", "P<2.5": "1.75", "PC>2.5": "1.9", "PC<2.5": "1.85",
                   "MaxH": "99", "MaxD": "99", "MaxA": "99",
                   "AvgH": "99", "AvgD": "99", "AvgA": "99"}
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            prices, summary = load_football_data(Path(tmp))
            away_open = next(q for q in prices if q.market == "1X2" and q.selection == "A" and q.price_stage == "opening")
            self.assertEqual(away_open.odds, 1.8)
            self.assertTrue(away_open.result)
            home_open = next(q for q in prices if q.market == "1X2" and q.selection == "H" and q.price_stage == "opening")
            self.assertFalse(home_open.result)
            over = next(q for q in prices if q.market == "total_2_5" and q.selection == "over_2_5")
            self.assertTrue(over.result)
            pinnacle_over = next(q for q in prices if q.bookmaker == "Pinnacle" and q.market == "total_2_5" and q.selection == "over_2_5" and q.price_stage == "opening")
            self.assertEqual(pinnacle_over.odds, 2.0)
            self.assertNotIn(99.0, [q.odds for q in prices])
            self.assertEqual(summary["price_stages"], ["closing", "opening"])
            self.assertEqual(summary["events"], 1)
            self.assertEqual(evaluate(prices, min_odds=1.01)["overall"]["n"], len(prices))
            self.assertEqual(discovery_report(prices, min_support=1)["groups"], len({(q.competition, q.market, q.price_stage, odds_band(q.odds)) for q in prices}))


if __name__ == "__main__":
    unittest.main()
