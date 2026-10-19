"""Fenêtre d'historique du moteur alpha : paramètre mesuré (5 en production, None = tout l'historique disponible), jamais figé dans le code."""
import json
from pathlib import Path

import pytest

from matrice_scenarios import backtest_comportement as B
from matrice_scenarios import comportement as C

ROOT = Path(__file__).resolve().parent.parent


def equipe(n, lieu=True, extra=()):
    ms = [{"date": f"2026-0{1 + i // 9}-{1 + (i % 9) * 3:02d}", "domicile": lieu, "buts_marques": i % 3, "buts_encaisses": 1} for i in range(n)]
    return {"matchs": ms + list(extra)}


@pytest.fixture
def fenetre(monkeypatch):
    def poser(w):
        monkeypatch.setattr(C, "FENETRE", w)
    return poser


# --- 3 cas qui doivent passer ---
@pytest.mark.parametrize("w,attendu", [(5, 5), (8, 8), (None, 10)])
def test_la_fenetre_decide_du_nombre_de_matchs_retenus(fenetre, w, attendu):
    fenetre(w)
    d, e = B.historiques(equipe(10), equipe(10, False), "2026-12-31")
    assert len(d) == attendu and len(e) == attendu


# --- 3 cas qui doivent échouer (renvoient None ou exclus) ---
def test_moins_de_3_matchs_pas_de_profil(fenetre):
    fenetre(None)
    assert B.historiques(equipe(2), equipe(2, False), "2026-12-31") is None


def test_un_match_du_jour_ou_posterieur_nest_jamais_compte(fenetre):
    fenetre(None)
    futur = [{"date": "2026-12-31", "domicile": True, "buts_marques": 9, "buts_encaisses": 9}]
    d, _ = B.historiques(equipe(4, True, futur), equipe(4, False), "2026-12-31")
    assert len(d) == 4 and (9, 9) not in d


def test_un_match_provisoire_nest_jamais_compte(fenetre):
    fenetre(None)
    prov = [{"date": "2026-06-01", "domicile": True, "buts_marques": 7, "buts_encaisses": 7, "provisoire": True}]
    d, _ = B.historiques(equipe(4, True, prov), equipe(4, False), "2026-12-31")
    assert (7, 7) not in d


def test_debut_suit_la_fenetre():
    assert C.DEBUT == (0 if C.FENETRE is None else -C.FENETRE)


def test_parametres_de_production_et_variante_complete_existent():
    prod = json.loads((ROOT / "docs" / "parametres_comportement.json").read_text(encoding="utf-8"))
    var = json.loads((ROOT / "docs" / "parametres_comportement_fenetre_complete.json").read_text(encoding="utf-8"))
    assert prod.get("fenetre", 5) == 5 and var["fenetre"] is None
