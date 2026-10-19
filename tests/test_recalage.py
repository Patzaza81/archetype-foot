import pytest
from matrice_scenarios import comportement as C, recalage as R, scanner_marches as S


@pytest.mark.parametrize("g,f", [("over_under_2.5", "over_under"), ("handicap_-1.5", "handicap"), ("handicap_3issues_-1", "handicap_3issues"),
                                 ("over_under_domicile_1.5", "over_under_domicile"), ("double_chance", "double_chance"), ("score_exact", "score_exact")])
def test_famille(g, f):
    assert R.famille(g) == f


def test_isotone_croissante():
    paires = [(i / 100, int(i % 3 == 0)) for i in range(100)] * 3
    c = R.isotone(paires, blocs=10)
    assert all(c[i][1] <= c[i + 1][1] for i in range(len(c) - 1))


def test_appliquer_sans_courbe_et_bornes():
    assert R.appliquer([], 0.7) == 0.7
    assert 0.0 <= R.appliquer([(0.5, 0.4), (0.9, 0.8)], 1.5) <= 1.0
    assert R.appliquer([(0.5, 0.4), (0.9, 0.8)], 0.7) == pytest.approx(0.6)


def test_appliquer_ne_depasse_jamais_0_1():
    assert R.appliquer([(0.1, 0.0), (0.2, 0.05)], 0.0) == 0.0
    assert R.appliquer([(0.8, 0.99), (0.9, 1.0)], 1.0) == 1.0


def test_profil_accepte_rho():
    assert C.profil([(1, 1)] * 3, [(1, 1)] * 3, rho=0.1)["favori"] in ("équilibré", "domicile", "extérieur")


@pytest.mark.parametrize("g,s", [("over_under_2", "plus"), ("over_under_domicile_1", "moins"), ("handicap_1", "domicile"), ("handicap_0", "exterieur")])
def test_lignes_entieres_non_lues(g, s):
    assert S.test_du_marche(g, s) is None


@pytest.mark.parametrize("g,s", [("over_under_2.5", "plus"), ("handicap_-1.5", "domicile"), ("handicap_0.5", "exterieur")])
def test_lignes_demi_lues(g, s):
    assert S.test_du_marche(g, s) is not None
