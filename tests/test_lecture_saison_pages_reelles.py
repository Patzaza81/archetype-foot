"""Lecture des saisons sur de VRAIES pages équipes matchendirect (capturées le 24/09/2026 par
.github/workflows/diagnostic_pages.yml, copiées dans tests/fixtures/pages_equipes/).

Avant le correctif du 24/09 : The New Saints -> 1 match (l'amical Glentoran 1-1), Cosenza -> la Coppa Italia Série C,
Aston Villa féminines -> les « Matchs Amicaux Femmes ». Chaque cas doit maintenant lire LA bonne section, et une page
sans la compétition demandée ne doit rien renvoyer (pas de données plutôt que de fausses données)."""
import os

import pytest
from bs4 import BeautifulSoup

import controle_saisons as cs
import scraper_details as sd
import stats_saison_en_cours as ss

DOSSIER = os.path.join(os.path.dirname(__file__), "fixtures", "pages_equipes")


def soupe(nom):
    with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "html.parser")


def lit(nom, competition, equipe):
    return sd._extrait_historique_competition(soupe(nom), competition, equipe)


def resume(matchs):
    return [(m["domicile"], m["buts_marques"], m["buts_encaisses"]) for m in matchs]


# --- doivent lire la BONNE section -----------------------------------------------------------------------------------
def test_the_new_saints_lit_ses_10_matchs_de_cymru_premier():
    m = lit("the_new_saints.html", "Pays de Galles : Cymru Premier", "the new saints")
    assert resume(m) == [(False, 0, 0), (True, 2, 0), (True, 1, 0), (False, 5, 0), (True, 5, 1),
                         (False, 3, 2), (True, 1, 0), (False, 2, 0), (True, 5, 0), (True, 2, 1)]


def test_cosenza_lit_la_serie_c_et_pas_la_coupe():
    titre, _ = sd._section_competition(soupe("cosenza.html"), sd._partie_competition("Italie : Série C Girone A"))
    assert titre == "série c"
    assert len(lit("cosenza.html", "Italie : Série C Girone A", "cosenza")) == 6


def test_aston_villa_lit_la_super_ligue_feminine_et_pas_les_amicaux():
    titre, _ = sd._section_competition(soupe("aston_villa.html"), sd._partie_competition("Angleterre : Femmes Super Ligue"))
    assert titre == "femmes super ligue"
    assert resume(lit("aston_villa.html", "Angleterre : Femmes Super Ligue", "aston villa")) == [(False, 1, 1), (True, 1, 4), (False, 1, 1)]


def test_bradford_inchange_par_le_correctif():
    # page qui était déjà bien lue : même résultat qu'avant le correctif (capture du 24/09)
    assert resume(lit("bradford.html", "Angleterre : League One", "bradford")) == [
        (True, 2, 0), (False, 1, 0), (False, 0, 2), (True, 1, 2), (True, 1, 0), (False, 1, 0), (False, 1, 0)]


# --- doivent être REFUSÉS -------------------------------------------------------------------------------------------
def test_competition_absente_de_la_page_rien_renvoye():
    assert lit("the_new_saints.html", "Pays de Galles : Coupe du Pays de Galles", "the new saints") is None


def test_amicaux_jamais_pris_pour_un_championnat():
    # la seule section contenant « femmes » ou « amicaux » ne doit pas servir pour une compétition qui n'en parle pas
    assert sd._score_titre_competition("femmes super ligue", "matchs amicaux femmes") is None
    assert sd._score_titre_competition("cymru premier", "matchs amicaux") is None


def test_coupe_jamais_prise_pour_le_championnat():
    assert sd._score_titre_competition("série c girone a", "coppa italia série c") is None
    assert sd._score_titre_competition("league one", "trophée efl") is None


@pytest.mark.parametrize("cible,candidat", [("cymru premier", "cymru premier"), ("série c girone a", "série c"),
                                            ("league one", "league one")])
def test_titres_acceptes(cible, candidat):
    assert sd._score_titre_competition(cible, candidat) is not None


