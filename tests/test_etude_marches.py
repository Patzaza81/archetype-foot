"""Étude des marchés (lecture seule) : calculs, séparation des jeux, absence de fuite, rejet possible des candidats, aucune intégration à la production."""
from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from alpha_serie import coeur, etude_marches as E, parametres as P, robustesse as RB, suivi as S

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def table():
    return E.construire_table()


# ---- calculs ----
def test_wilson_identique_a_celui_du_suivi():
    for g, n in ((0, 10), (7, 10), (70, 100), (1, 1), (845, 1000)):
        assert round(E.wilson(g, n)[0], 4) == S.wilson_bas(g, n)


def test_rendement_gains_pertes_et_taux_d_equilibre():
    r = E.rendement([(True, 1.5), (False, 1.5), (True, 2.0)])
    assert (r["paris"], r["gagnes"], r["gains"], r["pertes"], r["net"]) == (3, 2, 1.5, 1.0, 0.5)
    assert r["rendement"] == round(0.5 / 3, 4) and r["taux_equilibre"] == round(1 / (5 / 3), 4)
    assert E.rendement([]) == {"paris": 0}


def test_baisse_significative_trois_cas_vrais_trois_faux():
    assert E.baisse_significative(800, 1000, 600, 1000)          # 80 % -> 60 %
    assert E.baisse_significative(750, 1000, 650, 1000)
    assert E.baisse_significative(90, 100, 700, 1000)
    assert not E.baisse_significative(750, 1000, 745, 1000)      # quasi égal
    assert not E.baisse_significative(60, 100, 80, 100)          # hausse
    assert not E.baisse_significative(0, 0, 5, 10)               # effectif nul


def test_bandes_de_cotes_borne_basse_incluse():
    def lg(cote, h, a):
        return {"src": "ARCH", "jour": "2026-10-01", "h": h, "a": a, "moy": {}, "mk": {"btts|Oui": [0.8, 1, 1, 1, cote]}}
    res = E.bandes_de_cotes([lg(1.35, 1, 1), lg(1.349, 0, 0), lg(1.25, 2, 1), lg(1.2, 1, 1)], "btts|Oui")["B_betpawa"]
    par = {b["bande"]: b["matchs"] for b in res}
    assert par == {"1.25-1.35": 2, "1.35-1.5": 1, "1.5-1.7": 0, "1.7-2": 0, ">=2": 0}      # 1,35 dans la 2e ; 1,2 hors bandes


# ---- configurations annoncées ----
def test_variable_de_chaque_marche_trois_vrais_trois_faux():
    assert ("mn", ">=") in E.variables_du_marche("btts|Oui") and ("mn", "<=") in E.variables_du_marche("btts|Non")
    assert ("d", ">=") in E.variables_du_marche("double_chance|1N") and ("d", "<=") in E.variables_du_marche("double_chance|N2")
    assert ("dom", "<=") in E.variables_du_marche("over_under_domicile_2.5|moins")
    assert ("d", "<=") not in E.variables_du_marche("double_chance|1N")
    assert ("total", ">=") not in E.variables_du_marche("over_under_3.5|moins")
    assert ("dom", "<=") not in E.variables_du_marche("over_under_exterieur_2.5|moins")


def test_les_deux_candidats_sont_dans_la_grille_annoncee():
    assert ("total", "<=", 2.8) in E.configs("over_under_3.5|moins")
    assert ("absd", ">=", 0.6) in E.configs("double_chance|12")


# ---- jeux, doublons, fuite ----
def test_jeux_disjoints_sans_doublon_ni_resultat_manquant_ni_cote_tardive(table):
    lignes, audit = table
    ids = [r["id"] for r in lignes]
    assert len(ids) == len(set(ids))
    assert all(r["jour"] < E.DEBUT_B for r in lignes if r["src"] == "FD")             # Football-Data s'arrête avant l'archive
    assert {E.jeu(r) for r in lignes} == {"R", "V", "B"}
    assert all(r["jour"] < E.FIN_R for r in lignes if E.jeu(r) == "R") and all(E.FIN_R <= r["jour"] < E.DEBUT_B for r in lignes if E.jeu(r) == "V")
    assert audit["resultats_manquants"] == audit["cotes_prises_apres_le_coup_d_envoi"] == audit["cotes_sans_horodatage"] == audit["ids_en_double"] == 0
    assert audit["matchs_en_double_meme_source"] == 0


def test_recouvrement_des_sources_est_detecte_et_ecarte():
    rec = E.recouvrement_fd_archive()
    assert rec["retrouves_dans_archive"] > 100 and rec["dont_meme_score"] == rec["retrouves_dans_archive"]


def test_le_choix_de_la_regle_ne_lit_que_le_reglage(table):
    lignes, _ = table
    base = E.etudier(lignes)
    modif = copy.deepcopy(lignes)
    for r in modif:
        if E.jeu(r) != "R":
            r["h"], r["a"] = r["a"] + 3, r["h"] + 1        # résultats de V et B bouleversés
    autre = E.etudier(modif)
    for k, m in base.items():
        if m["etudie"]:
            assert {mo: x["config"] for mo, x in m["regles"].items()} == {mo: x["config"] for mo, x in autre[k]["regles"].items()}, k


