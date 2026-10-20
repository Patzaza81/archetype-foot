"""Tests du moteur alpha « séries » : pour chaque règle, au moins 3 cas qui passent et 3 qui échouent."""
import copy

import pytest

from alpha_serie import coeur, parametres as P

PARAMS = P.defaut()


def equipe(rows):
    """rows = [(date, domicile, marqués, encaissés)]"""
    return {"matchs": [{"date": d, "domicile": dom, "buts_marques": m, "buts_encaisses": e, "provisoire": False} for d, dom, m, e in rows]}


def serie_dom(marq, enc, debut=1):
    return equipe([(f"2026-09-{debut + i:02d}", True, m, e) for i, (m, e) in enumerate(zip(marq, enc))])


# Northampton - Tranmere (20/10/2026) : exemple de référence de Patrick
NORTHAMPTON = serie_dom([0, 1, 1, 0], [0, 1, 0, 1])
TRANMERE = equipe([(f"2026-09-{1 + i:02d}", False, m, e) for i, (m, e) in enumerate(zip([1, 2, 0, 0, 2], [1, 2, 2, 0, 4]))])


def test_coefficient_k_par_plus_petit_echantillon():
    assert [P.coef_k(n) for n in (4, 5, 6, 7)] == [0.8, 0.9, 1.0, 1.0]
    for n in (0, 2, 3):
        assert P.coef_k(n) is None


def test_serie_meme_lieu_avant_le_jour_sans_fuite():
    eq = equipe([("2026-09-01", True, 1, 0), ("2026-09-05", False, 3, 3), ("2026-09-10", True, 2, 2), ("2026-09-20", True, 9, 9)])
    assert coeur.serie_lieu(eq, True, "2026-09-20") == ([1, 2], [0, 2])         # le match du jour lui-même est exclu
    assert coeur.serie_lieu(eq, False, "2026-09-20") == ([3], [3])               # lieu extérieur
    assert coeur.serie_lieu(eq, True, "2026-09-01") == ([], [])                  # rien avant la date
    eq["matchs"][0]["provisoire"] = True
    assert coeur.serie_lieu(eq, True, "2026-09-20") == ([2], [2])                # match provisoire ignoré
    long = serie_dom(list(range(10)), [0] * 10)
    assert len(coeur.serie_lieu(long, True, "2026-10-01")[0]) == 7               # fenêtre de 7


def test_exemple_northampton_scenarios_apparies():
    hm, hc = coeur.serie_lieu(NORTHAMPTON, True, "2026-10-20")
    am, ac = coeur.serie_lieu(TRANMERE, False, "2026-10-20")
    off, de = coeur.scenarios(hm, hc, am, ac)
    assert off == [(0, 2), (1, 0), (1, 0), (0, 2)]
    assert de == [(2, 0), (2, 1), (0, 0), (4, 1)]
    niv = coeur.niveaux(hm, hc, am, ac)
    assert niv["dom"] == pytest.approx(1.15) and niv["ext"] == pytest.approx(0.75) and niv["total"] == pytest.approx(1.9)


def test_marge_de_niveau_buts_entiers():
    niv = lambda t: {"dom": t / 2, "ext": t / 2, "total": t, "d": 0.0}
    plus15 = lambda t: coeur.norme_niveau("over_under_1.5", "plus", niv(t), PARAMS)[0]
    assert plus15(3.5) and plus15(4.0) and plus15(3.5001)                        # 1,5 + marge 2
    assert not plus15(1.9) and not plus15(3.0) and not plus15(3.49)              # 1,9 ne garantit pas 2 buts
    moins35 = lambda t: coeur.norme_niveau("over_under_3.5", "moins", niv(t), PARAMS)[0]
    assert moins35(2.0) and moins35(1.0) and moins35(0.0)
    assert not moins35(2.5) and not moins35(3.0) and not moins35(2.01)


def test_resultats_victoire_nul_double_chance():
    def n(d):
        return coeur.norme_niveau
    f = lambda g, s, d: coeur.norme_niveau(g, s, {"dom": 1 + d / 2, "ext": 1 - d / 2, "total": 2.0, "d": d}, PARAMS)[0]
    assert f("1x2", "1", 0.5) and f("1x2", "2", -0.5) and f("double_chance", "1N", 1.0) and f("double_chance", "N2", -0.5) and f("double_chance", "12", 0.0)
    assert not f("1x2", "1", 0.4) and not f("1x2", "2", -0.4) and not f("double_chance", "1N", 0.9) and not f("double_chance", "N2", -0.4)
    assert not f("1x2", "N", 0.0)                                                # aucun seuil appris pour le nul : rejeté, avec la raison
    avec_nul = copy.deepcopy(PARAMS)
    avec_nul["seuils_resultat"]["nul"] = 0.25
    assert coeur.norme_niveau("1x2", "N", {"dom": 1, "ext": 1, "total": 2, "d": 0.2}, avec_nul)[0]
    assert not coeur.norme_niveau("1x2", "N", {"dom": 1, "ext": 1, "total": 2, "d": 0.3}, avec_nul)[0]


