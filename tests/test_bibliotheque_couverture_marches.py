"""Couverture des textes de justification par marché (21/09/2026).

Règle du projet : un marché retenu doit avoir un texte SPÉCIFIQUE à ce marché, calculé
exactement sur les historiques réels, sinon NO DATA -> NO GO. Ces tests verrouillent :
  - le NameError de la branche X2 / 1x2_exterieur (introduit le 20/09/2026, commit 6f60b3b) ;
  - un texte par famille de marché (nul, double chance 12, BTTS non, lignes de buts
    quelconques, buts d'une équipe), avec pour chacune au moins 3 cas qui DOIVENT
    produire un texte et 3 qui NE DOIVENT PAS en produire ;
  - l'absence de toute exception, quelles que soient les données.
Chaque « cas qui ne doit pas produire de texte » est construit pour ne déclencher
AUCUNE autre preuve du même marché : la seule réponse acceptable est resume is None.
"""
import bibliotheque_justification as bj
import justification


def m(gf, ga, dom):
    return {"buts_marques": gf, "buts_encaisses": ga, "domicile": dom}


def dom(*scores):   # matchs de l'équipe à domicile, joués à domicile
    return [m(gf, ga, True) for gf, ga in scores]


def ext(*scores):   # matchs de l'équipe visiteuse, joués à l'extérieur
    return [m(gf, ga, False) for gf, ga in scores]


def h2h(*scores):   # (buts de l'équipe à domicile aujourd'hui, buts de la visiteuse)
    return [{"buts_a": a, "buts_b": b} for a, b in scores]


def just(marche, a, b, h=None):
    return bj.construit_justification_bibliotheque(marche, a, b, h, nom_domicile="Alpha", nom_exterieur="Bravo")


def resume(marche, a, b, h=None):
    return just(marche, a, b, h)["resume"]


# ────────────────────────── NameError X2 / 1x2_exterieur ──────────────────────────
def test_x2_et_1x2_exterieur_ne_plantent_plus():
    a, b = dom((1, 0), (1, 0), (1, 0)), ext((0, 1), (0, 1), (0, 1))
    for marche in ("double_chance_X2", "1x2_exterieur"):
        r = just(marche, a, b, h2h((0, 1), (0, 1), (0, 1), (1, 1)))
        assert r["resume"] is not None
        assert "Bravo" in r["resume"]


def test_x2_sans_h2h_ni_historique_ne_plante_pas():
    for marche in ("double_chance_X2", "1x2_exterieur"):
        for args in ((None, None, None), ([], [], []), (None, None, [])):
            r = bj.construit_justification_bibliotheque(marche, *args)
            assert r["resume"] is None and r["preuve_specifique_disponible"] is False


def test_x2_preuve_h2h_seule():
    r = just("double_chance_X2", [], [], h2h((0, 1), (1, 1), (0, 2), (1, 1), (0, 0)))
    assert r["resume"].startswith("Avantage historique : Bravo est restée invaincue lors de 5 des 5")


# ────────────────────────────── btts_non ──────────────────────────────
def test_btts_non_matchs_fermes_produit_un_texte():
    assert "Match fermé" in resume("btts_non", dom((2, 0), (1, 0), (3, 0)), ext((0, 1), (0, 2), (0, 1)))


def test_btts_non_attaque_visiteuse_muette():
    r = resume("btts_non", dom((1, 1), (2, 1), (1, 2)), ext((0, 2), (0, 1), (0, 3)))
    assert r is not None and "Bravo" in r and "n'a marqué que dans 0.0%" in r


def test_btts_non_defense_solide_a_domicile():
    r = resume("btts_non", dom((2, 0), (3, 0), (1, 0)), ext((1, 1), (1, 2), (2, 1)))
    assert r is not None and "Alpha a gardé sa cage inviolée lors de 100.0%" in r


def test_btts_non_refuse_quand_tout_le_monde_marque():
    assert resume("btts_non", dom((1, 1), (2, 1), (1, 2)), ext((1, 1), (1, 2), (2, 1))) is None


def test_btts_non_refuse_sous_le_seuil_de_donnees():
    assert resume("btts_non", dom((2, 0), (1, 0)), ext((0, 1), (0, 2))) is None


def test_btts_non_refuse_juste_au_dessus_du_seuil():
    # BTTS 2/6 = 33,3 % (> 30), visiteuse marque 100 %, domicile concède 33,3 % (> 30)
    assert resume("btts_non", dom((1, 1), (2, 0), (2, 0)), ext((1, 1), (1, 0), (1, 0))) is None


