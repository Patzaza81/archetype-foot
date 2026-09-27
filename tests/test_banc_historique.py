"""Banc de test historique (banc_historique.py) : chaque règle testée sur au moins 3 cas qui passent et 3 qui échouent,
plus un verrou de non-régression sur les chiffres mesurés le 27/09/2026 (jeu figé de 501 matchs)."""
import gzip
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import banc_historique as bh  # noqa: E402

COTES = {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "dc_1X": 1.25, "dc_X2": 1.8, "dc_12": 1.33,
         "btts_oui": 1.8, "btts_non": 1.95, "over_2_5": 1.9, "under_2_5": 1.9}


# --- règles de gain ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("marche,h,a", [("victoire", 2, 1), ("dc_X2", 1, 1), ("over_2_5", 2, 1), ("btts_non", 3, 0),
                                        ("under_0_5", 0, 0)])
def test_marche_gagne(marche, h, a):
    assert bh.gagne(marche, h, a) is True


@pytest.mark.parametrize("marche,h,a", [("victoire", 1, 1), ("dc_12", 2, 2), ("over_2_5", 1, 1), ("btts_oui", 3, 0),
                                        ("under_1_5", 1, 1)])
def test_marche_perd(marche, h, a):
    assert bh.gagne(marche, h, a) is False


# --- probabilités du marché sans marge --------------------------------------------------------------------------------

def test_probabilites_marche_normalisees():
    p = bh.probabilites_marche(COTES)
    assert abs(p["victoire"] + p["nul"] + p["defaite"] - 1) < 1e-12
    assert abs(p["btts_oui"] + p["btts_non"] - 1) < 1e-12
    assert abs(p["over_2_5"] - 0.5) < 1e-12
    assert abs(p["dc_1X"] - (p["victoire"] + p["nul"])) < 1e-12          # déduite du 1X2, pas de la cote DC


@pytest.mark.parametrize("cotes,absent", [
    ({"victoire": 2.0, "nul": 3.4}, "victoire"),                         # groupe incomplet
    ({"btts_oui": 1.0, "btts_non": 1.9}, "btts_oui"),                    # cote <= 1 invalide
    ({"over_2_5": 1.9, "under_2_5": None}, "over_2_5"),                  # cote manquante
])
def test_probabilites_marche_groupe_incomplet(cotes, absent):
    assert absent not in bh.probabilites_marche(cotes)


# --- verdicts ---------------------------------------------------------------------------------------------------------

# Verdict sur les DEUX mesures (écart modèle - marché : négatif = modèle meilleur).
@pytest.mark.parametrize("ic_ll,ic_br,attendu", [
    ((-0.03, -0.01), (-0.02, -0.001), "AVANTAGE MESURABLE"),        # meilleur sur les deux
    ((-0.03, -0.01), (-0.01, 0.02), "AVANTAGE MESURABLE"),          # meilleur sur une, jamais pire
    ((-0.01, 0.02), (-0.02, -0.001), "AVANTAGE MESURABLE"),         # idem, l'autre mesure
])
def test_verdict_avantage_seulement_si_jamais_pire(ic_ll, ic_br, attendu):
    assert bh.verdict(150, 1000, ic_ll, ic_br) == attendu


@pytest.mark.parametrize("ic_ll,ic_br,attendu", [
    ((-0.03, -0.01), (0.001, 0.02), "MOINS BON QUE LE MARCHÉ"),     # meilleur en log-loss mais PIRE en Brier
    ((0.01, 0.03), (-0.02, -0.001), "MOINS BON QUE LE MARCHÉ"),     # pire en log-loss
    ((-0.01, 0.02), (-0.01, 0.01), "AUCUN AVANTAGE MESURABLE"),     # rien de significatif
])
def test_verdict_pire_sur_une_mesure_ou_rien(ic_ll, ic_br, attendu):
    assert bh.verdict(150, 1000, ic_ll, ic_br) == attendu


@pytest.mark.parametrize("n_matchs,n_obs,ic_ll,ic_br", [(99, 1000, (-0.03, -0.01), (-0.03, -0.01)),
                                                        (150, 199, (-0.03, -0.01), (-0.03, -0.01)),
                                                        (150, 1000, (-0.03, -0.01), None)])
def test_verdict_echantillon_insuffisant_jamais_de_conclusion(n_matchs, n_obs, ic_ll, ic_br):
    assert bh.verdict(n_matchs, n_obs, ic_ll, ic_br) == "ÉCHANTILLON INSUFFISANT"


