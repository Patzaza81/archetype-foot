"""Règle D6 (21/09/2026) : un match n'est analysé que si l'équipe qui reçoit a >= 2 matchs à domicile ET la visiteuse
>= 2 matchs à l'extérieur. Sinon refus explicite ; sinon le moteur tourne sans erreur, sur de petits échantillons aussi."""
import datetime
import math
import random

import pytest

import branchement_moteur as bm
import moteur_v2_6_9 as moteur
import precalcul

NOW = datetime.datetime(2026, 9, 21, 21, 0, tzinfo=datetime.timezone.utc)
COMP = "Pays : Ligue"


def _matchs(n, domicile, rnd, gf_moy, ga_moy):
    return [{"domicile": domicile, "buts_marques": max(0, round(rnd.gauss(gf_moy, 1))), "buts_encaisses": max(0, round(rnd.gauss(ga_moy, 1)))} for _ in range(n)]


def stats_n(nd, ne, seed=1, fort=True):
    rnd = random.Random(seed)
    md = _matchs(nd, True, rnd, 2.0 if fort else 1.2, 0.7 if fort else 1.2)
    me = _matchs(ne, False, rnd, 0.7 if fort else 1.2, 1.9 if fort else 1.2)
    a = {"nb_domicile": nd, "nb_exterieur": 0, "matchs_domicile_bruts": md, "matchs_exterieur_bruts": []}
    b = {"nb_domicile": 0, "nb_exterieur": ne, "matchs_domicile_bruts": [], "matchs_exterieur_bruts": me}
    if md:
        a["gf_domicile"] = sum(m["buts_marques"] for m in md) / nd; a["ga_domicile"] = sum(m["buts_encaisses"] for m in md) / nd
    if me:
        b["gf_exterieur"] = sum(m["buts_marques"] for m in me) / ne; b["ga_exterieur"] = sum(m["buts_encaisses"] for m in me) / ne
    return {("Alpha FC", COMP): a, ("Beta FC", COMP): b}


COTES = {"1x2": {"1": 1.55, "N": 3.7, "2": 4.6}, "double_chance": {"1N": 1.30, "N2": 2.3, "12": 1.28}, "btts": {"Oui": 1.95, "Non": 1.8},
         "over_under_1.5": {"plus": 1.32, "moins": 3.3}, "over_under_2.5": {"plus": 2.0, "moins": 1.8}, "over_under_3.5": {"plus": 3.2, "moins": 1.3}}


def signal(cotes=COTES, mid="t1"):
    return {"match_id": mid, "domicile": "Alpha FC", "exterieur": "Beta FC", "competition": COMP, "date": "2026-09-22", "heure": "20:45",
            "cotes_manuelles": cotes, "url_match": "https://x/m"}


H2H_A_INVAINCU = [{"buts_a": 2, "buts_b": 0}, {"buts_a": 1, "buts_b": 1}, {"buts_a": 3, "buts_b": 1}, {"buts_a": 2, "buts_b": 1}, {"buts_a": 1, "buts_b": 0}]


# ───────────────────────────── frontières de la règle ─────────────────────────────
@pytest.mark.parametrize("nd,ne", [(2, 2), (3, 2), (2, 3), (5, 5), (12, 12)])
def test_a_partir_de_2_et_2_le_match_est_analyse(nd, ne):
    bloc, _ = bm.analyse_signal(signal(), stats_n(nd, ne), NOW, lambda s: [])
    assert bloc["statut"] == "OK", bloc


@pytest.mark.parametrize("nd,ne", [(1, 2), (2, 1), (1, 1), (1, 12), (12, 1)])
def test_sous_2_a_domicile_ou_2_a_l_exterieur_refus_explicite(nd, ne):
    bloc, non_sel = bm.analyse_signal(signal(), stats_n(nd, ne), NOW, lambda s: [])
    assert bloc["statut"] == "NON_EXPORTABLE" and bloc["raison"].startswith("echantillon_insuffisant") and non_sel == []
    assert f"{nd} match(s) à domicile pour Alpha FC" in bloc["raison"] and f"{ne} match(s) à l'extérieur pour Beta FC" in bloc["raison"]
    assert bloc["selection"] == {}