# ─────────────────────────── double_chance_12 ───────────────────────────
def test_dc12_peu_de_nuls_produit_un_texte():
    assert "Peu de nuls" in resume("double_chance_12", dom((2, 0), (0, 1), (3, 1)), ext((0, 2), (1, 0), (2, 1)))


def test_dc12_un_nul_sur_six_est_accepte():
    r = resume("double_chance_12", dom((1, 1), (2, 0), (0, 1)), ext((0, 2), (1, 0), (2, 1)))
    assert r is not None and "16.7%" in r


def test_dc12_historique_decisif_seul():
    nuls_combines = dom((1, 1), (0, 0), (2, 2)) + ext((1, 1), (0, 0), (2, 2))  # 100 % de nuls : pas de preuve de forme
    r = resume("double_chance_12", nuls_combines[:3], nuls_combines[3:], h2h((1, 0), (0, 2), (1, 1), (2, 0), (0, 1)))
    assert r is not None and "Historique décisif : 1 nul seulement lors des 5" in r


def test_dc12_refuse_si_les_nuls_sont_frequents():
    assert resume("double_chance_12", dom((1, 1), (0, 0), (2, 0)), ext((1, 1), (0, 0), (0, 2))) is None


def test_dc12_refuse_a_33_pourcent_de_nuls():
    assert resume("double_chance_12", dom((1, 1), (0, 0), (2, 0)), ext((1, 0), (0, 2), (1, 2))) is None


def test_dc12_refuse_un_h2h_de_4_duels():
    nuls = dom((1, 1), (0, 0), (2, 2)), ext((1, 1), (0, 0), (2, 2))
    assert resume("double_chance_12", nuls[0], nuls[1], h2h((1, 0), (0, 2), (2, 0), (0, 1))) is None


# ───────────────────────────── 1x2_nul ─────────────────────────────
def test_nul_taux_de_nuls_eleve():
    r = resume("1x2_nul", dom((1, 1), (0, 0), (2, 0)), ext((1, 1), (0, 2), (2, 2)))
    assert r is not None and r.startswith("Nuls fréquents : 66.7%")


def test_nul_historique_serre_seul():
    r = resume("1x2_nul", dom((2, 0), (1, 0), (0, 1)), ext((1, 0), (0, 2), (1, 2)), h2h((1, 1), (0, 0), (2, 0), (1, 0), (0, 1)))
    assert r is not None and "Historique serré : 2 nuls lors des 5" in r


def test_nul_h2h_de_six_duels_dont_trois_nuls():
    r = resume("1x2_nul", dom((2, 0), (1, 0), (0, 1)), ext((1, 0), (0, 2), (1, 2)), h2h((1, 1), (0, 0), (2, 2), (1, 0), (0, 1), (2, 0)))
    assert r is not None and "3 nuls lors des 6" in r


def test_nul_refuse_sans_aucun_nul():
    assert resume("1x2_nul", dom((2, 0), (1, 0), (0, 1)), ext((1, 0), (0, 2), (1, 2))) is None


def test_nul_refuse_a_33_pourcent():
    assert resume("1x2_nul", dom((1, 1), (0, 0), (2, 0)), ext((1, 0), (0, 2), (1, 2))) is None


def test_nul_refuse_h2h_trop_court_ou_peu_serre():
    a, b = dom((2, 0), (1, 0), (0, 1)), ext((1, 0), (0, 2), (1, 2))
    assert resume("1x2_nul", a, b, h2h((1, 1), (0, 0), (2, 2), (1, 0))) is None          # 4 duels seulement
    assert resume("1x2_nul", a, b, h2h((1, 1), (0, 1), (2, 0), (1, 0), (0, 2))) is None  # 1 nul sur 5 (20 %)


# ─────────────────────── buts d'une équipe : over / under ───────────────────────
def test_equipe_domicile_over_attaque_en_forme():
    r = resume("buts_equipe_domicile_1.5_over", dom((2, 0), (3, 1), (2, 2)), ext((1, 0), (0, 1), (1, 1)))
    assert r is not None and r.startswith("Attaque en forme : Alpha a inscrit plus de 1,5 buts dans 100.0%") and "à domicile" in r


def test_equipe_domicile_over_defense_adverse_fragile():
    r = resume("buts_equipe_domicile_1.5_over", dom((1, 0), (0, 1), (1, 1)), ext((0, 2), (1, 3), (0, 2)))
    assert r is not None and r.startswith("Défense adverse fragile : Bravo a concédé plus de 1,5 buts dans 100.0%") and "en déplacement" in r


