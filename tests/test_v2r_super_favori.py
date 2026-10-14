"""Tests du statut SUPER FAVORI (indice en % >= 75 %, buts seulement) des paris modérés de v2r."""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import modere as MOD, super_favori as SF  # noqa: E402
from tests.test_v2r_autonome import match  # noqa: E402

UTC = datetime.timezone.utc


def h(dom, bm, be, n=1):
    return [dict(date=f"2026-09-{i + 1:02d}", domicile=dom, buts_marques=bm, buts_encaisses=be) for i in range(n)]


def hist(scores_dom, scores_ext):
    """Historique d'équipe à domicile (scores_dom) / à l'extérieur (scores_ext) : listes de (marqués, encaissés)."""
    return ([x for s in scores_dom for x in h(True, *s)], [x for s in scores_ext for x in h(False, *s)])


# ---- 3 cas qui passent (>= 75 %) et 3 qui échouent, par famille
def test_totaux_passent_et_echouent():
    d, _ = hist([(2, 1)] * 4, []); _, e = hist([], [(1, 2)] * 4)           # 3 buts partout
    assert SF.statut("Plus de 1.5 buts", d, e) == dict(indice_pct=100.0, super_favori=True)
    assert SF.statut("Plus de 2.5 buts", d, e)["super_favori"]
    assert SF.statut("Moins de 4.5 buts", d, e)["super_favori"]
    assert not SF.statut("Plus de 3.5 buts", d, e)["super_favori"]          # 0 %
    assert not SF.statut("Moins de 2.5 buts", d, e)["super_favori"]
    d2, _ = hist([(2, 1)] * 2 + [(0, 0)] * 2, []); _, e2 = hist([], [(1, 2)] * 2 + [(0, 0)] * 2, )
    assert SF.statut("Plus de 1.5 buts", d2, e2) == dict(indice_pct=50.0, super_favori=False)


def test_double_chance_passe_et_echoue():
    d, _ = hist([(2, 0)] * 3 + [(1, 1)], []); _, e = hist([], [(0, 1)] * 3 + [(1, 1)])      # domicile invaincu, extérieur perd 3/4
    assert SF.statut("Double chance - 1X", d, e)["super_favori"]
    assert SF.statut("Double chance - 1X", d, e)["indice_pct"] == 100.0
    _, e_mixte = hist([], [(2, 1)] * 2 + [(0, 1)] * 2)                                                  # l'extérieur gagne 2 fois sur 4
    assert SF.statut("Double chance - 1X", d, e_mixte)["indice_pct"] == 75.0
    assert not SF.statut("Double chance - X2", d, e)["super_favori"]
    d3, _ = hist([(0, 2)] * 3 + [(1, 1)], []); _, e3 = hist([], [(2, 0)] * 3 + [(1, 1)])
    assert SF.statut("Double chance - X2", d3, e3)["super_favori"]
    assert not SF.statut("Double chance - 1X", d3, e3)["super_favori"]
    assert SF.statut("Double chance - 12", *hist([(2, 0)] * 4, [])[:1], hist([], [(0, 2)] * 4)[1])["super_favori"]


def test_btts_handicap_buts_equipe_cage_passent_et_echouent():
    d, _ = hist([(0, 2)] * 4, []); _, e = hist([], [(0, 3)] * 4)
    assert SF.statut("BTTS - non", d, e)["super_favori"] and not SF.statut("BTTS - oui", d, e)["super_favori"]
    d, _ = hist([(2, 1)] * 4, []); _, e = hist([], [(2, 1)] * 2 + [(1, 1)] * 2)
    assert SF.statut("Handicap 0.5 - Domicile", d, e) == dict(indice_pct=75.0, super_favori=True)   # 100 % domicile, 50 % extérieur
    assert not SF.statut("Handicap -1.5 - Domicile", d, e)["super_favori"]
    assert SF.statut("Plus de 1.5 buts - Domicile", d, e)["super_favori"] is False                     # 100 % et 0 % -> 50 %
    assert SF.statut("Plus de 0.5 buts - Extérieur", d, e)["super_favori"]
    d, _ = hist([(3, 0)] * 4, []); _, e = hist([], [(0, 2)] * 4)
    assert SF.statut("Cage inviolée - Extérieur", d, e)["indice_pct"] == 0.0                           # domicile marque : extérieur inviolée perd
    assert SF.statut("Cage inviolée - Domicile", d, e) == dict(indice_pct=100.0, super_favori=True)


