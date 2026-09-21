"""Règlement des marchés 1X2 et handicaps (correctif du 21/09/2026).

Avant le correctif, 1x2_domicile / 1x2_exterieur étaient réglés comme une double chance (un nul comptait GAGNÉ) et
1x2_nul n'existait pas. Pour chaque marché : 3 cas qui DOIVENT gagner et 3 qui DOIVENT perdre.
"""
import pytest

from archetype_model.learning.reglement import evaluer_marche

CAS = [
    # marché, buts_dom, buts_ext, statut attendu
    ("1x2_domicile", 2, 0, "WIN"), ("1x2_domicile", 3, 1, "WIN"), ("1x2_domicile", 1, 0, "WIN"),
    ("1x2_domicile", 1, 1, "LOSS"), ("1x2_domicile", 0, 0, "LOSS"), ("1x2_domicile", 0, 2, "LOSS"),
    ("1x2_exterieur", 0, 1, "WIN"), ("1x2_exterieur", 1, 3, "WIN"), ("1x2_exterieur", 2, 5, "WIN"),
    ("1x2_exterieur", 1, 1, "LOSS"), ("1x2_exterieur", 2, 0, "LOSS"), ("1x2_exterieur", 0, 0, "LOSS"),
    ("1x2_nul", 0, 0, "WIN"), ("1x2_nul", 1, 1, "WIN"), ("1x2_nul", 3, 3, "WIN"),
    ("1x2_nul", 1, 0, "LOSS"), ("1x2_nul", 0, 2, "LOSS"), ("1x2_nul", 4, 1, "LOSS"),
    ("double_chance_1X", 1, 1, "WIN"), ("double_chance_1X", 2, 0, "WIN"), ("double_chance_1X", 0, 0, "WIN"),
    ("double_chance_1X", 0, 1, "LOSS"), ("double_chance_1X", 1, 2, "LOSS"), ("double_chance_1X", 0, 3, "LOSS"),
    ("double_chance_X2", 1, 1, "WIN"), ("double_chance_X2", 0, 2, "WIN"), ("double_chance_X2", 0, 0, "WIN"),
    ("double_chance_X2", 1, 0, "LOSS"), ("double_chance_X2", 3, 1, "LOSS"), ("double_chance_X2", 2, 0, "LOSS"),
    # handicap : la ligne est celle de l'équipe NOMMÉE, sans « + » ; l'égalité sur la ligne entière PERD (3 issues)
    ("handicap_domicile_-1.5", 2, 0, "WIN"), ("handicap_domicile_-1.5", 3, 1, "WIN"), ("handicap_domicile_-1.5", 4, 0, "WIN"),
    ("handicap_domicile_-1.5", 1, 0, "LOSS"), ("handicap_domicile_-1.5", 1, 1, "LOSS"), ("handicap_domicile_-1.5", 0, 2, "LOSS"),
    ("handicap_exterieur_1.5", 0, 1, "WIN"), ("handicap_exterieur_1.5", 1, 1, "WIN"), ("handicap_exterieur_1.5", 1, 0, "WIN"),
    ("handicap_exterieur_1.5", 2, 0, "LOSS"), ("handicap_exterieur_1.5", 3, 1, "LOSS"), ("handicap_exterieur_1.5", 4, 0, "LOSS"),
    ("handicap_domicile_-1.0", 2, 0, "WIN"), ("handicap_domicile_-1.0", 3, 1, "WIN"), ("handicap_domicile_-1.0", 4, 1, "WIN"),
    ("handicap_domicile_-1.0", 1, 0, "LOSS"), ("handicap_domicile_-1.0", 2, 1, "LOSS"), ("handicap_domicile_-1.0", 0, 0, "LOSS"),
    ("handicap_exterieur_1.0", 0, 0, "WIN"), ("handicap_exterieur_1.0", 0, 1, "WIN"), ("handicap_exterieur_1.0", 1, 2, "WIN"),
    ("handicap_exterieur_1.0", 1, 0, "LOSS"), ("handicap_exterieur_1.0", 2, 1, "LOSS"), ("handicap_exterieur_1.0", 3, 0, "LOSS"),
]


@pytest.mark.parametrize("marche,dom,ext,attendu", CAS)
def test_reglement(marche, dom, ext, attendu):
    assert evaluer_marche(marche, dom, ext).statut == attendu


def test_le_nul_n_est_plus_un_marche_inconnu():
    assert evaluer_marche("1x2_nul", 2, 2).statut == "WIN"


def test_un_nul_ne_fait_plus_gagner_une_victoire():
    # régression : avant le correctif, ces deux paris étaient comptés gagnés sur un 1-1
    assert evaluer_marche("1x2_domicile", 1, 1).statut == "LOSS"
    assert evaluer_marche("1x2_exterieur", 1, 1).statut == "LOSS"


def test_un_signe_plus_dans_le_nom_reste_non_reconnu():
    # le nom canonique n'a pas de « + » : un nom avec « + » ne doit jamais être réglé en silence
    assert evaluer_marche("handicap_exterieur_+1.5", 0, 1).statut == "MARCHE_NON_RECONNU"
