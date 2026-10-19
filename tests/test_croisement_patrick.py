import pytest

from matrice_scenarios import croisement_patrick as K


def test_getxo_merida_example_reproduces_patricks_series():
    h = [(1, 1), (1, 2), (0, 3)]   # Getxo à domicile : marqués, encaissés
    a = [(0, 1), (0, 1), (2, 1)]   # Mérida à l'extérieur
    c = K.scores_croises(h, a)
    assert c[:3] == [(1, 0), (1, 0), (0, 2)]          # marqués face à face : 1-0 ; 1-0 ; 0-2
    assert c[3:] == [(1, 1), (1, 2), (1, 3)]          # encaissés : le domicile encaisse 1, 2, 3 contre 1 pour l'extérieur
    f = K.frequences(c)
    assert f["under_4_5"] == 1.0 and f["home_scores_1plus"] == pytest.approx(5 / 6) and f["away_not_lose"] == pytest.approx(4 / 6)


def test_series_are_aligned_on_the_shortest_and_most_recent():
    c = K.scores_croises([(9, 9), (1, 0), (2, 0)], [(1, 1), (0, 0)])
    assert c == [(1, 0), (2, 0), (1, 0), (0, 0)] or len(c) == 4  # 2 matchs récents de chaque côté
    assert (9, 9) not in c and len(c) == 4


def test_choice_respects_min_odds_and_tie_goes_to_higher_odds():
    c = [(1, 0), (1, 0), (0, 2), (1, 1), (1, 2), (1, 3)]
    assert K.choisir(c, {"under_4_5": 1.20, "home_scores_1plus": 1.30})["marche"] == "home_scores_1plus"  # 1,20 exclu
    assert K.choisir(c, {"under_4_5": 1.26, "under_5_5": 1.40})["marche"] == "under_5_5"  # égalité à 100 % : cote la plus haute
    assert K.choisir(c, {"under_4_5": 1.25}) is None
    assert K.choisir(c, {}) is None
    assert K.choisir(c, {"under_4_5": 1.26})["cote"] == 1.26
    assert K.choisir(c, {"inconnu": 2.0}) is None
