"""Mission du 02/11/2026 : évaluation A / B / C, deux routes (cote ≥ 1,35 / combinaisons), événements joints. Données synthétiques à vérité connue."""
import numpy as np
import pytest

from moteur_omega_v3 import evaluation as E, marches as M

N = len(M.CLES)
I = {c: i for i, c in enumerate(M.CLES)}


def faux_echantillon(n=300, graine=1):
    """n matchs ; marché 0 : g haut, réussite 90 %, cote 1,20 (cote basse, solide) ; marché 1 : g haut, réussite 90 %, cote 1,60 ; marché 2 : 100 % mais 12 cas seulement."""
    rng = np.random.default_rng(graine)
    ech = []
    for t in range(n):
        g = rng.uniform(0.2, 0.6, N)
        y = (rng.uniform(size=N) < 0.4).astype(int)
        cotes: dict = {}
        def poser(i, cote):
            cotes.setdefault(M.CLES[i][0], {})[M.CLES[i][1]] = cote
        g[0], y[0] = 0.92, int(rng.uniform() < 0.9); poser(0, 1.20)
        g[1], y[1] = 0.92, int(rng.uniform() < 0.9); poser(1, 1.60)
        if t < 12:
            g[2], y[2] = 0.95, 1
        else:
            g[2], y[2] = 0.3, 0
        poser(2, 1.20)
        ech.append({"m": {"jour": f"2026-10-{1 + t // 12:02d}", "id": str(t), "cotes": cotes}, "g": g, "f": g.copy(), "y": y, "sequences": {}})
    return ech


def test_trois_notions_separees_dans_le_tableau():
    mx = E.matrices(faux_echantillon())
    r = E.tableau_marches(mx)[0]
    assert set(r) >= {"A_estime", "B_historique", "C_validation_reserve", "ecart_A_moins_B", "qualite", "seuil_pour_cible", "definition", "formule", "famille", "id"}
    assert set(r["A_estime"]) == {"f_moyen", "g_moyen"} and {"n_valides", "succes", "echecs", "frequence", "par_periode"} <= set(r["B_historique"])
    assert r["B_historique"]["n_valides"] == r["B_historique"]["succes"] + r["B_historique"]["echecs"]
    assert len(r["B_historique"]["par_periode"]) == E.NB_PERIODES
    assert len(E.tableau_marches(mx)) == N


def test_aucun_edge_ev_edv_dans_le_module():
    t = open(E.__file__, encoding="utf-8").read().lower()
    for mot in ("p_implicite", "rendement", "ecart_implicite"):
        assert mot not in t.replace("jamais", "")
    assert '"ev"' not in t


def test_route_principale_exclut_les_cotes_sous_1_35():
    mx = E.matrices(faux_echantillon())
    th = E.seuils_principaux(mx, 0.70, mx["dev"])
    assert np.isnan(th[0])                                   # marché 0 : cote 1,20, jamais jouable en principal
    assert not np.isnan(th[1])                               # marché 1 : cote 1,60, 90 % → seuil appris
    r = E.evaluer_principal(mx, 0.70)
    assert r["paris"] > 0 and r["reussite_C"] > 0.7


def test_seuil_propre_a_chaque_marche_pas_uniforme():
    ech = faux_echantillon()
    for x in ech:                                            # un autre marché, à 75 % de réussite : son seuil / niveau diffère
        x["g"][3] = 0.80
        x["y"][3] = int(np.random.default_rng(int(x["m"]["id"])).uniform() < 0.62)
        x["m"]["cotes"].setdefault(M.CLES[3][0], {})[M.CLES[3][1]] = 1.50
    mx = E.matrices(ech)
    a, b = E.niveau_atteignable(mx["G"][:, 1], mx["S"][:, 1].astype(float)), E.niveau_atteignable(mx["G"][:, 3], mx["S"][:, 3].astype(float))
    assert a["reussite_lissee"] > b["reussite_lissee"] + 0.15 and a["seuil_g"] != b["seuil_g"] or a["reussite_lissee"] != b["reussite_lissee"]


def test_echantillon_insuffisant_donne_aucun_niveau():
    assert E.niveau_atteignable(np.array([0.9] * 29), np.ones(29)) is None
    assert E.niveau_atteignable(np.array([0.9] * 30), np.ones(30)) is not None


def test_validation_chronologique_sans_fuite():
    ech = faux_echantillon()
    mx = E.matrices(ech)
    th = E.seuils_principaux(mx, 0.70, mx["dev"])
    for x in ech:                                            # on sabote les résultats de la réserve : les seuils appris ne doivent pas bouger
        if x["m"]["jour"] >= mx["coupe"]:
            x["y"][:] = 0
    th2 = E.seuils_principaux(E.matrices(ech), 0.70, E.matrices(ech)["dev"])
    assert np.array_equal(np.isnan(th), np.isnan(th2)) and np.allclose(th[~np.isnan(th)], th2[~np.isnan(th2)])
    assert max(mx["jours"][mx["dev"]]) < mx["coupe"] <= min(mx["jours"][mx["res"]])


