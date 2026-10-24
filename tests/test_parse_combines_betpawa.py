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


# --- 24/10/2026 : page Betpawa en français (3 lectures qui réussissent, 3 qui ne doivent rien produire) --------------
FR_TABLEAU = """Double Chance & Plus de/Moins de | Fin de Match
1X
12
X2
Moins de 1.5
7.57
6.68
7.04
Plus de 1.5
1.96
1.61
1.71
Les Deux Équipes Marquent | Fin de Match
Oui
1.50
"""
FR_PAIRES = """Double Chance et Les Deux Équipes Marquent | Fin de Match
1X & Oui
2.30
1X & Non
4.50
X2 & Oui
2.09
"""
FR_PAIRES_TOTAL = """Double Chance & Plus de/Moins de | Fin de Match
1X & Moins de 3.5
1.72
X2 & Plus de 2.5
2.65
"""


def test_fr_tableau():
    r = parse_combines(FR_TABLEAU)
    assert r["dc_total_1.5"]["1N|plus"] == 1.96 and r["dc_total_1.5"]["N2|moins"] == 7.04 and r["dc_total_1.5"]["12|plus"] == 1.61


def test_fr_paires_btts():
    assert parse_combines(FR_PAIRES)["dc_btts"] == {"1N|Oui": 2.30, "1N|Non": 4.50, "N2|Oui": 2.09}


def test_fr_paires_total():
    r = parse_combines(FR_PAIRES_TOTAL)
    assert r["dc_total_3.5"] == {"1N|moins": 1.72} and r["dc_total_2.5"] == {"N2|plus": 2.65}


def test_fr_marche_simple_non_lu_comme_combine():
    assert parse_combines("Double Chance | Fin de Match\n1X\n1.30\nX2\n1.55\n12\n1.25\n") == {}


def test_fr_mi_temps_ignoree():
    assert parse_combines("Double Chance & Plus de/Moins de | 1ère Mi-temps\n1X & Plus de 0.5\n1.40\n") == {}


def test_fr_cote_illisible():
    assert parse_combines("Double Chance & Plus de/Moins de | Fin de Match\n1X & Plus de 1.5\nsuspendu\n") == {}


def test_releve_brut_des_blocs():
    from parse_combines_betpawa import diagnostic_combines
    assert diagnostic_combines(FR_PAIRES)[0][0] == "Double Chance et Les Deux Équipes Marquent | Fin de Match"
    assert diagnostic_combines("Double Chance | Fin de Match\n1X\n1.30\n") == []
