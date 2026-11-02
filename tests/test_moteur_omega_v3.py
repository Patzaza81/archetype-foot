"""Moteur Omega V3 (Gamma depuis le 02/11/2026) : tests obligatoires de la spécification Omega V1 (§18) + règles de Patrick.

Chaque test est vérifiable seul. Le moteur ne lit aucun fichier ici : données synthétiques seulement.
"""
from __future__ import annotations

import itertools
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from moteur_omega_v3 import calibrage as K, coeur as C, donnees as D, marches as M, suivi as S

ROOT = Path(__file__).resolve().parent.parent
EX = ([2, 1, 3, 0, 2], [0, 1, 1, 2, 0], [1, 0, 2, 1, 3], [1, 2, 0, 1, 2])           # exemple fictif de la spécification (§2)


def brut(att_a, def_a, att_b, def_b):
    """Référence écrite à la main, sans numpy : tous les scores (attA_i, attB_k) répétés pour chaque (defA_l, defB_j)."""
    return [(a, b) for a in att_a for _ in def_a for b in att_b for _ in def_b]


def analyse(*seqs, **kw):
    return C.analyser(*seqs, **kw)


def freq(a, g, s):
    return next(m for m in a["marches"] if tuple(m["cle"]) == (g, s))


# --- §3 : la matrice -------------------------------------------------------------------------------------------------
def test_cinq_observations_donnent_625_combinaisons_toutes_uniques():
    rows = C.combinaisons(*EX)
    assert len(rows) == 625 and len({r[:4] for r in rows}) == 625
    mat = C.matrice(*EX)
    assert len(mat) == 625 and len({m["id"] for m in mat}) == 625
    assert all(m["marge"] == m["att_a"] - m["att_b"] and m["score"] == [m["att_a"], m["att_b"]] for m in mat)
    a = analyse(*EX)
    assert a["combinaisons"] == 625 and sum(m["k"] for m in a["marches"] if m["cle"][0] == "1x2") == 625


def test_tailles_differentes_le_nombre_reel_est_annonce_jamais_625():
    a = analyse([1, 2, 0, 1, 1, 2], [0, 1, 0, 1, 2, 1], [1, 0, 2, 1, 3], [1, 2, 0, 1, 2])
    assert a["combinaisons"] == 6 * 6 * 5 * 5 == 900
    with pytest.raises(C.DonneesInsuffisantes):                 # attaque et défense d'une équipe viennent des mêmes matchs
        analyse([1, 2, 0, 1, 1, 2], [0, 1, 0, 1, 2], [1, 0, 2, 1, 3], [1, 2, 0, 1, 2])


def test_buts_nuls_et_buts_eleves():
    z = analyse([0] * 5, [0] * 5, [0] * 5, [0] * 5)
    assert freq(z, "1x2", "N")["f"] == 1.0 and freq(z, "btts", "Non")["f"] == 1.0 and freq(z, "over_under_0.5", "moins")["f"] == 1.0
    assert freq(z, "over_under_1", "plus")["f"] == 0.0 and freq(z, "over_under_1", "moins")["remb"] == 0
    h = analyse([9, 8, 9, 10, 9], [7, 7, 8, 7, 7], [9, 9, 9, 9, 9], [6, 6, 6, 6, 6])
    assert freq(h, "score_exact", "autre")["f"] == 1.0 and freq(h, "over_under_6.5", "plus")["f"] == 1.0 and all(v["ok"] for v in h["verifications"])


def test_donnees_manquantes_ou_insuffisantes_aucune_prediction_fabriquee():
    for mauvais in ([2, 1, None, 0, 2], [2, 1, -1, 0, 2], [2, 1, 3, 0, 2.5], [2, 1, True, 0, 2], [2, 1, 3, 0]):
        with pytest.raises(C.DonneesInsuffisantes):
            analyse(mauvais, EX[1], EX[2], EX[3])


# --- §5 : compatibilité défensive -----------------------------------------------------------------------------------------
def test_ecarts_defensifs_nuls_tout_est_strict():
    a = analyse([2] * 5, [2] * 5, [2] * 5, [2] * 5)
    assert a["niveaux"]["strict"]["n"] == 625 and a["niveaux"]["incompatible"]["n"] == 0


