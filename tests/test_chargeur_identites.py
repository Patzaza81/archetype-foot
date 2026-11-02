"""Chargeur de Gamma (moteur_dc/donnees.py, Ligues) : jamais d'identité attribuée par simple ressemblance de scores (enquête du 01/11/2026).
3 cas qui rattachent un alias, 3 qui ne doivent PAS le faire ; cas réel de la Série B ; non-régression sur tous les championnats."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from moteur_dc import donnees as D

RACINE = Path(__file__).resolve().parent.parent
SERIE_B = json.loads((Path(__file__).parent / "fixtures" / "assemblage_serie_b_2026-11-01.json").read_text(encoding="utf-8"))
LG = "x : ligue"


def _eq(nom, matchs):
    return {"cle_cache": f"https://www.matchendirect.fr/equipe/{nom}_abcdefghijklmnopqrstu.html||{LG}", "competition": LG, "nom_matchendirect": nom.title(), "matchs": matchs}


def _m(date, dom, adv, g, c):
    return {"date": date, "domicile": dom, "adversaire": adv, "buts_marques": g, "buts_encaisses": c}


def _noms(L, lg=LG):
    ms = L.matchs.get(lg, [])
    return {m[k] for m in ms for k in ("dom", "ext")}


@pytest.mark.parametrize("g,c", [(2, 1), (0, 0), (3, 3)])
def test_alias_rattache_quand_l_autre_equipe_nomme_explicitement_la_notre(g, c):
    # A écrit « Zeta FC » (alias) ; le bloc de Zeta nomme A : l'alias est Zeta, quel que soit le score (nul compris)
    doc = {"equipes": [_eq("alpha", [_m("2026-09-01", True, "Zeta FC", g, c)]), _eq("zeta", [_m("2026-09-01", False, "Alpha", c, g)])]}
    L = D.Ligues(doc)
    ms = L.matchs[LG]
    assert len(ms) == 1 and ms[0]["dom"] != ms[0]["ext"] and len(_noms(L)) == 2
    assert not any(i.startswith("?") for i in _noms(L))                                   # aucune identité « ? » restante


@pytest.mark.parametrize("g,c", [(0, 0), (1, 1), (2, 2)])
def test_alias_jamais_rattache_sur_la_seule_ressemblance_des_scores(g, c):
    # A joue « Ghost » et B joue « Phantom » le même jour avec le même nul : aucune preuve explicite, A et B ne sont pas adversaires
    doc = {"equipes": [_eq("alpha", [_m("2026-09-01", True, "Ghost", g, c)]), _eq("bravo", [_m("2026-09-01", False, "Phantom", c, g)])]}
    L = D.Ligues(doc)
    ms = L.matchs[LG]
    assert len(ms) == 2 and all(m["dom"] != m["ext"] for m in ms)
    ids = _noms(L)
    assert len(ids) == 4 and sum(i.startswith("?") for i in ids) == 2                      # deux clubs inconnus restent des identités distinctes
    alpha, bravo = L.equipe(doc["equipes"][0]["cle_cache"]), L.equipe(doc["equipes"][1]["cle_cache"])
    assert not any({m["dom"], m["ext"]} == {alpha, bravo} for m in ms)


@pytest.mark.parametrize("nom", ["cerro", "yangon-city", "america-cali"])
def test_auto_rencontre_de_la_source_mise_en_quarantaine(nom):
    doc = {"equipes": [_eq(nom, [_m("2026-05-29", True, nom.replace("-", " ").title(), 2, 0), _m("2026-06-05", False, "Autre FC", 1, 1)])]}
    L = D.Ligues(doc)
    assert [m for m in L.matchs[LG] if m["dom"] == m["ext"]] == []                         # exclue des statistiques
    assert len(L.matchs[LG]) == 1                                                          # le match sain est conservé
    q = L.quarantaine
    assert len(q) == 1 and q[0]["date"] == "2026-05-29" and q[0]["score"] == [2, 0] and "auto-rencontre" in q[0]["raison"]


def test_serie_b_reelle_20_clubs_et_identites_de_virtus_juve_stabia_cremonese_mantova():
    L = D.Ligues(SERIE_B)
    ms = L.matchs["italie : série b"]
    ident = _noms(L, "italie : série b")
    assert len(SERIE_B["equipes"]) == 14 and len(ident) == 20                             # 14 clubs avec bloc propre + 6 vus seulement comme adversaires
    assert [m for m in ms if m["dom"] == m["ext"]] == [] and L.quarantaine == []
    pair = Counter((m["date"], frozenset((m["dom"], m["ext"]))) for m in ms)
    assert max(pair.values()) == 1                                                         # aucun doublon de rencontre

    def n(club):
        ids = [i for i in ident if club in str(L.noms.get(i, i)).lower().replace(" ", "-") or club in i.lower()]
        assert len(ids) == 1, (club, ids)
        return sum(1 for m in ms if ids[0] in (m["dom"], m["ext"]))
    assert (n("virtus"), n("juve-stabia")) == (9, 9)                                       # avant correctif : 13 et 15 (matchs de Cremonese et de Mantova)
    assert n("cremonese") == 6 and n("mantova") == 7
    assert any(m["date"] == "2026-09-19" for m in ms) and not any(m["date"] == "2026-09-19" and m["dom"] == m["ext"] for m in ms)


def test_tous_les_championnats_aucune_auto_rencontre_et_identites_du_cache_conservees():
    doc = json.loads((RACINE / "data" / "assemblage" / "equipes.json").read_text(encoding="utf-8"))
    L = D.Ligues(doc)
    assert sum(1 for v in L.matchs.values() for m in v if m["dom"] == m["ext"]) == 0
    cles = [x["cle_cache"] for x in doc["equipes"]]
    assert len({L.equipe(k) for k in cles}) == len(cles)                                   # aucun club du cache fusionné avec un autre
    for v in L.matchs.values():
        c = Counter((m["date"], frozenset((m["dom"], m["ext"]))) for m in v)
        assert max(c.values()) == 1                                                        # aucun doublon de rencontre
    assert all(q["score"] and q["raison"] for q in L.quarantaine)
