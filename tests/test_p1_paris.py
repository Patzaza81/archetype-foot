import p1_paris as pp_

P = {"dom": .5, "nul": .3, "ext": .2, "o15": .8, "o25": .55, "o35": .3, "btts": .5}
BP = {"1x2": {"1": 2.4, "N": 3.0, "2": 6.0}, "double_chance": {"1N": 1.3, "N2": 2.4, "12": 1.4}, "over_under_2.5": {"plus": 1.7, "moins": 2.2}, "btts": {"Oui": 1.9, "Non": 1.8}}

def test_proba_exactes_par_somme_et_complement():
    assert abs(pp_.proba(P, "1N") - .8) < 1e-12 and abs(pp_.proba(P, "N2") - .5) < 1e-12 and abs(pp_.proba(P, "12") - .7) < 1e-12 and abs(pp_.proba(P, "-o25") - .45) < 1e-12 and abs(pp_.proba(P, "-btts") - .5) < 1e-12

def test_retenu_plus_forte_proba_parmi_valeur_positive():
    c = pp_.cotes_utiles(BP); r = pp_.choisir(P, c, "A", "B")
    v = {m["cle"]: round(m["valeur"], 4) for m in r["marches"]}
    assert v["1"] == .2 and v["1N"] == .04 and v["12"] == -.02 and v["o25+"] == -.065 and v["btts+"] == -.05 and v["N2"] == .2
    assert r["retenu"]["cle"] == "1N" and r["retenu"]["libelle"] == "A ou match nul"      # valeurs > 0 : 1 (50 %), 1N (80 %), N2 (50 %), 2(+20 %)

def test_aucun_marche_si_aucune_valeur_positive():
    r = pp_.choisir(P, {"1": 1.5, "N": 2.0, "2": 3.0}); assert r["retenu"] is None and r["cotes_disponibles"] == 3

def test_sans_cote_rien_n_est_invente():
    assert pp_.cotes_utiles({}) == {} and pp_.cotes_utiles(None) == {} and pp_.choisir(P, {})["marches"] == [] and pp_.choisir(P, {})["retenu"] is None
    assert pp_.cotes_utiles({"1x2": {"1": None, "N": "x", "2": 1.0}}) == {} and pp_.cotes_utiles({"btts": {"Oui": True}}) == {}

def test_reglement_des_marches():
    for cle, d, e, att in (("1", 2, 1, True), ("1", 1, 1, False), ("N", 0, 0, True), ("2", 0, 1, True), ("1N", 1, 1, True), ("1N", 0, 1, False), ("12", 1, 1, False),
                            ("o25+", 2, 1, True), ("o25+", 1, 1, False), ("o25-", 1, 1, True), ("o15+", 1, 0, False), ("o35+", 2, 2, True), ("btts+", 1, 1, True), ("btts+", 3, 0, False), ("btts-", 3, 0, True)):
        assert pp_.gagne(cle, d, e) is att, (cle, d, e)
