"""Tests de verif_etude.py (onglet « Étude » d'Analyse Verdict) : chaque règle avec >= 3 cas qui passent et >= 3 cas qui échouent."""
import gzip, json, os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verif_etude as E
import verif_pronostic as v

GRAND = 1.06

# ---------------------------------------------------------------- la condition : le double des buts marqués ET une meilleure défense
@pytest.mark.parametrize("gf_a, ga_a, gf_b, ga_b", [(2.0, 1.0, 1.0, 1.5), (1.5, 1.0, 0.7, 1.2), (3.0, 0.5, 1.0, 2.0), (11 / 7, 1.071, 11 / 14, 1.929)])
def test_condition_remplie(gf_a, ga_a, gf_b, ga_b):          # inclut le double EXACT (11/7 = 2 x 11/14) : les valeurs arrondies de la page (1,571 et 0,786) ne le montrent pas, la comparaison se fait sur les valeurs exactes
    assert E.condition(gf_a, ga_a, gf_b, ga_b)

@pytest.mark.parametrize("gf_a, ga_a, gf_b, ga_b", [(1.9, 0.9, 1.0, 1.5), (2.0, 1.5, 1.0, 1.5), (2.0, 2.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0), (None, 1.0, 1.0, 1.5), (2.0, None, 1.0, 1.5)])
def test_condition_non_remplie(gf_a, ga_a, gf_b, ga_b):      # moins du double, défense égale ou pire, aucun but marqué, valeur absente
    assert not E.condition(gf_a, ga_a, gf_b, ga_b)

# ---------------------------------------------------------------- les trois catégories d'écart de défense
@pytest.mark.parametrize("ecart, cat", [(0.05, "mince"), (0.79, "mince"), (0.8, "moyen"), (1.0, "moyen"), (1.06, "grand"), (2.4, "grand")])
def test_categories(ecart, cat):
    assert E.categorie(ecart, GRAND) == cat

@pytest.mark.parametrize("ecart", [0, -0.3, None])
def test_pas_de_categorie_sans_ecart_en_faveur(ecart):
    assert E.categorie(ecart, GRAND) is None

# ---------------------------------------------------------------- étude sur matchs joués : moyennes AVANT le match, 4 matchs au même lieu
def _m(jour, dom, ext, gd, ge, saison="2627"):
    return {"saison": saison, "division": "T", "date": jour, "domicile": dom, "exterieur": ext, "buts_dom": gd, "buts_ext": ge}

def _historique(n):    # A gagne 2-0 chez lui n fois ; B perd 0-2 dehors n fois ; puis A - B (score final 3-1)
    L = [_m(f"2026-09-{i + 1:02d}", "A", f"X{i}", 2, 0) for i in range(n)] + [_m(f"2026-09-{i + 1:02d}", f"Y{i}", "B", 2, 0) for i in range(n)]
    return L + [_m("2026-10-30", "A", "B", 3, 1)]

def test_cas_joues_ecart_et_resultat():
    cas = [c for c in E.cas_joues(_historique(4)) if c["lieu"] == "dom" and c["gf"] == 3]
    assert len(cas) == 1 and cas[0]["ecart"] == 2.0 and cas[0]["ga"] == 1            # A encaisse 0, B 2 : écart 2,0 ; le 3-1 final n'entre pas dans les moyennes

@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_cas_joues_moins_de_4_matchs_au_meme_lieu(n):
    assert [c for c in E.cas_joues(_historique(n)) if c["gf"] == 3] == []

def test_cas_joues_ne_regarde_pas_l_avenir():       # changer le score du dernier match ne change pas son écart
    a, b = _historique(5), _historique(5); b[-1] = _m("2026-10-30", "A", "B", 0, 4)
    assert [c["ecart"] for c in E.cas_joues(a) if c["lieu"] == "dom"][-1] == [c["ecart"] for c in E.cas_joues(b) if c["lieu"] == "dom"][-1]

