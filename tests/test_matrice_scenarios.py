from __future__ import annotations

import gzip
import json
from pathlib import Path

from matrice_scenarios.core import (
    DEFAULT_MAX_CANDIDATES, build_features, discover_scenarios, evaluate_scenario, load_dataset,
    prematch_timing_issue, run_experiment, scenario_matches, validate_record, walk_forward,
    _split_chronologically, _wilson, _bh_adjust, _binomial_p_approx,
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
    for i in range(1, 121):
        r = record(i, f"2026-{1 + (i-1)//28:02d}-{1 + (i-1)%28:02d}",
                   int(i % 3 != 0), int(i % 4 == 0), hr=1 + i % 20, ar=1 + (i * 7) % 20)
        r["home_odds"] = 1.25 + (i % 10) * 0.1
        rows.append(r)
    report = run_experiment(rows, max_candidates=100)
    assert report["mode"] == "EXPERIMENTAL_READ_ONLY"
    assert report["scenarios_tested"] > 0
    assert report["dataset"]["train_n"] + report["dataset"]["validation_n"] + report["dataset"]["test_n"] == 120
    assert report["rules"]["auto_promotion"] is False
    assert all(c["promotion_allowed"] is False for c in report["candidates"])



def test_loads_resolved_archive_test_records_without_inventing_odds(tmp_path):
    match = {
        "match_id": "archive-1", "date": "2026-03-10", "competition": "Ligue Test",
        "domicile": "Alpha", "exterieur": "Beta",
        "coup_d_envoi_utc": "2026-03-10T18:00:00Z", "run": {"pris_le": "2026-03-10T09:00:00Z"},
        "score": {"buts_dom": 2, "buts_ext": 1},
        "equipe_dom": {"statut": "OK", "rang": 3, "classement_horodatage": "2026-03-10T08:00:00.123456+00:00", "matchs": [
            {"date": "2026-03-09", "buts_marques": 1, "buts_encaisses": 0, "domicile": False},
            {"date": "2026-03-10", "buts_marques": 9, "buts_encaisses": 0, "domicile": True},
        ]},
        "equipe_ext": {"statut": "OK", "rang": 8, "classement_horodatage": "2026-03-10T19:00:00Z", "matchs": []},
        "cotes_betpawa": {"1x2": {"1": 1.7, "N": 3.2, "2": 4.1},
                          "double_chance": {"1N": 1.25, "N2": 2.1},
                          "btts": {"Oui": 1.9},
                          "over_under_2.5": {"moins": 1.6, "plus": 2.3}},
        "cotes_observees": {"label_inconnu": 1.4},
    }
    path = tmp_path / "2026-03-10.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump({"archive-1": match}, stream)
    rows, diag = load_dataset(tmp_path)
    assert len(rows) == 1
    assert rows[0]["home_goals"] == 2
    assert rows[0]["home_history"][0]["venue"] == "away"
    assert len(rows[0]["home_history"]) == 2  # filtre temporel appliqué par build_features
    features = build_features(rows[0])
    assert features["home_history_n"] == 1
    assert features["home_odds"] == 1.7
    assert rows[0]["target_odds"]["home_not_lose"] == 1.25
    assert rows[0]["target_odds"]["both_score"] == 1.9
    assert rows[0]["target_odds"]["under_2_5"] == 1.6
    assert diag["archive_unresolved_or_missing_score"] == 0
    # Le classement du domicile est horodaté avant le coup d'envoi (gardé) ; celui de l'extérieur
    # l'est après (écarté : pas de classement plutôt qu'un classement non prouvé).
    assert rows[0]["home_rank"] == 3 and rows[0]["away_rank"] is None



def test_head_to_head_uses_only_exact_names_and_prior_matches():
    r = record(1, "2026-03-10", 1, 0, home_history=[
        {"date": "2026-03-01", "goals_for": 2, "goals_against": 1, "venue": "home", "opponent": "Away1"}
    ], away_history=[
        {"date": "2026-03-02", "goals_for": 0, "goals_against": 1, "venue": "away", "opponent": "Home1"}
    ])
    f = build_features(r)
    assert f["h2h_n"] == 2
    assert f["h2h_home_score_rate"] == 100
    assert f["h2h_home_not_lose_rate"] == 100



# ---------------------------------------------------------------------------------------------
# Preuve pré-match, doublons, découpe, exploration, métriques, absence de fuite
# ---------------------------------------------------------------------------------------------

def archive_match(match_id, date, hg=1, ag=0, *, kickoff="X", snapshot="2026-03-10T09:00:00Z", home="Alpha", away="Beta"):
    item = {
        "match_id": match_id, "date": date, "competition": "Ligue Test", "domicile": home, "exterieur": away,
        "score": {"buts_dom": hg, "buts_ext": ag},
        "equipe_dom": {"statut": "OK", "matchs": []}, "equipe_ext": {"statut": "OK", "matchs": []},
        "cotes_betpawa": {"1x2": {"1": 1.7, "N": 3.2, "2": 4.1}},
    }
    if kickoff != "X":
        item["coup_d_envoi_utc"] = kickoff
    else:
        item["coup_d_envoi_utc"] = f"{date}T18:00:00Z"
    if snapshot is not None:
        item["run"] = {"pris_le": snapshot}
    return item


def write_archive(tmp_path, *items):
    by_file = {}
    for item in items:
        by_file.setdefault(item["date"], {})
        by_file[item["date"]][f'{item["match_id"]}@{len(by_file[item["date"]])}'] = item
    for day, content in by_file.items():
        with gzip.open(tmp_path / f"{day}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(content, stream)


def test_timing_proof_accepts_captures_strictly_before_kickoff():
    base = {"snapshot_at": "2026-03-10T09:00:00Z", "kickoff_at": "2026-03-10T18:00:00Z"}
    assert prematch_timing_issue(base) is None
    assert prematch_timing_issue({"snapshot_at": "2026-03-10T17:59:59+00:00", "kickoff_at": "2026-03-10T18:00:00Z"}) is None
    assert prematch_timing_issue({"snapshot_at": "2026-03-10T10:00:00.5+01:00", "kickoff_at": "2026-03-10T18:00:00Z"}) is None


def test_timing_proof_rejects_unprovable_or_late_captures():
    assert prematch_timing_issue({"snapshot_at": "2026-03-10T18:00:00Z", "kickoff_at": "2026-03-10T18:00:00Z"}) == "CAPTURE_APRES_COUP_D_ENVOI"
    assert prematch_timing_issue({"snapshot_at": "2026-03-10T20:00:00Z", "kickoff_at": "2026-03-10T18:00:00Z"}) == "CAPTURE_APRES_COUP_D_ENVOI"
    assert prematch_timing_issue({"snapshot_at": "2026-03-10T09:00:00Z", "kickoff_at": None}) == "COUP_D_ENVOI_ABSENT"
    assert prematch_timing_issue({"snapshot_at": None, "kickoff_at": "2026-03-10T18:00:00Z"}) == "CAPTURE_SANS_HORODATAGE"
    assert prematch_timing_issue({"snapshot_at": "pas une date", "kickoff_at": "2026-03-10T18:00:00Z"}) == "CAPTURE_SANS_HORODATAGE"


def test_archive_loader_excludes_captures_without_pre_match_proof(tmp_path):
    write_archive(
        tmp_path,
        archive_match("ok", "2026-03-10"),
        archive_match("tard", "2026-03-10", snapshot="2026-03-10T19:00:00Z"),
        archive_match("sans-coup-d-envoi", "2026-03-10", kickoff=None),
        archive_match("sans-capture", "2026-03-10", snapshot=None),
    )
    rows, diag = load_dataset(tmp_path)
    assert [r["match_id"] for r in rows] == ["ok"]
    assert diag["rejected"] == {"CAPTURE_APRES_COUP_D_ENVOI": 1, "COUP_D_ENVOI_ABSENT": 1, "CAPTURE_SANS_HORODATAGE": 1}


def test_same_match_listed_two_days_keeps_the_pre_kickoff_copy(tmp_path):
    # Cas réel : même match_id, même score, date décalée d'un jour ; la copie du 03 a été capturée
    # après le coup d'envoi, celle du 04 avant.
    write_archive(
        tmp_path,
        archive_match("x", "2026-10-03", kickoff="2026-10-03T02:00:00Z", snapshot="2026-10-03T11:33:00Z"),
        archive_match("x", "2026-10-04", kickoff="2026-10-04T02:00:00Z", snapshot="2026-10-04T00:07:00Z"),
    )
    rows, diag = load_dataset(tmp_path)
    assert len(rows) == 1 and rows[0]["date"] == "2026-10-04"
    assert diag["conflicting_match_ids"] == 0 and diag["rejected"] == {"CAPTURE_APRES_COUP_D_ENVOI": 1}


def test_identical_copies_with_shifted_dates_keep_latest_pre_kickoff_snapshot(tmp_path):
    write_archive(
        tmp_path,
        archive_match("x", "2026-10-03", kickoff="2026-10-03T20:00:00Z", snapshot="2026-10-03T09:00:00Z"),
        archive_match("x", "2026-10-04", kickoff="2026-10-04T20:00:00Z", snapshot="2026-10-04T09:00:00Z"),
    )
    rows, diag = load_dataset(tmp_path)
    assert len(rows) == 1 and rows[0]["date"] == "2026-10-04"
    assert diag["duplicate_rows"] == 1 and diag["date_shifted_duplicates"] == 1 and diag["conflicting_match_ids"] == 0


def test_duplicates_with_different_score_or_teams_stay_contradictory(tmp_path):
    write_archive(
        tmp_path,
        archive_match("score", "2026-10-03", 1, 0), archive_match("score", "2026-10-04", 2, 0),
        archive_match("equipes", "2026-10-03", home="A", away="B"), archive_match("equipes", "2026-10-04", home="A", away="C"),
    )
    rows, diag = load_dataset(tmp_path)
    assert rows == [] and diag["conflicting_match_ids"] == 2 and diag["rejected"]["DOUBLON_CONTRADICTOIRE"] == 4


def test_untimed_source_with_different_dates_is_still_contradictory(tmp_path):
    rows = [record(1, "2026-01-01", 1, 0), record(1, "2026-01-02", 1, 0)]
    for r in rows:
        r["home_team"], r["away_team"] = "H", "A"
    p = tmp_path / "data.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    clean, diag = load_dataset(p)
    assert clean == [] and diag["conflicting_match_ids"] == 1


def _dated_rows(days, per_day):
    rows = []
    for d in range(days):
        for k in range(per_day):
            i = d * per_day + k
            rows.append(record(i, f"2026-03-{d + 1:02d}", i % 3, i % 2))
    return rows


def test_split_never_shares_a_day_between_segments():
    rows = _dated_rows(days=12, per_day=7)
    train, validation, test = _split_chronologically(rows)
    assert len(train) + len(validation) + len(test) == len(rows)
    days = [{r["date"] for r in part} for part in (train, validation, test)]
    assert not (days[0] & days[1]) and not (days[1] & days[2]) and not (days[0] & days[2])
    assert max(days[0]) < min(days[1]) and max(days[1]) < min(days[2])
    assert 0.5 <= len(train) / len(rows) <= 0.7


def test_split_aligns_on_the_closest_date_boundary():
    # 60 % et 80 % tombent au milieu de la journée 2 : avec trois dates, la seule découpe sans jour partagé est 10/80/10.
    rows = [record(i, "2026-03-01", 1, 0) for i in range(10)] + [record(100 + i, "2026-03-02", 1, 0) for i in range(80)] \
        + [record(200 + i, "2026-03-03", 1, 0) for i in range(10)]
    train, validation, test = _split_chronologically(rows)
    assert (len(train), len(validation), len(test)) == (10, 80, 10)
    # Avec davantage de dates, le couple de frontières le plus proche de 60 %/80 % est choisi.
    rows = [record(i, f"2026-03-{1 + i // 10:02d}", 1, 0) for i in range(100)]
    train, validation, test = _split_chronologically(rows)
    assert (len(train), len(validation), len(test)) == (60, 20, 20)


def test_split_falls_back_to_rank_when_fewer_than_three_dates():
    rows = [record(i, "2026-03-01", 1, 0) for i in range(20)]
    train, validation, test = _split_chronologically(rows)
    assert (len(train), len(validation), len(test)) == (12, 4, 4)


def _rich_rows(n=240, seed=3):
    import random
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        day = i // 8
        date = f"2026-{1 + day // 28:02d}-{1 + day % 28:02d}"
        hist = lambda: [{"date": f"2025-{m:02d}-15", "goals_for": rng.randint(0, 3), "goals_against": rng.randint(0, 3),
                         "venue": rng.choice(["home", "away"])} for m in range(1, 9)]
        r = record(i, date, rng.randint(0, 3), rng.randint(0, 3), hr=rng.randint(1, 20), ar=rng.randint(1, 20),
                   home_history=hist(), away_history=hist())
        r["home_odds"], r["draw_odds"], r["away_odds"] = rng.uniform(1.3, 4), rng.uniform(2.8, 4), rng.uniform(1.5, 6)
        r["target_odds"] = {"home_win": r["home_odds"], "draw": r["draw_odds"], "away_win": r["away_odds"]}
        rows.append(r)
    return rows


def test_discovery_is_deterministic_and_respects_the_budget():
    rows = _rich_rows()
    train = rows[:150]
    fmap = {r["match_id"]: build_features(r) for r in train}
    first = discover_scenarios(train, fmap, max_candidates=600)
    second = discover_scenarios(train, fmap, max_candidates=600)
    assert first == second and 0 < len(first) <= 600
    counts = {c: sum(s["complexity"] == c for s in first) for c in (1, 2, 3)}
    assert counts[1] <= 240 and counts[2] <= 240 and counts[3] <= 120
    assert all(s["discovery_support"] >= 30 for s in first)


def test_pairs_and_triples_are_spread_over_many_conditions_not_one_anchor():
    rows = _rich_rows()
    train = rows[:150]
    fmap = {r["match_id"]: build_features(r) for r in train}
    found = discover_scenarios(train, fmap, max_candidates=3000)
    for complexity in (2, 3):
        rules = {json.dumps(s["conditions"], sort_keys=True): s["conditions"] for s in found if s["complexity"] == complexity}
        assert len(rules) >= 20
        usage = {}
        for conds in rules.values():
            for c in conds:
                usage[json.dumps(c, sort_keys=True)] = usage.get(json.dumps(c, sort_keys=True), 0) + 1
        assert max(usage.values()) / len(rules) < 0.35  # avant correction : 100 % des paires partageaient une condition
        assert len({c["feature"] for conds in rules.values() for c in conds}) >= 15


def test_discovery_reads_only_the_discovery_rows():
    rows = _rich_rows()
    train = rows[:150]
    fmap = {r["match_id"]: build_features(r) for r in rows}
    base = discover_scenarios(train, fmap, max_candidates=400)
    altered = {}
    for r in rows[150:]:
        altered[r["match_id"]] = {**fmap[r["match_id"]], "home_gf_avg_3": 999.0, "home_odds": 1.01}
    other = discover_scenarios(train, {**fmap, **altered}, max_candidates=400)
    assert base == other


def test_wilson_interval_matches_reference_values():
    lo, hi = _wilson(8, 10)
    assert round(lo, 4) == 0.4902 and round(hi, 4) == 0.9433
    lo, hi = _wilson(0, 10)
    assert lo == 0.0 and round(hi, 4) == 0.2775
    assert _wilson(0, 0) == (None, None)


def test_evaluation_reports_roi_mean_odds_market_edge_and_settled_bets():
    rows = []
    for i, (hg, ag) in enumerate([(1, 0), (2, 1), (0, 0), (0, 2)]):
        r = record(i + 1, f"2026-01-{i + 1:02d}", hg, ag)
        r["target_odds"] = {"home_win": 2.0}
        r["home_odds"], r["draw_odds"], r["away_odds"] = 2.0, 4.0, 4.0  # 1/2 + 1/4 + 1/4 = 1 : marge nulle
        rows.append(r)
    rows[3]["target_odds"] = {}  # une cote absente n'est jamais remplacée
    features = {r["match_id"]: build_features(r) for r in rows}
    s = {"scenario_id": "s", "target": "home_win", "conditions": [{"feature": "home_odds", "op": "le", "value": 2}]}
    result = evaluate_scenario(s, rows, features)
    assert result["n"] == 4 and result["wins"] == 2
    assert result["settled_bets"] == 3 and result["roi_n"] == 3
    assert result["mean_odds"] == 2.0
    assert abs(result["roi"] - ((1.0 + 1.0 - 1.0) / 3)) < 1e-12  # deux gagnés à 2.0 (+1), un perdu (-1)
    assert abs(result["hit_rate_with_odds"] - 2 / 3) < 1e-12
    assert result["market_implied_basis"] == "1x2_sans_marge" and abs(result["market_implied_rate"] - 0.5) < 1e-12
    assert abs(result["edge_vs_market"] - (2 / 3 - 0.5)) < 1e-12
    assert result["roi_ci95"][0] < result["roi"] < result["roi_ci95"][1]


def test_market_probability_for_non_1x2_targets_keeps_the_bookmaker_margin():
    r = record(1, "2026-01-01", 2, 1)
    r["target_odds"] = {"both_score": 1.8}
    features = {r["match_id"]: build_features(r)}
    s = {"scenario_id": "s", "target": "both_score", "conditions": [{"feature": "home_odds", "op": "ge", "value": 1}]}
    result = evaluate_scenario(s, [r], features)
    assert result["market_implied_basis"] == "brute_avec_marge" and abs(result["market_implied_rate"] - 1 / 1.8) < 1e-12
    assert result["roi_ci95"] is None  # un seul pari : pas d'intervalle inventé


def test_features_ignore_final_score_and_future_matches():
    base = record(1, "2026-03-10", 3, 1, home_history=[history("2026-03-01", 1, 0), history("2026-03-05", 0, 2, "away")],
                  away_history=[history("2026-03-02", 2, 2)])
    reference = build_features(base)
    altered = {**base, "home_goals": 0, "away_goals": 9}
    altered["home_history"] = base["home_history"] + [history("2026-03-10", 7, 0), history("2026-03-20", 0, 8)]
    altered["away_history"] = base["away_history"] + [history("2026-03-11", 5, 5)]
    assert build_features(altered) == reference


def test_selection_and_discovery_never_depend_on_test_outcomes():
    rows = _rich_rows(n=320)
    first = run_experiment(rows, max_candidates=800)
    last_days = sorted({r["date"] for r in rows})[-6:]
    flipped = [({**r, "home_goals": 5 - r["home_goals"] % 4, "away_goals": 3 - r["away_goals"] % 3} if r["date"] in last_days else r)
               for r in rows]
    second = run_experiment(flipped, max_candidates=800)
    assert first["dataset"]["test_n"] == second["dataset"]["test_n"] and first["dataset"]["split_dates"] == second["dataset"]["split_dates"]
    ids = lambda rep: sorted(c["scenario"]["scenario_id"] for c in rep["candidates"])
    assert ids(first) == ids(second)
    chosen = lambda rep: sorted(c["scenario"]["scenario_id"] for c in rep["candidates"] if c["selected_on_validation"])
    assert chosen(first) == chosen(second)


def test_report_exposes_exploration_selection_and_stays_read_only():
    report = run_experiment(_rich_rows(n=320), max_candidates=800)
    assert report["dataset"]["days_shared_between_splits"] == 0
    assert report["exploration"]["by_complexity"]["3"]["distinct_rules"] > 0
    assert report["selection"]["criteria"]["train_q_bh_max"] == 0.10
    assert report["selection"]["selected"] == sum(c["selected_on_validation"] for c in report["candidates"])
    assert all(c["promotion_allowed"] is False for c in report["candidates"])
    assert report["rules"]["auto_promotion"] is False and report["rules"]["production_changes"] is False
    assert DEFAULT_MAX_CANDIDATES >= 5000
    assert any("match_ids" in c["train"] for c in report["candidates"][:5])
    assert all("match_ids" not in c["train"] for c in report["candidates"][250:])


def test_walk_forward_folds_have_disjoint_chronological_tests():
    result = walk_forward(_rich_rows(n=400), max_candidates=400)
    spans = [fold["test_days"] for fold in result["folds"]]
    assert len(spans) == 3 and all(spans)
    assert spans[0][1] < spans[1][0] and spans[1][1] < spans[2][0]
    assert all(fold["split"]["test_n"] > 0 for fold in result["folds"])


def test_dynamic_venue_and_scoring_in_losses_features():
    # Dernier match à l'extérieur après deux autres déplacements : « retour à domicile » après série à l'extérieur.
    r = record(1, "2026-03-20", 1, 0, home_history=[
        history("2026-03-01", 2, 0, "home"), history("2026-03-06", 1, 2, "away"),
        history("2026-03-12", 0, 3, "away"), history("2026-03-16", 1, 2, "away"),
    ])
    f = build_features(r)
    assert f["home_last_venue_away"] == 1 and f["home_last_venue_home"] == 0
    assert f["home_away_streak"] == 3 and f["home_home_streak"] == 0
    assert f["home_after_away_loss"] == 1 and f["home_loss_streak"] == 3
    assert f["home_loss_count_5"] == 3
    assert abs(f["home_score_in_loss_rate_5"] - 2 / 3 * 100) < 1e-9  # a marqué dans 2 des 3 défaites
    assert f["home_score_streak"] == 1  # le 0-3 interrompt la série de matchs avec but
    s = {"conditions": [{"feature": "home_away_streak", "op": "ge", "value": 2},
                        {"feature": "home_last_venue_away", "op": "ge", "value": 1},
                        {"feature": "home_score_in_loss_rate_5", "op": "ge", "value": 60}]}
    assert scenario_matches(f, s)


def test_venue_features_are_absent_when_venue_is_unknown_or_no_loss():
    r = record(1, "2026-03-20", 1, 0, home_history=[
        {"date": "2026-03-01", "goals_for": 2, "goals_against": 0},  # pas de lieu : rien n'est deviné
        {"date": "2026-03-06", "goals_for": 1, "goals_against": 0},
    ])
    f = build_features(r)
    assert not any("last_venue" in k or k.endswith("_away_streak") for k in f)
    assert f["home_loss_count_5"] == 0 and "home_score_in_loss_rate_5" not in f


def test_benjamini_hochberg_matches_reference_values():
    adjusted = _bh_adjust([0.01, 0.04, 0.03, 0.005])
    assert [round(x, 6) for x in adjusted] == [0.02, 0.04, 0.04, 0.02]
    assert _bh_adjust([]) == []
    assert all(0 <= q <= 1 for q in _bh_adjust([0.9, 0.95, 1.0]))


def test_normal_p_value_approximation_is_close_to_the_exact_normal_tail():
    assert abs(_binomial_p_approx(60, 100, 0.5) - 0.0455) < 0.002   # z = 2
    assert abs(_binomial_p_approx(50, 100, 0.5) - 1.0) < 0.001      # z = 0
    assert _binomial_p_approx(10, 0, 0.5) == 1.0 and _binomial_p_approx(10, 50, 1.0) == 1.0
