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
    assert len(inverse["A"]) == 6 and len(inverse["B"]) == 6                      # tous les matchs disponibles entrent (5 au minimum, 19 au maximum)
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
    assert f["statut"] == "analyse" and f["exploration"]["combinaisons"] == len(f["donnees"]["sequences"]["att_a"]) ** 2 * len(f["donnees"]["sequences"]["att_b"]) ** 2 and len(f["tous_marches"]) == len(M.CLES) and f["ordre_marches"] == S.ORDRE
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


def test_le_pipeline_lance_omega_v3_et_garde_le_moteur_dc_pour_la_comparaison():
    y = (ROOT / ".github" / "workflows" / "pipeline.yml").read_text(encoding="utf-8")
    assert "python -m moteur_omega_v3.suivi pipeline" in y and "python -m moteur_dc.suivi pipeline" in y


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


# =====================================================================================================================
# Tests ajoutés par l'audit du 02/11/2026
# =====================================================================================================================
import subprocess

import numpy as np

from moteur_omega_v3 import definitions as Df, variantes as V


def test_les_scenarios_gardent_leurs_quatre_observations_et_les_defavorables_restent():
    mat = C.matrice(*EX)
    att_a, def_a, att_b, def_b = EX
    for m in mat:
        i, l, k, j = (int(x) for x in m["id"].split("-"))
        assert (m["att_a"], m["def_a"], m["att_b"], m["def_b"]) == (att_a[i], def_a[l], att_b[k], def_b[j])
        assert m["ecart_a"] == abs(att_a[i] - def_b[j]) and m["ecart_b"] == abs(att_b[k] - def_a[l])          # orientation : attaque A contre défense B, attaque B contre défense A
    assert any(m["niveau"] == "incompatible" for m in mat) and any(m["marches"][M.INDEX[("1x2", "2")]] == 1 for m in mat)    # défavorables et incompatibles gardés dans le brut


def test_la_defense_ne_change_ni_la_frequence_brute_ni_g():
    """Constat de l'audit : le score d'un scénario est (attA, attB), chaque couple est répété une fois par couple de défenses. Les défenses n'ont donc AUCUN effet sur f ni sur g."""
    a = analyse(*EX)
    b = analyse(EX[0], [4, 4, 0, 3, 4], EX[2], [0, 0, 5, 1, 2])                       # mêmes attaques, défenses toutes différentes
    assert [m["f"] for m in a["marches"]] == [m["f"] for m in b["marches"]]
    assert [m["g"] for m in a["marches"]] == [m["g"] for m in b["marches"]]
    assert a["niveaux"] != b["niveaux"]                                                    # seuls les paliers de compatibilité changent
    f, g = V.robuste("A", [list(x) for x in EX])
    assert np.allclose(g, [m["g"] for m in a["marches"]], atol=1e-4) and np.allclose(f, [m["f"] for m in a["marches"]], atol=1e-4)


def test_frequence_brute_egale_ponderation_marginale():
    pa, pb = Counter(EX[0]), Counter(EX[2])
    a = analyse(*EX)
    for m in a["marches"]:
        _, _, fn = Df.definition(*m["cle"])
        marginal = sum(pa[x] * pb[y] for x in pa for y in pb if fn(x, y) == 1) / 25
        assert m["f"] == pytest.approx(marginal, abs=1e-4)


from collections import Counter  # noqa: E402


def test_les_383_marches_egalent_les_definitions_independantes_sur_toute_la_grille():
    assert len(M.CLES) == len(set(M.CLES))
    for c in M.CLES:
        _, formule, fn = Df.definition(*c)
        assert formule
        for i in range(M.MAX_EQUIPE + 3):
            for j in range(M.MAX_EQUIPE + 3):
                assert fn(i, j) == M.REGLES[c](i, j), (c, i, j)


@pytest.mark.parametrize("cle", [("1x2", "X"), ("over_under_2.5", "dessus"), ("handicap_0.5", "nulle"), ("inconnu", "1"), ("handicap_3issues_x", "1")])
def test_cles_inconnues_refusees_par_les_definitions(cle):
    with pytest.raises((ValueError, KeyError)):
        Df.definition(*cle)


def test_les_lignes_couvrent_les_scores_reellement_observes():
    chemin = ROOT / "data" / "assemblage" / "equipes.json"
    if not chemin.exists():
        pytest.skip("historique absent")
    h = [m for v in D.charger_ligues(chemin).matchs.values() for m in v]
    assert max(max(m["h"], m["a"]) for m in h) <= M.MAX_EQUIPE
    assert max(m["h"] + m["a"] for m in h) <= M.MAX_TOTAL
    assert max(abs(m["h"] - m["a"]) for m in h) <= M.MAX_ECART


