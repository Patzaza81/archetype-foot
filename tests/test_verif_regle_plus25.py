"""Tests de verif_regle_plus25.py (onglet « +2,5 buts » d'Analyse Verdict, 23/11/2026) : chaque condition avec >= 3 cas qui passent et >= 3 cas qui échouent,
aucune fuite vers l'avenir, la cote seulement à la fin, et les autres onglets inchangés."""
import gzip, json, os, pathlib, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest.mock as mk
import verif_regle_plus25 as R
import verif_regle_buts as RB
import verif_pronostic as v

# valeurs qui remplissent la règle (championnat 3,0 ; écart 1,5 ; l'équipe à domicile marque 5 fois sur 5 ; l'extérieur marque 1,0)
OK = {"n_dom": 5, "n_ext": 5, "n_championnat": 40, "championnat": 3.0, "ecart_diff_buts": 1.5, "freq_dom_marque": 1.0, "ext_marques": 1.0}

# ---------------------------------------------------------------- la règle : chaque condition
@pytest.mark.parametrize("ch", [2.88, 3.0, 3.6])                     # 2,88 exactement : « au moins »
def test_championnat_assez_de_buts(ch): assert R.remplie({**OK, "championnat": ch})

@pytest.mark.parametrize("ch", [2.87, 2.5, 1.9, None])
def test_championnat_pas_assez_de_buts(ch): assert not R.remplie({**OK, "championnat": ch})

@pytest.mark.parametrize("ec", [1.09, 1.5, 3.0])
def test_ecart_de_difference_de_buts_suffisant(ec): assert R.remplie({**OK, "ecart_diff_buts": ec})

@pytest.mark.parametrize("ec", [1.08, 0.5, -1.0, None])
def test_ecart_de_difference_de_buts_insuffisant(ec): assert not R.remplie({**OK, "ecart_diff_buts": ec})

@pytest.mark.parametrize("fq", [0.6, 0.75, 1.0])
def test_domicile_marque_assez_souvent(fq): assert R.remplie({**OK, "freq_dom_marque": fq})

@pytest.mark.parametrize("fq", [0.59, 0.4, 0.0, None])
def test_domicile_ne_marque_pas_assez_souvent(fq): assert not R.remplie({**OK, "freq_dom_marque": fq})

@pytest.mark.parametrize("em", [1.33, 1.0, 0.0])
def test_exterieur_marque_peu(em): assert R.remplie({**OK, "ext_marques": em})

@pytest.mark.parametrize("em", [1.34, 1.8, 3.0, None])
def test_exterieur_marque_trop(em): assert not R.remplie({**OK, "ext_marques": em})

@pytest.mark.parametrize("nd, ne, nc", [(4, 4, 10), (5, 9, 40), (12, 12, 200)])
def test_assez_de_matchs(nd, ne, nc): assert R.remplie({**OK, "n_dom": nd, "n_ext": ne, "n_championnat": nc})

@pytest.mark.parametrize("nd, ne, nc", [(3, 8, 40), (8, 3, 40), (8, 8, 9), (0, 0, 0)])
def test_pas_assez_de_matchs(nd, ne, nc): assert not R.remplie({**OK, "n_dom": nd, "n_ext": ne, "n_championnat": nc})

def test_remplie_sans_donnees(): assert not R.remplie(None) and not R.remplie({})

def test_mesures():
    x = R.mesures([(2, 0), (1, 1), (0, 2), (3, 1)], [(1, 2)] * 4, {"buts_marques": 2.0, "buts_encaisses": 0.5}, {"buts_marques": 1.0, "buts_encaisses": 1.5}, (60, 20))
    assert x == {"n_dom": 4, "n_ext": 4, "n_championnat": 20, "championnat": 3.0, "ecart_diff_buts": 2.0, "freq_dom_marque": 0.75, "ext_marques": 1.0}

# ---------------------------------------------------------------- étude sur matchs joués : sans fuite
def _m(jour, dom, ext, gd, ge, div="T", saison="2627", ou=None):
    m = {"id": f"{jour}|{dom}|{ext}", "saison": saison, "division": div, "date": jour, "domicile": dom, "exterieur": ext, "buts_dom": gd, "buts_ext": ge, "cotes": {}}
    if ou: m["cotes"]["plus_moins_2_5_cloture"] = {"moy": [ou, 1.9]}
    return m

def _historique(n, final=(3, 1), ou=1.5):
    """A gagne 3-0 chez lui n fois, B perd 0-3 dehors n fois (championnat à 3 buts par match), puis A - B."""
    L = [_m(f"2026-09-{i + 1:02d}", "A", f"X{i}", 3, 0) for i in range(n)] + [_m(f"2026-09-{i + 1:02d}", f"Y{i}", "B", 3, 0) for i in range(n)]
    return L + [_m("2026-10-30", "A", "B", *final, ou=ou)]

