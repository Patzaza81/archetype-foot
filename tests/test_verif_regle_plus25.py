"""Tests de verif_regle_plus25.py (onglet « +2,5 buts » d'Analyse Verdict, refait le 24/11/2026 : modèle de probabilité appris sur 2000-2012, seuil pris sur 2013-2016).
Chaque condition a >= 3 cas qui passent et >= 3 cas qui échouent ; aucune fuite vers l'avenir ; la cote seulement à la fin (1,26 à 1,45) ; les autres onglets inchangés."""
import gzip, json, math, os, pathlib, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest.mock as mk
import verif_regle_plus25 as R
import verif_regle_buts as RB
import verif_pronostic as v

SEUIL = R.modele()["seuil"]
OK = {"n_dom": 5, "n_ext": 5, "n_championnat": 40, "proba": 0.70}

# ---------------------------------------------------------------- le modèle gelé
def test_modele_coherent():
    M = R.modele()
    assert len(M["F"]) == len(M["coef"]) == len(M["mean"]) == len(M["scale"]) == len(M["bornes_bas"]) == len(M["bornes_haut"]) == 29
    assert 0.5 < M["seuil"] < 0.8 and M["apprentissage"]["periode"] == "2000 à 2012" and all(b <= h for b, h in zip(M["bornes_bas"], M["bornes_haut"]))

EXEMPLES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modele_plus25_exemples.json"), encoding="utf-8"))   # 6 lignes, proba calculée à l'apprentissage
@pytest.mark.parametrize("i", range(6))
def test_proba_reproduit_l_apprentissage(i): assert R.proba(EXEMPLES[i]["traits"]) == pytest.approx(EXEMPLES[i]["proba"], abs=1e-9)

def test_proba_sans_donnees(): assert R.proba(None) is None and R.proba({}) is None

def test_proba_valeurs_extremes_ramenees_aux_bornes():
    t = dict(EXEMPLES[0]["traits"]); t2 = {**t, "hgd": 500.0, "gdd": 900.0, "hM": 80.0}
    assert 0.0 < R.proba(t2) < 1.0 and R.proba(t2) == R.proba({**t, "hgd": 5000.0, "gdd": 9000.0, "hM": 8000.0})

# ---------------------------------------------------------------- les mesures, calculées à la main
def test_traits_a_la_main():
    t = R.traits([(2, 0), (1, 1), (0, 2), (3, 1)], [(1, 2)] * 4, {"buts_marques": 2.0, "buts_encaisses": 0.5}, {"buts_marques": 1.0, "buts_encaisses": 1.5}, (60, 20, 9))
    att = {"L": 3.0, "pL": 0.45, "hM": 1.5, "hC": 1.0, "aM": 1.0, "aC": 2.0, "SM": 2.5, "SC": 3.0, "X1": 3.5, "X2": 2.0, "hf3": 0.25, "af3": 1.0, "f3": 0.625, "hsc": 0.75, "asc": 1.0,
           "hcn": 0.75, "acn": 1.0, "hbt": 0.5, "abt": 1.0, "bt": 0.75, "hgd": 1.5, "agd": -0.5, "hsM": 2.0, "hsC": 0.5, "asM": 1.0, "asC": 1.5, "gdd": 2.0, "dM": 0.5, "dC": 1.0}
    assert t == pytest.approx(att)

@pytest.mark.parametrize("args", [([], [(1, 1)] * 4, {"buts_marques": 1, "buts_encaisses": 1}, {"buts_marques": 1, "buts_encaisses": 1}, (60, 20, 9)),          # pas de match à domicile
                                  ([(1, 1)] * 4, [(1, 1)] * 4, None, {"buts_marques": 1, "buts_encaisses": 1}, (60, 20, 9)),                                      # saison de A inconnue
                                  ([(1, 1)] * 4, [(1, 1)] * 4, {"buts_marques": None, "buts_encaisses": 1}, {"buts_marques": 1, "buts_encaisses": 1}, (60, 20, 9)),
                                  ([(1, 1)] * 4, [(1, 1)] * 4, {"buts_marques": 1, "buts_encaisses": 1}, {"buts_marques": 1, "buts_encaisses": 1}, (60, 0, 0)),     # championnat vide
                                  ([(1, 1)] * 4, [(1, 1)] * 4, {"buts_marques": 1, "buts_encaisses": 1}, {"buts_marques": 1, "buts_encaisses": 1}, (60, 20))])    # pas de nombre de matchs à 3 buts