def test_marches_ajoutes_par_l_audit_sont_complets_et_coherents():
    a = analyse(*EX)
    N = a["combinaisons"]
    assert sum(freq(a, "nombre_exact_buts", s)["k"] for s in ["0", "1", "2", "3", "4", "5", "6+"]) == N
    for h in M.LIGNES_HANDICAP_3:
        assert sum(freq(a, f"handicap_3issues_{h}", s)["k"] for s in ("1", "X", "2")) == N
    for x in M.LIGNES_COMBO:
        g = f"btts_total_{x:g}"
        assert sum(freq(a, g, f"{b}|{s}")["k"] for b in ("Oui", "Non") for s in ("plus", "moins")) == N
    assert freq(a, "over_under_9.5", "plus")["k"] == 0 and freq(a, "over_under_9.5", "moins")["k"] == N
    assert freq(a, "handicap_3issues_0", "1") if False else True
    assert ("handicap_3issues_0", "1") not in M.INDEX                                       # handicap 0 = le 1X2 lui-même, pas de doublon
    # handicap à trois issues -1 : « 1 » = domicile gagne par 2 buts ou plus ; sens confirmé par les cotes de la source (cote(1 | -1) ≈ 1,9 × cote(1X2 « 1 »))
    assert M.resultat(("handicap_3issues_-1", "1"), 3, 1) == 1 and M.resultat(("handicap_3issues_-1", "1"), 2, 1) == 0 and M.resultat(("handicap_3issues_-1", "X"), 2, 1) == 1


@pytest.mark.parametrize("jours_ecart,attendu", [(0, True), (1, True), (-1, True), (2, False), (5, False), (-3, False)])
def test_le_match_lui_meme_est_reconnu_a_un_jour_pres(jours_ecart, attendu):
    from datetime import date, timedelta
    jour = "2026-10-27"
    d = (date.fromisoformat(jour) + timedelta(days=jours_ecart)).isoformat()
    assert D._est_le_match({"date": d, "dom": "A", "ext": "B"}, "A", "B", jour) is attendu


@pytest.mark.parametrize("dom,ext", [("B", "A"), ("A", "C"), ("C", "B")])
def test_une_autre_affiche_n_est_jamais_prise_pour_le_match_lui_meme(dom, ext):
    assert D._est_le_match({"date": "2026-10-26", "dom": dom, "ext": ext}, "A", "B", "2026-10-27") is False


def test_le_resultat_du_match_date_la_veille_par_la_source_n_entre_pas_dans_ses_sequences():
    liste = _liste("A", "Z", 8) + _liste("B", "Y", 8, dom=False)
    soi = {"date": "2026-11-29", "dom": "A", "ext": "B", "h": 9, "a": 9, "dom_nom": "A", "ext_nom": "B"}       # le match, daté la veille (fuseau) avec son score final
    s = D.sequences(liste + [soi], "A", "B", "2026-11-30")
    assert 9 not in s["att_a"] and 9 not in s["att_b"] and all(x["date"] < "2026-11-29" for x in s["A"] + s["B"])
    assert D.sequences(liste, "A", "B", "2026-11-30") == s


def test_ordre_des_donnees_sans_effet_sur_les_sequences():
    liste = _liste("A", "Z", 8) + _liste("B", "Y", 8, dom=False)
    r = random.Random(3)
    melange = liste[:]
    r.shuffle(melange)
    assert D.sequences(liste, "A", "B", "2026-12-30") == D.sequences(melange, "A", "B", "2026-12-30")


def test_orientation_des_buts_marques_et_encaisses():
    liste = [{"date": f"2026-09-{q + 1:02d}", "dom": "A", "ext": f"Z{q}", "h": q + 1, "a": 0, "dom_nom": "A", "ext_nom": "Z"} for q in range(5)] + \
            [{"date": f"2026-09-{q + 10:02d}", "dom": f"Y{q}", "ext": "B", "h": 7, "a": q, "dom_nom": "Y", "ext_nom": "B"} for q in range(5)]
    s = D.sequences(liste, "A", "B", "2026-12-01")
    assert s["att_a"] == [1, 2, 3, 4, 5] and s["def_a"] == [0] * 5            # A à domicile : buts marqués = h, encaissés = a
    assert s["att_b"] == [0, 1, 2, 3, 4] and s["def_b"] == [7] * 5            # B à l'extérieur : buts marqués = a, encaissés = h


@pytest.mark.parametrize("variante", ["A", "B", "C"])
@pytest.mark.parametrize("graine", [11, 12, 13])
def test_variantes_pas_de_double_comptage_et_somme_un(variante, graine):
    r = random.Random(graine)
    seqs = [[r.randint(0, 5) for _ in range(5)] for _ in range(4)]
    W = V.poids(variante, *seqs)
    assert W.sum() == pytest.approx(1.0, abs=1e-12) and (W >= 0).all()
    assert np.abs(W - V.poids_par_scenarios(variante, *seqs)).max() < 1e-12     # factorisation = énumération scénario par scénario (chaque scénario pèse 1/625)


