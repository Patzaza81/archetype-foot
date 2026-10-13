import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import echantillon as X  # noqa: E402


def l(mid, lib, o, gagne):
    return dict(mid=mid, lib=lib, o=o, profit=(o - 1) if gagne else -1.0, r=1 if gagne else -1)


def cellule_gagnante(n=10):
    return [l(f"m{i}", "BTTS - oui", 1.9, True) for i in range(n)]


def test_ajuste_garde_cellule_rentable():
    assert X.cle("BTTS - oui", 1.9) in X.ajuste_cellules(cellule_gagnante(10))
    assert X.cle("BTTS - oui", 1.9) in X.ajuste_cellules(cellule_gagnante(25))
    assert len(X.ajuste_cellules(cellule_gagnante(12), min_paris=10, roi_min=0.3)) == 1


def test_ajuste_rejette_cellule_non_rentable_ou_trop_petite():
    assert X.ajuste_cellules(cellule_gagnante(9)) == {}                          # < 10 paris
    perdante = [l(f"m{i}", "BTTS - non", 1.9, False) for i in range(20)]
    assert X.ajuste_cellules(perdante) == {}                                     # ROI < 0
    mitigee = [l(f"m{i}", "X", 2.0, i % 2 == 0) for i in range(20)]
    assert X.ajuste_cellules(mitigee) == {}                                      # ROI 0 < 30 %


def test_choisir_un_pari_par_match_meilleure_cellule():
    L = [l("a", "A", 1.9, True), l("a", "B", 1.9, True), l("b", "A", 1.9, True)]
    cell = {X.cle("A", 1.9): 0.5, X.cle("B", 1.9): 0.9}
    S = X.choisir(L, cell)
    assert [(p["mid"], p["lib"]) for p in S] == [("a", "B"), ("b", "A")]


def test_choisir_ignore_cellules_inconnues():
    assert X.choisir([l("a", "Z", 1.9, True)], {X.cle("A", 1.9): 0.5}) == []
    assert X.choisir([l("a", "A", 3.5, True)], {X.cle("A", 1.9): 0.5}) == []      # autre tranche de cote
    assert X.choisir([], {X.cle("A", 1.9): 0.5}) == []
