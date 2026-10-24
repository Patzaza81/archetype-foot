"""Règle définitive d'affichage du moteur alpha (24/10/2026) : cinq catégories indépendantes, cote obligatoire sauf multigoals et multiscores."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
JS = (RACINE / "archetype_comportement.js").read_text(encoding="utf-8")
HTML = (RACINE / "pronostics_comportement.html").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")


def meilleurs(match):
    """{catégorie: marché affiché ou None}, calculé par af-alpha-selection.js lui-même (node)."""
    code = (
        "const s = require(process.argv[1]); const m = JSON.parse(process.argv[2]);"
        "const out = {}; for (const c of s.CATEGORIES_ALPHA) { const b = s.meilleurAffichable(m, c); out[c.cle] = b ? b.marche : null; }"
        "out.__carte = s.carteAffichable(m); console.log(JSON.stringify(out));"
    )
    r = subprocess.run(["node", "-e", code, str(RACINE / "af-alpha-selection.js"), json.dumps(match)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def mk(marche, valeur, cote=None, cle=None):
    return {"marche": marche, "valeur": valeur, "cote": cote, "cle": cle or ["x", marche]}


def test_meilleur_avec_cote_affiche_par_categorie():
    m = {"onglets": {"buts": [mk("Plus de 1,5 buts", 0.8, 1.45), mk("Moins de 4,5 buts", 0.7, 1.30)],
                     "equipes": [mk("Victoire domicile", 0.6, 1.90)], "calibrees": [mk("Handicap +1,5 extérieur", 0.78, 1.28)]}}
    r = meilleurs(m)
    assert r["buts"] == "Plus de 1,5 buts" and r["equipes"] == "Victoire domicile" and r["calibrees"] == "Handicap +1,5 extérieur"


def test_meilleur_sans_cote_masque_la_categorie_sans_remplacant():
    m = {"onglets": {"buts": [mk("Plus de 1,5 buts", 0.8, None), mk("Moins de 4,5 buts", 0.7, 1.30)],          # le 2e a une cote : PAS affiché
                     "equipes": [mk("L'extérieur encaisse", 0.9, None)], "calibrees": [mk("Combo", 0.6, None, ["combo", "1N+moins_4.5"])]}}
    r = meilleurs(m)
    assert r["buts"] is None and r["equipes"] is None and r["calibrees"] is None and r["__carte"] is False


def test_multigoals_et_multiscores_sans_cote_affiches():
    m = {"onglets": {"buts": [mk("Plus de 1,5 buts", 0.6, None), mk("Multigoals 1-4", 0.58, None, ["multigoals", "1-4"])],
                     "multiscores": [mk("Match nul", 0.33, None, ["multiscores", "Match nul"])]}}
    r = meilleurs(m)
    assert r["multigoals"] == "Multigoals 1-4" and r["multiscores"] == "Match nul" and r["buts"] is None and r["__carte"] is True


def test_aucun_classement_entre_categories():
    # Équipes à 95 % ne masque pas Buts à 55 % : chaque catégorie garde son meilleur marché
    m = {"onglets": {"buts": [mk("Plus de 2,5 buts", 0.55, 1.70)], "equipes": [mk("Handicap +1,5 domicile", 0.95, 1.26)],
                     "calibrees": [mk("Victoire extérieur", 0.42, 2.10)]}}
    r = meilleurs(m)
    assert r["buts"] == "Plus de 2,5 buts" and r["equipes"] == "Handicap +1,5 domicile" and r["calibrees"] == "Victoire extérieur"


def test_multigoal_separe_des_buts():
    m = {"onglets": {"buts": [mk("Multigoals 2-4", 0.9, None, ["multigoals", "2-4"]), mk("Plus de 1,5 buts", 0.7, 1.40)]}}
    r = meilleurs(m)
    assert r["buts"] == "Plus de 1,5 buts" and r["multigoals"] == "Multigoals 2-4"      # le multigoal ne prend pas la place du meilleur « Buts »


def test_doublons_retires_dans_la_categorie_seulement():
    code = ("const s = require(process.argv[1]); const m = JSON.parse(process.argv[2]);"
            "console.log(JSON.stringify(s.CATEGORIES_ALPHA.map((c) => s.lignesCategorie(m, c).length)));")
    m = {"onglets": {"equipes": [mk("Victoire domicile", 0.6, 1.9, ["1x2", "1"]), mk("Victoire domicile", 0.6, 1.9, ["1x2", "1"])],
                     "calibrees": [mk("Victoire domicile", 0.45, 1.9, ["1x2", "1"])]}}
    r = subprocess.run(["node", "-e", code, str(RACINE / "af-alpha-selection.js"), json.dumps(m)], capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == [0, 0, 1, 0, 1]                                    # 1 dans Équipes, et toujours 1 dans Calibrés


def test_cote_invalide_traitee_comme_absente():
    for cote in (None, "", 0, 1.0, "abc"):
        assert meilleurs({"onglets": {"buts": [mk("Plus de 1,5 buts", 0.8, cote)]}})["buts"] is None


def test_page_branchee_sur_la_regle():
    assert HTML.index("af-alpha-selection.js") < HTML.index("archetype_comportement.js")
    assert "CATEGORIES_ALPHA.forEach" in JS and "meilleurAffichable(m, cat)" in JS and "carteAffichable(m)" in JS
    assert "NOMS_ONGLETS" not in JS