# --- calibration : verdict propre, jamais « hors tolérance » sur un petit échantillon --------------------------------

@pytest.mark.parametrize("n,ecart,attendu", [(30, 0.05, "CALIBRATION_ACCEPTABLE"), (500, -0.049, "CALIBRATION_ACCEPTABLE"),
                                             (30, 0.0, "CALIBRATION_ACCEPTABLE")])
def test_tranche_acceptable(n, ecart, attendu):
    assert bh.statut_tranche(n, ecart) == attendu


@pytest.mark.parametrize("n,ecart,attendu", [(30, 0.051, "CALIBRATION_HORS_TOLERANCE"),
                                             (500, -0.20, "CALIBRATION_HORS_TOLERANCE"),
                                             (29, 0.30, "ÉCHANTILLON INSUFFISANT")])     # petit : jamais « mauvaise »
def test_tranche_hors_tolerance_ou_insuffisante(n, ecart, attendu):
    assert bh.statut_tranche(n, ecart) == attendu


@pytest.mark.parametrize("statuts,attendu", [
    (["CALIBRATION_ACCEPTABLE", "ÉCHANTILLON INSUFFISANT"], "CALIBRATION_ACCEPTABLE"),
    (["CALIBRATION_ACCEPTABLE", "CALIBRATION_HORS_TOLERANCE"], "CALIBRATION_HORS_TOLERANCE"),
    (["ÉCHANTILLON INSUFFISANT", "ÉCHANTILLON INSUFFISANT"], "ÉCHANTILLON INSUFFISANT"),
])
def test_verdict_calibration_global(statuts, attendu):
    assert bh.verdict_calibration([{"statut": s} for s in statuts]) == attendu


# --- évaluation complète sur un jeu synthétique -----------------------------------------------------------------------

def jeu_synthetique(n=150):
    scores = [(2, 0), (0, 1), (1, 1)]
    jeu = []
    for i in range(n):
        entree = {"id": f"m{i}", "date": "2026-09-20", "competition": "X", "source": "test", "n_lieu": 5,
                  "cotes": dict(COTES), "equipe_dom": bh._equipe_moyennes("A", 1.5, 1.0, 5),
                  "equipe_ext": bh._equipe_moyennes("B", 1.2, 1.3, 5), "assemblage": None}
        jeu.append((entree, scores[i % 3]))
    return jeu


def _oracle(jeu, confiance):
    """Modèle qui connaît le score (confiance proche de 1) ou qui se trompe systématiquement (proche de 0)."""
    reels = {e["id"]: sc for e, sc in jeu}

    def modele(entree):
        h, a = reels[entree["id"]]
        return {m: (confiance if bh.gagne(m, h, a) else 1 - confiance) for m in COTES}
    return modele


def test_modele_marche_ecart_nul():
    r = bh.evalue(jeu_synthetique(), bh.modele_marche, tirages=100)
    assert abs(r["global"]["ecart_logloss"]) < 1e-12 and r["global"]["verdict"] == "AUCUN AVANTAGE MESURABLE"


def test_oracle_avantage_mesurable():
    jeu = jeu_synthetique()
    assert bh.evalue(jeu, _oracle(jeu, 0.95), tirages=100)["global"]["verdict"] == "AVANTAGE MESURABLE"


def test_anti_oracle_moins_bon():
    jeu = jeu_synthetique()
    assert bh.evalue(jeu, _oracle(jeu, 0.05), tirages=100)["global"]["verdict"] == "MOINS BON QUE LE MARCHÉ"


def test_petit_jeu_aucune_conclusion():
    jeu = jeu_synthetique(60)
    assert bh.evalue(jeu, _oracle(jeu, 0.95), tirages=100)["global"]["verdict"] == "ÉCHANTILLON INSUFFISANT"


def test_modele_qui_plante_compte_jamais_masque():
    def casse(entree):
        raise KeyError("x")
    r = bh.evalue(jeu_synthetique(10), casse, tirages=50)
    assert r["global"] is None and r["rejets"] == {"ERREUR_MOTEUR": 10}
    assert r["rejets_detail"]["ERREUR_MOTEUR"] == {"KeyError": 10}


