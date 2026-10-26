"""Sélection provisoire alpha (26/10/2026) : 8 marchés, niveaux, cote figée, exception multigoals, gel, résultats, page."""
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from alpha_serie import selection_provisoire as SP

RACINE = Path(__file__).resolve().parent.parent
HUIT = {"multigoals|1-4": "normal", "double_chance|12": "normal", "over_under_1.5|plus": "normal", "handicap_1.5|domicile": "normal",
        "over_under_4.5|moins": "normal", "over_under_domicile_0.5|plus": "normal", "over_under_exterieur_2.5|moins": "normal",
        "over_under_domicile_2.5|moins": "maximal"}
PAIRES_OK = ([[1, 1], [2, 0], [1, 2], [0, 1]], [[1, 0], [0, 1], [2, 1], [1, 1]])     # aucun total 0-1 côté buts élevés : peu d'échecs pour « dom ≤ 2 »


def analyse(*cles, off=None, de=None):
    o, d = PAIRES_OK if off is None else (off, de)
    return {"statut": "analyse", "onglets": {"buts": [{"cle": list(c)} for c in cles if c[0] in ("multigoals",) or c[0].startswith("over_under_") and "_" not in c[0][11:] or c[0] == "btts"],
                                             "equipes": [{"cle": list(c)} for c in cles if not (c[0] in ("multigoals",) or c[0].startswith("over_under_") and "_" not in c[0][11:] or c[0] == "btts")]},
            "scenarios_offensifs": o, "scenarios_defensifs": d}


def ids(sel):
    return {s["regle"] for s in sel}


def test_exactement_les_huit_marches_et_leurs_niveaux():
    r = SP.charger_regles()
    assert {x["id"]: x["niveau"] for x in r} == HUIT
    assert all(x["cote_min"] == 1.25 for x in r)
    assert {x["id"] for x in r if x["sans_cote"]} == {"multigoals|1-4"}
    assert [x["echecs_max"] for x in r if x["niveau"] == "maximal"] == [1]
    d = json.loads(SP.REGLES.read_text(encoding="utf-8"))
    assert "576577e" in d["source"] and "provisoire" in d["statut"]


@pytest.mark.parametrize("cote,attendu", [(1.25, True), (1.30, True), (2.10, True), (1.24, False), (1.0, False), (None, False)])
def test_filtre_de_cote_3_passent_3_echouent(cote, attendu):
    cotes = {} if cote is None else {"double_chance": {"12": cote}}
    assert ("double_chance|12" in ids(SP.selections(analyse(("double_chance", "12")), cotes))) is attendu


def test_chacun_des_huit_passe_avec_une_cote_valide():
    cotes = {"double_chance": {"12": 1.3}, "over_under_1.5": {"plus": 1.3}, "handicap_1.5": {"domicile": 1.3}, "over_under_4.5": {"moins": 1.3},
             "over_under_domicile_0.5": {"plus": 1.3}, "over_under_exterieur_2.5": {"moins": 1.3}, "over_under_domicile_2.5": {"moins": 1.3}}
    r = analyse(("multigoals", "1-4"), ("double_chance", "12"), ("over_under_1.5", "plus"), ("handicap_1.5", "domicile"), ("over_under_4.5", "moins"),
                ("over_under_domicile_0.5", "plus"), ("over_under_exterieur_2.5", "moins"), ("over_under_domicile_2.5", "moins"))
    assert ids(SP.selections(r, cotes)) == set(HUIT)
    assert ids(SP.selections(r, {})) == {"multigoals|1-4"}                    # sans aucune cote : seul le multigoal reste


def test_multigoals_sans_cote_mais_jamais_sans_alpha():
    s = SP.selections(analyse(("multigoals", "1-4")), {})
    assert [x["cote"] for x in s] == [None] and s[0]["niveau"] == "normal"
    assert SP.selections(analyse(("multigoals", "1-3")), {}) == []             # autre plage : exclue
    assert SP.selections(analyse(("double_chance", "12")), {}) == []           # non publié par alpha : rien
    assert SP.selections({"statut": "exclu"}, {"double_chance": {"12": 1.4}}) == []