def test_analyse_du_moteur_insensible_aux_matchs_futurs():
    params = P.charger()
    for m in (x for x in RB.charger_archive_archetype() if x["jour"] == "2026-10-10"):
        avant = coeur.analyser_match(m["dom"], m["ext"], m["jour"], params)
        if avant["statut"] == "analyse":
            break
    assert avant["statut"] == "analyse"
    d, e = copy.deepcopy(m["dom"]), copy.deepcopy(m["ext"])
    for eq, dom in ((d, True), (e, False)):
        for jour in ("2026-10-10", "2026-10-11", "2026-12-01"):         # le jour même et le futur : doivent être ignorés
            eq["matchs"].append({"date": jour, "domicile": dom, "buts_marques": 9, "buts_encaisses": 9})
    apres = coeur.analyser_match(d, e, m["jour"], params)
    assert avant["niveaux"] == apres["niveaux"] and avant["statut"] == apres["statut"]
    assert [f["marche"] for l in avant["onglets"].values() for f in l] == [f["marche"] for l in apres["onglets"].values() for f in l]


# ---- verdicts, candidats ----
def _ev(v_g, v_n, b_jouables, b_rend, w_haut=0.8):
    def j(g, n):
        lo, hi = E.wilson(g, n)
        return {"matchs": n, "gagnes": g, "taux": g / n, "wilson_bas_95": lo, "wilson_haut_95": hi, "reference_tous_les_paris_du_marche": {"taux": 0.6}}
    return {"R": j(60, 100), "V": j(v_g, v_n), "B": {**j(30, 50), "jouables_cote_min": b_jouables, "taux_des_jouables": {"taux": 0.6, "wilson_haut_95": w_haut},
                                                    "rendement_jouables": {"rendement": b_rend, "ic95": [b_rend - .1, b_rend + .1], "taux_equilibre": 0.6}}}


def test_verdict_trois_cas_acceptes_trois_rejetes():
    assert E.verdict(_ev(700, 1000, 50, 0.01), 0.6, True)[0] == "sous_observation"
    assert E.verdict(_ev(700, 1000, 50, 0.0), None, True)[0] == "sous_observation"
    assert E.verdict(_ev(700, 1000, 50, 0.02), 0.65, True)[0] == "sous_observation"
    assert E.verdict(_ev(580, 1000, 50, 0.01), 0.6, True)[0] == "non_valide"       # Wilson bas sous la barre
    assert E.verdict(_ev(700, 1000, 10, 0.01), 0.6, True)[0] == "non_valide"       # trop peu de paris jouables
    assert E.verdict(_ev(700, 1000, 50, -0.05), 0.6, True)[0] == "non_valide"      # rendement net négatif


def test_jamais_valide_et_les_candidats_peuvent_etre_rejetes(table):
    lignes, _ = table
    res = E.etudier(lignes)
    assert all(m["verdict"] in ("sous_observation", "non_valide") for m in res.values() if m["etudie"])
    c = {k: res[k]["candidat_impose"] for k in E.CANDIDATS_IMPOSES}
    assert tuple(c["over_under_3.5|moins"]["config"]) == ("total", "<=", 2.8) and tuple(c["double_chance|12"]["config"]) == ("absd", ">=", 0.6)
    assert all(x["verdict"] == "non_valide" for x in c.values())                    # conclusion reportée dans le rapport
    assert E.verdict(c["double_chance|12"]["evaluation"], res["double_chance|12"]["objectif"]["taux_equilibre"], False)[0] == c["double_chance|12"]["verdict"]


def test_objectif_indefini_sans_assez_de_paris_jouables():
    l = [{"src": "ARCH", "jour": "2026-10-01", "h": 1, "a": 0, "moy": {}, "mk": {"btts|Oui": [0.8, 1, 1, 1, 1.5]}} for _ in range(10)]
    assert E.objectif_du_marche(l, "btts|Oui")["taux_equilibre"] is None


def test_etude_reproductible(table):
    lignes, _ = table
    assert E.etudier(lignes) == E.etudier(lignes)


# ---- aucune intégration ----
def test_etude_non_branchee_a_la_production():
    for f in (RACINE / "alpha_serie").glob("*.py"):
        if f.name != "etude_marches.py":
            assert "etude_marches" not in f.read_text(encoding="utf-8"), f.name
    suivi = (RACINE / "alpha_serie" / "suivi.py").read_text(encoding="utf-8")
    assert not re.search(r"etude_marches", suivi)
    ecr = (RACINE / "alpha_serie" / "etude_marches.py").read_text(encoding="utf-8")
    assert "journal.jsonl" not in ecr and "_ajouter" not in ecr and "geler" not in ecr          # aucun accès au journal gelé
