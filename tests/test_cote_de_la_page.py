"""Côté de l'équipe propriétaire d'une page d'équipe (correctif du 01/11/2026).

Avant : 'Cali' est contenu dans 'America Cali' -> sur la page d'America Cali, le match Cali - America Cali était lu avec
America Cali à DOMICILE (copie de l'enregistrement de Cali) ; idem Cerro / Cerro Largo. Après : égalité exacte d'abord,
ressemblance seulement si elle désigne un seul côté, sinon la ligne est ignorée."""
import datetime
import json
import os

import pytest
from bs4 import BeautifulSoup

import scraper_details as sd

DIAG = os.path.join(os.path.dirname(__file__), "..", "diagnostic", "pages")
REF = datetime.date(2026, 9, 24)


# --- côté décidé (6 cas) -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("equipe,dom,ext,attendu", [
    ("America Cali", "Cali", "America Cali", "ext"),            # le bug d'origine
    ("Cerro", "Cerro Largo", "Cerro", "ext"),                    # idem
    ("Cali", "Cali", "America Cali", "dom"),
    ("Cerro", "Cerro", "Cerro Largo", "dom"),
    ("Real Madrid", "Real Madrid Castilla", "Real Madrid", "ext"),
    ("Audace Cerignola", "Audace Cerig", "Cosenza", "dom"),      # ressemblance sur un seul côté : comportement antérieur conservé
])
def test_le_cote_est_decide(equipe, dom, ext, attendu):
    assert sd._cote_de_la_page(equipe, dom, ext) == attendu


# --- ligne ignorée (4 cas) ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("equipe,dom,ext", [
    ("Union Berlin", "Union", "Berlin"),                         # ressemble aux deux côtés, aucune égalité exacte
    ("Atletico Madrid Fem", "Atletico", "Madrid"),
    ("Alpha", "Beta", "Gamma"),                                  # aucun côté
    ("Wil", "Wil", "Wil"),                                       # égalité exacte des deux côtés
])
def test_la_ligne_ambigue_est_ignoree(equipe, dom, ext):
    assert sd._cote_de_la_page(equipe, dom, ext) is None


# --- lecture complète d'une page ---------------------------------------------------------------------------------------
def page(competition, lignes):
    rows = "".join(f'<tr><td class="lm2"><span class="lm2_time">{d}</span></td><td><a href="/live-score/x-y_{i * 25}.html">{t}</a></td></tr>'
                   for i, (d, t) in enumerate(lignes))
    return BeautifulSoup(f"<html><body><h3>{competition}</h3><table>{rows}</table></body></html>", "html.parser")


def lit(soup, competition, equipe):
    return [(m["domicile"], m["adversaire"], m["buts_marques"], m["buts_encaisses"])
            for m in sd._extrait_historique_competition(soup, competition, equipe, date_reference=REF)]


def test_america_cali_voit_le_match_a_l_exterieur():
    s = page("Colombie : Première A Cloture", [("26/04", "Cali 1 - 0 America Cali")])
    assert lit(s, "colombie : première a cloture", "America Cali") == [(False, "Cali", 0, 1)]


def test_cali_voit_le_meme_match_a_domicile():
    s = page("Colombie : Première A Cloture", [("26/04", "Cali 1 - 0 America Cali")])
    assert lit(s, "colombie : première a cloture", "Cali") == [(True, "America Cali", 1, 0)]


def test_cerro_et_cerro_largo():
    comp = "Uruguay : Primera Division Cloture"
    s = page(comp, [("29/05", "Cerro Largo 2 - 0 Cerro"), ("16/10", "Cerro 1 - 1 Cerro Largo")])
    assert lit(s, comp.lower(), "Cerro") == [(False, "Cerro Largo", 0, 2), (True, "Cerro Largo", 1, 1)] or \
        sorted(lit(s, comp.lower(), "Cerro")) == sorted([(False, "Cerro Largo", 0, 2), (True, "Cerro Largo", 1, 1)])


def test_une_ligne_ambigue_n_entre_pas_dans_l_historique():
    comp = "Allemagne : Bundesliga"
    s = page(comp, [("01/09", "Union 2 - 1 Berlin"), ("08/09", "Union Berlin 3 - 0 Bayern")])
    assert lit(s, comp.lower(), "Union Berlin") == [(True, "Bayern", 3, 0)]


def test_un_match_ordinaire_est_inchange():
    comp = "Italie : Série C"
    s = page(comp, [("22/08", "Audace Cerig. 3 - 1 Cosenza")])
    assert lit(s, comp.lower(), "Cosenza") == [(False, "Audace Cerig.", 1, 3)]


# --- vraies pages capturées : résultat identique à celui d'avant le correctif ----------------------------------------------
PAGES = [("colwyn_bay", "pays de galles : cymru premier", "colwyn bay", 10), ("aston_villa", "angleterre : femmes super ligue", "aston villa", 3),
         ("cosenza", "italie : série c girone a", "cosenza", 6), ("pineto", "italie : série c girone a", "pineto", 6),
         ("salernitana", "italie : série c girone a", "salernitana", 6), ("the_new_saints", "pays de galles : cymru premier", "the new saints", 10),
         ("bradford", "angleterre : league one", "bradford", 7), ("barnsley", "angleterre : league one", "barnsley", 7)]


@pytest.mark.parametrize("fichier,competition,equipe,n", PAGES)
def test_vraie_page_nombre_de_matchs_inchange(fichier, competition, equipe, n):
    chemin = os.path.join(DIAG, fichier + ".html")
    if not os.path.exists(chemin):
        pytest.skip("page capturée absente")
    s = BeautifulSoup(open(chemin, encoding="utf-8").read(), "html.parser")
    assert len(sd._extrait_historique_competition(s, competition, equipe, date_reference=REF)) == n
