"""Tests du moteur Europe-Gamma (03/11/2026) : poids 20/30/50, échantillons sans fuite, équivalence avec l'énumération exhaustive de Gamma, enjeu, cotes, appariements."""
import itertools
import json
import math
from collections import defaultdict

import pytest

from moteur_europe_gamma import coeur as C, donnees as D, enjeu as E, marches as M


def obs(date, adv, m, e, w=1.0, dom=True, saison="2026/2027"):
    return {"date": date, "adversaire": adv, "domicile": dom, "buts_marques": m, "buts_encaisses": e, "saison": saison, "competition": "ldc"}


def sq(att_a, def_a, att_b, def_b, wa=None, wb=None):
    wa, wb = wa or [1.0] * len(att_a), wb or [1.0] * len(att_b)
    return {"att_a": list(zip(att_a, wa)), "def_a": list(zip(def_a, wa)), "att_b": list(zip(att_b, wb)), "def_b": list(zip(def_b, wb))}


def test_poids_de_base_20_30_50_et_renormalisation():
    assert C.BASE == {"prec": 0.20, "champ": 0.30, "eu": 0.50}
    assert C.pi_effectifs(["prec", "champ", "eu"]) == pytest.approx({"prec": 0.2, "champ": 0.3, "eu": 0.5})
    assert C.pi_effectifs(["champ", "eu"]) == pytest.approx({"champ": 0.375, "eu": 0.625})
    assert C.pi_effectifs(["prec", "champ"]) == pytest.approx({"prec": 0.4, "champ": 0.6})
    assert C.pi_effectifs(["eu"]) == {"eu": 1.0}


@pytest.mark.parametrize("t", [None, 0, 1, 2])
def test_histogramme_equivaut_a_l_enumeration_exhaustive(t):
    s = sq([2, 0, 1, 3, 1], [1, 1, 0, 2, 3], [1, 1, 2, 0, 0], [0, 2, 1, 1, 4], wa=[1, .5, 2, 1, .7], wb=[1, 1.5, .3, 1, 2])
    # énumération explicite avec poids par séquence (attaque et défense portent chacune leur poids)
    exp = defaultdict(float)
    for (a, w1), (da, w2), (b, w3), (db, w4) in itertools.product(s["att_a"], s["def_a"], s["att_b"], s["def_b"]):
        e = max(abs(a - db), abs(b - da))
        if t is None or e <= t:
            exp[(a, b)] += w1 * w2 * w3 * w4
    h = C.histogramme(s, t)
    assert set(h) == {k for k, v in exp.items() if v > 0}
    for k in h:
        assert h[k] == pytest.approx(exp[k])


def test_paliers_emboites_et_brut_complet():
    s = sq([2, 0, 1], [1, 1, 0], [1, 1, 2], [0, 2, 1])
    n = {t: sum(C.histogramme(s, t).values()) for t in (None, 0, 1, 2)}
    assert n[0] <= n[1] <= n[2] <= n[None] == pytest.approx(3 * 3 * 3 * 3)


def test_aucune_fuite_et_trois_echantillons():
    m = {"date": "2026-10-20", "competition_code": "ldc", "domicile": "A", "exterieur": "B", "meta_dom": {}, "meta_ext": {},
         "entree": {"europe_dom": [obs("2026-10-20", "X", 9, 9), obs("2026-10-21", "X", 9, 9)] + [obs(f"2026-09-0{i}", f"E{i}", 1, 0) for i in range(1, 5)]
                    + [obs(f"2026-08-0{i}", f"S{i}", 2, 2, saison="2025/2026") for i in range(1, 8)],
                    "europe_ext": [obs(f"2026-09-1{i}", f"F{i}", 0, 1, dom=False) for i in range(1, 4)],
                    "ligue_dom": [obs(f"2026-09-2{i}", f"L{i}", 1, 1) for i in range(1, 4)], "ligue_ext": [obs(f"2026-09-2{i}", f"M{i}", 1, 2, dom=False) for i in range(1, 4)],
                    "odds": {}, "handicap_lines": []}}
    r = D.echantillons(m, {})["sources"]
    assert [o["marques"] for o in r["eu"]["A"]] == [1, 1, 1, 1]            # les matchs du jour et du lendemain (9-9) sont exclus
    assert r["prec"]["A"] == [] or len(r["prec"]["A"]) <= 5
    assert r["eu"]["valide"] and r["champ"]["valide"]
    assert not r["prec"]["valide"]                                          # l'extérieur n'a aucun match de la saison passée