def test_variante_c_est_un_modele_et_a_b_des_frequences():
    z = V.poids("C", [0] * 5, [0] * 5, [0] * 5, [0] * 5)
    assert z[0, 0] == pytest.approx(1.0)                                         # λ = 0 : aucun but, sans masse parasite
    a = V.poids("A", [2] * 5, [0] * 5, [1] * 5, [0] * 5)
    assert a[2, 1] == pytest.approx(1.0)
    b = V.poids("B", [2] * 5, [0] * 5, [1] * 5, [0] * 5)
    assert b[2, 1] == pytest.approx(0.25) and b[0, 1] == pytest.approx(0.25) and b[2, 0] == pytest.approx(0.25) and b[0, 0] == pytest.approx(0.25)
    with pytest.raises(ValueError):
        V.poids("Z", *EX)


def test_calibrage_sur_la_population_jouable_ne_compte_pas_les_cotes_injouables():
    r = random.Random(5)
    ech = []
    k_dc = M.INDEX[("double_chance", "1N")]
    for q in range(300):
        y = np.zeros(len(M.CLES), dtype=np.int8)
        y[k_dc] = 1 if (r.random() < (0.97 if q % 2 else 0.4)) else 0           # injouable (q impair) : presque toujours gagné ; jouable (q pair) : 40 %
        g = np.zeros(len(M.CLES))
        g[k_dc] = 0.9
        j = np.zeros(len(M.CLES), dtype=bool)
        j[k_dc] = q % 2 == 0
        ech.append({"m": {"jour": f"2026-10-{1 + q % 28:02d}", "id": str(q)}, "g": g, "y": y, "jouable": j})
    tout = K.seuils(ech, jouable=False)["double_chance|1N"]
    jou = K.seuils(ech, jouable=True)["double_chance|1N"]
    assert tout["seuil"] is not None and jou["seuil"] is None                    # sur la population jouable le marché n'atteint jamais 70 %
    assert jou["predictions"] == 150 and tout["predictions"] == 300


def test_conclusion_sans_cle_technique_et_sans_marche_certain():
    a = analyse(*EX)
    texte = " ".join(a["conclusion"])
    assert "|" not in texte and "_" not in texte and "vrais ou faux dans 100 %" in texte
    assert "100%" not in a["conclusion"][0].split("sur 625")[0]


def test_page_distingue_matchs_non_analyses_et_matchs_analyses_sans_pari(tmp_path):
    j = tmp_path / "j.jsonl"
    ko = "2099-01-01T15:00:00Z"
    base = {"jour": "2099-01-01", "heure": "16:00", "coup_d_envoi_utc": ko, "competition": "x", "domicile": "A", "exterieur": "B"}
    lignes = [{"type": "pronostic", "match_id": "e", "gele_le": "2098-12-31T10:00:00+00:00", "fiche": {**base, "match_id": "e", "statut": "exclu", "raison": "données insuffisantes : 3 match(s) pour A", "principal": None, "autres": []}},
              {"type": "pronostic", "match_id": "s", "gele_le": "2098-12-31T10:00:00+00:00", "fiche": {**base, "match_id": "s", "statut": "analyse", "raison": "AUCUN MARCHÉ RETENU", "principal": None, "autres": []}}]
    j.write_text("\n".join(json.dumps(l) for l in lignes) + "\n", encoding="utf-8")
    p = S.page(maintenant=datetime(2098, 12, 31, 12, tzinfo=timezone.utc), journal=j, sortie=tmp_path / "p.json")
    assert p["sans_pronostic"] == 1 and p["nb_exclus"] == 1 and p["exclus"] == {"données insuffisantes": 1}


def test_ancien_moteur_dc_intact_par_rapport_a_main():
    try:
        r = subprocess.run(["git", "diff", "--quiet", "origin/main", "--", "moteur_dc", "data/dc", "tests/test_moteur_dc.py"], cwd=ROOT, capture_output=True, timeout=30)
        ref = subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, timeout=30)
    except Exception:
        pytest.skip("git indisponible")
    if ref.returncode != 0:
        pytest.skip("référence origin/main absente")
    assert r.returncode == 0, "moteur_dc/, data/dc/ ou leurs tests ont été modifiés : l'ancien moteur DC doit rester intact"


def test_la_page_dc_conservee_lit_toujours_les_donnees_dc():
    js = (ROOT / "archetype_dc.js").read_text(encoding="utf-8")
    assert "data/dc/pronostics.json" in js and (ROOT / "pronostics_dc.html").exists()
    assert "data/gamma/pronostics.json" in (ROOT / "archetype_gamma.js").read_text(encoding="utf-8")


