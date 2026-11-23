"""Tests de verif_regle_buts.py (onglet « +1,5 buts » d'Analyse Verdict) : chaque règle avec >= 3 cas qui passent et >= 3 cas qui échouent."""
import gzip, json, os, pathlib, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest.mock as mk
import verif_regle_buts as R
import verif_pronostic as v

CFG_REGLE = {"regle": {"n_min": 4, "marques_min": 3.5, "encaisses_min": 2.8, "marche": "total_plus_1.5", "cote_min": 1.24}, "etude": {"matchs": 10, "taux": 0.8}}
CFG_CH = {**CFG_REGLE, "championnat": {"seuil": 0.8, "base": 0.8, "poids": 10}}          # filtre de championnat : seuil 80 %, taux lissé vers 80 % avec un poids de 10 matchs

# ---------------------------------------------------------------- la règle : marqués >= 3,5 ET encaissés >= 2,8 ET 4 matchs au même lieu
@pytest.mark.parametrize("S, E, nd, ne", [(3.5, 2.8, 4, 4), (4.2, 3.1, 6, 9), (3.51, 2.81, 4, 5), (5.0, 2.8, 4, 4), (3.5, 4.0, 10, 10)])
def test_regle_remplie(S, E, nd, ne):                                    # inclut les valeurs EXACTES de Patrick (3,5 et 2,8 : « au moins »)
    assert R.remplie(S, E, nd, ne)

@pytest.mark.parametrize("S, E, nd, ne", [(3.49, 2.9, 5, 5),              # marqués juste sous 3,5
                                          (3.8, 2.79, 5, 5),              # encaissés juste sous 2,8
                                          (4.5, 3.5, 3, 8),               # domicile : 3 matchs seulement
                                          (4.5, 3.5, 8, 3),               # extérieur : 3 matchs seulement
                                          (None, 3.0, 5, 5), (4.0, None, 5, 5), (3.0, 2.0, 5, 5)])
def test_regle_non_remplie(S, E, nd, ne):
    assert not R.remplie(S, E, nd, ne)

def test_evaluer_somme_des_deux_equipes():
    A = {"n": 6, "buts_marques": 2.0, "buts_encaisses": 1.5}; B = {"n": 5, "buts_marques": 1.5, "buts_encaisses": 1.3}
    assert R.evaluer(A, B) == {"marques": 3.5, "encaisses": 2.8, "n_dom": 6, "n_ext": 5}

@pytest.mark.parametrize("A, B", [({"n": 6, "buts_marques": 2.0, "buts_encaisses": 1.5}, {"n": 5, "buts_marques": 1.4, "buts_encaisses": 1.3}),     # 3,4 marqués
                                  ({"n": 3, "buts_marques": 3.0, "buts_encaisses": 3.0}, {"n": 5, "buts_marques": 3.0, "buts_encaisses": 3.0}),   # 3 matchs
                                  ({"n": 6, "buts_marques": None, "buts_encaisses": 1.5}, {"n": 5, "buts_marques": 3.0, "buts_encaisses": 3.0}),
                                  (None, {"n": 5, "buts_marques": 3.0, "buts_encaisses": 3.0})])
def test_evaluer_non_remplie(A, B):
    assert R.evaluer(A, B) is None

# ---------------------------------------------------------------- étude sur matchs joués : sommes AVANT le match, 4 matchs au même lieu
def _m(jour, dom, ext, gd, ge, saison="2627"):
    return {"saison": saison, "division": "T", "date": jour, "domicile": dom, "exterieur": ext, "buts_dom": gd, "buts_ext": ge}

def _historique(n, final=(2, 2)):    # A gagne 3-1 chez lui n fois ; B perd 1-3 dehors n fois ; puis A - B
    L = [_m(f"2026-09-{i + 1:02d}", "A", f"X{i}", 3, 1) for i in range(n)] + [_m(f"2026-09-{i + 1:02d}", f"Y{i}", "B", 3, 1) for i in range(n)]
    return L + [_m("2026-10-30", "A", "B", *final)]

def test_cas_joues_sommes():
    c = [x for x in R.cas_joues(_historique(4)) if x["date"] == "2026-10-30"]
    assert len(c) == 1 and c[0]["marques"] == 4.0 and c[0]["encaisses"] == 4.0 and c[0]["total"] == 4          # A marque 3 et B marque 1 : 4,0 ; A encaisse 1 et B 3 : 4,0

