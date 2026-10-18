import json

import pytest

from matrice_scenarios import analyse_match as A

CAL = json.loads(A.CALIBRATION_FILE.read_text(encoding="utf-8"))


def test_parse_scores_accepts_three_formats_and_rejects_three_bad_ones():
    assert A.parse_scores("1-1,1-2,0-3") == [(1, 1), (1, 2), (0, 3)]
    assert A.parse_scores("1 - 1; 2-0 ;3-3") == [(1, 1), (2, 0), (3, 3)]
    assert A.parse_scores("") == []
    for bad in ("1:1,2-0", "a-b", "1-2-3"):
        with pytest.raises(ValueError):
            A.parse_scores(bad)


def test_requires_three_to_five_matches_per_team():
    ok = [(1, 0), (2, 1), (0, 0)]
    A.analyser(ok, ok, CAL)
    for h, a in (([(1, 0)] * 2, ok), (ok, [(1, 0)] * 2), ([(1, 0)] * 6, ok)):
        with pytest.raises(ValueError):
            A.analyser(h, a, CAL)


def test_strong_home_gets_higher_home_win_probability_than_weak_home():
    strong = A.analyser([(3, 0)] * 4, [(0, 3)] * 4, CAL)["markets"]
    weak = A.analyser([(0, 3)] * 4, [(3, 0)] * 4, CAL)["markets"]
    assert strong["home_win"]["probabilite"] > CAL["markets"]["home_win"]["base_rate"] > weak["home_win"]["probabilite"]
    assert strong["away_win"]["probabilite"] < weak["away_win"]["probabilite"]
    assert strong["over_2_5"]["probabilite"] + strong["under_2_5"]["probabilite"] == pytest.approx(1.0, abs=0.12)


def test_odds_reading_and_small_sample_warning():
    r = A.analyser([(2, 2), (1, 1), (1, 1)], [(2, 1), (0, 2), (2, 2)], CAL, {"home_scores_1plus": 1.01, "draw": 50.0})
    m = r["markets"]
    assert m["home_scores_1plus"]["lecture"] == "cote trop basse" and m["draw"]["lecture"] == "avantage apparent"
    assert m["draw"]["marge_sur_cote_equilibre"] == pytest.approx(50 * m["draw"]["probabilite"] - 1, abs=1e-3)
    assert r["warnings"] and "both_score" in m and "cote_donnee" not in m["both_score"]


def test_calibration_file_is_sane():
    for market, c in CAL["markets"].items():
        assert all(0 < x < 1 for x in c["rate"]) and len(c["rate"]) == len(c["edges"]) + 1 == len(c["n"])
        assert c["out_of_sample"]["brier_model"] <= c["out_of_sample"]["brier_taux_de_base"] + 1e-3, market
    assert CAL["calibration_cutoff_day"] > "2026-01-01" and CAL["markets"]["home_win"]["out_of_sample"]["amelioration_pct"] > 1