def test_marches_sans_indice_et_echantillon_trop_petit():
    d, _ = hist([(2, 1)] * 4, []); _, e = hist([], [(1, 2)] * 4)
    for lib in ("1X2 - X", "Total buts - pair", "Total buts - impair", "Encaisse au moins 1 but - Domicile",
                "Handicap 1 - Domicile", "libellé inconnu"):
        assert SF.statut(lib, d, e) == dict(indice_pct=None, super_favori=False), lib
    pd, _ = hist([(2, 1)] * 2, []); _, pe = hist([], [(1, 2)] * 4)
    assert SF.statut("Plus de 1.5 buts", pd, pe) == dict(indice_pct=None, super_favori=False)       # 2 matchs au lieu < 3
    assert SF.statut("Plus de 1.5 buts", [], []) == dict(indice_pct=None, super_favori=False)
    mixte = h(True, 2, 1, 3) + h(False, 0, 0, 5)                                                      # les matchs à l'extérieur de l'équipe à domicile ne comptent pas
    assert SF.statut("Plus de 1.5 buts", mixte, _e(e))["indice_pct"] == 100.0


def _e(e):
    return e


def test_seuil_exact_75_est_retenu_et_74_non():
    d, _ = hist([(2, 1)] * 3 + [(0, 0)], []); _, e = hist([], [(1, 2)] * 3 + [(0, 0)])
    assert SF.statut("Plus de 1.5 buts", d, e) == dict(indice_pct=75.0, super_favori=True)
    d, _ = hist([(2, 1)] * 2 + [(0, 0)] * 2, []); _, e = hist([], [(1, 2)] * 4)
    assert SF.statut("Plus de 1.5 buts", d, e) == dict(indice_pct=75.0, super_favori=True)
    d, _ = hist([(2, 1)] * 5 + [(0, 0)] * 2, []); _, e = hist([], [(1, 2)] * 5 + [(0, 0)] * 2)
    assert SF.statut("Plus de 1.5 buts", d, e)["indice_pct"] == 71.4 and not SF.statut("Plus de 1.5 buts", d, e)["super_favori"]


# ---- intégration : le carnet modéré porte l'indice et le bilan SUPER FAVORI est publié
def test_carnet_modere_porte_l_indice_et_le_bilan_super_favori():
    d, _ = hist([(2, 1)] * 4, []); _, e = hist([], [(1, 2)] * 4)
    mm = match("m", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z", cotes={"Plus de 3.5 buts": 2.2, "Plus de 2.5 buts": 1.6})
    mm["hd"], mm["he"] = d, e
    officiel = {"m": dict(match_id="m", coup_d_envoi_utc="2026-10-14T18:00:00Z", marche="Plus de 3.5 buts", cote=2.2,
                          fige=False, resultat=None, score=None, profit=None)}
    with tempfile.TemporaryDirectory() as dossier:
        s = MOD.met_a_jour([mm], officiel, dossier, datetime.datetime(2026, 10, 14, 12, 0, tzinfo=UTC))
        l = s["1_cran"]["a_venir"][0]
        assert l["marche"] == "Plus de 2.5 buts" and l["indice_pct"] == 100.0 and l["super_favori"] is True
        assert s["1_cran"]["super_favori"]["seuil"] == 0.75 and s["1_cran"]["super_favori"]["a_venir"] == 1
        assert s["2_crans"]["a_venir"][0]["super_favori"] is False or s["2_crans"]["a_venir"][0]["indice_pct"] is not None
        officiel["m"]["fige"] = True
        fini = dict(mm, h=2, a=2)
        s2 = MOD.met_a_jour([fini], officiel, dossier, datetime.datetime(2026, 10, 14, 21, 0, tzinfo=UTC))
        b = s2["1_cran"]["super_favori"]["bilan"]
        assert b["regles"] == 1 and b["gagnes"] == 1 and b["statut"] == "observation"
        assert s2["1_cran"]["reglees"][0]["super_favori"] is True


def test_page_affiche_le_badge_super_favori():
    import pathlib
    racine = pathlib.Path(__file__).parent.parent
    js = (racine / "archetype_v2r.js").read_text(encoding="utf-8")
    assert "SUPER FAVORI" in js and "v2r-super" in (racine / "pronostics_v2r.html").read_text(encoding="utf-8")