@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_cas_joues_moins_de_4_matchs_au_meme_lieu(n):
    assert [x for x in R.cas_joues(_historique(n)) if x["date"] == "2026-10-30"] == []

def test_cas_joues_ne_regarde_pas_l_avenir():
    a, b = R.cas_joues(_historique(5, (0, 0)))[-1], R.cas_joues(_historique(5, (5, 5)))[-1]
    assert (a["marques"], a["encaisses"]) == (b["marques"], b["encaisses"]) and a["total"] != b["total"]

def test_calculer(tmp_path):
    f = str(tmp_path / "bloc.json.gz"); json.dump({"liste": _historique(5, (0, 3))}, gzip.open(f, "wt", encoding="utf-8"))
    r = R.calculer(f)
    assert r["etude"]["matchs"] == 1 and r["etude"]["reussis"] == 1 and r["etude"]["taux"] == 1.0                   # règle remplie (4,0 / 4,0) et 3 buts : +1,5 réussi
    assert r["regle"]["marques_min"] == 3.5 and r["regle"]["encaisses_min"] == 2.8 and r["regle"]["cote_min"] == 1.24

def test_table_du_depot_coherente():
    r = R.charger(); assert r is not None
    E = r["etude"]
    assert r["regle"]["cote_min"] == 1.24 and 0 < E["taux"] <= 1 and E["matchs"] >= E["reussis"] > 0
    assert E["borne_basse"] <= E["taux"] <= E["borne_haute"] and abs(E["cote_equilibre"] - E["matchs"] / E["reussis"]) < 1e-3

# ---------------------------------------------------------------- de bout en bout : la fiche d'un match
def _x(A, B, cotes, jour="2026-11-21", mid="t1"):
    L = lambda S, dom: [{"domicile": dom, "date": f"2026-10-{i + 1:02d}", "saison": "2627", "buts_marques": h, "buts_encaisses": a} for i, (h, a) in enumerate(S)]
    return {"match_id": mid, "date": jour, "coup_d_envoi_utc": f"{jour}T15:00:00Z", "domicile": "A", "exterieur": "B", "competition": "Championnat inconnu", "cotes_betpawa": cotes,
            "assemblage": {"saison_football_data": "2627", "equipe_dom": {"matchs": L(A, True)}, "equipe_ext": {"matchs": L(B, False)}}}
def OU(plus): return {"over_under_1.5": {"plus": plus, "moins": 3.9}}
OUI_A, OUI_B = [(2, 1)] * 6, [(2, 2)] * 6            # 4,0 marqués et 3,0 encaissés : règle remplie

def _fiche(A, B, cotes, regle=CFG_REGLE, totaux=None):
    with mk.patch.object(R, "charger", return_value=regle): return v.fiche_match(_x(A, B, cotes), "2026-11-21T06:00:00Z", {"cote_min": 1.26}, totaux)

@pytest.mark.parametrize("cote", [1.26, 1.30, 1.55])
def test_fiche_regle_remplie_avec_cote_suffisante(cote):                  # 1,26 = le minimum de la page, plus de seuil propre à l'onglet
    f = _fiche(OUI_A, OUI_B, OU(cote)); p = f["regle_buts"]["pari"]
    assert f["regle_buts"]["marques"] == 4.0 and f["regle_buts"]["encaisses"] == 3.0 and p["marche"] == "total_plus_1.5" and p["cote"] == cote
    assert p["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE", "NE TIENT PAS")           # le verdict de la page ne filtre pas : seule la règle décide

@pytest.mark.parametrize("cotes", [OU(1.23), OU(1.10), {}, {"over_under_2.5": {"plus": 1.8, "moins": 1.9}}])
def test_fiche_sans_cote_valable_pas_d_onglet(cotes):                      # sous 1,24, sans cote, ou seulement un autre marché
    f = _fiche(OUI_A, OUI_B, cotes); assert "regle_buts" not in f and "plus15" not in f

@pytest.mark.parametrize("A, B", [([(2, 1)] * 6, [(1, 2)] * 6),           # 3,0 marqués seulement
                                  ([(2, 0)] * 6, [(2, 2)] * 6),           # 2,0 encaissés seulement
                                  ([(2, 1)] * 3, [(2, 2)] * 6),           # 3 matchs au même lieu
                                  ([(0, 0)] * 6, [(0, 0)] * 6)])