def test_traits_donnee_absente(args): assert R.traits(*args) is None

A6 = [(2, 1), (3, 2), (2, 2), (1, 2), (3, 1), (2, 3)]          # A à domicile : beaucoup de buts
B6 = [(1, 2), (2, 2), (0, 3), (1, 1), (2, 3), (1, 2)]          # B à l'extérieur : beaucoup de buts aussi
SD = lambda S: {"buts_marques": sum(a for a, _ in S) / len(S), "buts_encaisses": sum(b for _, b in S) / len(S)}
CH = (120, 40, 24)                                              # championnat à 3,0 buts par match, 24 matchs sur 40 à 3 buts ou plus
def _mes(A, B, ch=CH): return R.mesures(A, B, SD(A), SD(B), ch)

def test_mesures():
    x = _mes(A6, B6)
    assert x["n_dom"] == 6 and x["n_ext"] == 6 and x["n_championnat"] == 40 and x["championnat"] == 3.0 and x["plus25_matchs"] == [11, 12]
    assert x["dom_marques"] == 2.17 and x["dom_encaisses"] == 1.83 and x["ext_marques"] == 1.17 and x["ext_encaisses"] == 2.17 and x["proba"] == pytest.approx(0.637377, abs=1e-5)

# ---------------------------------------------------------------- la règle : chaque condition
@pytest.mark.parametrize("p", [SEUIL, SEUIL + 0.0001, 0.70, 0.95])                  # « au moins » le seuil
def test_proba_assez_haute(p): assert R.remplie({**OK, "proba": p})

@pytest.mark.parametrize("p", [SEUIL - 0.0001, 0.55, 0.30, 0.0, None])
def test_proba_trop_basse(p): assert not R.remplie({**OK, "proba": p})

@pytest.mark.parametrize("nd, ne, nc", [(4, 4, 10), (5, 9, 30), (12, 6, 10)])
def test_assez_de_matchs(nd, ne, nc): assert R.remplie({**OK, "n_dom": nd, "n_ext": ne, "n_championnat": nc})

@pytest.mark.parametrize("nd, ne, nc", [(3, 8, 40), (8, 3, 40), (0, 6, 40), (5, 5, 9), (5, 5, 0)])
def test_pas_assez_de_matchs(nd, ne, nc): assert not R.remplie({**OK, "n_dom": nd, "n_ext": ne, "n_championnat": nc})

def test_remplie_sans_donnees(): assert not R.remplie(None) and not R.remplie({})

@pytest.mark.parametrize("A, B, ch, voulu", [(A6, B6, CH, True),                                                                   # deux équipes à buts, championnat à 3,0
                                             (A6[:5] + [(3, 3)], B6, (130, 40, 30), True),                                          # idem, un peu plus de buts
                                             (A6, [(2, 2), (1, 3), (3, 1), (0, 3), (2, 3), (2, 1)], CH, True),
                                             ([(1, 0), (0, 0), (1, 1), (0, 1), (1, 0), (0, 0)], B6, CH, False),                    # l'équipe à domicile n'a presque pas de buts
                                             ([(1, 0), (0, 0), (1, 1), (0, 1), (1, 0), (0, 0)], [(0, 1), (0, 0), (1, 0), (0, 0), (0, 2), (1, 0)], CH, False),   # deux équipes sans buts
                                             ([(0, 0)] * 6, [(0, 0)] * 6, CH, False),
                                             (A6, B6, (80, 40, 8), False)])                                                        # championnat à 2,0 buts par match, 20 % de matchs à 3 buts
