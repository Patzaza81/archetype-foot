"""Affichage de la page Moteur alpha (22/10/2026) : pronostics visibles dès l'entrée, lisibles sur téléphone."""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
JS = (RACINE / "archetype_comportement.js").read_text(encoding="utf-8")
CSS = (RACINE / "af-comportement.css").read_text(encoding="utf-8")
HTML = (RACINE / "pronostics_comportement.html").read_text(encoding="utf-8")


def test_pas_de_tableau_html():
    assert "<table" not in JS and "<th" not in JS and "<td" not in JS


def test_apercu_replie_et_lignes_par_marche():
    for classe in ("ax-resume", "ax-mk-liste", "ax-mk-alerte", "ax-resume-alerte"):
        assert classe in JS


def test_alerte_visible_pas_seulement_infobulle():
    assert "ax-mk-alerte" in JS and ".ax-mk-alerte" in CSS


def test_nom_de_marche_peut_passer_a_la_ligne():
    bloc = re.search(r"\.ax-mk-nom\s*\{([^}]*)\}", CSS).group(1)
    assert "nowrap" not in bloc


def test_aucun_masquage_et_portee_alpha():
    assert "display:none" not in CSS.replace(" ", "")
    sans_commentaires = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for selecteur in re.findall(r"^([^{}@\n][^{}]*)\{", sans_commentaires, flags=re.M):
        assert all(s.strip().startswith("body.af-alpha") for s in selecteur.split(",")), selecteur


def test_versions_de_cache_dans_la_page():
    assert re.search(r"af-comportement\.css\?v=\d", HTML)
    assert re.search(r"archetype_comportement\.js\?v=\d", HTML)
