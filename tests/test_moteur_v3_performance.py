"""Indice de performance du marché V3 : scénarios moyen/pire croisés (décision de Patrick, 10/10/2026)."""
import itertools

import pytest

from moteur_v3.markets import gagne
from moteur_v3.performance import indice_performance, marge, profils


def _m(*scores):
    return [{"buts_marques": a, "buts_encaisses": b} for a, b in scores]


BORO = _m((2, 1), (3, 1), (4, 3), (2, 2))
WOLVES = _m((3, 1), (2, 4), (2, 2), (1, 0))   # buts marqués/encaissés de Wolves à l'extérieur


def test_exemple_boro_wolves_over_25_donne_3_sur_4():
    r = indice_performance("over_2_5", BORO, WOLVES)
    assert (r["indice"], r["libelle"]) == (3, "Recommandé")
    totaux = [round(s["buts_domicile"] + s["buts_exterieur"], 3) for s in r["scenarios"]]
    assert totaux == [4.125, 3.375, 2.75, 2.0]


def test_moyennes_simples():
    r = indice_performance("over_2_5", BORO, WOLVES)
    assert r["moyenne_domicile"] == {"marque": 2.75, "encaisse": 1.75}
    assert r["moyenne_exterieur"] == {"marque": 2.0, "encaisse": 1.75}


def test_niveaux_4_2_1_0():
    # over 2,5 ; domicile marque/encaisse, extérieur marque/encaisse
    assert indice_performance("over_2_5", _m((3, 2)), _m((2, 3)))["indice"] == 4          # 5 buts partout
    r2 = indice_performance("over_2_5", _m((2, 2)), _m((4, 4), (0, 0)))
    assert (r2["indice"], r2["libelle"]) == (2, "Attention")
    r1 = indice_performance("over_2_5", _m((4, 4), (0, 0)), _m((4, 4), (0, 0)))
    assert (r1["indice"], r1["libelle"]) == (1, "Risqué")
    r0 = indice_performance("over_5_5", _m((1, 0)), _m((0, 1)))
    assert (r0["indice"], r0["libelle"]) == (0, "Très risqué")


def test_un_seul_match_par_equipe_donne_0_ou_4():
    assert indice_performance("over_2_5", _m((2, 2)), _m((2, 2)))["indice"] == 4
    assert indice_performance("over_2_5", _m((1, 0)), _m((0, 1)))["indice"] == 0


def test_pire_exterieur_est_oriente_du_point_de_vue_de_l_exterieur():
    # victoire extérieure : le pire match de l'extérieur est celui où il marque le moins
    p = profils(_m((3, 0), (0, 2)), "1x2_2", False)
    assert p["pire"] == (0, 2)


def test_egalite_exacte_avec_la_ligne_ne_valide_pas():
    r = indice_performance("over_2_5", _m((1, 1)), _m((1, 0.5)))
    assert all(not s["valide"] for s in r["scenarios"] if abs(s["buts_domicile"] + s["buts_exterieur"] - 2.5) < 1e-9)


@pytest.mark.parametrize("marche", ["score_2_1", "exact_goals_3", "total_pair", "handicap_0_X"])
def test_marche_non_continu_donne_none(marche):
    assert indice_performance(marche, BORO, WOLVES) is None


def test_donnees_vides_donnent_none():
    assert indice_performance("over_2_5", [], WOLVES) is None
    assert indice_performance("over_2_5", BORO, []) is None


MARCHES = ["1x2_1", "1x2_2", "dc_1X", "dc_X2", "dc_12", "btts_yes", "btts_no", "over_2_5", "under_2_5", "over_1_5",
           "home_over_1_5", "away_under_0_5", "clean_home", "clean_away", "clean_home_no", "clean_away_no",
           "handicap_1_1", "handicap_1_2", "handicap_1.5_1", "handicap_1.5_2", "handicap_-1.5_1", "handicap_-1.5_2"]


@pytest.mark.parametrize("marche", MARCHES)
def test_marge_coherente_avec_le_reglement_entier(marche):
    for h, a in itertools.product(range(9), range(9)):
        mg = marge(marche, h, a)
        assert mg is not None and mg != 0
        assert (mg > 0) == bool(gagne(marche, h, a)), (marche, h, a)
