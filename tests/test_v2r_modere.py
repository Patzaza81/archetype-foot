"""Tests des variantes « marché modéré » de v2r : familles, plancher de cote 1,40, carnets séparés, règlement."""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import carnet as K, execution as X, modere as MOD  # noqa: E402
from tests.test_v2r_autonome import joues, match  # noqa: E402

UTC = datetime.timezone.utc


# ---- familles : 3 cas qui passent, 3 qui échouent
def test_frere_cas_qui_passent():
    assert MOD.frere("Plus de 5.5 buts", 2) == "Plus de 3.5 buts"                       # exemple Villarreal – Naples
    assert MOD.frere("Moins de 2.5 buts - Domicile", 1) == "Moins de 3.5 buts - Domicile"
    assert MOD.frere("Handicap -1.5 - Extérieur", 1) == "Handicap -0.5 - Extérieur"
    assert MOD.frere("1X2 - 2", 2) == "Double chance - X2"
    assert MOD.frere("Plus de 1.5 buts", 2) == "Plus de 0.5 buts"                       # ligne minimale 0,5


def test_frere_nouveaux_equivalents_cas_qui_passent():
    assert MOD.frere("BTTS - oui", 1) == "Plus de 1.5 buts" and MOD.frere("BTTS - oui", 2) == "Plus de 1.5 buts"
    assert MOD.frere("Cage inviolée - Domicile", 1) == "Moins de 1.5 buts - Extérieur"   # domicile cage inviolée = extérieur à 0
    assert MOD.frere("Cage inviolée - Extérieur", 2) == "Moins de 2.5 buts - Domicile"
    assert MOD.candidats("1X2 - X", 1) == ["Double chance - 1X", "Double chance - X2"]


def test_frere_cas_qui_echouent():
    for lib in ("BTTS - non", "Total buts - pair", "Total buts - impair", "Encaisse au moins 1 but - Domicile",
                "1X2 - X", "libellé inconnu"):
        assert MOD.frere(lib, 1) is None, lib
    for lib in ("BTTS - non", "Total buts - pair", "Encaisse au moins 1 but - Domicile"):
        assert MOD.candidats(lib, 1) == [], lib


def test_nul_choisit_la_double_chance_la_plus_proche_du_plancher():
    nul = pari("1X2 - X", 4.43)
    assert MOD.variante(nul, {"Double chance - 1X": 1.61, "Double chance - X2": 1.55}, 1)["marche"] == "Double chance - X2"
    assert MOD.variante(nul, {"Double chance - 1X": 1.30, "Double chance - X2": 1.52}, 2)["marche"] == "Double chance - X2"
    assert MOD.variante(nul, {"Double chance - 1X": 1.40, "Double chance - X2": 1.30}, 1)["cote"] == 1.40
    assert MOD.variante(nul, {"Double chance - 1X": 1.30, "Double chance - X2": 1.35}, 1) is None   # rien, pas de repli sur le nul
    assert MOD.variante(nul, {"Double chance - 1X": 1.39}, 2) is None
    assert MOD.variante(nul, {}, 1)["marche"] == "1X2 - X"                                            # double chances non cotées : nul gardé


def test_les_deux_marquent_oui_et_cage_inviolee_sous_le_plancher_ou_non():
    assert MOD.variante(pari("BTTS - oui", 2.0), {"Plus de 1.5 buts": 1.45}, 1)["marche"] == "Plus de 1.5 buts"
    assert MOD.variante(pari("BTTS - oui", 2.0), {"Plus de 1.5 buts": 1.25}, 1) is None
    v = MOD.variante(pari("Cage inviolée - Domicile", 2.3), {"Moins de 1.5 buts - Extérieur": 1.60, "Moins de 2.5 buts - Extérieur": 1.2}, 1)
    assert v["marche"] == "Moins de 1.5 buts - Extérieur"
    assert MOD.variante(pari("Cage inviolée - Domicile", 2.3), {"Moins de 2.5 buts - Extérieur": 1.2}, 2) is None
    assert MOD.variante(pari("BTTS - non", 1.8), {"Plus de 1.5 buts": 1.2}, 1)["marche"] == "BTTS - non"   # sans équivalent : gardé


# ---- plancher de cote
def pari(lib="Plus de 5.5 buts", cote=8.26):
    return dict(match_id="m", coup_d_envoi_utc="2026-10-14T18:00:00Z", marche=lib, cote=cote)


def test_variante_cas_qui_passent():
    cotes = {"Plus de 3.5 buts": 2.46, "Plus de 4.5 buts": 4.41}
    v = MOD.variante(pari(), cotes, 2)
    assert v["marche"] == "Plus de 3.5 buts" and v["cote"] == 2.46 and v["marche_v2r"] == "Plus de 5.5 buts" and v["crans"] == 2
    assert MOD.variante(pari(), cotes, 1)["marche"] == "Plus de 4.5 buts"
    assert MOD.variante(pari(), {"Plus de 3.5 buts": 1.40}, 2)["cote"] == 1.40            # pile au plancher : gardé
    assert MOD.variante(pari("BTTS - non", 1.8), {}, 1)["marche"] == "BTTS - non"          # sans version modérée : gardé


def test_variante_sous_le_plancher_ne_propose_rien():
    assert MOD.variante(pari("Plus de 2.5 buts", 2.44), {"Plus de 1.5 buts": 1.47, "Plus de 0.5 buts": 1.08}, 2) is None
    assert MOD.variante(pari("Plus de 1.5 buts - Domicile", 1.43), {"Plus de 0.5 buts - Domicile": 1.06}, 1) is None
    assert MOD.variante(pari("BTTS - non", 1.39), {}, 1) is None                           # pari d'origine sous le plancher
    assert MOD.variante(pari(), {"Plus de 3.5 buts": 1.39}, 2) is None                     # jamais de repli sur 8,26


