"""Tests de la couche de robustesse de l'alpha (cahier des charges du 23/10/2026)."""
from alpha_serie import robustesse as R


def _grille(cle):
    for c, _, p, z in R.catalogue():
        if c == cle:
            return R.grilles(p, z)
    raise KeyError(cle)


def test_juste_au_seuil_plus_1_5():
    passe, solide = _grille(("over_under_1.5", "plus"))
    assert solide[2][1] and solide[3][0] and solide[2][2]          # 3 buts et plus : solide
    assert not solide[1][1] and not solide[2][0] and not solide[0][2]  # 2 buts pile : juste au seuil
    assert not passe[1][0]


def test_juste_double_chance_et_victoire():
    _, solide = _grille(("double_chance", "1N"))
    assert solide[1][0] and solide[2][0] and solide[3][1]          # victoire du domicile : solide
    assert not solide[0][0] and not solide[1][1] and not solide[2][2]  # passe grâce au nul : juste
    _, sv = _grille(("1x2", "1"))
    assert sv[2][0] and sv[3][1] and sv[4][2]
    assert not sv[1][0] and not sv[2][1] and not sv[3][2]          # gagné d'un seul but : juste


def test_marches_zero_but_exemptes():
    _, solide = _grille(("btts", "Non"))
    assert solide[0][0] and solide[3][0] and solide[0][2]
    assert not solide[1][1] and not solide[2][1] and not solide[1][3]


def test_defavorable_pire_des_quatre_coins():
    passe, solide = _grille(("over_under_1.5", "plus"))
    # (A, C, B, D) : domicile marque 3 / extérieur encaisse 2 ; extérieur marque 1 / domicile encaisse 1 -> coins (2..3, 1..1) : 3 et 4 buts
    assert R.lecture_paire((3, 2, 1, 1), passe, solide) == (1, 1)
    # coin le plus fermé (1, 0) : 1 but -> le défavorable tombe, l'habituel (2, 1) passe
    assert R.lecture_paire((2, 1, 1, 0), passe, solide) == (0, 1)
    assert R.lecture_paire((0, 0, 0, 0), passe, solide) == (0, 0)


def test_combo_juste_si_une_jambe_juste():
    _, solide = _grille(("combo", "1N+plus_1.5"))
    assert solide[3][0] and solide[2][1] and solide[4][1]          # aucune jambe ne tombe avec un but de plus ou de moins
    assert not solide[3][3]                                        # nul : jambe 1N juste
    assert not solide[2][0] and not solide[1][1]                   # 2 buts pile : jambe total juste


def test_wilson_et_effectif_minimum():
    assert R.wilson_bas(16, 16) >= R.SEUIL_WILSON
    assert R.wilson_bas(15, 15) < R.SEUIL_WILSON                   # un petit groupe parfait ne suffit pas
    assert R.wilson_bas(0, 0) == 0.0


def test_verdict_stabilite_table_gelee():
    passe, solide = _grille(("over_under_1.5", "plus"))
    prs = [(3, 3, 2, 2)] * 4
    cle = ("over_under_1.5", "plus")
    ok = {"retenu": True}
    cel = {R.cle_cellule(cle, 4, 4, 4): ok, R.cle_cellule(cle, 3, 3, 3): ok}
    assert R.verdict(prs, cle, passe, solide, cel)["statut"] == "retenu"
    cel_instable = {R.cle_cellule(cle, 4, 4, 4): ok, R.cle_cellule(cle, 3, 3, 3): {"retenu": False}}
    assert R.verdict(prs, cle, passe, solide, cel_instable)["statut"] == "instable"
    assert R.verdict(prs, cle, passe, solide, {})["statut"] == "abstention"
    assert R.verdict(prs[:3], cle, passe, solide, cel)["statut"] == "exclu"
