"""Tests du harnais xG (moteur_dc/xg_harnais.py) : 3 cas qui passent et 3 qui échouent par règle (demande de Patrick)."""
import json

import numpy as np
import pytest

from moteur_dc import modele as MO, xg_harnais as X


def _ecrire(dossier, code, lignes):
    (dossier / f"{code}.jsonl").write_text("\n".join(json.dumps(l) for l in lignes), encoding="utf-8")


def _m(jour, h=1, a=0, xh=1.2, xa=0.4, dom="A", ext="B"):
    return {"date": jour, "home_team": dom, "away_team": ext, "full_time_home_goals": h, "full_time_away_goals": a, "home_xg": xh, "away_xg": xa}


# --- Couverture : règle des 80 % -------------------------------------------------------------------------------------------------
def test_ligue_couverte_a_100_pct_est_retenue(tmp_path):
    _ecrire(tmp_path, "E0", [_m("2026-08-01"), _m("2026-08-08")])
    matchs, couv = X.charger(tmp_path)
    assert couv["E0"]["retenue"] and len(matchs) == 2


def test_ligue_a_80_pct_pile_est_retenue(tmp_path):
    _ecrire(tmp_path, "D1", [_m(f"2026-08-0{k}") for k in range(1, 5)] + [_m("2026-08-09", xh=None, xa=None)])
    assert X.charger(tmp_path)[1]["D1"]["couverture"] == 0.8 and X.charger(tmp_path)[1]["D1"]["retenue"]


def test_ligne_sans_xg_ecartee_dans_une_ligue_retenue(tmp_path):
    _ecrire(tmp_path, "F1", [_m(f"2026-08-0{k}") for k in range(1, 5)] + [_m("2026-08-09", xh=None, xa=None)])
    assert len(X.charger(tmp_path)[0]) == 4


def test_ligue_sous_80_pct_est_exclue(tmp_path):
    _ecrire(tmp_path, "SP1", [_m("2026-08-01"), _m("2026-08-08", xh=None, xa=None), _m("2026-08-15", xh=None, xa=None)])
    matchs, couv = X.charger(tmp_path)
    assert not couv["SP1"]["retenue"] and matchs == []


def test_ligue_sans_aucun_xg_est_exclue(tmp_path):
    _ecrire(tmp_path, "USA", [_m("2026-08-01", xh=None, xa=None)])
    assert not X.charger(tmp_path)[1]["USA"]["retenue"]


def test_match_non_joue_ne_compte_pas(tmp_path):
    _ecrire(tmp_path, "I1", [_m("2026-08-01"), {**_m("2026-08-08"), "full_time_home_goals": None, "full_time_away_goals": None}])
    assert X.charger(tmp_path)[1]["I1"]["joues"] == 1


# --- Cible mélangée ----------------------------------------------------------------------------------------------------------
def test_beta_zero_ne_change_rien():
    m = [{"id": 1, "h": 2, "a": 1, "xh": 0.5, "xa": 0.5}]
    assert "hf" not in X.avec_cible(m, 0.0)[0]


def test_beta_melange_buts_et_xg():
    c = X.avec_cible([{"id": 1, "h": 2, "a": 0, "xh": 1.0, "xa": 0.5}], 0.25)[0]
    assert c["hf"] == pytest.approx(1.75) and c["af"] == pytest.approx(0.125) and c["h"] == 2


def test_beta_un_est_le_xg_pur_mais_les_buts_restent():
    c = X.avec_cible([{"id": 1, "h": 3, "a": 0, "xh": 1.0, "xa": 0.5}], 1.0)[0]
    assert c["hf"] == 1.0 and c["h"] == 3


# --- modele.ajuster : compatibilité et correction tau sur les buts réels ----------------------------------------------------------
def _petit():
    dom, ext = ["A", "B", "C", "A", "B", "C"], ["B", "C", "A", "C", "A", "B"]
    return dom, ext, np.array([2, 0, 1, 3, 1, 0]), np.array([0, 0, 1, 1, 2, 1]), np.arange(1, 7)


def test_ajuster_sans_buts_tau_est_inchange():
    dom, ext, h, a, age = _petit()
    f1 = MO.ajuster(dom, ext, h, a, age, 0.5, 0.004, None, -0.04)
    f2 = MO.ajuster(dom, ext, h, a, age, 0.5, 0.004, None, -0.04, None, (h, a))
    assert np.allclose(f1.att, f2.att) and f1.mu == pytest.approx(f2.mu)


def test_ajuster_avec_cibles_xg_utilise_les_buts_reels_pour_tau():
    dom, ext, h, a, age = _petit()
    xg_h, xg_a = h * 0.6 + 0.2, a * 0.6 + 0.2
    f_reel = MO.ajuster(dom, ext, xg_h, xg_a, age, 0.5, 0.004, None, -0.04, None, (h, a))
    f_naif = MO.ajuster(dom, ext, xg_h, xg_a, age, 0.5, 0.004, None, -0.04)
    assert not np.allclose(f_reel.att, f_naif.att)           # sans buts_tau, les xG arrondis fausseraient la correction des petits scores


# --- Seuils et refus ---------------------------------------------------------------------------------------------------------
def test_paris_necessaires_pour_les_regles_de_patrick():
    assert X.paris_necessaires(2.0) == 985 and X.paris_necessaires(0.5) == 15747


def test_plus_l_effet_est_petit_plus_il_faut_de_matchs():
    assert X.matchs_necessaires_logloss(0.3, 0.001) > X.matchs_necessaires_logloss(0.3, 0.01) > 0


def test_decoupe_60_20_20():
    assert X.decoupe(100) == (60, 80) and X.decoupe(275) == (165, 220)


def test_lancer_refuse_sous_le_seuil(monkeypatch):
    monkeypatch.setattr(X, "verifier", lambda log=print: {"atteint": False, "matchs_predits": 275, "seuil_matchs_predits": 66060})
    monkeypatch.setattr(X, "executer", lambda log=print: pytest.fail("le test complet ne doit pas être exécuté sous le seuil"))
    with pytest.raises(SystemExit):
        X.lancer()


def test_lancer_s_execute_au_dessus_du_seuil(monkeypatch, tmp_path):
    monkeypatch.setattr(X, "verifier", lambda log=print: {"atteint": True, "matchs_predits": 70000, "seuil_matchs_predits": 66060})
    monkeypatch.setattr(X, "executer", lambda log=print: {"ok": True})
    monkeypatch.setattr(X, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    assert X.lancer() == {"ok": True}
