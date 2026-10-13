import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import integration as I  # noqa: E402


def l(mid, lib, o, gagne, profil=(1, 1)):
    return dict(mid=mid, lib=lib, o=o, profit=(o - 1) if gagne else -1.0, r=1 if gagne else -1, profil=profil)


def test_classe_cas_qui_passent():
    assert I.classe(2.0, I.COUPURES_LIGUE) == 0
    assert I.classe(2.5, I.COUPURES_LIGUE) == 1      # borne incluse dans la classe haute
    assert I.classe(3.5, I.COUPURES_LIGUE) == 2


def test_classe_cas_qui_echouent():
    assert I.classe(2.49, I.COUPURES_LIGUE) != 1
    assert I.classe(2.9, I.COUPURES_LIGUE) != 1
    assert I.classe(1.0, I.COUPURES_MATCH) != 2


def test_cellule_separee_par_profil():
    L = [l(f"a{i}", "BTTS - oui", 1.9, True, (2, 2)) for i in range(10)] + \
        [l(f"b{i}", "BTTS - oui", 1.9, False, (0, 0)) for i in range(10)]
    c = I.ajuste(L)
    assert len(c) == 1 and list(c)[0][2:] == (2, 2)          # le profil bas, perdant, est rejeté
    assert I.choisir([l("z", "BTTS - oui", 1.9, True, (0, 0))], c) == []
    assert len(I.choisir([l("z", "BTTS - oui", 1.9, True, (2, 2))], c)) == 1


def test_ajuste_seuils():
    assert I.ajuste([l(f"a{i}", "X", 1.9, True) for i in range(9)]) == {}            # < 10 paris
    assert I.ajuste([l(f"a{i}", "X", 1.9, False) for i in range(20)]) == {}          # perdant
    assert len(I.ajuste([l(f"a{i}", "X", 1.9, True) for i in range(10)])) == 1


def test_moyenne_buts_ligue():
    m = dict(ligue="L", hd=[dict(buts_marques=2, buts_encaisses=1)], he=[dict(buts_marques=1, buts_encaisses=0)])
    assert I.moyenne_buts_ligue([m]) == {"L": 2.0}
    assert I.moyenne_buts_ligue([]) == {}
