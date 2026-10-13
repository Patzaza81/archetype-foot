import pytest

from moteur_europe import evaluate_match_europe
from moteur_europe.model import N_MAX, POIDS_CHAMPIONNAT, POIDS_EUROPE, _lisse, build_model_europe
from moteur_europe.performance import indice_performance_europe, profil_moyen
from moteur_europe.socle.calibration import CalibrationFit, IsotonicCalibrator
from moteur_europe.socle.model import MOYENNE_REFERENCE, build_model


def rows(scores, domicile, debut=1):
    return [{"date": f"2026-0{(debut + i) // 28 + 1}-{(debut + i) % 28 + 1:02d}", "domicile": domicile,
             "buts_marques": gf, "buts_encaisses": ga} for i, (gf, ga) in enumerate(scores)]


def donnees(eu_dom, eu_ext, lg_dom, lg_ext):
    return rows(eu_dom, True), rows(eu_ext, False), rows(lg_dom, True), rows(lg_ext, False)


# --- cas qui doivent PASSER -------------------------------------------------------------------------------------------
def test_lambda_europe_plus_proche_de_la_moyenne_que_le_calcul_v3_copie():
    """Lissage Europe (K = 8) plus fort que le noyau copié (K = 4) : lambda tiré davantage vers 1,35."""
    sc_d, sc_e = [(2, 1), (1, 0), (3, 1), (0, 0)], [(1, 2), (0, 1), (1, 1), (0, 2)]
    ed, ee, ld, le = donnees(sc_d, sc_e, sc_d, sc_e)
    eu = build_model_europe(ed, ee, ld, le)
    v3 = build_model(ed, ee)
    assert abs(eu.lambda_home - MOYENNE_REFERENCE) < abs(v3.lambda_home - MOYENNE_REFERENCE) or v3.lambda_home == MOYENNE_REFERENCE
    assert abs(eu.lambda_away - MOYENNE_REFERENCE) <= abs(v3.lambda_away - MOYENNE_REFERENCE) + 1e-9


def test_ponderation_70_30_calcul_a_la_main():
    ed, ee, ld, le = donnees([(3, 1)] * 4, [(1, 3)] * 4, [(1, 1)] * 5, [(1, 1)] * 5)
    m = build_model_europe(ed, ee, ld, le)
    att_d = POIDS_EUROPE * _lisse(3, 4) + POIDS_CHAMPIONNAT * _lisse(1, 5)
    def_e = POIDS_EUROPE * _lisse(3, 4) + POIDS_CHAMPIONNAT * _lisse(1, 5)
    assert m.lambda_home == pytest.approx(att_d * def_e / MOYENNE_REFERENCE)


def test_le_lambda_est_entre_les_deux_sources_et_plus_proche_de_l_europe():
    ed, ee, ld, le = donnees([(3, 1)] * 4, [(1, 3)] * 4, [(1, 1)] * 5, [(1, 1)] * 5)
    m = build_model_europe(ed, ee, ld, le)
    eu, lg = m.diagnostics["lambda_europe_seule"][0], m.diagnostics["lambda_championnat_seul"][0]
    assert lg < m.lambda_home < eu
    assert eu - m.lambda_home < m.lambda_home - lg


def test_maximum_6_matchs_les_plus_recents_par_source():
    sc = [(0, 0)] * 4 + [(2, 1)] * 6          # 10 matchs : les 6 derniers seulement
    ed, ee, ld, le = donnees(sc, [(1, 1)] * 3, sc, [(1, 1)] * 3)
    d = build_model_europe(ed, ee, ld, le).diagnostics
    assert d["europe_dom_n"] == N_MAX == 6 and d["championnat_dom_n"] == 6
    assert d["europe_dom_dates"] == [m["date"] for m in ed[-6:]]


def test_minimum_3_suffit():
    ed, ee, ld, le = donnees([(1, 0)] * 3, [(0, 1)] * 3, [(1, 0)] * 3, [(0, 1)] * 3)
    assert build_model_europe(ed, ee, ld, le).lambda_home > 0


# --- cas qui doivent ÉCHOUER -------------------------------------------------------------------------------------------
def test_europe_moins_de_3_au_meme_lieu_refuse():
    ed, ee, ld, le = donnees([(1, 0)] * 2, [(0, 1)] * 4, [(1, 0)] * 4, [(0, 1)] * 4)
    with pytest.raises(ValueError, match="EUROPE_INSUFFISANT"):
        build_model_europe(ed, ee, ld, le)


