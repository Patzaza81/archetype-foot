"""Cotes corners / cartons BetPawa (12/10/2026) : lecture du texte de la page, rattachement aux équipes, et passage dans
corners_cartons. Cas qui doivent réussir et cas qui doivent échouer. Format = celui du navigateur automatisé
(titre, puis étiquette et valeur sur deux lignes)."""
import pytest

import corners_cartons as cc
from parse_corners_cartons_betpawa import parse_corners_cartons_betpawa as parse

PAGE = """
1X2 | Full Time
1
3.24
X
3.63
2
2.15
Total Corners Over/Under | Full Time
Over 7.5
1.30
Under 7.5
3.25
Over 8.5
1.52
Under 8.5
2.37
Over 9.5
1.85
Under 9.5
1.85
Over 10.5
2.34
Under 10.5
1.53
Total Corners | Full Time
0-8
2.39
9-11
2.76
12+
3.12
Total Corners Coventry City | Full Time
0-2
4.75
3-4
2.88
5-6
3.32
7+
3.83
Total Corners Newcastle United | Full Time
0-2
5.21
3-4
2.98
5-6
3.26
7+
3.51
Total Bookings Over/Under | Full Time
Over 1.5
1.06
Under 1.5
6.31
Over 3.5
1.61
Under 3.5
2.09
Over 4.5
2.29
Under 4.5
1.51
Total Bookings Coventry City | Full Time
0-1
2.09
2
2.90
3
4.22
4+
5.24
Total Bookings Newcastle United | Full Time
0-1
2.11
2
2.90
3
4.21
4+
5.26
Player Sent Off | Full Time
Yes
3.67
No
1.21
Player Sent Off Coventry City | Full Time
Yes
5.70
No
1.08
"""


def test_total_corners_plus_et_moins_par_ligne():
    c = parse(PAGE, "Coventry", "Newcastle")
    assert c["corners_total_9.5"] == {"plus": 1.85, "moins": 1.85}
    assert c["corners_total_7.5"] == {"plus": 1.30, "moins": 3.25}
    assert "corners_total_11.5" not in c            # ligne non publiée : jamais reconstituée


def test_total_cartons_plus_et_moins_par_ligne():
    c = parse(PAGE, "Coventry", "Newcastle")
    assert c["cartons_total_3.5"] == {"plus": 1.61, "moins": 2.09}
    assert c["cartons_total_4.5"] == {"plus": 2.29, "moins": 1.51}


def test_corners_d_une_equipe_seule_la_tranche_7_plus_vaut_plus_de_6_5():
    c = parse(PAGE, "Coventry", "Newcastle")
    assert c["corners_domicile_6.5"] == {"plus": 3.83}
    assert c["corners_exterieur_6.5"] == {"plus": 3.51}
    assert not any(k.startswith("corners_domicile_") and not k.endswith("6.5") for k in c)   # « 3-4 », « 5-6 » ignorées


def test_cartons_d_une_equipe_seule_la_tranche_0_1_vaut_moins_de_1_5():
    c = parse(PAGE, "Coventry", "Newcastle")
    assert c["cartons_domicile_1.5"] == {"moins": 2.09}
    assert c["cartons_exterieur_1.5"] == {"moins": 2.11}


def test_carton_rouge_du_match_pas_celui_d_une_equipe():
    c = parse(PAGE, "Coventry", "Newcastle")
    assert c["rouge_match"] == {"oui": 3.67, "non": 1.21}


def test_page_sans_corners_ni_cartons_donne_un_dict_vide():
    assert parse("1X2 | Full Time\n1\n2.0\nX\n3.0\n2\n3.5\n", "A", "B") == {}
    assert parse("", "A", "B") == {}


def test_une_cote_impossible_est_ecartee_jamais_gardee():
    texte = "Total Corners Over/Under | Full Time\nOver 9.5\n0.95\nUnder 9.5\n1.85\nPlayer Sent Off | Full Time\nYes\n1.0\nNo\n1.2\n"
    c = parse(texte, "A", "B")
    assert c["corners_total_9.5"] == {"moins": 1.85}
    assert "rouge_match" not in c


def test_equipe_inconnue_dans_le_titre_n_est_pas_rattachee():
    texte = "Total Corners Autre Club | Full Time\n0-2\n4.0\n7+\n3.0\n"
    assert parse(texte, "Coventry", "Newcastle") == {}


def test_lignes_entieres_ignorees_car_remboursables():
    texte = "Total Corners Over/Under | Full Time\nOver 9\n1.9\nUnder 9\n1.9\n"
    assert parse(texte, "A", "B") == {}


# --- passage dans corners_cartons : seuil, côté dépassé, lignes que le modèle ne calcule pas ------------------------
def previsions():
    return {"corners": {"total": {"9.5": 0.60, "10.5": 0.30}, "domicile": {"6.5": 0.20}, "exterieur": {"6.5": 0.20}},
            "cartons": {"total": {"3.5": 0.55}, "domicile": {"1.5": 0.70}, "exterieur": {"1.5": 0.70}},
            "rouge": {"oui": 0.18, "taux_division": 0.2}}


def test_seuil_est_un_sur_cote_et_cote_du_cote_depasse():
    c = cc.cotes_du_match(parse(PAGE, "Coventry", "Newcastle"), previsions())
    ligne = c["corners"]["total"]["9.5"]
    assert ligne["seuil_plus"] == pytest.approx(1 / 1.85, abs=1e-4)
    assert ligne["modele_au_dessus"] == "plus"          # 60 % > 54,1 %
    assert c["corners"]["total"]["10.5"]["modele_au_dessus"] == "moins"   # moins = 70 % > 1/1,53 = 65,4 %


def test_un_cote_depasse_au_plus_jamais_les_deux():
    for p in (0.05, 0.3, 0.5, 0.7, 0.95):
        l = cc._ligne_cotes(p, {"plus": 1.80, "moins": 1.80})
        assert l["modele_au_dessus"] in (None, "plus", "moins")
    assert cc._ligne_cotes(0.5, {"plus": 1.80, "moins": 1.80})["modele_au_dessus"] is None


def test_ligne_hors_modele_ou_sans_cote_est_absente():
    c = cc.cotes_du_match(parse(PAGE, "Coventry", "Newcastle"), previsions())
    assert "8.5" not in c["corners"]["total"]            # le modèle de ce test ne calcule pas 8,5
    assert "domicile" in c["corners"] and "6.5" in c["corners"]["domicile"]
    assert c["cartons"]["domicile"]["1.5"] == {"moins": 2.09, "seuil_moins": pytest.approx(0.4785, abs=1e-4),
                                               "modele_au_dessus": None}   # moins = 30 % < 47,8 %


def test_carton_rouge_cotes_oui_non():
    c = cc.cotes_du_match(parse(PAGE, "Coventry", "Newcastle"), previsions())
    assert c["rouge"]["oui"] == 3.67 and c["rouge"]["non"] == 1.21
    assert c["rouge"]["modele_au_dessus"] is None         # non = 82 % < seuil 1/1,21 = 82,6 % : aucun côté au-dessus


def test_aucune_cote_donne_none():
    assert cc.cotes_du_match(None, previsions()) is None
    assert cc.cotes_du_match({}, previsions()) is None
    assert cc.cotes_du_match({"corners_total_9.5": {"plus": 0.9}}, previsions()) is None