@pytest.mark.parametrize("nd,ne", [(0, 6), (6, 0), (0, 0)])
def test_aucun_match_a_un_lieu_reste_refuse(nd, ne):
    bloc, _ = bm.analyse_signal(signal(), stats_n(nd, ne), NOW, lambda s: [])
    assert bloc["statut"] == "NON_EXPORTABLE" and bloc["selection"] == {}


def test_le_moteur_n_est_pas_appele_pour_un_match_refuse(monkeypatch):
    def piege(*a, **k):
        raise AssertionError("le moteur ne doit pas tourner sous le seuil")
    monkeypatch.setattr(moteur, "analyser_match", piege)
    assert bm.analyse_signal(signal(), stats_n(1, 5), NOW, lambda s: [])[0]["statut"] == "NON_EXPORTABLE"


def test_le_resume_du_pipeline_compte_les_refus_pour_echantillon():
    sigs = [signal(mid="a"), signal(mid="b"), signal(mid="c")]
    for s, (nd, ne) in zip(sigs, [(1, 5), (2, 2), (5, 1)]):
        s["domicile"], s["exterieur"] = f"Alpha{s['match_id']}", f"Beta{s['match_id']}"
    stats = {}
    for s, (nd, ne) in zip(sigs, [(1, 5), (2, 2), (5, 1)]):
        st = stats_n(nd, ne); stats[(s["domicile"], COMP)] = st[("Alpha FC", COMP)]; stats[(s["exterieur"], COMP)] = st[("Beta FC", COMP)]
    r = bm.applique_moteur(sigs, stats, maintenant=NOW, h2h_fetcher=lambda s: [])
    assert r["statuts"] == {"NON_EXPORTABLE": 2, "OK": 1}
    assert r["raisons"] == {"NON_EXPORTABLE / echantillon_insuffisant": 2}


# ───────────────────────────── l'export reste cohérent ─────────────────────────────
def test_les_matchs_refuses_pour_echantillon_ne_sont_pas_exportes():
    def s(mid, bloc):
        return {"match_id": mid, bm.CLE_BLOC: bloc}
    exportables = precalcul.signaux_exportables([
        s("ok", {"statut": "OK"}), s("skip", {"statut": "SKIP", "raison": "V11 : reporté"}),
        s("sans_cotes", {"statut": "NON_EXPORTABLE", "raison": "pas_de_cotes_betpawa"}),
        s("petit", {"statut": "NON_EXPORTABLE", "raison": "echantillon_insuffisant: 1 match(s)..."}), {"match_id": "sans_bloc"}])
    assert [x["match_id"] for x in exportables] == ["ok", "skip", "sans_cotes", "sans_bloc"]


# ───────────────── robustesse : le moteur sur de petits échantillons ─────────────────
def _cotes_aleatoires(rnd):
    c = {}
    p1, pn = rnd.uniform(0.2, 0.7), rnd.uniform(0.15, 0.3); p2 = max(0.05, 1 - p1 - pn); marge = rnd.uniform(1.04, 1.12)
    c["1x2"] = {"1": round(marge / p1, 2), "N": round(marge / pn, 2), "2": round(marge / p2, 2)}
    c["double_chance"] = {"1N": round(marge / min(0.97, p1 + pn), 2), "N2": round(marge / min(0.97, p2 + pn), 2), "12": round(marge / min(0.97, p1 + p2), 2)}
    pb = rnd.uniform(0.35, 0.65); c["btts"] = {"Oui": round(marge / pb, 2), "Non": round(marge / (1 - pb), 2)}
    for L in ("1.5", "2.5", "3.5"):
        po = rnd.uniform(0.2, 0.8); c[f"over_under_{L}"] = {"plus": round(marge / po, 2), "moins": round(marge / (1 - po), 2)}
    return c


