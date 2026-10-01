# -*- coding: utf-8 -*-
"""Tests de moteur_v2_6_10 : lissage, calibration isotone, alertes, et intégration avec moteur_v2_6_9.

Les tests d'intégration vérifient des PROPRIÉTÉS (schéma conservé, probabilités moins extrêmes, calibration
monotone, sélection P1/P2/P3 inchangée dans sa forme), pas des valeurs numériques figées.
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
from moteur_v2_6_10 import lissage, risque  # noqa: E402


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


def proba(res, marche):
    return {l["marche"]: l for l in res["inventaire"]}[marche]["proba_modele"]


# ───────────────────────── lissage ─────────────────────────
def test_lisse_formule_exacte():
    assert lissage.lisse(3.0, 4) == pytest.approx((4 * 3.0 + 4 * 1.35) / 8)
    assert lissage.lisse(1.35, 7) == pytest.approx(1.35)


def test_lisse_grand_echantillon_garde_sa_valeur():
    assert abs(lissage.lisse(3.0, 400) - 3.0) < 0.02


def test_lisse_parametres_fixes_a_l_avance():
    assert lissage.MOYENNE_REFERENCE == 1.35 and lissage.K_LISSAGE == 4.0


def test_niveaux_d_echantillon():
    assert [lissage.niveau_echantillon(n) for n in (None, 0, 2, 4, 6, 9, 12)] == [
        "INCONNU", "IMPOSSIBLE", "TRES_FAIBLE", "FAIBLE", "UTILISABLE", "SOLIDE", "TRES_SOLIDE"]


def test_lisser_equipe_ne_modifie_pas_l_original():
    eq = {"nom": "A", "buts_marques_moy": 3.0, "buts_encaisses_moy": 0.4, "matchs_joues": 3}
    avant = copy.deepcopy(eq)
    lisse, trace = lissage.lisser_equipe(eq)
    assert eq == avant
    assert lisse["buts_marques_moy"] < 3.0 and lisse["buts_encaisses_moy"] > 0.4
    assert trace["poids_reference"] == pytest.approx(4 / 7)


def test_lisser_equipe_matchs_recents_devient_moyennes_et_effectif():
    eq = {"nom": "A", "matchs_recents": [[2, 0], [4, 1]]}
    lisse, trace = lissage.lisser_equipe(eq)
    assert "matchs_recents" not in lisse and lisse["matchs_joues"] == 2
    assert trace["attaque_brute"] == 3.0 and trace["n"] == 2


def test_effectif_inconnu_utilise_la_valeur_par_defaut_et_reste_inconnu_pour_le_moteur():
    eq = {"nom": "A", "buts_marques_moy": 2.0, "buts_encaisses_moy": 1.0}
    lisse, trace = lissage.lisser_equipe(eq)
    assert trace["n"] is None and trace["n_utilise"] == lissage.N_PAR_DEFAUT
    assert "matchs_joues" not in lisse


def test_valeur_aberrante_n_est_jamais_rattrapee_par_le_lissage():
    eq = {"nom": "A", "buts_marques_moy": 12.0, "buts_encaisses_moy": 1.0, "matchs_joues": 5}
    lisse, trace = lissage.lisser_equipe(eq)
    assert lisse is eq and trace is None            # inchangée : le moteur de base la refusera (V5)
    res = moteur.analyser_match(un_match(att_d=12.0))
    assert res["statut_global"] == "SKIP" and "V5" in (res["raison_skip"] or "")


def test_equipe_invalide_laissee_au_moteur_de_base():
    lisse, trace = lissage.lisser_equipe({"nom": "A"})
    assert trace is None
    assert moteur.analyser_match(un_match(equipe_dom={"nom": "A"}))["statut_global"] == "SKIP"


def test_matchs_joues_invalide_garde_son_avertissement():
    m = un_match()
    m["equipe_dom"]["matchs_joues"] = 0
    res = moteur.analyser_match(m)
    assert any("matchs_joues invalide" in a for a in res["avertissements_match"])


def test_lisser_match_ne_modifie_pas_le_match():
    m = un_match()
    avant = copy.deepcopy(m)
    lissage.lisser_match(m)
    assert m == avant


# ───────────────────────── intégration : surconfiance ─────────────────────────
def test_lissage_rend_les_probabilites_moins_extremes():
    m = un_match()                                   # grand favori sur 5 matchs
    brut = base.analyser_match(copy.deepcopy(m))
    lisse = moteur.analyser_match(copy.deepcopy(m))
    assert brut["statut_global"] != "SKIP" and lisse["statut_global"] != "SKIP"
    assert proba(lisse, "victoire") < proba(brut, "victoire")
    assert proba(lisse, "defaite") > proba(brut, "defaite")
    assert lisse["lambda_dom"] < brut["lambda_dom"]


def test_sans_lissage_on_retrouve_exactement_la_v2_6_9():
    m = un_match()
    a = base.analyser_match(copy.deepcopy(m))
    b = moteur.analyser_match(copy.deepcopy(m), lisser=False)
    assert [(l["marche"], l["proba_modele"], l["ev"], l["categorie"]) for l in a["inventaire"]] == \
           [(l["marche"], l["proba_modele"], l["ev"], l["categorie"]) for l in b["inventaire"]]
    assert a["verdict"] == b["verdict"] and a["statut_global"] == b["statut_global"]


def test_l_effet_du_lissage_diminue_quand_l_echantillon_grandit():
    ecarts = []
    for n in (3, 12, 60):
        brut = base.analyser_match(un_match(n=n))
        lisse = moteur.analyser_match(un_match(n=n))
        ecarts.append(abs(proba(brut, "victoire") - proba(lisse, "victoire")))
    assert ecarts[0] > ecarts[1] > ecarts[2]


def test_le_resultat_est_un_sur_ensemble_du_schema_de_la_v2_6_9():
    m = un_match()
    res = moteur.analyser_match(m)
    assert set(base.resultat_vide(m)) <= set(res)
    for cle in ("moteur", "version_moteur", "lissage", "calibration", "alertes"):
        assert cle in res
    assert res["moteur"] == "moteur_v2_6_10" and res["calibration"]["statut"] == "NON_CALIBRE"
    assert "Probabilités non calibrées" in res["alertes"]
    for l in res["inventaire"]:
        assert {"marche", "proba_modele", "p_juste", "cote", "edge", "ev", "statut", "is_value", "categorie"} <= set(l)
        assert l["proba_brute"] == l["proba_modele"]


def test_le_match_d_origine_n_est_pas_modifie_par_l_analyse():
    m = un_match()
    avant = copy.deepcopy(m)
    moteur.analyser_match(m)
    assert m == avant


def test_un_skip_reste_un_skip_avec_les_champs_ajoutes():
    res = moteur.analyser_match(un_match(cotes={"victoire": 2.0}))
    assert res["statut_global"] == "SKIP" and res["alertes"] == [] and res["moteur"] == "moteur_v2_6_10"


# ───────────────────────── calibration ─────────────────────────
def observations(n_matchs, f=lambda p: p, par_match=12):
    """Observations déterministes : pour chaque match, `par_match` marchés distincts de probabilité p, gagnés selon f(p)."""
    out = []
    for i in range(n_matchs):
        for j in range(par_match):
            p = (j + 0.5) / par_match
            # le « résultat » est déterministe : gagné si la position du match dans le cycle est sous f(p)
            gagne = ((i % 20) + 0.5) / 20 < f(p)
            out.append({"match_id": f"m{i}", "marche": f"marche_{j}", "proba": p, "gagne": gagne, "date": f"2026-09-{1 + i % 28:02d}"})
    return out


def test_calibration_refuse_un_echantillon_insuffisant():
    c, diag = cal.apprendre(observations(10))
    assert c is None and diag["raison"] in ("OBSERVATIONS_INSUFFISANTES", "MATCHS_INSUFFISANTS")
    c, diag = cal.apprendre(observations(40, par_match=10))        # 400 observations mais 40 matchs
    assert c is None and diag["raison"] == "MATCHS_INSUFFISANTS"


def test_calibration_monotone_et_corrige_la_surconfiance():
    # Modèle trop extrême : la réalité est la probabilité annoncée ramenée vers 0,5.
    c, diag = cal.apprendre(observations(100, f=lambda p: 0.5 + 0.6 * (p - 0.5)))
    assert c is not None and diag["pret"]
    ys = [c.predire(x / 100) for x in range(1, 100)]
    assert all(b >= a - 1e-12 for a, b in zip(ys, ys[1:]))         # monotone
    assert c.predire(0.9) < 0.9 and c.predire(0.1) > 0.1          # tirée vers le centre
    assert cal.PLANCHER <= min(ys) and max(ys) <= cal.PLAFOND


def test_calibration_ne_sort_jamais_0_ou_1():
    c = cal.CalibrateurIsotone(((0.1, 0.0), (0.9, 1.0)))
    assert c.predire(0.0) == cal.PLANCHER and c.predire(1.0) == cal.PLAFOND


def test_calibration_aller_retour_json():
    c, _ = cal.apprendre(observations(100))
    d = cal.CalibrateurIsotone.from_dict(c.to_dict())
    assert d.points == c.points and d.n_matchs == c.n_matchs
    with pytest.raises(ValueError):
        cal.CalibrateurIsotone.from_dict({"schema": 1, "points": [[0.2, 0.9], [0.8, 0.1]]})


def test_marches_equivalents_comptent_une_fois():
    assert cal.marche_equivalent("handicap_dom_-0_5") == "victoire"
    assert cal.marche_equivalent("handicap_ext_+0_5") == "dc_X2"
    assert cal.marche_equivalent("handicap_dom_+0_5") == "dc_1X"
    assert cal.marche_equivalent("handicap_ext_-0_5") == "defaite"
    assert cal.marche_equivalent("clean_sheet_dom") == "buts_ext_under_0_5"
    assert cal.marche_equivalent("handicap_dom_-1_5") == "handicap_dom_-1_5"
    obs = [{"match_id": 1, "marche": "victoire", "proba": 0.6, "gagne": 1},
           {"match_id": 1, "marche": "handicap_dom_-0_5", "proba": 0.6, "gagne": 1},
           {"match_id": 2, "marche": "handicap_dom_-0_5", "proba": 0.6, "gagne": 0}]
    assert len(cal.dedoublonne(obs)) == 2


def test_observations_invalides_ecartees():
    mauvaises = [{"match_id": 1, "marche": "x", "proba": 0.0, "gagne": 1}, {"match_id": 1, "marche": "x", "proba": 1.0, "gagne": 1},
                 {"match_id": None, "marche": "x", "proba": 0.5, "gagne": 1}, {"match_id": 1, "marche": "x", "proba": 0.5, "gagne": None},
                 {"match_id": 1, "marche": "x", "proba": True, "gagne": 1}]
    assert cal.dedoublonne(mauvaises) == []


def test_avant_ne_garde_que_le_passe_strict_et_refuse_sans_date():
    obs = [{"date": "2026-09-10"}, {"date": "2026-09-20"}, {"date": "2026-09-21"}, {}]
    assert cal.avant(obs, "2026-09-20") == [{"date": "2026-09-10"}]


# ───────────────────────── calibration branchée sur le moteur ─────────────────────────
def calibrateur_centre():
    """Calibrateur qui ramène toute probabilité vers 0,5 (surconfiance corrigée à l'extrême)."""
    return cal.CalibrateurIsotone(((0.0, 0.40), (1.0, 0.60)), 1000, 80)


def test_calibration_appliquee_recalcule_tout_avec_les_fonctions_du_moteur_de_base():
    m = un_match()
    non_cal = moteur.analyser_match(copy.deepcopy(m))
    res = moteur.analyser_match(copy.deepcopy(m), calibrateur=calibrateur_centre())
    assert res["calibration"]["statut"] == "CALIBRE" and "Probabilités non calibrées" not in res["alertes"]
    for l in res["inventaire"]:
        assert 0.40 - 1e-9 <= l["proba_modele"] <= 0.60 + 1e-9
        assert l["proba_brute"] == pytest.approx(proba(non_cal, l["marche"]))
        # edge et EV recalculés sur la probabilité calibrée
        assert l["edge"] == pytest.approx(l["proba_modele"] - l["p_juste"])
        assert l["ev"] == pytest.approx(l["proba_modele"] * l["cote"] - 1.0)
    probas = [l["proba_modele"] for l in res["inventaire"]]
    assert probas == sorted(probas, reverse=True)                  # tri du moteur conservé (probabilité décroissante)
    assert proba(res, "victoire") < proba(non_cal, "victoire")
    # catégories et désignations recalculées de façon cohérente
    for l in res["inventaire"]:
        assert (l["categorie"] is not None) == l["is_value"]
    assert res["statut_global"] in ("ECRASANT_JOUABLE", "COMPROMIS", "AUCUN")


def test_calibration_un_calibrateur_non_pret_est_ignore():
    res = moteur.analyser_match(un_match(), calibrateur=cal.CalibrateurIsotone(()))
    assert res["calibration"]["statut"] == "NON_CALIBRE"


def test_la_calibration_ne_change_pas_les_cotes_ni_les_marches():
    m = un_match()
    a = moteur.analyser_match(copy.deepcopy(m))
    b = moteur.analyser_match(copy.deepcopy(m), calibrateur=calibrateur_centre())
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
    assert any("extrêmes" in a for a in risque.alertes_match({"lambda_dom": 0.5, "lambda_ext": 0.5}, True))
    assert any("extrêmes" in a for a in risque.alertes_match({"lambda_dom": 2.5, "lambda_ext": 2.0}, True))
    assert risque.alertes_match({"lambda_dom": 1.5, "lambda_ext": 1.1}, True) == []


def test_les_alertes_ne_changent_pas_la_selection():
    m = un_match()
    res = moteur.analyser_match(m)
    sans = base.analyser_match(lissage.lisser_match(m)[0])
    assert [(l["marche"], l["categorie"], l["designation"]) for l in res["inventaire"]] == \
           [(l["marche"], l["categorie"], l["designation"]) for l in sans["inventaire"]]


# ───────────────────────── isolation ─────────────────────────
def test_le_moteur_de_base_n_est_pas_modifie():
    """Importer moteur_v2_6_10 ne touche à aucune constante de la v2.6.9."""
    assert base.LAMBDA_MIN == 0.05 and base.SEUIL_VALUE_EDGE_MIN == 0.03 and base.HANDICAP_ENTIER_REMBOURSE is False
    assert base.calcul_lambdas(1.5, 1.0, 1.0, 1.5) == (1.5, 1.0)