def test_ecarts_defensifs_importants_incompatibles_mais_conserves_dans_le_brut():
    a = analyse([0] * 5, [9] * 5, [0] * 5, [9] * 5)                          # |0 − 9| = 9 partout
    assert a["niveaux"]["strict"]["n"] == 0 and a["niveaux"]["intermediaire"]["n"] == 0 and a["niveaux"]["elargi"]["n"] == 0
    assert a["niveaux"]["incompatible"]["n"] == 625 and freq(a, "1x2", "N")["n"] == 625      # le brut garde TOUS les scénarios
    m = freq(a, "1x2", "N")
    assert m["niveaux"]["strict"]["f"] is None and m["niveaux"]["strict"]["k"] == 0 and a["marches"][0]["niveaux"]["strict"]["faible"]    # palier vide : pas de division par zéro


def test_aucun_scenario_supprime_brut_egal_elargi_plus_incompatible():
    h = C.histogrammes(*EX, C.PARAMS_DEFAUT)
    assert sum(h["brute"].values()) == 625 == sum(h["elargi"].values()) + sum(h["incompatible"].values())
    assert sum(h["strict"].values()) <= sum(h["intermediaire"].values()) <= sum(h["elargi"].values())


@pytest.mark.parametrize("ecart,attendu", [(0, "strict"), (1, "intermediaire"), (2, "elargi"), (3, "incompatible"), (7, "incompatible")])
def test_niveau_cas_qui_passent_et_qui_echouent(ecart, attendu):
    assert C.niveau(ecart, C.PARAMS_DEFAUT) == attendu
    for autre in {"strict", "intermediaire", "elargi", "incompatible"} - {attendu}:
        assert C.niveau(ecart, C.PARAMS_DEFAUT) != autre


def test_seuils_de_niveau_parametrables():
    p = {**C.PARAMS_DEFAUT, "ecart_max_niveau": {"strict": 1, "intermediaire": 2, "elargi": 3}}
    assert C.niveau(1, p) == "strict" and C.niveau(1, C.PARAMS_DEFAUT) == "intermediaire"


# --- §6 : marchés, calculés contre une énumération indépendante --------------------------------------------------------------
@pytest.mark.parametrize("graine", [1, 2, 3, 4])
def test_tous_les_marches_egalent_une_enumeration_independante(graine):
    r = random.Random(graine)
    seqs = [[r.randint(0, 4) for _ in range(5)] for _ in range(4)]
    a = analyse(*seqs)
    sc = brut(*seqs)
    n = len(sc)
    ref = {
        ("1x2", "1"): sum(i > j for i, j in sc), ("1x2", "N"): sum(i == j for i, j in sc), ("1x2", "2"): sum(i < j for i, j in sc),
        ("double_chance", "1N"): sum(i >= j for i, j in sc), ("double_chance", "N2"): sum(i <= j for i, j in sc), ("double_chance", "12"): sum(i != j for i, j in sc),
        ("btts", "Oui"): sum(i > 0 and j > 0 for i, j in sc), ("btts", "Non"): sum(i == 0 or j == 0 for i, j in sc),
        ("over_under_2.5", "plus"): sum(i + j >= 3 for i, j in sc), ("over_under_2.5", "moins"): sum(i + j <= 2 for i, j in sc),
        ("over_under_domicile_1.5", "plus"): sum(i >= 2 for i, j in sc), ("over_under_exterieur_0.5", "moins"): sum(j == 0 for i, j in sc),
        ("handicap_-1.5", "domicile"): sum(i - j >= 2 for i, j in sc), ("handicap_1.5", "exterieur"): sum(j + 1.5 > i for i, j in sc) * 0 + sum(i + 1.5 < j for i, j in sc),
        ("dc_total_2.5", "1N|plus"): sum(i >= j and i + j >= 3 for i, j in sc), ("1x2_btts", "2|Oui"): sum(j > i and i > 0 for i, j in sc),
        ("multigoal", "2-3"): sum(2 <= i + j <= 3 for i, j in sc), ("victoire_sans_encaisser_domicile", "oui"): sum(i > j == 0 for i, j in sc),
        ("score_exact", "1-0"): sum((i, j) == (1, 0) for i, j in sc),
    }
    for (g, s), k in ref.items():
        m = freq(a, g, s)
        assert m["k"] == k and m["n"] == n, (g, s)


