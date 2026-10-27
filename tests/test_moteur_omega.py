"""Tests du moteur omega : 3 cas qui passent et 3 cas qui échouent par règle, plus les contrôles numériques du cahier des charges."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from moteur_omega import coeur, donnees as D, marches as M, modele as MO, suivi

PARAMS = {"global_dom": 1.5, "global_ext": 1.2, "forme": "moyenne", "fenetre": None, "m_equipe": 3.9, "m_ligue": 2000.0, "rho": -0.04,
          "calibration": {}, "selection": {"cote_min": 1.39, "seuil": 0.62, "exiger_accord_cote": True, "exiger_resistance": False, "exiger_stabilite": False},
          "version": "test"}


def _equipe(lieu_dom: bool, marques: list[int], encaisses: list[int], debut: int = 1) -> list[dict]:
    return [{"date": f"2026-09-{debut + 2 * k:02d}", "domicile": lieu_dom, "buts_marques": g, "buts_encaisses": c}
            for k, (g, c) in enumerate(zip(marques, encaisses))]


def _match(dm, dc, em, ec, jour="2026-10-20", cotes=None, h=None, a=None, ko="2026-10-20T18:00:00Z", mid="m1"):
    return {"id": mid, "match_id": mid, "jour": jour, "ligue": "test", "competition": "Test : Ligue", "domicile": "Alpha", "exterieur": "Beta",
            "dom_matchs": _equipe(True, dm, dc), "ext_matchs": _equipe(False, em, ec), "cotes": cotes or {}, "h": h, "a": a,
            "coup_d_envoi_utc": ko}


# --- Règle des buts entiers (Patrick : « Plus de 1,5 » = au moins 2 buts, pas de demi-buts) ----------------------
@pytest.mark.parametrize("x,y", [(1, 1), (2, 0), (1.5, 1)])
def test_plus_1_5_tient_en_buts_entiers(x, y):
    assert M.tient_en_buts_entiers(M.test_du_marche("over_under_1.5", "plus"), x, y)


@pytest.mark.parametrize("x,y", [(1, 0), (1.5, 0), (0.5, 0.5)])
def test_plus_1_5_ne_tient_pas_si_un_score_entier_possible_perd(x, y):
    assert not M.tient_en_buts_entiers(M.test_du_marche("over_under_1.5", "plus"), x, y)


@pytest.mark.parametrize("x,y,ok", [(1, 1, True), (1, 0.5, True), (0, 2, True), (1.5, 1, False), (2, 1, False), (2.5, 0, False)])
def test_moins_2_5_veut_dire_au_plus_2_buts(x, y, ok):
    assert M.tient_en_buts_entiers(M.test_du_marche("over_under_2.5", "moins"), x, y) is ok


# --- Sens défavorable (scénario propre au marché) -----------------------------------------------------------------
@pytest.mark.parametrize("cle,sens", [(("over_under_1.5", "plus"), ("bas", "bas")), (("over_under_2.5", "moins"), ("haut", "haut")),
                                      (("1x2", "1"), ("bas", "haut")), (("1x2", "2"), ("haut", "bas")),
                                      (("over_under_domicile_0.5", "plus"), ("bas", "neutre")), (("1x2", "N"), (None, None))])
def test_sens_defavorable(cle, sens):
    assert coeur.sens_defavorable(cle) == sens


# --- Scénario contradictoire : valeurs réelles des échantillons, (attaque + défense adverse) / 2 ---------------------
def _series(dm, dc, em, ec):
    return {"dom_marques": dm, "dom_encaisses": dc, "ext_marques": em, "ext_encaisses": ec}


def test_coins_utilisent_les_extremes_observes():
    c = coeur.coins(_series([2, 3, 1, 4], [0, 1, 2, 1], [1, 0, 2, 1], [3, 1, 2, 2]))
    assert c == {"dom_bas": (1 + 1) / 2, "dom_haut": (4 + 3) / 2, "ext_bas": (0 + 0) / 2, "ext_haut": (2 + 2) / 2}


@pytest.mark.parametrize("s", [_series([2, 3, 2, 4], [1, 1, 2, 1], [1, 2, 2, 1], [2, 3, 2, 2]),
                               _series([3, 3, 2, 4], [1, 2, 1, 1], [1, 1, 2, 2], [2, 2, 3, 2]),
                               _series([2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2])])
def test_plus_1_5_resiste(s):
    assert coeur.scenario_contradictoire(("over_under_1.5", "plus"), coeur.coins(s))["statut"] == "RESISTE"


@pytest.mark.parametrize("s", [_series([0, 3, 2, 4], [1, 1, 2, 1], [1, 2, 2, 1], [0, 3, 2, 2]),
                               _series([1, 1, 1, 1], [0, 0, 0, 0], [1, 1, 1, 1], [1, 1, 1, 1]),
                               _series([2, 2, 2, 2], [0, 1, 1, 1], [0, 1, 1, 1], [1, 1, 1, 1])])
def test_plus_1_5_fragile(s):
    r = coeur.scenario_contradictoire(("over_under_1.5", "plus"), coeur.coins(s))
    assert r["statut"] == "FRAGILE" and r["dom"] + r["ext"] < 2.5


def test_victoire_domicile_utilise_attaque_min_dom_et_attaque_max_ext():
    s = _series([3, 3, 4, 4], [0, 0, 1, 0], [0, 1, 0, 0], [2, 3, 3, 4])
    r = coeur.scenario_contradictoire(("1x2", "1"), coeur.coins(s))
    assert (r["dom"], r["ext"]) == ((3 + 2) / 2, (1 + 1) / 2) and r["statut"] == "RESISTE"


# --- Séries au même lieu, anti-fuite --------------------------------------------------------------------------------
def test_serie_lieu_exclut_jour_du_match_autre_lieu_et_futur():
    ms = _equipe(True, [1, 2, 3], [0, 0, 0]) + _equipe(False, [9, 9], [9, 9]) + \
        [{"date": "2026-10-20", "domicile": True, "buts_marques": 7, "buts_encaisses": 7},
         {"date": "2026-10-25", "domicile": True, "buts_marques": 8, "buts_encaisses": 8}]
    assert D.serie_lieu(ms, True, "2026-10-20", None) == ([1, 2, 3], [0, 0, 0])
    assert D.serie_lieu(ms, True, "2026-10-20", 2) == ([2, 3], [0, 0])


def test_moins_de_4_matchs_exclu():
    m = _match([1, 2, 1], [0, 1, 1], [1, 0, 2, 1], [1, 1, 2, 0])
    a = coeur.analyser(m, D.References(), PARAMS)
    assert a["statut"] == "exclu"


# --- Modèle : distribution, marchés, contrôles du cahier des charges ----------------------------------------------
@pytest.mark.parametrize("la,lb,rho", [(1.4, 1.1, -0.05), (0.3, 2.8, 0.0), (3.5, 0.4, 0.08)])
def test_distribution_normalisee_et_positive(la, lb, rho):
    g = MO.grilles(np.array([la]), np.array([lb]), rho)[0]
    assert (g >= 0).all() and abs(g.sum() - 1) < 1e-12
    p = MO.probas(g[None], [("1x2", "1"), ("1x2", "N"), ("1x2", "2"), ("double_chance", "1N"), ("double_chance", "N2"), ("double_chance", "12")])[0]
    assert abs(p[:3].sum() - 1) < 1e-12 and abs(p[3:].sum() - 2) < 1e-12
    q = MO.probas(g[None], [("over_under_2.5", "plus"), ("over_under_2.5", "moins")])[0]
    assert abs(q.sum() - 1) < 1e-12


def test_isotone_croissante():
    xs, ys = MO.isotone(np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]), np.array([0, 1, 0, 1, 1, 1], float))
    assert all(b >= a for a, b in zip(ys, ys[1:])) and xs == sorted(xs)


def test_tous_les_marches_du_catalogue_sont_lus():
    for c in M.catalogue():
        assert M.test_du_marche(*c) is not None, c
    for exclu in [("over_under_5.5", "plus"), ("score_exact", "1-0"), ("pair_impair", "pair"), ("handicap_-2.5", "domicile")]:
        assert M.test_du_marche(*exclu) is None


# --- Probabilité de la cote (marge retirée) ------------------------------------------------------------------------
def test_proba_cote_normalisee():
    cotes = {"1x2": {"1": 2.0, "N": 3.4, "2": 3.8}, "over_under_2.5": {"plus": 1.8, "moins": 1.95},
             "double_chance": {"1N": 1.25, "N2": 1.75, "12": 1.3}}
    p1 = [coeur.proba_cote(cotes, ("1x2", s)) for s in ("1", "N", "2")]
    assert abs(sum(p1) - 1) < 1e-12
    assert abs(coeur.proba_cote(cotes, ("over_under_2.5", "plus")) + coeur.proba_cote(cotes, ("over_under_2.5", "moins")) - 1) < 1e-12
    assert abs(sum(coeur.proba_cote(cotes, ("double_chance", s)) for s in ("1N", "N2", "12")) - 2) < 1e-12


@pytest.mark.parametrize("cotes,cle", [({"1x2": {"1": 2.0, "N": 3.4}}, ("1x2", "1")), ({"over_under_2.5": {"plus": 1.8}}, ("over_under_2.5", "plus")),
                                       ({}, ("btts", "Oui"))])
def test_proba_cote_incomplete_rien_devine(cotes, cle):
    assert coeur.proba_cote(cotes, cle) is None


# --- Règle de sélection --------------------------------------------------------------------------------------------
def _ligne(**kw):
    l = {"cle": ["over_under_1.5", "plus"], "marche": "Plus de 1,5 buts", "p": 0.70, "p_cote": 0.65, "p_retenue": 0.65, "p_min": 0.66,
         "cote": 1.45, "resistance": "FRAGILE"}
    l.update(kw)
    return l


@pytest.mark.parametrize("kw", [{}, {"cote": 1.39, "p_cote": 0.66}, {"p": 0.62, "p_cote": 0.62}])
def test_retenu(kw):
    assert coeur.retenu(_ligne(**kw), PARAMS["selection"])[0]


@pytest.mark.parametrize("kw", [{"cote": 1.38}, {"cote": 1.25, "p_cote": 0.76}, {"p": 0.61}, {"p_cote": 0.60}, {"cote": None}, {"p_cote": None}])
def test_non_retenu(kw):
    assert not coeur.retenu(_ligne(**kw), PARAMS["selection"])[0]


def test_filtres_resistance_et_stabilite_si_actives():
    sel = {**PARAMS["selection"], "exiger_resistance": True, "exiger_stabilite": True}
    assert not coeur.retenu(_ligne(), sel)[0]
    assert not coeur.retenu(_ligne(resistance="RESISTE", p_min=0.60), sel)[0]
    assert coeur.retenu(_ligne(resistance="RESISTE"), sel)[0]


def test_jamais_de_cote_sous_1_39():
    """Ordre de Patrick (27/10/2026) : omega ne propose que des cotes de 1,39 et plus, même très probables."""
    for c in (1.10, 1.25, 1.30, 1.38):
        assert not coeur.retenu(_ligne(cote=c, p=0.95, p_cote=0.90), PARAMS["selection"])[0]
    assert coeur.COTE_MIN == 1.39


def test_meme_evenement_garde_une_seule_fois():
    a = {"statut": "analyse", "marches": [_ligne(cle=["double_chance", "1N"], marche="Domicile ne perd pas", p=0.72, p_retenue=0.68, cote=1.40),
                                          _ligne(cle=["handicap_0.5", "domicile"], marche="Handicap +0,5 domicile", p=0.72, p_retenue=0.68, cote=1.43),
                                          _ligne(cle=["over_under_1.5", "plus"], p=0.71, p_retenue=0.66)]}
    s = coeur.selectionner(a, PARAMS["selection"])
    assert s["principal"]["marche"] == "Handicap +0,5 domicile"          # même probabilité : la meilleure cote est gardée
    assert [x["marche"] for x in s["autres"]] == ["Plus de 1,5 buts"]


# --- Analyse complète et suivi (gel avant le coup d'envoi, ajout seul) -------------------------------------------
COTES = {"1x2": {"1": 1.55, "N": 4.0, "2": 6.0}, "double_chance": {"1N": 1.12, "N2": 2.4, "12": 1.27},
         "over_under_1.5": {"plus": 1.42, "moins": 2.7}, "over_under_2.5": {"plus": 1.9, "moins": 1.85}}


def test_analyse_complete_et_sorties_obligatoires():
    m = _match([2, 3, 1, 2, 3], [1, 0, 1, 2, 1], [1, 0, 1, 2, 0], [2, 3, 1, 2, 2], cotes=COTES)
    a = coeur.analyser(m, D.References(), PARAMS)
    assert a["statut"] == "analyse" and set(a["croisements"]) >= {"attaque_dom_x_attaque_ext", "defense_dom_x_defense_ext",
                                                                  "attaque_dom_x_defense_ext", "attaque_ext_x_defense_dom", "convergence"}
    for l in a["marches"]:
        assert 0 <= l["p"] <= 1 and l["resistance"] in ("RESISTE", "FRAGILE") and l["p_min"] <= l["p"] + 1e-12 <= l["p_max"] + 2e-12


def test_gel_avant_coup_d_envoi_seulement(tmp_path):
    j = tmp_path / "journal.jsonl"
    avant = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    m = _match([2, 3, 1, 2, 3], [1, 0, 1, 2, 1], [1, 0, 1, 2, 0], [2, 3, 1, 2, 2], cotes=COTES)
    assert suivi.geler(avant, j, [m], D.References(), PARAMS) == 1
    assert suivi.geler(avant, j, [m], D.References(), PARAMS) == 0            # rien n'a changé : pas de nouvelle ligne
    apres = datetime(2026, 10, 20, 19, tzinfo=timezone.utc)
    m2 = dict(m, cotes={**COTES, "over_under_1.5": {"plus": 1.45, "moins": 2.6}})
    assert suivi.geler(apres, j, [m2], D.References(), PARAMS) == 0          # coup d'envoi passé : jamais de pronostic
    lignes = [json.loads(x) for x in j.read_text().splitlines()]
    assert len(lignes) == 1 and lignes[0]["type"] == "pronostic"


def test_resultat_regle_sur_dernier_gel_avant_le_match(tmp_path):
    j = tmp_path / "journal.jsonl"
    m = _match([2, 3, 1, 2, 3], [1, 0, 1, 2, 1], [1, 0, 1, 2, 0], [2, 3, 1, 2, 2], cotes=COTES)
    suivi.geler(datetime(2026, 10, 20, 12, tzinfo=timezone.utc), j, [m], D.References(), PARAMS)
    joue = dict(m, h=2, a=1)
    assert suivi.resultats(j, [joue]) == 1
    assert suivi.resultats(j, [joue]) == 0                                     # un résultat n'est écrit qu'une fois
    res = [json.loads(x) for x in j.read_text().splitlines()][-1]
    assert res["type"] == "resultat" and res["score"] == [2, 1]
    for p in res["paris"]:
        assert p["gagne"] == M.test_du_marche(*p["cle"])(2, 1)


# --- Derniers matchs affichés (même échantillon que le modèle, jamais le futur) ------------------------------------
def test_derniers_matchs_meme_echantillon_que_le_modele_du_plus_recent_au_plus_ancien():
    m = _match([2, 3, 1, 2, 3], [1, 0, 1, 2, 1], [1, 0, 1, 2, 0], [2, 3, 1, 2, 2])
    m["dom_matchs"] = m["dom_matchs"] + _equipe(False, [9], [9]) + [{"date": "2026-10-20", "domicile": True, "buts_marques": 7, "buts_encaisses": 7}]
    m["dom_matchs"][0]["adversaire"] = "Premier"
    d = D.derniers_matchs(m)
    assert [x["marques"] for x in d["dom"]] == [3, 2, 1, 3, 2]                       # 5 matchs à domicile, récent d'abord ; ni l'extérieur ni le jour J
    assert [x["marques"] for x in reversed(d["ext"])] == [1, 0, 1, 2, 0]                  # extérieur : ses 5 matchs, du plus ancien au plus récent
    assert d["dom"][-1]["adversaire"] == "Premier" and d["dom"] == sorted(d["dom"], key=lambda x: x["date"], reverse=True)
    assert [x["marques"] for x in reversed(d["dom"])] == D.serie_lieu(m["dom_matchs"], True, m["jour"], None)[0]


def test_derniers_matchs_limite_et_cas_vides():
    m = _match([1] * 8, [0] * 8, [1] * 8, [0] * 8)
    assert len(D.derniers_matchs(m, par_equipe=3)["dom"]) == 3
    assert D.derniers_matchs({"jour": "2026-10-20", "dom_matchs": None, "ext_matchs": []}) == {"dom": [], "ext": []}
    assert D.derniers_matchs(_match([1] * 5, [0] * 5, [1] * 5, [0] * 5, jour="2026-09-01"))["dom"] == []        # rien avant le jour du match


def test_fiche_gelee_contient_les_derniers_matchs(tmp_path):
    j = tmp_path / "journal.jsonl"
    m = _match([2, 3, 1, 2, 3], [1, 0, 1, 2, 1], [1, 0, 1, 2, 0], [2, 3, 1, 2, 2], cotes=COTES)
    suivi.geler(datetime(2026, 10, 20, 12, tzinfo=timezone.utc), j, [m], D.References(), PARAMS)
    f = json.loads(j.read_text().splitlines()[0])["fiche"]
    assert len(f["derniers_matchs"]["dom"]) == 5 and len(f["derniers_matchs"]["ext"]) == 5


def test_page_complete_les_anciens_gels_sans_toucher_au_journal(tmp_path):
    j, sortie = tmp_path / "journal.jsonl", tmp_path / "pronostics.json"
    m = _match([2, 3, 1, 2, 3], [1, 0, 1, 2, 1], [1, 0, 1, 2, 0], [2, 3, 1, 2, 2], cotes=COTES, ko="2026-10-20T18:00:00Z")
    suivi.geler(datetime(2026, 10, 20, 12, tzinfo=timezone.utc), j, [m], D.References(), PARAMS)
    lignes = [json.loads(x) for x in j.read_text().splitlines()]
    del lignes[0]["fiche"]["derniers_matchs"]                                   # gel ancien, avant cette fonction
    j.write_text("".join(json.dumps(x) + "\n" for x in lignes))
    avant = j.read_text()
    out = suivi.page(datetime(2026, 10, 20, 13, tzinfo=timezone.utc), j, sortie, matchs=[m])
    assert len(out["a_venir"][0]["derniers_matchs"]["dom"]) == 5
    assert j.read_text() == avant                                               # le journal gelé n'est jamais modifié
    sans = suivi.page(datetime(2026, 10, 20, 13, tzinfo=timezone.utc), j, sortie)
    assert "derniers_matchs" not in sans["a_venir"][0]                          # sans archive : rien d'inventé
