import datetime
import random

import pytest

import calibration_europe as ce
from moteur_v3.calibration import CalibrationFit, IsotonicCalibrator

COTES = {"1x2_1": 2.0, "1x2_X": 3.3, "1x2_2": 3.5, "dc_1X": 1.45, "dc_X2": 1.9, "over_1_5": 1.4, "over_2_5": 1.95,
         "under_3_5": 1.35, "btts_yes": 1.8, "btts_no": 1.9}


def hist(scores, dom, debut="2026-08-"):
    return [{"date": f"{debut}{i + 1:02d}", "domicile": dom, "buts_marques": gf, "buts_encaisses": ga,
             "adversaire": "X", "competition": "ldc", "saison": "2026/2027"} for i, (gf, ga) in enumerate(scores)]


def match(i, score=None, date="2026-09-20", cotes=None, nb=4):
    rnd = random.Random(i)
    sc = lambda: [(rnd.randint(0, 3), rnd.randint(0, 2)) for _ in range(nb)]
    e = {"europe_dom": hist(sc(), True), "europe_ext": hist(sc(), False), "ligue_dom": hist(sc(), True),
         "ligue_ext": hist(sc(), False), "odds": COTES if cotes is None else cotes, "handicap_lines": []}
    return {"match_id": f"m{i}", "date": date, "domicile": "A", "exterieur": "B", "competition_code": "ldc",
            "couverture": {}, "score": ({"buts_dom": score[0], "buts_ext": score[1]} if score else None), "entree": e}


def joues(n, date="2026-09-20"):
    rnd = random.Random(99)
    return [match(i, (rnd.randint(0, 3), rnd.randint(0, 2)), date) for i in range(n)]


# --- doivent PASSER ----------------------------------------------------------------------------------------------------
def test_calibration_prete_avec_assez_de_matchs():
    cal, nb = ce.entraine_calibration_europe(joues(80), "2026-10-13")
    assert cal.fit_result.ready and nb == 80 and cal.fit_result.observations >= 300


def test_calibration_utilise_la_meme_chaine_que_v3_pour_les_seuils():
    from moteur_v3_pipeline import MIN_MATCHS_CALIBRATION
    assert MIN_MATCHS_CALIBRATION == 50


def test_evaluation_a_venir_sans_calibration_donne_zero_selection_mais_un_apercu_structure():
    r = ce.evalue_match_europe(match(1), None)
    assert r["statut"] == "EVALUE" and r["selections"] == [] and r["calibree"] is False
    assert isinstance(r["apercu_non_calibre"], list) and len(r["candidats"]) > 0


def test_resultat_serialisable_json():
    import json
    json.dumps(ce.evalue_match_europe(match(2), None))


# --- doivent ÉCHOUER / être refusés ---------------------------------------------------------------------------------------
def test_moins_de_50_matchs_pas_de_calibration_meme_avec_300_observations():
    cal, nb = ce.entraine_calibration_europe(joues(40), "2026-10-13")
    assert nb == 40 and not cal.fit_result.ready


def test_match_du_jour_ou_futur_exclu_de_l_entrainement():
    cal, nb = ce.entraine_calibration_europe(joues(80, date="2026-10-13"), "2026-10-13")
    assert nb == 0 and not cal.fit_result.ready


def test_match_sans_score_exclu_de_l_entrainement():
    _, nb = ce.entraine_calibration_europe([match(i) for i in range(80)], "2026-10-13")
    assert nb == 0


def test_moins_de_3_matchs_non_evalue():
    r = ce.evalue_match_europe(match(3, nb=2), None)
    assert r["statut"].startswith("NON_EVALUE") and r["selections"] == []


def test_sans_cote():
    assert ce.evalue_match_europe(match(4, cotes={}), None)["statut"] == "SANS_COTE"


def test_calibrateur_non_pret_ne_selectionne_jamais():
    cal = IsotonicCalibrator()
    cal.fit_result = CalibrationFit(False, 10, "ECHANTILLON_INSUFFISANT", ())
    assert ce.evalue_match_europe(match(5), cal)["selections"] == []


def test_execution_de_bout_en_bout(tmp_path):
    import json
    ent = tmp_path / "e.json"
    ent.write_text(json.dumps({"matchs": joues(60) + [match(500, date="2026-10-15")]}))
    b = ce.execution(str(ent), str(tmp_path / "s.json"), aujourdhui=datetime.date(2026, 10, 13), site=str(tmp_path / "p.json"))
    assert b["matchs_a_venir"] == 1 and b["calibration"]["prete"] and b["calibration"]["matchs"] == 60


# --- pronostics visibles sans calibration (format de la page V3) -----------------------------------------------------------
def match_coherent(i=1, cotes=None):
    m = match(i, cotes=cotes or {"dc_1X": 1.45, "1x2_1": 1.5, "over_1_5": 1.3, "btts_yes": 1.6})
    e = m["entree"]
    e["europe_dom"], e["ligue_dom"] = hist([(2, 1)] * 6, True), hist([(2, 1)] * 6, True)
    e["europe_ext"], e["ligue_ext"] = hist([(1, 2)] * 6, False), hist([(1, 2)] * 6, False)
    m["heure"], m["competition"] = "21:00", "Europe : Ligue des Champions Phase de Ligue"
    return m


def test_apercu_non_calibre_produit_sans_attendre_la_calibration():
    r = ce.evalue_match_europe(match_coherent(), None)
    assert r["selections"] == [] and [a["marche"] for a in r["apercu_non_calibre"]] == ["dc_1X"]


def test_format_site_identique_a_v3(tmp_path):
    import json
    ent = tmp_path / "e.json"
    ent.write_text(json.dumps({"matchs": [match_coherent()]}))
    p = tmp_path / "p.json"
    ce.execution(str(ent), str(tmp_path / "s.json"), aujourdhui=datetime.date(2026, 10, 13), site=str(p))
    d = json.loads(p.read_text())
    sig = d["signaux"][0]
    assert sig["moteur_utilise"] == "moteur_v3" and sig["moteur_v3"]["apercu_non_calibre"] is True
    assert sig["moteur_v3"]["selection"]["P1"]["apercu_non_calibre"] is True
    assert d["calibration"]["prete"] is False and d["calibration"]["minimum_matchs"] == 50


def test_marche_hors_fenetre_de_cotes_jamais_propose():
    r = ce.evalue_match_europe(match_coherent(cotes={"1x2_1": 1.1, "dc_1X": 1.1}), None)
    assert r["apercu_non_calibre"] == []


def test_page_europe_lit_les_donnees_europe_et_pas_celles_de_v3():
    import pathlib
    h = (pathlib.Path(__file__).parent.parent / "pronostics_europe.html").read_text(encoding="utf-8")
    assert "data/europe/pronostics_europe.json" in h and h.index("window.fetch") < h.index('src="archetype_v3.js')