# --- route « combinaisons » : 3 cas qui passent, 3 qui échouent -----------------------------------------------------------------
@pytest.mark.parametrize("lecture", E.LECTURES)
def test_marche_solide_a_cote_basse_candidat_combinaison(lecture):
    mx = E.matrices(faux_echantillon())
    adm = E.route_combinaison(mx, lecture)
    assert adm[:, 0].mean() > 0.9                            # marché 0 : B ≈ 90 %, g = 92 %, 300 matchs
    ev = E.evaluer_route_combinaison(mx, lecture)
    assert ev["observations_reserve"] > 0 and ev["reussite"] > 0.8


def test_petit_echantillon_jamais_admis():
    mx = E.matrices(faux_echantillon())
    for lecture in ("historique", "les_deux"):
        assert not E.route_combinaison(mx, lecture)[:, 2].any()       # marché 2 : 12 cas à 100 %, mais < 30 matchs valides réussis sur la période de référence
    # chaque lecture respecte le seuil
    assert not E.route_combinaison(mx, "les_deux", seuil=0.99)[:, 0].any()
    with pytest.raises(ValueError):
        E.route_combinaison(mx, "autre")


def test_marche_fragile_rejete():
    ech = faux_echantillon()
    for x in ech:
        x["y"][0] = 0
    mx = E.matrices(ech)
    assert not E.route_combinaison(mx, "historique")[:, 0].any() and not E.route_combinaison(mx, "les_deux")[:, 0].any()


def test_un_marche_a_cote_basse_n_est_pas_rejete_il_reste_en_combinaison():
    mx = E.matrices(faux_echantillon())
    r = E.tableau_marches(mx)[0]
    assert r["qualite"]["cote_lt_1_35"] > 0 and r["qualite"]["cote_ge_1_35"] == 0
    assert r["B_historique"]["frequence"] > 0.8 and r["B_historique"]["n_valides"] == 300   # historique et fréquence accessibles


# --- événements joints -------------------------------------------------------------------------------------------------------
def test_evenement_joint_n_est_ni_produit_ni_minimum():
    att_a, att_b = [0, 1, 2, 3], [0, 0, 1, 2]
    joint = E.evenement_joint_exact(att_a, att_b, ("dc_total_2.5", "1N|plus"))
    p1 = E.evenement_joint_exact(att_a, att_b, ("double_chance", "1N"))
    p2 = E.evenement_joint_exact(att_a, att_b, ("over_under_2.5", "plus"))
    assert joint == pytest.approx(0.375) and p1 == pytest.approx(0.8125) and p2 == pytest.approx(0.4375)
    assert joint != pytest.approx(p1 * p2) and joint != pytest.approx(min(p1, p2)) and joint != pytest.approx(p1 + p2)
    # 2e cas : deux conditions qui se recouvrent (btts ⊂ plus de 1,5) → le joint est égal à la plus petite, pas au produit
    j2 = E.evenement_joint_exact([0, 2], [0, 2], ("btts_total_1.5", "Oui|plus"))
    assert j2 == pytest.approx(0.25) and j2 != pytest.approx(0.25 * 0.75)


def test_dependance_entre_marches_dans_un_combine():
    # deux conditions identiques → l'événement joint vaut la condition, pas son carré
    j = E.evenement_joint_exact([0, 1, 1, 2], [0, 1, 2, 2], ("1x2_total_1.5", "1|plus"))
    assert 0 < j < 1
    assert E.evenement_joint_exact([3, 3], [0, 0], ("1x2_total_2.5", "1|plus")) == 1.0
    assert E.evenement_joint_exact([3, 3], [0, 0], ("1x2_total_2.5", "2|plus")) == 0.0


def test_composantes_des_combines():
    assert E.composantes(("dc_btts", "1N|Oui")) == [("double_chance", "1N"), ("btts", "Oui")]
    assert E.composantes(("1x2_total_2.5", "1|plus")) == [("1x2", "1"), ("over_under_2.5", "plus")]
    assert E.composantes(("btts_total_2.5", "Oui|plus")) == [("btts", "Oui"), ("over_under_2.5", "plus")]


def test_combine_sans_cote_reelle_n_est_jamais_propose():
    mx = E.matrices(faux_echantillon())
    assert E.combinaisons_proposees(mx) == []                # aucun combiné coté dans le faux jeu : rien n'est publiable
    ech = faux_echantillon()
    i = I[("dc_btts", "1N|Oui")]
    for x in ech:
        x["m"]["cotes"].setdefault("dc_btts", {})["1N|Oui"] = 2.1
    mx2 = E.matrices(ech)
    assert E.combinaisons_proposees(mx2) == [i]
    r = E.evaluer_combinaisons(mx2)
    assert set(r["methodes_reserve"]) == {"evenement_joint_f", "evenement_joint_g", "produit_des_pourcentages", "minimum_des_pourcentages"}
    assert "btts_total_2.5" in r["groupes_sans_aucune_cote"]


def test_surestimation_est_un_constat_sans_correction():
    mx = E.matrices(faux_echantillon())
    s = E.surestimation(mx)
    assert set(s) >= {"ensemble", "par_tranche_g", "par_famille", "par_periode", "par_effectif_du_marche"}
    assert s["ensemble"]["ecart"] == pytest.approx(s["ensemble"]["g_moyen"] - s["ensemble"]["reussite"], abs=1e-3)