def test_calculer_cases_et_seuil_70(tmp_path):
    f = str(tmp_path / "bloc.json.gz"); json.dump({"liste": _historique(5)}, gzip.open(f, "wt", encoding="utf-8"))
    r = E.calculer(f); c = r["cellules"]["dom"]["grand"]
    assert c["n"] >= 1 and r["seuils"]["ecart_mince_max"] == 0.8 and r["seuils"]["retenu_min"] == 0.7
    for lieu in E.LIEUX:
        for cat in E.CATEGORIES:
            for x in r["cellules"][lieu][cat]["marches"].values(): assert x["retenu"] == bool(x["taux"] is not None and x["taux"] > 0.70)

# ---------------------------------------------------------------- chaque marché de l'étude = le bon marché de la page, avec la même définition
@pytest.mark.parametrize("m", list(E.MARCHES))
def test_marches_identiques_au_catalogue_de_la_page(m):
    f, mdom, mext = E.MARCHES[m]
    for gf in range(0, 6):
        for ga in range(0, 6):
            assert bool(f(gf, ga)) == bool(v.CATALOGUE[mdom](gf, ga)), (m, "domicile", gf, ga)     # équipe à domicile : buts marqués = home
            assert bool(f(gf, ga)) == bool(v.CATALOGUE[mext](ga, gf)), (m, "extérieur", gf, ga)    # équipe à l'extérieur : buts marqués = away

# ---------------------------------------------------------------- évaluer un match, marquer les paris retenus
ETUDE = {"source": {}, "seuils": {"ecart_grand_min": GRAND}, "cellules": {l: {c: {"n": 100, "marches": {m: {"taux": 0.8, "retenu": True} for m in E.MARCHES}} for c in E.CATEGORIES} for l in E.LIEUX}}
ETUDE["cellules"]["dom"]["mince"]["marches"]["equipe_plus_1.5"] = {"taux": 0.625, "retenu": False}

def test_evaluer_domicile_mince():
    r = E.evaluer({"buts_marques": 2.0, "buts_encaisses": 1.0}, {"buts_marques": 1.0, "buts_encaisses": 1.4}, 6, 6, ETUDE)
    assert r["lieu"] == "dom" and r["ecart"] == "mince" and r["valeur_ecart"] == 0.4

def test_evaluer_exterieur_grand():
    r = E.evaluer({"buts_marques": 0.9, "buts_encaisses": 2.4}, {"buts_marques": 1.9, "buts_encaisses": 1.3}, 14, 14, ETUDE)
    assert r["lieu"] == "ext" and r["ecart"] == "grand"

def test_evaluer_domicile_moyen():
    assert E.evaluer({"buts_marques": 2.0, "buts_encaisses": 0.6}, {"buts_marques": 1.0, "buts_encaisses": 1.4}, 5, 5, ETUDE)["ecart"] == "moyen"

@pytest.mark.parametrize("sa, sb, nd, ne", [
    ({"buts_marques": 2.0, "buts_encaisses": 1.0}, {"buts_marques": 1.0, "buts_encaisses": 1.4}, 3, 6),     # 3 matchs seulement au même lieu
    ({"buts_marques": 2.0, "buts_encaisses": 1.0}, {"buts_marques": 1.0, "buts_encaisses": 1.4}, 6, 2),
    ({"buts_marques": 1.5, "buts_encaisses": 1.0}, {"buts_marques": 1.0, "buts_encaisses": 1.4}, 6, 6),     # pas le double
    ({"buts_marques": 2.0, "buts_encaisses": 1.5}, {"buts_marques": 1.0, "buts_encaisses": 1.4}, 6, 6)])   # le double mais pas la meilleure défense
def test_evaluer_non_qualifie(sa, sb, nd, ne):
    assert E.evaluer(sa, sb, nd, ne, ETUDE) is None

def test_evaluer_sans_etude():
    assert E.evaluer({"buts_marques": 2.0, "buts_encaisses": 1.0}, {"buts_marques": 1.0, "buts_encaisses": 1.4}, 6, 6, None) is None

def _noms(info): return [m for m, _, _ in E.retenus(info, ETUDE)]

def test_retenus_domicile_mince():           # marché + cote de la page pour l'équipe à domicile, du plus au moins réussi, sans aucun filtre de la page
    L = E.retenus({"lieu": "dom", "ecart": "mince"}, ETUDE)
    assert sorted(_noms({"lieu": "dom", "ecart": "mince"})) == sorted(["1", "1N", "dom_plus_0.5", "1N&total_plus_1.5", "1N&total_moins_4.5"]) and all(z["taux"] == 0.8 and z["n"] == 100 for _, _, z in L)