def test_codes_de_rejet_distincts():
    def modele(entree):
        return {"victoire": 1.4, "nul": 0.3, "defaite": None, "exact_goals_2": 0.3, "marche_invente": 0.5}
    r = bh.evalue(jeu_synthetique(10), modele, tirages=50)
    assert r["rejets"]["PROBABILITÉ_INVALIDE"] == 10                   # victoire = 1,4
    assert r["rejets_detail"]["MARCHÉ_NON_DISPONIBLE"]["defaite"] == 10  # absence explicite (None)
    assert r["rejets_detail"]["MARCHÉ_NON_DISPONIBLE"]["btts_oui"] == 10  # cote présente, rien du moteur
    assert r["rejets_detail"]["PAS_DE_COTE"]["exact_goals_2"] == 10      # probabilité sans cote : jamais évaluée
    assert r["rejets_detail"]["MARCHÉ_HORS_REGISTRE"]["marche_invente"] == 10
    assert r["global"]["observations"] == 10                            # seul « nul » est évalué


def test_match_sans_aucune_cote():
    jeu = jeu_synthetique(5)
    for e, _ in jeu:
        e["cotes"] = {}
    r = bh.evalue(jeu, bh.modele_marche, tirages=50)
    assert r["rejets"] == {"PAS_DE_COTE": 5} and r["global"] is None


# --- règle de décision de référence (V2) -----------------------------------------------------------------------------

def test_selection_v2_une_par_famille_au_plus_trois():
    cotes = {"victoire": 1.50, "dc_1X": 1.30, "btts_oui": 1.60, "over_1_5": 1.40, "under_3_5": 1.35}
    probas = {"victoire": 0.80, "dc_1X": 0.95, "btts_oui": 0.75, "over_1_5": 0.85, "under_3_5": 0.90}
    choix = bh.selection_regle_v2({"cotes": cotes}, probas)
    familles = [bh.MARCHES[m][0] for m in choix]
    assert len(choix) == 3 and len(set(familles)) == 3


@pytest.mark.parametrize("cote,p", [(1.20, 0.95), (1.80, 0.90), (1.50, 0.59)])
def test_selection_v2_refuse_hors_fenetre_ou_proba_faible(cote, p):
    assert bh.selection_regle_v2({"cotes": {"victoire": cote}}, {"victoire": p}) == []


# --- sources : jeu figé et archive de test ----------------------------------------------------------------------------

def test_snapshot_empreinte_et_chargement():
    assert bh.verifie_empreinte(bh.FICHIER_SNAPSHOT) is True
    jeu = bh.charge_snapshot()
    assert len(jeu) == 501
    assert all("handicap" not in k for e, _ in jeu for k in e["cotes"])


def test_snapshot_modifie_refuse(tmp_path):
    copie = tmp_path / "snap.json"
    shutil.copy(bh.FICHIER_SNAPSHOT, copie)
    shutil.copy(bh.FICHIER_SNAPSHOT + ".sha256", str(copie) + ".sha256")
    assert bh.verifie_empreinte(str(copie)) is True
    with open(copie, "a", encoding="utf-8") as f:
        f.write(" ")
    assert bh.verifie_empreinte(str(copie)) is False
    os.remove(str(copie) + ".sha256")
    assert bh.verifie_empreinte(str(copie)) is False


def _enreg(mid, date="2026-09-27", testable=True, score=(2, 1), dates_equipe=("2026-09-10", "2026-09-14")):
    matchs_dom = [{"date": dates_equipe[0], "domicile": True, "buts_marques": 2, "buts_encaisses": 0}]
    matchs_ext = [{"date": dates_equipe[1], "domicile": False, "buts_marques": 1, "buts_encaisses": 1}]
    return {"match_id": mid, "date": date, "competition": "Italie : Série C", "domicile": "A", "exterieur": "B",
            "testable": testable, "score": {"buts_dom": score[0], "buts_ext": score[1]} if score else None,
            "cotes_betpawa": {"1x2": {"1": 2.0, "N": 3.3, "2": 3.6}, "btts": {"Oui": 1.8, "Non": 1.9},
                              "over_under_2.5": {"plus": 1.9, "moins": 1.9},
                              "handicap_1.5": {"domicile": 1.2, "exterieur": 4.6}},
            "cotes_observees": {"Double chance - 12": 1.3},
            "equipe_dom": {"matchs": matchs_dom}, "equipe_ext": {"matchs": matchs_ext}, "assemblage": {"statut": "OK"}}


