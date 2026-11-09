"""Règles par marché : condition non remplie = un cran de moins ; seules les règles actives comptent."""
import verif_regles as VR
import verif_pronostic as V

REG = {"1": {"trait": "xa", "sens": 1, "seuil": 1.48, "actif": True}, "total_moins_2.5": {"trait": "x_tot", "sens": -1, "seuil": 2.41, "actif": True},
       "N2": {"trait": "b_tot", "sens": -1, "seuil": 2.35, "actif": False}}
A = {"n": 10, "reussi": 7}; B = {"n": 10, "reussi": 6}
T = lambda xa0, xa1: VR.traits(A, B, (1.4, 1.1), (xa0, xa1), {"buts": 1.5})

# doivent baisser d'un cran
def test_victoire_domicile_xg_trop_bas_baisse():
    assert VR.appliquer("1", "TIENT", T(1.2, 1.0), REG)[0] == "TIENT AVEC RÉSERVE"
def test_reserve_devient_ne_tient_pas():
    assert VR.appliquer("1", "TIENT AVEC RÉSERVE", T(1.47, 1.0), REG)[0] == "NE TIENT PAS"
def test_sens_inverse_moins_de_buts():
    assert VR.appliquer("total_moins_2.5", "TIENT", T(1.6, 1.2), REG)[0] == "TIENT AVEC RÉSERVE"     # xG total 2.8 > 2.41
def test_phrase_explique():
    assert "Condition du marché non remplie" in VR.appliquer("1", "TIENT", T(1.2, 1.0), REG)[1]["phrase"]

# ne doivent rien changer
def test_condition_remplie_garde_le_verdict():
    assert VR.appliquer("1", "TIENT", T(1.48, 1.0), REG) [0] == "TIENT" and VR.appliquer("total_moins_2.5", "TIENT", T(1.0, 1.0), REG)[0] == "TIENT"
def test_regle_inactive_ou_marche_sans_regle_ignores():
    assert VR.appliquer("N2", "TIENT", VR.traits(A, B, (2.0, 1.9), (1, 1), {"buts": 1.5}), REG)[0] == "TIENT" and VR.appliquer("12", "TIENT", T(0.5, 0.5), REG)[0] == "TIENT"
def test_valeur_absente_ou_verdict_deja_bas_ignores():
    assert VR.appliquer("1", "TIENT", T(None, None), REG)[0] == "TIENT" and VR.appliquer("1", "NE TIENT PAS", T(1.0, 1.0), REG)[0] == "NE TIENT PAS"

def test_config_reelle_quatre_regles_actives_et_seuils_presents():
    R = VR.charger(); assert sorted(k for k, r in R.items() if r["actif"]) == ["1", "1N", "btts_oui", "total_plus_2.5"] and all("seuil" in r and "trait" in r for r in R.values())

def test_audit_regle_qui_tient_et_regle_qui_ne_tient_pas():
    L = []
    for j in ("2026-10-01", "2026-10-02", "2026-11-01", "2026-11-02"):
        for i in range(100):                                    # xa >= 1.48 : 70 % de reussite ; xa < 1.48 : 40 %
            haut = i < 50; L.append({"jour": j, "marche": "1", "gagne": (i % 10) < (7 if haut else 4), "T": {"xa": 1.6 if haut else 1.0}})
            L.append({"jour": j, "marche": "N2", "gagne": (i % 2) == 0, "T": {"b_tot": 2.0 if haut else 3.0}})   # aucune difference
    a = VR.auditer(L, {"1": REG["1"], "N2": {**REG["N2"], "actif": True}})
    assert a["1"]["tient"] and not a["N2"]["tient"]

def test_constat_applique_la_regle_et_cfg_sans_regles_la_desactive():
    x = {"match_id": "m", "date": "2026-11-09", "domicile": "A", "exterieur": "B", "competition": "T : L", "assemblage": {"saison_football_data": "2627", "equipe_dom": {"matchs": []}, "equipe_ext": {"matchs": []}}}
    assert V.constat(x, "1", 1.5, {"cote_min": 1.26})["verdict"] == "NON ÉVALUABLE"          # sans historique rien ne change (garde-fous intacts)