def test_analyse_northampton_registre_et_onglets():
    r = coeur.analyser_match(NORTHAMPTON, TRANMERE, "2026-10-20", PARAMS)
    assert r["statut"] == "analyse" and r["k"] == 0.8
    buts = {f["marche"]: f for f in r["onglets"]["buts"]}
    assert "Multigoals 1-3" in buts and buts["Multigoals 1-3"]["offensive"] == 1.0 and buts["Multigoals 1-3"]["defensive"] == 0.5
    assert buts["Multigoals 1-3"]["valeur"] == pytest.approx(0.6)                # (100 % + 50 %) / 2 × 0,8
    assert "Moins de 2,5 buts" not in buts and "Plus de 1,5 buts" not in buts    # norme de niveau non respectée (1,9 buts attendus)
    rejetes = {f["marche"]: f["raison"] for f in r["rejetes"]}
    assert "norme de niveau" in rejetes["Moins de 2,5 buts"]
    assert "branche défensive sous" in rejetes["Extérieur ne perd pas (N2)"]                # Tranmere ne perd pas : 25 % défensif
    assert "norme de niveau" in rejetes["Victoire domicile"] and "norme de niveau" in rejetes["Domicile ne perd pas (1N)"]   # écart attendu +0,40
    ms = {f["marche"]: f for f in r["onglets"]["multiscores"]}
    assert set(ms) == {"1:0 / 2:0 / 3:0"} and ms["1:0 / 2:0 / 3:0"]["scenarios"] == 3 and ms["1:0 / 2:0 / 3:0"]["valeur"] == pytest.approx(3 / 8 * 0.8)
    eq = {f["marche"]: f for f in r["onglets"]["equipes"]}
    assert eq["Pas de nul (12)"]["offensive"] == 1.0 and eq["Pas de nul (12)"]["defensive"] == 0.75
    assert eq["Pas de nul (12)"]["valeur"] == pytest.approx(0.7)                  # (100 % + 75 %) / 2 × 0,8


def test_aucune_cote_dans_l_analyse_et_cote_a_l_etape_2():
    r = coeur.analyser_match(NORTHAMPTON, TRANMERE, "2026-10-20", PARAMS)
    cotes = {"over_under_domicile_1.5": {"moins": 1.49}, "double_chance": {"12": 1.32}}
    e2 = coeur.choisir(r, cotes)
    # le résultat de l'étape 1 est identique quelles que soient les cotes (la fonction n'en reçoit pas)
    assert r == coeur.analyser_match(NORTHAMPTON, TRANMERE, "2026-10-20", PARAMS)
    noms2 = {f["marche"]: f for lst in e2["onglets"].values() for f in lst}
    if "Pas de nul (12)" in noms2:
        assert noms2["Pas de nul (12)"]["cote"] == 1.32
    bas = coeur.choisir(r, {"double_chance": {"12": 1.24}})
    assert all(f["marche"] != "Pas de nul (12)" for f in bas["onglets"]["equipes"])           # cote 1,24 < 1,25 : écarté
    assert any(f["marche"] == "Pas de nul (12)" for f in bas["ecartes_par_la_cote"]) or "Pas de nul (12)" not in {f["marche"] for f in r["onglets"]["equipes"]}
    ok = coeur.choisir(r, {"double_chance": {"12": 1.25}})
    assert all(f["marche"] != "Pas de nul (12)" for f in ok["ecartes_par_la_cote"])           # 1,25 est accepté, aucun maximum
    ms = coeur.choisir(r, {"multiscores": {}})["onglets"]["multiscores"]
    assert ms and ms[0]["cote"] is None and ms[0]["cote_a_lire"]                              # multiscore : pas d'exclusion par la cote


def test_echantillon_insuffisant_exclut_le_match():
    court = serie_dom([1, 2, 0], [0, 1, 1])
    for dom, ext in ((court, TRANMERE), (NORTHAMPTON, equipe([("2026-09-01", False, 1, 1)])), (equipe([]), equipe([]))):
        r = coeur.analyser_match(dom, ext, "2026-10-20", PARAMS)
        assert r["statut"] == "exclu" and all(not v for v in r["onglets"].values())
    assert coeur.analyser_match(NORTHAMPTON, TRANMERE, "2026-10-20", PARAMS)["statut"] == "analyse"
    assert coeur.analyser_match(NORTHAMPTON, TRANMERE, "2026-09-02", PARAMS)["statut"] == "exclu"       # avant le début des séries


def test_pas_deux_evenements_identiques():
    # domicile marque toujours 3 et encaisse 0 ; extérieur marque 0 et encaisse 3 : « Victoire dom », « Handicap -0,5 dom » = même événement
    dom = serie_dom([3, 3, 3, 3], [0, 0, 0, 0])
    ext = equipe([(f"2026-09-{1 + i:02d}", False, 0, 3) for i in range(4)])
    r = coeur.analyser_match(dom, ext, "2026-10-20", PARAMS)
    noms = [f["marche"] for lst in r["onglets"].values() for f in lst]
    assert not ({"Victoire domicile", "Handicap -0,5 domicile"} <= set(noms))
    assert any("doublon" in f.get("raison", "") for f in r["rejetes"])


def test_graduation_alerte_seulement_exact_et_sans_ressemblance():
    cl = [{"equipe": "Alpha", "pts": 30, "j": 10, "diff": 12}, {"equipe": "Beta", "pts": 10, "j": 10, "diff": -8}]
    g = coeur.graduation(cl, "Alpha", "Beta")
    assert g["dom"]["pts_match"] == 3.0 and g["ext"]["diff_match"] == -0.8
    assert coeur.alerte_graduation(("1x2", "2"), g) and "domicile" in coeur.alerte_graduation(("1x2", "2"), g)
    assert coeur.alerte_graduation(("1x2", "1"), g) is None and coeur.alerte_graduation(("over_under_2.5", "plus"), g) is None
    assert coeur.graduation(cl, "Alpha FC", "Beta") is None and coeur.graduation(None, "Alpha", "Beta") is None