@pytest.mark.parametrize("cle", [("1x2", "1"), ("1x2", "2"), ("double_chance", "1N"), ("double_chance", "N2"), ("over_under_3.5", "moins"),
                                 ("over_under_2.5", "plus"), ("btts", "Oui"), ("btts", "Non"), ("handicap_-1.5", "exterieur"), ("multigoals", "2-5"),
                                 ("over_under_exterieur_0.5", "plus"), ("over_under_exterieur_1.5", "moins")])
def test_aucun_marche_exclu_ne_reapparait(cle):
    cotes = {cle[0]: {cle[1]: 1.5}}
    assert SP.selections(analyse(cle), cotes) == []


def test_niveau_maximal_domicile_moins_de_2_5_3_passent_3_echouent():
    cotes = {"over_under_domicile_2.5": {"moins": 1.4}}
    cle = ("over_under_domicile_2.5", "moins")
    # échec = l'équipe qui reçoit a marqué 3+ à domicile (off[i][0]) ou l'équipe qui se déplace a encaissé 3+ à l'extérieur (de[i][0])
    cas_ok = [([[1, 0], [2, 1], [0, 0]], [[1, 1], [2, 0], [0, 2]]),          # 0 échec
              ([[3, 0], [2, 1], [0, 0]], [[1, 1], [2, 0], [0, 2]]),          # 1 échec (domicile 3 buts)
              ([[1, 0], [2, 1], [0, 0]], [[4, 1], [2, 0], [0, 2]])]          # 1 échec (extérieur a encaissé 4)
    cas_ko = [([[3, 0], [2, 1], [0, 0]], [[3, 1], [2, 0], [0, 2]]),          # 2 échecs
              ([[3, 0], [4, 1], [5, 0]], [[1, 1], [2, 0], [0, 2]]),          # 3 échecs
              ([], [])]                                                       # paires absentes
    for off, de in cas_ok:
        assert ids(SP.selections(analyse(cle, off=off, de=de), cotes)) == {"over_under_domicile_2.5|moins"}
    for off, de in cas_ko:
        assert SP.selections(analyse(cle, off=off, de=de), cotes) == []


def test_echecs_definition_plus_de_1_5():
    p = SP.predicat(("over_under_1.5", "plus"))
    # match domicile : (off[0] marqués, de[1] encaissés) ; match extérieur : (de[0], off[1])
    assert SP.echecs([[1, 0], [2, 3]], [[0, 0], [1, 1]], p) == 2      # domicile 1+0 = 1 (échec), 2+1 ; extérieur 0+0 (échec), 1+3
    assert SP.echecs([], [], p) is None


def test_equivalent_domicile_marque_publie_comme_cage_inviolee():
    r = analyse(("cages_inviolees_exterieur", "non"))
    s = SP.selections(r, {"over_under_domicile_0.5": {"plus": 1.31}, "cages_inviolees_exterieur": {"non": 1.2}})
    assert ids(s) == {"over_under_domicile_0.5|plus"} and s[0]["cote"] == 1.31   # même événement, cote prise dans l'ordre des clés


def _m(mid, ko, score=None, cote=1.3):
    from alpha_serie import coeur
    return {"match_id": mid, "coup_d_envoi_utc": ko, "date": ko[:10], "heure_cameroun": "20:00", "competition": "Test", "domicile": "A", "exterieur": "B",
            "assemblage": {}, "cotes_betpawa": {"double_chance": {"12": cote}}, "run": {"pris_le": "2026-10-26T00:10:00Z"}, "score_final": score}


