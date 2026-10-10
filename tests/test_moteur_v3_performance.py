"""Indice de performance du marché V3 : scénarios moyen/pire croisés (décision de Patrick, 10/10/2026)."""
import itertools

import pytest

from moteur_v3.markets import gagne
from moteur_v3.performance import indice_performance, marge, profils


def _m(*scores):
    return [{"buts_marques": a, "buts_encaisses": b} for a, b in scores]


BORO = _m((2, 1), (3, 1), (4, 3), (2, 2))
WOLVES = _m((3, 1), (2, 4), (2, 2), (1, 0))   # buts marqués/encaissés de Wolves à l'extérieur


def test_exemple_virton_hasselt_under_35_donne_1_sur_4():
    # pire Virton 3-0 (marque 3) et pire Hasselt 2-1 (marque 2) : 3 + 2 = 5 buts, non validé (règle de Patrick)
    virton = _m((3, 0), (0, 1), (3, 0))
    hasselt = _m((1, 0), (0, 3), (2, 1))
    r = indice_performance("under_3_5", virton, hasselt)
    assert (r["pire_domicile"]["marque"], r["pire_exterieur"]["marque"]) == (3.0, 2.0)
    assert [(s["buts_domicile"], s["buts_exterieur"]) for s in r["scenarios"]] == [(2.0, 1.0), (3.0, 1.0), (2.0, 2.0), (3.0, 2.0)]
    assert [s["valide"] for s in r["scenarios"]] == [True, False, False, False]
    assert (r["indice"], r["libelle"]) == (1, "Risqué")


def test_boro_wolves_over_25_seuls_les_buts_marques_comptent():
    r = indice_performance("over_2_5", BORO, WOLVES)
    assert [(s["buts_domicile"], s["buts_exterieur"]) for s in r["scenarios"]] == [(2.75, 2.0), (2.0, 2.0), (2.75, 1.0), (2.0, 1.0)]
    assert r["indice"] == 4


def test_moyennes_simples():
    r = indice_performance("over_2_5", BORO, WOLVES)
    assert r["moyenne_domicile"] == {"marque": 2.75, "encaisse": 1.75}
    assert r["moyenne_exterieur"] == {"marque": 2.0, "encaisse": 1.75}


def test_niveaux_4_2_1_0():
    # over 2,5 ; domicile marque/encaisse, extérieur marque/encaisse
    assert indice_performance("over_2_5", _m((3, 2)), _m((2, 3)))["indice"] == 4          # 5 buts partout
    r2 = indice_performance("over_2_5", _m((2, 2)), _m((4, 4), (0, 0)))
    assert (r2["indice"], r2["libelle"]) == (2, "Attention")
    r1 = indice_performance("over_2_5", _m((4, 4), (0, 0)), _m((4, 4), (0, 0)))
    assert (r1["indice"], r1["libelle"]) == (1, "Risqué")
    r0 = indice_performance("over_5_5", _m((1, 0)), _m((0, 1)))
    assert (r0["indice"], r0["libelle"]) == (0, "Très risqué")


def test_un_seul_match_par_equipe_donne_0_ou_4():
    assert indice_performance("over_2_5", _m((2, 2)), _m((2, 2)))["indice"] == 4
    assert indice_performance("over_2_5", _m((1, 0)), _m((0, 1)))["indice"] == 0


def test_pire_exterieur_est_oriente_du_point_de_vue_de_l_exterieur():
    # victoire extérieure : le pire match de l'extérieur est celui où il marque le moins
    p = profils(_m((3, 0), (0, 2)), "1x2_2", False)
    assert p["pire"] == (0, 2)


def test_egalite_exacte_avec_la_ligne_ne_valide_pas():
    r = indice_performance("over_2_5", _m((1, 1)), _m((1, 0.5)))
    assert all(not s["valide"] for s in r["scenarios"] if abs(s["buts_domicile"] + s["buts_exterieur"] - 2.5) < 1e-9)


