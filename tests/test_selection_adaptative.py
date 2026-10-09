import json
import math
from pathlib import Path

import pytest

import generateur_tickets as gt
import selection_adaptative as sa


def test_wilson_et_marge_succes():
    lower = sa.wilson_lower(45, 50)
    assert 0 < lower < 1
    assert lower > 0.7
    assert sa.confidence_tier(50, 0.05, 0.08) == ("PROUVE", 4)
    assert sa.confidence_tier(5, 0.05, 0.08) == ("MODELE_SEUL", 0)


def test_selection_classe_sans_coefficients_arbitraires():
    h = {
        "par_marche": {
            "moteur_v2_6_10|1x2_domicile": {
                "observations": 50, "taux_reussite": 0.84,
                "borne_basse_95": 0.71, "roi": 0.12
            }
        }
    }
    rows = [{
        "source": "moteur_v2_6_10", "moteur": "moteur_v2_6_10",
        "match_id": "a", "marche": "1x2_domicile",
        "cote": 1.50, "probabilite": 0.72, "edv": 0.08
    }]
    out = sa.enrich(rows, h)[0]
    assert out["marge_modele"] > 0
    assert out["marge_succes"] > 0
    assert out["niveau_confiance"] == "PROUVE"


def candidate(mid, source, odds=1.5, p=0.72, rank=4, margin=0.08):
    return {
        "source": source,
        "moteur": source if source != "journal" else None,
        "match_id": mid,
        "date": "2026-10-08",
        "heure": "20:00",
        "competition": "L1",
        "domicile": "A" + mid,
        "exterieur": "B" + mid,
        "marche": "1X2 - 1",
        "cote": odds,
        "probabilite": p,
        "marge_modele": (p - 1 / odds) if p is not None else None,
        "marge_succes": margin,
        "rang_confiance": rank,
        "niveau_confiance": "PROUVE" if rank == 4 else "ETABLI",
        "historique_observations": 50,
        "market_family": "RESULT",
        "exposure_group": "GROUPE_RESULTAT",
    }


def test_ticket_ne_depasse_jamais_12_et_un_match_une_seule_fois():
    rows = [candidate(str(i), "moteur_v2_6_10", 1.35 + (i % 4) * .05) for i in range(20)]
    chosen = gt.tirage_cible(rows, 20.0, "2026-10-08", "T")
    assert 2 <= len(chosen) <= 12
    assert len({gt.match_key(x) for x in chosen}) == len(chosen)


def test_objectif_10_cherche_une_cote_proche():
    rows = [
        candidate("a", "moteur_v2_6_10", 2.0),
        candidate("b", "moteur_v3", 2.0),
        candidate("c", "journal", 2.5, p=None, rank=4, margin=.10),
        candidate("d", "moteur_v2_6_10", 1.4),
        candidate("e", "moteur_v3", 1.8),
        candidate("f", "journal", 1.6, p=None, rank=4, margin=.08),
    ]
    rows = gt.dedupe(rows)
    chosen = gt.tirage_cible(rows, 10.0, "2026-10-08", "T")
    assert len(chosen) >= 2
    product = math.prod(float(x["cote"]) for x in chosen)
    assert 10 / 1.25 <= product <= 10 * 1.25


def test_ticket_vide_est_signale_et_non_rempli():
    result = gt.ticket([], "TEST")
    assert result["statut"] == "AUCUN_TICKET_SOLIDE"
    assert result["selection"] == []


def test_avantage_par_marche_exige_un_echantillon_minimum():
    history = {
        "par_marche": {
            "moteur_v2_6_10|m": {"moteur": "moteur_v2_6_10", "marche": "m", "observations": 20, "borne_basse_95": .70, "roi": .10, "taux_reussite": .80},
            "moteur_v3|m": {"moteur": "moteur_v3", "marche": "m", "observations": 20, "borne_basse_95": .62, "roi": .08, "taux_reussite": .75},
        }
    }
    x = sa.advantage_by_market(history)["m"]
    assert x["meilleur"] == "moteur_v2_6_10"


