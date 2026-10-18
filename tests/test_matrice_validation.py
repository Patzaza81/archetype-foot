from __future__ import annotations

import ast
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")  # numpy vient avec pandas (requirements.txt) ; sans lui ces tests sont ignorés, pas en erreur
from matrice_scenarios import core, validate as validate_cli, validation as V  # noqa: E402
from matrice_scenarios.football_data import load_football_data  # noqa: E402


# ---------------------------------------------------------------------------------------------
# Jeux synthétiques
# ---------------------------------------------------------------------------------------------

def day_of(i: int, per_day: int = 8, start: date = date(2026, 1, 1)) -> str:
    return (start + timedelta(days=i // per_day)).isoformat()


def synthetic(n=400, seed=0, signal=True, odds=False, per_day=8):
    """Une seule variable informative (`pre_x`). Avec signal, x > 0,5 fait marquer le domicile ; sans signal, le score est indépendant."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        x = rng.random()
        if signal:
            hg = rng.choice([1, 2, 3]) if x > 0.5 else (0 if rng.random() < 0.8 else 1)
        else:
            hg = rng.choice([0, 1, 2])
        ag = rng.choice([0, 1, 2])
        row = {"match_id": f"s{seed}-{i}", "date": day_of(i, per_day), "league": "L", "home_team": f"H{i}", "away_team": f"A{i}",
               "home_goals": hg, "away_goals": ag, "home_history": [], "away_history": [], "prematch_features": {"pre_x": x}}
        if odds:
            row["target_odds"] = {"home_scores_1plus": 1.5, "home_win": 2.0, "draw": 3.0, "away_win": 3.5}
            row["home_odds"], row["draw_odds"], row["away_odds"] = 2.0, 3.0, 3.5
        rows.append(row)
    return rows


def build_arena(rows, *, max_candidates=300, odds=False):
    clean, _ = core._clean_records(rows)
    fm = {str(r["match_id"]): core.build_features(r) for r in clean}
    train, validation, test = core._split_chronologically(clean)
    scenarios = core.discover_scenarios(train, fm, max_candidates=max_candidates)
    return clean, fm, scenarios, V.Arena(clean, fm, scenarios, {"train": train, "validation": validation, "test": test})


def write_football_data(root: Path, rows: list[tuple], *, code="E0", with_odds=True, season="2526"):
    (root / "snapshots" / season / "raw").mkdir(parents=True, exist_ok=True)
    (root / "snapshots" / season / "catalogue.json").write_text(json.dumps(
        {"entries": [{"competition_code": code, "country": "England", "competition": "Premier League"}]}), encoding="utf-8")
    lines = ["Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR" + (",B365H,B365D,B365A" if with_odds else "")]
    for day, home, away, hg, ag in rows:
        d = date.fromisoformat(day)
        lines.append(f"{code},{d.day:02d}/{d.month:02d}/{d.year},15:00,{home},{away},{hg},{ag},H" + (",1.5,3.5,6.0" if with_odds else ""))
    (root / "snapshots" / season / "raw" / f"{code}.csv").write_text("\n".join(lines), encoding="utf-8")


def football_like(tmp_path: Path, days=200, per_day=6, seed=3):
    rng = random.Random(seed)
    teams = [f"T{i}" for i in range(24)]
    rows = []
    start = date(2025, 8, 1)
    for d in range(days):
        day = (start + timedelta(days=d)).isoformat()
        sample = rng.sample(teams, per_day * 2)
        for k in range(per_day):
            rows.append((day, sample[2 * k], sample[2 * k + 1], rng.choice([0, 1, 2, 3]), rng.choice([0, 1, 2])))
    write_football_data(tmp_path, rows)
    return load_football_data(tmp_path)


# ---------------------------------------------------------------------------------------------
# Football-Data : résultats seulement, aucune cote, historique strictement antérieur
# ---------------------------------------------------------------------------------------------

def test_football_data_loader_reads_results_only_and_never_odds(tmp_path):
    write_football_data(tmp_path, [("2026-03-01", "A", "B", 2, 1), ("2026-03-08", "B", "A", 0, 0)], with_odds=True)
    (tmp_path / "normalized" / "2627").mkdir(parents=True)
    (tmp_path / "normalized" / "2627" / "E0.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"competition_code": "E0", "date": "2026-03-01", "home_team": "A", "away_team": "B", "full_time_home_goals": 2, "full_time_away_goals": 1},  # doublon identique
        {"competition_code": "E0", "date": "2026-03-15", "home_team": "A", "away_team": "C", "full_time_home_goals": 1, "full_time_away_goals": 1},
    ]), encoding="utf-8")
    records, diag = load_football_data(tmp_path)
    assert len(records) == 3 and diag["duplicate_rows"] == 1 and diag["conflicting_matches"] == 0
    assert diag["odds_used"] is False
    for r in records:
        assert r["target_odds"] == {} and "home_odds" not in r and "snapshot_at" not in r
        assert core.validate_record(r) == (True, "OK")


def test_football_data_conflicting_duplicates_and_cutoff(tmp_path):
    write_football_data(tmp_path, [("2026-03-01", "A", "B", 2, 1), ("2026-03-08", "B", "A", 0, 0)])
    (tmp_path / "normalized" / "2627").mkdir(parents=True)
    (tmp_path / "normalized" / "2627" / "E0.jsonl").write_text(json.dumps(
        {"competition_code": "E0", "date": "2026-03-01", "home_team": "A", "away_team": "B", "full_time_home_goals": 0, "full_time_away_goals": 3}), encoding="utf-8")
    records, diag = load_football_data(tmp_path)
    assert [r["date"] for r in records] == ["2026-03-08"]
    assert diag["conflicting_matches"] == 1 and diag["rejected"]["DOUBLON_CONTRADICTOIRE"] == 2
    cut, diag2 = load_football_data(tmp_path, until="2026-03-05")
    assert cut == [] and diag2["rejected"]["APRES_DATE_LIMITE"] == 1


def test_football_data_history_is_strictly_before_and_keyed_by_country(tmp_path):
    write_football_data(tmp_path, [
        ("2026-03-01", "A", "B", 2, 0), ("2026-03-08", "A", "C", 1, 0), ("2026-03-08", "D", "A", 5, 5),  # même jour : A joue deux fois (impossible mais ne doit pas fuir)
        ("2026-03-15", "A", "E", 0, 0),
    ])
    records, _ = load_football_data(tmp_path)
    target = next(r for r in records if r["date"] == "2026-03-15")
    features = core.build_features(target)
    assert features["home_history_n"] == 3  # 01/03, et les deux du 08/03 ; aucun match du 15/03 ni après
    first = next(r for r in records if r["date"] == "2026-03-08" and r["home_team"] == "A")
    assert core.build_features(first)["home_history_n"] == 1  # le match du même jour et le futur sont exclus
    assert core.build_features(first)["home_gf_avg_2"] == 2


# ---------------------------------------------------------------------------------------------
# Équivalence avec le code de référence
# ---------------------------------------------------------------------------------------------

def test_vectorized_bh_and_p_value_match_the_reference_implementation():
    rng = random.Random(5)
    p = [round(rng.random(), 3) for _ in range(300)] + [0.0, 1.0, 0.5, 0.5, 0.5]  # ex aequo inclus
    assert np.allclose(V.bh_vec(np.array(p)), core._bh_adjust(p), atol=1e-12)
    wins = np.array([0, 5, 30, 10, 4, 50], dtype=float)
    n = np.array([0, 10, 60, 50, 4, 100], dtype=float)
    base = np.array([0.5, 0.0, 0.5, 1.0, 0.3, 0.45])
    reference = [core._binomial_p_approx(int(w), int(m), b) for w, m, b in zip(wins, n, base)]
    assert np.allclose(V.binomial_p_vec(wins, n, base), reference, atol=1e-12)


def test_vectorized_condition_masks_match_core_semantics():
    rows = [{"x": 1.0, "y": 5.0, "league": "A"}, {"x": 2.0, "league": "B"}, {"y": 3.0, "league": "A"}, {"x": float("nan"), "y": 1.0, "league": "INCONNUE"}]
    columns = V._feature_columns(rows, {"x", "y", "league"})
    conditions = [{"feature": "x", "op": "ge", "value": 1.5}, {"feature": "x", "op": "le", "value": 1.0}, {"feature": "y", "op": "ge", "value": 3},
                  {"feature": "y", "op": "le", "value": 3}, {"feature": "league", "op": "eq", "value": "A"}, {"feature": "x", "op": "gt", "value": 1},
                  {"feature": "x", "op": "lt", "value": 2}, {"feature": "y", "op": "between", "value": [2, 5]}]
    for condition in conditions:
        expected = [core._condition_value(r, condition) for r in rows]
        assert V._condition_mask_np(columns, condition).tolist() == expected, condition


def test_vectorized_selection_equals_run_experiment():
    rng = random.Random(8)
    rows = []
    for i in range(360):
        x, y = rng.random(), rng.random()
        hg = rng.choice([1, 2, 3]) if x > 0.55 else rng.choice([0, 0, 1])
        r = {"match_id": f"e{i}", "date": day_of(i), "league": rng.choice(["L1", "L2"]), "home_team": f"H{i}", "away_team": f"A{i}",
             "home_goals": hg, "away_goals": rng.choice([0, 1, 2]), "home_history": [], "away_history": [],
             "prematch_features": {"pre_x": x, "pre_y": y}, "home_odds": 1.5 + y, "draw_odds": 3.2, "away_odds": 2.5 + x,
             "target_odds": {"home_win": 1.5 + y, "draw": 3.2, "away_win": 2.5 + x, "home_scores_1plus": 1.3 + y / 2}}
        rows.append(r)
    report = core.run_experiment(rows, max_candidates=600, detail_top=0)
    clean, fm, scenarios, arena = build_arena(rows, max_candidates=600)
    selection = arena.select(arena.Y)
    mine = {scenarios[k]["scenario_id"] for k in np.nonzero(selection["selected"])[0]}
    reference = {c["scenario"]["scenario_id"] for c in report["candidates"] if c["selected_on_validation"]}
    assert mine == reference and len(reference) > 0
    by_id = {c["scenario"]["scenario_id"]: c for c in report["candidates"]}
    for k in range(len(scenarios)):
        c = by_id[scenarios[k]["scenario_id"]]
        assert abs(c["q_bh_approx"] - selection["q"][k]) < 1e-9
        t = selection["test"]
        if c["test"]["n"]:
            assert abs(c["test"]["hit_rate"] - t["hit"][k]) < 1e-12
        if c["test"]["roi"] is not None:
            assert abs(c["test"]["roi"] - t["roi"][k]) < 1e-9 and c["test"]["settled_bets"] == int(t["settled"][k])


def test_rule_discovery_does_not_read_any_score():
    rows = synthetic(300, seed=2)
    clean, _ = core._clean_records(rows)
    train = core._split_chronologically(clean)[0]
    fm = {str(r["match_id"]): core.build_features(r) for r in clean}
    first = core.discover_scenarios(train, fm, max_candidates=300)
    changed = [{**r, "home_goals": 9 - r["home_goals"], "away_goals": 7} for r in rows]
    clean2, _ = core._clean_records(changed)
    train2 = core._split_chronologically(clean2)[0]
    fm2 = {str(r["match_id"]): core.build_features(r) for r in clean2}
    assert core.discover_scenarios(train2, fm2, max_candidates=300) == first  # condition nécessaire à l'exactitude de la permutation imbriquée


# ---------------------------------------------------------------------------------------------
# Permutations
# ---------------------------------------------------------------------------------------------

def test_permutation_moves_whole_scores_inside_strata_only():
    clean, fm, scenarios, arena = build_arena(synthetic(120, seed=4, odds=True))
    strata = np.array(["a", "b", "c"] * 40, dtype=object)
    groups = V._groups(strata)
    rng = np.random.default_rng(1)
    Yp = V.permuted(arena.Y, groups, rng)
    assert Yp.shape == arena.Y.shape
    for label in ("a", "b", "c"):
        idx = np.nonzero(strata == label)[0]
        before = sorted(map(tuple, arena.Y[:, idx].T.astype(int).tolist()))
        after = sorted(map(tuple, Yp[:, idx].T.astype(int).tolist()))
        assert before == after  # même multiensemble de scores, 16 issues restées liées
    assert not np.array_equal(Yp, arena.Y)
    again = V.permuted(arena.Y, groups, np.random.default_rng(1))
    assert np.array_equal(Yp, again)  # déterministe pour une graine donnée
    singleton = V._groups(np.array(["x", "y", "z"], dtype=object))
    assert singleton == []  # une strate d'un seul match n'est jamais mélangée


def test_market_strata_separate_matches_without_complete_odds():
    rows = synthetic(60, seed=1, odds=True)
    for i, r in enumerate(rows):
        r["home_odds"] = 1.4 + (i % 12) * 0.2
        r["draw_odds"], r["away_odds"] = 3.3, 2.0 + (i % 6) * 0.5
    rows[0].pop("away_odds")
    clean, _ = core._clean_records(rows)
    fm = {str(r["match_id"]): core.build_features(r) for r in clean}
    labels = V.market_strata(clean, fm)
    assert labels[0] == "SANS_COTES" and sum(l == "SANS_COTES" for l in labels) == 1
    assert len(set(labels)) > 5


def test_permutation_p_value_is_never_zero_and_counts_ties():
    null = np.array([0.1, 0.2, 0.3, 0.4])
    assert V.p_value(10.0, null) == pytest.approx(1 / 5)
    assert V.p_value(0.3, null) == pytest.approx(3 / 5)
    assert V.p_value(-1.0, null) == 1.0


def test_nested_permutation_detects_a_real_signal_and_stays_quiet_on_noise():
    strata = lambda n: np.array(["L"] * n, dtype=object)
    clean, fm, scenarios, arena = build_arena(synthetic(400, seed=7, signal=True))
    observed = V.pipeline_stats(arena, arena.Y)
    result = V.compare_to_null(observed, V.nested_permutation(arena, strata(len(clean)), 99, seed=1))
    assert observed["selected"] >= 5 and result["selected"]["p"] <= 0.05
    false_alarms = 0
    for seed in range(8):
        clean, fm, scenarios, arena = build_arena(synthetic(400, seed=100 + seed, signal=False))
        observed = V.pipeline_stats(arena, arena.Y)
        comparison = V.compare_to_null(observed, V.nested_permutation(arena, strata(len(clean)), 99, seed=seed))
        false_alarms += comparison["selected"]["p"] <= 0.05
    assert false_alarms <= 1  # niveau nominal 5 % ; 8 jeux de pur bruit


def test_nested_permutation_replays_the_selection_instead_of_reusing_it():
    clean, fm, scenarios, arena = build_arena(synthetic(400, seed=7, signal=True))
    null = V.nested_permutation(arena, np.array(["L"] * len(clean), dtype=object), 40, seed=3)
    # sous des scores permutés, presque aucune règle ne passe la sélection : le test n'hérite pas de la sélection observée
    assert null["selected"].mean() < 0.2 * V.pipeline_stats(arena, arena.Y)["selected"]


# ---------------------------------------------------------------------------------------------
# Règles gelées, max-T, un pari par match, bootstrap par jour
# ---------------------------------------------------------------------------------------------

def test_freeze_uses_nothing_after_the_cutoff(tmp_path):
    records, _ = football_like(tmp_path, days=200)
    cutoff = "2026-01-10"
    first = V.freeze_rules(records, cutoff=cutoff, max_candidates=300)
    rng = random.Random(1)
    altered = [({**r, "home_goals": rng.choice([0, 6]), "away_goals": rng.choice([0, 5])} if r["date"] > cutoff else r) for r in records]
    # l'historique partagé par référence doit être recalculé : on recharge des données modifiées après le gel
    rows = []
    for r in records:
        d = r["date"]
        hg, ag = (r["home_goals"], r["away_goals"]) if d <= cutoff else (rng.choice([0, 6]), rng.choice([0, 5]))
        rows.append((d, r["home_team"], r["away_team"], hg, ag))
    other = tmp_path / "other"
    write_football_data(other, rows)
    second = V.freeze_rules(load_football_data(other)[0], cutoff=cutoff, max_candidates=300)
    assert first["frozen"] == second["frozen"] and first["matches_used"] == second["matches_used"]
    assert first["last_validation_day"] <= cutoff and len(altered) == len(records)


def test_frozen_rule_family_detects_signal_with_max_t_adjustment():
    rows = synthetic(500, seed=11, signal=True, odds=True)
    frozen = [{"conditions": [{"feature": "pre_x", "op": "ge", "value": 0.5}], "target": "home_scores_1plus", "complexity": 1, "priority_validation_lift": 0.3}]
    for k, thr in enumerate((0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 0.95)):
        for target in ("away_scores_1plus",):  # indépendante de x par construction (away_win/draw en dépendent réellement)
            frozen.append({"conditions": [{"feature": "pre_x", "op": "le" if k % 2 else "ge", "value": thr}], "target": target,
                           "complexity": 1, "priority_validation_lift": 0.05 - k * 0.001})
    result = V.evaluate_frozen(frozen, rows, repetitions=199, seed=5)
    best = result["best_by_lift"][0]
    assert best["target"] == "home_scores_1plus" and best["p_adj_lift_marche"] <= 0.05
    noise = [r for r in result["best_by_lift"] if r["target"] != "home_scores_1plus"]
    assert sum(r["p_adj_lift_marche"] <= 0.05 for r in noise) <= 1
    assert all(0 < r["p_adj_lift_marche"] <= 1 for r in result["best_by_lift"])
    assert result["family_size_lift"] == len(frozen) - 1  # la règle « ge 0,95 » couvre < 30 matchs : exclue de la famille par effectif, jamais par résultat


def test_evaluate_frozen_roi_and_portfolio_are_exact_and_one_bet_per_match():
    rows = synthetic(200, seed=13, signal=True, odds=True)
    frozen = [{"conditions": [{"feature": "pre_x", "op": "ge", "value": 0.5}], "target": "home_scores_1plus", "complexity": 1, "priority_validation_lift": 0.4},
              {"conditions": [{"feature": "pre_x", "op": "ge", "value": 0.0}], "target": "draw", "complexity": 1, "priority_validation_lift": 0.1}]
    result = V.evaluate_frozen(frozen, rows, repetitions=50, seed=2)
    p = result["portfolio"]
    assert p["picks"] == 200 == p["distinct_matches"]  # un seul pari par match malgré deux règles qui se recoupent
    expected = []
    for r in rows:
        if r["prematch_features"]["pre_x"] >= 0.5:
            expected.append(1.5 * (r["home_goals"] >= 1) - 1)
        else:
            expected.append(3.0 * (r["home_goals"] == r["away_goals"]) - 1)
    assert p["roi"]["mean"] == pytest.approx(float(np.mean(expected)), abs=1e-12)
    assert p["settled_bets"] == 200 and p["mean_odds"] == pytest.approx(np.mean([1.5 if r["prematch_features"]["pre_x"] >= 0.5 else 3.0 for r in rows]))


def test_pick_one_bet_follows_priority_order_and_skips_missing_odds():
    rows = []
    for i, x in enumerate([0.9, 0.9, 0.2, 0.2]):
        rows.append({"match_id": f"t{i}", "date": f"2026-01-0{i + 1}", "league": "L", "home_team": f"H{i}", "away_team": f"A{i}", "home_goals": 1, "away_goals": 0,
                     "home_history": [], "away_history": [], "prematch_features": {"pre_a": x},
                     "target_odds": {"home_win": 2.0, "draw": 3.0} if i != 1 else {"draw": 3.0}})
    clean, _ = core._clean_records(rows)
    fm = {str(r["match_id"]): core.build_features(r) for r in clean}
    scenarios = [{"conditions": [{"feature": "pre_a", "op": "ge", "value": 0.5}], "target": "home_win"},
                 {"conditions": [{"feature": "pre_a", "op": "ge", "value": 0.0}], "target": "draw"}]
    arena = V.Arena(clean, fm, scenarios, {"all": clean})
    positions, chosen = arena.pick_one_bet(np.array([0, 1]), "all", require_odds=True)
    assert positions.tolist() == [0, 1, 2, 3] and chosen.tolist() == [0, 1, 1, 1]  # t1 n'a pas de cote home_win : repli sur la 2e règle
    reversed_positions, reversed_chosen = arena.pick_one_bet(np.array([1, 0]), "all", require_odds=True)
    assert reversed_chosen.tolist() == [1, 1, 1, 1]
    picks = arena.picks(arena.Y, "all", positions, chosen)
    assert picks["roi"].tolist() == [1.0, -1.0, -1.0, -1.0]  # 1-0 : home_win gagne à 2.0, les nuls perdent


def test_cluster_bootstrap_resamples_days_not_matches():
    values = np.array([1.0, 1.0, 1.0, -1.0, -1.0, -1.0, 0.5, 0.5])
    days = np.array(["d1", "d1", "d1", "d2", "d2", "d2", "d3", "d3"])
    out = V.cluster_bootstrap_mean(values, days, repetitions=500, seed=3)
    assert out["days"] == 3 and out["n"] == 8 and out["mean"] == pytest.approx(values.mean())
    assert out["ci95"][0] < out["mean"] < out["ci95"][1]
    assert V.cluster_bootstrap_mean(values, days, repetitions=500, seed=3) == out
    # avec 3 jours opposés, l'intervalle par jour est bien plus large que celui, naïf, par match
    naive = 1.96 * values.std(ddof=1) / np.sqrt(len(values))
    assert (out["ci95"][1] - out["ci95"][0]) / 2 > naive
    assert V.cluster_bootstrap_mean(values[:3], days[:3])["ci95"] is None  # un seul jour : pas d'intervalle inventé
    assert V.cluster_bootstrap_mean(np.array([np.nan]), np.array(["d"]))["n"] == 0


def test_verdict_requires_every_criterion_and_defaults_to_insufficient_data():
    good = {"span_days": 60, "portfolio": {"settled_bets": 400, "roi": {"mean": 0.05, "ci95": [0.01, 0.09]}},
            "permutation_marche": {"portfolio_roi": {"p": 0.01}},
            "portfolio_by_date_block": [{"roi": 0.1}, {"roi": 0.05}, {"roi": -0.01}]}
    assert V.decide_verdict(good)["verdict"] == "PREUVE_DE_RENTABILITE_INDEPENDANTE"
    short = {**good, "span_days": 20}
    assert V.decide_verdict(short)["verdict"] == "DONNEES_INSUFFISANTES"
    few = {**good, "portfolio": {**good["portfolio"], "settled_bets": 100}}
    assert V.decide_verdict(few)["verdict"] == "DONNEES_INSUFFISANTES"
    losing = {**good, "portfolio": {**good["portfolio"], "roi": {"mean": -0.05, "ci95": [-0.1, 0.0]}}}
    assert V.decide_verdict(losing)["verdict"] == "NON_RENTABLE"
    for broken in ({**good, "portfolio": {**good["portfolio"], "roi": {"mean": 0.05, "ci95": [-0.02, 0.1]}}},
                   {**good, "permutation_marche": {"portfolio_roi": {"p": 0.2}}},
                   {**good, "portfolio_by_date_block": [{"roi": 0.1}, {"roi": -0.05}, {"roi": -0.01}]}):
        assert V.decide_verdict(broken)["verdict"] == "NON_CONCLUANT"
    assert V.decide_verdict(None)["verdict"] == "DONNEES_INSUFFISANTES"


# ---------------------------------------------------------------------------------------------
# Walk-forward : aucun futur dans l'apprentissage ni la sélection
# ---------------------------------------------------------------------------------------------

def test_date_cut_never_splits_a_day():
    rows = [{"date": f"2026-01-{1 + i // 10:02d}"} for i in range(100)]
    for fraction in (0.3, 0.5, 0.75):
        cut = V._date_cut(rows, fraction)
        assert rows[cut - 1]["date"] != rows[cut]["date"]


def test_football_data_walk_forward_trains_and_validates_before_each_test_month(tmp_path):
    records, _ = football_like(tmp_path, days=200)
    months = ["2026-01", "2026-02"]
    result = V.football_data_walk_forward(records, test_months=months, max_candidates=200, repetitions=5)
    assert [f["month"] for f in result["folds"]] == months
    for fold in result["folds"]:
        start = f'{fold["month"]}-01'
        assert fold["train_last_day"] < fold["validation_last_day"] < start  # tout l'apprentissage et la sélection précèdent le mois
        assert fold["split"]["test"] > 0 and fold["split"]["train"] > fold["split"]["validation"] > 0
    assert result["folds"][1]["split"]["train"] > result["folds"][0]["split"]["train"]  # fenêtre croissante
    assert "pooled" in result and all("_null" not in f for f in result["folds"])


def test_archive_walk_forward_tests_are_disjoint_and_after_selection():
    rows = synthetic(480, seed=21, signal=True, odds=True, per_day=6)
    result = V.archive_walk_forward(rows, fractions=(0.6, 0.8, 1.0), max_candidates=200, repetitions=9)
    spans = [f["test_days"] for f in result["folds"]]
    assert spans[0][1] < spans[1][0] and spans[1][1] < spans[2][0]
    for fold in result["folds"]:
        assert fold["permutation_marche"]["selected"]["p"] > 0 and "portfolio_test" in fold


# ---------------------------------------------------------------------------------------------
# CLI : jeu gelé infalsifiable, aucun chevauchement, isolation du reste du dépôt
# ---------------------------------------------------------------------------------------------

def test_frozen_file_digest_detects_edits_and_overlap(tmp_path, monkeypatch):
    frozen = [{"conditions": [{"feature": "pre_x", "op": "ge", "value": 0.5}], "target": "home_win"}]
    path = tmp_path / "gel.json"
    path.write_text(json.dumps({"cutoff": "2026-01-05", "sha256": validate_cli.rules_digest(frozen), "frozen": frozen}), encoding="utf-8")
    assert validate_cli.rules_digest(frozen) == validate_cli.rules_digest([dict(frozen[0])])
    edited = [{**frozen[0], "target": "home_scores_1plus"}]
    assert validate_cli.rules_digest(edited) != validate_cli.rules_digest(frozen)
    archive = tmp_path / "archive"
    archive.mkdir()
    import gzip
    item = {"match_id": "m", "date": "2026-01-03", "competition": "L", "domicile": "A", "exterieur": "B", "score": {"buts_dom": 1, "buts_ext": 0},
            "coup_d_envoi_utc": "2026-01-03T18:00:00Z", "run": {"pris_le": "2026-01-03T09:00:00Z"}, "equipe_dom": {"statut": "OK", "matchs": []}, "equipe_ext": {"statut": "OK", "matchs": []},
            "cotes_betpawa": {"1x2": {"1": 1.7, "N": 3.2, "2": 4.1}}}
    with gzip.open(archive / "2026-01-03.json.gz", "wt", encoding="utf-8") as stream:
        json.dump({"m": item}, stream)
    fd = tmp_path / "fd"
    write_football_data(fd, [("2026-01-01", "A", "B", 1, 1)])
    # l'échantillon (03/01) commence avant la date de gel (05/01) : refus explicite
    with pytest.raises(SystemExit):
        validate_cli.main(["--archive", str(archive), "--football-data", str(fd), "--evaluate-frozen", str(path), "--output", str(tmp_path / "o.json")])
    # fichier modifié après gel : refus
    path.write_text(json.dumps({"cutoff": "2025-12-31", "sha256": validate_cli.rules_digest(frozen), "frozen": edited}), encoding="utf-8")
    with pytest.raises(SystemExit):
        validate_cli.main(["--archive", str(archive), "--football-data", str(fd), "--evaluate-frozen", str(path), "--output", str(tmp_path / "o.json")])


def test_validation_modules_stay_isolated_from_production_code():
    forbidden = ("moteur", "pipeline", "journal", "generateur", "precalcul", "branchement", "run_pipeline", "pont_moteur", "contrat_moteur")
    root = Path(core.__file__).parent
    for name in ("validation.py", "football_data.py", "validate.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        assert not [m for m in imported if any(f in m.lower() for f in forbidden)], (name, imported)
    assert validate_cli.validation.PROOF_MIN_SPAN_DAYS == 56 and validate_cli.validation.PROOF_MIN_SETTLED_PICKS == 300