def test_cas_joues_valeurs():
    c = [x for x in R.cas_joues(_historique(6)) if x["date"] == "2026-10-30"][0]
    assert c["championnat"] == 3.0 and c["ecart_diff_buts"] == 6.0 and c["freq_dom_marque"] == 1.0 and c["ext_marques"] == 0.0 and c["n_championnat"] == 12 and R.remplie(c)

@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_cas_joues_moins_de_4_matchs_au_meme_lieu(n):
    assert [x for x in R.cas_joues(_historique(n)) if x["date"] == "2026-10-30"] == []

def test_cas_joues_ne_regarde_pas_l_avenir():
    a, b = R.cas_joues(_historique(6, (0, 0)))[-1], R.cas_joues(_historique(6, (5, 5)))[-1]
    assert {k: a[k] for k in a if k not in ("total",)} == {k: b[k] for k in b if k not in ("total",)} and a["total"] != b["total"]

def test_cas_joues_le_jour_meme_ne_compte_pas():         # un match du même jour (déjà joué dans la liste) ne change pas les valeurs
    L = _historique(6); L2 = L + [_m("2026-10-30", "Z1", "Z2", 9, 9)]
    a = [x for x in R.cas_joues(L) if x["date"] == "2026-10-30"][0]; b = [x for x in R.cas_joues(L2) if x["date"] == "2026-10-30" and x["n_dom"] == 6][0]
    assert a["championnat"] == b["championnat"] and a["n_championnat"] == b["n_championnat"]

def test_calculer(tmp_path):
    f = str(tmp_path / "bloc.json.gz"); json.dump({"liste": _historique(6, (2, 1), ou=1.40)}, gzip.open(f, "wt", encoding="utf-8"))
    r = R.calculer(f)
    assert r["etude"]["matchs"] == 1 and r["etude"]["reussis"] == 1 and r["etude"]["recherche"]["matchs"] == 0 and r["etude"]["non_vus"]["matchs"] == 1 and r["etude"]["non_vus_cote_min"]["matchs"] == 1   # 30/10/2026 : après la coupure
    assert r["regle"]["championnat_min"] == 2.88 and r["regle"]["cote_min"] == 1.26

def test_table_du_depot_coherente():
    r = R.charger(); assert r is not None
    E = r["etude"]; NV = E["non_vus"]
    assert E["matchs"] == E["recherche"]["matchs"] + NV["matchs"] and NV["matchs"] >= NV["reussis"] > 0 and NV["borne_basse"] <= NV["taux"] <= NV["borne_haute"]
    assert NV["taux"] > E["tous_non_vus"]["taux"]                       # la règle fait mieux que tous les matchs de la même période jamais vue
    assert r["regle"]["coupure"] == R.COUPURE and r["regle"]["championnat_min"] == R.CHAMP_MIN and r["regle"]["ext_marques_max"] == R.EXT_MAX

# ---------------------------------------------------------------- de bout en bout : la fiche d'un match
def _x(A, B, cotes, SA=None, SB=None, jour="2026-11-21", mid="t1"):
    """A : scores de l'équipe à domicile CHEZ ELLE ; B : scores de l'équipe à l'extérieur DEHORS ; SA / SB : autres matchs de la saison (l'autre lieu)."""
    L = lambda S, dom, d0: [{"domicile": dom, "date": f"2026-{d0}-{i + 1:02d}", "saison": "2627", "buts_marques": h, "buts_encaisses": a} for i, (h, a) in enumerate(S)]
    return {"match_id": mid, "date": jour, "coup_d_envoi_utc": f"{jour}T15:00:00Z", "domicile": "A", "exterieur": "B", "competition": "Ch", "cotes_betpawa": cotes,
            "assemblage": {"saison_football_data": "2627", "equipe_dom": {"matchs": L(A, True, "10") + L(SA or [], False, "09")}, "equipe_ext": {"matchs": L(B, False, "10") + L(SB or [], True, "09")}}}
def OU(plus): return {"over_under_2.5": {"plus": plus, "moins": 2.6}}
OUI_A, OUI_B = [(3, 0)] * 6, [(1, 2)] * 6                      # A : +3 par match ; B : -1 par match, marque 1,0 dehors : écart 4,0
TOT = {"Ch": [("2026-10-01", 3)] * 40}                          # championnat à 3,0 buts par match sur 40 matchs précédents

def _fiche(A, B, cotes, regle="depot", totaux=TOT, **k):
    with mk.patch.object(R, "charger", return_value=(R.charger() if regle == "depot" else regle)), mk.patch.object(RB, "charger", return_value=None):
        return v.fiche_match(_x(A, B, cotes, **k), "2026-11-21T06:00:00Z", {"cote_min": 1.26, "sans_regles": True}, totaux)

@pytest.mark.parametrize("cote", [1.26, 1.45, 2.10])
def test_fiche_regle_remplie_avec_cote_suffisante(cote):
    f = _fiche(OUI_A, OUI_B, OU(cote)); x = f["plus25"]; p = x["pari"]
    assert p["marche"] == "total_plus_2.5" and p["cote"] == cote and p["regle"] and x["championnat"] == 3.0 and x["ecart_diff_buts"] == 4.0 and x["freq_dom_marque"] == 1.0 and x["ext_marques"] == 1.0