def test_calibrage_externe_prime_les_candidats_sans_modifier_le_moteur():
    rows = [
        candidate("a", "moteur_v2_6_10", odds=1.60, p=0.72, rank=4),
        candidate("b", "moteur_v2_6_10", odds=1.60, p=0.80, rank=4),
    ]
    rows[0]["calibrage_rang"] = 2
    rows[0]["calibrage_marge"] = 0.04
    rows[0]["calibrage_lift"] = 0.05
    rows[1]["calibrage_rang"] = 0
    rows[1]["calibrage_marge"] = None
    rows[1]["calibrage_lift"] = None
    import generateur_tickets as gt
    assert gt.candidate_rank(rows[0]) > gt.candidate_rank(rows[1])
    assert rows[0]["probabilite"] == 0.72


def test_journal_equipe_5_sur_5_devient_une_opportunite_sans_precalcul_detaille():
    journal = {
        "equipes_a_suivre": [{
            "equipe": "Equipe Forte",
            "ligue": "Ligue Test",
            "marche": "Match à moins de 3,5 buts",
            "gagnes": 5,
            "joues": 5,
            "frequence": 1.0,
            "roi_betpawa": 0.30,
            "prochain_match": {
                "date": "2099-10-10",
                "heure": "15:00",
                "adversaire": "Adversaire",
                "lieu": "domicile",
                "cote_betpawa": 1.60,
                "betpawa_url": "https://example.invalid/event"
            }
        }]
    }
    # Mode explicite : le test ne dépend pas du réglage livré (config/journal_calibrage.json).
    rows = sa.extract_journal_candidates(journal, {"signaux": []}, "wilson")
    assert len(rows) == 1
    assert rows[0]["journal_frequency"] == 1.0
    assert rows[0]["journal_observations"] == 5
    assert rows[0]["probabilite_source"] == "JOURNAL_WILSON"
    assert rows[0]["probabilite_estimee"] < 1.0


def test_preuve_journal_5_sur_5_passe_devant_un_modele_v2_non_calibre():
    journal = {
        "source": "journal",
        "journal_team": "Equipe Forte",
        "journal_frequency": 1.0,
        "journal_wins": 5,
        "journal_observations": 5,
        "journal_lower_bound": sa.wilson_lower(5, 5),
        "journal_roi": 0.30,
        "cote": 1.60,
        "rang": None,
        "probabilite_estimee": sa.wilson_lower(5, 5),
        # champs normalisés par enrich() : le générateur ne lit que ceux-là
        "selection_evidence_rank": 3,
        "selection_evidence_lower_bound": sa.wilson_lower(5, 5),
        "selection_evidence_rate": 1.0,
        "selection_evidence_roi": 0.30,
        "selection_evidence_observations": 5,
    }
    v2 = {
        "source": "moteur_v2_6_10",
        "rang": "P1",
        "cote": 1.60,
        "probabilite": 0.90,
        "probabilite_estimee": 0.90,
        "historique_observations": 0,
        "ev_estime": 0.44,
    }
    assert gt.candidate_rank(journal) > gt.candidate_rank(v2)


# --- AJOUT 08/10/2026 : probabilité du Journal lissée vers la fréquence générale du marché (remplace Wilson) -----------

@pytest.mark.parametrize("wins,n,base,attendu", [
    (5, 5, 0.50, 0.60),          # 5/5 sur un marché à 50 % : (5 + 20×0,5) / 25
    (0, 8, 0.50, 10 / 28),       # 0/8 : tiré vers le bas mais pas à 0
    (20, 20, 0.54, (20 + 10.8) / 40),
])
def test_journal_probabilite_lissee_cas_valides(wins, n, base, attendu):
    assert sa.journal_probabilite_lissee(wins, n, base) == pytest.approx(attendu)


@pytest.mark.parametrize("wins,n,base", [
    (5, 0, 0.5),                 # aucun match
    (5, 5, None),                # fréquence générale absente
    (6, 5, 0.5),                 # plus de réussites que de matchs
    (5, 5, 1.3),                 # base impossible
])
def test_journal_probabilite_lissee_cas_refuses(wins, n, base):
    assert sa.journal_probabilite_lissee(wins, n, base) is None


