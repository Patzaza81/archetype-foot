# -*- coding: utf-8 -*-
"""Phase 4 de la feuille de route : le noyau de v2.6.10 reproduit exactement la v2.6.9 (tant que son fichier existe).

Chaque match de la batterie est analysé par les deux moteurs ; tout le résultat doit être identique.
"""
import copy
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

ancien = pytest.importorskip("moteur_v2_6_9")
from moteur_v2_6_10 import noyau as nouveau  # noqa: E402

COTES = {"victoire": 1.55, "nul": 4.2, "defaite": 6.0, "btts_oui": 2.05, "btts_non": 1.70,
         "over_1_5": 1.30, "under_1_5": 3.40, "over_2_5": 1.75, "under_2_5": 2.05,
         "dc_1X": 1.20, "dc_X2": 2.60, "dc_12": 1.25,
         "handicap_dom_-0_5": 1.58, "handicap_ext_+0_5": 2.45, "handicap_dom_-1_0": 2.90, "handicap_ext_+1_0": 1.40,
         "handicap_dom_-1_5": 3.6, "handicap_ext_+1_5": 1.3}


def un_match(att_d, def_d, att_e, def_e, n=5, cotes=None, **extra):
    m = {"id": 1, "nom_dom": "A", "nom_ext": "B",
         "equipe_dom": {"nom": "A", "buts_marques_moy": att_d, "buts_encaisses_moy": def_d, "matchs_joues": n},
         "equipe_ext": {"nom": "B", "buts_marques_moy": att_e, "buts_encaisses_moy": def_e, "matchs_joues": n},
         "cotes": dict(COTES if cotes is None else cotes), "meta": {"fiabilite": "OK"}}
    m.update(extra)
    return m


BATTERIE = [
    un_match(3.0, 0.4, 0.6, 2.4),
    un_match(1.5, 1.2, 1.2, 1.5, n=3),
    un_match(2.0, 0.9, 1.2, 1.5, n=3),
    un_match(0.0, 0.0, 0.0, 0.0),
    un_match(10.0, 10.0, 10.0, 10.0),
    un_match(1.8, 1.0, 1.2, 1.4, n=12),
    un_match(1.8, 1.0, 1.2, 1.4, cotes={"victoire": 2.0, "nul": 3.4, "defaite": 3.8}),
    un_match(1.8, 1.0, 1.2, 1.4, cotes={"victoire": 1.5, "nul": 2.5, "defaite": 2.5}),
    un_match(1.8, 1.0, 1.2, 1.4, cotes={**COTES, "clean_sheet_dom": 50.0}),
    un_match(1.8, 1.0, 1.2, 1.4, cotes={**COTES, "handicap_dom_-1_5": 1.5, "handicap_ext_+1_5": 1.5}),
    un_match(1.8, 1.0, 1.2, 1.4, meta={"fiabilite": "FALLBACK"}),
    un_match(12.0, 1.0, 1.0, 1.0),
    un_match(1.8, 1.0, 1.2, 1.4, statut="reporte"),
    un_match(1.8, 1.0, 1.2, 1.4, cotes_prises_le="2026-09-01T00:00:00+00:00"),
    un_match(2.5, 0.8, 0.8, 2.0, cotes={"victoire": 5.0, "nul": 3.4, "defaite": 1.7, "btts_oui": 1.85, "btts_non": 1.95}),
]


@pytest.mark.parametrize("i", range(len(BATTERIE)))
@pytest.mark.parametrize("remboursement", [False, True])
def test_noyau_identique_a_la_v2_6_9(i, remboursement):
    m = BATTERIE[i]
    maintenant = None
    ancien.HANDICAP_ENTIER_REMBOURSE = remboursement
    nouveau.HANDICAP_ENTIER_REMBOURSE = remboursement
    try:
        from datetime import datetime, timezone
        maintenant = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        a = ancien.analyser_match(copy.deepcopy(m), "", maintenant)
        b = nouveau.analyser_match(copy.deepcopy(m), "", maintenant)
    finally:
        ancien.HANDICAP_ENTIER_REMBOURSE = False
        nouveau.HANDICAP_ENTIER_REMBOURSE = False
    assert a == b
