import json
from pathlib import Path

import pytest
from matrice_scenarios import page_comportement as P

PARAMS = {"seuil_btts_haut": 0.565, "seuil_btts_bas": 0.509, "seuil_secondaire": 0.6, "seuil_buts_equipe": 0.361}


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
                                 ("over_under_domicile_1.5", "dom_buts"), ("over_under_exterieur_0.5", "ext_buts"), ("cages_inviolees_exterieur", "dom_buts"), ("cages_inviolees_domicile", "ext_buts"), ("btts", "deux_marquent"), ("score_exact", None)])
def test_tendance_de(g, t):
    assert P.tendance_de(g) == t


def test_json_genere_coherent():
    f = Path(__file__).resolve().parent.parent / "data" / "comportement" / "pronostics_comportement.json"
    if not f.exists():
        pytest.skip("JSON non généré")
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d["promotion_allowed"] is False
    assert all(s["cote"] >= d["cote_min"] for m in d["matchs"] for s in m["selections"])


@pytest.mark.parametrize("g1,s1,g2,s2,egal", [
    ("over_under_domicile_0.5", "plus", "cages_inviolees_exterieur", "non", True),      # domicile marque = cage de l'extérieur violée
    ("over_under_exterieur_0.5", "moins", "cages_inviolees_domicile", "oui", True),
    ("btts", "Oui", "over_under_2.5", "plus", False),
    ("1x2", "1", "double_chance", "1N", False),
    ("1x2", "N", "handicap_3issues_0", "X", True),
    ("over_under_domicile_1.5", "plus", "over_under_exterieur_1.5", "plus", False)])
def test_evenement_equivalent(g1, s1, g2, s2, egal):
    assert (P.evenement(g1, s1) == P.evenement(g2, s2)) is egal


def test_pas_de_doublon_d_evenement_dans_un_match():
    r = P.analyser_match(_match({**COTES, "over_under_domicile_0.5": {"plus": 1.3, "moins": 3.5}, "cages_inviolees_exterieur": {"oui": 3.2, "non": 1.31}}), PARAMS)
    ev = [P.evenement(s["groupe"], s["choix"]) for s in r["selections"]]
    assert len(ev) == len(set(ev))


def test_seuil_par_tendance_bloque_les_secondaires():
    p = {**PARAMS, "seuil_secondaire": 0.0, "seuils_tendance": {k: 2.0 for k in P.TENDANCES}}
    r = P.analyser_match(_match(COTES), p)
    assert [s["role"] for s in r["selections"]] == ["principal"]


def test_seuil_par_tendance_zero_laisse_passer():
    p = {**PARAMS, "seuil_secondaire": 0.0, "seuils_tendance": {k: 0.0 for k in P.TENDANCES}}
    assert len(P.analyser_match(_match(COTES), p)["selections"]) >= 2


def test_tendance_non_nette_sans_pronostic_secondaire():
    p = {**PARAMS, "seuil_secondaire": 0.0, "seuil_buts_equipe": 2.0}      # aucune tendance d'équipe ne peut être nette
    r = P.analyser_match(_match(COTES), p)
    assert all(s["tendance"] not in ("Buts du domicile", "Buts de l'extérieur") or s["role"] == "principal" for s in r["selections"])
    assert all(t.get("nette") is False for t in r["tendances"] if t["cle"] in ("dom_buts", "ext_buts"))


# ── Intitulés pour le parieur (équipes par leur nom) ──────────────────────────
from matrice_scenarios.page_comportement import libelle_parieur as _lp


def test_libelle_parieur_cas_valides():
    assert _lp("1x2", "1", "M. Tel", "Beitar", "x") == "M. Tel gagne"
    assert _lp("double_chance", "N2", "A", "B", "x") == "B ne perd pas (N2)"
    assert _lp("handicap_-1.5", "exterieur", "M. Hollyhock", "B", "x") == "B +1,5 (handicap)"
    assert _lp("handicap_-1.5", "domicile", "M. Hollyhock", "B", "x") == "M. Hollyhock -1,5 (handicap)"
    assert _lp("handicap_3issues_2", "2", "A", "B", "x") == "B -2 (handicap 3 issues)"


def test_libelle_parieur_ne_touche_pas_au_nom_de_l_equipe():
    assert "M. Hollyhock" in _lp("handicap_1.5", "domicile", "M. Hollyhock", "B", "x")


def test_libelle_parieur_marches_sans_equipe_gardent_le_libelle_du_moteur():
    assert _lp("btts", "Oui", "A", "B", "Les deux marquent : oui") == "Les deux marquent : oui"
    assert _lp("over_under_2.5", "plus", "A", "B", "Plus de 2,5 buts") == "Plus de 2,5 buts"
    assert _lp("1x2", "inconnu", "A", "B", "défaut") == "défaut"


# ── Raison propre au pick ─────────────────────────────────────────────────────
from matrice_scenarios.page_comportement import raison_du_pick as _rp
_PROF = {"buts_attendus": (1.9, 0.8), "total_attendu": 2.7, "victoire_dom": 0.5, "nul": 0.25, "victoire_ext": 0.25, "deux_marquent": 0.52}


def test_raison_du_pick_cas_valides():
    assert _rp("over_under_2.5", "plus", _PROF, "A", "B") == "2,7 buts attendus dans le match"
    assert _rp("over_under_domicile_1.5", "plus", _PROF, "A", "B") == "A : 1,9 but attendu"
    assert _rp("cages_inviolees_exterieur", "non", _PROF, "A", "B") == "A : 1,9 but attendu"      # l'extérieur encaisse si A marque
    assert _rp("cages_inviolees_domicile", "non", _PROF, "A", "B") == "B : 0,8 but attendu"
    assert _rp("btts", "Oui", _PROF, "A", "B") == "Les deux marquent : 52 % selon le modèle"


def test_raison_du_pick_ne_contredit_jamais_le_pick():
    for g, s in (("over_under_4.5", "moins"), ("over_under_1.5", "plus")):
        txt = _rp(g, s, _PROF, "A", "B")
        assert "ouvert" not in txt and "fermé" not in txt


def test_raison_du_pick_resultats_et_handicaps_donnent_les_trois_issues():
    assert _rp("handicap_1.5", "domicile", _PROF, "A", "B") == "A 50 % · nul 25 % · B 25 %"
    assert _rp("double_chance", "12", _PROF, "A", "B") == "A 50 % · nul 25 % · B 25 %"
    assert _rp("handicap_3issues_2", "1", _PROF, "A", "B") == "A 50 % · nul 25 % · B 25 %"
