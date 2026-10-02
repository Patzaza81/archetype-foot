# -*- coding: utf-8 -*-
"""Tests de moteur_v2_6_10 : lissage, calibration isotone, cohérence, alertes, et intégration avec moteur_v2_6_9.

Les tests d'intégration vérifient des PROPRIÉTÉS (schéma conservé, probabilités moins extrêmes, calibration monotone et
cohérente, sélection P1/P2/P3 inchangée dans sa forme), pas des valeurs numériques figées.
"""
import copy
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

import moteur_v2_6_9 as base  # noqa: E402
import moteur_v2_6_10 as moteur  # noqa: E402
from moteur_v2_6_10 import calibration as cal  # noqa: E402
from moteur_v2_6_10 import coherence, lissage, risque  # noqa: E402


# ───────────────────────── données ─────────────────────────
def un_match(att_d=3.0, def_d=0.4, att_e=0.6, def_e=2.4, n=5, **extra):
    m = {"id": 1, "nom_dom": "A", "nom_ext": "B",
         "equipe_dom": {"nom": "A", "buts_marques_moy": att_d, "buts_encaisses_moy": def_d, "matchs_joues": n},
         "equipe_ext": {"nom": "B", "buts_marques_moy": att_e, "buts_encaisses_moy": def_e, "matchs_joues": n},
         "cotes": {"victoire": 1.55, "nul": 4.2, "defaite": 6.0, "btts_oui": 2.05, "btts_non": 1.70,
                   "over_1_5": 1.30, "under_1_5": 3.40, "over_2_5": 1.75, "under_2_5": 2.05,
                   "dc_1X": 1.20, "dc_X2": 2.60, "dc_12": 1.25},
         "meta": {"fiabilite": "OK"}}
    m.update(extra)
    return m


def avec_handicaps(m):
    m["cotes"].update({"handicap_dom_-0_5": 1.58, "handicap_ext_+0_5": 2.45,
                       "handicap_dom_-1_0": 2.90, "handicap_ext_+1_0": 1.40})
    return m


def lignes(res):
    return {l["marche"]: l for l in res["inventaire"]}


def proba(res, marche):
    return lignes(res)[marche]["proba_modele"]


# ───────────────────────── contrat avec le moteur de base ─────────────────────────
def test_le_moteur_de_base_expose_tout_ce_que_la_v2_6_10_utilise():
    """Si une de ces fonctions est renommée dans moteur_v2_6_9, ce test échoue AVANT toute analyse, avec un nom clair."""
    for nom in ("analyser_match", "resultat_vide", "evaluer_ligne", "statut_1x2", "statut_autres", "artefacts_marche",
                "categorie_value", "attribuer_designations", "construire_verdict", "biais_asymetrique", "_cle_tri",
                "GROUPES", "HANDICAP_ENTIER_REMBOURSE"):
        assert hasattr(base, nom), f"moteur_v2_6_9.{nom} manquant"


def test_le_moteur_de_base_n_est_pas_modifie():
    assert base.LAMBDA_MIN == 0.05 and base.SEUIL_VALUE_EDGE_MIN == 0.03 and base.HANDICAP_ENTIER_REMBOURSE is False
    assert base.calcul_lambdas(1.5, 1.0, 1.0, 1.5) == (1.5, 1.0)


# ───────────────────────── lissage ─────────────────────────
def test_lisse_formule_exacte():
    assert lissage.lisse(3.0, 4, 1.35) == pytest.approx((4 * 3.0 + 4 * 1.35) / 8)
    assert lissage.lisse(1.35, 7, 1.35) == pytest.approx(1.35)


def test_lisse_grand_echantillon_garde_sa_valeur():
    assert abs(lissage.lisse(3.0, 400, 1.35) - 3.0) < 0.02


