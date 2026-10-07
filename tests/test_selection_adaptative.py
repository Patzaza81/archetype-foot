import json
import math
from pathlib import Path

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
        "marge_modele": p - 1 / odds,
        "marge_succes": margin,
        "rang_confiance": rank,
        "niveau_confiance": "PROUVE" if rank == 4 else "ETABLI",
        "historique_observations": 50,
        "market_family": "RESULT",
        "exposure_group": "GROUPE_RESULTAT",
    }


def test_ticket_ne_depasse_jamais_12_et_un_match_une_seule_fois():
    rows = [candidate(str(i), "moteur_v2_6_10", 1.35 + (i % 4) * .05) for i in range(20)]
    chosen = gt.greedy(rows, 12, "normal")
    assert len(chosen) == 12
    assert len({gt.match_key(x) for x in chosen}) == 12


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
    chosen = gt.beam_target(rows, 3, 10.0)
    assert len(chosen) == 3
    product = math.prod(float(x["cote"]) for x in chosen)
    assert product <= 14.5


def test_ticket_vide_est_signale_et_non_rempli():
    result = gt.ticket([], "TEST")
    assert result["statut"] == "AUCUN_TICKET_SOLIDE"
    assert result["selection"] == []