def test_variante_marche_non_cote_garde_le_pari_d_origine():
    v = MOD.variante(pari(), {}, 2)
    assert v["marche"] == "Plus de 5.5 buts" and v["cote"] == 8.26


# ---- carnets séparés et règlement
def ligne_officielle(lib, cote, mid="m", ko="2026-10-14T18:00:00Z"):
    return {mid: dict(match_id=mid, coup_d_envoi_utc=ko, marche=lib, cote=cote, fige=False, resultat=None, score=None, profit=None)}


def test_met_a_jour_ecrit_regle_et_ne_touche_pas_au_carnet_officiel():
    with tempfile.TemporaryDirectory() as d:
        officiel = ligne_officielle("Plus de 5.5 buts", 8.26)
        avant = dict(officiel["m"])
        m = match("m", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z",
                  cotes={"Plus de 5.5 buts": 8.26, "Plus de 4.5 buts": 4.41, "Plus de 3.5 buts": 2.46})
        t1 = datetime.datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
        s = MOD.met_a_jour([m], officiel, d, t1)
        assert s["plancher"] == 1.40
        assert [l["marche"] for l in s["1_cran"]["a_venir"]] == ["Plus de 4.5 buts"]
        assert [l["marche"] for l in s["2_crans"]["a_venir"]] == ["Plus de 3.5 buts"]
        assert officiel["m"] == avant                                                      # carnet officiel intact
        # après le coup d'envoi, avec le score (3-1 = 4 buts) : 4.5 perdu, 3.5 gagné
        officiel["m"]["fige"] = True
        fini = dict(m, h=3, a=1)
        t2 = datetime.datetime(2026, 10, 14, 21, 0, tzinfo=UTC)
        s2 = MOD.met_a_jour([fini], officiel, d, t2)
        assert s2["1_cran"]["reglees"][0]["resultat"] == "LOSS" and s2["2_crans"]["reglees"][0]["resultat"] == "WIN"
        assert abs(s2["2_crans"]["reglees"][0]["profit"] - 1.46) < 1e-9
        # un score ne se réécrit jamais
        s3 = MOD.met_a_jour([dict(fini, h=0, a=0)], officiel, d, t2)
        assert s3["2_crans"]["reglees"][0]["score"] == [3, 1]


def test_met_a_jour_retire_un_pari_devenu_inferieur_au_plancher_avant_le_coup_d_envoi():
    with tempfile.TemporaryDirectory() as d:
        officiel = ligne_officielle("Plus de 3.5 buts", 3.2)
        t1 = datetime.datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
        m = match("m", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z",
                  cotes={"Plus de 3.5 buts": 3.2, "Plus de 2.5 buts": 1.9})
        assert len(MOD.met_a_jour([m], officiel, d, t1)["1_cran"]["a_venir"]) == 1
        m2 = dict(m, cotes={"Plus de 3.5 buts": 3.2, "Plus de 2.5 buts": 1.30})
        t2 = datetime.datetime(2026, 10, 14, 14, 0, tzinfo=UTC)
        assert MOD.met_a_jour([m2], officiel, d, t2)["1_cran"]["a_venir"] == []           # plus rien, pas de repli


def test_execution_publie_les_variantes_et_une_erreur_ne_bloque_pas(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        a_venir = match("n1", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z")
        t1 = datetime.datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
        s = X.execute(joues() + [a_venir], d, t1)
        assert s["modere"]["plancher"] == 1.40 and "1_cran" in s["modere"] and "2_crans" in s["modere"]
        assert os.path.exists(os.path.join(d, "modere1", "carnet.json"))
        assert len(s["a_venir"]) == 1                                                       # v2r officiel inchangé

        def casse(*a, **k):
            raise ValueError("test")
        monkeypatch.setattr(MOD, "met_a_jour", casse)
        s2 = X.execute(joues() + [a_venir], d, datetime.datetime(2026, 10, 13, 13, 0, tzinfo=UTC))
        assert s2["modere"] == dict(erreur="ValueError: test") and len(s2["a_venir"]) == 1


# ---- page : le pari d'origine reste inchangé, le pari modéré est affiché dessous
def test_page_affiche_le_pari_modere_sous_le_pari_d_origine():
    import pathlib
    racine = pathlib.Path(__file__).parent.parent
    js = (racine / "archetype_v2r.js").read_text(encoding="utf-8")
    h = (racine / "pronostics_v2r.html").read_text(encoding="utf-8")
    corps = js[js.index("function v2rCarte"):js.index("function v2rListe")]
    assert corps.index("v2rMarche(l)") < corps.index("roi_cellule") < corps.index("v2rBlocModere(l, mode)")   # sous le pari d'origine
    assert "Pari modéré associé" in js and ".v2r-modere{" in h and "data/v2r/pronostics_v2r.json" in js
    assert "if (!m || m.erreur) return null" in js                                      # variantes indisponibles : rien d'affiché


def test_variantes_publient_a_venir_en_cours_et_reglees():
    with tempfile.TemporaryDirectory() as d:
        m = match("m", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z", cotes={"BTTS - non": 1.8})
        s = MOD.met_a_jour([m], ligne_officielle("BTTS - non", 1.8), d, datetime.datetime(2026, 10, 14, 12, 0, tzinfo=UTC))
        for cle in ("1_cran", "2_crans"):
            assert set(s[cle]) == {"bilan", "a_venir", "en_cours", "reglees", "super_favori"} and len(s[cle]["a_venir"]) == 1
