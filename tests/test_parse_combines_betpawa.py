"""Marchés combinés Betpawa : 3 lectures qui doivent réussir, 3 textes qui ne doivent rien produire."""
from parse_combines_betpawa import parse_combines

TABLEAU = """Double Chance and Over/Under | Full Time
- 1X
- 12
- X2
Under 1.5
7.57
6.68
7.04
Over 1.5
1.96
1.61
1.71
Both Teams To Score | Full Time
Yes
1.50
"""
PAIRES = """Double Chance and Both Teams To Score | Full Time
1X & Yes
2.30
1X & No
4.50
X2 & Yes
2.09
1X2 and Both Teams To Score | Full Time
1 & Yes
4.67
X & No
4.45
"""
ALTERNE = """1X2 and Over/Under | Full Time
Over 2.5
1
4.15
X
9.01
2
3.23
"""


def test_tableau_double_chance_total():
    r = parse_combines(TABLEAU)
    assert r["dc_total_1.5"]["1N|plus"] == 1.96 and r["dc_total_1.5"]["N2|moins"] == 7.04 and r["dc_total_1.5"]["12|plus"] == 1.61
    assert "btts" not in r


def test_paires_btts():
    r = parse_combines(PAIRES)
    assert r["dc_btts"] == {"1N|Oui": 2.30, "1N|Non": 4.50, "N2|Oui": 2.09}
    assert r["1x2_btts"] == {"1|Oui": 4.67, "N|Non": 4.45}


def test_disposition_alternee():
    assert parse_combines(ALTERNE)["1x2_total_2.5"] == {"1|plus": 4.15, "N|plus": 9.01, "2|plus": 3.23}


def test_texte_sans_combine():
    assert parse_combines("1X2 | Full Time\n1\n2.95\nX\n3.44\n2\n2.33\n") == {}


def test_titre_mi_temps_ignore():
    assert parse_combines("Double Chance and Both Teams To Score | First Half\n1X & Yes\n4.81\n") == {}


def test_cote_illisible_aucun_marche():
    assert parse_combines("Double Chance and Over/Under | Full Time\n- 1X\nOver 1.5\nabc\n") == {}