def test_parametres_fixes_a_l_avance():
    p = lissage.PARAMETRES_PAR_DEFAUT
    assert (p.k, p.ref_dom, p.ref_ext) == (4.0, 1.50, 1.20)
    assert p.ref_dom + p.ref_ext == pytest.approx(2.70)          # même niveau de buts total que 2 × 1,35
    with pytest.raises(ValueError):
        lissage.ParametresLissage(k=-1)


def test_references_par_role():
    """Équipe qui reçoit : marqués → ref domicile, encaissés → ref extérieur. Visiteuse : l'inverse."""
    eq = {"nom": "A", "buts_marques_moy": 2.0, "buts_encaisses_moy": 2.0, "matchs_joues": 4}
    dom, t_dom = lissage.lisser_equipe(eq, "dom")
    ext, t_ext = lissage.lisser_equipe(eq, "ext")
    assert dom["buts_marques_moy"] == pytest.approx((4 * 2.0 + 4 * 1.50) / 8)
    assert dom["buts_encaisses_moy"] == pytest.approx((4 * 2.0 + 4 * 1.20) / 8)
    assert ext["buts_marques_moy"] == pytest.approx((4 * 2.0 + 4 * 1.20) / 8)
    assert ext["buts_encaisses_moy"] == pytest.approx((4 * 2.0 + 4 * 1.50) / 8)
    assert t_dom["reference_attaque"] == 1.50 and t_ext["reference_attaque"] == 1.20
    with pytest.raises(ValueError):
        lissage.lisser_equipe(eq, "neutre")


def test_deux_equipes_moyennes_ne_sont_pas_modifiees_par_le_lissage():
    """Défaut corrigé à l'audit : une référence unique rognait l'avantage du domicile des équipes moyennes."""
    m = un_match(att_d=1.50, def_d=1.20, att_e=1.20, def_e=1.50, n=3)
    brut, lisse = base.analyser_match(copy.deepcopy(m)), moteur.analyser_match(copy.deepcopy(m))
    for marche in ("victoire", "nul", "defaite", "btts_oui", "over_2_5"):
        assert proba(lisse, marche) == pytest.approx(proba(brut, marche), abs=1e-9)
    assert lisse["lambda_dom"] == pytest.approx(brut["lambda_dom"]) and lisse["lambda_ext"] == pytest.approx(brut["lambda_ext"])


def test_niveaux_d_echantillon():
    assert [lissage.niveau_echantillon(n) for n in (None, 0, 2, 4, 6, 9, 12)] == [
        "INCONNU", "IMPOSSIBLE", "TRES_FAIBLE", "FAIBLE", "UTILISABLE", "SOLIDE", "TRES_SOLIDE"]


def test_lisser_equipe_ne_modifie_pas_l_original():
    eq = {"nom": "A", "buts_marques_moy": 3.0, "buts_encaisses_moy": 0.4, "matchs_joues": 3}
    avant = copy.deepcopy(eq)
    lisse, trace = lissage.lisser_equipe(eq, "dom")
    assert eq == avant
    assert lisse["buts_marques_moy"] < 3.0 and lisse["buts_encaisses_moy"] > 0.4
    assert trace["poids_reference"] == pytest.approx(4 / 7)


def test_lisser_equipe_matchs_recents_devient_moyennes_et_effectif():
    lisse, trace = lissage.lisser_equipe({"nom": "A", "matchs_recents": [[2, 0], [4, 1]]}, "dom")
    assert "matchs_recents" not in lisse and lisse["matchs_joues"] == 2
    assert trace["attaque_brute"] == 3.0 and trace["n"] == 2


def test_effectif_inconnu_utilise_la_valeur_par_defaut_et_reste_inconnu_pour_le_moteur():
    lisse, trace = lissage.lisser_equipe({"nom": "A", "buts_marques_moy": 2.0, "buts_encaisses_moy": 1.0}, "dom")
    assert trace["n"] is None and trace["n_utilise"] == lissage.N_PAR_DEFAUT
    assert "matchs_joues" not in lisse


