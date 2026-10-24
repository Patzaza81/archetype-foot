"""Libellés de marchés en mots simples (22/10/2026) : 3 cas qui doivent passer, 3 qui doivent rester inchangés ou échouer."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")


def node(code: str):
    sortie = subprocess.run(["node", "-e", code], cwd=RACINE, capture_output=True, text=True, check=True).stdout
    return json.loads(sortie)


def clair(texte):
    return node(f'const t=require("./traduction_marches.js");console.log(JSON.stringify(t.clarifieLibelle({json.dumps(texte)},{{domicile:"Madura",exterieur:"Bali"}})))')


def titre(marche):
    return node(f'const t=require("./traduction_marches.js");console.log(JSON.stringify(t.traduitMarche({json.dumps(marche)},{{domicile:"Madura",exterieur:"Bali"}})))')


def alpha(marche):
    code = ('const fs=require("fs");const s=fs.readFileSync("archetype_comportement.js","utf8");'
            'const i=s.indexOf("const butsN"),j=s.indexOf("// Marchés d\'un onglet");eval(s.slice(i,j)+";global.L=libelleClair");'
            f'console.log(JSON.stringify(L({json.dumps(marche)},"Madura","Bali")))')
    return node(code)


# ── Doivent passer ──
def test_totaux_en_buts_entiers():
    assert titre("over_under_total_2.5_over") == "Au moins 3 buts dans le match"
    assert titre("over_under_total_2.5_under") == "2 buts au maximum dans le match"
    assert clair("Plus de 1,5 buts") == "Au moins 2 buts dans le match"


def test_buts_par_equipe_et_handicap():
    assert titre("buts_equipe_domicile_1.5_over") == "Madura marque au moins 2 buts"
    assert titre("buts_equipe_exterieur_0.5_under") == "Bali ne marque pas"
    assert titre("handicap_exterieur_1.5") == "Bali ne perd pas par 2 buts d'écart ou plus (handicap +1,5)"


def test_alpha_multigoals_multiscores():
    assert alpha("Multigoals 2-4") == "Entre 2 et 4 buts dans le match"
    assert alpha("2:1 / 3:1 / 4:1") == "Madura gagne 2-1, 3-1 ou 4-1"
    assert alpha("0:1 / 0:2 / 0:3").startswith("Bali gagne 1-0, 2-0 ou 3-0")
    assert alpha("Match nul").startswith("Match nul (égalité")


# ── Doivent rester tels quels (jamais devinés) ──
def test_libelles_inconnus_inchanges():
    assert clair("Truc inconnu 7") == "Truc inconnu 7"
    assert alpha("Multigoals A-B") == "Multigoals A-B"
    assert alpha("Handicap 3 issues domicile +1 : nul") == "Handicap 3 issues domicile +1 : nul"


def test_aucune_formule_ambigue_restante():
    for m in ("over_under_total_3.5_over", "buts_equipe_domicile_2.5_over", "handicap_domicile_-1.5"):
        assert "Plus de" not in titre(m) and "Moins de" not in titre(m)


def test_alpha_moins_de_pas_plus_de():
    assert alpha("Moins de 2,5 buts") == "Pas plus de 2,5 buts dans le match"
    assert alpha("Moins de 3,5 buts") == "Pas plus de 3,5 buts dans le match"
    assert alpha("Moins de 2,5 buts du domicile") == "Madura ne marque pas plus de 2,5 buts"
    assert alpha("Moins de 0,5 buts") == "Aucun but dans le match"
    assert alpha("Moins de 0,5 buts de l'extérieur") == "Bali ne marque pas"
    assert alpha("Plus de 1,5 buts") == "Au moins 2 buts dans le match"
