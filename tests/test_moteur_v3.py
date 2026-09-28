from __future__ import annotations

import pytest

from moteur_v3.calibration import IsotonicCalibrator
from moteur_v3.decision import decide
from moteur_v3.markets import derive_markets
from moteur_v3.model import build_model
from moteur_v3.value import evaluate
from moteur_v3.risk import goal_context_dispersion, assess


def rows(home=True, n=6):
    return [
        {
            "date": f"2026-09-{10+i:02d}",
            "domicile": home,
            "buts_marques": 2 if i % 2 == 0 else 1,
            "buts_encaisses": 1 if i % 3 else 0,
        }
        for i in range(n)
    ]


def test_sample_gate_metadata():
    m = build_model(rows(True, 2), rows(False, 2))
    assert m.home_sample.current_n == 2
    assert m.home_sample.level == "TRES_FAIBLE"


def test_previous_season_is_contextual_and_not_a_league_prior():
    current = rows(True, 3)
    previous = rows(True, 8)
    m = build_model(
        current, rows(False, 5),
        previous_home_matches=previous,
        season_progress=0.0,
    )
    assert 0 < m.home_sample.previous_weight < 1
    assert m.diagnostics["h2h_used"] is False


def test_zero_lambda_does_not_get_an_arbitrary_floor():
    home = rows(True, 5)
    away = rows(False, 5)
    for r in home:
        r["buts_marques"] = 0
        r["xg"] = 0.0
        r["xg_concede"] = 1.0
    m = build_model(home, away)
    assert m.lambda_home == 0.0
    assert m.degenerate_home is True


def test_exact_total_goals_is_exhaustive():
    m = build_model(rows(True, 6), rows(False, 6))
    p = derive_markets(m)
    assert abs(sum(p[f"exact_goals_{n}"] for n in range(6)) + p["exact_goals_6_plus"] - 1) < 1e-9


def test_handicap_three_way_is_exhaustive():
    m = build_model(rows(True, 6), rows(False, 6))
    p = derive_markets(m, [1])
    assert abs(p["handicap_1_1"] + p["handicap_1_X"] + p["handicap_1_2"] - 1) < 1e-9


def test_dispersion_est_un_ratio_variance_moyenne():
    m = build_model(rows(True, 6), rows(False, 6))
    d = goal_context_dispersion(rows(True, 6) + rows(False, 6))
    assert d is not None and d < 10
    assert assess(d, 0.70).eligible


def test_htft_comes_from_joint_convolution():
    m = build_model(
        [{**x, "buts_marques_mi_temps": 1, "buts_encaisses_mi_temps": 0} for x in rows(True, 6)],
        [{**x, "buts_marques_mi_temps": 0, "buts_encaisses_mi_temps": 1} for x in rows(False, 6)],
    )
    p = derive_markets(m)
    assert all(f"htft_{ht}_{ft}" in p for ht in "1X2" for ft in "1X2")
    assert abs(sum(p[f"htft_{ht}_{ft}"] for ht in "1X2" for ft in "1X2") - 1) < 1e-9


def test_handicap_negative_line_is_supported():
    m = build_model(rows(True, 6), rows(False, 6))
    p = derive_markets(m, [-1.5])
    assert abs(p["handicap_-1.5_1"] + p["handicap_-1.5_X"] + p["handicap_-1.5_2"] - 1) < 1e-9


def test_no_corner_or_card_fabrication():
    m = build_model(rows(True, 6), rows(False, 6))
    p = derive_markets(m)
    assert not any(k.startswith(("corners_", "cards_", "red_cards_")) for k in p)


def test_value_uses_calibrated_probability():
    v = evaluate("x", 0.70, 1.60, calibrated_probability=0.65)
    assert v.probability == 0.65
    assert v.edv > 0


def test_degenerate_probability_is_rejected():
    v = evaluate("x", 1.0, 1.30, calibrated_probability=1.0)
    assert not v.eligible
    assert "PROBABILITE_DEGENEREE" in v.reasons


def test_calibrator_refuses_small_training_set():
    c = IsotonicCalibrator(minimum_observations=300)
    fit = c.fit([0.6] * 20, [1] * 20)
    assert not fit.ready
    assert c.predict(0.6) is None


def test_decision_is_adaptive_and_never_requires_three():
    candidate = {
        "market": "x",
        "probability": 0.70,
        "odds": 1.60,
        "edge": 0.075,
        "edv": 12.0,
        "eligible": True,
        "calibrated": True,
        "double_control_ok": True,
        "justification": "preuve directe",
        "n_relevant": 5,
        "family": "goals",
        "exposure_group": "goals_total",
    }
    selected, rejected, _ = decide([candidate])
    assert len(selected) == 1
    assert not rejected


def test_missing_double_control_blocks_selection():
    candidate = {
        "market": "x", "probability": 0.75, "odds": 1.50, "edge": 1/12,
        "edv": 12.5, "eligible": True, "calibrated": True,
        "double_control_ok": False, "justification": "preuve",
        "n_relevant": 8,
    }
    selected, rejected, _ = decide([candidate])
    assert not selected
    assert any("DOUBLE_CONTROLE" in r for _, reasons in rejected for r in reasons)


# --- AJOUT 27/09/2026 : bout en bout avec cotes (evaluate_match n'était appelé par aucun test) ------------------------

from moteur_v3 import evaluate_match  # noqa: E402

ODDS = {"1x2_1": 1.9, "1x2_X": 3.4, "1x2_2": 4.0, "dc_1X": 1.3, "over_2_5": 1.9, "under_2_5": 1.9,
        "btts_yes": 1.8, "btts_no": 1.95}


def _calibre():
    c = IsotonicCalibrator()
    c.fit([0.2, 0.4, 0.6, 0.8] * 20, [0, 0, 1, 1] * 20)
    return c


@pytest.mark.parametrize("odds,calibrator", [({"dc_1X": 1.3}, None), (ODDS, None), (ODDS, "calibre")])
def test_evaluate_match_bout_en_bout_avec_cotes(odds, calibrator):
    r = evaluate_match({"home_matches": rows(True, 6), "away_matches": rows(False, 6), "odds": odds},
                       calibrator=_calibre() if calibrator else None)
    assert {c["market"] for c in r["candidates"]} == set(odds)
    assert all(v.market in odds for v in r["values"].values())


@pytest.mark.parametrize("champ", ["buts_marques", "buts_encaisses"])
def test_lambda_nul_rejete_sans_planter(champ):
    home = rows(True, 5)
    for x in home:
        x[champ] = 0
    r = evaluate_match({"home_matches": home, "away_matches": rows(False, 5), "odds": ODDS})
    assert not r["selected"]
    assert any("PROBABILITE_DEGENEREE" in v.reasons for v in r["values"].values())


def test_probabilite_nulle_rejetee_pas_exception():
    for p in (0.0, 1.0):
        v = evaluate("x", p, 1.5)
        assert not v.eligible and "PROBABILITE_DEGENEREE" in v.reasons
    with pytest.raises(ValueError):
        evaluate("x", 1.2, 1.5)


@pytest.mark.parametrize("competition", ["Angleterre : Premier League", "Angleterre : League Two", None])
def test_nom_de_competition_sans_effet(competition):
    base = {"home_matches": rows(True, 6), "away_matches": rows(False, 6), "odds": ODDS}
    r0 = evaluate_match(base, calibrator=_calibre())
    r1 = evaluate_match({**base, "competition": competition}, calibrator=_calibre())
    assert r0["probabilities_raw"] == r1["probabilities_raw"]
    assert [c["probability"] for c in r0["candidates"]] == [c["probability"] for c in r1["candidates"]]
