import json

from parse_betpawa import parse_betpawa
from parse_betpawa_playwright import parse_betpawa_playwright
from parse_betpawa_url import parse_betpawa_url


def test_parse_fr_preserve_signed_lines():
    texte = """Handicap À 3 Choix | Fin de Match
1
X
2
Domicile -2
3.10
Nul -2
4.20
Extérieur +2
1.35
Domicile -1
2.05
Nul -1
3.50
Extérieur +1
1.72
Domicile +1
1.28
Nul +1
4.00
Extérieur -1
8.00
Domicile +2
1.12
Nul +2
5.00
Extérieur -2
18.00
"""
    got = parse_betpawa(texte, "Alpha", "Beta")
    assert got["handicap_3issues_-2"] == {"1": 3.10, "X": 4.20, "2": 1.35}
    assert got["handicap_3issues_-1"] == {"1": 2.05, "X": 3.50, "2": 1.72}
    assert got["handicap_3issues_1"] == {"1": 1.28, "X": 4.00, "2": 8.00}
    assert got["handicap_3issues_2"] == {"1": 1.12, "X": 5.00, "2": 18.00}
    assert "handicap_3choix_1" not in got


def test_playwright_preserve_signed_lines():
    texte = """3-Way Handicap | Full Time
1
X
2
Home -2
3.10
Home -2
4.20
Away +2
1.35
Home +1
1.28
Home +1
4.00
Away -1
8.00
"""
    got = parse_betpawa_playwright(texte, "Alpha", "Beta")
    assert got["handicap_3issues_-2"] == {"1": 3.10, "X": 4.20, "2": 1.35}
    assert got["handicap_3issues_1"] == {"1": 1.28, "X": 4.00, "2": 8.00}


def test_url_parser_preserve_signed_lines():
    texte = """3-Way Handicap | Full Time
- 1
- X
- 2
Home -2 3.10
Home -2 4.20
Away +2 1.35
Home +1 1.28
Home +1 4.00
Away -1 8.00
"""
    got = parse_betpawa_url(texte, "Alpha", "Beta")
    assert got["handicap_3issues_-2"] == {"1": 3.10, "X": 4.20, "2": 1.35}
    assert got["handicap_3issues_1"] == {"1": 1.28, "X": 4.00, "2": 8.00}


def test_v3_normalisation_conserve_la_ligne_et_les_trois_issues():
    from moteur_v3_pipeline import cotes_etendues

    enreg = {
        "cotes_betpawa": {
            "handicap_3issues_-2": {"1": 3.10, "X": 4.20, "2": 1.35},
            "handicap_3issues_-1": {"1": 2.05, "X": 3.50, "2": 1.72},
            "handicap_3issues_1": {"1": 1.28, "X": 4.00, "2": 8.00},
            "handicap_3issues_2": {"1": 1.12, "X": 5.00, "2": 18.00},
        }
    }
    got = cotes_etendues(enreg)
    assert got["handicap_2_1"] == 3.10
    assert got["handicap_2_X"] == 4.20
    assert got["handicap_2_2"] == 1.35
    assert got["handicap_1_1"] == 2.05
    assert got["handicap_1_X"] == 3.50
    assert got["handicap_1_2"] == 1.72
    assert got["handicap_-1_1"] == 1.28
    assert got["handicap_-1_X"] == 4.00
    assert got["handicap_-1_2"] == 8.00
    assert got["handicap_-2_1"] == 1.12
    assert got["handicap_-2_X"] == 5.00
    assert got["handicap_-2_2"] == 18.00