def test_valeur_aberrante_n_est_jamais_rattrapee_par_le_lissage():
    eq = {"nom": "A", "buts_marques_moy": 12.0, "buts_encaisses_moy": 1.0, "matchs_joues": 5}
    lisse, trace = lissage.lisser_equipe(eq, "dom")
    assert lisse is eq and trace is None
    res = moteur.analyser_match(un_match(att_d=12.0))
    assert res["statut_global"] == "SKIP" and "V5" in (res["raison_skip"] or "")


def test_equipe_invalide_laissee_au_moteur_de_base():
    assert lissage.lisser_equipe({"nom": "A"}, "dom")[1] is None
    assert moteur.analyser_match(un_match(equipe_dom={"nom": "A"}))["statut_global"] == "SKIP"


def test_matchs_joues_invalide_garde_son_avertissement():
    m = un_match()
    m["equipe_dom"]["matchs_joues"] = 0
    assert any("matchs_joues invalide" in a for a in moteur.analyser_match(m)["avertissements_match"])


def test_lisser_match_ne_modifie_pas_le_match():
    m = un_match()
    avant = copy.deepcopy(m)
    lissage.lisser_match(m)
    assert m == avant


# ───────────────────────── intégration : surconfiance ─────────────────────────
def test_lissage_rend_les_probabilites_moins_extremes():
    m = un_match()
    brut, lisse = base.analyser_match(copy.deepcopy(m)), moteur.analyser_match(copy.deepcopy(m))
    assert brut["statut_global"] != "SKIP" and lisse["statut_global"] != "SKIP"
    assert proba(lisse, "victoire") < proba(brut, "victoire")
    assert proba(lisse, "defaite") > proba(brut, "defaite")
    assert lisse["lambda_dom"] < brut["lambda_dom"]


def test_sans_lissage_on_retrouve_exactement_la_v2_6_9():
    m = un_match()
    a, b = base.analyser_match(copy.deepcopy(m)), moteur.analyser_match(copy.deepcopy(m), lisser=False)
    assert [(l["marche"], l["proba_modele"], l["ev"], l["categorie"]) for l in a["inventaire"]] == \
           [(l["marche"], l["proba_modele"], l["ev"], l["categorie"]) for l in b["inventaire"]]
    assert a["verdict"] == b["verdict"] and a["statut_global"] == b["statut_global"]
    assert a["avertissements_match"] == b["avertissements_match"]


def test_l_effet_du_lissage_diminue_quand_l_echantillon_grandit():
    ecarts = []
    for n in (3, 12, 60):
        brut, lisse = base.analyser_match(un_match(n=n)), moteur.analyser_match(un_match(n=n))
        ecarts.append(abs(proba(brut, "victoire") - proba(lisse, "victoire")))
    assert ecarts[0] > ecarts[1] > ecarts[2]


def test_le_resultat_est_un_sur_ensemble_du_schema_de_la_v2_6_9():
    m = un_match()
    res = moteur.analyser_match(m)
    assert set(base.resultat_vide(m)) <= set(res)
    for cle in ("moteur", "version_moteur", "modele", "lissage", "calibration", "alertes"):
        assert cle in res
    assert res["moteur"] == "moteur_v2_6_10" and res["calibration"]["statut"] == "NON_CALIBRE"
    assert "Probabilités non calibrées" in res["alertes"]
    for l in res["inventaire"]:
        assert {"marche", "proba_modele", "p_juste", "cote", "edge", "ev", "statut", "is_value", "categorie"} <= set(l)
        assert l["proba_brute"] == l["proba_modele"]


def test_le_match_d_origine_n_est_pas_modifie_par_l_analyse():
    m = un_match()
    avant = copy.deepcopy(m)
    moteur.analyser_match(m, calibrateur=calibrateur_centre())
    assert m == avant


def test_un_skip_reste_un_skip_avec_les_champs_ajoutes():
    res = moteur.analyser_match(un_match(cotes={"victoire": 2.0}), calibrateur=calibrateur_centre())
    assert res["statut_global"] == "SKIP" and res["alertes"] == [] and res["moteur"] == "moteur_v2_6_10"


