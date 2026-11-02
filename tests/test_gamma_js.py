"""Page Gamma = Omega V3 : exécute archetype_gamma.js sous Node avec un document factice (affichages, vocabulaire, aucune probabilité inventée)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")

SCRIPT = """
global.document = {getElementById: () => null, body: {classList: {toggle() {}}}, createElement: () => ({})};
global.window = {};
const g = require(process.argv[1]);
const [fn, ...args] = JSON.parse(process.argv[2]);
console.log(JSON.stringify(g[fn](...args)));
"""


def appel(fn: str, *args):
    r = subprocess.run(["node", "-e", SCRIPT, str(ROOT / "archetype_gamma.js"), json.dumps([fn, *args])], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


F = {"domicile": "Arezzo", "exterieur": "Ascoli"}
PARI = {"k": 400, "n": 625, "f": 0.64, "g": 0.6, "seuil": 0.55, "p_calibree": 0.72, "cote": 1.4, "p_implicite": 0.714, "ev": 0.008,
        "niveaux": {"strict": {"k": 30, "n": 50, "f": 0.6}, "intermediaire": {"k": 100, "n": 200, "f": 0.5}, "elargi": {"k": 300, "n": 500, "f": 0.6, "faible": True}},
        "stabilite": {"f_min": 0.6, "f_max": 0.66}, "diversite": {}}


@pytest.mark.parametrize("cle,attendu", [
    (["1x2", "1"], "Victoire Arezzo"), (["1x2", "N"], "Match nul"), (["double_chance", "1N"], "Arezzo ou match nul"),
    (["btts", "Oui"], "Les deux équipes marquent"), (["over_under_2.5", "plus"], "Plus de 2,5 buts"),
])
def test_phrase_des_marches_qui_passent(cle, attendu):
    assert attendu in appel("gaPhrase", cle, "Arezzo", "Ascoli")["titre"]


@pytest.mark.parametrize("cle,interdit", [(["1x2", "1"], "Ascoli"), (["over_under_2.5", "plus"], "Moins de"), (["over_under_2.5", "moins"], "Plus de")])
def test_phrase_des_marches_qui_ne_doivent_pas_apparaitre(cle, interdit):
    assert interdit not in appel("gaPhrase", cle, "Arezzo", "Ascoli")["titre"]


def test_frequence_jamais_presentee_comme_une_probabilite():
    t = appel("gaFreqPari", PARI, F)
    assert "400 scénarios sur 625" in t and "n'est pas une probabilité" in t and "Fréquence robuste" in t
    assert "trop peu représenté" in t and "BetPawa" not in t
    assert "information" in t                                                          # l'EV n'est jamais un critère
    assert appel("gaFreqPari", None, F) == ""


def test_ev_affichee_et_signe():
    assert "+0,8" in appel("gaEv", {"ev": 0.008}) and "−3,0" in appel("gaEv", {"ev": -0.03})
    assert appel("gaEv", {}) == "" and appel("gaEv", None) in ("", None)


def test_statuts_et_aucun_mot_betpawa():
    assert "retenu" in appel("gaStatut", 6) and appel("gaStatut", 99) == "—"
    assert all("BetPawa" not in appel("gaStatut", c) for c in range(8))


def test_sequences_affichees_et_absentes():
    f = {**F, "donnees": {"sequences": {"att_a": [2, 1, 0, 1, 3], "def_a": [0] * 5, "att_b": [1] * 5, "def_b": [2] * 5}, "source": "archive"}}
    t = appel("gaSequences", f)
    assert "[2, 1, 0, 1, 3]" in t and "5 matchs" in t and "pas des matchs indépendants" in t
    assert appel("gaSequences", F) == ""


def test_exploration_et_tous_marches_sans_donnees_ne_cassent_pas():
    assert appel("gaExploration", F) == "" and appel("gaTousMarches", F) == ""
    assert appel("gaSurveiller", F) == ""
    x = {**F, "exploration": {"combinaisons": 625, "scores_distincts": 12, "issues": {"A": 300, "N": 100, "B": 225}, "concentration_top3": 0.4,
                              "top_scores": [{"score": "2-1", "occurrences": 100, "f": 0.16}]},
         "niveaux": {"strict": {"n": 50, "part": 0.08}, "incompatible": {"n": 0, "part": 0}}}
    t = appel("gaExploration", x)
    assert "625 scénarios" in t and "Victoire de Arezzo" in t and "jamais un pronostic retenu" in t