def test_equipe_exterieur_over_utilise_bien_la_visiteuse():
    r = resume("buts_equipe_exterieur_1.5_over", dom((1, 0), (0, 1), (1, 1)), ext((2, 0), (3, 1), (2, 2)))
    assert r is not None and r.startswith("Attaque en forme : Bravo a inscrit plus de 1,5 buts") and "en déplacement" in r


def test_equipe_exterieur_over_defense_de_l_equipe_a_domicile():
    r = resume("buts_equipe_exterieur_0.5_over", dom((0, 1), (1, 2), (0, 1)), ext((0, 1), (0, 1), (0, 1)))
    assert r is not None and "Défense adverse fragile : Alpha a concédé plus de 0,5 buts" in r and "à domicile" in r


def test_equipe_over_refuse_si_les_deux_taux_sont_bas():
    assert resume("buts_equipe_domicile_1.5_over", dom((1, 0), (0, 1), (1, 1)), ext((1, 0), (0, 1), (1, 1))) is None


def test_equipe_over_refuse_a_66_pourcent():
    # équipe : 2 matchs sur 3 au-dessus de 1,5 (66,7 % < 70) ; adversaire : 2/3 aussi
    assert resume("buts_equipe_domicile_1.5_over", dom((2, 0), (2, 1), (0, 0)), ext((0, 2), (1, 2), (0, 0))) is None


def test_equipe_over_refuse_sous_3_matchs_par_lieu():
    assert resume("buts_equipe_domicile_1.5_over", dom((3, 0), (3, 0)), ext((0, 3), (0, 3))) is None


def test_equipe_domicile_under_attaque_limitee():
    r = resume("buts_equipe_domicile_1.5_under", dom((1, 0), (0, 1), (1, 1)), ext((1, 0), (2, 1), (3, 0)))
    assert r is not None and r.startswith("Attaque limitée : Alpha n'a inscrit plus de 1,5 buts que dans 0.0%")


def test_equipe_domicile_under_defense_adverse_solide():
    r = resume("buts_equipe_domicile_1.5_under", dom((3, 0), (2, 1), (4, 0)), ext((0, 1), (1, 0), (0, 0)))
    assert r is not None and r.startswith("Défense adverse solide : Bravo n'a concédé plus de 1,5 buts que dans 0.0%")


def test_equipe_exterieur_under_visiteuse_muette():
    r = resume("buts_equipe_exterieur_0.5_under", dom((2, 2), (3, 3), (1, 2)), ext((0, 1), (0, 2), (0, 0)))
    assert r is not None and "Attaque limitée : Bravo n'a inscrit plus de 0,5 buts que dans 0.0%" in r


def test_equipe_under_refuse_quand_les_taux_sont_hauts():
    assert resume("buts_equipe_domicile_1.5_under", dom((2, 0), (3, 1), (2, 2)), ext((1, 2), (0, 3), (1, 2))) is None


def test_equipe_under_refuse_a_33_pourcent():
    # 1 match sur 3 au-dessus de la ligne = 33,3 % (> 30 %) des deux côtés
    assert resume("buts_equipe_domicile_1.5_under", dom((2, 0), (1, 0), (0, 0)), ext((0, 2), (0, 1), (0, 0))) is None


def test_equipe_under_refuse_sous_3_matchs():
    assert resume("buts_equipe_domicile_1.5_under", dom((0, 0), (0, 0)), ext((0, 0), (0, 0))) is None


# ────────────────── lignes de buts quelconques (hors 1,5, inchangée) ──────────────────
def test_total_over_2_5_rythme_offensif():
    a, b = dom((2, 1), (3, 0), (1, 2)), ext((2, 2), (1, 3), (3, 1))
    r = resume("over_under_total_2.5_over", a, b)
    assert r is not None and r.startswith("Rythme offensif : plus de 2,5 buts dans 100.0%")


def test_total_over_3_5_a_83_pourcent():
    a, b = dom((3, 1), (2, 2), (4, 0)), ext((2, 2), (3, 1), (1, 1))
    r = resume("over_under_total_3.5_over", a, b)
    assert r is not None and "83.3%" in r


def test_total_over_0_5_et_ligne_ancienne_over_2_5():
    a, b = dom((1, 0), (2, 0), (1, 1)), ext((0, 1), (1, 1), (2, 0))
    assert "plus de 0,5 buts dans 100.0%" in resume("over_under_total_0.5_over", a, b)
    assert resume("over_2.5", dom((2, 1), (3, 0), (1, 2)), ext((2, 2), (1, 3), (3, 1))) is not None


def test_total_over_refuse_a_50_pourcent():
    assert resume("over_under_total_2.5_over", dom((1, 0), (2, 1), (0, 0)), ext((0, 0), (1, 0), (2, 1))) is None


