"""Présentation commune « nom du marché + phrase simple dessous » (22/10/2026) : 3+ cas qui passent, 3+ qui échouent,
et preuve que rien d'autre ne change (traduitMarche inchangée, aucune donnée touchée, pages bien câblées)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
EQ = '{domicile:"Madura",exterieur:"Bali"}'

HELPER = """
const vm=require('vm'),fs=require('fs');
const ctx={window:{},document:{getElementById:()=>({}),head:{appendChild(){}},createElement:()=>({})}};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(fs.readFileSync('af-marche-affichage.js','utf8'),ctx);
const f=ctx.afMarcheHtml;
"""


def node(code: str):
    return json.loads(subprocess.run(["node", "-e", code], cwd=RACINE, capture_output=True, text=True, check=True).stdout)


def html(titre, expl):
    return node(HELPER + f"console.log(JSON.stringify(f({json.dumps(titre)},{json.dumps(expl)})))")


def nom(m):
    return node(f'const t=require("./traduction_marches.js");console.log(JSON.stringify(t.nomOrigineMarche({json.dumps(m)},{EQ})))')


def phrase(m):
    return node(f'const t=require("./traduction_marches.js");console.log(JSON.stringify(t.traduitMarche({json.dumps(m)},{EQ})))')


# ── Doivent donner « nom + explication » ──
@pytest.mark.parametrize("marche,titre,explication", [
    ("over_under_total_5.5_over", "Plus de 5.5 buts", "Au moins 6 buts dans le match"),
    ("over_under_total_2.5_under", "Moins de 2.5 buts", "2 buts au maximum dans le match"),
    ("btts_oui", "BTTS - oui", "Les deux équipes marquent"),
    ("handicap_exterieur_-0.5", "Handicap -0.5 - Extérieur", "Bali gagne (handicap -0,5)"),
    ("buts_equipe_domicile_1.5_over", "Madura marque +1.5 buts", "Madura marque au moins 2 buts"),
])
def test_cas_qui_passent(marche, titre, explication):
    assert nom(marche) == titre
    assert phrase(marche) == explication
    h = html(titre, explication)
    assert '<span class="mk-nom">' + titre + "</span>" in h and '<small class="mk-expl">' + explication + "</small>" in h


# ── Ne doivent PAS fabriquer d'explication ou de doublon ──
def test_nom_identique_a_l_explication_une_seule_ligne():
    assert "mk-expl" not in html("Victoire Madura", "Victoire Madura")
    assert "mk-expl" not in html("Plus de 2.5 buts", "Plus de 2,5 buts")        # point/virgule : même texte


def test_sans_explication_nom_seul():
    assert "mk-expl" not in html("1:0 / 2:0 / 3:0", "")
    assert "mk-expl" not in html("Marché inconnu", None)


def test_sans_titre_l_explication_devient_le_titre():
    h = html("", "Au moins 3 buts dans le match")
    assert 'mk-nom">Au moins 3 buts dans le match<' in h and "mk-expl" not in h


def test_html_echappe():
    h = html('<img src=x onerror=alert(1)>', 'a "b" & <c>')
    assert "<img" not in h and "&lt;img" in h and "&amp;" in h and "&quot;" in h


def test_marche_inconnu_garde_son_texte():
    assert nom("truc_bizarre") == "truc bizarre" and phrase("truc_bizarre") == "truc bizarre"


def test_traduitMarche_est_inchangee_pour_tous_les_marches_connus():
    """Les phrases existantes ne bougent pas (la présentation ajoute, ne remplace pas)."""
    attendu = {"1x2_domicile": "Victoire Madura", "double_chance_X2": "Bali ne perd pas", "btts_non": "Une des deux équipes ne marque pas",
               "over_2_5": "Au moins 3 buts dans le match", "cage_inviolee_domicile": "Madura garde sa cage inviolée"}
    for m, p in attendu.items():
        assert phrase(m) == p


# ── Câblage des pages ──
PAGES_AVEC_TRADUCTION = ["archetype.html", "pronostics_v3.html", "pronostics_europe.html", "pronostics_v.html", "panier.html", "journal.html", "tickets.html"]


@pytest.mark.parametrize("page", PAGES_AVEC_TRADUCTION + ["pronostics_comportement.html"])
def test_page_charge_la_presentation_avant_les_scripts_de_rendu(page):
    s = (RACINE / page).read_text(encoding="utf-8")
    scripts = [re.sub(r"\?.*$", "", x) for x in re.findall(r'<script src="([^"]+)"', s)]
    assert "af-marche-affichage.js" in scripts
    i = scripts.index("af-marche-affichage.js")
    rendu = [x for x in scripts if x.startswith(("archetype", "journal", "tickets")) and x != "archetype_v2r.js"]
    assert all(scripts.index(x) > i for x in rendu), page
    if page in PAGES_AVEC_TRADUCTION:
        assert i < scripts.index("traduction_marches.js")


@pytest.mark.parametrize("script,appel", [
    ("archetype.js", "marcheAvecExplication(nomOrigineMarche("), ("archetype_v3.js", "marcheV3Html("), ("archetype_europe.js", "marcheV3Html("),
    ("archetype_v.js", "marcheAvecExplication(p.marche"), ("archetype_comportement.js", "afMarcheHtml(s.marche"),
    ("journal.js", "marcheHtml("), ("tickets.js", "marcheTicketHtml("), ("meilleures_selections.js", "afMarcheHtml("),
])
def test_chaque_affichage_utilise_la_presentation_commune(script, appel):
    assert appel in (RACINE / script).read_text(encoding="utf-8")


def test_aucun_calcul_dans_le_fichier_de_presentation():
    s = (RACINE / "af-marche-affichage.js").read_text(encoding="utf-8")
    assert not re.search(r"fetch\(|XMLHttpRequest|Math\.|probabilit|cote", s)