def test_retenus_exterieur_marches_de_l_equipe_exterieure():
    assert sorted(_noms({"lieu": "ext", "ecart": "grand"})) == sorted(["2", "N2", "ext_plus_0.5", "ext_plus_1.5", "N2&total_plus_1.5", "N2&total_moins_4.5"])

def test_retenus_plus_1_5_est_bien_analyse():                # « l'équipe marque +1,5 » : écarté dans la case où il est sous 70 %, retenu dans les autres
    assert "dom_plus_1.5" not in _noms({"lieu": "dom", "ecart": "mince"})                  # 62,5 % : sous le seuil
    assert "dom_plus_1.5" in _noms({"lieu": "dom", "ecart": "moyen"}) and "dom_plus_1.5" in _noms({"lieu": "dom", "ecart": "grand"})

def test_retenus_jamais_un_marche_hors_etude():
    for lieu in E.LIEUX:
        for cat in E.CATEGORIES: assert not {"total_plus_2.5", "btts_oui", "total_moins_3.5"} & set(_noms({"lieu": lieu, "ecart": cat}))

def test_retenus_sans_condition():
    assert E.retenus(None, ETUDE) == []

# ---------------------------------------------------------------- la table versionnée du dépôt
def test_table_du_depot_coherente():
    r = E.charger(); assert r is not None
    assert r["seuils"]["ecart_mince_max"] == 0.8 and r["seuils"]["retenu_min"] == 0.7 and r["seuils"]["ecart_grand_min"] > 0.8
    for lieu in E.LIEUX:
        for cat in E.CATEGORIES:
            c = r["cellules"][lieu][cat]; assert c["n"] > 0
            for x in c["marches"].values(): assert x["retenu"] == (x["taux"] > 0.70)

def test_resume_classe_du_plus_au_moins_reussi():
    R = E.resume(E.charger())
    for c in R["cases"]:
        t = [x["taux"] for x in c["marches"]]; assert t == sorted(t, reverse=True) and all(x > 0.70 for x in t)

# ---------------------------------------------------------------- gel des sélections de l'onglet Étude (mesure de la réussite réelle)
def _pari(m, etude=None): return {"marche": m, "cote": 1.5, "taux": 0.7, "verdict": "TIENT", **({"etude": etude} if etude else {})}
def _match(mid, ep, ko="2026-11-20T18:00:00Z"):
    return {"match_id": mid, "date": ko[:10], "coup_d_envoi_utc": ko, "statut": "a_venir", "domicile": "A", "exterieur": "B", "paris": {}, "etude_paris": ep}

def test_selection_etude_gelee_avant_le_match(tmp_path):
    j = str(tmp_path / "sel.jsonl")
    d = {"genere_le": "2026-11-20T10:00:00Z", "matchs": [_match("m1", [_pari("1N", {"taux": 0.8})]), _match("m2", [])]}
    v.geler_selections(d, chemin=j)
    L = v.lire_journal(j); assert [r["match_id"] for r in L if r["selection"] == "etude"] == ["m1"] and v.verifier_journal(j) == []   # m2 : aucun marché retenu, rien à geler
    assert v.geler_selections(d, maintenant="2026-11-20T18:30:00Z", chemin=j) == 0                                                 # après le coup d'envoi : plus de gel

# ---------------------------------------------------------------- de bout en bout : la fiche d'un match (cotes, verdict de la page non filtrant)
def _x(A, B, cotes, jour="2026-11-21"):
    L = lambda eq, S, dom: [{"domicile": dom, "date": f"2026-10-{i + 1:02d}", "saison": "2627", "buts_marques": h, "buts_encaisses": a} for i, (h, a) in enumerate(S)]
    return {"match_id": "t1", "date": jour, "coup_d_envoi_utc": f"{jour}T15:00:00Z", "domicile": "A", "exterieur": "B", "competition": "Championnat inconnu de l'étude", "cotes_betpawa": cotes,
            "assemblage": {"saison_football_data": "2627", "equipe_dom": {"matchs": L("a", A, True)}, "equipe_ext": {"matchs": L("b", B, False)}}}