def test_fiche_regle_non_remplie_pas_d_onglet(A, B):
    assert "regle_buts" not in _fiche(A, B, OU(1.30))

def test_fiche_sans_etude_pas_d_onglet():
    assert "regle_buts" not in _fiche(OUI_A, OUI_B, OU(1.30), regle=None)

def test_plus_1_5_entre_dans_l_onglet_des_1_24_mais_pas_dans_les_autres():     # 1,25 : onglet +1,5 buts (seuil 1,24) mais pas les marchés de buts (1,26) ; 1,23 : nulle part
    f = _fiche(OUI_A, OUI_B, OU(1.25)); assert all(p["marche"] != "total_plus_1.5" for p in f["paris"]["buts"]) and f["plus15"]["pari"]["cote"] == 1.25
    f = _fiche(OUI_A, OUI_B, OU(1.23)); assert all(p["marche"] != "total_plus_1.5" for p in f["paris"]["buts"]) and "plus15" not in f and "regle_buts" not in f

# ---------------------------------------------------------------- la page garde le match, et le gel des sélections
def _flux(tmp_path, matchs):
    dossier = tmp_path / "flux"; dossier.mkdir()
    with gzip.open(str(dossier / "2026-11-21.json.gz"), "wt", encoding="utf-8") as f: json.dump({x["match_id"]: x for x in matchs}, f)
    return str(dossier)

def _page(tmp_path, matchs):
    with mk.patch.object(R, "charger", return_value=CFG_REGLE): return v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, matchs), cfg={"cote_min": 1.26, "sans_regles": True})

def test_page_garde_le_match_de_la_regle_meme_sans_autre_marche(tmp_path):
    d = _page(tmp_path, [_x(OUI_A, OUI_B, OU(1.30))]); assert [m["match_id"] for m in d["matchs"]] == ["t1"] and d["regle_buts"]["regle"]["cote_min"] == 1.24

def test_page_ecarte_le_match_sous_la_cote_minimale(tmp_path):
    assert _page(tmp_path, [_x([(0, 0)] * 6, [(0, 0)] * 6, {"over_under_1.5": {"plus": 1.23}})])["matchs"] == []      # seul le +1,5 est coté, sous 1,24 : rien ne retient le match

def test_selection_regle_buts_gelee_avant_le_match(tmp_path):
    j = str(tmp_path / "sel.jsonl")
    m1 = {"match_id": "m1", "date": "2026-11-20", "coup_d_envoi_utc": "2026-11-20T18:00:00Z", "statut": "a_venir", "domicile": "A", "exterieur": "B", "paris": {}, "regle_buts": {"pari": {"marche": "total_plus_1.5", "cote": 1.3, "taux": 0.8, "verdict": "TIENT"}}}
    m2 = {**m1, "match_id": "m2", "regle_buts": None}
    d = {"genere_le": "2026-11-20T10:00:00Z", "matchs": [m1, m2]}
    v.geler_selections(d, chemin=j)
    assert [r["match_id"] for r in v.lire_journal(j) if r["selection"] == "regle_buts"] == ["m1"] and v.verifier_journal(j) == []
    assert v.geler_selections(d, maintenant="2026-11-20T18:30:00Z", chemin=j) == 0                                       # après le coup d'envoi : plus de gel

# ---------------------------------------------------------------- la page web
def test_page_web_onglet_et_libelle_exact():
    js = (pathlib.Path(v.RACINE) / "archetype_verif.js").read_text(encoding="utf-8")
    assert '["plus15", "+1,5 buts"]' in js and "m.plus15 ? [m.plus15.pari]" in js and '"Onglet +1,5 buts"' in js
    assert 'concat(pariTotalEtude(m))' in js and '["total", "Total +1,5"]' in js and 'm === "total_plus_1.5" ? "total"' in js   # le +1,5 du match apparaît aussi dans l'onglet Étude (même pari, mêmes chiffres)
    assert '"Ne tient pas"' in js                                             # un « NE TIENT PAS » ne doit jamais s'afficher « Tient avec réserve »


# ---------------------------------------------------------------- filtre du championnat (22/11/2026)
def _tot(k, n, comp="Championnat inconnu", jour="2026-10-01"):          # n matchs précédents du championnat dont k à 2 buts ou plus
    return {comp: [(jour, 3 if i < k else 0) for i in range(n)]}