def test_total_over_refuse_a_66_pourcent():
    assert resume("over_under_total_2.5_over", dom((1, 0), (2, 1), (0, 0)), ext((2, 2), (1, 2), (0, 0))) is None


def test_total_over_refuse_sous_5_matchs_combines():
    assert resume("over_under_total_2.5_over", dom((3, 1), (2, 2)), ext((2, 2), (1, 3))) is None


def test_total_under_2_5_rythme_ferme():
    a, b = dom((1, 0), (0, 1), (1, 1)), ext((0, 0), (1, 0), (0, 1))
    r = resume("over_under_total_2.5_under", a, b)
    assert r is not None and r.startswith("Rythme fermé : plus de 2,5 buts dans seulement 0.0%")


def test_total_under_3_5_et_4_5():
    a, b = dom((1, 0), (0, 1), (2, 1)), ext((0, 0), (1, 0), (0, 2))
    assert "plus de 3,5 buts dans seulement 0.0%" in resume("over_under_total_3.5_under", a, b)
    assert "plus de 4,5 buts dans seulement 0.0%" in resume("over_under_total_4.5_under", a, b)


def test_total_under_historique_ferme_devient_possible():
    # CORRECTIF : h2h_over_count n'était calculé que pour « over », donc cette preuve n'existait jamais.
    a, b = dom((2, 1), (3, 0), (1, 2)), ext((2, 2), (1, 3), (3, 1))  # combiné très offensif : aucune autre preuve « under »
    r = resume("over_under_total_2.5_under", a, b, h2h((1, 0), (0, 1), (1, 1), (2, 1), (0, 0)))
    assert r is not None and "Historique fermé : la barre des 2,5 buts n'a été franchie que dans 1 des 5" in r


def test_total_under_refuse_a_50_pourcent():
    assert resume("over_under_total_2.5_under", dom((1, 0), (2, 1), (0, 0)), ext((0, 0), (1, 0), (2, 1))) is None


def test_total_under_refuse_a_33_pourcent():
    # 2 matchs sur 6 dépassent 2,5 buts = 33,3 % (> 25 %)
    assert resume("over_under_total_2.5_under", dom((2, 1), (2, 1), (0, 0)), ext((0, 0), (1, 0), (0, 1))) is None


def test_x2_ne_plante_pas_quand_l_equipe_a_domicile_a_moins_de_3_matchs():
    # KeyError: 'home_loss_rate' avant correctif (clé absente sous le seuil de 3 matchs à domicile)
    for marche in ("double_chance_X2", "1x2_exterieur"):
        r = just(marche, dom((1, 0), (2, 0)), ext((1, 0), (1, 1), (2, 1), (0, 0)), h2h((0, 1)))
        assert r["resume"] is not None and "Régularité à l'extérieur : Bravo reste sur 4 matchs sans défaite" in r["resume"]


def test_x2_ne_pretend_jamais_sans_defaite_apres_des_defaites():
    # CORRECTIF : le texte disait « sans défaite » pour 4 DÉFAITES de suite (série « sans victoire » confondue).
    for marche in ("double_chance_X2", "1x2_exterieur"):
        assert resume(marche, dom((1, 0), (1, 0), (1, 0)), ext((0, 1), (0, 1), (0, 1), (0, 1))) is None


def test_x2_les_nuls_comptent_comme_sans_defaite_et_une_defaite_coupe_la_serie():
    for marche in ("double_chance_X2", "1x2_exterieur"):
        assert "sans défaite" in resume(marche, dom((1, 0), (1, 0), (1, 0)), ext((1, 0), (0, 0), (2, 2), (0, 0)))
        # la dernière rencontre (fin de liste) est une défaite : série de 0 -> aucun texte
        assert resume(marche, dom((1, 0), (1, 0), (1, 0)), ext((1, 0), (0, 0), (2, 2), (0, 1))) is None


def test_donnees_forme_exterieur_exactes():
    d = bj.construit_donnees("double_chance_X2", dom((1, 0), (1, 0), (1, 0)), ext((2, 0), (1, 1), (0, 1), (1, 0), (1, 1)))
    assert d["away_win_rate"] == 40.0            # 2 victoires sur 5
    assert d["away_unbeaten_streak"] == 2        # 1-1 puis 1-0 (fin de liste), la défaite 0-1 coupe la série
    assert d["away_winless_streak"] == 1         # le dernier match (1-1) est un nul ; le précédent (1-0) est une victoire
    d2 = bj.construit_donnees("double_chance_X2", [], ext((1, 0), (1, 0)))
    assert d2["away_win_rate"] is None and d2["away_unbeaten_streak"] is None  # sous 3 matchs : non calculable