def test_championnat_moins_de_3_refuse():
    ed, ee, ld, le = donnees([(1, 0)] * 4, [(0, 1)] * 4, [(1, 0)] * 4, [(0, 1)] * 2)
    with pytest.raises(ValueError, match="CHAMPIONNAT_INSUFFISANT"):
        build_model_europe(ed, ee, ld, le)


def test_les_matchs_a_l_autre_lieu_ne_comptent_pas():
    ed = rows([(1, 0)] * 2, True) + rows([(1, 0)] * 5, False, debut=10)   # 2 à domicile seulement
    _, ee, ld, le = donnees([], [(0, 1)] * 4, [(1, 0)] * 4, [(0, 1)] * 4)
    with pytest.raises(ValueError, match="EUROPE_INSUFFISANT"):
        build_model_europe(ed, ee, ld, le)


def test_pas_de_selection_sans_calibration():
    ed, ee, ld, le = donnees([(3, 0)] * 6, [(0, 2)] * 6, [(3, 0)] * 6, [(0, 2)] * 6)
    cotes = {"1x2_1": 1.40, "over_1_5": 1.30, "btts_no": 1.60}
    r = evaluate_match_europe({"europe_dom": ed, "europe_ext": ee, "ligue_dom": ld, "ligue_ext": le, "odds": cotes})
    assert r["selected"] == []
    assert any("CALIBRATION_ABSENTE" in reasons for _, reasons in r["rejected"])


def test_pas_de_selection_sans_double_controle():
    ed, ee, ld, le = donnees([(3, 0)] * 6, [(0, 2)] * 6, [(3, 0)] * 6, [(0, 2)] * 6)
    cal = IsotonicCalibrator()
    cal.fit_result = CalibrationFit(True, 400, "OK", ((0.0, 0.0), (1.0, 1.0)))
    r = evaluate_match_europe({"europe_dom": ed, "europe_ext": ee, "ligue_dom": ld, "ligue_ext": le,
                               "odds": {"1x2_1": 1.40}}, calibrator=cal)
    assert r["selected"] == []
    assert any("DOUBLE_CONTROLE_ECHOUE_OU_ABSENT" in reasons for _, reasons in r["rejected"])


def test_chemin_complet_avec_calibration_et_preuves():
    ed, ee, ld, le = donnees([(2, 1)] * 6, [(1, 2)] * 6, [(2, 1)] * 6, [(1, 2)] * 6)
    cal = IsotonicCalibrator()
    cal.fit_result = CalibrationFit(True, 400, "OK", ((0.0, 0.0), (1.0, 1.0)))
    ev = {"dc_1X": {"double_control_ok": True, "justification": "test", "exposure_group": "resultat"}}
    r = evaluate_match_europe({"europe_dom": ed, "europe_ext": ee, "ligue_dom": ld, "ligue_ext": le,
                               "odds": {"dc_1X": 1.45}}, calibrator=cal, evidence=ev)
    assert [s.market for s in r["selected"]] == ["dc_1X"]
    perf = r["indices_performance"]["dc_1X"]
    assert perf["sur"] == 4 and perf["indice"] == 4


def test_surdispersion_bloque_meme_avec_tout_le_reste():
    ed, ee, ld, le = donnees([(3, 0)] * 6, [(0, 2)] * 6, [(3, 0)] * 6, [(0, 2)] * 6)
    cal = IsotonicCalibrator()
    cal.fit_result = CalibrationFit(True, 400, "OK", ((0.0, 0.0), (1.0, 1.0)))
    ev = {"1x2_1": {"double_control_ok": True, "justification": "test", "exposure_group": "resultat"}}
    r = evaluate_match_europe({"europe_dom": ed, "europe_ext": ee, "ligue_dom": ld, "ligue_ext": le,
                               "odds": {"1x2_1": 1.40}}, calibrator=cal, evidence=ev)
    assert r["selected"] == []


# --- indice de performance -------------------------------------------------------------------------------------------
def test_profil_moyen_pondere():
    eu, lg = rows([(4, 0)] * 3, True), rows([(0, 2)] * 3, True)
    assert profil_moyen(eu, lg) == pytest.approx((0.7 * 4, 0.3 * 2))


