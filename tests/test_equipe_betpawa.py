import pytest

from equipe_betpawa import cote_de_l_equipe, memes_equipes
from parse_betpawa import parse_betpawa

ATTACH = """Plus de/Moins de | AS Saint-Etienne | Fin de match
Plus de 1.5
1.31
Moins de 1.5
2.97
Plus de/Moins de | Rodez Aveyron Football | Fin de match
Plus de 0.5
1.50
Moins de 0.5
2.32
Cages Inviolées | AS Saint-Etienne | Fin de Match
Oui
2.35
Non
1.53
"""


@pytest.mark.parametrize("a,b", [("AS Saint-Etienne", "Saint-Étienne"), ("Rodez Aveyron Football", "Rodez"),
                                 ("Paris FC", "Paris"), ("Real Madrid", "Real Madrid"), ("FC Zürich", "Zurich")])
def test_memes_equipes_oui(a, b):
    assert memes_equipes(a, b)


@pytest.mark.parametrize("a,b", [("Real Madrid", "Real Madrid II"), ("Rodez", "Saint-Étienne"), ("Manchester United", "Manchester City"), ("Bayern Munich", "Bayern Munich U19"), ("", "Rodez")])
def test_memes_equipes_non(a, b):
    assert not memes_equipes(a, b)


def test_cote_de_l_equipe():
    assert cote_de_l_equipe("AS Saint-Etienne", "Saint-Étienne", "Rodez") == "domicile"
    assert cote_de_l_equipe("Rodez Aveyron Football", "Saint-Étienne", "Rodez") == "exterieur"
    assert cote_de_l_equipe("Lyon", "Saint-Étienne", "Rodez") is None
    assert cote_de_l_equipe("Paris Saint-Germain", "Paris FC", "Paris Saint-Germain") == "exterieur"


def test_le_parseur_garde_les_marches_par_equipe_quand_les_noms_different():
    r = parse_betpawa(ATTACH, "Saint-Étienne", "Rodez")
    assert r["over_under_domicile_1.5"] == {"plus": 1.31, "moins": 2.97}
    assert r["over_under_exterieur_0.5"] == {"plus": 1.5, "moins": 2.32}
    assert r["cages_inviolees_domicile"] == {"oui": 2.35, "non": 1.53}


def test_le_parseur_ignore_une_equipe_inconnue():
    r = parse_betpawa(ATTACH, "Lyon", "Nice")
    assert not any(k.startswith(("over_under_domicile", "over_under_exterieur", "cages")) for k in r)
