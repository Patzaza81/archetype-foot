"""Rapprochement des noms Football-Data → ClubElo (3 cas qui passent, 3 qui échouent) et Elo strictement antérieur."""
import pytest

from moteur_dc import elo_donnees as ED

ELO = {"Man United": {"pays": "ENG", "niveau": 1, "periodes": [("2026-01-01", "2026-01-10", 1800.0), ("2026-01-11", "2026-12-31", 1850.0)]},
       "Atletico": {"pays": "ESP", "niveau": 1, "periodes": [("2026-01-01", "2026-12-31", 1900.0)]},
       "Bayern": {"pays": "GER", "niveau": 1, "periodes": [("2026-01-01", "2026-12-31", 2000.0)]},
       "Koeln": {"pays": "GER", "niveau": 1, "periodes": [("2026-01-01", "2026-12-31", 1700.0)]},
       "Valencia": {"pays": "ESP", "niveau": 1, "periodes": [("2026-01-01", "2026-12-31", 1750.0)]}}
IDX = ED.index_noms(ELO)


@pytest.mark.parametrize("nom,div,attendu", [("Man United", "E0", "Man United"), ("Ath Madrid", "SP1", "Atletico"), ("Bayern Munich", "D1", "Bayern"), ("FC Koln", "D1", "Koeln")])
def test_rapprochements_corrects(nom, div, attendu):
    assert ED.rapprocher(nom, div, IDX) == attendu


@pytest.mark.parametrize("nom,div", [("Valencia", "E0"),        # bon nom, mauvais pays
                                     ("Valence", "SP1"),        # approximation interdite
                                     ("Man City", "E0"),        # club absent des données
                                     ("Bayern Munich", "ARG"),  # division hors des cinq pays
                                     ("Koeln", "SP1")])         # bon nom, mauvais pays
def test_rapprochements_refuses(nom, div):
    assert ED.rapprocher(nom, div, IDX) is None


def test_normalisation_accents_et_ponctuation():
    assert ED.normaliser("M'gladbach") == ED.normaliser("Mgladbach") and ED.normaliser("Köln") == "koln"


def test_elo_est_celui_de_la_veille():
    # match le 2026-01-11 : la veille (10/01) est dans la 1re période (1800), pas la 2e, qui commence le jour même
    assert ED.elo_veille(ELO, "Man United", "2026-01-11") == 1800.0
    assert ED.elo_veille(ELO, "Man United", "2026-01-12") == 1850.0


def test_pas_d_elo_avant_le_debut_des_donnees():
    assert ED.elo_veille(ELO, "Man United", "2026-01-01") is None      # la veille (31/12) précède la 1re période


def test_club_inconnu_ou_absent():
    assert ED.elo_veille(ELO, None, "2026-02-01") is None and ED.elo_veille(ELO, "Inconnu", "2026-02-01") is None