def _ecrit(dossier, enregs):
    os.makedirs(dossier, exist_ok=True)
    with gzip.open(os.path.join(dossier, "2026-09-27.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({e["match_id"]: e for e in enregs}, f)


def test_archive_charge_uniquement_testables_avec_score(tmp_path):
    d = str(tmp_path / "archive")
    _ecrit(d, [_enreg("ok1"), _enreg("ok2", score=(0, 0)), _enreg("ok3", score=(1, 3)),
               _enreg("sans_score", score=None), _enreg("non_testable", testable=False),
               _enreg("fuite", dates_equipe=("2026-09-10", "2026-09-27"))])
    jeu, fuite = bh.charge_archive(d)
    assert sorted(e["id"] for e, _ in jeu) == ["ok1", "ok2", "ok3"] and fuite == 1
    e = dict((x["id"], x) for x, _ in jeu)["ok1"]
    assert e["cotes"]["victoire"] == 2.0 and e["cotes"]["dc_12"] == 1.3 and e["n_lieu"] == 1
    assert e["equipe_dom"]["buts_marques_moy"] == 2 and e["equipe_ext"]["buts_encaisses_moy"] == 1
    assert not any("handicap" in k for k in e["cotes"])          # handicaps exclus (étiquettes BetPawa incohérentes)


# --- verrou de non-régression : chiffres mesurés le 27/09/2026 sur le jeu figé --------------------------------------

def test_non_regression_v2_sur_le_jeu_fige():
    perim = bh.PERIMETRE_REFERENCE_2709
    r = bh.evalue(bh.charge_snapshot(), bh.restreint(bh.modele_v2_produit, perim),
                  bh.restreint(bh.selection_regle_v2, perim), tirages=50)
    sel = r["selection"]
    assert sel["selections"] == 548 and sel["matchs"] == 353
    assert abs(sel["reussite_reelle"] - 0.6332) < 0.0005 and abs(sel["reussite_annoncee"] - 0.8190) < 0.0005
    assert abs(sel["roi"] - (-0.062)) < 0.001
    assert r["global"]["verdict"] == "MOINS BON QUE LE MARCHÉ"


def test_erreur_de_la_regle_de_decision_comptee():
    def regle_cassee(entree, probas):
        raise ValueError("x")
    sel = bh.evalue(jeu_synthetique(10), bh.modele_marche, regle_cassee, tirages=50)["selection"]
    assert sel["selections"] == 0 and sel["erreurs"] == {"ValueError": 10}
    assert "ERREURS" in bh.rapport_texte("t", bh.evalue(jeu_synthetique(10), bh.modele_marche, regle_cassee, tirages=50))


def test_perimetre_de_reference_jamais_modifie():
    attendu = {"victoire", "nul", "defaite", "dc_1X", "dc_X2", "dc_12", "btts_oui", "btts_non"} | \
        {f"{s}_{x}_5" for s in ("over", "under") for x in range(5)}
    assert set(bh.PERIMETRE_REFERENCE_2709) == attendu


# --- registre complet : règles de gain et marge retirée --------------------------------------------------------------

@pytest.mark.parametrize("marche,h,a", [("over_5_5", 4, 2), ("buts_dom_over_1_5", 2, 0), ("clean_sheet_dom", 3, 0),
                                        ("clean_sheet_ext_non", 1, 0), ("exact_goals_3", 2, 1),
                                        ("exact_goals_6_plus", 4, 3), ("buts_ext_under_0_5", 5, 0)])
def test_nouveaux_marches_gagnent(marche, h, a):
    assert bh.gagne(marche, h, a) is True


@pytest.mark.parametrize("marche,h,a", [("over_5_5", 3, 2), ("buts_dom_over_1_5", 1, 3), ("clean_sheet_dom", 0, 1),
                                        ("clean_sheet_ext_non", 0, 4), ("exact_goals_3", 2, 2),
                                        ("exact_goals_6_plus", 3, 2), ("buts_ext_under_0_5", 0, 1)])
def test_nouveaux_marches_perdent(marche, h, a):
    assert bh.gagne(marche, h, a) is False


def test_nombre_exact_normalise_sur_ses_7_issues():
    cotes = {f"exact_goals_{n}": c for n, c in zip(range(6), (9.0, 4.5, 3.4, 3.8, 5.5, 9.5))}
    cotes["exact_goals_6_plus"] = 14.0
    p = bh.probabilites_marche(cotes)
    assert abs(sum(p[f"exact_goals_{n}"] for n in range(6)) + p["exact_goals_6_plus"] - 1) < 1e-12


@pytest.mark.parametrize("cotes,oui,attendu_non", [
    ({"clean_sheet_dom": 3.0, "clean_sheet_dom_non": 1.35}, "clean_sheet_dom", "clean_sheet_dom_non"),
    ({"clean_sheet_dom": 3.0, "buts_ext_over_0_5": 1.35}, "clean_sheet_dom", "buts_ext_over_0_5"),  # même événement
    ({"clean_sheet_ext": 4.0, "buts_dom_over_0_5": 1.2}, "clean_sheet_ext", "buts_dom_over_0_5"),
])
def test_cage_inviolee_marge_retiree_avec_son_complement(cotes, oui, attendu_non):
    p = bh.probabilites_marche(cotes)
    attendu = (1 / cotes[oui]) / (1 / cotes[oui] + 1 / cotes[attendu_non])
    assert abs(p[oui] - attendu) < 1e-12 and abs(p[oui] + p[oui + "_non"] - 1) < 1e-12


@pytest.mark.parametrize("cotes,absent", [
    ({"clean_sheet_dom": 3.0}, "clean_sheet_dom"),                                       # aucun complément
    ({f"exact_goals_{n}": 5.0 for n in range(6)}, "exact_goals_0"),                     # 6+ manquant
    ({"buts_dom_over_0_5": 1.3}, "buts_dom_over_0_5"),                                  # paire incomplète
])
def test_aucune_probabilite_inventee_pour_un_groupe_incomplet(cotes, absent):
    assert absent not in bh.probabilites_marche(cotes)


def test_archive_nouveaux_marches_betpawa():
    e = {"cotes_betpawa": {"nombre_exact_buts": {"0": 9.0, "6+": 14.0}, "over_under_5.5": {"plus": 6.0, "moins": 1.1},
                           "over_under_domicile_1.5": {"plus": 2.2, "moins": 1.6},
                           "cages_inviolees_exterieur": {"oui": 3.2, "non": 1.3}},
         "cotes_observees": {"Cage inviolée - Domicile": 2.9, "Plus de 0.5 buts - Extérieur": 1.4}}
    c = bh.cotes_archive(e)
    assert c["exact_goals_0"] == 9.0 and c["exact_goals_6_plus"] == 14.0 and c["over_5_5"] == 6.0
    assert c["buts_dom_over_1_5"] == 2.2 and c["clean_sheet_ext_non"] == 1.3
    assert c["clean_sheet_dom"] == 2.9 and c["buts_ext_over_0_5"] == 1.4


@pytest.mark.parametrize("libelle,marche,h,a,gagnant", [
    ("Cage inviolée - Domicile", "clean_sheet_dom", 2, 0, True),
    ("Encaisse au moins 1 but - Domicile", "clean_sheet_dom_non", 2, 1, True),     # le domicile encaisse
    ("Encaisse au moins 1 but - Extérieur", "clean_sheet_ext_non", 1, 0, True),    # l'extérieur encaisse
    ("Encaisse au moins 1 but - Domicile", "clean_sheet_dom_non", 3, 0, False),
    ("Cage inviolée - Extérieur", "clean_sheet_ext", 1, 1, False),
    ("Encaisse au moins 1 but - Extérieur", "clean_sheet_ext_non", 0, 2, False),
])
def test_libelles_cage_inviolee_relies_a_la_bonne_equipe(libelle, marche, h, a, gagnant):
    assert bh.cotes_archive({"cotes_observees": {libelle: 2.0}}) == {marche: 2.0}
    assert bh.gagne(marche, h, a) is gagnant


def test_restreint_filtre_modele_et_selection():
    m = bh.restreint(lambda e: {"victoire": 0.5, "over_5_5": 0.1}, {"victoire"})
    s = bh.restreint(lambda e, p: ["victoire", "over_5_5"], {"victoire"})
    assert m({}) == {"victoire": 0.5} and s({}, {}) == ["victoire"]


def test_rapport_separe_performance_et_calibration():
    texte = bh.rapport_texte("t", bh.evalue(jeu_synthetique(), bh.modele_marche, tirages=50))
    assert "PERFORMANCE VS MARCHÉ" in texte and "\nCALIBRATION :" in texte
    assert texte.index("-- Par marché") < texte.index("-- Par famille") < texte.index("-- Par taille")