def test_gel_avant_match_sans_doublon_resultat_et_rendement(tmp_path, monkeypatch):
    j = tmp_path / "j.jsonl"
    r_admis = analyse(("double_chance", "12"), ("multigoals", "1-4"))
    monkeypatch.setattr(SP.coeur, "analyser_match", lambda *a, **k: r_admis)
    t = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    matchs = [_m("m1", "2026-10-26T18:00:00Z"), _m("m2", "2026-10-26T11:00:00Z"), _m("m3", "2026-10-27T18:00:00Z", score={"buts_dom": 1, "buts_ext": 1})]
    assert SP.geler(matchs, t, j) == 2                                       # m1 : 2 marchés ; m2 déjà commencé ; m3 a déjà un score
    assert SP.geler(matchs, t, j) == 0                                       # jamais regelé
    lignes = [json.loads(l) for l in j.read_text().splitlines()]
    dc = next(l for l in lignes if l["regle"] == "double_chance|12")
    assert dc["cote"] == 1.3 and dc["cotes_prises_le"] == "2026-10-26T00:10:00Z" and dc["gele_le"] < dc["coup_d_envoi_utc"]
    fini = [_m("m1", "2026-10-26T18:00:00Z", score={"buts_dom": 1, "buts_ext": 1})]
    assert SP.regler(fini, j) == 2 and SP.regler(fini, j) == 0
    b = SP.bilan(j)
    assert b["par_marche"]["double_chance|12"] == {**b["par_marche"]["double_chance|12"], "regles": 1, "gagnes": 0, "perdus": 1, "taux": 0.0, "net": -1.0, "rendement": -1.0, "paris_avec_cote": 1}
    assert b["par_marche"]["multigoals|1-4"]["gagnes"] == 1 and b["par_marche"]["multigoals|1-4"]["rendement"] is None   # pas de cote : pas de rendement inventé
    d = SP.page(j, tmp_path / "p.json", maintenant=t)
    assert {p["regle"] for p in d["pronostics"]} == {"double_chance|12", "multigoals|1-4"}
    assert all(set(p) >= {"marche", "cote", "heure", "domicile", "exterieur", "resultat"} for p in d["pronostics"])


def test_branchee_dans_le_pipeline_nocturne_sans_le_bloquer():
    src = (RACINE / "alpha_serie" / "suivi.py").read_text(encoding="utf-8")
    bloc = src[src.index("def pipeline"):]
    assert "selection_provisoire.pipeline(matchs)" in bloc and 'sortie["selection_provisoire"] = {"erreur": repr(e)}' in bloc
    mod = (RACINE / "alpha_serie" / "selection_provisoire.py").read_text(encoding="utf-8")
    assert '"journal.jsonl"' not in mod and "tickets_journal" not in mod      # n'écrit que dans ses propres fichiers
    assert SP.JOURNAL.name == "selection_provisoire_journal.jsonl" and SP.PAGE.name == "selection_provisoire_page.json"


def test_donnees_publiees_respectent_les_regles():
    d = json.loads((RACINE / "data" / "alpha_serie" / "selection_provisoire_page.json").read_text(encoding="utf-8"))
    assert {p["regle"] for p in d["pronostics"]} <= set(HUIT)
    for p in d["pronostics"]:
        if p["regle"] != "multigoals|1-4":
            assert p["cote"] is not None and p["cote"] >= 1.25
        assert p["heure"] and p["domicile"] and p["exterieur"] and p["marche"]


def test_page_et_navigation():
    for f in ("pronostics_comportement.html", "tickets_alpha.html", "indice_alpha.html", "selection_alpha.html"):
        assert '<a href="selection_alpha.html"' in (RACINE / f).read_text(encoding="utf-8"), f
    html = (RACINE / "selection_alpha.html").read_text(encoding="utf-8")
    assert "af-selection-alpha.js" in html and "ne garantissent" in html
    js = (RACINE / "af-selection-alpha.js").read_text(encoding="utf-8")
    assert "selection_provisoire_page.json" in js and "innerHTML" in js
    for champ in ("p.domicile", "p.exterieur", "p.marche", "p.competition", "r.nom"):
        assert f"esc({champ})" in js                                          # tout texte venant des données est échappé
    try:
        subprocess.run(["node", "--check", str(RACINE / "af-selection-alpha.js")], check=True, capture_output=True, timeout=30)
    except FileNotFoundError:
        pytest.skip("node absent")