@pytest.mark.parametrize("cotes", [OU(1.25), OU(1.10), {}, {"over_under_1.5": {"plus": 1.3, "moins": 3.5}}])
def test_fiche_sans_cote_valable_pas_d_onglet(cotes):          # la cote vient à la fin : sous 1,26 ou absente, rien
    assert "plus25" not in _fiche(OUI_A, OUI_B, cotes)

@pytest.mark.parametrize("A, B, tot", [(OUI_A, OUI_B, {"Ch": [("2026-10-01", 2)] * 40}),        # championnat à 2,0 buts
                                       (OUI_A, [(2, 2)] * 6, TOT),                                # l'extérieur marque 2,0 dehors (et écart 3,0)
                                       ([(0, 0)] * 3 + [(3, 0)] * 3, OUI_B, TOT),                  # l'équipe à domicile n'a marqué que 3 fois sur 6 chez elle
                                       ([(1, 1)] * 6, [(1, 1)] * 6, TOT),                         # écart de différence de buts nul
                                       ([(3, 0)] * 3, OUI_B, TOT),                                # 3 matchs au même lieu
                                       (OUI_A, OUI_B, {"Ch": [("2026-10-01", 3)] * 9})])          # 9 matchs de championnat seulement
def test_fiche_regle_non_remplie_pas_d_onglet(A, B, tot):
    assert "plus25" not in _fiche(A, B, OU(1.50), totaux=tot)

def test_fiche_championnat_ne_regarde_pas_l_avenir():           # matchs du championnat le jour même et après : ignorés
    tot = {"Ch": [("2026-10-01", 2)] * 40 + [("2026-11-21", 9)] * 40 + [("2026-11-25", 9)] * 40}
    assert "plus25" not in _fiche(OUI_A, OUI_B, OU(1.50), totaux=tot)

def test_fiche_sans_etude_pas_d_onglet():
    assert "plus25" not in _fiche(OUI_A, OUI_B, OU(1.50), regle=None)

def test_fiche_les_autres_onglets_ne_changent_pas():           # avec ou sans la règle +2,5 : mêmes paris dans tous les autres onglets
    a = _fiche(OUI_A, OUI_B, {**OU(1.50), "1x2": {"1": 1.4, "N": 4.0, "2": 7.0}})
    b = _fiche(OUI_A, OUI_B, {**OU(1.50), "1x2": {"1": 1.4, "N": 4.0, "2": 7.0}}, regle=None)
    assert "plus25" in a and "plus25" not in b and {k: a[k] for k in a if k != "plus25"} == b

# ---------------------------------------------------------------- page, gel des sélections, page web
def _flux(tmp_path, matchs):
    dossier = tmp_path / "flux"; dossier.mkdir()
    with gzip.open(str(dossier / "2026-11-21.json.gz"), "wt", encoding="utf-8") as f: json.dump({x["match_id"]: x for x in matchs}, f)
    return str(dossier)

def test_page_porte_l_etude_et_le_match(tmp_path):
    with mk.patch.object(RB, "charger", return_value=None), mk.patch.object(v, "totaux_championnats", return_value=TOT):
        d = v.page_donnees(0, "2026-11-21T06:00:00Z", flux=_flux(tmp_path, [_x(OUI_A, OUI_B, OU(1.50))]), cfg={"cote_min": 1.26, "sans_regles": True})
    assert d["regle_plus25"]["regle"]["marche"] == "total_plus_2.5" and [m["match_id"] for m in d["matchs"] if m.get("plus25")] == ["t1"]

def test_selection_plus25_gelee_avant_le_match(tmp_path):
    j = str(tmp_path / "sel.jsonl")
    m1 = {"match_id": "m1", "date": "2026-11-20", "coup_d_envoi_utc": "2026-11-20T18:00:00Z", "statut": "a_venir", "domicile": "A", "exterieur": "B", "paris": {}, "plus25": {"pari": {"marche": "total_plus_2.5", "cote": 1.5, "taux": 0.8, "verdict": "TIENT"}}}
    m2 = {**m1, "match_id": "m2", "plus25": None}
    d = {"genere_le": "2026-11-20T10:00:00Z", "matchs": [m1, m2]}
    v.geler_selections(d, chemin=j)
    assert [r["match_id"] for r in v.lire_journal(j) if r["selection"] == "plus25"] == ["m1"] and v.verifier_journal(j) == []
    assert v.geler_selections(d, maintenant="2026-11-20T18:30:00Z", chemin=j) == 0

def test_page_web_onglet():
    js = (pathlib.Path(v.RACINE) / "archetype_verif.js").read_text(encoding="utf-8")
    assert '["plus25", "+2,5 buts"]' in js and "m.plus25 ? [m.plus25.pari]" in js and '"Onglet +2,5 buts"' in js and "noteRegle25(d)" in js
    assert '["plus15", "+1,5 buts"]' in js                                    # l'onglet +1,5 reste en place
