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
    # V2 inchangée : l'ancienne clé reste produite exactement comme avant (lignes « Domicile -N » seulement).
    assert got["handicap_3choix_1"] == {"domicile": 2.05, "nul": 3.50, "exterieur": 1.72}
    assert got["handicap_3choix_2"] == {"domicile": 3.10, "nul": 4.20, "exterieur": 1.35}
    assert not any(k.startswith("handicap_3choix_-") for k in got)


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


def test_calibration_signature_dedoublonne_un_evenement_equivalent():
    from moteur_v3_pipeline import _signature_evenement_calibration
    assert _signature_evenement_calibration("handicap_1_1") == _signature_evenement_calibration("handicap_1.5_1")
    # Domicile +1 issue 2 = extérieur gagne par 2 buts ou plus = Handicap extérieur -1,5 (V3 handicap_-1.5_2).
    assert _signature_evenement_calibration("handicap_-1_2") == _signature_evenement_calibration("handicap_-1.5_2")
    assert _signature_evenement_calibration("handicap_-1_2") != _signature_evenement_calibration("handicap_1.5_2")
    assert _signature_evenement_calibration("handicap_2_2") != _signature_evenement_calibration("dc_X2")


# Format RÉEL de la capture BetPawa du 28/09 (colonne X étiquetée « Domicile -2 », lignes + étiquetées « Extérieur -1 »).
BLOC_FR_REEL = """Handicap À 3 Choix | Fin de Match
1
X
2
Domicile -2
15.43
Domicile -2
7.94
Extérieur +2
1.11
Domicile -1
5.81
Domicile -1
4.45
Extérieur +1
1.44
Domicile +1
1.43
Extérieur -1
4.49
Extérieur -1
5.96
Domicile +2
1.11
Extérieur -2
8.07
Extérieur -2
15.93
Impair/Pair | Fin de Match
Impair
1.90
Pair
1.85
"""


def test_fr_reel_quatre_lignes():
    got = parse_betpawa(BLOC_FR_REEL, "A", "B")
    assert got["handicap_3issues_-2"] == {"1": 15.43, "X": 7.94, "2": 1.11}
    assert got["handicap_3issues_-1"] == {"1": 5.81, "X": 4.45, "2": 1.44}
    assert got["handicap_3issues_1"] == {"1": 1.43, "X": 4.49, "2": 5.96}
    assert got["handicap_3issues_2"] == {"1": 1.11, "X": 8.07, "2": 15.93}


def test_fr_reel_section_suivante_intacte():
    assert parse_betpawa(BLOC_FR_REEL, "A", "B")["pair_impair"] == {"pair": 1.85, "impair": 1.90}


def test_fr_reel_v2_ne_recoit_rien_de_nouveau():
    # L'ancienne lecture ne reconnaissait pas ce format : la V2 ne reçoit toujours aucune clé « handicap_3choix ».
    assert not any(k.startswith("handicap_3choix") for k in parse_betpawa(BLOC_FR_REEL, "A", "B"))


def test_fr_cote_illisible_arrete_la_lecture():
    got = parse_betpawa(BLOC_FR_REEL.replace("4.45", "SUSPENDU"), "A", "B")
    assert "handicap_3issues_-2" in got and "handicap_3issues_-1" not in got and "handicap_3issues_1" not in got


def test_fr_premiere_etiquette_exterieur_refusee():
    texte = "Handicap À 3 Choix | Fin de Match\nExtérieur +2\n1.11\nDomicile -2\n7.94\nDomicile -2\n15.43\n"
    assert not any(k.startswith("handicap_3") for k in parse_betpawa(texte, "A", "B"))


def test_fr_ligne_3_ignoree():
    texte = BLOC_FR_REEL.replace("Domicile +2\n1.11", "Domicile +3\n1.11")
    got = parse_betpawa(texte, "A", "B")
    assert "handicap_3issues_2" not in got and "handicap_3issues_3" not in got and "handicap_3issues_1" in got