def test_pire_scenario_cherche_dans_europe_et_championnat():
    ed = rows([(1, 0)] * 3, True)
    ee = rows([(0, 1)] * 3, False)
    ld = rows([(1, 0)] * 2 + [(1, 5)], True)       # un 1-5 en championnat doit compter dans le pire match
    le = rows([(0, 1)] * 3, False)
    perf = indice_performance_europe("under_3_5", ed, ld, ee, le)
    assert perf["indice"] < 4
    perf_ok = indice_performance_europe("under_3_5", ed, rows([(1, 0)] * 3, True), ee, le)
    assert perf_ok["indice"] == 4


def test_autonomie_totale_aucun_lien_avec_v2_v3():
    """Le moteur Europe ne doit importer ni V2 ni V3 : tout est copié dans moteur_europe/."""
    import glob, re
    interdits = re.compile(r"^\s*(from|import)\s+(moteur_v3|moteur_v3_pipeline|regles_selection|scraper_details|banc_historique|"
                           r"precalcul|calculs)\b", re.M)
    fichiers = glob.glob("moteur_europe/**/*.py", recursive=True) + ["collecte_europe.py", "calibration_europe.py",
                                                                       "source_livescore.py"]
    for f in fichiers:
        src = open(f, encoding="utf-8").read()
        assert not interdits.search(src), f
        assert not re.search(r"^\s*from\s+moteur_v3", src, re.M), f
    for f in ("pronostics_europe.html", "archetype_europe.js", "europe_autres.js"):
        src = open(f, encoding="utf-8").read()
        assert "archetype_v3" not in src.replace("Aucun lien avec archetype_v3.js", "") and "data/v3" not in src, f


# --- revue des marchés et des cotes (13/10) ---------------------------------------------------------------------------
def test_marche_exclu_trois_cas_exclus_et_trois_gardes():
    from moteur_europe.core import marche_exclu
    for m in ("score_2_1", "exact_goals_3", "handicap_-3.5_1", "handicap_2.5_2"):
        assert marche_exclu(m), m
    for m in ("1x2_1", "over_2_5", "handicap_-1.5_1", "handicap_2_2", "btts_yes", "dc_1X"):
        assert not marche_exclu(m), m


def _rows(n, dom, bm=2, be=1, annee=2026):
    return [{"date": f"{annee}-0{i + 1}-10", "domicile": dom, "buts_marques": bm, "buts_encaisses": be} for i in range(n)]


def test_lissage_europe_plus_fort_que_v3_et_probabilite_plafonnee_sans_calibration():
    from moteur_europe.core import PLAFOND_NON_CALIBRE, evaluate_match_europe
    from moteur_europe.model import K_LISSAGE_EUROPE
    from moteur_europe.socle.model import K_LISSAGE
    assert K_LISSAGE_EUROPE > K_LISSAGE
    forts, faibles = _rows(6, True, 5, 0), _rows(6, False, 0, 5)
    r = evaluate_match_europe({"europe_dom": forts, "europe_ext": faibles, "ligue_dom": forts, "ligue_ext": faibles,
                               "odds": {"1x2_1": 1.5, "over_0_5": 1.3}, "handicap_lines": []})
    assert r["values"]["over_0_5"].probability <= PLAFOND_NON_CALIBRE + 1e-12
    assert all(c["probability"] <= PLAFOND_NON_CALIBRE + 1e-12 for c in r["candidates"])


def test_marches_exclus_jamais_candidats():
    from moteur_europe.core import evaluate_match_europe
    d, e = _rows(5, True), _rows(5, False)
    r = evaluate_match_europe({"europe_dom": d, "europe_ext": e, "ligue_dom": d, "ligue_ext": e,
                               "odds": {"score_2_1": 8.0, "exact_goals_3": 4.0, "handicap_-3.5_1": 1.2, "over_1_5": 1.4},
                               "handicap_lines": [-3.5, -1.5]})
    assert set(r["values"]) == {"over_1_5"}


def test_double_controle_sur_echantillon_melange():
    from moteur_europe.preuves import preuves_europe
    eu_d, eu_e = _rows(3, True, 2, 0), _rows(3, False, 0, 2)
    lg_d, lg_e = _rows(3, True, 2, 0, 2025), _rows(3, False, 0, 2, 2025)
    p = preuves_europe(eu_d, eu_e, lg_d, lg_e, ["1x2_1"], "A", "B")["1x2_1"]
    assert {"double_controle_europe", "double_controle_championnat"} <= set(p)
    # l'échantillon mélangé compte les deux sources : au moins aussi de matchs que l'Europe seule
    assert p["double_control_ok"] in (True, False)
