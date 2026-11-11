"""Collecte J+2 / J+3 : secours en HTTP simple quand le navigateur ne ramène rien (panne du 08/11/2026). Aucun accès réseau : tout est simulé."""
import datetime
import io

import pytest

import scraper
import scraper_semaine as S

JOUR = datetime.date(2026, 11, 14)
PAGE_OK = '<html><body><a href="/live-score/a-b_abc123.html">A - B</a></body></html>'


class _Page:
    def __init__(self, html, plante=False):
        self.html, self.plante = html, plante
    def goto(self, *a, **k):
        if self.plante:
            raise TimeoutError("page non chargée")
    def content(self):
        return self.html
    def title(self):
        return "Vérification"


@pytest.fixture
def lecture(monkeypatch):
    """parse_matches simulé : un match par lien /live-score/ ; fetch_html simulé et compté."""
    appels = {"http": 0, "html": PAGE_OK, "finale": None}
    monkeypatch.setattr(S, "parse_matches", lambda html, max_matchs=200, date_label=None: [{"match_id": f"m{i}", "date": date_label} for i in range(html.count("/live-score/"))])
    def faux_fetch(url, retries=3, delay=2):
        appels["http"] += 1
        return appels["html"], appels["finale"] or url
    monkeypatch.setattr(scraper, "fetch_html", faux_fetch)
    return appels


def test_navigateur_suffit_pas_de_http(lecture):
    matchs, chemin = S.scrape_jour(_Page(PAGE_OK), JOUR, journal=io.StringIO())
    assert chemin == "navigateur" and len(matchs) == 1 and lecture["http"] == 0


@pytest.mark.parametrize("page", [_Page("<html></html>"), _Page(PAGE_OK, plante=True), None])
def test_secours_http_dans_trois_cas(lecture, page):          # navigateur vide, navigateur en panne, pas de navigateur
    matchs, chemin = S.scrape_jour(page, JOUR, journal=io.StringIO())
    assert chemin == "http" and matchs == [{"match_id": "m0", "date": "2026-11-14"}] and lecture["http"] == 1


@pytest.mark.parametrize("finale", ["https://www.matchendirect.fr/", "https://www.matchendirect.fr/resultat-foot-11-11-2026/", "https://www.matchendirect.fr/resultat-foot-13-11-2026/"])
def test_redirection_vers_un_autre_jour_refusee(lecture, finale):   # jamais les matchs d'un autre jour sous la date demandée
    lecture["finale"] = finale
    with pytest.raises(RuntimeError):
        S.scrape_jour(_Page("<html></html>"), JOUR, journal=io.StringIO())


def test_jour_vraiment_sans_match(lecture):
    lecture["html"] = "<html></html>"
    assert S.scrape_jour(_Page("<html></html>"), JOUR, journal=io.StringIO()) == ([], "http")