def test_aucun_plantage_ni_valeur_aberrante_sur_600_matchs_a_petits_echantillons():
    rnd = random.Random(21092026)
    n_ok = n_choix = 0
    for i in range(600):
        nd, ne = rnd.choice([2, 2, 3, 3, 4, 5, 8, 12]), rnd.choice([2, 2, 3, 3, 4, 5, 8, 12])
        h2h = rnd.choice([[], H2H_A_INVAINCU, [{"buts_a": 0, "buts_b": 2}] * 5])
        bloc, non_sel = bm.analyse_signal(signal(_cotes_aleatoires(rnd), mid=f"f{i}"), stats_n(nd, ne, seed=i, fort=rnd.random() < 0.5), NOW, lambda s, h=h2h: h)
        assert bloc["statut"] in ("OK", "SKIP"), (nd, ne, bloc)
        if bloc["statut"] != "OK":
            continue
        n_ok += 1
        for l in bloc["inventaire"]:
            assert 0.0 <= l["probabilite"] <= 1.0 and math.isfinite(l["ev"]) and math.isfinite(l["edge"]) and l["cote"] > 1.0, l
        # comptabilité : chaque value bet est soit candidat justifié, soit rejeté (motif), soit de catégorie D : aucun n'est perdu
        nb_d = sum(1 for c in non_sel if c["categorie"] == "D")
        assert bloc["nb_value"] == len(bloc["candidats"]) + len(bloc["rejets"]) + nb_d, (bloc["nb_value"], len(bloc["candidats"]), bloc["rejets"], nb_d)
        sel = [c for c in bloc["selection"].values() if c]
        n_choix += len(sel)
        assert len({c["marche"] for c in sel}) == len(sel) <= 3
        assert all(c["justification"]["donnees_suffisantes"] and c["justification"]["resume"] for c in sel)
        assert all(0 < c["cote"] and 0 < c["probabilite"] < 1 for c in sel)
    assert n_ok > 300 and n_choix > 0, (n_ok, n_choix)          # le test exerce vraiment le moteur, pas seulement des refus


def test_a_2_matchs_le_h2h_ne_justifie_plus_aucun_choix():
    # MAJ 24/09/2026 -- règle du 23/09 (CLAUDE.md, 965e6a5) : le H2H est affiché à titre indicatif et ne rend JAMAIS
    # une justification disponible. À 2 matchs par lieu (les statistiques de forme en exigent 3), même un H2H très
    # favorable ne produit donc aucun choix ; l'avertissement reste visible sur le bloc analysé.
    bloc, _ = bm.analyse_signal(signal(), stats_n(2, 2), NOW, lambda s: H2H_A_INVAINCU)
    assert bloc["statut"] == "OK" and "Fenêtre d'analyse trop courte" in bloc["avertissements"]
    assert bloc["selection"]["P1"] is None


def test_l_avertissement_du_moteur_est_visible_sur_le_choix():
    # 4 matchs par lieu : fenêtre toujours jugée courte par le moteur, mais la forme à domicile suffit à justifier 1X.
    bloc, _ = bm.analyse_signal(signal(), stats_n(4, 4), NOW, lambda s: H2H_A_INVAINCU)
    assert bloc["statut"] == "OK" and "Fenêtre d'analyse trop courte" in bloc["avertissements"]
    p1 = bloc["selection"]["P1"]
    types = [pr["type"] for pr in p1["justification"]["preuves"]]
    assert p1["marche"] == "double_chance_1X" and "home_unbeaten_streak" in types
    assert not any(t.startswith("h2h") for t in types)          # jamais de preuve H2H
    assert "Fenêtre d'analyse trop courte" in p1["points_de_vigilance"]


def test_a_2_matchs_sans_h2h_les_value_bets_sont_rejetes_faute_de_preuve_et_comptes():
    # Documente la cohérence avec la règle NO DATA -> NO GO : la bibliothèque exige 3 matchs par lieu pour ses statistiques de
    # forme ; à 2 matchs, sans H2H, il y a analyse mais aucun choix, et chaque value bet est rejeté avec son motif.
    bloc, _ = bm.analyse_signal(signal(), stats_n(2, 2), NOW, lambda s: [])
    assert bloc["statut"] == "OK" and bloc["nb_value"] > 0 and bloc["selection"]["P1"] is None
    assert all(r["motif"] == bm.MOTIF_JUSTIFICATION for r in bloc["rejets"]) and len(bloc["rejets"]) + 0 >= 1
