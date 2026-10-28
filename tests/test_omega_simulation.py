"""Matchs simulés dans les deux sens (méthode de Patrick, 28/10/2026) : badge « Accord » et « Alerte » des fiches omega."""
import json
from pathlib import Path

from moteur_omega import simulation as SIM, suivi

# Exemple vérifié avec Patrick : Celtic Glasgow (domicile) – Dundee Utd. (extérieur), 28/10/2026
CELTIC = {"dom_marques": [1, 2, 3, 0, 7], "dom_encaisses": [0, 1, 0, 1, 1],
          "ext_marques": [0, 4, 0, 3, 1], "ext_encaisses": [4, 0, 3, 0, 1]}


def test_les_dix_scores_simules_de_l_exemple_celtic():
    assert SIM.scores_simules(CELTIC) == [(1, 4), (2, 0), (3, 3), (0, 0), (7, 1), (0, 0), (1, 4), (0, 0), (1, 3), (1, 1)]


def test_frequences_de_l_exemple_celtic():
    attendu = {("over_under_4.5", "moins"): 6, ("over_under_1.5", "plus"): 7, ("double_chance", "N2"): 8,
               ("handicap_-1.5", "exterieur"): 8, ("1x2", "1"): 2, ("1x2", "2"): 3, ("1x2", "N"): 5, ("btts", "Oui"): 6}
    for cle, ok in attendu.items():
        assert SIM.frequence(cle, CELTIC) == {"ok": ok, "n": 10}, cle


def test_alerte_trois_paris_sans_alerte_et_trois_avec():
    sans = [("over_under_1.5", "plus"), ("double_chance", "N2"), ("handicap_-1.5", "exterieur")]   # 7, 8, 8 sur 10
    avec = [("1x2", "1"), ("1x2", "2"), ("1x2", "N")]                                               # 2, 3, 5 sur 10
    for cle in sans:
        f = SIM.frequence(cle, CELTIC)
        assert f["ok"] / f["n"] >= SIM.SEUIL_ALERTE, cle
    for cle in avec:
        f = SIM.frequence(cle, CELTIC)
        assert f["ok"] / f["n"] < SIM.SEUIL_ALERTE, cle


def test_echantillons_de_taille_differente_apparies_sur_les_plus_recents():
    s = {"dom_marques": [9, 1, 2, 3, 4], "dom_encaisses": [9, 0, 0, 0, 0],
         "ext_marques": [1, 1, 1, 1], "ext_encaisses": [2, 2, 2, 2]}
    sc = SIM.scores_simules(s)
    assert len(sc) == 8 and (9, 2) not in sc and sc[:4] == [(1, 2), (2, 2), (3, 2), (4, 2)]


def test_marche_inconnu_ou_serie_vide_rien_n_est_invente():
    assert SIM.frequence(("marche_inconnu", "x"), CELTIC) is None
    assert SIM.scores_simules({"dom_marques": [], "dom_encaisses": [], "ext_marques": [1], "ext_encaisses": [1]}) == []


def _faux_poids(monkeypatch, valeurs):
    monkeypatch.setattr(SIM.SO, "probabilite", lambda poids, cle, s: valeurs.get(tuple(cle)))


def test_accord_quand_les_deux_premiers_choix_coincident(monkeypatch):
    cotes = {"double_chance": {"N2": 1.45}, "over_under_4.5": {"moins": 1.47}, "1x2": {"1": 1.25}}
    _faux_poids(monkeypatch, {("double_chance", "N2"): 0.70, ("over_under_4.5", "moins"): 0.65, ("1x2", "1"): 0.90})
    assert SIM.marche_accord(CELTIC, cotes, {"x": 1}) == ("double_chance", "N2")    # 1x2|1 écarté : cote sous 1,39


def test_pas_d_accord_quand_les_premiers_choix_divergent(monkeypatch):
    cotes = {"double_chance": {"N2": 1.45}, "over_under_4.5": {"moins": 1.47}}
    _faux_poids(monkeypatch, {("double_chance", "N2"): 0.60, ("over_under_4.5", "moins"): 0.80})
    assert SIM.marche_accord(CELTIC, cotes, {"x": 1}) is None                       # Solidité : -4,5 ; simulation : N2 (8 contre 6)
    assert SIM.marche_accord(CELTIC, None, {"x": 1}) is None and SIM.marche_accord(CELTIC, cotes, None) is None


def test_fiche_badge_accord_et_alerte_sans_toucher_au_pari(monkeypatch):
    _faux_poids(monkeypatch, {("double_chance", "N2"): 0.70, ("over_under_4.5", "moins"): 0.65})
    principal = {"cle": ["over_under_4.5", "moins"], "cote": 1.47}
    f = {"series": CELTIC, "principal": principal, "autres": [{"cle": ["double_chance", "N2"], "cote": 1.45}]}
    suivi._ajouter_simulation(f, {"x": 1}, {"cotes": {"double_chance": {"N2": 1.45}, "over_under_4.5": {"moins": 1.47}}})
    assert principal == {"cle": ["over_under_4.5", "moins"], "cote": 1.47}             # copie : le pari gelé n'est pas modifié
    assert f["principal"]["simules"] == {"ok": 6, "n": 10} and f["principal"]["alerte"] is False
    assert f["autres"][0]["accord"] is True and f["accord"]["affiche"] is True and f["accord"]["cle"] == ["double_chance", "N2"]


def test_accord_hors_des_paris_affiches_et_alerte(monkeypatch):
    _faux_poids(monkeypatch, {("double_chance", "N2"): 0.70, ("1x2", "N"): 0.30})
    f = {"series": CELTIC, "principal": {"cle": ["1x2", "N"], "cote": 3.4}, "autres": []}
    suivi._ajouter_simulation(f, {"x": 1}, {"cotes": {"double_chance": {"N2": 1.45}, "1x2": {"N": 3.4}}})
    assert f["principal"]["alerte"] is True and "accord" not in f["principal"]
    assert f["accord"]["affiche"] is False and f["accord"]["cote"] == 1.45 and f["accord"]["simules"] == {"ok": 8, "n": 10}


def test_sans_series_rien_n_est_ajoute():
    f = {"principal": {"cle": ["1x2", "1"], "cote": 1.5}, "autres": []}
    suivi._ajouter_simulation(f, {"x": 1}, None)
    assert "simules" not in f["principal"] and "accord" not in f


def test_affichage_prudent_dans_la_page():
    js = (Path(__file__).resolve().parent.parent / "archetype_omega.js").read_text(encoding="utf-8")
    assert "function omSimulation(" in js and "function omAccord(" in js and "omAccord(f)" in js
    assert "if (!a || a.affiche || !a.cle)" in js                                    # pas de doublon quand le pari est déjà affiché
    html = (Path(__file__).resolve().parent.parent / "pronostics_omega.html").read_text(encoding="utf-8")
    assert ".om-acc" in html and ".om-alerte" in html and "archetype_omega.js?v=20261028g" in html
