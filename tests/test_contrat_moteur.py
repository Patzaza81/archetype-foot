"""A5 (24/09/2026) : contrat de transmission au moteur. Données conformes qui doivent passer, écarts qui doivent être
refusés. Si un format change sans mise à jour du contrat, ces tests échouent."""
import copy
import json
import os

import pytest

import contrat_moteur as cm

FD = {"date": "2026-09-20", "domicile": True, "adversaire": "Hull", "buts_marques": 2, "buts_encaisses": 1,
      "buts_marques_mi_temps": 1, "buts_encaisses_mi_temps": 0, "tirs": 12, "tirs_concedes": 7, "tirs_cadres": 5,
      "tirs_cadres_concedes": 2, "corners": 6, "corners_concedes": 3, "cartons_jaunes": 1, "cartons_rouges": 0,
      "xg": 1.31, "xg_concede": 0.72, "source": "football-data", "provisoire": False, "saison": "2627"}
MED_PROV = {"date": "2026-09-23", "domicile": False, "adversaire": "Leeds", "buts_marques": 0, "buts_encaisses": 0,
            "url_match": "/live-score/x.html", "source": "matchendirect", "provisoire": True}
COUVERTE = {"cle_cache": "u/norwich_1.html||angleterre : championnat", "competition": "angleterre : championnat",
            "couverte_par_football_data": True, "division_football_data": "E1", "nom_football_data": "Norwich",
            "nom_matchendirect": "Norwich", "matchs_sans_date_ignores": 0, "matchs": [FD, MED_PROV]}
NON_COUVERTE = {"cle_cache": "u/tns_1.html||pays de galles : cymru premier", "competition": "pays de galles : cymru premier",
                "couverte_par_football_data": False, "raison": "championnat non couvert par Football-Data",
                "matchs": [{"date": "2026-09-19", "domicile": True, "adversaire": "Llandudno", "buts_marques": 2,
                            "buts_encaisses": 1, "url_match": "/x", "source": "matchendirect", "provisoire": False}]}


def doc(*equipes):
    return {"version_contrat": cm.VERSION_CONTRAT, "equipes": [copy.deepcopy(e) for e in equipes]}


# --- doivent être CONFORMES -------------------------------------------------------------------------------------------
def test_equipe_couverte_avec_provisoire_conforme():
    assert cm.erreurs_assemblage(doc(COUVERTE)) == []


def test_equipe_non_couverte_conforme():
    assert cm.erreurs_assemblage(doc(NON_COUVERTE)) == []


def test_champs_absents_null_acceptes():
    d = doc(COUVERTE)
    d["equipes"][0]["matchs"][0].update(xg=None, corners=None, buts_marques_mi_temps=None)   # donnée non publiée
    assert cm.erreurs_assemblage(d) == []


def test_lecture_par_le_moteur(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps(doc(COUVERTE, NON_COUVERTE)), encoding="utf-8")
    d = cm.charge_assemblage(str(p))
    assert cm.equipe(d, "u/tns_1.html", "Pays de Galles : Cymru Premier")["raison"].startswith("championnat non couvert")
    assert cm.equipe(d, "u/inconnue.html", "x") is None


# --- doivent être REFUSÉS ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("modif,message", [
    (lambda d: d["equipes"][0]["matchs"][0].update(provisoire=True), "jamais provisoire"),
    (lambda d: d["equipes"][0]["matchs"][1].update(corners=4), "ne porte pas de données Football-Data"),
    (lambda d: d["equipes"][0]["matchs"][1].update(date="2026-09-21"), "doublon probable"),
    (lambda d: d["equipes"][0]["matchs"][0].update(buts_marques=True), "de type bool"),
    (lambda d: d["equipes"][0]["matchs"][0].update(source="besoccer"), "source inconnue"),
    (lambda d: d["equipes"][0].pop("nom_football_data"), "obligatoire pour une équipe couverte"),
    (lambda d: d["equipes"][1].pop("raison"), "« raison » obligatoire"),
    (lambda d: d.update(version_contrat=99), "version_contrat"),
    (lambda d: d["equipes"][1]["matchs"][0].update(provisoire=True), "n'existe que pour un championnat couvert"),
])
def test_ecart_refuse(modif, message):
    d = doc(COUVERTE, NON_COUVERTE)
    modif(d)
    erreurs = cm.erreurs_assemblage(d)
    assert any(message in e for e in erreurs), erreurs


def test_moteur_refuse_un_fichier_non_conforme(tmp_path):
    d = doc(COUVERTE)
    d["equipes"][0]["matchs"][0]["provisoire"] = True
    p = tmp_path / "a.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(cm.ContratRompu):
        cm.charge_assemblage(str(p))


def test_correspondances_nom_relie_deux_fois_refuse():
    corr = {"divisions": {"E1": {"equipes": {"Man City": {"matchendirect": "Manchester", "preuves": 3},
                                             "Man United": {"matchendirect": "Manchester", "preuves": 2}}}}}
    assert any("relié à deux équipes" in e for e in cm.erreurs_correspondances(corr))


# --- les fichiers réellement publiés respectent le contrat ------------------------------------------------------------
def test_fichiers_publies_conformes():
    for chemin, fn in ((cm.FICHIER_ASSEMBLAGE, cm.erreurs_assemblage), (cm.FICHIER_CORRESPONDANCES, cm.erreurs_correspondances)):
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                assert fn(json.load(f)) == [], chemin