def test_modele_juge_les_matchs(A, B, ch, voulu): assert R.remplie(_mes(A, B, ch)) is voulu

# ---------------------------------------------------------------- étude sur matchs joués : sans fuite
def _m(jour, dom, ext, gd, ge, div="T", saison="2627", ou=None):
    m = {"id": f"{jour}|{dom}|{ext}", "saison": saison, "division": div, "date": jour, "domicile": dom, "exterieur": ext, "buts_dom": gd, "buts_ext": ge, "cotes": {}}
    if ou: m["cotes"]["plus_moins_2_5_cloture"] = {"moy": [ou, 1.9]}
    return m

def _historique(n, final=(3, 1), ou=1.5):
    """A reçoit n adversaires (scores de A6), B joue chez n adversaires (scores de B6), puis A - B."""
    L = [_m(f"2026-09-{i + 1:02d}", "A", f"X{i}", *A6[i % 6]) for i in range(n)] + [_m(f"2026-09-{i + 1:02d}", f"Y{i}", "B", B6[i % 6][1], B6[i % 6][0]) for i in range(n)]
    return L + [_m("2026-10-30", "A", "B", *final, ou=ou)]

def test_cas_joues_valeurs():
    c = [x for x in R.cas_joues(_historique(6)) if x["date"] == "2026-10-30"][0]
    assert c["n_championnat"] == 12 and c["n_dom"] == 6 and c["n_ext"] == 6 and c["plus25_matchs"] == [11, 12] and c["proba"] is not None and R.remplie(c)

@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_cas_joues_moins_de_4_matchs_au_meme_lieu(n):
    assert [x for x in R.cas_joues(_historique(n)) if x["date"] == "2026-10-30"] == []

def test_cas_joues_ne_regarde_pas_l_avenir():
    a, b = R.cas_joues(_historique(6, (0, 0)))[-1], R.cas_joues(_historique(6, (5, 5)))[-1]
    assert {k: a[k] for k in a if k not in ("total",)} == {k: b[k] for k in b if k not in ("total",)} and a["total"] != b["total"]

def test_cas_joues_le_jour_meme_ne_compte_pas():         # un match du même jour (déjà joué dans la liste) ne change pas les valeurs
    L = _historique(6); L2 = L + [_m("2026-10-30", "Z1", "Z2", 9, 9)]
    a = [x for x in R.cas_joues(L) if x["date"] == "2026-10-30"][0]; b = [x for x in R.cas_joues(L2) if x["date"] == "2026-10-30" and x["n_dom"] == 6][0]
    assert a["proba"] == b["proba"] and a["n_championnat"] == b["n_championnat"]

def _calc(tmp_path, ou):
    f = str(tmp_path / "bloc.json.gz"); json.dump({"liste": _historique(6, (2, 1), ou=ou)}, gzip.open(f, "wt", encoding="utf-8")); return R.calculer(f)

@pytest.mark.parametrize("ou, dans_la_bande", [(1.26, 1), (1.40, 1), (1.45, 1), (1.25, 0), (1.46, 0), (1.90, 0)])
def test_calculer_cote_a_la_fin(tmp_path, ou, dans_la_bande):
    r = _calc(tmp_path, ou)
    assert r["etude"]["matchs"] == 1 and r["etude"]["reussis"] == 1 and r["etude"]["non_vus"]["matchs"] == 1 and r["etude"]["non_vus_cote_min"]["matchs"] == dans_la_bande
    assert r["regle"]["seuil_proba"] == SEUIL and r["regle"]["cote_min"] == 1.26 and r["regle"]["cote_max"] == 1.45

