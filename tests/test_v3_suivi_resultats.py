"""Suivi des résultats V3 (correctif 24/10/2026) : toutes les sélections enregistrées sont réglées dès que le score est connu."""
import json

import selection_adaptative as S


def _prepare(tmp_path, monkeypatch, records, scores):
    hist = tmp_path / "historique_selection.json"
    hist.write_text(json.dumps(records), encoding="utf-8")
    v3 = tmp_path / "pronostics_v3.json"
    v3.write_text(json.dumps({"signaux": []}), encoding="utf-8")          # matchs terminés : absents du fichier du jour
    hp = tmp_path / "historique_pronostics.json"
    hp.write_text(json.dumps([{"matchs": [{"match_id": k, "score": v} for k, v in scores.items()]}]), encoding="utf-8")
    monkeypatch.setattr(S, "V3_HISTORY", hist)
    monkeypatch.setattr(S, "HISTORIQUE", hp)
    monkeypatch.setitem(S.INPUTS, S.V3, v3)
    return {r["record_id"]: r for r in S.sync_v3_history()}


def rec(mid, marche):
    return {"record_id": f"{mid}|{marche}", "match_id": mid, "marche": marche, "cote": 1.4, "resultat_statut": "PENDING"}


def test_reglement_gagnants_et_perdants(tmp_path, monkeypatch):
    records = [rec("a", "over_under_total_3.5_under"), rec("b", "buts_equipe_exterieur_1.5_under"), rec("c", "handicap3_domicile_1_1"),
               rec("d", "over_under_total_3.5_under"), rec("e", "over_under_total_2.5_over"), rec("f", "handicap3_domicile_-2_2")]
    scores = {"a": "1-2", "b": "3-1", "c": "1-1", "d": "5-1", "e": "1-1", "f": "4-0"}
    r = _prepare(tmp_path, monkeypatch, records, scores)
    # 3 qui doivent gagner : 3 buts < 3,5 ; extérieur 1 but < 1,5 ; domicile +1 à 3 choix sur 1-1 (2-1 après handicap)
    assert [r[f"{m}|{x['marche']}"]["resultat_marche"] for m, x in zip("abc", records[:3])] == ["WIN"] * 3
    # 3 qui doivent perdre : 6 buts (moins de 3,5) ; 2 buts (plus de 2,5) ; issue 2 du handicap domicile -2 sur 4-0 (2-0 après handicap)
    assert [r[f"{m}|{x['marche']}"]["resultat_marche"] for m, x in zip("def", records[3:])] == ["LOSS"] * 3
    assert all(x["resultat_statut"] == "RESOLVED" for x in r.values())


def test_sans_score_ou_marche_inconnu_reste_en_attente(tmp_path, monkeypatch):
    r = _prepare(tmp_path, monkeypatch, [rec("x", "over_under_total_2.5_over"), rec("y", "corners_plus_9.5")], {"y": "2-1"})
    assert r["x|over_under_total_2.5_over"]["resultat_statut"] == "PENDING"      # pas de score : rien d'inventé
    assert r["y|corners_plus_9.5"]["resultat_statut"] == "PENDING"               # marché non réglable sur le score
