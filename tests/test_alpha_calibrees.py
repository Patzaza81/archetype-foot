"""Tests des sélections calibrées de l'alpha en production (alpha_serie/calibrees.py, branchées le 24/10/2026)."""
import json
from datetime import datetime, timezone

from alpha_serie import calibrees as K
from alpha_serie import suivi


def equipe(dom, marques, encaisses):
    return {"matchs": [{"date": f"2026-09-{1 + i:02d}", "domicile": dom, "buts_marques": m, "buts_encaisses": e, "provisoire": False}
                       for i, (m, e) in enumerate(zip(marques, encaisses))]}


FORT_DOM = equipe(True, [3, 2, 3, 2, 3, 2], [0, 0, 1, 0, 0, 1])      # domicile qui marque beaucoup, encaisse peu
FAIBLE_EXT = equipe(False, [0, 0, 1, 0, 0, 0], [3, 2, 2, 3, 2, 3])  # extérieur qui marque peu, encaisse beaucoup
JOUR = "2026-10-20"


def regle(marche, n_min=4, d=0.0, h=0.5, cat="toutes", statut="exploitable", q=0.01):
    return {"marche": marche, "n_min": n_min, "marge_defavorable": d, "marge_habituelle": h, "categorie": cat, "statut": statut, "q_final": q,
            "test_final": {"paris": 100, "reussite": 0.8, "reussite_sans_filtre": 0.7}}


def test_charger_regles_exploitables_seulement(tmp_path):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"regles": {"a": regle("Victoire domicile", q=0.03), "b": regle("Victoire extérieur", statut="prometteur"),
                                        "c": regle("Plus de 1,5 buts", q=0.001), "d": regle("Marché inconnu")}}), encoding="utf-8")
    r = K.charger_regles(f)
    assert [x["marche"] for x in r] == ["Plus de 1,5 buts", "Victoire domicile"]      # prometteur et marché inconnu écartés, tri par preuve


def test_regles_reelles_chargees():
    r = K.charger_regles()
    assert r and all(x["statut"] == "exploitable" for x in r)


def test_regle_qui_passe():
    s = K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {"1x2": {"1": 1.40}}, [regle("Victoire domicile")])
    assert len(s) == 1 and s[0]["cote"] == 1.40 and not s[0]["cote_a_lire"] and s[0]["valeur"] == 0.8
    s = K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {}, [regle("Victoire domicile")])
    assert len(s) == 1 and s[0]["cote_a_lire"]                                        # cote absente : proposée, « cote à lire »
    s = K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {"1x2": {"1": 1.60}}, [regle("Victoire domicile", cat="B")])
    assert len(s) == 1                                                                # règle de grosse cote, cote 1,60 : passe


def test_regle_qui_ne_passe_pas():
    assert K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {"1x2": {"1": 1.10}}, [regle("Victoire domicile")]) == []   # cote sous 1,25
    assert K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {"1x2": {"1": 1.40}}, [regle("Victoire domicile", n_min=7)]) == []   # 6 matchs seulement
    assert K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {"1x2": {"1": 1.40}}, [regle("Victoire extérieur")]) == []   # marge non atteinte
    assert K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {"1x2": {"1": 1.30}}, [regle("Victoire domicile", cat="B")]) == []   # cote A, règle B


def test_meme_evenement_propose_une_seule_fois():
    s = K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {}, [regle("Victoire domicile"), regle("Handicap -0,5 domicile")])
    assert len(s) == 1


def test_echantillon_insuffisant_et_sans_fuite():
    court = equipe(True, [3, 2, 3], [0, 0, 1])
    assert K.selections(court, FAIBLE_EXT, JOUR, {}, [regle("Victoire domicile")]) == []
    assert K.selections(FORT_DOM, FAIBLE_EXT, "2026-09-04", {}, [regle("Victoire domicile")]) == []   # seuls les 3 matchs avant le 04/09 comptent


def test_combo_lu_et_regle():
    s = K.selections(FORT_DOM, FAIBLE_EXT, JOUR, {}, [regle("Domicile ne perd pas + moins de 4,5 buts", h=0.0)])
    assert len(s) == 1 and s[0]["famille"] == "combos" and s[0]["cote_a_lire"]
    assert suivi._gagne(s[0]["cle"], 2, 1) is True and suivi._gagne(s[0]["cle"], 3, 2) is False and suivi._gagne(s[0]["cle"], 0, 1) is False


