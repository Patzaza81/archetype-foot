"""Tests de verif_categories.py (onglet « Catégories » d'Analyse Verdict, 24/11/2026) :
- les mesures de la fiche sont celles de l'étude (88 lignes de référence tirées de l'étude, valeurs et marchés calculés par le code de l'étude) ;
- chaque marché a >= 3 cas qui passent et >= 3 cas qui échouent ; les bornes sont « bas <= valeur < haut » ;
- la cote vient à la fin (>= 1,26, jamais sans cote) ; aucune fuite vers l'avenir ; les autres onglets sont inchangés ; sélection gelée ; page web."""
import json, math, os, pathlib, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest.mock as mk
import verif_categories as VC
import verif_regle_buts as RB
import verif_regle_plus25 as R25
import verif_pronostic as v

REF = json.load(open(pathlib.Path(__file__).with_name("categories_exemples.json"), encoding="utf-8"))
ZONES = VC.charger()
# seuils de Patrick (24/11/2026), un par marché
SEUILS = {"1": 0.70, "2": 0.60, "total_plus_1.5": 0.80, "1N": 0.90, "N2": 0.75, "dom_plus_0.5": 0.90, "ext_plus_0.5": 0.80,
          "1N&total_plus_1.5": 0.70, "N2&total_plus_1.5": 0.60, "1N&total_moins_4.5": 0.70, "N2&total_moins_4.5": 0.65}
ENT = ("hM", "hC", "aM", "aC", "sMh", "sCh", "sMa", "sCa", "mu")

def _fiche_ref(l):
    return VC.caracteristiques(*(l["entrees"][k] for k in ENT), cal=REF["calibration"])

# ---------------------------------------------------------------- la table figée
def test_table_figee_marches_et_seuils():
    M = ZONES["marches"]; assert {m["marche"]: m["seuil"] for m in M.values()} == SEUILS
    assert all(m["marche"] in v.CATALOGUE for m in M.values())             # les noms sont ceux du catalogue de la page
    assert ZONES["calibration_xg"]["n"] == 316 and ZONES["gele_le"] == "2026-11-24"

@pytest.mark.parametrize("nom", list(ZONES["marches"]))
def test_table_figee_chaque_marche_atteint_son_seuil_sur_la_recherche(nom):
    M = ZONES["marches"][nom]; r = M["stats"]["recherche_2000_2016"]
    assert M["intervalles"] and r["reussis"] / r["matchs"] >= M["seuil"] - 1e-9                 # l'ensemble atteint le seuil sur la période de recherche
    for z in M["intervalles"]:
        s = z["stats"]["recherche_2000_2016"]; assert 0 < s["s"] <= s["n"]
        assert all(len(c) == 3 and (c[1] is None or c[2] is None or c[1] < c[2]) for c in z["conditions"])

def test_version_b_exige_le_seuil_sur_chaque_moitie():
    """Version B = chaque intervalle atteint le seuil avec certitude (borne basse de Wilson) : sa réussite brute sur la recherche dépasse le seuil."""
    for nom, M in ZONES["marches"].items():
        if M["version"] != "B": continue
        for z in M["intervalles"]:
            s = z["stats"]["recherche_2000_2016"]; assert s["s"] / s["n"] >= M["seuil"], (nom, s)

# ---------------------------------------------------------------- mesures de la fiche = mesures de l'étude
@pytest.mark.parametrize("i", range(len(REF["lignes"])))
def test_mesures_identiques_a_l_etude(i):
    l = REF["lignes"][i]; c = _fiche_ref(l)
    for k, x in l["attendu"].items(): assert c[k] == pytest.approx(x, abs=1e-9), k

@pytest.mark.parametrize("i", range(len(REF["lignes"])))
def test_marches_identiques_a_l_etude(i):
    l = REF["lignes"][i]; assert sorted(e["marche"] for e in VC.evaluer(_fiche_ref(l), ZONES)) == sorted(l["marches"])

@pytest.mark.parametrize("marche", sorted(SEUILS))
def test_chaque_marche_au_moins_3_cas_qui_passent_et_3_qui_echouent(marche):
    oui = [l for l in REF["lignes"] if marche in l["marches"]]; non = [l for l in REF["lignes"] if marche not in l["marches"]]
    assert len(oui) >= 3 and len(non) >= 3
    for l in oui: assert marche in [e["marche"] for e in VC.evaluer(_fiche_ref(l), ZONES)]
    for l in non: assert marche not in [e["marche"] for e in VC.evaluer(_fiche_ref(l), ZONES)]