@pytest.mark.parametrize("marche", ["score_2_1", "exact_goals_3", "total_pair", "handicap_0_X"])
def test_marche_non_continu_donne_none(marche):
    assert indice_performance(marche, BORO, WOLVES) is None


def test_donnees_vides_donnent_none():
    assert indice_performance("over_2_5", [], WOLVES) is None
    assert indice_performance("over_2_5", BORO, []) is None


MARCHES = ["1x2_1", "1x2_2", "dc_1X", "dc_X2", "dc_12", "btts_yes", "btts_no", "over_2_5", "under_2_5", "over_1_5",
           "home_over_1_5", "away_under_0_5", "clean_home", "clean_away", "clean_home_no", "clean_away_no",
           "handicap_1_1", "handicap_1_2", "handicap_1.5_1", "handicap_1.5_2", "handicap_-1.5_1", "handicap_-1.5_2"]


@pytest.mark.parametrize("marche", MARCHES)
def test_marge_coherente_avec_le_reglement_entier(marche):
    for h, a in itertools.product(range(9), range(9)):
        mg = marge(marche, h, a)
        assert mg is not None and mg != 0
        assert (mg > 0) == bool(gagne(marche, h, a)), (marche, h, a)


JEUX = [(_m((3, 0), (0, 1), (3, 0)), _m((1, 0), (0, 3), (2, 1))), (BORO, WOLVES),
        (_m((0, 0), (1, 1), (2, 0)), _m((1, 1), (0, 2), (3, 3), (0, 0)))]


@pytest.mark.parametrize("marche", MARCHES)
def test_aucun_scenario_n_est_pire_que_le_pire_scenario(marche):
    for dom, ext in JEUX:
        r = indice_performance(marche, dom, ext)
        pire = r["scenarios"][-1]["marge"]
        for x, y in itertools.product(dom, ext):
            assert marge(marche, x["buts_marques"], y["buts_marques"]) >= pire - 1e-9
        assert pire == min(s["marge"] for s in r["scenarios"])


def test_double_chance_12_pire_cas_est_le_nul_le_plus_proche():
    r = indice_performance("dc_12", _m((2, 0), (1, 1)), _m((1, 0), (3, 3)))
    assert (r["pire_domicile"]["marque"], r["pire_exterieur"]["marque"]) == (1, 1)
    assert r["scenarios"][3]["valide"] is False


def test_pire_exterieur_victoire_domicile_est_son_match_le_plus_prolifique():
    r = indice_performance("1x2_1", _m((2, 0), (3, 0)), _m((0, 2), (3, 3), (1, 1)))
    assert (r["pire_domicile"]["marque"], r["pire_exterieur"]["marque"]) == (2, 3)


MARCHES_UNE_EQUIPE = ["home_over_1.5", "home_under_2.5", "away_over_0.5", "away_under_1.5", "clean_home", "clean_away",
                      "clean_home_no", "clean_away_no"]
MARCHES_DEUX_EQUIPES = ["1x2_1", "dc_12", "btts_yes", "over_2_5", "under_3_5", "handicap_1_1"]


@pytest.mark.parametrize("marche", MARCHES_UNE_EQUIPE)
def test_marche_d_une_seule_equipe_a_2_scenarios(marche):
    r = indice_performance(marche.replace(".", "_"), BORO, WOLVES) if marche.count("_") >= 3 else indice_performance(marche, BORO, WOLVES)
    assert r is not None and r["sur"] == 2 and len(r["scenarios"]) == 2


@pytest.mark.parametrize("marche", MARCHES_DEUX_EQUIPES)
def test_marche_des_deux_equipes_garde_4_scenarios(marche):
    assert indice_performance(marche, BORO, WOLVES)["sur"] == 4


def test_domicile_plus_de_1_5_buts():
    # Wycombe-like : moyenne 1,75 valide, pire match (1 but) ne valide pas -> 1/2
    r = indice_performance("home_over_1_5", _m((1, 1), (1, 2), (3, 3), (2, 2)), _m((4, 3), (2, 5), (1, 2)))
    assert (r["indice"], r["sur"], r["libelle"]) == (1, 2, "Attention")
    assert [s["valide"] for s in r["scenarios"]] == [True, False]
    assert r["pire_exterieur"] is None and r["scenarios"][0]["buts_exterieur"] is None


