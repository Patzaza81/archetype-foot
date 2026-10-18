from matrice_scenarios import croisements as C


def hist(venue, rows):
    return [{"date": d, "goals_for": gf, "goals_against": ga, "venue": venue} for d, gf, ga in rows]


def rec(home, away, day="2026-05-01"):
    return {"date": day, "home_history": home, "away_history": away}


FOUR_H = hist("home", [("2026-01-01", 2, 0), ("2026-01-08", 1, 1), ("2026-01-15", 0, 2), ("2026-01-22", 3, 1)])
FOUR_A = hist("away", [("2026-01-02", 0, 1), ("2026-01-09", 1, 1), ("2026-01-16", 2, 2), ("2026-01-23", 0, 3)])


def test_needs_four_same_venue_matches():
    assert C.scores(rec(FOUR_H, FOUR_A)) is not None
    assert C.scores(rec(FOUR_H[:3], FOUR_A)) is None
    assert C.scores(rec(FOUR_H, FOUR_A[:3])) is None
    assert C.scores(rec(FOUR_H + hist("away", [("2026-02-01", 1, 1)]), FOUR_A)) is not None  # un match à l'extérieur ne compte pas pour le domicile
    assert C.scores(rec(hist("away", [("2026-01-0%d" % i, 1, 1) for i in range(1, 6)]), FOUR_A)) is None
    assert C.scores(rec([], [])) is None


def test_never_uses_same_day_or_future_matches():
    base = C.scores(rec(FOUR_H, FOUR_A, "2026-05-01"))
    polluted_h = FOUR_H + hist("home", [("2026-05-01", 9, 9), ("2026-06-01", 9, 9)])
    polluted_a = FOUR_A + hist("away", [("2026-05-01", 9, 0), ("2026-07-01", 9, 0)])
    assert C.scores(rec(polluted_h, polluted_a, "2026-05-01")) == base
    assert C.scores(rec(polluted_h, polluted_a, "2026-05-02")) != base  # le lendemain, le match de la veille compte


def test_scores_signs_and_formulas():
    s = C.scores(rec(FOUR_H, FOUR_A))
    assert s["over_2_5"] == -s["under_2_5"] and s["home_win"] == -s["away_win"] and s["draw"] <= 0
    assert s["home_scores_1plus"] == 0.75 + 1.0  # domicile marque 3/4 ; extérieur encaisse 4/4
    assert abs(s["home_win"] - ((6 / 4 - 4 / 4) - (3 / 4 - 7 / 4))) < 1e-12


def test_wilson_interval():
    lo, hi = C.wilson(50, 100)
    assert lo < 0.5 < hi and 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    assert C.wilson(0, 0) is None