# ---------------------------------------------------------------- bornes : bas <= valeur < haut
@pytest.mark.parametrize("nom", list(ZONES["marches"]))
def test_bornes_de_chaque_intervalle(nom):
    for z in ZONES["marches"][nom]["intervalles"]:
        C = z["conditions"]; centre = {}
        for f, lo, hi in C: centre[f] = (lo + hi) / 2 if lo is not None and hi is not None else (lo + 1 if lo is not None else hi - 1)
        assert VC.dans(centre, C)                                                           # un point du milieu passe
        for f, lo, hi in C:
            if lo is not None: assert VC.dans({**centre, f: lo}, C) and not VC.dans({**centre, f: lo - 1e-9}, C)       # le bas est inclus
            if hi is not None: assert not VC.dans({**centre, f: hi}, C) and VC.dans({**centre, f: hi - 1e-9}, C)       # le haut est exclu

@pytest.mark.parametrize("val", [None, float("nan"), "x"])
def test_valeur_absente_ou_non_numerique_ne_passe_pas(val): assert not VC.dans({"hM": val}, [["hM", 1.0, None]])

def test_variable_absente_ne_passe_pas(): assert not VC.dans({}, [["hM", 1.0, None]]) and not VC.dans(None, [["hM", 1.0, None]])

# ---------------------------------------------------------------- mesures depuis les matchs de la page
def test_mesures_depuis_les_matchs():
    c = VC.mesures([(2, 0), (1, 1), (0, 2), (3, 1)], [(1, 2)] * 4, {"buts_marques": 1.5, "buts_encaisses": 1.0}, {"buts_marques": 1.0, "buts_encaisses": 1.5}, (60, 20), ZONES)
    assert (c["hM"], c["hC"], c["aM"], c["aC"], c["n_dom"], c["n_ext"], c["n_championnat"]) == (1.5, 1.0, 1.0, 2.0, 4, 4, 20)
    assert c["mu"] == pytest.approx(1.5) and c["X1g"] == 3.5 and c["SM"] == 2.5
    cal = ZONES["calibration_xg"]; EH = ((cal["am"] + cal["bm"] * 1.5) + (cal["ae"] + cal["be"] * 1.5)) / 2
    assert c["EH"] == pytest.approx(EH) and c["EHm"] == pytest.approx(EH - 1.5)

@pytest.mark.parametrize("nd, ne", [(3, 8), (8, 3), (0, 5), (2, 2)])
def test_moins_de_4_matchs_au_meme_lieu_aucune_mesure(nd, ne): assert VC.mesures([(1, 1)] * nd, [(1, 1)] * ne, {"buts_marques": 1, "buts_encaisses": 1}, {"buts_marques": 1, "buts_encaisses": 1}, (300, 100), ZONES) is None

@pytest.mark.parametrize("champ", [(27, 9), (0, 0), None])
def test_championnat_de_moins_de_10_matchs_pas_de_xg(champ):
    c = VC.mesures([(2, 0)] * 5, [(0, 1)] * 5, {"buts_marques": 2, "buts_encaisses": 0}, {"buts_marques": 0, "buts_encaisses": 1}, champ, ZONES)
    assert "EH" not in c and "mu" not in c and c["hM"] == 2                                    # les piliers restent, le xG et le championnat manquent
    assert not any(e["marche"] in ("total_plus_1.5",) for e in VC.evaluer(c, ZONES))            # un intervalle qui demande le xG ne s'applique jamais sans lui

def test_sans_saison_pas_de_xg():
    c = VC.mesures([(2, 0)] * 5, [(0, 1)] * 5, None, {"buts_marques": 0, "buts_encaisses": 1}, (300, 100), ZONES); assert "EH" not in c

def test_victoire_domicile_sans_xg_est_impossible_car_l_intervalle_utilise_le_xg():
    c = VC.mesures([(3, 0)] * 5, [(0, 2)] * 5, None, None, (300, 100), ZONES); assert "1" not in [e["marche"] for e in VC.evaluer(c, ZONES)]