@pytest.mark.parametrize("k, n", [(32, 40), (40, 40), (100, 100), (35, 40)])        # (32, 40) = EXACTEMENT 80 % : « au moins » le seuil
def test_championnat_assez_riche_en_buts_garde_le_match(k, n):
    f = _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, _tot(k, n)); assert f["regle_buts"]["n_championnat"] == n and f["regle_buts"]["taux_championnat"] >= 0.8

@pytest.mark.parametrize("k, n", [(31, 40), (20, 40), (0, 40), (0, 0)])             # juste sous le seuil, nettement sous, aucun but, aucun match connu
def test_championnat_trop_pauvre_en_buts_ecarte_le_match(k, n):
    assert "regle_buts" not in _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, _tot(k, n))

def test_championnat_sans_donnee_pas_de_pari():
    assert "regle_buts" not in _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, {}) and "regle_buts" not in _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, _tot(40, 40, comp="Autre championnat"))

def test_championnat_ne_regarde_pas_l_avenir():           # des matchs du jour et d'après, sans but, ne changent rien
    t = _tot(40, 40); t["Championnat inconnu"] += [("2026-11-21", 0)] * 100 + [("2026-12-01", 0)] * 100
    assert _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, t)["regle_buts"]["n_championnat"] == 40

def test_sans_seuil_de_championnat_la_regle_seule_decide():
    f = _fiche(OUI_A, OUI_B, OU(1.30), CFG_REGLE, {}); assert f["regle_buts"] and "taux_championnat" not in f["regle_buts"]

def test_championnat_ne_change_pas_les_autres_marches():   # le filtre n'ajoute ni ne retire un marché des autres onglets
    a = _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, _tot(40, 40)); b = _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, _tot(0, 40))
    assert a["paris"] == b["paris"] and a.get("etude_paris") == b.get("etude_paris") and "regle_buts" not in b

def test_championnat_avant_compte_les_matchs_precedents_seulement():
    x = {"competition": "L", "date": "2026-11-21"}; T = {"L": [("2026-11-01", 3), ("2026-11-20", 1), ("2026-11-21", 5), ("2026-11-22", 0)], "M": [("2026-11-01", 9)]}
    assert v.championnat_avant(x, T) == (1, 2) and v.championnat_avant(x, {}) == (0, 0) and v.championnat_avant({"competition": "Z", "date": "2026-11-21"}, T) == (0, 0)

@pytest.mark.parametrize("k, n, base, attendu", [(0, 0, 0.8, 0.8), (40, 40, 0.8, 0.96), (0, 10, 0.8, 0.4), (30, 40, 0.75, 0.75), (100, 100, 0.8, 108 / 110)])
def test_taux_champ(k, n, base, attendu):
    assert R.taux_champ(k, n, base, 10) == pytest.approx(attendu)

def test_cas_joues_championnat_ne_compte_que_les_jours_precedents():
    L = [{**m, "competition": "L"} for m in _historique(4)]; L.insert(-1, {**_m("2026-10-30", "P", "Q", 5, 5), "competition": "L"})   # même jour, autre match : ne compte pas
    c = [x for x in R.cas_joues(L) if x["date"] == "2026-10-30"]
    assert len(c) == 1 and c[0]["n_champ"] == 8 and c[0]["k_champ"] == 8 and c[0]["comp"] == "L"

def test_calculer_choisit_le_seuil_sur_la_premiere_moitie(tmp_path):
    L = []
    for i in range(6):
        L += [_m(f"2026-09-{j + 1:02d}", f"A{i}", f"X{i}_{j}", 3, 1) for j in range(5)] + [_m(f"2026-09-{j + 1:02d}", f"Y{i}_{j}", f"B{i}", 3, 1) for j in range(5)] + [_m(f"2026-10-{i + 1:02d}", f"A{i}", f"B{i}", 2, 2)]
    L = [{**m, "competition": "L"} for m in L]; f = str(tmp_path / "bloc.json.gz"); json.dump({"liste": L}, gzip.open(f, "wt", encoding="utf-8"))
    with mk.patch.object(R, "N_SEUIL", 2): r = R.calculer(f)
    assert r["championnat"]["seuil"] in R.GRILLE and r["championnat"]["poids"] == R.POIDS and r["etude"]["verification"]["coupure"] >= "2026-09-01"
    assert r["etude"]["regle_seule"]["matchs"] >= r["etude"]["matchs"] > 0

