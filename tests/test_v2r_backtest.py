"""Test à l'aveugle de v2r (moteur_v2r/backtest.py) : règlement, absence de fuite, résumé."""
import pytest

from moteur_v2r import backtest as B, regles as R


@pytest.mark.parametrize("lib,cote,h,a,attendu", [
    ("Plus de 2.5 buts", 2.0, 2, 1, 1.0),            # gagné
    ("Moins de 2.5 buts", 1.8, 1, 1, 0.8),
    ("Handicap 2 - Domicile", 3.0, 0, 2, 0.0),        # remboursé
])
def test_profit_cas_qui_passent(lib, cote, h, a, attendu):
    assert B.profit(lib, cote, h, a) == pytest.approx(attendu)


@pytest.mark.parametrize("lib,cote,h,a", [
    ("Plus de 2.5 buts", 2.0, 1, 1),                 # perdu
    ("Moins de 2.5 buts", 1.8, 3, 0),
    ("Handicap 1.5 - Domicile", 2.2, 0, 2),
])
def test_profit_cas_perdus(lib, cote, h, a):
    assert B.profit(lib, cote, h, a) == -1.0


@pytest.mark.parametrize("lib,h,a", [("Marché inconnu", 1, 0), ("Plus de 2.5 buts", None, 1), ("Plus de 2.5 buts", 1, None)])
def test_profit_non_reglable_donne_none(lib, h, a):
    assert B.profit(lib, 2.0, h, a) is None


def _match(i, date, h=1, a=0):
    return dict(id=str(i), date=date, ligue="L", h=h, a=a, cotes={"Plus de 2.5 buts": 2.0}, dom="A", ext="B",
                kickoff=None, hd=[], he=[])


def test_aucune_fuite_les_regles_n_ont_vu_que_le_passe(monkeypatch):
    vus = []

    def faux(matchs, jour):
        vus.append((jour, [m["date"] for m in matchs]))
        return None
    monkeypatch.setattr(R, "entraine", faux)
    ms = [_match(1, "2026-10-10"), _match(2, "2026-10-11"), _match(3, "2026-10-12"), _match(4, "2026-10-13")]
    B.rejoue(ms, ["2026-10-12", "2026-10-13"])
    assert vus[0] == ("2026-10-12", ["2026-10-10", "2026-10-11"])
    assert vus[1] == ("2026-10-13", ["2026-10-10", "2026-10-11", "2026-10-12"])
    assert all(d < j for j, ds in vus for d in ds)


def test_le_score_du_jour_teste_ne_change_pas_les_regles(monkeypatch):
    capture = []
    monkeypatch.setattr(R, "entraine", lambda matchs, jour: capture.append([(m["id"], m["h"]) for m in matchs]))
    B.rejoue([_match(1, "2026-10-10", 1, 0), _match(2, "2026-10-13", 0, 0)], ["2026-10-13"])
    B.rejoue([_match(1, "2026-10-10", 1, 0), _match(2, "2026-10-13", 5, 5)], ["2026-10-13"])
    assert capture[0] == capture[1] == [("1", 1)]


def test_jour_sans_match_ne_donne_rien():
    res = B.rejoue([_match(1, "2026-10-10")], ["2026-10-20"])
    assert all(v == [] for v in res.values())


def test_resume_vide():
    assert B.resume([])["paris"] == 0 and B.resume([])["roi"] is None


def test_resume_calcule_roi_et_reussite():
    L = [dict(mid=str(i), lib="x", o=2.0, profit=p, r=r) for i, (p, r) in enumerate([(1.0, 1), (-1.0, -1), (0.0, 0), (1.0, 1)])]
    r = B.resume(L)
    assert r["paris"] == 4 and r["roi"] == pytest.approx(0.25) and r["reussite"] == pytest.approx(2 / 3)
    assert r["ic95"] is None                      # moins de 20 paris : pas d'intervalle
