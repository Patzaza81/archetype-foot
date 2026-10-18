from __future__ import annotations

import json
from pathlib import Path

from matrice_scenarios.core import (
    build_features, evaluate_scenario, load_dataset, run_experiment,
    scenario_matches, validate_record,
)


def record(i, date, hg, ag, *, hr=5, ar=12, home_history=None, away_history=None):
    return {
        "match_id": f"m{i}", "date": date, "league": "Ligue Test",
        "home_team": f"Home{i}", "away_team": f"Away{i}",
        "home_goals": hg, "away_goals": ag, "home_rank": hr, "away_rank": ar,
        "home_odds": 1.8, "draw_odds": 3.2, "away_odds": 4.2,
        "home_history": home_history or [], "away_history": away_history or [],
    }


def history(date, gf, ga, venue="home"):
    return {"date": date, "goals_for": gf, "goals_against": ga, "venue": venue}


def test_rejects_missing_or_invalid_score():
    ok, reason = validate_record({"match_id": "x", "date": "2026-01-01", "home_team": "A", "away_team": "B"})
    assert not ok and reason == "SCORE_ABSENT_OU_INVALIDE"


def test_features_exclude_same_day_and_future_history():
    r = record(1, "2026-03-10", 1, 0, home_history=[
        history("2026-03-09", 2, 0), history("2026-03-10", 0, 4), history("2026-03-11", 0, 5)
    ])
    f = build_features(r)
    assert f["home_history_n"] == 1
    assert f["home_gf_avg_2"] == 2


def test_rank_gap_sign_is_documented():
    f = build_features(record(1, "2026-03-10", 1, 0, hr=3, ar=11))
    assert f["rank_gap"] == 8
    assert f["rank_gap_abs"] == 8


def test_scenario_conditions_are_composable():
    f = build_features(record(1, "2026-03-10", 1, 0, hr=3, ar=11))
    s = {"conditions": [
        {"feature": "rank_gap", "op": "ge", "value": 5},
        {"feature": "home_odds", "op": "le", "value": 2},
    ]}
    assert scenario_matches(f, s)


def test_loader_deduplicates_and_rejects_conflicting_scores(tmp_path):
    rows = [record(1, "2026-01-01", 1, 0), record(1, "2026-01-01", 1, 0),
            record(2, "2026-01-02", 0, 0), record(2, "2026-01-02", 3, 0)]
    p = tmp_path / "data.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    clean, diag = load_dataset(p)
    assert [r["match_id"] for r in clean] == ["m1"]
    assert diag["duplicate_rows"] == 2
    assert diag["conflicting_match_ids"] == 1


def test_evaluation_never_invents_odds():
    rows = [record(i, f"2026-01-{i:02d}", 1, 0) for i in range(1, 6)]
    features = {r["match_id"]: build_features(r) for r in rows}
    s = {"scenario_id": "s", "target": "home_win", "conditions": [
        {"feature": "home_odds", "op": "le", "value": 2}
    ]}
    result = evaluate_scenario(s, rows, features)
    assert result["n"] == 5 and result["roi"] is None and result["roi_n"] == 0


def test_experiment_is_read_only_and_chronological():
    rows = []
    for i in range(1, 61):
        rows.append(record(i, f"2026-{1 + (i-1)//28:02d}-{1 + (i-1)%28:02d}", int(i % 3 != 0), int(i % 4 == 0)))
    report = run_experiment(rows, max_candidates=100)
    assert report["mode"] == "EXPERIMENTAL_READ_ONLY"
    assert report["dataset"]["train_n"] + report["dataset"]["validation_n"] + report["dataset"]["test_n"] == 60
    assert report["rules"]["auto_promotion"] is False
    assert all(c["promotion_allowed"] is False for c in report["candidates"])