def test_onglet_calibrees_gele_et_regle(tmp_path, monkeypatch):
    monkeypatch.setattr(suivi, "_REGLES", [regle("Victoire domicile")])
    m = {"match_id": "x1", "date": JOUR, "coup_d_envoi_utc": "2026-10-20T18:00:00Z", "heure_cameroun": "19:00", "competition": "Test",
         "domicile": "A", "exterieur": "B", "assemblage": {"equipe_dom": FORT_DOM, "equipe_ext": FAIBLE_EXT},
         "cotes_betpawa": {"1x2": {"1": 1.40}}, "score_final": None}
    j = tmp_path / "journal.jsonl"
    assert suivi.geler(maintenant=datetime(2026, 10, 20, 12, tzinfo=timezone.utc), journal=j, matchs=[m]) == 1
    gele = json.loads(j.read_text().splitlines()[0])
    assert [s["marche"] for s in gele["onglets"]["calibrees"]] == ["Victoire domicile"]
    m["score_final"] = {"buts_dom": 2, "buts_ext": 0}
    assert suivi.resultats(journal=j, matchs=[m]) == 1
    b = suivi.bilan(journal=j, ecrire=False)
    assert b["onglets"]["calibrees"]["cas"] == 1 and b["onglets"]["calibrees"]["reussite"] == 1.0


def test_lecture_commune_a_la_campagne():
    src = (suivi.ROOT / "alpha_serie" / "campagne.py").read_text(encoding="utf-8")
    assert "R.parts_marche(" in src and "R.parts_marche(" in (suivi.ROOT / "alpha_serie" / "calibrees.py").read_text(encoding="utf-8")


def test_page_affiche_l_onglet_calibres():
    js = (suivi.ROOT / "archetype_comportement.js").read_text(encoding="utf-8")
    assert '["calibrees", "Calibrés"]' in js and "aucune rentabilité n'est démontrée" in js


# --- Affichage du 24/10/2026 : matchs au même lieu, buts par match, explication factuelle, plus de marchés exclus -----
def test_historique_lieu_tous_les_matchs_avant_le_jour():
    eq = {"matchs": [{"date": "2026-09-01", "domicile": True, "adversaire": "X", "buts_marques": 2, "buts_encaisses": 0},
                     {"date": "2026-09-08", "domicile": False, "adversaire": "Y", "buts_marques": 1, "buts_encaisses": 1},
                     {"date": "2026-09-15", "domicile": True, "adversaire": "Z", "buts_marques": 0, "buts_encaisses": 3},
                     {"date": "2026-10-20", "domicile": True, "adversaire": "W", "buts_marques": 5, "buts_encaisses": 0}]}
    h = suivi.historique_lieu(eq, True, "2026-10-20")
    assert [x["adversaire"] for x in h] == ["Z", "X"]                                   # domicile seulement, avant le jour, plus récent d'abord
    assert suivi.bilan_historique(h) == {"matchs": 2, "marques": 2, "encaisses": 3, "marques_par_match": 1.0, "encaisses_par_match": 1.5}
    assert suivi.historique_lieu(eq, False, "2026-10-20")[0]["adversaire"] == "Y"
    assert suivi.bilan_historique([])["marques_par_match"] is None


def test_explication_compte_les_vrais_matchs():
    h_dom = [{"marques": 2, "encaisses": 0}, {"marques": 1, "encaisses": 1}, {"marques": 0, "encaisses": 2}]   # domicile : V, N, D
    h_ext = [{"marques": 3, "encaisses": 1}, {"marques": 0, "encaisses": 1}]                                  # extérieur : V, D
    assert suivi.explication(["1x2", "1"], h_dom, h_ext) == {"domicile": [1, 3], "exterieur": [1, 2]}       # victoire du domicile : 1/3 et 1/2 (l'hôte gagne)
    assert suivi.explication(["over_under_1.5", "plus"], h_dom, h_ext) == {"domicile": [3, 3], "exterieur": [1, 2]}
    assert suivi.explication(["combo", "N2+plus_2.5"], h_dom, h_ext) == {"domicile": [0, 3], "exterieur": [1, 2]}
    assert suivi.explication(["inconnu", "?"], h_dom, h_ext) is None                    # marché non lisible : aucune explication inventée


def test_page_sans_marches_exclus_avec_historique(tmp_path, monkeypatch):
    monkeypatch.setattr(suivi, "_REGLES", [regle("Victoire domicile")])
    m = {"match_id": "x1", "date": "2099-01-01", "coup_d_envoi_utc": "2099-01-01T18:00:00Z", "heure_cameroun": "19:00", "competition": "Test",
         "domicile": "A", "exterieur": "B", "assemblage": {"equipe_dom": FORT_DOM, "equipe_ext": FAIBLE_EXT}, "cotes_betpawa": {"1x2": {"1": 1.40}}, "score_final": None}
    f = suivi.page(matchs=[m], sortie=tmp_path / "p.json")["matchs"][0]
    assert "rejetes" not in f and f["historique"]["bilan_domicile"]["matchs"] == 6
    assert all("explication" in x for lst in f["onglets"].values() for x in lst)


def test_page_js_explication_et_details():
    js = (suivi.ROOT / "archetype_comportement.js").read_text(encoding="utf-8")
    assert "explicationCourte(s, m)" in js and "matchs joués à domicile" in js and "matchs joués à l'extérieur" in js
    assert "Marchés exclus" not in js
