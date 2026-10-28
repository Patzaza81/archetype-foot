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
    assert "--s:" in JS and "var(--s" in CSS                                       # pastille remplie à hauteur du pourcentage (lisible au premier coup d'œil)
    assert ".ax-mk > .ax-resume-texte { grid-column: 1 / -1; }" in CSS and ".ax-mk > .ax-mk-sol { grid-column: 1; grid-row: 2; }" in CSS   # grille de la ligne de marché non décalée
    assert "af-comportement.css?v=20261028b" in HTML and "archetype_comportement.js?v=20261028b" in HTML


# --- Onglet « Sélection » de l'alpha : Solidité du marché sélectionné (affichage seulement) ------------------------------------------
from datetime import datetime, timezone

from alpha_serie import selection_provisoire as SP


def _journal(tmp_path, regle="double_chance|12", mid="m1"):
    j = tmp_path / "j.jsonl"
    j.write_text(json.dumps({"type": "selection", "regle": regle, "marche": "Pas de nul (12)", "niveau": "normal", "cote": 1.3, "date": "2026-10-29", "heure": "20:00",
                             "coup_d_envoi_utc": "2026-10-29T19:00:00Z", "competition": "Test", "domicile": "A", "exterieur": "B", "match_id": mid}) + "\n", encoding="utf-8")
    return j


def _match_archive(mid="m1", n=5):
    eq = lambda dom: {"matchs": [{"date": f"2026-10-{10 + 2 * k:02d}", "domicile": dom, "buts_marques": g, "buts_encaisses": c, "adversaire": "X"}
                                 for k, (g, c) in enumerate([(1, 0), (2, 1), (0, 1), (1, 2), (3, 1)][:n])]}
    return {"match_id": mid, "date": "2026-10-29", "assemblage": {"equipe_dom": eq(True), "equipe_ext": eq(False)}}


W = {"poids_frequence": 0.5, "poids_ecart": 0.4, "marches": {"double_chance|12": {"niveau": 0.5, "ecart_type_ecart": 1.5, "n": 500}}}


def test_selection_affiche_la_solidite_quand_les_poids_et_le_match_existent(tmp_path):
    t = datetime(2026, 10, 29, 10, tzinfo=timezone.utc)
    d = SP.page(_journal(tmp_path), tmp_path / "p.json", maintenant=t, matchs=[_match_archive()], solidite=W)
    assert 0 < d["pronostics"][0]["solidite"] < 1
    assert json.loads((tmp_path / "p.json").read_text(encoding="utf-8"))["pronostics"][0]["solidite"] == d["pronostics"][0]["solidite"]


@pytest.mark.parametrize("matchs,poids", [(None, W), ([_match_archive()], None), ([_match_archive(mid="autre")], W), ([_match_archive(n=3)], W)])
def test_selection_sans_poids_sans_match_ou_avec_moins_de_4_matchs_rien_invente(tmp_path, matchs, poids):
    t = datetime(2026, 10, 29, 10, tzinfo=timezone.utc)
    d = SP.page(_journal(tmp_path), tmp_path / "p.json", maintenant=t, matchs=matchs, solidite=poids)
    assert "solidite" not in d["pronostics"][0]


def test_la_solidite_n_est_jamais_ecrite_dans_le_journal_gele(tmp_path):
    j = _journal(tmp_path)
    avant = j.read_text(encoding="utf-8")
    SP.page(j, tmp_path / "p.json", maintenant=datetime(2026, 10, 29, 10, tzinfo=timezone.utc), matchs=[_match_archive()], solidite=W)
    assert j.read_text(encoding="utf-8") == avant and "solidite" not in avant


def test_affichage_selection_solidite_prudent_et_versionne():
    js = (RACINE / "af-selection-alpha.js").read_text(encoding="utf-8")
    css = (RACINE / "af-selection-alpha.css").read_text(encoding="utf-8")
    html = (RACINE / "selection_alpha.html").read_text(encoding="utf-8")
    assert "p.solidite != null" in js and "Number.isFinite(sv)" in js and ".sa-sol" in css
    assert "af-selection-alpha.js?v=20261028b" in html and "af-selection-alpha.css?v=20261028b" in html
