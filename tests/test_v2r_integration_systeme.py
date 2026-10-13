"""Branchement de v2r dans ARCHETYPE : page, menu, crochet nocturne isolé."""
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import execution as X  # noqa: E402

RACINE = pathlib.Path(__file__).parent.parent
PAGES_AVEC_MENU = ["index.html", "journal.html", "panier.html", "archetype.html", "pronostics_v3.html", "pronostics_europe.html"]


def test_page_v2r_branchee_sur_le_fichier_de_donnees():
    h = (RACINE / "pronostics_v2r.html").read_text(encoding="utf-8")
    js = (RACINE / "archetype_v2r.js").read_text(encoding="utf-8")
    assert "archetype_v2r.js" in h and "data/v2r/pronostics_v2r.json" in js
    assert "data/v3" not in js and "data/europe" not in js and "archetype_v3" not in h


def test_menu_contient_v2r_dans_toutes_les_pages():
    for f in PAGES_AVEC_MENU:
        assert 'href="pronostics_v2r.html"' in (RACINE / f).read_text(encoding="utf-8"), f


def test_passage_nocturne_jamais_bloquant():
    r = X.passage_nocturne(dossier="/proc/inexistant/v2r")    # sortie illisible : un texte, jamais une exception
    assert isinstance(r, str) and r.startswith("v2r indisponible")


def test_passage_nocturne_ecrit_seulement_son_dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(X, "charge", lambda a_venir=False: [])
    r = X.passage_nocturne(dossier=str(tmp_path / "v2r"))
    assert isinstance(r, dict) and r["a_venir"] == 0 and r["statut"] == "observation"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["v2r"]


def test_tache_nocturne_appelle_v2r_dans_un_try():
    src = (RACINE / "enregistre_scores_historique.py").read_text(encoding="utf-8")
    i = src.index("from moteur_v2r.execution import passage_nocturne")
    assert "try:" in src[i - 200:i] and "except Exception" in src[i:i + 400]
    assert src.index("archive_donnees_test.execution_nocturne()") < i      # après l'archive dont v2r lit les données


def test_fichier_publie_a_les_champs_lus_par_la_page():
    import json
    d = json.load(open(RACINE / "data" / "v2r" / "pronostics_v2r.json"))
    for k in ("statut", "bilan", "regles_version", "regles_cellules", "a_venir", "en_cours", "reglees", "genere_le"):
        assert k in d, k
    for l in d["a_venir"]:
        for k in ("competition", "domicile", "exterieur", "marche", "cote", "coup_d_envoi_utc", "roi_cellule", "buts_attendus"):
            assert k in l, k
