"""Harmonisation visuelle V2/V3, panier et Journal (branche de travail) : garde-fous des couches de présentation.
- af-pronostics.css ne s'applique qu'aux pages marquées af-v2 / af-v3 / af-panier / af-journal ;
- af-journal.css ne s'applique qu'au Journal (body.af-journal) ;
- il ne masque, n'ajoute ni ne déplace aucun contenu (ni display:none, ni content:, ni visibility, ni order) ;
- af-drapeaux-cartes.js ne touche qu'au libellé de compétition, jamais aux cotes, probabilités ou sélections."""
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lit(nom):
    with open(os.path.join(RACINE, nom), encoding="utf-8") as f:
        return f.read()


def regles(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def decoupe(selecteurs):
    """Sépare une liste de sélecteurs sur les virgules de premier niveau (pas celles de :is(...))."""
    parts, prof, cour = [], 0, ""
    for ch in selecteurs:
        prof += (ch == "(") - (ch == ")")
        if ch == "," and prof == 0:
            parts.append(cour.strip()); cour = ""
        else:
            cour += ch
    return [x for x in parts + [cour.strip()] if x]


def test_toutes_les_regles_sont_limitees_aux_pages_marquees():
    for selecteurs, _ in regles(lit("af-pronostics.css")):
        for s in decoupe(selecteurs):
            assert re.match(r"^(body)?:is\(\.af-v2,\.af-v3,\.af-panier,\.af-journal\)", s), s
    for selecteurs, _ in regles(lit("af-journal.css")):
        for s in decoupe(selecteurs):
            assert s.startswith("body.af-journal"), s


def test_aucun_contenu_masque_ajoute_ou_deplace():
    interdits = (r"display:none", r"visibility:", r"(?<![-\w])content:", r"(?<![-\w])order:",
                 r"position:(absolute|fixed)", r"hidden")
    for _, corps in regles(lit("af-pronostics.css")) + regles(lit("af-journal.css")):
        c = corps.replace(" ", "")
        for motif in interdits:
            assert not re.search(motif, c), (motif, corps)


@pytest.mark.parametrize("page,classe,avant", [("archetype.html", "af-v2", 'href="archetype.css'),
                                              ("pronostics_v3.html", "af-v3", 'href="archetype.css'),
                                              ("panier.html", "af-panier", 'href="archetype.css'),
                                              ("journal.html", "af-journal", 'href="journal.css')])
def test_pages_chargent_la_couche_apres_leurs_styles(page, classe, avant):
    s = lit(page)
    assert f'<body class="ax-page af-fond {classe}">' in s
    assert 'href="af-pronostics.css"' in s
    assert s.index(avant) < s.index('href="af-pronostics.css"')   # la couche vient après les styles de la page
    if page == "journal.html":
        assert s.index('href="af-pronostics.css"') < s.index('href="af-journal.css"')


def test_autres_pages_non_concernees():
    for page in ("index.html", "tickets.html", "systeme.html"):
        if os.path.exists(os.path.join(RACINE, page)):
            s = lit(page)
            assert "af-pronostics.css" not in s and "af-journal.css" not in s, page


def test_script_drapeaux_ne_touche_que_la_competition():
    js = re.sub(r"//.*", "", lit("af-drapeaux-cartes.js"))
    assert re.findall(r'querySelectorAll\("([^"]+)"\)', js) == [".ax-competition"]
    for mot in ("cote", "proba", "ax-badge", "ax-onglet", "ax-panneau", "fetch(", "localStorage", "innerHTML", ".remove("):
        assert mot not in js, mot
    assert 'setAttribute("aria-hidden", "true")' in js
