import math
import pytest

from moteur_decision.statistical_model import build_model, poisson_matrix, previous_season_weight
from moteur_decision.market_engine import derive_goal_markets
from moteur_decision.value_engine import evaluate_market

def match(date, home, gf, ga, **extra):
    return {"date": date, "domicile": home, "buts_marques": gf, "buts_encaisses": ga, **extra}

def test_only_latest_12_are_used():
    rows=[match(f"2026-08-{i:02d}", True, 0, 0) for i in range(1,14)]
    out=build_model(rows, [match("2026-08-01", False, 1, 0)])
    assert out.diagnostics["home_matches_used"] == 12
    assert out.diagnostics["home_dates"][0] == "2026-08-02"

def test_lambda_uses_home_attack_and_away_defence():
    home=[match("2026-08-01",True,2,1),match("2026-08-02",True,2,1),match("2026-08-03",True,2,1)]
    away=[match("2026-08-01",False,1,1),match("2026-08-02",False,1,1),match("2026-08-03",False,1,1)]
    out=build_model(home,away)
    assert out.lambda_home > 0
    assert out.lambda_away > 0
    assert out.diagnostics["h2h_used"] is False

def test_xg_is_used_without_arbitrary_addition():
    home=[match("2026-08-01",True,1,1,xg=4,xg_concede=1)]
    away=[match("2026-08-01",False,1,1,xg=1,xg_concede=4)]
    out=build_model(home,away)
    assert out.diagnostics["xg_home_used"]
    assert out.diagnostics["xg_away_used"]
    assert out.lambda_home != 1.0

def test_missing_xg_does_not_create_fake_xg():
    home=[match("2026-08-01",True,2,0)]
    away=[match("2026-08-01",False,0,2)]
    out=build_model(home,away)
    assert out.diagnostics["xg_home_used"] is False
    assert out.diagnostics["xg_away_used"] is False

def test_poisson_matrix_sums_to_one():
    m=poisson_matrix(1.7,1.2)
    assert abs(sum(map(sum,m))-1.0) < 1e-12

def test_exact_total_goals_and_basic_markets():
    rows=[match("2026-08-01",True,2,0, buts_marques_mi_temps=1,buts_encaisses_mi_temps=0),
          match("2026-08-02",True,1,0, buts_marques_mi_temps=0,buts_encaisses_mi_temps=0),
          match("2026-08-03",True,2,1, buts_marques_mi_temps=1,buts_encaisses_mi_temps=1)]
    away=[match("2026-08-01",False,0,1, buts_marques_mi_temps=0,buts_encaisses_mi_temps=1),
          match("2026-08-02",False,1,1, buts_marques_mi_temps=0,buts_encaisses_mi_temps=1),
          match("2026-08-03",False,1,0, buts_marques_mi_temps=1,buts_encaisses_mi_temps=0)]
    out=build_model(rows,away)
    markets=derive_goal_markets(out)
    assert "exact_goals_0" in markets and "exact_goals_6_plus" in markets
    assert abs(markets["victoire"] + markets["nul"] + markets["defaite"] - 1.0) < 1e-12
    assert abs(markets["exact_goals_0"] + markets["exact_goals_1"] + markets["exact_goals_2"] + markets["exact_goals_3"] + markets["exact_goals_4"] + markets["exact_goals_5"] + markets["exact_goals_6_plus"] - 1.0) < 1e-12

def test_half_model_is_not_invented_when_half_data_missing():
    home=[match("2026-08-01",True,1,0)]
    away=[match("2026-08-01",False,0,1)]
    out=build_model(home,away)
    assert out.score_matrix_first_half is None
    assert out.score_matrix_second_half is None

def test_value_rules():
    r=evaluate_market("btts_oui",.68,1.60)
    assert r.eligible
    assert abs(r.edge-(.68-1/1.60)) < 1e-12
    assert abs(r.edv-(100*1.60*r.edge)) < 1e-12
    assert abs(r.ev-(r.edv/100.0)) < 1e-12
    assert not evaluate_market("x",.59,1.60).eligible
    assert not evaluate_market("x",.70,1.80).eligible

def test_previous_weight_is_explicit():
    home=[match("2026-08-01",True,1,1)]
    away=[match("2026-08-01",False,1,1)]
    prev_h=[match("2025-08-01",True,4,1)]
    prev_a=[match("2025-08-01",False,1,4)]
    a=build_model(home,away,previous_home_matches=prev_h,previous_away_matches=prev_a,previous_weight=0)
    b=build_model(home,away,previous_home_matches=prev_h,previous_away_matches=prev_a,previous_weight=.5)
    assert a.lambda_home != b.lambda_home


def test_previous_season_weight_decreases_with_current_sample_and_progress():
    assert previous_season_weight(1, 0.0) == .8
    assert previous_season_weight(2, 0.0) == .6
    assert previous_season_weight(4, 0.0) == .2
    assert previous_season_weight(5, 0.0) == 0.0
    assert previous_season_weight(2, 0.5) == .3

def test_incompatible_previous_context_is_ignored():
    home=[match("2026-08-01",True,1,1)]
    away=[match("2026-08-01",False,1,1)]
    prev_h=[match("2025-08-01",True,4,1)]
    prev_a=[match("2025-08-01",False,1,4)]
    out=build_model(
        home, away,
        previous_home_matches=prev_h,
        previous_away_matches=prev_a,
        season_progress=0.0,
        previous_context_compatible=False,
    )
    assert out.diagnostics["previous_weight"] == 0.0
    assert out.diagnostics["previous_context_compatible"] is False


def test_three_way_handicap_matches_betpawa_convention():
    rows=[match("2026-08-01",True,2,0),match("2026-08-02",True,1,0),match("2026-08-03",True,3,1)]
    away=[match("2026-08-01",False,0,1),match("2026-08-02",False,1,2),match("2026-08-03",False,2,2)]
    out=derive_goal_markets(build_model(rows,away), handicap_lines=(1,))
    assert "handicap_3way_1_dom" in out
    assert "handicap_3way_1_nul" in out
    assert "handicap_3way_1_ext" in out
    assert abs(out["handicap_3way_1_dom"] + out["handicap_3way_1_nul"] + out["handicap_3way_1_ext"] - 1.0) < 1e-12

def test_half_markets_are_only_emitted_when_both_half_models_exist():
    home=[match("2026-08-01",True,2,0,buts_marques_mi_temps=1,buts_encaisses_mi_temps=0),
          match("2026-08-02",True,1,1,buts_marques_mi_temps=0,buts_encaisses_mi_temps=1)]
    away=[match("2026-08-01",False,0,1,buts_marques_mi_temps=0,buts_encaisses_mi_temps=1),
          match("2026-08-02",False,1,1,buts_marques_mi_temps=1,buts_encaisses_mi_temps=0)]
    markets=derive_goal_markets(build_model(home,away))
    assert "htft_1_1" in markets
    assert "dom_scores_both_halves" in markets
    assert abs(markets["half_most_goals_first"] + markets["half_most_goals_second"] + markets["half_most_goals_equal"] - 1.0) < 1e-12

def test_no_corners_or_cards_are_fabricated_from_goal_matrix():
    home=[match("2026-08-01",True,1,0)]
    away=[match("2026-08-01",False,0,1)]
    markets=derive_goal_markets(build_model(home,away))
    assert not any("corner" in k.lower() or "carton" in k.lower() for k in markets)
