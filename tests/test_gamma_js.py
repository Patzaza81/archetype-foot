"""Page Gamma (audit du 01/11/2026) : k/n séparés, EV, panneau « Détail du calcul ». Exécute archetype_gamma.js sous Node avec un document factice."""
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


F = {"domicile": "Arezzo", "exterieur": "Ascoli", "n_domicile": 4, "n_exterieur": 4}
PR = {"dom": {"k": 4, "n": 4, "wilson": [0.51, 1.0]}, "ext": {"k": 3, "n": 4, "wilson": [0.30, 0.95]},
      "estimation": {"p": 0.6944, "ic": [0.47, 0.92], "methode": "x"}}


def test_deux_populations_affichees_separement_jamais_7_sur_8():
    t = appel("gaPops", PR, F, False)
    assert "4 sur 4" in t and "3 sur 4" in t and "7 sur 8" not in t
    assert "Estimation combinée" in t and "pas une fréquence observée" in t
    assert "7 sur 8" not in appel("gaPreuve", {"p": 0.82, "cote": 1.33, "ev": 0.09, "base": 0.63, "edge": 0.19, "seuil": 0.75, "preuve": PR}, F)
    assert appel("gaPops", {"k": 7, "n": 8}, F, False) == ""                         # ancienne ligne gelée (k/n additionné) : plus rien d'affiché
    assert appel("gaPops", None, F, False) == ""


def test_ev_affichee_et_signe():
    assert "+9,1" in appel("gaEv", {"ev": 0.091}) and "−3,0" in appel("gaEv", {"ev": -0.03})
    assert appel("gaEv", {}) == ""


def test_panneau_detail_du_calcul_avec_et_sans_decomposition():
    d = {"lambda_dom": {"niveau_ligue": 1.359, "avantage_terrain": 0.985, "attaque_dom": 0.9, "faiblesse_defensive_ext": 0.823, "valeur": 0.991},
         "lambda_ext": {"niveau_ligue": 1.359, "attaque_ext": 1.136, "faiblesse_defensive_dom": 1.236, "valeur": 1.909},
         "moyennes_ligue": {"buts_dom": 1.383, "buts_ext": 1.333, "n_matchs": 81},
         "shrinkage": {"sigma": 0.25, "xi": 0.004, "n_matchs_equipe_dom": 9, "n_matchs_equipe_ext": 9}, "effets_modules": {"dom": 1.0, "ext": 1.0, "rho_final": -0.07}}
    h = appel("gaDecomposition", {**F, "decomposition": d})
    for mot in ("Détail du calcul", "Avantage du terrain", "Force d'attaque de Arezzo", "Faiblesse défensive de Ascoli", "0,991", "1,909", "σ = 0,25", "81 matchs"):
        assert mot in h
    assert "non gelée" in appel("gaDecomposition", F)
    assert "non gelée" in appel("gaDecomposition", {**F, "decomposition": {}})
