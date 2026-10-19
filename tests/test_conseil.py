import pytest
from matrice_scenarios import conseil as K

COTES = {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "double_chance": {"1N": 1.3, "N2": 2.5, "12": 1.2}, "btts": {"Oui": 2.0, "Non": 1.7}}
DOM, EXT = [(3, 0), (2, 0), (3, 1), (2, 1)], [(0, 2), (0, 3), (1, 2), (0, 1)]


def test_quatre_conseillers_et_toutes_selections():
    pr, ms, nl = K.probas_par_conseiller(DOM, EXT, COTES)
    assert set(pr) == set(K.CONSEILLERS) and len(ms) == 8 and nl == []
    assert all(len(v) == 8 for v in pr.values())


def test_probas_entre_0_et_1():
    pr, _, _ = K.probas_par_conseiller(DOM, EXT, COTES)
    assert all(0 < p < 1 for v in pr.values() for p in v.values())


@pytest.mark.parametrize("mode", ["poisson", "moyenne", "prudent"])
def test_choix_respecte_cote_min(mode):
    pr, ms, _ = K.probas_par_conseiller(DOM, EXT, COTES)
    assert K.president(pr, ms, mode)["cote"] >= 1.26


def test_aucun_marche_sous_cote_min():
    pr, ms, _ = K.probas_par_conseiller(DOM, EXT, {"1x2": {"1": 1.1, "N": 1.2, "2": 1.05}})
    assert K.president(pr, ms, "poisson") is None


def test_favori_clair_prefere_victoire_ou_double_chance_domicile():
    pr, ms, _ = K.probas_par_conseiller(DOM, EXT, COTES)
    assert K.president(pr, ms, "poisson")["groupe"] in ("1x2", "double_chance")


def test_unanime_ecarte_si_desaccord():
    pr, ms, _ = K.probas_par_conseiller(DOM, EXT, COTES)
    for k in pr["croisement"]:
        pr["croisement"][k] = 0.01
        pr["poisson"][k] = 0.9
    assert K.president(pr, ms, "unanime") is None
