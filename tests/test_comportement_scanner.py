import pytest
from matrice_scenarios import comportement as C, scanner_marches as S


def test_profil_favori_domicile():
    p = C.profil([(3, 0), (2, 0), (3, 1)], [(0, 2), (0, 3), (1, 2)])
    assert p["favori"] == "domicile" and p["victoire_dom"] > 0.6


def test_grille_somme_un():
    g = C.grille(1.4, 1.1)
    assert sum(map(sum, g)) == pytest.approx(1.0)


def test_scores_extremes_plafonnes():
    a = C.buts_attendus([(9, 0), (1, 1), (1, 1)], [(1, 1)] * 3)
    b = C.buts_attendus([(4, 0), (1, 1), (1, 1)], [(1, 1)] * 3)
    assert a == b


@pytest.mark.parametrize("groupe,sel,score,attendu", [
    ("1x2", "1", (2, 1), True), ("btts", "Oui", (2, 0), False), ("handicap_3issues_-1", "1", (2, 0), True),
    ("handicap_-1.5", "domicile", (1, 0), False), ("over_under_exterieur_1.5", "plus", (0, 2), True),
    ("cages_inviolees_domicile", "oui", (1, 1), False), ("nombre_exact_buts", "6+", (4, 3), True), ("score_exact", "1-1", (1, 2), False)])
def test_marches(groupe, sel, score, attendu):
    assert S.test_du_marche(groupe, sel)(*score) is attendu


def test_groupe_inconnu_signale_non_lu():
    g = C.grille(1.4, 1.1)
    ms, nl = S.scanner(g, {"inconnu": {"x": 2.0}, "1x2": {"1": 2.0}})
    assert len(ms) == 1 and nl == ["inconnu:x"]


def test_choix_respecte_cote_min():
    ms = [{"cote": 1.20, "probabilite": 0.9}, {"cote": 1.30, "probabilite": 0.7}, {"cote": 1.8, "probabilite": 0.4}]
    assert S.choisir(ms)["cote"] == 1.30 and S.choisir([ms[0]]) is None