def test_r5_reste_evalue_sur_les_moyennes_brutes():
    """Le lissage gomme les profils asymétriques : sans réalignement, l'avertissement R5 de la v2.6.9 disparaîtrait."""
    m = un_match(att_d=2.0, def_d=0.9, att_e=1.2, def_e=1.5, n=3)
    brut = base.analyser_match(copy.deepcopy(m))
    naif = base.analyser_match(lissage.lisser_match(copy.deepcopy(m))[0])
    res = moteur.analyser_match(copy.deepcopy(m))
    assert "Profil attaque/défense très asymétrique" in brut["avertissements_match"]
    assert "Profil attaque/défense très asymétrique" not in naif["avertissements_match"]       # le défaut
    assert res["avertissements_match"].count("Profil attaque/défense très asymétrique") == 1 and res["biais_attaque_defense"] is True
    ok = moteur.analyser_match(un_match(att_d=1.5, def_d=1.2, att_e=1.2, def_e=1.5, n=3))
    assert "Profil attaque/défense très asymétrique" not in ok["avertissements_match"] and ok["biais_attaque_defense"] is False


def test_r5_garde_sa_place_dans_la_liste_des_avertissements():
    """Sans effet de bord sur l'affichage : R5 reste juste après R4, comme dans la v2.6.9."""
    m = un_match(att_d=2.0, def_d=0.9, att_e=1.2, def_e=1.5, n=3)
    brut = base.analyser_match(copy.deepcopy(m))["avertissements_match"]
    assert moteur.analyser_match(copy.deepcopy(m))["avertissements_match"] == brut


# ───────────────────────── cohérence des probabilités ─────────────────────────
GROUPES_TEST = {"1X2": ["victoire", "nul", "defaite"], "BTTS": ["btts_oui", "btts_non"], "OU": ["over_2_5", "under_2_5"]}


def test_harmonise_groupes_complets_somment_a_1():
    out = coherence.harmonise({"victoire": 0.6, "nul": 0.3, "defaite": 0.3, "btts_oui": 0.55, "btts_non": 0.55,
                               "over_2_5": 0.4, "under_2_5": 0.5}, GROUPES_TEST)
    assert out["victoire"] + out["nul"] + out["defaite"] == pytest.approx(1.0)
    assert out["btts_oui"] + out["btts_non"] == pytest.approx(1.0)
    assert out["over_2_5"] + out["under_2_5"] == pytest.approx(1.0)


def test_harmonise_ne_touche_pas_un_groupe_incomplet():
    out = coherence.harmonise({"victoire": 0.6, "nul": 0.3, "btts_oui": 0.7}, GROUPES_TEST)
    assert out == {"victoire": 0.6, "nul": 0.3, "btts_oui": 0.7}


def test_harmonise_derive_la_double_chance_du_1x2():
    out = coherence.harmonise({"victoire": 0.5, "nul": 0.3, "defaite": 0.3, "dc_1X": 0.1, "dc_X2": 0.1, "dc_12": 0.1}, GROUPES_TEST)
    assert out["dc_1X"] == pytest.approx(out["victoire"] + out["nul"])
    assert out["dc_X2"] == pytest.approx(out["nul"] + out["defaite"])
    assert out["dc_12"] == pytest.approx(out["victoire"] + out["defaite"])


