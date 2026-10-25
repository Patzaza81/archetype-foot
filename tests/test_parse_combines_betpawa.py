"""Marchés combinés Betpawa : 3 lectures qui doivent réussir, 3 textes qui ne doivent rien produire."""
import pytest

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


# --- 25/10/2026 : disposition RÉELLE relevée par la collecte (étiquette répétée devant chaque colonne) -----------------
REEL_TOTAL = """Double Chance and Over/Under | Full Time
1X
12
X2
Under 1.5
12.22
Under 1.5
11.54
Under 1.5
16.47
Over 1.5
1.34
Over 1.5
1.33
Over 1.5
2.45
Multiscores | Full Time
"""
REEL_BTTS = """Double Chance and Both Teams To Score | Full Time
Yes
No
1X
1.68
1X
3.87
12
1.77
12
3.30
X2
2.67
X2
9.51
"""
REEL_1X2 = """1X2 and Over/Under | Full Time
1
X
2
Over 2.5
1.93
Over 2.5
7.97
Over 2.5
5.03
"""


def test_reel_double_chance_total():
    r = parse_combines(REEL_TOTAL)
    assert r["dc_total_1.5"] == {"1N|moins": 12.22, "12|moins": 11.54, "N2|moins": 16.47, "1N|plus": 1.34, "12|plus": 1.33, "N2|plus": 2.45}


def test_reel_double_chance_btts():
    assert parse_combines(REEL_BTTS)["dc_btts"] == {"1N|Oui": 1.68, "1N|Non": 3.87, "12|Oui": 1.77, "12|Non": 3.3, "N2|Oui": 2.67, "N2|Non": 9.51}


def test_reel_1x2_total():
    assert parse_combines(REEL_1X2)["1x2_total_2.5"] == {"1|plus": 1.93, "N|plus": 7.97, "2|plus": 5.03}


def test_reel_colonne_manquante_rien_n_est_devine():
    incomplet = REEL_TOTAL.replace("Under 1.5\n16.47\n", "")          # 2 cotes pour 3 colonnes : la ligne est ignorée
    r = parse_combines(incomplet)
    assert "1N|moins" not in r.get("dc_total_1.5", {}) and r["dc_total_1.5"]["N2|plus"] == 2.45


def test_reel_mi_temps_et_cote_illisible_ignorees():
    assert parse_combines(REEL_BTTS.replace("Full Time", "First Half")) == {}
    assert "dc_btts" not in parse_combines(REEL_BTTS.replace("1.68", "suspendu").replace("3.87", "-")) or \
        "1N|Oui" not in parse_combines(REEL_BTTS.replace("1.68", "suspendu").replace("3.87", "-"))["dc_btts"]


def test_reel_relevé_complet_de_la_collecte():
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "diagnostic" / "betpawa_combines.json"
    if not f.exists():
        pytest.skip("relevé absent")
    rel = json.loads(f.read_text(encoding="utf-8"))["releves"]
    avec = [x for x in rel if x["blocs_combines"]]
    assert avec and all(parse_combines("\n".join(sum(x["blocs_combines"], []))) for x in avec)
