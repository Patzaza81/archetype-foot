import indice_corners_cartons as ic


def test_indice_plus_4_sur_4():
    assert ic.indice([11, 12, 13], [10, 11, 12], 8.5, True) == 4


def test_indice_plus_pire_scenario_casse():
    # pire domicile 6 : (6+11)/2 = 8,5 -> pas > 8,5 ; (6+6)/2 = 6 non plus ; moyens valident
    assert ic.indice([6, 14, 14], [11, 11, 11], 8.5, True) == 2     # (pire dom 6 + 11)/2 = 8,5 : non validé


def test_indice_moins_utilise_le_plus_grand_total():
    assert ic.indice([6, 7, 8], [6, 7, 8], 10.5, False) == 4
    assert ic.indice([6, 7, 15], [6, 7, 8], 10.5, False) == 2       # pire dom 15 : (15+7)/2 = 11 > 10,5


def test_egalite_exacte_non_validee():
    assert ic.indice([9, 9, 9], [9, 9, 9], 9.0, True) == 0


def test_echantillon_trop_petit():
    assert ic.indice([9, 9], [9, 9, 9], 8.5, True) is None
    assert ic.indice([9, 9, 9], [], 8.5, True) is None
    assert ic.indice([], [], 8.5, False) is None


def test_historique_lieu_et_derniers():
    ms = [{"competition_code": "E0", "date": f"2026-09-{d:02d}", "home_team": "A", "away_team": "B", "c": (d, 1)} for d in range(1, 9)]
    h = ic.historique(ms, lambda m: m["c"])
    assert ("E0", "A", "dom") in h and ("E0", "B", "ext") in h and ("E0", "A", "ext") not in h
    assert ic._derniers(h, ("E0", "A", "dom")) == [d + 1 for d in range(4, 9)]      # 5 derniers


def test_choix_prend_meilleur_indice_puis_proba():
    prev = {"corners": {"total": {"8.5": 0.78, "9.5": 0.7, "10.5": 0.2, "7.5": 0.95}}}
    hist = {"corners": {("E0", "A", "dom"): [("1", 11), ("2", 12), ("3", 13)], ("E0", "B", "ext"): [("1", 10), ("2", 11), ("3", 12)]}}
    ind, ch = ic.indices_et_choix(prev, hist, "E0", "A", "B")
    assert ch["corners"]["ligne"] == "8.5" and ch["corners"]["cote"] == "plus" and ch["corners"]["indice"] == 4
    assert ind["corners"]["10.5"]["moins"] <= 2


def test_pas_de_donnee_pas_de_choix():
    ind, ch = ic.indices_et_choix({"corners": {"total": {"8.5": 0.9}}}, {"corners": {}}, "E0", "A", "B")
    assert ind == {} and ch == {}


def test_choix_ecarte_les_probas_trop_hautes():
    prev = {"corners": {"total": {"7.5": 0.95, "8.5": 0.78}}}
    hist = {"corners": {("E0", "A", "dom"): [("1", 11), ("2", 12), ("3", 13)], ("E0", "B", "ext"): [("1", 10), ("2", 11), ("3", 12)]}}
    _, ch = ic.indices_et_choix(prev, hist, "E0", "A", "B")
    assert ch["corners"]["ligne"] == "8.5" and ch["corners"]["proba"] == 0.78