def test_harmonise_aligne_les_marches_equivalents():
    out = coherence.harmonise({"victoire": 0.5, "nul": 0.3, "defaite": 0.3, "handicap_dom_-0_5": 0.9, "handicap_ext_+0_5": 0.9,
                               "handicap_dom_+0_5": 0.9, "handicap_ext_-0_5": 0.9, "dc_1X": 0.1, "dc_X2": 0.1, "dc_12": 0.1,
                               "buts_ext_under_0_5": 0.4, "clean_sheet_dom": 0.9}, GROUPES_TEST)
    assert out["handicap_dom_-0_5"] == pytest.approx(out["victoire"])
    assert out["handicap_ext_+0_5"] == pytest.approx(out["dc_X2"])
    assert out["handicap_dom_+0_5"] == pytest.approx(out["dc_1X"])
    assert out["handicap_ext_-0_5"] == pytest.approx(out["defaite"])
    assert out["clean_sheet_dom"] == out["buts_ext_under_0_5"] == 0.4


# ───────────────────────── calibration ─────────────────────────
def observations(n_matchs, f=lambda p: p, par_match=12):
    """Observations déterministes : pour chaque match, `par_match` marchés distincts de probabilité p, gagnés selon f(p)."""
    out = []
    for i in range(n_matchs):
        for j in range(par_match):
            p = (j + 0.5) / par_match
            gagne = ((i % 20) + 0.5) / 20 < f(p)
            out.append({"match_id": f"m{i}", "marche": f"marche_{j}", "proba": p, "gagne": gagne, "date": f"2026-09-{1 + i % 28:02d}"})
    return out


def test_calibration_refuse_un_echantillon_insuffisant():
    c, diag = cal.apprendre(observations(10), modele="x")
    assert c is None and diag["raison"] == "OBSERVATIONS_INSUFFISANTES"
    c, diag = cal.apprendre(observations(40, par_match=10), modele="x")             # 400 observations mais 40 matchs
    assert c is None and diag["raison"] == "MATCHS_INSUFFISANTS"
    assert cal.MIN_MATCHS == 100


def test_calibration_refuse_un_echantillon_biaise_par_la_selection():
    """Des value bets seules (1 à 3 marchés par match) mesurent la malchance du modèle, pas sa fiabilité."""
    c, diag = cal.apprendre(observations(150, par_match=3), modele="x")
    assert c is None and diag["raison"] == "ECHANTILLON_BIAISE_PAR_SELECTION"


def test_calibration_exige_la_signature_du_modele():
    with pytest.raises(ValueError):
        cal.apprendre(observations(100), modele="")


def test_observations_sans_date_sont_ecartees():
    obs = observations(100)
    for o in obs[:50]:
        o.pop("date")
    c, diag = cal.apprendre(obs, modele="x")
    assert diag["ecartees"] == 50


def test_calibration_monotone_et_corrige_la_surconfiance():
    c, diag = cal.apprendre(observations(100, f=lambda p: 0.5 + 0.6 * (p - 0.5)), modele="x")
    assert c is not None and diag["pret"] and c.date_max is not None
    ys = [c.predire(x / 100) for x in range(1, 100)]
    assert all(b >= a - 1e-12 for a, b in zip(ys, ys[1:]))
    assert c.predire(0.9) < 0.9 and c.predire(0.1) > 0.1
    assert cal.PLANCHER <= min(ys) and max(ys) <= cal.PLAFOND


def test_poids_du_calibrateur_croit_avec_l_echantillon_et_garde_la_monotonie():
    iso = ((0.1, 0.3), (0.5, 0.5), (0.9, 0.7))
    petit, grand = cal.CalibrateurIsotone(iso, 100, 100, "x"), cal.CalibrateurIsotone(iso, 10 ** 6, 10 ** 6, "x")
    assert petit.poids == pytest.approx(0.5) and grand.poids > 0.9999
    assert grand.predire(0.9) == pytest.approx(0.7, abs=1e-3)
    assert 0.7 < petit.predire(0.9) < 0.9                           # correction à moitié
    ys = [petit.predire(x / 100) for x in range(0, 101)]
    assert all(b >= a - 1e-12 for a, b in zip(ys, ys[1:]))