def test_evaluer_sans_donnees(): assert VC.evaluer(None, ZONES) == [] and VC.evaluer({}, ZONES) == [] and VC.evaluer({"hM": 3}, {"marches": {}}) == []

# ---------------------------------------------------------------- classement : borne basse de Wilson sur les matchs jamais vus
def test_classement_par_marge_decroissante():
    l = max(REF["lignes"], key=lambda l: len(l["marches"])); E = VC.evaluer(_fiche_ref(l), ZONES)
    assert len(E) >= 2 and [e["marge"] for e in E] == sorted((e["marge"] for e in E), reverse=True)
    for e in E:
        s, n = e["vus"]; assert 0 < s <= n and e["marge"] == pytest.approx(round(VC.wilson(s, n)[0], 4)) and e["marge"] <= e["taux_vu"]

def test_wilson_valeurs_connues():
    lo, hi = VC.wilson(50, 100); assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    assert VC.wilson(0, 0) == (0.0, 1.0)

def test_resume():
    R = VC.resume(ZONES); assert set(R["marches"]) == set(ZONES["marches"]) and R["gele_le"] == "2026-11-24"
    assert R["marches"]["Victoire domicile"]["test_2017_2020"] == [734, 1008]

# ---------------------------------------------------------------- de bout en bout : la fiche d'un match
def _x(A, B, cotes, SA=None, SB=None, jour="2026-11-21", mid="t1"):
    """A : scores de l'équipe à domicile CHEZ ELLE ; B : scores de l'équipe à l'extérieur DEHORS ; SA / SB : autres matchs de la saison (l'autre lieu)."""
    L = lambda S, dom, d0: [{"domicile": dom, "date": f"2026-{d0}-{i + 1:02d}", "saison": "2627", "buts_marques": h, "buts_encaisses": a} for i, (h, a) in enumerate(S)]
    return {"match_id": mid, "date": jour, "coup_d_envoi_utc": f"{jour}T15:00:00Z", "domicile": "A", "exterieur": "B", "competition": "Ch", "cotes_betpawa": cotes,
            "assemblage": {"saison_football_data": "2627", "equipe_dom": {"matchs": L(A, True, "10") + L(SA or [], False, "09")}, "equipe_ext": {"matchs": L(B, False, "10") + L(SB or [], True, "09")}}}

FORT, FAIBLE = [(2, 0)] * 6, [(0, 1)] * 6            # A gagne 2-0 chez lui ; B perd 0-1 dehors : hM 2,0 ; xG attendu du domicile très supérieur
TOT = {"Ch": [("2026-10-01", 3)] * 40}               # championnat à 3 buts par match (1,5 par équipe), 40 matchs précédents
C1X2 = {"1x2": {"1": 1.40, "N": 4.0, "2": 9.0}}

def _fiche(A, B, cotes, zones="depot", totaux=TOT, **k):
    with mk.patch.object(VC, "charger", return_value=(VC.charger() if zones == "depot" else zones)), mk.patch.object(RB, "charger", return_value=None), mk.patch.object(R25, "charger", return_value=None):
        return v.fiche_match(_x(A, B, cotes, **k), "2026-11-21T06:00:00Z", {"cote_min": 1.26, "sans_regles": True}, totaux)

@pytest.mark.parametrize("cote", [1.26, 1.40, 2.10])
def test_fiche_dans_un_intervalle_avec_cote_suffisante(cote):
    f = _fiche(FORT, FAIBLE, {"1x2": {"1": cote, "N": 4.0, "2": 9.0}}); P = f["categories"]["paris"]
    assert [p["marche"] for p in P] == ["1"] and P[0]["cote"] == cote and P[0]["categorie"]["seuil"] == 0.70 and P[0]["categorie"]["version"] == "B"
    c = P[0]["categorie"]["conditions"]; assert [x["variable"] for x in c] == ["hM", "rE"] and c[0]["valeur"] == 2.0 and c[0]["bas"] == 1.8
    assert f["categories"]["mesures"]["hM"] == 2.0 and P[0]["categorie"]["vus"][1] == 1792