def test_table_du_depot_coherente():
    r = R.charger(); assert r is not None
    E = r["etude"]; NV = E["non_vus"]
    assert E["matchs"] == NV["matchs"] and NV["matchs"] >= NV["reussis"] > 0 and NV["borne_basse"] <= NV["taux"] <= NV["borne_haute"]
    assert NV["taux"] > E["tous_non_vus"]["taux"]                       # le modèle fait mieux que tous les matchs de la même période
    assert r["regle"]["seuil_proba"] == SEUIL and r["regle"]["cote_max"] == R.COTE_MAX and len(E["grands_echantillons"]) == 2
    assert all(g["taux"] > g["tous"]["taux"] for g in E["grands_echantillons"])

# ---------------------------------------------------------------- de bout en bout : la fiche d'un match
def _x(A, B, cotes, SA=None, SB=None, jour="2026-11-21", mid="t1"):
    """A : scores de l'équipe à domicile CHEZ ELLE ; B : scores de l'équipe à l'extérieur DEHORS ; SA / SB : autres matchs de la saison (l'autre lieu)."""
    L = lambda S, dom, d0: [{"domicile": dom, "date": f"2026-{d0}-{i + 1:02d}", "saison": "2627", "buts_marques": h, "buts_encaisses": a} for i, (h, a) in enumerate(S)]
    return {"match_id": mid, "date": jour, "coup_d_envoi_utc": f"{jour}T15:00:00Z", "domicile": "A", "exterieur": "B", "competition": "Ch", "cotes_betpawa": cotes,
            "assemblage": {"saison_football_data": "2627", "equipe_dom": {"matchs": L(A, True, "10") + L(SA or [], False, "09")}, "equipe_ext": {"matchs": L(B, False, "10") + L(SB or [], True, "09")}}}
def OU(plus): return {"over_under_2.5": {"plus": plus, "moins": 2.6}}
TOT = {"Ch": [("2026-10-01", 5)] * 24 + [("2026-10-01", 0)] * 16}   # championnat à 3,0 buts par match, 24 matchs sur 40 à 3 buts ou plus
FAIBLE_A, FAIBLE_B = [(1, 0), (0, 0), (1, 1), (0, 1), (1, 0), (0, 0)], [(0, 1), (0, 0), (1, 0), (0, 0), (0, 2), (1, 0)]

def _fiche(A, B, cotes, regle="depot", totaux=TOT, **k):
    with mk.patch.object(R, "charger", return_value=(R.charger() if regle == "depot" else regle)), mk.patch.object(RB, "charger", return_value=None):
        return v.fiche_match(_x(A, B, cotes, **k), "2026-11-21T06:00:00Z", {"cote_min": 1.26, "sans_regles": True}, totaux)

@pytest.mark.parametrize("cote", [1.26, 1.35, 1.45])
def test_fiche_retenue_avec_cote_dans_la_bande(cote):
    f = _fiche(A6, B6, OU(cote)); x = f["plus25"]; p = x["pari"]
    assert p["marche"] == "total_plus_2.5" and p["cote"] == cote and p["regle"] and x["championnat"] == 3.0 and x["proba"] >= SEUIL and x["plus25_matchs"] == [11, 12] and x["dom_marques"] == 2.17

@pytest.mark.parametrize("cotes", [OU(1.25), OU(1.10), OU(1.46), OU(1.80), OU(2.10), {}, {"over_under_1.5": {"plus": 1.3, "moins": 3.5}}])
def test_fiche_sans_cote_valable_pas_d_onglet(cotes):          # la cote vient à la fin : sous 1,26, au-dessus de 1,45 ou absente, rien
    assert "plus25" not in _fiche(A6, B6, cotes)