def test_blocs_trop_petits_sont_fusionnes():
    blocs = [[0.1, 0.0, 50], [0.5, 1.0, 3], [0.9, 30.0, 40]]
    fusion = cal._fusionne_petits_blocs(blocs, 30)
    assert all(b[2] >= 30 for b in fusion) and sum(b[2] for b in fusion) == 93
    assert [b[1] / b[2] for b in fusion] == sorted(b[1] / b[2] for b in fusion)


def test_calibration_ne_sort_jamais_0_ou_1():
    c = cal.CalibrateurIsotone(((0.1, 0.0), (0.9, 1.0)))
    assert c.predire(0.0) == cal.PLANCHER and c.predire(1.0) == cal.PLAFOND


def test_calibration_aller_retour_json():
    c, _ = cal.apprendre(observations(100), modele="m|v1")
    d = cal.CalibrateurIsotone.from_dict(c.to_dict())
    assert d == c and d.modele == "m|v1"
    with pytest.raises(ValueError):
        cal.CalibrateurIsotone.from_dict({"schema": 2, "points": [[0.2, 0.9], [0.8, 0.1]]})
    with pytest.raises(ValueError):
        cal.CalibrateurIsotone.from_dict({"schema": 1, "points": []})


def test_marches_equivalents_comptent_une_fois():
    assert cal.marche_equivalent("handicap_dom_-0_5") == "victoire"
    assert cal.marche_equivalent("handicap_ext_+0_5") == "dc_X2"
    assert cal.marche_equivalent("handicap_dom_+0_5") == "dc_1X"
    assert cal.marche_equivalent("handicap_ext_-0_5") == "defaite"
    assert cal.marche_equivalent("clean_sheet_dom") == "buts_ext_under_0_5"
    assert cal.marche_equivalent("handicap_dom_-1_5") == "handicap_dom_-1_5"
    d = "2026-09-01"
    obs = [{"match_id": 1, "marche": "victoire", "proba": 0.6, "gagne": 1, "date": d},
           {"match_id": 1, "marche": "handicap_dom_-0_5", "proba": 0.6, "gagne": 1, "date": d},
           {"match_id": 2, "marche": "handicap_dom_-0_5", "proba": 0.6, "gagne": 0, "date": d}]
    assert len(cal.dedoublonne(obs)) == 2


def test_observations_invalides_ecartees():
    d = "2026-09-01"
    mauvaises = [{"match_id": 1, "marche": "x", "proba": 0.0, "gagne": 1, "date": d}, {"match_id": 1, "marche": "x", "proba": 1.0, "gagne": 1, "date": d},
                 {"match_id": None, "marche": "x", "proba": 0.5, "gagne": 1, "date": d}, {"match_id": 1, "marche": "x", "proba": 0.5, "gagne": None, "date": d},
                 {"match_id": 1, "marche": "x", "proba": True, "gagne": 1, "date": d}, {"match_id": 1, "marche": "x", "proba": 0.5, "gagne": 1}]
    assert cal.dedoublonne(mauvaises) == []


def test_avant_ne_garde_que_le_passe_strict_et_refuse_sans_date():
    obs = [{"date": "2026-09-10"}, {"date": "2026-09-20"}, {"date": "2026-09-21"}, {}]
    assert cal.avant(obs, "2026-09-20") == [{"date": "2026-09-10"}]


# ───────────────────────── calibration branchée sur le moteur ─────────────────────────
def calibrateur_centre(modele=None, date_max="2020-01-01"):
    """Calibrateur qui ramène toute probabilité vers 0,5 (poids ≈ 1 : n_matchs énorme)."""
    return cal.CalibrateurIsotone(((0.0, 0.40), (1.0, 0.60)), 10 ** 9, 10 ** 9,
                                  moteur.signature_modele() if modele is None else modele, date_max)