@pytest.mark.parametrize("cotes", [{"1x2": {"1": 1.239, "N": 4.0, "2": 9.0}}, {"1x2": {"1": 1.10, "N": 6.0, "2": 15.0}}, {}, {"over_under_1.5": {"plus": 1.1, "moins": 6.0}}])
def test_fiche_cote_insuffisante_ou_absente_pas_de_marche(cotes):          # la cote vient à la fin : sous 1,24 ou absente, jamais proposé
    assert "1" not in [p["marche"] for p in (_fiche(FORT, FAIBLE, cotes).get("categories") or {}).get("paris", [])]

@pytest.mark.parametrize("A, B", [([(1, 1)] * 6, [(1, 1)] * 6),                       # équipes équilibrées
                                  ([(0, 2)] * 6, [(2, 0)] * 6),                       # l'extérieur domine
                                  ([(2, 0)] * 3, FAIBLE),                             # 3 matchs au même lieu seulement
                                  (FORT, [(0, 1)] * 3),                               # idem côté extérieur
                                  ([(1, 0)] * 6, [(1, 0)] * 6)])                      # hM sous 1,8
def test_fiche_hors_intervalle_pas_de_victoire_domicile(A, B):
    assert "1" not in [p["marche"] for p in (_fiche(A, B, C1X2).get("categories") or {}).get("paris", [])]

@pytest.mark.parametrize("tot", [{"Ch": [("2026-10-01", 3)] * 9}, {}])
def test_fiche_championnat_trop_court_pas_de_marche_xg(tot):      # la victoire domicile utilise le xG relatif au championnat : moins de 10 matchs = rien
    assert "categories" not in _fiche(FORT, FAIBLE, C1X2, totaux=tot)

def test_fiche_championnat_ne_regarde_pas_l_avenir():             # matchs du championnat le jour même et après : ignorés, il reste 9 matchs
    tot = {"Ch": [("2026-10-01", 3)] * 9 + [("2026-11-21", 3)] * 40 + [("2026-11-25", 3)] * 40}
    assert "categories" not in _fiche(FORT, FAIBLE, C1X2, totaux=tot)

def test_fiche_sans_table_pas_d_onglet(): assert "categories" not in _fiche(FORT, FAIBLE, C1X2, zones=None)

def test_fiche_les_autres_onglets_ne_changent_pas():              # avec ou sans l'onglet Catégories : mêmes paris dans tous les autres onglets
    a = _fiche(FORT, FAIBLE, C1X2); b = _fiche(FORT, FAIBLE, C1X2, zones=None)
    assert "categories" in a and "categories" not in b and {k: a[k] for k in a if k != "categories"} == b

def test_fiche_resultat_gagne():
    f = _fiche(FORT, FAIBLE, C1X2, SA=[(1, 0)], SB=[(0, 0)]); assert "gagne" not in f["categories"]["paris"][0]          # match à venir : pas de résultat
    x = _x(FORT, FAIBLE, C1X2); x["score"] = {"buts_dom": 2, "buts_ext": 0}
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(R25, "charger", return_value=None):
        g = v.fiche_match(x, "2026-11-21T20:00:00Z", {"cote_min": 1.26, "sans_regles": True}, TOT)
    assert g["categories"]["paris"][0]["gagne"] is True

# ---------------------------------------------------------------- page, gel des sélections, page web
def _flux(tmp_path, matchs):
    import gzip
    dossier = tmp_path / "flux"; dossier.mkdir()
    with gzip.open(str(dossier / "2026-11-21.json.gz"), "wt", encoding="utf-8") as f: json.dump({x["match_id"]: x for x in matchs}, f)
    return str(dossier)

def test_page_porte_la_table_et_le_match(tmp_path):
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(R25, "charger", return_value=None), mk.patch.object(v, "totaux_championnats", return_value=TOT):
        d = v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, [_x(FORT, FAIBLE, C1X2)]), cfg={"cote_min": 1.26, "sans_regles": True})
    assert d["categories"]["marches"]["Victoire domicile"]["seuil"] == 0.70 and [m["match_id"] for m in d["matchs"] if m.get("categories")] == ["t1"]

