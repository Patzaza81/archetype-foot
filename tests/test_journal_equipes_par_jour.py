"""Journal : « Équipes à suivre » classées par jour du prochain match, une carte par match (même présentation que les moteurs)."""
import json
import pathlib
import shutil
import subprocess

import pytest

RACINE = pathlib.Path(__file__).parent.parent
JS = (RACINE / "journal.js").read_text(encoding="utf-8")
HTML = (RACINE / "journal.html").read_text(encoding="utf-8")

# Extrait les fonctions pures de regroupement / de libellé (sans le DOM) et les exécute avec Node.
DEBUT = JS.index("  var JOURS = [")
FIN = JS.index("  function blocMarches")
PURES = JS[DEBUT:FIN]


def node(script):
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def ligne(equipe, date, heure, adv, lieu, marche="Les deux équipes marquent", ligue="France : Ligue 1"):
    pm = None if date is None else dict(date=date, heure=heure, adversaire=adv, lieu=lieu)
    return dict(equipe=equipe, ligue=ligue, marche=marche, joues=8, gagnes=7, frequence=.875, prochain_match=pm)


def groupe(lignes):
    return node("function esc(t){return String(t)}\n" + PURES + "\nconsole.log(JSON.stringify(groupeParMatch(" + json.dumps(lignes) + ")))")


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")


def test_classe_par_jour_puis_par_heure_cas_qui_passent():
    g = groupe([ligne("Lens", "2026-10-17", "21:00", "Nice", "domicile"), ligne("Lyon", "2026-10-14", "22:00", "Metz", "extérieur"),
                ligne("Brest", "2026-10-14", "18:30", "Rennes", "domicile"), ligne("Lille", "2026-10-16", "20:45", "Reims", "domicile")])
    assert [(m["date"], m["heure"]) for m in g["matchs"]] == [("2026-10-14", "18:30"), ("2026-10-14", "22:00"), ("2026-10-16", "20:45"), ("2026-10-17", "21:00")]
    m = g["matchs"][1]
    assert (m["dom"], m["ext"]) == ("Metz", "Lyon")                                   # Lyon joue à l'extérieur : adversaire à domicile
    assert (g["matchs"][0]["dom"], g["matchs"][0]["ext"]) == ("Brest", "Rennes")


def test_deux_equipes_d_un_meme_match_partagent_la_carte():
    g = groupe([ligne("Brest", "2026-10-14", "18:30", "Rennes", "domicile"), ligne("Rennes", "2026-10-14", "18:30", "Brest", "extérieur"),
                ligne("Brest", "2026-10-14", "18:30", "Rennes", "domicile", marche="Ne perd pas")])
    assert len(g["matchs"]) == 1
    assert [e["equipe"] for e in g["matchs"][0]["equipes"]] == ["Brest", "Rennes"]
    assert len(g["matchs"][0]["equipes"][0]["lignes"]) == 2                           # deux marchés pour Brest dans la même carte


def test_equipes_sans_match_connu_regroupees_a_la_fin_et_cas_qui_echouent():
    g = groupe([ligne("Nantes", None, None, None, None), ligne("Brest", "2026-10-14", "18:30", "Rennes", "domicile"), ligne("Nantes", None, None, None, None, marche="Ne perd pas")])
    assert len(g["matchs"]) == 1 and [e["equipe"] for e in g["sans"]] == ["Nantes"] and len(g["sans"][0]["lignes"]) == 2
    assert groupe([])["matchs"] == [] and groupe([])["sans"] == []
    # même jour, heures différentes : deux cartes ; mêmes équipes, jours différents : deux cartes
    g2 = groupe([ligne("Brest", "2026-10-14", "18:30", "Rennes", "domicile"), ligne("Brest", "2026-10-17", "18:30", "Rennes", "domicile")])
    assert len(g2["matchs"]) == 2


def test_libelles_de_jour():
    r = node("function esc(t){return String(t)}\n" + PURES + "\nconsole.log(JSON.stringify([jourLisible('2026-10-14'), etiquetteJour('2026-10-14','2026-10-14'), "
             "etiquetteJour('2026-10-15','2026-10-14'), etiquetteJour('2026-10-17','2026-10-14'), jourLisible('2026-12-01')]))")
    assert r == ["Mer 14 oct", "Aujourd'hui · Mer 14 oct", "Demain · Jeu 15 oct", "Sam 17 oct", "Mar 1 déc"]


def test_page_utilise_la_carte_des_moteurs_et_le_drapeau():
    corps = JS[JS.index("function carteMatch"):JS.index("function afficherEquipes")]
    for classe in ("ax-carte ax-replie jr-match", "ax-ligne-match", "ax-horaire", "ax-competition", "ax-details"):
        assert classe in corps, classe
    assert "af-drapeaux-cartes.js" in HTML and '<div id="equipes" class="jr-equipes-jours">' in HTML
    assert "Match déjà commencé ou terminé" in corps                                   # match du jour déjà joué : signalé, pas masqué
    assert 'data-f="prochain"' in HTML and 'data-f="bon"' in HTML                      # filtres conservés
