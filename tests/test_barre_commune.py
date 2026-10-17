"""Barre de navigation commune (branche accueil-prototype) sur les pages V2, V3, Journal et panier.
Garde-fous : la barre est présente, le bouton de thème garde l'id lu par archetype.js / archetype_v3.js / journal.js,
et les scripts de la page sont exactement ceux d'avant (aucune fonctionnalité retirée ou ajoutée)."""
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_ATTENDUS = {
    "archetype.html": ["traduction_marches.js", "ui_mappings.js", "archetype.js"],
    "pronostics_v3.html": ["traduction_marches.js", "ui_mappings.js", "archetype_v3.js"],
    "journal.html": ["journal.js"],
    "panier.html": ["traduction_marches.js", "ui_mappings.js", "archetype.js", "panier.js"],
}
PAGES = ["archetype.html", "pronostics_v3.html", "journal.html", "panier.html"]


def lit(page):
    with open(os.path.join(RACINE, page), encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("page", PAGES)
def test_barre_commune_presente_et_bouton_de_theme_conserve(page):
    s = lit(page)
    assert s.count('class="af-barre"') == 1
    assert s.count('id="ax-bouton-theme"') == 1          # id lu par le script de la page pour le mode nuit
    assert 'href="af-barre.css"' in s
    assert 'class="ax-barre"' not in s                   # ancienne barre retirée, pas dupliquée
    if page != "panier.html":                            # le panier n'est pas dans la navigation (page hors menu)
        assert f'href="{page}" aria-current="page"' in s  # page courante signalée dans la navigation


@pytest.mark.parametrize("page", PAGES)
def test_liens_de_la_barre_vers_des_pages_existantes(page):
    barre = re.search(r'<div class="af-barre">.*?</div>\n</div>', lit(page), re.S).group(0)
    for h in re.findall(r'href="([^"]+\.html)"', barre):
        assert os.path.exists(os.path.join(RACINE, h)), h


# Seuls ajouts autorisés : la couche de présentation des drapeaux (harmonisation V2/V3), chargée APRÈS
# les scripts métier (V2, V3, Journal, panier). Aucun script métier ne change, ni d'ordre ni de nom.
PRESENTATION_AUTORISEE = {
    "archetype.html": ["drapeaux.js", "af-drapeaux-cartes.js", "af-date-navigation.js"],
    "pronostics_v3.html": ["drapeaux.js", "af-drapeaux-cartes.js", "af-date-navigation.js"],
    "journal.html": ["drapeaux.js", "af-drapeaux-cartes.js"],
    "panier.html": ["drapeaux.js", "af-drapeaux-cartes.js"],
}


@pytest.mark.parametrize("page,attendus", SCRIPTS_ATTENDUS.items())
def test_scripts_de_la_page_inchanges(page, attendus):
    scripts = [re.sub(r"\?.*$", "", x) for x in re.findall(r'<script src="([^"]+)"', lit(page))]
    assert scripts == attendus + PRESENTATION_AUTORISEE.get(page, [])


def test_accueil_publie_et_ancienne_adresse_redirigee():
    """La nouvelle page d'accueil est index.html : plus de mention « prototype », indexable, et l'ancienne
    adresse accueil-prototype.html renvoie vers l'accueil. Les liens de l'ancien accueil restent tous présents."""
    s = lit("index.html")
    assert "non publié" not in s and 'content="noindex"' not in s
    assert "<title>Archetype Foot</title>" in s
    for h in ("archetype.html", "pronostics_v3.html", "tickets.html", "journal.html", "systeme.html",
              "corners_cartons.html", "compte.html", "abonnement.html"):
        assert f'href="{h}"' in s, h
    assert 'url=index.html' in lit("accueil-prototype.html")
    for page in PAGES:
        assert 'href="accueil-prototype.html"' not in lit(page), page