def test_selection_categories_gelee_avant_le_match(tmp_path):
    j = str(tmp_path / "sel.jsonl")
    m1 = {"match_id": "m1", "date": "2026-11-20", "coup_d_envoi_utc": "2026-11-20T18:00:00Z", "statut": "a_venir", "domicile": "A", "exterieur": "B", "paris": {}, "categories": {"paris": [{"marche": "1", "cote": 1.5, "taux": 0.8, "verdict": "TIENT"}]}}
    m2 = {**m1, "match_id": "m2", "categories": None}
    d = {"genere_le": "2026-11-20T10:00:00Z", "matchs": [m1, m2]}
    v.geler_selections(d, chemin=j)
    assert [r["match_id"] for r in v.lire_journal(j) if r["selection"] == "categories"] == ["m1"] and v.verifier_journal(j) == []
    assert v.geler_selections(d, maintenant="2026-11-20T18:30:00Z", chemin=j) == 0                  # après le coup d'envoi : plus rien n'est écrit

def test_page_web_onglet():
    js = (pathlib.Path(v.RACINE) / "archetype_verif.js").read_text(encoding="utf-8")
    assert '["categories", "Catégories"]' in js and "m.categories && m.categories.paris" in js and '"Onglet Catégories"' in js and "noteCategories(d)" in js
    assert '["plus25", "+2,5 buts"]' in js and '["plus15", "+1,5 buts"]' in js and '["etude", "Étude"]' in js          # les autres onglets restent en place

# ---------------------------------------------------------------- cote minimale 1,24 pour le plus de 1,5 seulement (Patrick, 24/11/2026)
FORT3 = [(3, 0)] * 6                                          # hM 3,0 : dans un intervalle du plus de 1,5 (hM >= 2,2 et xG attendu du domicile >= 1,56)

def _p15(cote, extra=None):
    f = _fiche(FORT3, FAIBLE, {"over_under_1.5": {"plus": cote, "moins": 5.0}, **(extra or {})})
    return [p for p in (f.get("categories") or {}).get("paris", []) if p["marche"] == "total_plus_1.5"]

@pytest.mark.parametrize("cote", [1.24, 1.25, 1.26, 1.40])
def test_plus_de_1_5_retenu_des_1_24(cote): assert len(_p15(cote)) == 1 and _p15(cote)[0]["cote"] == cote

@pytest.mark.parametrize("cote", [1.23, 1.20, 1.10])
def test_plus_de_1_5_sous_1_24_jamais_retenu(cote): assert _p15(cote) == []

def test_plus_de_1_5_sans_cote_jamais_retenu(): assert _p15(1.5, None) != [] and "total_plus_1.5" not in [p["marche"] for p in (_fiche(FORT3, FAIBLE, {}).get("categories") or {}).get("paris", [])]

@pytest.mark.parametrize("marche, cotes", [("1", {"1x2": {"1": 1.23, "N": 4.0, "2": 9.0}}), ("1", {"1x2": {"1": 1.10, "N": 4.0, "2": 9.0}}), ("1N", {"double_chance": {"1N": 1.22, "N2": 5.0, "12": 1.2}})])
def test_les_autres_marches_sous_1_24_jamais_retenus(marche, cotes):
    assert marche not in [p["marche"] for p in (_fiche(FORT3, FAIBLE, cotes).get("categories") or {}).get("paris", [])]

def test_cote_min_fonction():
    assert VC.cote_min("total_plus_1.5", 1.26) == 1.24 and VC.cote_min("1", 1.26) == 1.26 and VC.cote_min("total_plus_1.5", 1.20) == 1.20

# ---------------------------------------------------------------- bande de cote 1,24-1,25 : les 3 meilleurs sur 4 jours pour chaque marché (Patrick, 24/11/2026)
def _par(marche, cote, marge, bande):
    e = {"marche": marche, "cote": cote, "categorie": {"marge": marge}}
    if bande: e["categorie"]["bande"] = True
    return e

def _m(mid, jour, *paris): return {"match_id": mid, "coup_d_envoi_utc": jour + "T15:00:00Z", "categories": {"paris": list(paris)}}
JOUR = lambda m: m["coup_d_envoi_utc"][:10]

@pytest.mark.parametrize("cote", [1.24, 1.25])
def test_fiche_bande_1_24_1_25_marquee(cote):
    p = _fiche(FORT, FAIBLE, {"1x2": {"1": cote, "N": 4.0, "2": 9.0}})["categories"]["paris"]
    assert [x["marche"] for x in p] == ["1"] and p[0]["categorie"]["bande"] is True and p[0]["cote"] == cote