def test_une_seule_equipe_sur_les_deux_scenarios_sur_2():
    assert indice_performance("home_over_1_5", _m((3, 0), (2, 1)), _m((0, 0)))["libelle"] == "Sûr"      # 2/2
    assert indice_performance("away_over_2_5", _m((0, 0)), _m((1, 1), (0, 2)))["indice"] == 0           # 0/2
    assert indice_performance("clean_home", _m((1, 0)), _m((0, 1), (0, 0)))["indice"] == 2               # extérieur ne marque jamais
    assert indice_performance("clean_home", _m((1, 0)), _m((0, 1), (0, 0), (1, 0)))["indice"] == 1      # moyenne 0,33 ok, pire match (1 but) non


def test_phrase_une_equipe_dit_ce_qui_tient():
    d = _m((1, 1), (1, 2), (3, 3), (2, 2))
    assert indice_performance("home_over_1_5", d, WOLVES)["phrase"] == "Tient en moyenne, mais pas dans le pire match."
    assert indice_performance("home_over_0_5", _m((2, 0), (1, 0)), WOLVES)["phrase"] == "Tient en moyenne et dans le pire match."
    assert indice_performance("home_over_3_5", _m((1, 0), (0, 0)), WOLVES)["phrase"] == "Ne tient ni en moyenne ni dans le pire match."


def test_phrase_deux_equipes_compte_les_scenarios():
    assert indice_performance("over_2_5", BORO, WOLVES)["phrase"] == "Validé dans 4 scénarios sur 4."


def _d(*lignes):
    return [{"date": d, "domicile": dom, "buts_marques": a, "buts_encaisses": b} for d, dom, a, b in lignes]


def test_derniers_matchs_tous_lieux_confondus():
    from moteur_v3.performance import derniers_matchs
    ms = _d(("2026-08-01", True, 1, 0), ("2026-08-08", False, 2, 2), ("2026-08-15", True, 0, 1), ("2026-08-22", False, 3, 3))
    r = derniers_matchs(ms, 3)
    assert [m["date"] for m in r] == ["2026-08-08", "2026-08-15", "2026-08-22"]      # domicile ET extérieur mélangés
    assert [m["domicile"] for m in r] == [False, True, False]
    assert len(derniers_matchs(ms)) == 4                                              # moins de 7 : tous
    assert derniers_matchs([]) == []


def test_derniers_matchs_ecarte_les_scores_invalides_et_garde_les_7_plus_recents():
    from moteur_v3.performance import derniers_matchs
    ms = _d(*[(f"2026-09-{i:02d}", i % 2 == 0, i, 0) for i in range(1, 10)])
    ms.append({"date": "2026-09-10", "domicile": True, "buts_marques": None, "buts_encaisses": 1})
    ms.append({"date": "2026-09-11", "domicile": True, "buts_marques": -1, "buts_encaisses": 1})
    r = derniers_matchs(ms)
    assert len(r) == 7 and r[0]["date"] == "2026-09-03" and r[-1]["date"] == "2026-09-09"
    assert derniers_matchs(ms, 2) != r and len(derniers_matchs(ms, 2)) == 2


def test_le_lieu_des_matchs_ne_change_pas_l_indice():
    a = _d(("2026-08-01", True, 3, 0), ("2026-08-08", False, 1, 1), ("2026-08-15", True, 2, 2))
    b = _d(("2026-08-01", False, 3, 0), ("2026-08-08", True, 1, 1), ("2026-08-15", False, 2, 2))
    from moteur_v3.performance import derniers_matchs
    assert indice_performance("over_2_5", derniers_matchs(a), derniers_matchs(a)) == indice_performance("over_2_5", derniers_matchs(b), derniers_matchs(b))