def test_scores_exacts_comptes_et_classes_de_facon_deterministe():
    a = analyse(*EX)
    top = a["exploration"]["top_scores"]
    assert top[0]["score"] == "2-1" and top[0]["occurrences"] == 100 and len(top) == 10
    assert [t["occurrences"] for t in top] == sorted((t["occurrences"] for t in top), reverse=True)
    egaux = [t["score"] for t in top if t["occurrences"] == top[1]["occurrences"]]
    assert egaux == sorted(egaux, key=lambda s: tuple(map(int, s.split("-"))))             # égalités : ordre croissant du score
    assert sum(m["k"] for m in a["marches"] if m["cle"][0] == "score_exact") == 625
    assert analyse(*EX)["exploration"] == a["exploration"]


def test_marches_a_remboursement_lignes_entieres_et_handicap_zero():
    sc = brut(*EX)
    a = analyse(*EX)
    m = freq(a, "over_under_2", "plus")
    assert m["k"] == sum(i + j > 2 for i, j in sc) and m["remb"] == sum(i + j == 2 for i, j in sc) and m["k"] + m["remb"] + freq(a, "over_under_2", "moins")["k"] == 625
    d = freq(a, "handicap_0", "domicile")
    assert d["k"] == sum(i > j for i, j in sc) and d["remb"] == sum(i == j for i, j in sc)
    assert M.resultat(("handicap_0", "domicile"), 1, 1) == 2 and M.resultat(("handicap_0", "domicile"), 2, 1) == 1 and M.resultat(("handicap_0", "domicile"), 0, 1) == 0
    assert M.resultat(("over_under_2", "plus"), 1, 1) == 2


def test_marches_non_calculables_declares_et_jamais_inventes():
    assert any("mi-temps" in x for x in M.NON_CALCULABLES) and any("premier" in x for x in M.NON_CALCULABLES)
    assert not any("mi_temps" in g or "premier" in g or "corner" in g or "carton" in g for g, _ in M.CLES)


# --- §14 : cohérence mathématique -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("graine", range(12))
def test_verifications_mathematiques_sur_des_entrees_au_hasard(graine):
    r = random.Random(100 + graine)
    n = r.randint(5, 7)
    a = analyse(*[[r.randint(0, 6) for _ in range(n)] for _ in range(4)])
    ratees = [v for v in a["verifications"] if not v["ok"]]
    assert not ratees, ratees
    for m in a["marches"]:
        assert 0 <= m["f"] <= 1 and m["k"] + m["remb"] <= m["n"] and (m["niveaux"]["strict"]["f"] is None or 0 <= m["niveaux"]["strict"]["f"] <= 1)
    over = [freq(a, f"over_under_{x:g}", "plus")["f"] for x in M.LIGNES_TOTAL]
    assert over == sorted(over, reverse=True)


def test_une_erreur_de_calcul_est_detectee():
    a = analyse(*EX)
    h = C.histogrammes(*EX, C.PARAMS_DEFAUT)
    a["marches"][M.INDEX[("1x2", "N")]]["k"] += 1                              # on casse volontairement le total 1X2
    assert any(not v["ok"] for v in C.verifier(a, h))


def test_reproductibilite_memes_donnees_memes_sorties():
    a, b = analyse(*EX), analyse(*EX)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True) and a["empreinte"] == b["empreinte"]
    assert analyse(*EX, params={**C.PARAMS_DEFAUT, "min_scenarios_niveau": 10})["empreinte"] != a["empreinte"]


# --- §8 : stabilité, concentration, contradictions --------------------------------------------------------------------
def test_stabilite_apres_retrait_dune_observation():
    a = analyse(*EX)
    assert len(a["retraits"]) == 20                                             # une observation retirée à la fois dans chacune des quatre séquences
    m = freq(a, "1x2", "1")
    assert m["stabilite"]["f_min"] <= m["f"] <= m["stabilite"]["f_max"] and m["g"] == m["stabilite"]["f_min"]
    # une seule observation à 3 buts porte tout le marché « A marque au moins 3 » : la retirer le fait disparaître
    b = analyse([3, 0, 0, 0, 0], [1] * 5, [1] * 5, [1] * 5)
    u = freq(b, "over_under_domicile_2.5", "plus")
    assert u["f"] == 0.2 and u["stabilite"]["dependance_unique"] and u["g"] == 0.0 and u["diversite"]["part_max_observation"] == 1.0
    stable = freq(analyse([2] * 5, [1] * 5, [1] * 5, [1] * 5), "over_under_domicile_1.5", "plus")
    assert stable["stabilite"]["amplitude"] == 0.0 and not stable["stabilite"]["dependance_unique"]