@pytest.mark.parametrize("cote", [1.26, 1.40, 2.0])
def test_fiche_1_26_et_plus_jamais_dans_la_bande(cote):
    p = _fiche(FORT, FAIBLE, {"1x2": {"1": cote, "N": 4.0, "2": 9.0}})["categories"]["paris"]; assert "bande" not in p[0]["categorie"]

@pytest.mark.parametrize("cote", [1.239, 1.20, 1.05])
def test_fiche_sous_1_24_pas_de_bande(cote):
    assert "1" not in [x["marche"] for x in (_fiche(FORT, FAIBLE, {"1x2": {"1": cote, "N": 4.0, "2": 9.0}}).get("categories") or {}).get("paris", [])]

def test_plus_de_1_5_a_1_24_n_est_pas_limite_par_la_bande():          # le plus de 1,5 a déjà 1,24 comme cote minimale : pas de bande, pas de limite
    assert "bande" not in _p15(1.24)[0]["categorie"]

def test_limiter_trois_meilleurs_par_jour_et_marche():
    M = [_m("a%d" % i, "2026-11-24", _par("1", 1.25, 0.60 + i / 100, True)) for i in range(5)]      # marges 0,60 ... 0,64
    VC.limiter_bande(M, JOUR)
    assert [m["match_id"] for m in M if m.get("categories")] == ["a2", "a3", "a4"]                  # les 3 meilleures marges
    assert all("categories" not in M[i] for i in (0, 1))                                             # un match sans pari restant perd sa clé

def test_limiter_exactement_3_ou_moins_rien_retire():
    for n in (1, 2, 3):
        M = [_m("b%d" % i, "2026-11-24", _par("1", 1.24, 0.5 + i / 100, True)) for i in range(n)]; VC.limiter_bande(M, JOUR); assert all(m.get("categories") for m in M)

def test_limiter_un_jour_et_un_marche_separes():
    M = [_m("c%d" % i, "2026-11-24", _par("1", 1.25, 0.5 + i / 100, True)) for i in range(4)] + [_m("d%d" % i, "2026-11-25", _par("1", 1.25, 0.5 + i / 100, True)) for i in range(3)] + \
        [_m("e%d" % i, "2026-11-24", _par("2", 1.25, 0.5 + i / 100, True)) for i in range(3)]
    VC.limiter_bande(M, JOUR)
    assert sum(1 for m in M if m.get("categories")) == 3 + 3 + 3                                    # 3 pour le marché 1 du 24, 3 pour le marché 1 du 25, 3 pour le marché 2 du 24

def test_limiter_ne_touche_jamais_les_cotes_1_26_et_plus():
    M = [_m("f%d" % i, "2026-11-24", _par("1", 1.30, 0.5, False)) for i in range(6)] + [_m("g%d" % i, "2026-11-24", _par("1", 1.25, 0.9 - i / 100, True)) for i in range(5)]
    VC.limiter_bande(M, JOUR); assert sum(1 for m in M if m.get("categories")) == 6 + 3

def test_limiter_un_match_garde_ses_autres_paris():
    M = [_m("h0", "2026-11-24", _par("1", 1.25, 0.1, True), _par("1N", 1.5, 0.9, False))] + [_m("h%d" % i, "2026-11-24", _par("1", 1.25, 0.8, True)) for i in range(1, 5)]
    VC.limiter_bande(M, JOUR); assert [p["marche"] for p in M[0]["categories"]["paris"]] == ["1N"]    # le pari de bande est écarté, le pari à 1,50 reste

def test_limiter_doublon_de_match_compte_une_fois():
    M = [_m("i0", "2026-11-24", _par("1", 1.25, 0.9, True)), _m("i0", "2026-11-24", _par("1", 1.25, 0.9, True))] + [_m("i%d" % i, "2026-11-24", _par("1", 1.25, 0.8 - i / 100, True)) for i in range(1, 4)]
    VC.limiter_bande(M, JOUR); assert [m["match_id"] for m in M if m.get("categories")] == ["i0", "i0", "i1", "i2"]     # i0 (deux copies) + i1 + i2 = 3 matchs

