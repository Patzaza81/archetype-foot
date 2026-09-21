"""Statistiques « combinées » = matchs des DEUX équipes (correctif du 21/09/2026, cas réel Dallas-Austin :
2 matchs à domicile pour Dallas, 6 à l'extérieur pour Austin -> phrase « des deux équipes » calculée sur Austin seule)."""
import pytest

import bibliotheque_justification as bj


def dom(n, gf=2, ga=1):
    return [{"domicile": True, "buts_marques": gf, "buts_encaisses": ga}] * n


def ext(n, gf=2, ga=1):
    return [{"domicile": False, "buts_marques": gf, "buts_encaisses": ga}] * n


CHAMPS = ("over_rate_combined", "over_15_rate_combined", "avg_goals_conceded_combined", "both_teams_score_rate", "draw_rate_combined")


@pytest.mark.parametrize("nd,ne", [(3, 3), (5, 4), (12, 12), (3, 8)])
def test_les_deux_equipes_ont_assez_de_matchs_la_statistique_combinee_existe(nd, ne):
    d = bj.construit_donnees("over_under_total_2.5_over", dom(nd), ext(ne), [])
    assert all(d[c] is not None for c in CHAMPS), d


@pytest.mark.parametrize("nd,ne", [(2, 6), (6, 2), (0, 8), (8, 0), (2, 2), (1, 12)])
def test_une_seule_equipe_avec_assez_de_matchs_aucune_statistique_combinee(nd, ne):
    d = bj.construit_donnees("over_under_total_2.5_over", dom(nd), ext(ne), [])
    assert all(d[c] is None for c in CHAMPS), d


def test_cas_reel_dallas_pas_de_phrase_des_deux_equipes_sur_une_seule_equipe():
    a = dom(2, 2, 1)                                   # Dallas : 2 matchs à domicile seulement
    b = ext(6, 2, 2)                                   # Austin : 6 matchs à l'extérieur, tous à plus de 2,5 buts
    r = bj.construit_justification_bibliotheque("over_under_total_2.5_over", a, b, [], nom_domicile="Dallas", nom_exterieur="Austin")
    assert r["resume"] is None and not any("des deux équipes" in p["texte"] for p in r["preuves"])


def test_avec_les_deux_equipes_la_phrase_est_produite_et_juste():
    r = bj.construit_justification_bibliotheque("over_under_total_2.5_over", dom(4, 2, 2), ext(4, 2, 2), [], nom_domicile="A", nom_exterieur="B")
    assert r["resume"].startswith("Rythme offensif : plus de 2,5 buts dans 100.0% des matchs récents des deux équipes")


def test_les_preuves_propres_a_une_equipe_restent_disponibles_sans_l_autre():
    # la série « sans défaite » de l'équipe à domicile n'a pas besoin des matchs de la visiteuse
    matchs = [{"domicile": True, "buts_marques": 2, "buts_encaisses": 0}] * 5
    r = bj.construit_justification_bibliotheque("double_chance_1X", matchs, [], [], nom_domicile="A", nom_exterieur="B")
    assert r["resume"].startswith("Régularité à domicile : A reste sur 5 matchs sans défaite")
