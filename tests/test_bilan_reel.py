"""Bilan réel (29/10/2026) : jamais de pari sur un match que le moteur n'a pas tourné."""
import json
import bilan_reel as B

KO = "2026-10-28T18:00:00Z"


def pron(mid, gele, ko=KO, onglets=None):
    return {"type": "pronostic", "match_id": mid, "gele_le": gele, "coup_d_envoi_utc": ko, "date": "2026-10-28", "onglets": onglets or {}}


def ecrire(tmp_path, lignes):
    f = tmp_path / "j.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in lignes), encoding="utf-8")
    return f


def mk(cle, valeur, cote=None):
    return {"cle": cle, "marche": "|".join(cle), "valeur": valeur, "cote": cote}


ON = {"buts": [mk(["over_under_1.5", "plus"], 0.9, 1.30), mk(["multigoals", "1-4"], 0.8)], "equipes": [mk(["1x2", "1"], 0.7, None)], "multiscores": [], "calibrees": []}
RES = {"type": "resultat", "match_id": "m1", "score": {"buts_dom": 2, "buts_ext": 1}, "gagnes": {"buts": [True, True], "equipes": [True], "multiscores": [], "calibrees": []}}


def test_retenus(tmp_path):                                   # 3 cas qui doivent passer
    f = ecrire(tmp_path, [pron("m1", "2026-10-28T10:00:00Z", onglets=ON), RES])
    p = B.paris_alpha(f)
    assert {(x["cat"], x["cote"]) for x in p} == {("buts", 1.30), ("multigoals", None)}          # équipes sans cote : jamais affiché
    assert all(x["mid"] == "m1" and x["gagne"] for x in p)
    assert [x["tete"] for x in p] == [True, True]                                                 # en tête de leur catégorie


def test_dernier_gel_avant_coup_d_envoi_gagne(tmp_path):
    autre = {"buts": [mk(["over_under_2.5", "plus"], 0.9, 1.50)], "equipes": [], "multiscores": [], "calibrees": []}
    res = {**RES, "gagnes": {"buts": [False], "equipes": [], "multiscores": [], "calibrees": []}}
    f = ecrire(tmp_path, [pron("m1", "2026-10-28T08:00:00Z", onglets=ON), pron("m1", "2026-10-28T12:00:00Z", onglets=autre), res])
    p = B.paris_alpha(f)
    assert len(p) == 1 and p[0]["cle"] == ["over_under_2.5", "plus"] and p[0]["gagne"] is False


def test_doublon_de_marche_retire(tmp_path):
    on = {"buts": [mk(["over_under_1.5", "plus"], 0.9, 1.30), mk(["over_under_1.5", "plus"], 0.9, 1.30)], "equipes": [], "multiscores": [], "calibrees": []}
    res = {**RES, "gagnes": {"buts": [True, True], "equipes": [], "multiscores": [], "calibrees": []}}
    assert len(B.paris_alpha(ecrire(tmp_path, [pron("m1", "2026-10-28T10:00:00Z", onglets=on), res]))) == 1


def test_ecartes_gel_apres_coup_d_envoi(tmp_path):            # 3 cas qui doivent échouer
    assert B.paris_alpha(ecrire(tmp_path, [pron("m1", "2026-10-28T18:00:01Z", onglets=ON), RES])) == []


def test_ecartes_match_non_termine(tmp_path):
    assert B.paris_alpha(ecrire(tmp_path, [pron("m1", "2026-10-28T10:00:00Z", onglets=ON)])) == []


def test_ecartes_sans_coup_d_envoi_et_resultat_d_un_autre_match(tmp_path):
    assert B.paris_alpha(ecrire(tmp_path, [pron("m1", "2026-10-28T10:00:00Z", ko=None, onglets=ON), RES])) == []
    assert B.paris_alpha(ecrire(tmp_path, [pron("m2", "2026-10-28T10:00:00Z", onglets=ON), RES])) == []


def test_omega_seuls_les_matchs_avec_pari_termines_avant_coup_d_envoi(tmp_path):
    fiche = {"jour": "2026-10-28", "coup_d_envoi_utc": KO, "series": {}, "principal": {"cle": ["1x2", "1"], "cote": 1.5}, "autres": [{"cle": ["btts", "Oui"], "cote": 1.6}]}
    vide = {**fiche, "principal": None, "autres": []}
    L = [{"type": "pronostic", "match_id": "o1", "gele_le": "2026-10-28T10:00:00Z", "fiche": fiche},
         {"type": "pronostic", "match_id": "o2", "gele_le": "2026-10-28T10:00:00Z", "fiche": vide},
         {"type": "pronostic", "match_id": "o3", "gele_le": "2026-10-28T19:00:00Z", "fiche": fiche},     # gelé après le coup d'envoi
         {"type": "resultat", "match_id": "o1", "score": [2, 0], "paris": [{"cle": ["1x2", "1"], "cote": 1.5, "gagne": True}, {"cle": ["btts", "Oui"], "cote": 1.6, "gagne": False}]},
         {"type": "resultat", "match_id": "o2", "score": [0, 0], "paris": []}, {"type": "resultat", "match_id": "o3", "score": [1, 0], "paris": [{"cle": ["1x2", "1"], "cote": 1.5, "gagne": True}]}]
    p = B.paris_omega(ecrire(tmp_path, L))
    assert [(x["mid"], x["cat"], x["gagne"]) for x in p] == [("o1", "principal", True), ("o1", "autre", False)]


def test_resume_annonce_matchs_et_periode():
    s = B.resume("T", [{"mid": "a", "jour": "2026-10-27", "cote": 1.5, "gagne": True}, {"mid": "b", "jour": "2026-10-28", "cote": 2.0, "gagne": False}])
    assert "2 paris sur 2 matchs terminés (2026-10-27 → 2026-10-28)" in s and "rendement -25.0 %" in s