def test_calculer_sans_assez_de_matchs_pas_de_seuil(tmp_path):
    f = str(tmp_path / "bloc.json.gz"); json.dump({"liste": _historique(5, (0, 3))}, gzip.open(f, "wt", encoding="utf-8")); r = R.calculer(f)
    assert "championnat" not in r and r["etude"]["matchs"] == 1                   # moins de 100 matchs de la règle : aucun seuil retenu, la règle seule décide

def test_depot_seuil_de_championnat_coherent():
    r = R.charger(); C = r.get("championnat"); assert C is not None
    V = r["etude"]["verification"]
    assert C["seuil"] in R.GRILLE and V["choix_du_seuil"]["matchs"] >= R.N_SEUIL and V["seconde_moitie_non_vue"]["matchs"] > 0
    assert r["etude"]["matchs"] == V["choix_du_seuil"]["matchs"] + V["seconde_moitie_non_vue"]["matchs"]


# ---------------------------------------------------------------- onglet « +1,5 buts » (22/11) : TOUT +1,5 coté 1,26 ou plus, évaluable ; la règle n'est qu'un repère
@pytest.mark.parametrize("A, B", [([(2, 1)] * 6, [(1, 2)] * 6),           # 3,0 marqués : règle non remplie
                                  ([(2, 0)] * 6, [(2, 2)] * 6),           # 2,0 encaissés : règle non remplie
                                  ([(1, 1)] * 6, [(2, 2)] * 6),           # 3,0 marqués
                                  ([(0, 0)] * 6, [(0, 0)] * 6)])          # verdict « NE TIENT PAS » : il reste dans l'onglet, avec son verdict
def test_onglet_ecarte_les_matchs_hors_regle(A, B):                         # l'onglet = seulement les matchs qui remplissent la règle (22/11/2026)
    f = _fiche(A, B, OU(1.30)); assert "plus15" not in f and "regle_buts" not in f

@pytest.mark.parametrize("A, B", [([(2, 1)] * 3, [(2, 2)] * 6), ([(2, 1)] * 6, [(2, 2)] * 3), ([], [(2, 2)] * 6), ([(2, 1)] * 6, [])])
def test_onglet_ecarte_un_match_non_evaluable(A, B):                       # moins de 4 matchs au même lieu : rejeté, comme partout
    assert "plus15" not in _fiche(A, B, OU(1.30))

def test_onglet_match_de_la_regle_porte_le_repere():
    f = _fiche(OUI_A, OUI_B, OU(1.30)); P = f["plus15"]
    assert P["regle_remplie"] is True and P["pari"]["regle"] is True and f["regle_buts"]["pari"] == P["pari"] and P["marques"] == 4.0 and P["encaisses"] == 3.0

def test_onglet_donne_le_taux_du_championnat():
    f = _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, _tot(40, 40))
    assert f["plus15"]["regle_remplie"] is True and f["plus15"]["n_championnat"] == 40 and f["plus15"]["taux_championnat"] > 0.9

def test_championnat_pauvre_retire_le_match_de_l_onglet():
    f = _fiche(OUI_A, OUI_B, OU(1.30), CFG_CH, _tot(0, 40)); assert "plus15" not in f and "regle_buts" not in f

def test_selection_plus15_gelee_avant_le_match(tmp_path):
    j = str(tmp_path / "sel.jsonl"); pari = {"marche": "total_plus_1.5", "cote": 1.3, "taux": 0.8, "verdict": "TIENT"}
    m1 = {"match_id": "m1", "date": "2026-11-20", "coup_d_envoi_utc": "2026-11-20T18:00:00Z", "statut": "a_venir", "domicile": "A", "exterieur": "B", "paris": {}, "plus15": {"pari": pari, "regle_remplie": False}}
    m2 = {**m1, "match_id": "m2", "plus15": None}
    d = {"genere_le": "2026-11-20T10:00:00Z", "matchs": [m1, m2]}
    v.geler_selections(d, chemin=j)
    assert [r["match_id"] for r in v.lire_journal(j) if r["selection"] == "plus15"] == ["m1"] and not [r for r in v.lire_journal(j) if r["selection"] == "regle_buts"] and v.verifier_journal(j) == []
