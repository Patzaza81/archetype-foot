"""Correctifs BetPawa du 24/09/2026, testés sur les VRAIS cas du run du 24/09 (diagnostic_precalcul_betpawa.txt) :
contrôle du titre de la page (bonnes pages rejetées à tort) et date BetPawa = lendemain (MLS 0 sur 16)."""
import pytest

from resolution_betpawa import date_compatible
from scraper_betpawa import titre_correspond


# --- titre : bonnes pages qui étaient rejetées à tort, doivent PASSER ---------------------------------------------------
@pytest.mark.parametrize("dom,ext,tdom,text", [
    ("Gérone", "Albacete", "Girona FC", "Albacete Balompie"),
    ("Rotherham Utd", "Crewe", "Rotherham United", "Crewe Alexandra"),
    ("Ostia Mare", "Forlì", "AS Ostiamare", "Forli FC"),
    ("Hfx Wan", "Atlético Ottawa", "HFX Wanderers FC", "Atletico Ottawa"),
    ("Arbroath", "Queen's Park", "Arbroath FC", "Queens Park FC"),
    ("Inverness CT", "G. Morton", "Inverness Caledonian Thistle FC", "Greenock Morton FC"),
    ("Livourne", "Pianese", "US Livorno 1915", "US Pianese"),
    ("Luqueño", "Club Guaraní", "Sportivo Luqueno", "Club Guarani Asuncion"),
    ("Dep. Pereira", "Bogota", "Deportivo Pereira FC SA", "Internacional de Bogota."),
    ("Klubi-04", "JäPS", "HJK Klubi 04", "JaPS"),
    ("Ibiza", "Real Saragosse", "UD Ibiza", "Real Zaragoza"),
])
def test_titre_bonne_page_acceptee(dom, ext, tdom, text):
    assert titre_correspond(dom, ext, tdom, text, competition="Pays : Championnat")


@pytest.mark.parametrize("dom,ext,tdom,text,comp", [
    ("Logroño", "Barcelone", "Cdef Logrono Women", "FC Barcelona Women", "Espagne : Primera Division Femmes"),
    ("AIK", "Växjö", "AIK DFF Women", "Vaxjo DFF Women", "Suède : Damallsvenskan"),
    ("Man. United", "West Ham", "Manchester United WFC Women", "West Ham United FC Women", "Angleterre : Femmes Super Ligue"),
])
def test_titre_competition_feminine_page_feminine_acceptee(dom, ext, tdom, text, comp):
    assert titre_correspond(dom, ext, tdom, text, competition=comp)


# --- titre : autre match, équipe féminine/réserve, autre club de la même ville : doivent être REFUSÉS --------------------
@pytest.mark.parametrize("dom,ext,tdom,text", [
    ("San Jose E.", "Portland", "San Marino", "Finland"),                                       # cache faux réel
    ("Man. United", "West Ham", "Manchester United WFC Women", "West Ham United FC Women"),      # féminines
    ("AIK", "Växjö", "AIK DFF Women", "Vaxjo DFF Women"),
    ("Real Madrid", "Getafe", "Real Madrid Castilla", "Getafe"),                                 # réserve
    ("Slavia Sofia", "Levski", "CSKA Sofia", "Levski"),                                          # même ville
    ("Man. United", "Leeds", "Manchester City", "Leeds United"),                                 # United / City
])
def test_titre_autre_match_refuse(dom, ext, tdom, text):
    assert not titre_correspond(dom, ext, tdom, text, competition="Angleterre : Premier League")


# --- date : doivent PASSER ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("trouvee,iso", [("26/09", "2026-09-26"), ("27/09", "2026-09-26"), ("01/01", "2026-12-31")])
def test_date_meme_jour_ou_lendemain(trouvee, iso):
    assert date_compatible(trouvee, iso)


# --- date : doivent être REFUSÉES --------------------------------------------------------------------------------------
@pytest.mark.parametrize("trouvee,iso", [("25/09", "2026-09-26"), ("28/09", "2026-09-26"), (None, "2026-09-26"), ("26/09", None)])
def test_date_veille_ou_trop_loin_refusee(trouvee, iso):
    assert not date_compatible(trouvee, iso)
