import json
from pathlib import Path

import pytest
from matrice_scenarios import page_comportement as P

PARAMS = {"seuil_btts_haut": 0.565, "seuil_btts_bas": 0.509, "seuil_secondaire": 0.6}


def _equipe(buts, domicile):
    return {"matchs": [{"date": f"2026-10-0{i + 1}", "domicile": domicile, "buts_marques": g, "buts_encaisses": c, "provisoire": False} for i, (g, c) in enumerate(buts)]}


def _match(cotes, dom=None, ext=None):
    return {"match_id": "x", "date": "2026-10-19", "heure_cameroun": "16:00", "competition": "Test", "domicile": "A", "exterieur": "B", "score_final": None,
            "cotes_betpawa": cotes, "assemblage": {"equipe_dom": _equipe(dom or [(3, 0), (2, 0), (3, 1), (2, 1)], True), "equipe_ext": _equipe(ext or [(0, 2), (0, 3), (1, 2), (0, 1)], False)}}


COTES = {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "double_chance": {"1N": 1.3, "N2": 2.5, "12": 1.2}, "btts": {"Oui": 2.0, "Non": 1.7},
         "over_under_2.5": {"plus": 1.9, "moins": 1.9}, "over_under_1.5": {"plus": 1.3, "moins": 3.4}}


def test_match_complet_ok():
    r = P.analyser_match(_match(COTES), PARAMS)
    assert r["statut"] == "OK" and 1 <= len(r["selections"]) <= 3 and r["selections"][0]["role"] == "principal"
    assert all(s["cote"] >= 1.26 for s in r["selections"]) and r["tendances"][0]["cle"] == "resultat"


def test_selections_distinctes():
    r = P.analyser_match(_match(COTES), PARAMS)
    cles = [(s["groupe"], s["choix"]) for s in r["selections"]]
    assert len(cles) == len(set(cles))


def test_historique_absent():
    m = _match(COTES)
    m["assemblage"] = {}
    assert P.analyser_match(m, PARAMS)["statut"].startswith("NON_EVALUE")


def test_cotes_absentes():
    assert P.analyser_match(_match(None), PARAMS)["statut"].startswith("NON_EVALUE")


def test_aucune_cote_assez_haute():
    assert P.analyser_match(_match({"1x2": {"1": 1.1, "N": 1.2, "2": 1.05}}), PARAMS)["statut"] == "AUCUN_MARCHE_COTE_1_26"


def test_resultat_connu_marque_gagne_perdu():
    m = _match(COTES)
    m["score_final"] = {"buts_dom": 2, "buts_ext": 0}
    assert all("gagne" in s for s in P.analyser_match(m, PARAMS)["selections"])


@pytest.mark.parametrize("g,t", [("1x2", "resultat"), ("handicap_-1.5", "resultat"), ("over_under_2.5", "buts"),
                                 ("over_under_domicile_1.5", "buts"), ("btts", "deux_marquent"), ("score_exact", None)])
def test_tendance_de(g, t):
    assert P.tendance_de(g) == t


def test_json_genere_coherent():
    f = Path(__file__).resolve().parent.parent / "data" / "comportement" / "pronostics_comportement.json"
    if not f.exists():
        pytest.skip("JSON non généré")
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d["promotion_allowed"] is False
    assert all(s["cote"] >= d["cote_min"] for m in d["matchs"] for s in m["selections"])