def test_saison_precedente_limitee_a_5_derniers():
    m = {"date": "2026-10-20", "competition_code": "ldc", "domicile": "A", "exterieur": "B", "meta_dom": {}, "meta_ext": {},
         "entree": {"europe_dom": [obs(f"2026-04-0{i}", f"S{i}", i, 0, saison="2025/2026") for i in range(1, 8)],
                    "europe_ext": [obs(f"2026-04-0{i}", f"T{i}", 0, i, dom=False, saison="2025/2026") for i in range(1, 8)], "ligue_dom": [], "ligue_ext": [], "odds": {}, "handicap_lines": []}}
    r = D.echantillons(m, {})["sources"]["prec"]
    assert [o["marques"] for o in r["A"]] == [3, 4, 5, 6, 7] and len(r["B"]) == 5


@pytest.mark.parametrize("jour,att", [("2026-10-20", ("2026/2027", "2025/2026")), ("2026-07-01", ("2026/2027", "2025/2026")), ("2026-06-30", ("2025/2026", "2024/2025")), ("2026-01-15", ("2025/2026", "2024/2025"))])
def test_saisons(jour, att):
    assert D.saisons(jour) == att


CL = {"angleterre : premier league": {"resultat": [{"equipe": "Arsenal", "pts": 9, "j": 3}]}, "allemagne : bundesliga": {"resultat": [{"equipe": "Bayern", "pts": 9, "j": 3}]},
      "autriche : bundesliga": {"resultat": [{"equipe": "LASK", "pts": 3, "j": 3}]}, "europe : ligue des champions phase de ligue": {"resultat": []}}


@pytest.mark.parametrize("titre,eq,cle", [("Premier League", "Arsenal", "angleterre : premier league"), ("Bundesliga", "Bayern", "allemagne : bundesliga"), ("Bundesliga", "LASK", "autriche : bundesliga")])
def test_cle_championnat_passe(titre, eq, cle):
    assert D.cle_championnat(CL, titre, eq) == cle


@pytest.mark.parametrize("titre,eq", [("Bundesliga", None), ("Bundesliga", "Inconnu"), ("Ligue Inexistante", "Arsenal")])
def test_cle_championnat_ne_devine_jamais(titre, eq):
    assert D.cle_championnat(CL, titre, eq) is None


def test_force_adversaire():
    f = D.table_force([{"equipe": "Fort", "pts": 9, "j": 3}, {"equipe": "Faible", "pts": 0, "j": 3}, {"equipe": "Moyen", "pts": 3, "j": 3}])
    assert f["fort"] == pytest.approx(2.25) and f["faible"] == 0 and f["moyen"] == pytest.approx(0.75)
    assert D.poids_adversaire({"adversaire": "Fort"}, f) == (pytest.approx(2.25), True)
    assert D.poids_adversaire({"adversaire": "Inconnu"}, f) == (1.0, False)
    assert D.table_force([]) == {}


@pytest.mark.parametrize("k,v,cle", [("1x2_X", 3.7, ("1x2", "N")), ("dc_X2", 1.33, ("double_chance", "N2")), ("under_2_5", 2.2, ("over_under_2.5", "moins")),
                                    ("home_over_1_5", 2.4, ("over_under_domicile_1.5", "plus")), ("handicap_-1.5_2", 1.9, ("handicap_1.5", "exterieur")),
                                    ("handicap_3.5_1", 3.83, ("handicap_-3.5", "domicile")), ("handicap_3.5_2", 1.22, ("handicap_-3.5", "exterieur")),
                                    ("handicap_0.5_1", 1.21, ("handicap_-0.5", "domicile")),
                                    ("handicap_-1_X", 3.9, ("handicap_3issues_1", "X")), ("handicap_1_1", 1.58, ("handicap_3issues_-1", "1"))])
def test_cotes_gamma_passe(k, v, cle):
    assert D.cotes_gamma({k: v}).get(cle[0], {}).get(cle[1]) == v


@pytest.mark.parametrize("k,v", [("exact_goals_2", 5.0), ("score_1_0", 7.0), ("total_pair", 1.9), ("over_2_5", 0.9), ("btts_yes", True), ("handicap_9.5_1", 2.0)])
def test_cotes_gamma_ignore_ce_qui_n_a_pas_d_equivalent(k, v):
    assert D.cotes_gamma({k: v}) == {}


def src_valide(a, b):
    return {"A": a, "B": b, "valide": True}


def _obs(vals, w=1.0):
    return [{"date": f"2026-0{i+1}-01", "adversaire": f"X{i}", "marques": m, "encaisses": e, "poids": w} for i, (m, e) in enumerate(vals)]