def test_total_under_refuse_h2h_ouvert():
    a, b = dom((2, 1), (3, 0), (1, 2)), ext((2, 2), (1, 3), (3, 1))
    assert resume("over_under_total_2.5_under", a, b, h2h((3, 0), (2, 2), (1, 2), (0, 1), (2, 1))) is None


def test_ligne_1_5_garde_sa_logique_d_origine():
    a, b = dom((2, 1), (3, 0), (1, 2)), ext((2, 2), (1, 3), (3, 1))
    assert resume("over_under_total_1.5_over", a, b).startswith("Rythme offensif : plus de 1.5 but inscrit dans 100.0%")
    a, b = dom((0, 0), (1, 0), (0, 0)), ext((0, 0), (0, 0), (0, 1))
    assert resume("over_under_total_1.5_under", a, b).startswith("Rythme fermé : plus de 1.5 but dans seulement 0.0%")


# ─────────────────────────────── robustesse ───────────────────────────────
TOUS_MARCHES = [
    "1x2_domicile", "1x2_nul", "1x2_exterieur", "double_chance_1X", "double_chance_12", "double_chance_X2",
    "btts_oui", "btts_non", "over_2.5", "under_2.5",
    "over_under_total_0.5_over", "over_under_total_1.5_over", "over_under_total_2.5_over", "over_under_total_3.5_over",
    "over_under_total_1.5_under", "over_under_total_2.5_under", "over_under_total_5.5_under",
    "buts_equipe_domicile_1.5_over", "buts_equipe_domicile_0.5_under", "buts_equipe_exterieur_1.5_over", "buts_equipe_exterieur_2.5_under",
    "handicap_domicile_1.0", "cage_inviolee_domicile", "marche_inconnu", "", None,
]


def test_aucune_exception_quelles_que_soient_les_donnees():
    valides = (dom((2, 1), (0, 0), (1, 1), (3, 0)), ext((1, 2), (0, 0), (2, 2), (0, 1)), h2h((1, 0), (1, 1), (0, 2), (2, 2), (0, 0)))
    sales = ([{"buts_marques": "x", "buts_encaisses": None, "domicile": True}] * 6, [{"domicile": False}] * 6, [{"buts_a": None, "buts_b": 1}, "n'importe quoi", None])
    for marche in TOUS_MARCHES:
        for a, b, h in [(None, None, None), ([], [], []), valides, sales]:
            r = bj.construit_justification_bibliotheque(marche, a, b, h, nom_domicile="Alpha", nom_exterieur="Bravo", odds_scraped=1.5, market_prob_pct=70)
            assert set(r) >= {"resume", "preuves", "preuve_specifique_disponible", "donnees_suffisantes"}
            assert r["preuve_specifique_disponible"] == (r["resume"] is not None)
            assert len(r["preuves"]) <= 3


def test_la_preuve_ev_seule_ne_suffit_jamais():
    # NO DATA -> NO GO : sans preuve spécifique, resume est None même avec cote et probabilité connues.
    for marche in TOUS_MARCHES[:-3]:
        r = bj.construit_justification_bibliotheque(marche, [], [], [], odds_scraped=1.5, market_prob_pct=70)
        assert r["resume"] is None and r["preuve_specifique_disponible"] is False


def test_l_api_publique_expose_les_nouveaux_marches():
    a, b = dom((2, 0), (1, 0), (3, 0)), ext((0, 1), (0, 2), (0, 1))
    r = justification.construit_justification("btts_non", a, b, h2h=[], nom_domicile="Alpha", nom_exterieur="Bravo", odds_scraped=1.6, market_prob_pct=72)
    assert r["preuve_specifique_disponible"] is True and "Match fermé" in r["resume"]


def test_un_meme_texte_ne_sert_pas_deux_marches_opposes():
    # Sur les mêmes données, « nul » et « pas de nul » ne peuvent pas être justifiés tous les deux.
    a, b = dom((1, 1), (0, 0), (2, 2)), ext((1, 1), (0, 0), (2, 2))
    assert resume("1x2_nul", a, b) is not None and resume("double_chance_12", a, b) is None
    a, b = dom((2, 0), (0, 1), (3, 1)), ext((0, 2), (1, 0), (2, 1))
    assert resume("1x2_nul", a, b) is None and resume("double_chance_12", a, b) is not None
    assert resume("btts_non", dom((1, 1), (2, 1), (1, 2)), ext((1, 1), (1, 2), (2, 1))) is None
    assert resume("btts_oui", dom((1, 1), (2, 1), (1, 2)), ext((1, 1), (1, 2), (2, 1))) is not None