def test_calibration_appliquee_recalcule_tout_et_reste_coherente():
    m = un_match()
    non_cal = moteur.analyser_match(copy.deepcopy(m))
    res = moteur.analyser_match(copy.deepcopy(m), calibrateur=calibrateur_centre())
    assert res["calibration"]["statut"] == "CALIBRE" and "Probabilités non calibrées" not in res["alertes"]
    p = {k: l["proba_modele"] for k, l in lignes(res).items()}
    # identités logiques rétablies
    assert p["victoire"] + p["nul"] + p["defaite"] == pytest.approx(1.0)
    assert p["btts_oui"] + p["btts_non"] == pytest.approx(1.0)
    assert p["over_2_5"] + p["under_2_5"] == pytest.approx(1.0)
    assert p["over_1_5"] + p["under_1_5"] == pytest.approx(1.0)
    assert p["dc_1X"] == pytest.approx(p["victoire"] + p["nul"]) and p["dc_12"] == pytest.approx(p["victoire"] + p["defaite"])
    for l in res["inventaire"]:
        assert l["proba_brute"] == pytest.approx(proba(non_cal, l["marche"]))
        assert l["edge"] == pytest.approx(l["proba_modele"] - l["p_juste"])           # recalculés sur la probabilité calibrée
        assert l["ev"] == pytest.approx(l["proba_modele"] * l["cote"] - 1.0)
        assert (l["categorie"] is not None) == l["is_value"]
    probas = [l["proba_modele"] for l in res["inventaire"]]
    assert probas == sorted(probas, reverse=True)
    assert proba(res, "victoire") < proba(non_cal, "victoire")
    assert res["statut_global"] in ("ECRASANT_JOUABLE", "COMPROMIS", "AUCUN")


def test_aucun_marche_complementaire_ne_peut_etre_value_des_deux_cotes():
    """Après calibration cohérente, p(A) + p(non A) = 1 : les deux côtés ne peuvent plus battre ensemble leurs cotes."""
    res = moteur.analyser_match(un_match(att_d=1.5, def_d=1.2, att_e=1.2, def_e=1.5), calibrateur=calibrateur_centre())
    l = lignes(res)
    for a, b in (("over_2_5", "under_2_5"), ("btts_oui", "btts_non")):
        assert l[a]["proba_modele"] + l[b]["proba_modele"] == pytest.approx(1.0)
        assert not (l[a]["ev"] > 0.10 and l[b]["ev"] > 0.10)


def test_les_handicaps_demi_ligne_suivent_leurs_marches_equivalents():
    res = moteur.analyser_match(avec_handicaps(un_match()), calibrateur=calibrateur_centre())
    l = lignes(res)
    assert l["handicap_dom_-0_5"]["proba_modele"] == pytest.approx(l["victoire"]["proba_modele"])
    assert l["handicap_ext_+0_5"]["proba_modele"] == pytest.approx(l["dc_X2"]["proba_modele"])


def test_handicap_entier_avec_push_rembourse_n_est_pas_calibre():
    """Le calibrateur apprend « le pari est gagné » (égalité = perdu). Si l'égalité est remboursée, l'événement diffère."""
    c = calibrateur_centre()
    sans = moteur.analyser_match(avec_handicaps(un_match()), calibrateur=c)
    assert lignes(sans)["handicap_dom_-1_0"]["proba_modele"] != pytest.approx(lignes(sans)["handicap_dom_-1_0"]["proba_brute"])
    base.HANDICAP_ENTIER_REMBOURSE = True
    try:
        avec = moteur.analyser_match(avec_handicaps(un_match()), calibrateur=c)
    finally:
        base.HANDICAP_ENTIER_REMBOURSE = False
    h = lignes(avec)["handicap_dom_-1_0"]
    assert h["proba_modele"] == pytest.approx(h["proba_brute"])


def test_un_calibrateur_non_pret_est_ignore():
    res = moteur.analyser_match(un_match(), calibrateur=cal.CalibrateurIsotone(()))
    assert res["calibration"]["statut"] == "NON_CALIBRE"