# --- garde-fou du moteur : une saison qui contredit un résultat connu n'est jamais utilisée ------------------------
def test_garde_fou_refuse_une_saison_incoherente(monkeypatch):
    monkeypatch.setattr(ss, "_RESULTATS_CONNUS", {"the new saints": [
        {"domicile": False, "marques": 2, "encaisses": 0, "date": "2026-09-11", "adversaire": "Broughton", "competition": "cymru premier"}]})
    monkeypatch.setattr(ss._loader, "recupere_historique_saison_courante",
                        lambda url, comp, nom: [{"domicile": False, "buts_marques": 1, "buts_encaisses": 1}])   # l'amical
    url = "https://www.matchendirect.fr/equipe/the-new-saints_85l2ewv17mqmw3otdletjc36.html"
    r = ss.stats_saison_en_cours(url, "The New Saints", "Pays de Galles : Cymru Premier")
    assert r["raison_non_traite"] == ss.RAISON_SAISON_INCOHERENTE


def test_garde_fou_accepte_la_bonne_saison(monkeypatch):
    monkeypatch.setattr(ss, "_RESULTATS_CONNUS", {"the new saints": [
        {"domicile": False, "marques": 2, "encaisses": 0, "date": "2026-09-11", "adversaire": "Broughton", "competition": "cymru premier"}]})
    bonne = lit("the_new_saints.html", "Pays de Galles : Cymru Premier", "the new saints")
    monkeypatch.setattr(ss._loader, "recupere_historique_saison_courante", lambda url, comp, nom: bonne)
    url = "https://www.matchendirect.fr/equipe/the-new-saints_85l2ewv17mqmw3otdletjc36.html"
    r = ss.stats_saison_en_cours(url, "The New Saints", "Pays de Galles : Cymru Premier")
    assert "raison_non_traite" not in r and r["nb_matchs_saison_courante"] == 10


def test_controle_sans_donnees_n_est_pas_une_incoherence():
    ligne = cs.controle_equipe("u/x_1.html||l : cymru premier", {"horodatage": "2026-09-24", "resultat": {}},
                               {"x": [{"domicile": True, "marques": 1, "encaisses": 0, "date": "2026-09-10",
                                       "adversaire": "Y", "competition": "cymru premier"}]})
    assert ligne["statut"] == "SANS_DONNEES"


# --- A3 bis (24/09/2026) : date, adversaire et lien de chaque match ---------------------------------------------------
import datetime as _dt


def test_the_new_saints_dates_et_adversaires_identiques_a_la_page():
    m = sd._extrait_historique_competition(soupe("the_new_saints.html"), "Pays de Galles : Cymru Premier",
                                           "the new saints", date_reference=_dt.date(2026, 9, 24))
    assert [(x["date"], x["adversaire"]) for x in m] == [
        ("2026-08-02", "Penybont"), ("2026-08-07", "Haverfordwest"), ("2026-08-14", "Briton Ferry"),
        ("2026-08-21", "Cardiff MU"), ("2026-08-28", "Colwyn Bay"), ("2026-08-31", "Caernarfon"),
        ("2026-09-05", "Barry Town"), ("2026-09-11", "Broughton"), ("2026-09-15", "Flint Town Utd"),
        ("2026-09-19", "Llandudno")]
    assert all(x["url_match"].startswith("/live-score/") for x in m)


class _Tr:
    """Ligne minimale : une cellule <span class="lm2_timeXxX">texte</span>."""
    def __init__(self, texte):
        self.s = BeautifulSoup(f'<tr><td><span class="lm2_timeXxX">{texte}</span></td></tr>', "html.parser").tr


@pytest.mark.parametrize("texte,ref,attendu", [
    ("02/08", _dt.date(2026, 9, 24), "2026-08-02"),
    ("30/12", _dt.date(2027, 1, 5), "2026-12-30"),      # saison à cheval : année précédente
    ("20:00", _dt.date(2026, 9, 24), "2026-09-24"),      # match du jour affiché avec l'heure
])
def test_date_ligne_annee_deduite(texte, ref, attendu):
    assert sd._date_ligne(_Tr(texte).s, ref) == attendu


@pytest.mark.parametrize("texte,ref,attendu", [
    ("31/02", _dt.date(2026, 9, 24), None),              # date impossible
    ("", _dt.date(2026, 9, 24), None),                   # pas de date
    ("28/09", _dt.date(2026, 9, 24), "2025-09-28"),      # jamais une date future : année précédente
])
def test_date_ligne_refus_ou_passe(texte, ref, attendu):
    assert sd._date_ligne(_Tr(texte).s, ref) == attendu
