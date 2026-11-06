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
    h = pm.historique("N2", doc(), S); assert len(h) == 3 and [x[0] for x in h] == sorted(x[0] for x in h)
    assert h[0][1:] == (S, "Alpha", "Beta", 2, 1) and h[1][2:] == ("Gamma", "Alpha", 0, 0) and h[2][2:] == ("Beta", "Gamma", 1, 3)

def test_division_et_noms_pour_deux_equipes_du_championnat():
    assert pm.division_et_noms("Pays-Bas : Eerste Divisie", cle("alpha"), cle("beta"), doc()) == ("N2", "Alpha", "Beta")

def test_calibrage_parametres_dans_la_grille_et_aucune_correction():
    h = [(i, S, "ABCD"[i % 4], "ABCD"[(i + 1 + i // 4) % 4], (i * 7) % 4, (i * 5) % 3) for i in range(1, 49)]
    r = cm.calibrer("N2", h); assert r["p1"]["k"] in pp.K_GRILLE and r["p1"]["demi_vie_jours"] in pp.HL_GRILLE and r["calibrage"]["matchs_historique"] == 48
    assert all(r[mk]["statut"] == "P1 CONSERVE" and r[mk]["methode"] == "P1" for mk in cp.MARCHES) and cm.calibrer("N2", h) == r

# doivent échouer (rejetés)
def test_autre_championnat_non_servi_par_matchendirect():
    assert pm.historique("E0", doc(), S) == [] and pm.division_et_noms("Angleterre : League Two", cle("alpha"), cle("beta"), doc()) is None

def test_equipe_inconnue_ou_meme_equipe_des_deux_cotes_rejetee():
    assert pm.division_et_noms("Pays-Bas : Eerste Divisie", cle("alpha"), cle("inconnue"), doc()) is None
    assert pm.division_et_noms("Pays-Bas : Eerste Divisie", cle("alpha"), cle("alpha"), doc()) is None and pm.division_et_noms("Pays-Bas : Eerste Divisie", None, None, doc()) is None

def test_match_sans_score_exclu_et_filtre_jusqua_jour():
    h = pm.historique("N2", doc([m("2026-09-01", "Beta", True, None, None)]), S); assert len(h) == 3
    assert [x for x in ic.historique("N2", jusqua_jour=h[1][0]) if x[0] >= h[1][0]] == []

def test_donnees_reelles_n2_exploitables_par_p1():
    h = ic.historique("N2"); assert len(h) >= 50 and "N2" in cp.charger()["competitions"] and all(isinstance(x[4], int) and isinstance(x[5], int) for x in h)
