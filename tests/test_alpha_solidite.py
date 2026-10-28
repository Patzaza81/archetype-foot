"""Solidité des marchés de l'alpha (28/10/2026) : mêmes principes que celle d'omega, appliquée à tous les marchés affichés."""
import json
import re
from pathlib import Path

import numpy as np
import pytest

from alpha_serie import solidite as SA, suivi

RACINE = Path(__file__).resolve().parent.parent
JS = (RACINE / "archetype_comportement.js").read_text(encoding="utf-8")
CSS = (RACINE / "af-comportement.css").read_text(encoding="utf-8")
HTML = (RACINE / "pronostics_comportement.html").read_text(encoding="utf-8")

# matchs au même lieu affichés sur la carte : l'équipe qui reçoit (marqués, encaissés) ; l'adversaire à l'extérieur (marqués, encaissés)
HD = [{"marques": a, "encaisses": b} for a, b in [(1, 0), (1, 1), (2, 1), (0, 0)]]
HE = [{"marques": a, "encaisses": b} for a, b in [(0, 1), (1, 1), (1, 2), (2, 1)]]   # vus du domicile : 1-0, 1-1, 2-1, 1-2


@pytest.mark.parametrize("cle,passe", [
    (("multigoals", "1-3"), (3 / 4 + 4 / 4) / 2),           # total de 1 à 3 buts : domicile 1,2,3,0 -> 3 sur 4 ; extérieur 1,2,3,3 -> 4 sur 4
    (("combo", "1N+moins_3.5"), (4 / 4 + 3 / 4) / 2),       # domicile ne perd pas ET moins de 3,5 buts
    (("multiscores", "Match nul"), (2 / 4 + 1 / 4) / 2),    # le groupe « Match nul » : scores nuls
    (("double_chance", "1N"), (4 / 4 + 3 / 4) / 2),
])
def test_mesures_alpha_sur_les_matchs_affiches(cle, passe):
    assert SA.mesures(cle, HD, HE)["passe"] == pytest.approx(passe)


@pytest.mark.parametrize("cle", [("over_under_3.5", "plus"), ("multigoals", "5-6"), ("combo", "N2+plus_3.5")])
def test_mesures_alpha_pari_qui_rate_a_un_ecart_negatif(cle):
    r = SA.mesures(cle, HD, HE)
    assert r["passe"] <= 0.25 and r["ecart"] < 0


def test_probabilite_sans_poids_marche_inconnu_ou_peu_de_matchs_rien_invente():
    w = {"poids_frequence": 0.5, "poids_ecart": 0.4, "marches": {"multigoals|1-3": {"niveau": 0.2, "ecart_type_ecart": 1.5, "n": 500}}}
    assert SA.probabilite(None, ("multigoals", "1-3"), HD, HE) is None
    assert SA.probabilite(w, ("double_chance", "1N"), HD, HE) is None                  # type non appris
    assert SA.probabilite(w, ("multigoals", "1-3"), HD[:3], HE) is None                # moins de 4 matchs d'une équipe : pas d'analyse
    assert 0 < SA.probabilite(w, ("multigoals", "1-3"), HD, HE) < 1


def test_solidite_plus_haute_quand_le_pari_passe_avec_plus_d_ecart():
    w = {"poids_frequence": 0.5, "poids_ecart": 0.4, "marches": {"over_under_3.5|moins": {"niveau": 1.0, "ecart_type_ecart": 1.5, "n": 500}}}
    mk = lambda tot: [{"marques": t // 2 + t % 2, "encaisses": t // 2} for t in tot]
    a = SA.probabilite(w, ("over_under_3.5", "moins"), mk([0, 1, 0, 1]), mk([1, 0, 1, 0]))
    b = SA.probabilite(w, ("over_under_3.5", "moins"), mk([3, 3, 3, 3]), mk([3, 3, 3, 3]))
    c = SA.probabilite(w, ("over_under_3.5", "moins"), mk([6, 5, 6, 5]), mk([5, 6, 5, 6]))
    assert a > b > c


def test_l_univers_appris_couvre_les_types_affiches():
    assert {("multigoals", "1-4"), ("multiscores", "Match nul"), ("combo", "1N+moins_4.5"), ("double_chance", "12"), ("over_under_domicile_2.5", "moins")} <= set(SA.univers())


def test_page_alpha_ajoute_la_solidite_sans_toucher_au_reste(tmp_path, monkeypatch):
    cle = ("over_under_3.5", "moins")
    w = {"poids_frequence": 0.5, "poids_ecart": 0.4, "marches": {"|".join(cle): {"niveau": 0.5, "ecart_type_ecart": 1.5, "n": 500}}}
    assert suivi._solidite(w, list(cle), HD, HE) == {"solidite": pytest.approx(SA.probabilite(w, cle, HD, HE), abs=1e-4)}
    assert suivi._solidite(None, list(cle), HD, HE) == {}                              # sans poids : aucun champ


def test_affichage_de_la_solidite_prudent_et_a_la_bonne_version():
    assert "function solidite(" in JS and JS.count('solidite(s, "') == 2
    assert "Number.isFinite(v)" in JS and "s.solidite != null" in JS                    # jamais « 0 % » quand le champ manque
    assert ".ax-mk-sol" in CSS and ".ax-resume-sol" in CSS
    assert "af-comportement.css?v=20261028a" in HTML and "archetype_comportement.js?v=20261028a" in HTML