def test_un_calibrateur_appris_pour_un_autre_modele_est_ignore():
    """Appliquer un calibrateur appris sur la v2.6.9 non lissée à des probabilités déjà lissées = double correction."""
    m = un_match()
    ref = moteur.analyser_match(copy.deepcopy(m))
    for autre in ("moteur_v2_6_9", moteur.signature_modele(lisser=False), ""):
        res = moteur.analyser_match(copy.deepcopy(m), calibrateur=calibrateur_centre(modele=autre))
        assert res["calibration"]["statut"] == "IGNORE_MODELE_DIFFERENT"
        assert any("Calibrateur ignoré" in a for a in res["alertes"])
        assert [l["proba_modele"] for l in res["inventaire"]] == [l["proba_modele"] for l in ref["inventaire"]]
    # et la signature suit les paramètres de lissage
    autre_params = lissage.ParametresLissage(k=8.0)
    assert moteur.signature_modele(True, autre_params) != moteur.signature_modele()
    res = moteur.analyser_match(copy.deepcopy(m), calibrateur=calibrateur_centre(), lissage_params=autre_params)
    assert res["calibration"]["statut"] == "IGNORE_MODELE_DIFFERENT"


def test_un_calibrateur_pas_anterieur_au_match_est_ignore():
    """Fuite d'information : un calibrateur qui a vu des matchs du jour du match (ou après) ne doit jamais servir."""
    m = un_match()
    for date_max, statut in (("2026-09-19", "CALIBRE"), ("2026-09-20", "IGNORE_ANACHRONIQUE"), ("2026-10-02", "IGNORE_ANACHRONIQUE")):
        res = moteur.analyser_match(copy.deepcopy(m), "2026-09-20", None, calibrateur=calibrateur_centre(date_max=date_max))
        assert res["calibration"]["statut"] == statut, date_max


def test_la_calibration_ne_change_pas_les_cotes_ni_les_marches():
    m = un_match()
    a, b = moteur.analyser_match(copy.deepcopy(m)), moteur.analyser_match(copy.deepcopy(m), calibrateur=calibrateur_centre())
    assert {(l["marche"], l["cote"]) for l in a["inventaire"]} == {(l["marche"], l["cote"]) for l in b["inventaire"]}


# ───────────────────────── ossature P1 / P2 / P3 ─────────────────────────
def test_les_champs_lus_par_la_selection_p1_p2_p3_sont_presents():
    """branchement_moteur.candidat_depuis_ligne lit ces champs : ils doivent exister sur chaque marché, calibré ou non."""
    for calibrateur in (None, calibrateur_centre()):
        res = moteur.analyser_match(un_match(), calibrateur=calibrateur)
        for l in res["inventaire"]:
            for cle in ("marche", "proba_modele", "cote", "p_juste", "edge", "ev", "categorie", "statut", "designation", "artefacts"):
                assert cle in l


# ───────────────────────── alertes ─────────────────────────
def test_alerte_ecart_inhabituel_seulement_sur_value_bets():
    assert risque.alertes_ligne({"is_value": True, "edge": 0.15}) != []
    assert risque.alertes_ligne({"is_value": True, "edge": 0.05}) == []
    assert risque.alertes_ligne({"is_value": False, "edge": 0.30}) == []


def test_alerte_buts_attendus_extremes():
    assert any("extrêmes" in a for a in risque.alertes_match({"lambda_dom": 0.5, "lambda_ext": 0.5}, "CALIBRE"))
    assert any("extrêmes" in a for a in risque.alertes_match({"lambda_dom": 2.5, "lambda_ext": 2.0}, "CALIBRE"))
    assert risque.alertes_match({"lambda_dom": 1.5, "lambda_ext": 1.1}, "CALIBRE") == []


def test_les_alertes_ne_changent_pas_la_selection():
    m = un_match()
    res = moteur.analyser_match(m)
    sans = base.analyser_match(lissage.lisser_match(m)[0])
    assert [(l["marche"], l["categorie"], l["designation"]) for l in res["inventaire"]] == \
           [(l["marche"], l["categorie"], l["designation"]) for l in sans["inventaire"]]
