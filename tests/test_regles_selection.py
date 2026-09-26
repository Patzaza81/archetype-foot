# -*- coding: utf-8 -*-
"""Tests de la RÈGLE DU DOUBLE CONTRÔLE (regles_selection.py).

Pour chaque famille de marchés : 3 cas réels qui doivent passer et 3 cas réels qui doivent être écartés
(matchs du 26/09/2026, résultats réels dans tests/fixtures/double_controle_26092026.json),
plus des cas construits qui isolent chaque contrôle.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import regles_selection as rs  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "double_controle_26092026.json")


def _lire_matchs(texte):
    """« 2026-08-08E2-5 » -> {"date": "2026-08-08", "lieu": "E", "bm": 2, "be": 5}"""
    res = []
    for m in texte.split():
        date, lieu, score = m[:10], m[10], m[11:]
        bm, be = score.split("-")
        res.append({"date": date, "lieu": lieu, "bm": int(bm), "be": int(be)})
    return res


with open(FIXTURE, encoding="utf-8") as f:
    CAS_REELS = json.load(f)["cas"]
for _c in CAS_REELS:
    _c["matchs_dom"] = _lire_matchs(_c["dom"])
    _c["matchs_ext"] = _lire_matchs(_c["ext"])


@pytest.mark.parametrize("cas", CAS_REELS, ids=[f"{c['match']} | {c['marche']}" for c in CAS_REELS])
def test_cas_reels_26092026(cas):
    r = rs.double_controle(cas["marche"], cas["matchs_dom"], cas["matchs_ext"], cas["domicile"], cas["exterieur"])
    assert r["retenu"] is cas["attendu_retenu"], r


def test_chaque_famille_a_3_passes_et_3_rejets():
    familles = {}
    for c in CAS_REELS:
        cle = c["marche"].split(" - ")[0] if c["marche"].startswith(("1X2", "Double")) else c["marche"]
        familles.setdefault(cle, [0, 0])[0 if c["attendu_retenu"] else 1] += 1
    assert len(familles) == 5
    for cle, (passes, rejets) in familles.items():
        assert passes >= 3 and rejets >= 3, cle


def test_cas_origine_real_salt_lake_ecarte_par_la_forme_recente():
    """Le cas qui a fait naître la règle : validé sur la saison, rejeté sur la forme récente."""
    cas = next(c for c in CAS_REELS if c["match"].startswith("Real Salt Lake") and c["marche"] == "BTTS - oui")
    r = rs.double_controle(cas["marche"], cas["matchs_dom"], cas["matchs_ext"], cas["domicile"], cas["exterieur"])
    assert r["saison"]["ok"] is True
    assert r["recent"]["ok"] is False
    assert r["retenu"] is False


# ---------------------------------------------------------------------------
# Cas construits
# ---------------------------------------------------------------------------
def _m(date, lieu, bm, be):
    return {"date": date, "lieu": lieu, "bm": bm, "be": be}


def _serie(scores, lieux):
    return [_m(f"2026-08-{i + 1:02d}", l, a, b) for i, ((a, b), l) in enumerate(zip(scores, lieux))]


FORT = _serie([(2, 0), (3, 1), (2, 1), (1, 1), (2, 0), (3, 1)], "DEDEDE")
FAIBLE = _serie([(0, 2), (1, 3), (0, 1), (1, 1), (0, 2), (1, 2)], "DEDEDE")


def test_victoire_refusee_si_seul_l_adversaire_est_faible():
    """Adversaire très faible mais équipe choisie moyenne : pari écarté (compétence non prouvée)."""
    moyen = _serie([(1, 1), (0, 1), (2, 1), (1, 1), (1, 2), (1, 0)], "DEDEDE")
    r = rs.double_controle("1X2 - 1", moyen, FAIBLE)
    assert r["retenu"] is False
    assert any(t.startswith("✗") and "gagne" in t for t in r["saison"]["raisons"])


def test_victoire_retenue_si_competence_et_faiblesse_prouvees():
    assert rs.double_controle("1X2 - 1", FORT, FAIBLE)["retenu"] is True


def test_moins_2_5_refuse_si_un_seul_cote_ferme():
    ferme = _serie([(1, 0), (0, 0), (1, 1), (0, 1), (1, 0), (0, 0)], "DEDEDE")
    ouvert = _serie([(2, 2), (3, 1), (1, 3), (2, 2), (3, 2), (1, 2)], "DEDEDE")
    assert rs.double_controle("Moins de 2.5 buts", ferme, ouvert)["retenu"] is False
    assert rs.double_controle("Moins de 2.5 buts", ferme, ferme)["retenu"] is True


def test_echantillon_trop_petit_ecarte():
    court = _serie([(2, 0), (3, 1), (2, 1), (1, 1)], "DEDE")
    r = rs.double_controle("1X2 - 1", court, FAIBLE)
    assert r["retenu"] is False


def test_marche_non_couvert_ecarte():
    assert rs.double_controle("Score exact - 1-0", FORT, FAIBLE)["retenu"] is False


# ---------------------------------------------------------------------------
# Version 1.1.0 : pari « limite » (ajout du 26/09/2026). Seuls les matchs de la même compétition comptent.
# ---------------------------------------------------------------------------
YORK = _lire_matchs("2026-08-15D3-2 2026-08-22E1-1 2026-08-29D2-1 2026-09-01E2-3 2026-09-05E1-1 "
                    "2026-09-12D4-0 2026-09-19E0-2")
GILLINGHAM = _lire_matchs("2026-08-15D0-3 2026-08-22E0-0 2026-08-29D1-1 2026-09-01E1-1 2026-09-05E4-1 "
                          "2026-09-12D2-0 2026-09-19D3-0")


def test_cas_york_retenu_mais_limite():
    """York ou nul passe les deux contrôles, mais Gillingham a gagné 3 de ses 6 derniers matchs de championnat :
    exactement le maximum autorisé. Le pari est donc « limite » et sort d'un combiné si un pari propre existe."""
    r = rs.double_controle("Double chance - 1X", YORK, GILLINGHAM, "York", "Gillingham")
    assert r["retenu"] is True
    assert r["marge_nulle"] is True
    assert r["limite"] is True


