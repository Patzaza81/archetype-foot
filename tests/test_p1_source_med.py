"""P1 sur l'Eerste Divisie : source Matchendirect (assemblage) a la place de Football-Data."""
import calibrer_p1_med as cm, calibration_p1 as cp, integration_calibration as ic, p1_source_med as pm, pouvoir_predictif as pp

COMP = "pays-bas : eerste divisie"
def cle(slug, comp=COMP): return f"https://www.matchendirect.fr/equipe/{slug}_abcdefghij.html||{comp}"
def m(date, adv, dom, bm, be): return {"date": date, "adversaire": adv, "domicile": dom, "buts_marques": bm, "buts_encaisses": be}
def doc(extra=()):
    A = [m("2026-08-07", "Beta", True, 2, 1), m("2026-08-14", "Gamma", False, 0, 0), *extra]
    B = [m("2026-08-07", "Alpha", False, 1, 2), m("2026-08-21", "Gamma", True, 1, 3)]
    C = [m("2026-08-14", "Alpha", True, 0, 0), m("2026-08-21", "Beta", False, 3, 1)]
    return {"equipes": [{"competition": COMP, "cle_cache": cle(s), "nom_matchendirect": n, "matchs": ms} for s, n, ms in (("alpha", "Alpha", A), ("beta", "Beta", B), ("gamma", "Gamma", C))]}
S = "2627"

# doivent réussir
def test_historique_un_match_une_fois_trie_avec_buts_et_saison():
    h = [x for x in pm.historique("N2", doc(), S) if x[1] == S]; assert len(h) == 3 and [x[0] for x in h] == sorted(x[0] for x in h)
    assert h[0][1:] == (S, "Alpha", "Beta", 2, 1) and h[1][2:] == ("Gamma", "Alpha", 0, 0) and h[2][2:] == ("Beta", "Gamma", 1, 3)

def test_division_et_noms_pour_deux_equipes_du_championnat():
    assert pm.division_et_noms("Pays-Bas : Eerste Divisie", cle("alpha"), cle("beta"), doc()) == ("N2", "Alpha", "Beta")

def test_calibrage_parametres_dans_la_grille_et_aucune_correction():
    h = [(i, S, "ABCD"[i % 4], "ABCD"[(i + 1 + i // 4) % 4], (i * 7) % 4, (i * 5) % 3) for i in range(1, 49)]
    r = cm.calibrer("N2", h); assert r["p1"]["k"] in pp.K_GRILLE and r["p1"]["demi_vie_jours"] in pp.HL_GRILLE and r["calibrage"]["matchs_historique"] == 48
    assert all(r[mk]["statut"] == "P1 CONSERVE" and r[mk]["methode"] == "P1" for mk in cp.MARCHES) and cm.calibrer("N2", h) == r

# doivent échouer (rejetés)
def test_autre_championnat_non_servi_par_matchendirect():
    assert pm.historique("E0", doc(), S) == [] and pm.saisons_passees("E0") == {} and pm.division_et_noms("Angleterre : League Two", cle("alpha"), cle("beta"), doc()) is None

def test_equipe_inconnue_ou_meme_equipe_des_deux_cotes_rejetee():
    assert pm.division_et_noms("Pays-Bas : Eerste Divisie", cle("alpha"), cle("inconnue"), doc()) is None
    assert pm.division_et_noms("Pays-Bas : Eerste Divisie", cle("alpha"), cle("alpha"), doc()) is None and pm.division_et_noms("Pays-Bas : Eerste Divisie", None, None, doc()) is None

def test_match_sans_score_exclu_et_filtre_jusqua_jour():
    h = [x for x in pm.historique("N2", doc([m("2026-09-01", "Beta", True, None, None)]), S) if x[1] == S]; assert len(h) == 3
    assert [x for x in ic.historique("N2", jusqua_jour=h[1][0]) if x[0] >= h[1][0]] == []

def test_donnees_reelles_n2_exploitables_par_p1():
    h = ic.historique("N2"); assert len(h) >= 50 and "N2" in cp.charger()["competitions"] and all(isinstance(x[4], int) and isinstance(x[5], int) for x in h)

# saisons passées complètes (data/eerste_divisie) — doivent réussir
import collections
def test_au_moins_quatre_saisons_passees_completes_de_380_matchs_et_20_equipes():
    s = pm.saisons_passees("N2"); assert len(s) >= 4 and all(len(v) == 380 for v in s.values())
    assert all(len({x[1] for x in v} | {x[2] for x in v}) == 20 for v in s.values())

def test_chaque_equipe_joue_19_domicile_et_19_exterieur_sans_doublon():
    for v in pm.saisons_passees("N2").values():
        assert len({(x[1], x[2]) for x in v}) == 380
        assert set(collections.Counter(x[1] for x in v).values()) == {19} and set(collections.Counter(x[2] for x in v).values()) == {19}

def test_equipes_actuelles_portent_les_noms_matchendirect_dans_l_historique_passe():
    actuels = {x[2] for x in pm.historique("N2") if x[1] == pm.saison_courante()} | {x[3] for x in pm.historique("N2") if x[1] == pm.saison_courante()}
    passe = {x[1] for v in pm.saisons_passees("N2").values() for x in v} | {x[2] for v in pm.saisons_passees("N2").values() for x in v}
    assert len(actuels & passe) >= 18

def test_calibrage_note_seulement_les_saisons_passees_hors_premiere_et_bat_la_frequence_de_base():
    import numpy as np
    r = cm.calibrer("N2"); passees = sorted(pm.saisons_passees("N2"))
    assert r["calibrage"]["saisons_notees"] == passees[1:] and pm.saison_courante() not in r["calibrage"]["saisons_notees"]
    h = [x for x in pm.historique("N2") if x[1] in passees[1:]]; Y = pp.issues(h)[:, :3]; f = Y.mean(0)
    assert r["calibrage"]["perte_logarithmique_1x2"] < float(-np.log(f[Y.argmax(1)]).mean())

# doivent échouer (rejetés)
def test_saison_incomplete_ecartee():
    pm.saisons_passees("N2"); sauve = pm._cache["passees"]
    try:
        pm._cache["passees"] = {**sauve, "2526": sauve["2526"][:379]}; assert "2526" not in pm.saisons_passees("N2") and "2425" in pm.saisons_passees("N2")
        pm._cache["passees"] = {k: v[:100] for k, v in sauve.items()}; assert pm.saisons_passees("N2") == {}
    finally: pm._cache["passees"] = sauve

def test_saison_en_cours_jamais_dupliquee_depuis_les_saisons_passees():
    for s in ("2425", "2526"): assert len([x for x in pm.historique("N2", doc(), s) if x[1] == s]) == 3