COTES = {"1x2": {"1": 1.8, "N": 3.5, "2": 4.5}, "dc": {"1N": 1.2, "N2": 1.9, "12": 1.3}}

def _fiche(A, B, cotes=COTES, etude=ETUDE):
    import unittest.mock as mk
    with mk.patch.object(E, "charger", return_value=etude): return v.fiche_match(_x(A, B, cotes), "2026-11-21T06:00:00Z", {"cote_min": 1.26})

def test_fiche_tout_match_qui_remplit_la_condition_figure_avec_ses_marches():
    f = _fiche([(2, 0)] * 6, [(1, 2)] * 6)                      # A marque 2,0 contre 1,0 et encaisse 0 contre 2 : double + écart 2 (grand)
    assert f["etude"]["lieu"] == "dom" and f["etude"]["ecart"] == "grand"
    P = {p["marche"]: p for p in f["etude_paris"]}
    assert "1" in P and P["1"]["cote"] == 1.8 and P["1"]["etude"]["ecart"] == "grand"
    assert "1N" not in P                                          # cote 1,20 sous le minimum 1,26 : seul filtre commun

def test_fiche_le_verdict_de_la_page_ne_filtre_pas_l_etude():
    f = _fiche([(2, 0)] * 6, [(1, 2)] * 6, {"1x2": {"1": 1.8, "N": 3.5, "2": 4.5}})
    assert f["etude_paris"] and all(p["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE", "NE TIENT PAS") for p in f["etude_paris"])

def test_fiche_match_sans_cote_n_a_aucun_marche():
    f = _fiche([(2, 0)] * 6, [(1, 2)] * 6, {})
    assert f["etude"] is not None and f["etude_paris"] == []           # la page l'écarte de l'onglet (voir test_page_*)

@pytest.mark.parametrize("A, B", [([(1, 0)] * 6, [(1, 2)] * 6),         # pas le double (1,0 contre 1,0)
                                  ([(2, 2)] * 6, [(1, 0)] * 6),          # le double mais pire défense
                                  ([(2, 0)] * 3, [(1, 2)] * 6),          # 3 matchs seulement au même lieu
                                  ([(0, 0)] * 6, [(0, 1)] * 6)])         # aucun but marqué
def test_fiche_hors_condition_pas_d_etude(A, B):
    f = _fiche(A, B); assert "etude" not in f and "etude_paris" not in f

# ---------------------------------------------------------------- la page : seuls les matchs avec au moins un marché retenu restent
def _flux(tmp_path, matchs):
    import gzip as gz
    dossier = tmp_path / "flux"; dossier.mkdir()
    with gz.open(str(dossier / "2026-11-21.json.gz"), "wt", encoding="utf-8") as f: json.dump({x["match_id"]: x for x in matchs}, f)
    return str(dossier)

def _page(tmp_path, matchs):
    import unittest.mock as mk
    with mk.patch.object(E, "charger", return_value=ETUDE): return v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, matchs), cfg={"cote_min": 1.26, "sans_regles": True})["matchs"]

def test_page_garde_le_match_avec_un_marche_retenu(tmp_path):
    x = _x([(2, 0)] * 6, [(1, 2)] * 6, COTES); assert [m["match_id"] for m in _page(tmp_path, [x])] == ["t1"]

@pytest.mark.parametrize("cotes", [{}, {"1x2": {"1": 1.1, "N": 9.0, "2": 15.0}, "dc": {"1N": 1.05, "N2": 5.0, "12": 1.1}}])    # pas de cote ; cotes toutes sous 1,26 : aucun marché retenu à cote valable
def test_page_ecarte_le_match_sans_marche_retenu(tmp_path, cotes):
    x = _x([(2, 0)] * 6, [(1, 2)] * 6, cotes); assert _page(tmp_path, [x]) == []

def test_page_ecarte_le_match_hors_condition_sans_pari(tmp_path):
    x = _x([(0, 0)] * 6, [(0, 1)] * 6, {}); assert _page(tmp_path, [x]) == []