def test_limiter_sans_categories(): M = [{"match_id": "z", "coup_d_envoi_utc": "2026-11-24T15:00:00Z"}]; assert VC.limiter_bande(M, JOUR) == M

def test_page_bande_trois_meilleurs_du_jour(tmp_path):
    ms = [_x(FORT, FAIBLE, {"1x2": {"1": 1.25, "N": 4.0, "2": 9.0}}, mid="m%d" % i) for i in range(5)]
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(R25, "charger", return_value=None), mk.patch.object(v, "totaux_championnats", return_value=TOT):
        d = v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, ms), cfg={"cote_min": 1.26, "sans_regles": True})
    assert len([m for m in d["matchs"] if m.get("categories")]) == 3 and d["nb_matchs"] == 3

def test_page_web_note_bande():
    js = (pathlib.Path(v.RACINE) / "archetype_verif.js").read_text(encoding="utf-8")
    assert "C.bande" in js and "3 meilleurs sur 4 jours" in js

@pytest.mark.parametrize("ko, attendu", [("2026-11-24T15:00:00Z", 0), ("2026-11-26T15:00:00Z", 0), ("2026-11-27T15:00:00Z", 0), ("2026-11-28T15:00:00Z", None), ("2026-11-23T15:00:00Z", None), ("2026-11-20T15:00:00Z", None), (None, None)])
def test_periode_4_jours_depuis_aujourd_hui(ko, attendu): assert v.periode_4_jours(ko, "2026-11-24T09:00:00Z") == attendu

def test_periode_4_jours_jour_de_douala():                      # 23h30 UTC = 00h30 le lendemain à Douala : c'est déjà le jour suivant
    assert v.periode_4_jours("2026-11-24T23:30:00Z", "2026-11-24T09:00:00Z") == v.periode_4_jours("2026-11-25T10:00:00Z", "2026-11-24T09:00:00Z") == 0

def test_page_bande_3_meilleurs_sur_les_4_jours_pas_par_jour(tmp_path):
    ms = [_x(FORT, FAIBLE, {"1x2": {"1": 1.25, "N": 4.0, "2": 9.0}}, jour="2026-11-21", mid="j%d" % i) for i in range(3)] + [_x(FORT, FAIBLE, {"1x2": {"1": 1.25, "N": 4.0, "2": 9.0}}, jour="2026-11-22", mid="k%d" % i) for i in range(3)]
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(R25, "charger", return_value=None), mk.patch.object(v, "totaux_championnats", return_value=TOT):
        d = v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, ms), cfg={"cote_min": 1.26, "sans_regles": True})
    assert len([m for m in d["matchs"] if m.get("categories")]) == 3                              # 6 candidats sur 2 jours de la même période : 3 gardés au total

def test_page_bande_hors_des_4_jours_pas_retenue(tmp_path):      # aujourd'hui = 21/11 : le 25/11 est à J+4, hors fenêtre ; les jours passés aussi
    ms = [_x(FORT, FAIBLE, {"1x2": {"1": 1.25, "N": 4.0, "2": 9.0}}, jour=j, mid="%s%d" % (j[-2:], i)) for j in ("2026-11-21", "2026-11-25") for i in range(2)]
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(R25, "charger", return_value=None), mk.patch.object(v, "totaux_championnats", return_value=TOT):
        d = v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, ms), cfg={"cote_min": 1.26, "sans_regles": True})
    assert sorted(m["match_id"] for m in d["matchs"] if m.get("categories")) == ["210", "211"]

def test_page_bande_jours_passes_pas_retenus(tmp_path):
    ms = [_x(FORT, FAIBLE, {"1x2": {"1": 1.25, "N": 4.0, "2": 9.0}}, jour="2026-11-19", mid="pas%d" % i) for i in range(2)]
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(R25, "charger", return_value=None), mk.patch.object(v, "totaux_championnats", return_value=TOT):
        d = v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, ms), cfg={"cote_min": 1.26, "sans_regles": True})
    assert not [m for m in d["matchs"] if m.get("categories")]

def test_aucune_bande_rien_n_est_force():                         # aucun candidat : aucun pari ajouté, aucune erreur
    M = [_m("n0", "2026-11-24", _par("1", 1.40, 0.7, False))]; VC.limiter_bande(M, JOUR); assert M[0]["categories"]["paris"][0]["cote"] == 1.40