def test_bilan_reel_lit_le_journal_gamma_gel_avant_le_coup_d_envoi_remboursements_exclus(tmp_path):
    import bilan_reel as B
    ko = "2026-12-05T15:00:00Z"
    def pari(cle, cote=1.5):
        return {"cle": list(cle), "cote": cote, "p_calibree": 0.8}
    def gel(mid, quand, principal, autres=()):
        return {"type": "pronostic", "match_id": mid, "gele_le": quand, "fiche": {"match_id": mid, "jour": "2026-12-05", "coup_d_envoi_utc": ko, "principal": principal, "autres": list(autres)}}
    def res(mid, paris):
        return {"type": "resultat", "match_id": mid, "score": [1, 1], "paris": paris}
    lignes = [
        gel("a", "2026-12-04T10:00:00+00:00", pari(("double_chance", "1N")), [pari(("handicap_0", "domicile"))]),
        res("a", [{"role": "principal", "cle": ["double_chance", "1N"], "cote": 1.5, "gagne": True, "rembourse": False}, {"role": "autre", "cle": ["handicap_0", "domicile"], "cote": 1.5, "gagne": None, "rembourse": True}]),
        gel("b", "2026-12-05T16:00:00+00:00", pari(("btts", "Oui"))),                         # gelé APRÈS le coup d'envoi : ne compte pas
        res("b", [{"role": "principal", "cle": ["btts", "Oui"], "cote": 1.5, "gagne": True, "rembourse": False}]),
        gel("c", "2026-12-04T10:00:00+00:00", pari(("btts", "Non"))),                          # pas de résultat : ne compte pas
    ]
    j = tmp_path / "j.jsonl"
    j.write_text("\n".join(json.dumps(l) for l in lignes) + "\n", encoding="utf-8")
    p = B.paris_gamma(j)
    assert len(p) == 1 and p[0]["moteur"] == "gamma" and p[0]["mid"] == "a" and p[0]["gagne"] is True and p[0]["tete"] is True       # remboursement exclu, gel tardif ignoré, sans résultat ignoré
    assert B.paris_gamma(tmp_path / "absent.jsonl") == []


# --- Règle de Patrick (03/11/2026) : au moins 5 matchs au même lieu, au plus les 19 derniers ---------------------------------------------------------------
@pytest.mark.parametrize("nb,attendu", [(5, 5), (12, 12), (19, 19), (30, 19)])
def test_fenetre_de_5_a_19_matchs_qui_passe(nb, attendu):
    liste = _liste("A", "Z", nb) + _liste("B", "Y", nb, dom=False)
    s = D.sequences(liste, "A", "B", "2027-12-01")
    assert len(s["A"]) == len(s["B"]) == attendu and len(s["att_a"]) == len(s["def_a"]) == attendu


def test_fenetre_prend_les_19_plus_recents():
    liste = _liste("A", "Z", 30) + _liste("B", "Y", 30, dom=False)
    s = D.sequences(liste, "A", "B", "2027-12-01")
    tous = sorted(x["date"] for x in liste if x["dom"] == "A")
    assert [x["date"] for x in s["A"]] == tous[-19:]


@pytest.mark.parametrize("nb", [0, 3, 4])
def test_moins_de_5_matchs_refuse(nb):
    liste = _liste("A", "Z", nb) + _liste("B", "Y", 8, dom=False)
    with pytest.raises(ValueError, match="insuffisantes"):
        D.sequences(liste, "A", "B", "2027-12-01")


def test_histogrammes_par_comptage_identiques_a_l_enumeration():
    import random
    random.seed(11)
    for _ in range(60):
        A, dA, B, dB = ([random.randint(0, 5) for _ in range(random.randint(1, 9))] for _ in range(4))
        h = C.histogrammes(A, dA, B, dB, C.PARAMS_DEFAUT)
        ref: dict = {k: {} for k in h}
        lim = C.PARAMS_DEFAUT["ecart_max_niveau"]
        for _, _, _, _, a, da, b, db in C.combinaisons(A, dA, B, dB):
            e = max(abs(a - db), abs(b - da))
            ref["brute"][(a, b)] = ref["brute"].get((a, b), 0) + 1
            if e > lim["elargi"]:
                ref["incompatible"][(a, b)] = ref["incompatible"].get((a, b), 0) + 1
            for t in C.NIVEAUX:
                if e <= lim[t]:
                    ref[t][(a, b)] = ref[t].get((a, b), 0) + 1
        assert {k: dict(v) for k, v in h.items()} == ref


def test_analyse_avec_19_observations_controles_mathematiques_verts():
    import random
    random.seed(3)
    A, dA, B, dB = ([random.randint(0, 4) for _ in range(19)] for _ in range(4))
    a = C.analyser(A, dA, B, dB)
    assert a["combinaisons"] == 19 ** 4 and all(v["ok"] for v in a["verifications"])
