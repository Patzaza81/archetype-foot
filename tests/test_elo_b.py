"""Piste B′ : règle de décision et vraisemblance du score (cas qui passent ET cas qui échouent)."""
import math

import numpy as np
import pytest

from moteur_dc import elo as EB, modele as MO


def test_regle_retenue_sur_gain_plante():
    rng = np.random.default_rng(1)
    d = rng.normal(0.03, 0.1, 800)
    assert EB.bootstrap(d, np.random.default_rng(2))["retenu"]


def test_regle_non_retenue_sans_gain():
    rng = np.random.default_rng(3)
    d = rng.normal(0.0, 0.1, 800)
    r = EB.bootstrap(d, np.random.default_rng(4))
    assert not r["retenu"] and r["ic95"][0] < 0 < r["ic95"][1]


def test_regle_non_retenue_sur_perte():
    rng = np.random.default_rng(5)
    d = rng.normal(-0.03, 0.1, 800)
    assert not EB.bootstrap(d, np.random.default_rng(6))["retenu"]


def test_mde_suit_la_dispersion_et_la_taille():
    rng = np.random.default_rng(7)
    petit = EB.bootstrap(rng.normal(0, 0.1, 100), np.random.default_rng(8))
    grand = EB.bootstrap(rng.normal(0, 0.1, 1600), np.random.default_rng(9))
    assert petit["mde"] > grand["mde"] and grand["mde"] == pytest.approx(1.96 * grand["sd_match"] / math.sqrt(1600))


def test_ll_match_est_le_log_de_la_case_du_score():
    r = {"lh": 1.5, "la": 1.0, "rho": -0.04, "h": 2, "a": 1}
    assert EB.ll_match(r) == pytest.approx(math.log(MO.grille(1.5, 1.0, -0.04)[2, 1]))


def test_ll_match_plus_vraisemblable_quand_l_espérance_colle_au_score():
    base = {"rho": -0.04, "h": 3, "a": 0}
    assert EB.ll_match({**base, "lh": 3.0, "la": 0.4}) > EB.ll_match({**base, "lh": 0.6, "la": 2.0})


def test_ll_match_facteur_de_niveau_change_la_vraisemblance():
    r = {"lh": 1.5, "la": 1.0, "rho": -0.04, "h": 2, "a": 1}
    assert EB.ll_match(r, 1.0) != EB.ll_match(r, 1.2)