def test_analyse_complete_controles_et_robustesse():
    src = {"prec": src_valide(_obs([(2, 1), (0, 0), (1, 2)]), _obs([(1, 1), (0, 2), (2, 2), (1, 0)])), "champ": src_valide(_obs([(3, 0), (1, 1), (2, 2), (0, 1)]), _obs([(0, 1), (1, 3), (1, 1)])),
           "eu": {"A": [], "B": [], "valide": False}}
    a = C.analyser(src, {"1x2": {"1": 1.8, "N": 3.5, "2": 4.0}})
    assert all(v["ok"] for v in a["verifications"])
    assert set(a["echantillons"]) == {"prec", "champ"} and a["absents"] == ["eu"]
    assert a["echantillons"]["champ"]["poids_effectif"] == pytest.approx(0.6)
    for m in a["marches"]:
        assert m["g"] <= m["f"] + 1e-9                                      # la fréquence robuste est un minimum
    assert [m for m in a["marches"] if m["statut"] == "apercu"].__len__() <= 1
    assert C.analyser(src, None)["empreinte"] == C.analyser(src, None)["empreinte"]


def test_refus_si_donnees_insuffisantes():
    un = {"prec": src_valide(_obs([(1, 1)] * 3), _obs([(1, 1)] * 3)), "champ": {"A": [], "B": [], "valide": False}, "eu": {"A": [], "B": [], "valide": False}}
    with pytest.raises(C.DonneesInsuffisantes):
        C.analyser(un)
    court = {"prec": src_valide(_obs([(1, 1)] * 2), _obs([(1, 1)] * 3)), "champ": src_valide(_obs([(1, 1)] * 3), _obs([(1, 1)] * 3)), "eu": src_valide(_obs([(1, 1)] * 3), _obs([(1, 1)] * 3))}
    with pytest.raises(C.DonneesInsuffisantes):
        C.analyser(court)


def test_poids_de_force_deplacent_la_frequence():
    base = {"champ": src_valide(_obs([(0, 0), (0, 0), (3, 0)]), _obs([(0, 0)] * 3)), "eu": src_valide(_obs([(0, 0)] * 3), _obs([(0, 0)] * 3))}
    f0 = next(m for m in C.analyser(base)["marches"] if m["cle"] == ["over_under_0.5", "plus"])["f"]
    lourd = {"champ": src_valide([dict(o, poids=(5.0 if o["marques"] == 3 else 1.0)) for o in _obs([(0, 0), (0, 0), (3, 0)])], _obs([(0, 0)] * 3)), "eu": base["eu"]}
    f1 = next(m for m in C.analyser(lourd)["marches"] if m["cle"] == ["over_under_0.5", "plus"])["f"]
    assert f1 > f0


# --- enjeu ------------------------------------------------------------------------------------------------------------
def table(pts, j=7):
    return [{"equipe": f"E{i}", "pts": p, "j": j} for i, p in enumerate(pts)]


def test_enjeu_ouvert_en_debut_de_phase():
    cl = [{"equipe": f"E{i}", "pts": (9 if i < 5 else 3), "j": 3} for i in range(36)]
    assert E.enjeu(cl, "E0")["reel"] and E.enjeu(cl, "E20")["reel"]


def test_enjeu_acquis_et_perdu_mathematiquement():
    pts = [21] * 2 + [10] * 22 + [0] * 12                                     # 7 matchs joués, 1 restant (+3 max)
    cl = table(pts)
    top = E.enjeu(cl, "E0")
    assert top["frontieres"]["8"] == "acquise"
    bas = E.enjeu(cl, "E35")
    assert bas["frontieres"]["24"] == "perdue" and bas["frontieres"]["8"] == "perdue" and not bas["reel"]


def test_enjeu_non_calcule_hors_phase_ou_equipe_inconnue():
    assert E.enjeu(None, "E0") is None
    assert E.enjeu(table([1, 2, 3], j=9), "E0") is None
    assert E.enjeu(table([1, 2, 3]), "Inconnu") is None


