"""Drapeaux du prototype d'accueil (drapeaux.js) : pays du CHAMPIONNAT seulement, jamais d'une équipe.
3 cas qui doivent donner un drapeau de pays, 3 qui ne doivent pas."""
import json
import os
import shutil
import subprocess

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = """
const fs = require("fs"); const vm = require("vm");
const ctx = {}; vm.createContext(ctx); vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const entrees = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(entrees.map(c => ctx.drapeauCompetition(c))));
"""


def drapeaux(competitions):
    if shutil.which("node") is None:
        pytest.skip("node absent")
    r = subprocess.run(["node", "-e", SCRIPT, os.path.join(RACINE, "drapeaux.js")], input=json.dumps(competitions),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def drapeau_iso(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


@pytest.mark.parametrize("competition,pays,symbole", [
    ("France : Ligue 1 McDonald's", "France", drapeau_iso("FR")),
    ("France :\n                        Ligue 3", "France", drapeau_iso("FR")),   # libellé brut Matchendirect
    ("Côte d'Ivoire : Ligue 1", "Côte d'Ivoire", drapeau_iso("CI")),
    ("Angleterre : Championnat", "Angleterre", "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"),
])
def test_drapeau_du_pays_du_championnat(competition, pays, symbole):
    r = drapeaux([competition])[0]
    assert (r["pays"], r["symbole"], r["type"]) == (pays, symbole, "pays")


@pytest.mark.parametrize("competition,type_attendu", [
    ("Europe : Ligue des Champions", "zone"),      # compétition européenne : globe, jamais le drapeau d'un club
    ("Paris FC", "aucun"),                         # pas de « Pays : » (nom d'équipe) : rien n'est deviné
    ("Irlande du Nord : IFA Premiership", "aucun"),  # pas de drapeau officiel : texte seul
    ("Atlantide : Ligue 1", "aucun"),              # pays inconnu
])
def test_pas_de_drapeau_de_pays(competition, type_attendu):
    r = drapeaux([competition])[0]
    assert r["type"] == type_attendu
    if type_attendu == "aucun":
        assert r["symbole"] == ""
