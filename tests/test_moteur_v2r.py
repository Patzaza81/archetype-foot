"""Tests de v2r : données synthétiques uniquement."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import calibration as C, modele as M, selection as S, evaluation as E  # noqa: E402


def L(mid, lib, o, ev):
    return dict(mid=mid, lib=lib, o=o, ev=ev)


def test_ev_valeurs_exactes():
    assert abs(S.ev(0.5, 2.0) - 0.0) < 1e-12
    assert abs(S.ev(0.6, 2.0) - 0.2) < 1e-12
    assert S.ev(0.4, 2.0) < 0


def test_choisir_cas_qui_passent():
    sel = S.choisir([L("a", "x", 1.5, 0.05), L("b", "y", 2.0, 0.10)], 0.03, 1.3, 3.0)
    assert {l["mid"] for l in sel} == {"a", "b"}
    assert S.choisir([L("a", "x", 1.3, 0.03)], 0.03, 1.3, 3.0)           # bornes basses incluses
    assert S.choisir([L("a", "x", 2.99, 0.5)], 0.03, 1.3, 3.0)


def test_choisir_cas_qui_echouent():
    assert S.choisir([L("a", "x", 1.5, 0.02)], 0.03, 1.3, 3.0) == []     # EV trop basse
    assert S.choisir([L("a", "x", 3.0, 0.5)], 0.03, 1.3, 3.0) == []      # borne haute exclue
    assert S.choisir([L("a", "x", 1.2, 0.5)], 0.03, 1.3, 3.0) == []      # cote trop basse


def test_choisir_un_seul_pari_par_match_le_meilleur_ev():
    sel = S.choisir([L("a", "x", 1.5, 0.05), L("a", "y", 1.6, 0.09), L("b", "z", 1.5, 0.04)], 0.0, 1.0, 9.0)
    assert [(l["mid"], l["lib"]) for l in sel] == [("a", "y"), ("b", "z")]


def test_poisson_et_probas_coherentes():
    assert abs(sum(M.poisson_row(1.4)) - 1.0) < 1e-12
    G = M.grille(1.5, 1.1)
    pr = M.probas(G, ["Plus de 2.5 buts", "Moins de 2.5 buts"])
    s = sum(G[i][j] for i in range(M.MAXG + 1) for j in range(M.MAXG + 1))
    a, b = pr["Plus de 2.5 buts"][0], pr["Moins de 2.5 buts"][0]
    assert abs(a + b - s) < 1e-9
    assert M.probas(G, ["libellé inconnu xyz"]) == {}


def test_calibration_retrouve_un_signal_sur_la_cote():
    import random
    r = random.Random(3)
    X, y = [], []
    for _ in range(3000):
        p = r.uniform(0.2, 0.8)
        o = 1 / p
        X.append(C.features(0.5, o))
        y.append(1 if r.random() < p else 0)
    w = C.ajuste(X, y)
    assert w[2] > 0.7 and abs(w[1]) < 0.5      # le poids va à la cote, pas au modèle constant


def test_roi_et_bootstrap():
    S_ = [dict(mid="a", profit=1.0), dict(mid="b", profit=-1.0)]
    assert E.roi(S_) == 0.0 and E.roi([]) is None
    lo, hi = E.bootstrap(S_, n=200)
    assert lo <= 0.0 <= hi and E.bootstrap([]) is None