@pytest.mark.parametrize("scores_adv", [
    [(2, 0), (0, 1), (2, 1), (0, 2), (1, 0), (0, 3)],   # 3 victoires sur 6 : marge nulle (double chance)
    [(1, 0), (2, 1), (3, 0), (0, 0), (0, 1), (1, 2)],   # 3 victoires
    [(2, 1), (1, 1), (1, 0), (0, 2), (2, 0), (0, 1)],   # 3 victoires
])
def test_marge_nulle_detectee(scores_adv):
    r = rs.double_controle("Double chance - 1X", FORT, _serie(scores_adv, "DEDEDE"))
    assert r["marge_nulle"] is True


@pytest.mark.parametrize("scores_adv", [
    [(0, 2), (0, 1), (2, 1), (0, 2), (1, 1), (0, 3)],   # 1 victoire
    [(1, 1), (0, 0), (2, 1), (0, 2), (1, 1), (0, 3)],   # 1 victoire
    [(0, 1), (0, 1), (1, 1), (0, 2), (2, 2), (0, 3)],   # 0 victoire
])
def test_pas_de_marge_nulle(scores_adv):
    r = rs.double_controle("Double chance - 1X", FORT, _serie(scores_adv, "DEDEDE"))
    assert r["marge_nulle"] is False


def test_combine_ecarte_les_paris_limites_si_un_pari_propre_existe():
    propre = {"retenu": True, "limite": False}
    limite = {"retenu": True, "limite": True}
    rejete = {"retenu": False, "limite": False}
    assert rs.choisir_pour_combine([propre, limite, rejete]) == [propre]
    assert rs.choisir_pour_combine([limite, rejete]) == [limite]
    assert rs.choisir_pour_combine([rejete]) == []