def _ligne_journal(**extra):
    row = {"equipe": "Equipe Test", "ligue": "Ligue Test", "marche": "Match à moins de 3,5 buts", "gagnes": 5, "joues": 5,
           "frequence": 1.0, "roi_betpawa": 0.3,
           "prochain_match": {"date": "2099-10-10", "heure": "15:00", "adversaire": "Adv", "lieu": "domicile",
                              "cote_betpawa": 1.60, "betpawa_url": "https://example.invalid/e"}}
    row.update(extra)
    return row


def test_candidat_journal_utilise_la_probabilite_lissee_et_plus_wilson():
    c = sa._journal_team_market_candidate(_ligne_journal(frequence_generale=0.5), "lisse")
    assert c["probabilite_source"] == "JOURNAL_LISSE" and c["probabilite_estimee"] == pytest.approx(0.6)
    assert c["journal_lower_bound"] == pytest.approx(sa.wilson_lower(5, 5)) and c["probabilite_estimee"] > c["journal_lower_bound"]
    assert c["journal_success_margin"] == pytest.approx(0.6 - 1 / 1.6, abs=1e-5)


def test_candidat_journal_sans_frequence_generale_retombe_sur_wilson():
    c = sa._journal_team_market_candidate(_ligne_journal(), "lisse")
    assert c["probabilite_source"] == "JOURNAL_WILSON" and c["probabilite_estimee"] == pytest.approx(sa.wilson_lower(5, 5), abs=1e-5)


def test_enrich_garde_la_probabilite_lissee():
    c = sa._journal_team_market_candidate(_ligne_journal(frequence_generale=0.5), "lisse")
    out = sa.enrich([c], {"par_marche": {}}, None)[0]
    assert out["probabilite_source"] == "JOURNAL_LISSE" and out["probabilite_estimee"] == pytest.approx(0.6)


# --- AJOUT 08/10/2026 : interrupteur du calibrage du Journal (retour à l'état initial, exigence non négociable) -------

def test_mode_wilson_redonne_exactement_l_etat_initial_meme_avec_frequence_generale():
    ligne = _ligne_journal(frequence_generale=0.5)
    w = sa._journal_team_market_candidate(ligne, "wilson")
    assert w["probabilite_source"] == "JOURNAL_WILSON" and w["journal_probabilite_lissee"] is None
    assert w["probabilite_estimee"] == pytest.approx(sa.wilson_lower(5, 5), abs=1e-5)
    assert w["journal_success_margin"] == pytest.approx(sa.wilson_lower(5, 5) - 1 / 1.6, abs=1e-5)
    out = sa.enrich([w], {"par_marche": {}}, None)[0]
    assert out["probabilite_source"] == "JOURNAL_WILSON" and out["probabilite_estimee"] == pytest.approx(sa.wilson_lower(5, 5), abs=1e-5)


def test_extract_journal_candidates_respecte_le_mode():
    journal = {"equipes_a_suivre": [_ligne_journal(frequence_generale=0.5)]}
    assert sa.extract_journal_candidates(journal, {"signaux": []}, "lisse")[0]["probabilite_source"] == "JOURNAL_LISSE"
    assert sa.extract_journal_candidates(journal, {"signaux": []}, "wilson")[0]["probabilite_source"] == "JOURNAL_WILSON"


@pytest.mark.parametrize("contenu,attendu", [
    ('{"mode": "lisse"}', "lisse"),
    ('{"mode": "wilson"}', "wilson"),
    ('{"mode": " LISSE "}', "lisse"),
    ('{"mode": "autre"}', "wilson"),      # mode inconnu : état initial
    ('pas du json', "wilson"),            # fichier illisible : état initial
    ('[1, 2]', "wilson"),                 # mauvaise forme : état initial
])
def test_journal_mode_lit_le_fichier_et_retombe_sur_wilson(tmp_path, contenu, attendu):
    f = tmp_path / "journal_calibrage.json"
    f.write_text(contenu, encoding="utf-8")
    assert sa.journal_mode(f) == attendu


def test_journal_mode_fichier_absent_donne_wilson(tmp_path):
    assert sa.journal_mode(tmp_path / "absent.json") == "wilson"


def test_le_fichier_de_configuration_livre_est_valide():
    assert sa.journal_mode(Path("config/journal_calibrage.json")) in sa.MODES_JOURNAL