@pytest.mark.parametrize("A, B, tot", [(A6, B6, {"Ch": [("2026-10-01", 2)] * 40}),                     # championnat à 2,0 buts, aucun match à 3 buts
                                       (FAIBLE_A, B6, TOT),                                              # l'équipe à domicile marque et encaisse peu
                                       (FAIBLE_A, FAIBLE_B, TOT),                                        # deux équipes à peu de buts
                                       ([(0, 0)] * 6, [(0, 0)] * 6, TOT),
                                       (A6[:3], B6, TOT),                                                # 3 matchs au même lieu
                                       (A6, B6[:3], TOT),
                                       (A6, B6, {"Ch": [("2026-10-01", 5)] * 5 + [("2026-10-01", 0)] * 4})])   # 9 matchs de championnat seulement
def test_fiche_non_retenue_pas_d_onglet(A, B, tot):
    assert "plus25" not in _fiche(A, B, OU(1.40), totaux=tot)

def test_fiche_championnat_ne_regarde_pas_l_avenir():           # matchs du championnat le jour même et après : ignorés
    tot = {"Ch": [("2026-11-21", 5)] * 40 + [("2026-11-22", 5)] * 40}
    assert "plus25" not in _fiche(A6, B6, OU(1.40), totaux=tot)

def test_fiche_sans_modele_pas_d_onglet():
    assert "plus25" not in _fiche(A6, B6, OU(1.40), regle=None)

def test_fiche_les_autres_onglets_ne_changent_pas():           # avec ou sans la règle +2,5 : mêmes paris dans tous les autres onglets
    a = _fiche(A6, B6, {**OU(1.40), "1x2": {"1": 1.4, "N": 4.0, "2": 7.0}})
    b = _fiche(A6, B6, {**OU(1.40), "1x2": {"1": 1.4, "N": 4.0, "2": 7.0}}, regle=None)
    assert "plus25" in a and "plus25" not in b and {k: a[k] for k in a if k != "plus25"} == b

# ---------------------------------------------------------------- page, gel des sélections, page web
def _flux(tmp_path, matchs):
    dossier = tmp_path / "flux"; dossier.mkdir()
    with gzip.open(str(dossier / "2026-11-21.json.gz"), "wt", encoding="utf-8") as f: json.dump({x["match_id"]: x for x in matchs}, f)
    return str(dossier)

def test_page_porte_l_etude_et_le_match(tmp_path):
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(v, "totaux_championnats", return_value=TOT):
        d = v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, [_x(A6, B6, OU(1.40))]), cfg={"cote_min": 1.26, "sans_regles": True})
    assert d["regle_plus25"]["regle"]["marche"] == "total_plus_2.5" and [m["match_id"] for m in d["matchs"] if m.get("plus25")] == ["t1"]

def test_selection_plus25_gelee_avant_le_match(tmp_path):
    j = str(tmp_path / "sel.jsonl")
    m1 = {"match_id": "m1", "date": "2026-11-20", "coup_d_envoi_utc": "2026-11-20T18:00:00Z", "statut": "a_venir", "domicile": "A", "exterieur": "B", "paris": {}, "plus25": {"pari": {"marche": "total_plus_2.5", "cote": 1.4, "taux": 0.8, "verdict": "TIENT"}}}
    m2 = {**m1, "match_id": "m2", "plus25": None}
    d = {"genere_le": "2026-11-20T10:00:00Z", "matchs": [m1, m2]}
    v.geler_selections(d, chemin=j)
    assert [r["match_id"] for r in v.lire_journal(j) if r["selection"] == "plus25"] == ["m1"] and v.verifier_journal(j) == []
    assert v.geler_selections(d, maintenant="2026-11-20T18:30:00Z", chemin=j) == 0

def test_page_web_onglet():
    js = (pathlib.Path(v.RACINE) / "archetype_verif.js").read_text(encoding="utf-8")
    assert '["plus25", "+2,5 buts"]' in js and "m.plus25 ? [m.plus25.pari]" in js and '"Onglet +2,5 buts"' in js and "noteRegle25(d)" in js
    assert '["plus15", "+1,5 buts"]' in js                                    # l'onglet +1,5 reste en place
    assert "r.seuil_proba" in js and "x.proba" in js and "x.plus25_matchs" in js