def test_enjeu_en_points_jamais_en_rangs():
    cl = [{"equipe": f"E{i}", "pts": 9 - (i // 4), "j": 3} for i in range(36)]      # beaucoup d'égalités : le rang ne départage rien
    x = E.enjeu(cl, "E0")
    assert "rang_provisoire" not in x and x["ecart_ligne"]["8"] == 9 - cl[7]["pts"]
    assert E.enjeu(cl, "E35")["ecart_ligne"]["24"] == cl[35]["pts"] - cl[23]["pts"]


@pytest.mark.parametrize("a,b,attendu", [("E0", "E1", 2), ("E1", "E0", -2), ("E2", "E2", 0)])
def test_ecart_de_points_entre_les_deux_equipes(a, b, attendu):
    cl = [{"equipe": "E0", "pts": 9, "j": 3}, {"equipe": "E1", "pts": 7, "j": 3}, {"equipe": "E2", "pts": 4, "j": 3}]
    assert E.ecart_points(cl, a, b) == attendu


@pytest.mark.parametrize("a,b", [("E0", "Inconnu"), ("Inconnu", "E1"), ("X", "Y")])
def test_ecart_de_points_absent_si_equipe_inconnue(a, b):
    assert E.ecart_points([{"equipe": "E0", "pts": 9, "j": 3}, {"equipe": "E1", "pts": 7, "j": 3}], a, b) is None


def test_saison_en_cours_sans_minimum_saison_passee_a_3():
    m = {"date": "2026-10-20", "competition_code": "ldc", "domicile": "A", "exterieur": "B", "meta_dom": {}, "meta_ext": {},
         "entree": {"europe_dom": [obs("2026-09-01", "E1", 2, 0)] + [obs(f"2026-04-0{i}", f"S{i}", 1, 1, saison="2025/2026") for i in range(1, 3)],
                    "europe_ext": [obs("2026-09-02", "F1", 0, 1, dom=False)] + [obs(f"2026-04-0{i}", f"T{i}", 1, 1, dom=False, saison="2025/2026") for i in range(1, 3)],
                    "ligue_dom": [obs("2026-09-03", "L1", 1, 0)], "ligue_ext": [obs("2026-09-04", "M1", 0, 0, dom=False)], "odds": {}, "handicap_lines": []}}
    r = D.echantillons(m, {})["sources"]
    assert r["eu"]["valide"] and r["champ"]["valide"]          # un seul match suffit pour la saison en cours
    assert not r["prec"]["valide"]                              # la saison passée garde son minimum de 3


def test_analyse_avec_un_seul_match_par_equipe_en_saison_en_cours():
    src = {"champ": src_valide(_obs([(2, 1)]), _obs([(0, 1)])), "eu": src_valide(_obs([(1, 1)]), _obs([(1, 2)])), "prec": {"A": [], "B": [], "valide": False}}
    a = C.analyser(src)
    assert a["echantillons"]["eu"]["poids_effectif"] == pytest.approx(0.625) and all(v["ok"] for v in a["verifications"])


def test_enjeu_nul_est_affiche_sans_exclure_le_match(monkeypatch):
    from moteur_europe_gamma import suivi as S
    nul = {"pts": 21, "j": 7, "restants": 1, "ecart_ligne": {"8": 5, "24": 11}, "frontieres": {"8": "acquise", "24": "acquise"}, "reel": False}
    monkeypatch.setattr(S, "_enjeu", lambda m, c: {"domicile": nul, "exterieur": dict(nul, reel=True), "ecart_points": 3})
    m = {"match_id": "x", "date": "2026-10-20", "domicile": "A", "exterieur": "B", "competition": "Europe : Ligue des Champions Phase de Ligue", "competition_code": "ldc",
         "meta_dom": {}, "meta_ext": {}, "coup_d_envoi_utc": "2026-10-20T19:00:00Z",
         "entree": {"europe_dom": [obs("2026-09-01", "E1", 2, 0)], "europe_ext": [obs("2026-09-02", "F1", 0, 1, dom=False)],
                    "ligue_dom": [obs("2026-09-03", "L1", 1, 0)], "ligue_ext": [obs("2026-09-04", "M1", 0, 0, dom=False)], "odds": {"1x2_1": 1.5}, "handicap_lines": []}}
    f = S.analyser_match(m, {}, None)
    assert f["statut"] == "analyse" and any("enjeu NUL" in l for l in f["conclusion"])


def test_echantillon_a_poids_nuls_est_retire_sans_plantage():
    nul = _obs([(1, 0)], w=0.0)
    src = {"champ": src_valide(_obs([(2, 1)]), _obs([(0, 1)])), "eu": src_valide(_obs([(1, 1)]), _obs([(1, 2)])), "prec": src_valide(nul * 3, nul * 3)}
    a = C.analyser(src)
    assert set(a["echantillons"]) == {"champ", "eu"} and "prec" in a["absents"] and all(v["ok"] for v in a["verifications"])
    seul = {"champ": src_valide(nul, nul), "eu": src_valide(_obs([(1, 1)]), _obs([(1, 2)])), "prec": {"A": [], "B": [], "valide": False}}
    with pytest.raises(C.DonneesInsuffisantes):
        C.analyser(seul)


@pytest.mark.parametrize("k,faux", [("handicap_3.5_1", ("handicap_3.5", "domicile")),        # Barcelone -3,5 ne doit JAMAIS devenir « Barcelone +3,5 »
                                    ("handicap_3.5_2", ("handicap_3.5", "exterieur")),
                                    ("handicap_1.5_1", ("handicap_1.5", "domicile")),
                                    ("handicap_1_1", ("handicap_3issues_1", "1"))])
def test_handicap_signe_jamais_inverse(k, faux):
    assert D.cotes_gamma({k: 2.5}).get(faux[0], {}).get(faux[1]) is None
