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


def test_principal_sans_cote_remplace_par_le_meilleur_inferieur_cote():
    m = {"onglets": {"buts": [mk("Plus de 1,5 buts", 0.8, None), mk("Moins de 4,5 buts", 0.7, 1.30), mk("Plus de 2,5 buts", 0.6, 1.80)],
                     "equipes": [mk("L'extérieur encaisse", 0.9, None)], "calibrees": [mk("Combo", 0.6, None, ["combo", "1N+moins_4.5"])]}}
    r = meilleurs(m)
    assert r["buts"] == "Moins de 4,5 buts"                                            # le meilleur inférieur coté, pas le suivant
    assert r["equipes"] is None and r["calibrees"] is None and r["__carte"] is True    # aucun marché coté : catégorie masquée


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
    assert "CATEGORIES_ALPHA.map((cat, i)" in JS and "meilleurAffichable(m, parCle[k])" in JS and "carteAffichable(m)" in JS
    assert "NOMS_ONGLETS" not in JS


# --- 24/10/2026 : aucun pronostic sans cote, même dans les onglets dépliés (sauf multigoals et multiscores) ----------
def affiches(match):
    code = ("const s = require(process.argv[1]); const m = JSON.parse(process.argv[2]);"
            "const o = {}; for (const c of s.CATEGORIES_ALPHA) o[c.cle] = s.marchesAffiches(m, c).map((x) => x.marche); console.log(JSON.stringify(o));")
    r = subprocess.run(["node", "-e", code, str(RACINE / "af-alpha-selection.js"), json.dumps(match)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def test_onglet_deplie_seulement_les_marches_avec_cote():
    m = {"onglets": {"calibrees": [mk("A", 0.9, 1.40), mk("B", 0.8, None), mk("C", 0.7, 1.30), mk("D", 0.6, None, ["combo", "1N+moins_4.5"])],
                     "equipes": [mk("E", 0.9, 1.50), mk("F", 0.8, "")], "buts": [mk("G", 0.9, 1.6), mk("H", 0.5, 1.0)]}}
    r = affiches(m)
    assert r["calibrees"] == ["A", "C"] and r["equipes"] == ["E"] and r["buts"] == ["G"]       # B, D, F, H (sans cote valable) jamais montrés


def test_onglet_garde_les_marches_cotes_quand_le_principal_est_sans_cote():
    m = {"onglets": {"calibrees": [mk("L'extérieur encaisse", 0.86, None), mk("Moins de 2,5 buts", 0.5, 1.79)],
                     "equipes": [mk("Handicap +1,5 extérieur", 0.92, None), mk("Handicap +1,5 domicile", 0.83, 1.26)],
                     "buts": [mk("Plus de 1,5 buts", 0.8, None)]}}
    r = affiches(m)
    assert r["calibrees"] == ["Moins de 2,5 buts"] and r["equipes"] == ["Handicap +1,5 domicile"] and r["buts"] == []


def test_remplacement_signale():
    code = ("const s = require(process.argv[1]); const m = JSON.parse(process.argv[2]);"
            "console.log(JSON.stringify(s.CATEGORIES_ALPHA.map((c) => s.estRemplacant(m, c))));")
    m = {"onglets": {"buts": [mk("Plus de 1,5 buts", 0.8, None), mk("Plus de 2,5 buts", 0.6, 1.7)],
                     "equipes": [mk("Victoire domicile", 0.7, 1.9)], "multiscores": [mk("Match nul", 0.3, None, ["multiscores", "Match nul"])]}}
    r = subprocess.run(["node", "-e", code, str(RACINE / "af-alpha-selection.js"), json.dumps(m)], capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == [True, False, False, False, False]                  # seul « Buts » est un remplacement
    assert "estRemplacant(m, cat)" in JS


def test_multigoals_multiscores_sans_cote_dans_l_onglet():
    m = {"onglets": {"buts": [mk("Multigoals 1-4", 0.58, None, ["multigoals", "1-4"]), mk("Multigoals 2-5", 0.5, None, ["multigoals", "2-5"])],
                     "multiscores": [mk("Match nul", 0.33, None, ["multiscores", "Match nul"])]}}
    r = affiches(m)
    assert r["multigoals"] == ["Multigoals 1-4", "Multigoals 2-5"] and r["multiscores"] == ["Match nul"]


def test_page_utilise_les_marches_affiches():
    assert "marchesAffiches(m, cat)" in JS and "<strong>à lire</strong>" not in JS


# --- 24/10/2026 : plaque compacte, repli / dépli au toucher n'importe où ---------------------------------------------
def test_carte_repliee_compacte():
    assert 'let choisies = ["buts", "equipes"].filter((k) => meilleurAffichable(m, parCle[k]));' in JS
    assert 'choisies = ["multigoals", "multiscores", "calibrees"].filter((k) => meilleurAffichable(m, parCle[k])).slice(0, 1);' in JS
    corps = JS.split("function construitResume(m) {")[1].split("function listeMatchs")[0]
    assert "pourquoiCourt" not in corps                                           # aucune phrase longue sur la carte repliée


def test_repli_depli_au_toucher_partout():
    assert 'if (e.target.closest("[role=tab], a")) return;' in JS                  # seuls les onglets et les liens gardent leur action
    assert "ax-bouton-replier" not in JS and "ax-bouton-details" not in JS          # plus de boutons « Replier » / « Détails »
    assert "if (onglets.parentNode) onglets.remove();" in JS                       # onglets seulement carte dépliée
