from matrice_scenarios import pronostic_sur as P
from matrice_scenarios.croisements import outcome


def an(**probas):
    return {"markets": {m: {"probabilite": p} for m, p in probas.items()}}


def test_picks_most_probable_market_inside_the_odds_window():
    a = an(over_1_5=0.80, under_4_5=0.86, home_not_lose=0.75)
    assert P.choisir(a, {"over_1_5": 1.20, "under_4_5": 1.15, "home_not_lose": 1.22})["marche"] == "under_4_5"
    assert P.choisir(a, {"over_1_5": 1.20, "under_4_5": 1.05, "home_not_lose": 1.22})["marche"] == "over_1_5"  # 1,05 est hors fenêtre
    assert P.choisir(a, {"over_1_5": 1.10, "under_4_5": 1.40, "home_not_lose": 1.30})["marche"] == "over_1_5"  # 1,10 inclus
    assert P.choisir(a, {"over_1_5": 1.25})["cote"] == 1.25  # 1,25 inclus


def test_no_pick_when_nothing_is_in_the_window_or_no_odds():
    a = an(over_1_5=0.80, under_4_5=0.86)
    assert P.choisir(a, {"over_1_5": 1.26, "under_4_5": 1.09}) is None
    assert P.choisir(a, {}) is None
    assert P.choisir(a, {"under_5_5": 1.2}) is None  # marché inconnu du modèle


def test_tie_goes_to_higher_odds_and_pick_carries_breakeven():
    a = an(over_1_5=0.80, under_4_5=0.80)
    p = P.choisir(a, {"over_1_5": 1.12, "under_4_5": 1.22})
    assert p["marche"] == "under_4_5" and p["cote_equilibre"] == 1.25


def test_betpawa_odds_mapping_and_outcomes():
    raw = {"double_chance": {"1N": 1.2, "N2": 1.9}, "over_under_1.5": {"plus": 1.15, "moins": 5.0}, "over_under_4.5": {"moins": 1.2}, "btts": {"Oui": "x"}}
    c = P.cotes_du_match(raw)
    assert c == {"home_not_lose": 1.2, "away_not_lose": 1.9, "over_1_5": 1.15, "under_4_5": 1.2}
    assert P.cotes_du_match(None) == {}
    r = {"home_goals": 3, "away_goals": 2}
    assert outcome(r, "under_4_5") == 0 and outcome(r, "under_5_5") == 1 and outcome(r, "over_1_5") == 1
    assert outcome({"home_goals": 2, "away_goals": 2}, "under_4_5") == 1 and outcome({"home_goals": 0, "away_goals": 0}, "over_1_5") == 0