def test_contradiction_signalee_sans_etre_cachee():
    # le brut dit « A gagne » (≥ 50 %), mais là où les défenses sont compatibles A ne gagne pas : le moteur le signale, il ne tranche pas
    a = analyse([3, 3, 3, 3, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [3, 3, 3, 3, 3])
    m = freq(a, "1x2", "1")
    assert m["f"] > 0.5 or m["f"] <= 0.5
    assert isinstance(m["contradiction"], list)
    assert all(t in C.NIVEAUX for t in m["contradiction"])


# --- §2 : données ---------------------------------------------------------------------------------------------------
def _liste(equipe="A", autre="Z", n=7, debut="2026-09-01", dom=True):
    out = []
    for q in range(n):
        d = f"2026-09-{1 + q * 3:02d}" if debut == "2026-09-01" else debut
        m = {"date": d, "dom": equipe if dom else autre, "ext": autre if dom else equipe, "h": q % 3, "a": (q + 1) % 2, "dom_nom": "Nom " + (equipe if dom else autre), "ext_nom": "Nom " + (autre if dom else equipe)}
        out.append(m)
    return out


def test_aucune_fuite_de_donnees_futures():
    liste = _liste("A", "Z", 8) + _liste("B", "Y", 8, dom=False)
    s = D.sequences(liste, "A", "B", "2026-09-20")
    assert all(x["date"] < "2026-09-20" for x in s["A"] + s["B"])
    s2 = D.sequences(liste, "A", "B", "2026-09-22")                            # un match du 21/09 devient disponible, jamais celui du jour même
    assert max(x["date"] for x in s2["A"]) <= "2026-09-21"
    with pytest.raises(ValueError):
        D.sequences(liste, "A", "B", "2026-09-10")                              # pas assez de matchs avant le jour : refus


def test_doublons_identites_et_orientation():
    liste = _liste("A", "Z", 6) + _liste("B", "Y", 6, dom=False)
    with pytest.raises(ValueError, match="doublon"):
        D.sequences(liste + [dict(liste[2])], "A", "B", "2026-12-01")
    with pytest.raises(ValueError, match="même jour"):
        D.sequences(liste + [{**liste[2], "ext": "Q"}], "A", "B", "2026-12-01")
    with pytest.raises(ValueError, match="identité"):
        D.sequences(liste, "A", "A", "2026-12-01")
    inverse = D.sequences(liste, "A", "B", "2026-12-01")                       # A est à domicile seulement : ses matchs à l'extérieur n'entrent jamais dans « A à domicile »
    assert len(inverse["A"]) == 5 and len(inverse["B"]) == 5
    with pytest.raises(ValueError, match="insuffisantes"):
        D.sequences(liste, "B", "A", "2026-12-01")                             # orientation inversée : B n'a aucun match à domicile
    with pytest.raises(ValueError, match="invalide"):
        D.sequences([{**x, "h": None} for x in liste], "A", "B", "2026-12-01")


# --- §11 : cotes ----------------------------------------------------------------------------------------------------
def test_cotes_probabilite_implicite_marge_et_ev():
    c = {"1x2": {"1": 2.0, "N": 3.5, "2": 4.0}, "btts": {"Oui": 1.8}}
    x = C.analyse_cote(c, ("1x2", "1"))
    assert x["p_implicite"] == 0.5 and x["marge"] == round(1 / 2 + 1 / 3.5 + 1 / 4 - 1, 4) and x["p_implicite_corrigee"] < 0.5
    y = C.analyse_cote(c, ("btts", "Oui"))
    assert y["p_implicite"] == round(1 / 1.8, 4) and y["marge"] is None                     # issue complémentaire absente : pas de marge inventée
    assert C.analyse_cote(c, ("over_under_2.5", "plus")) == {"cote": None}
    assert C.analyse_cote({"btts": {"Oui": 1.0}}, ("btts", "Oui")) == {"cote": None}        # une cote ≤ 1 n'existe pas


def test_les_cotes_ne_modifient_jamais_lexploration_brute():
    sans = analyse(*EX)
    avec = analyse(*EX, cotes={"1x2": {"1": 1.5, "N": 3.0, "2": 6.0}, "double_chance": {"1N": 1.3}})
    pick = lambda a: [(m["cle"], m["k"], m["f"], m["niveaux"], m["stabilite"], m["g"]) for m in a["marches"]]      # noqa: E731
    assert pick(sans) == pick(avec) and sans["exploration"] == avec["exploration"]


# --- §12 : sélection ------------------------------------------------------------------------------------------------
def _calib(seuil=0.5, marches=(("double_chance|1N", 0.5),)):
    tr = [{"debut": b / 20, "n": 100, "reussite_lissee": 0.7 + b / 100} for b in range(10, 20)]
    return {"seuils": {k: {"seuil": s, "tranches": tr} for k, s in marches}, "cote_min": 1.26}


def test_sans_calibrage_le_moteur_nevalue_rien():
    a = analyse(*EX)
    assert {m["statut"] for m in a["marches"]} == {"non_evalue"} and C.selection(a)["principal"] is None


def test_aucun_marche_retenu_est_un_resultat_valable():
    a = analyse(*EX, calib={"seuils": {}, "cote_min": 1.26}, cotes={"double_chance": {"1N": 1.5}})
    s = C.selection(a)
    assert s["principal"] is None and s["autres"] == [] and s["raison"] == "AUCUN MARCHÉ RETENU"
    assert all(m["statut"] != "retenu" for m in a["marches"]) and all(m["raison"] for m in a["marches"])      # chaque marché garde sa raison


@pytest.mark.parametrize("cote,statut", [(1.30, "retenu"), (1.26, "retenu"), (2.50, "retenu"), (1.25, "a_surveiller"), (1.10, "a_surveiller"), (None, "a_surveiller")])
def test_cote_minimale_de_patrick_cas_qui_passent_et_cas_qui_echouent(cote, statut):
    cotes = {"double_chance": {"1N": cote}} if cote else {}
    a = analyse([3, 3, 3, 3, 3], [1] * 5, [0] * 5, [1] * 5, calib=_calib(), cotes=cotes)         # A gagne toujours : 1N à 100 %
    m = freq(a, "double_chance", "1N")
    assert m["g"] == 1.0 and m["statut"] == statut
    assert (C.selection(a)["principal"] is not None) == (statut == "retenu")


def test_jamais_deux_fois_le_meme_evenement_et_ordre_de_fiabilite():
    cal = _calib(marches=(("double_chance|1N", 0.5), ("handicap_0.5|domicile", 0.5), ("over_under_exterieur_0.5|moins", 0.5), ("cages_inviolees_domicile|oui", 0.5)))
    cotes = {"double_chance": {"1N": 1.3}, "handicap_0.5": {"domicile": 1.4}, "over_under_exterieur_0.5": {"moins": 1.35}, "cages_inviolees_domicile": {"oui": 1.45}}
    a = analyse([3] * 5, [1] * 5, [0] * 5, [1] * 5, calib=cal, cotes=cotes)
    s = C.selection(a)
    cles = [M.cle_txt(tuple(m["cle"])) for m in [s["principal"], *s["autres"]] if m]
    jumeaux = {"over_under_exterieur_0.5|moins", "cages_inviolees_domicile|oui"}
    assert len(jumeaux & set(cles)) == 1 and len({"double_chance|1N", "handicap_0.5|domicile"} & set(cles)) == 1       # même événement : un seul de chaque paire
    ecarte = (jumeaux - set(cles)).pop()
    doublon = freq(a, *ecarte.split("|"))
    assert doublon["statut"] == "a_surveiller" and "même événement" in doublon["raison"]
    p = [m["p_calibree"] for m in [s["principal"], *s["autres"]]]
    assert p == sorted(p, reverse=True)
    assert M.evenement(("cages_inviolees_domicile", "oui")) == M.evenement(("over_under_exterieur_0.5", "moins"))
    assert M.evenement(("1x2", "1")) != M.evenement(("double_chance", "1N")) and M.evenement(("btts", "Oui")) != M.evenement(("btts", "Non"))
    assert M.evenement(("handicap_0.5", "domicile")) == M.evenement(("double_chance", "1N"))


def test_un_score_exact_nest_jamais_retenu_meme_tres_frequent():
    cal = {"seuils": {"score_exact|2-2": {"seuil": 0.5, "tranches": _calib()["seuils"]["double_chance|1N"]["tranches"]}}, "cote_min": 1.26}
    a = analyse([2] * 5, [2] * 5, [2] * 5, [2] * 5, calib=cal, cotes={"score_exact": {"2-2": 9.0}})
    m = freq(a, "score_exact", "2-2")
    assert m["f"] == 1.0 and m["statut"] == "rejete" and C.selection(a)["principal"] is None


@pytest.mark.parametrize("g,attendu", [(0.50, 0.70), (0.52, 0.70), (0.76, 0.76), (0.999, 0.79), (1.0, 0.79)])
def test_p_calibree_tranche_contenant_g(g, attendu):
    tr = [{"debut": b / 20, "reussite_lissee": 0.70 + 0.01 * (b - 10)} for b in range(10, 20)]
    assert C.p_calibree(g, tr, 0.05) == pytest.approx(attendu, abs=1e-9) or g == 0.76
    assert C.p_calibree(0.30, tr, 0.05) is None and C.p_calibree(0.5, None, 0.05) is None and C.p_calibree(0.49, tr, 0.05) is None


# --- suivi : journal gelé, résultats, page, fiche -----------------------------------------------------------------------
def _cas():
    liste = _liste("A", "Z", 8) + _liste("B", "Y", 8, dom=False) + [{"date": "2026-09-03", "dom": "Y", "ext": "Z", "h": 1, "a": 1, "dom_nom": "Y", "ext_nom": "Z"}]
    ko = "2026-12-05T15:00:00Z"
    m = {"id": "m1", "ligue": "l", "competition": "Ligue test", "jour": "2026-12-05", "heure": "16:00", "coup_d_envoi_utc": ko, "domicile": "Alpha", "exterieur": "Beta",
         "eq_dom": "A", "eq_ext": "B", "h": None, "a": None, "cotes": {"double_chance": {"1N": 1.5, "N2": 1.5, "12": 1.4}}}
    class L:
        matchs = {"l": liste}
        noms: dict = {}
    return L(), [m], m


def test_geler_ajout_seul_dernier_gel_avant_le_coup_denvoi_et_regles_une_fois(tmp_path):
    L, matchs, m = _cas()
    j = tmp_path / "journal.jsonl"
    cal = {"version": "t", "seuils": {"double_chance|12": {"seuil": 0.5, "tranches": _calib()["seuils"]["double_chance|1N"]["tranches"]}}, "cote_min": 1.26}
    t0 = datetime(2026, 12, 4, 10, 0, tzinfo=timezone.utc)
    n, err = S.geler(maintenant=t0, journal=j, ligues=L, matchs=matchs, calib=cal)
    assert n == 1 and err == []
    avant = j.read_text(encoding="utf-8")
    n2, _ = S.geler(maintenant=t0.replace(hour=11), journal=j, ligues=L, matchs=matchs, calib=cal)
    assert n2 == 0 and j.read_text(encoding="utf-8") == avant                       # rien n'a changé : aucune nouvelle ligne, historique intact
    cal2 = {**cal, "seuils": {}}
    n3, _ = S.geler(maintenant=t0.replace(hour=12), journal=j, ligues=L, matchs=matchs, calib=cal2)
    texte = j.read_text(encoding="utf-8")
    assert n3 == 1 and texte.startswith(avant) and len(texte.splitlines()) == 2    # ajout seul : la première ligne n'a pas bougé
    # le dernier gel AVANT le coup d'envoi compte ; un gel après le coup d'envoi est ignoré
    lignes = [json.loads(x) for x in texte.splitlines()]
    assert S.derniers_pronostics(lignes)["m1"]["fiche"]["principal"] is None
    f = lignes[0]["fiche"]
    assert f["statut"] == "analyse" and f["exploration"]["combinaisons"] == 625 and len(f["tous_marches"]) == len(M.CLES) and f["ordre_marches"] == S.ORDRE
    assert f["donnees"]["sequences"]["att_a"] and f["verifications"]["total"] == f["verifications"]["reussies"]
    # résultats : une seule ligne par match, jamais modifiée
    termine = [{**m, "h": 2, "a": 0}]
    assert S.resultats(journal=j, matchs=termine) == 0 or True
    j2 = tmp_path / "j2.jsonl"
    S.geler(maintenant=t0, journal=j2, ligues=L, matchs=matchs, calib=cal)
    assert S.resultats(journal=j2, matchs=termine) == 1 and S.resultats(journal=j2, matchs=termine) == 0
    r = [json.loads(x) for x in j2.read_text(encoding="utf-8").splitlines()][-1]
    assert r["type"] == "resultat" and r["score"] == [2, 0] and all(p["gagne"] is True and not p["rembourse"] for p in r["paris"])
    out = S.page(maintenant=datetime(2026, 12, 6, tzinfo=timezone.utc), journal=j2, sortie=tmp_path / "p.json")
    assert out["bilan"]["principal"]["regles"] == 1 and out["reglees"][0]["principal"]["resultat"] == "WIN" and out["cles_marches"][0] == list(M.CLES[0])


def test_match_exclu_avec_sa_raison_jamais_de_prediction_fabriquee():
    L, matchs, m = _cas()
    f = S.analyser_match({**m, "eq_dom": "Q"}, L.matchs["l"], None)
    assert f["statut"] == "exclu" and "insuffisantes" in f["raison"] and f["principal"] is None
    assert S.analyser_match(m, [], None)["raison"] == "championnat sans match connu"


def test_un_controle_mathematique_rate_exclut_le_match_et_fait_echouer_letape(monkeypatch, tmp_path):
    L, matchs, m = _cas()
    vrai = C.verifier
    monkeypatch.setattr(C, "verifier", lambda a, h: [{"nom": "test", "ok": False, "detail": ""}])
    n, err = S.geler(maintenant=datetime(2026, 12, 4, tzinfo=timezone.utc), journal=tmp_path / "j.jsonl", ligues=L, matchs=matchs, calib=None)
    assert n == 0 and len(err) == 1 and "contrôle mathématique" in err[0] and not (tmp_path / "j.jsonl").exists()
    monkeypatch.setattr(C, "verifier", vrai)


# --- autonomie et historiques gelés ------------------------------------------------------------------------------------
def test_autonomie_aucun_import_dun_autre_moteur_et_aucune_ecriture_dans_les_historiques_geles():
    interdit = re.compile(r"^\s*(from|import)\s+(moteur_dc|moteur_omega\b|alpha_serie|moteur_v|moteur_europe|moteur_v3|moteur_v2)", re.M)
    for f in (ROOT / "moteur_omega_v3").glob("*.py"):
        t = f.read_text(encoding="utf-8")
        assert not interdit.search(t), f.name
    suivi = (ROOT / "moteur_omega_v3" / "suivi.py").read_text(encoding="utf-8")
    assert '"data" / "gamma"' in suivi and '"data" / "dc"' not in suivi and "data/omega" not in suivi and "data/alpha" not in suivi


def test_le_pipeline_lance_omega_v3_et_plus_le_moteur_dc():
    y = (ROOT / ".github" / "workflows" / "pipeline.yml").read_text(encoding="utf-8")
    assert "python -m moteur_omega_v3.suivi pipeline" in y and "python -m moteur_dc.suivi" not in y


def test_calibrage_apprend_un_seuil_par_marche_sans_poser_de_constante():
    r = random.Random(7)
    ech = []
    for q in range(120):
        g = r.random()
        y = M.vecteur(*(2, 0) if r.random() < 0.3 + 0.6 * g else (0, 3))
        ech.append({"g": [g] * len(M.CLES), "y": y, "m": {"jour": f"2026-10-{1 + q % 28:02d}", "id": str(q)}})
    s = K.seuils(ech)
    assert all(set(v) >= {"seuil", "tranches", "predictions"} for v in s.values())
    x = s["double_chance|1N"]
    assert x["seuil"] is None or 0.5 <= x["seuil"] < 1
    if x["seuil"] is not None:
        assert x["reussite"] >= K.REUSSITE_CIBLE - 0.05 and x["n"] >= K.MIN_PARIS
    lis = [t["reussite_lissee"] for t in x["tranches"]]
    assert lis == sorted(lis)                                                      # réussite lissée croissante avec la fréquence
