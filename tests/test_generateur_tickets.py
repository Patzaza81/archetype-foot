import math

import generateur_tickets as gt


def cand(mid, odds, p, source="moteur_v2_6_10", rang="P1", **kw):
    c = {
        "source": source, "moteur": source if source != "journal" else None,
        "match_id": str(mid), "date": "2026-10-08", "heure": "20:00",
        "competition": "L1", "domicile": "A" + str(mid), "exterieur": "B" + str(mid),
        "marche": "1X2 - 1", "cote": odds, "probabilite": p, "rang": rang,
        "market_family": "RESULT", "exposure_group": "G" + str(mid),
        # aucun historique : rang_confiance 0, pas de marge_succes
        "rang_confiance": 0, "historique_observations": 0,
    }
    c.update(kw)
    return c


def pool_sans_historique():
    odds = [1.30, 1.45, 1.60, 1.75, 1.90, 2.05, 2.20, 2.40, 1.50, 1.85, 2.60, 1.35]
    return [cand(i, o, round(1 / o + 0.06, 4), rang=("P1", "P2", "P3")[i % 3]) for i, o in enumerate(odds)]


def test_ticket_possible_sans_aucun_historique():
    rows = gt.dedupe(pool_sans_historique())
    chosen = gt.best_target_ticket(rows, 10.0)
    assert chosen, "un ticket doit sortir sans historique"
    product = math.prod(float(x["cote"]) for x in chosen)
    assert 10 / 1.25 <= product <= 10 * 1.25


def test_cote_totale_toujours_entre_2_et_20():
    rows = gt.dedupe(pool_sans_historique())
    for target in (2, 2.5, 3, 5, 7.3, 10, 15, 19.9, 20):
        chosen = gt.best_target_ticket(rows, target)
        if chosen:
            product = math.prod(float(x["cote"]) for x in chosen)
            assert 2.0 - 1e-9 <= product <= 20.0 + 1e-9, (target, product)


def test_cible_hors_intervalle_est_ramenee_dans_2_20():
    assert gt.clamp_target(1) == 2.0
    assert gt.clamp_target(50) == 20.0
    assert gt.clamp_target("abc") == 10.0
    rows = gt.dedupe(pool_sans_historique())
    for target in (0.5, 35):
        chosen = gt.best_target_ticket(rows, target)
        if chosen:
            product = math.prod(float(x["cote"]) for x in chosen)
            assert 2.0 - 1e-9 <= product <= 20.0 + 1e-9


def test_un_seul_pari_par_match_et_12_max():
    rows = gt.dedupe(pool_sans_historique())
    chosen = gt.best_target_ticket(rows, 20.0)
    assert len(chosen) <= 12
    assert len({gt.match_key(x) for x in chosen}) == len(chosen)


def test_choix_sans_valeur_exclu():
    # probabilité inférieure à la probabilité implicite : le moteur n'y voit pas de valeur
    c = cand(1, 2.0, 0.40)
    assert not gt.eligible(c)
    assert gt.eligible(cand(2, 2.0, 0.55))


def test_journal_utilisable_via_sa_probabilite_estimee():
    j = cand(9, 2.0, None, source="journal", rang=None, marge_succes=0.08, niveau="A_JOUER")
    assert abs(gt.proba(j) - 0.58) < 1e-9
    assert gt.eligible(j)


def test_aucun_ticket_si_pool_insuffisant():
    assert gt.best_target_ticket([cand(1, 2.0, 0.6)], 10.0) == []


def test_build_publie_pool_et_respecte_intervalle():
    top = [dict(c, rang_confiance=0) for c in pool_sans_historique()]
    data = {"sources": {"moteur_v2_6_10": {"top": top[:10]}, "moteur_v3": {"top": top[10:]}, "journal": {"top": []}}}
    out = gt.build(data)
    assert out["intervalle_cote_totale"] == [2.0, 20.0]
    assert out["pool"] and all("cle_match" in x for x in out["pool"])
    for s in out["scenarios"]:
        t = s["metrics"]["cote_totale"]
        if t is not None:
            assert 2.0 - 1e-9 <= t <= 20.0 + 1e-9
    assert any(s["scenario"] == "OBJECTIF_COTE_10" for s in out["scenarios"])


def test_meme_marche_conserve_les_sources_distinctes():
    v2 = cand("same", 2.0, 0.56, source="moteur_v2_6_10")
    v3 = cand("same", 2.0, 0.57, source="moteur_v3")
    journal = cand("same", 2.0, None, source="journal", marge_succes=0.08, niveau="A_JOUER", rang=None)
    rows = gt.dedupe([v2, v3, journal])
    assert {x["source"] for x in rows} == {"moteur_v2_6_10", "moteur_v3", "journal"}


def test_tolerance_est_symetrique_autour_de_la_cible():
    assert gt.tolerance_tier(9.5, 10.0) == 0
    assert gt.tolerance_tier(10.5, 10.0) == 0
    assert gt.tolerance_tier(9.4, 10.0) == 1
    assert gt.tolerance_tier(10.6, 10.0) == 1


# ---------- Marge d'erreur et rentabilité par ticket ----------
import itertools
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def sel(odds, probs):
    return [cand(i, o, p) for i, (o, p) in enumerate(zip(odds, probs))]


def plan(a, nom):
    return next(p for p in a["plans"] if p["nom"] == nom)


def retour(a_plan, odds, outcome):
    """Retour réel par unité misée pour une issue (1 = pari juste) : somme des mises × cote des tickets gagnants."""
    total = 0.0
    for t in a_plan["composition"]:
        if all(outcome[i] for i in t["paris"]):
            total += t["mise"] * t["cote"]
    return total


def test_distribution_des_paris_justes_somme_a_un():
    a = gt.analyse_ticket(sel([1.5, 1.8, 2.0, 1.4], [0.7, 0.6, 0.55, 0.75]))
    assert abs(sum(a["probabilite_bonnes"]) - 1.0) < 1e-5
    assert len(a["probabilite_bonnes"]) == 5
    assert abs(a["paris_justes_attendus"] - (0.7 + 0.6 + 0.55 + 0.75)) < 1e-9


def test_12_paris_donnent_les_plans_attendus_et_4_tickets_de_3_disjoints():
    a = gt.analyse_ticket(sel([1.5 + 0.05 * i for i in range(12)], [0.7] * 12))
    assert [p["tickets"] for p in a["plans"]] == [1, 2, 3, 4, 5, 6, 12]
    p4 = plan(a, "TICKETS_4X3")
    assert p4["tailles"] == [3, 3, 3, 3]
    tous = sorted(i for t in p4["composition"] for i in t["paris"])
    assert tous == list(range(12))                       # chaque pari dans un seul ticket
    assert abs(sum(t["mise"] for t in p4["composition"]) - 1.0) < 1e-3


def test_exemple_utilisateur_3_perdants_sur_12_restent_gagnants_en_4x3():
    odds = [1.7] * 12                                     # ticket de 3 = 4,913 → retour 1,228 par ticket gagnant
    a = gt.analyse_ticket(sel(odds, [0.7] * 12))
    p4 = plan(a, "TICKETS_4X3")
    assert p4["gagnants_requis"] == 1 and p4["erreurs_garanties"] == 3
    for t_perdants in itertools.combinations(range(4), 3):   # 3 perdants dans 3 tickets différents : pire cas
        outcome = [1] * 12
        for j in t_perdants:
            outcome[p4["composition"][j]["paris"][0]] = 0
        assert retour(p4, odds, outcome) >= 1.0


def test_erreurs_garanties_tiennent_pour_toute_issue_et_pas_une_de_plus():
    odds = [1.6, 1.9, 2.2, 1.5, 1.8, 1.7]
    a = gt.analyse_ticket(sel(odds, [0.66, 0.58, 0.5, 0.7, 0.6, 0.62]))
    for p in a["plans"]:
        if p["gagnants_requis"] is None:
            continue
        e = p["erreurs_garanties"]
        for outcome in itertools.product([0, 1], repeat=6):
            if outcome.count(0) <= e:
                assert retour(p, odds, outcome) >= 1.0 - 1e-3
        # une erreur de plus, bien placée (un seul pari faux par ticket), fait passer sous la mise
        if e + 1 <= p["tickets"]:
            outcome = [1] * 6
            for t in p["composition"][: e + 1]:
                outcome[t["paris"][0]] = 0
            assert retour(p, odds, outcome) < 1.0


def test_esperance_et_proba_profit_egalent_enumeration_exacte():
    odds, probs = [1.6, 1.9, 2.2, 1.5, 1.8, 1.7], [0.66, 0.58, 0.5, 0.7, 0.6, 0.62]
    a = gt.analyse_ticket(sel(odds, probs))
    for p in a["plans"]:
        ev, pr_profit = -1.0, 0.0
        for outcome in itertools.product([0, 1], repeat=6):
            pr = 1.0
            for ok, q in zip(outcome, probs):
                pr *= q if ok else 1 - q
            r = retour(p, odds, outcome)
            ev += pr * r
            if r >= 1.0 - 1e-3:
                pr_profit += pr
        assert abs(p["esperance_gain"] - ev) < 2e-3
        assert abs(p["proba_profit"] - pr_profit) < 2e-3


@pytest.mark.parametrize("cote,tickets_attendus,erreurs", [
    (1.7, 1, 3),   # tickets à 4,91 : un seul gagnant suffit
    (1.3, 2, 2),   # tickets à 2,20 : retour 0,55 → 2 gagnants requis
    (1.2, 3, 1),   # tickets à 1,73 : retour 0,43 → 3 gagnants requis
])
def test_gagnants_requis_dependent_des_cotes(cote, tickets_attendus, erreurs):
    p = plan(gt.analyse_ticket(sel([cote] * 12, [0.8] * 12)), "TICKETS_4X3")
    assert p["gagnants_requis"] == tickets_attendus
    assert p["erreurs_garanties"] == erreurs


def test_cotes_tres_basses_exigent_tous_les_tickets_gagnants():
    # Cotes ≤ 1,1 : tous les tickets doivent gagner, aucune erreur n'est garantie (le cas « impossible » n'existe pas : tous gagnants rapporte toujours > 1)
    p = plan(gt.analyse_ticket(sel([1.1] * 4, [0.9] * 4)), "SIMPLES")
    assert p["gagnants_requis"] == 4 and p["erreurs_garanties"] == 0


def test_combine_ne_tolere_aucune_erreur():
    p = plan(gt.analyse_ticket(sel([1.5, 1.6, 1.7], [0.7, 0.7, 0.7])), "COMBINE")
    assert p["gagnants_requis"] == 1 and p["erreurs_garanties"] == 0


@pytest.mark.parametrize("rows", [
    sel([1.5, 1.6, 1.7], [0.40, 0.40, 0.40]),   # aucune valeur : rien de rentable
    sel([1.5, 1.5], [0.50, 0.50]),
    sel([2.0, 2.0, 2.0, 2.0], [0.30, 0.30, 0.30, 0.30]),
])
def test_ticket_sans_valeur_est_non_rentable(rows):
    a = gt.analyse_ticket(rows)
    assert a["rentable"] is False
    assert a["plan_le_plus_regulier"] is None and a["plan_marge_max"] is None


@pytest.mark.parametrize("rows", [
    sel([1.5, 1.6, 1.7], [0.70, 0.70, 0.70]),
    sel([1.8, 2.0], [0.62, 0.60]),
    sel([1.5] * 6, [0.72] * 6),
])
def test_ticket_avec_valeur_est_rentable(rows):
    a = gt.analyse_ticket(rows)
    assert a["rentable"] is True
    assert a["plan_le_plus_regulier"] is not None and a["plan_marge_max"] is not None


@pytest.mark.parametrize("rows", [
    [],
    sel([1.5], [0.7]),                                  # un seul pari : pas de ticket
    [cand(1, 1.5, None), cand(2, 1.6, 0.7)],            # probabilité inconnue : on n'invente rien
    sel([1.0, 1.6], [0.7, 0.7]),                        # cote invalide
])
def test_analyse_impossible_renvoie_none(rows):
    assert gt.analyse_ticket(rows) is None


def test_build_ajoute_l_analyse_a_chaque_ticket_et_garde_le_journal_comme_source():
    top = pool_sans_historique()
    journal = cand(50, 1.7, None, source="journal", rang=None, marge_succes=0.1, niveau="A_JOUER")
    data = {"sources": {"moteur_v2_6_10": {"top": top[:6]}, "moteur_v3": {"top": top[6:]}, "journal": {"top": [journal]}}}
    out = gt.build(data)
    assert out["sources"]["journal"] == 1
    assert any(x["source"] == "journal" for x in out["pool"])
    tickets = [s for s in out["scenarios"] if s["selection"]]
    assert tickets
    for s in tickets:
        assert s["analyse"] and s["analyse"]["paris"] == len(s["selection"])
        assert s["analyse"]["plans"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
@pytest.mark.parametrize("odds,probs", [
    ([1.5, 1.8, 2.0, 1.4, 1.65, 2.2], [0.7, 0.6, 0.55, 0.75, 0.62, 0.5]),
    ([1.7, 1.6, 1.9, 1.3, 1.5, 2.1, 1.45, 1.8, 1.6, 1.75, 1.55, 1.4], [0.65] * 12),
])
def test_python_et_javascript_calculent_la_meme_analyse(tmp_path, odds, probs):
    rows = sel(odds, probs)
    py = gt.analyse_ticket(rows)
    legs = [gt.leg(x) for x in rows]
    racine = Path(__file__).resolve().parent.parent
    script = tmp_path / "run.js"
    script.write_text(
        "const a=require(process.argv[2]).analyse(JSON.parse(process.argv[3]));console.log(JSON.stringify(a));",
        encoding="utf-8",
    )
    res = subprocess.run(["node", str(script), str(racine / "tickets_analyse.js"), json.dumps(legs)],
                         capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    for k in ("meilleur_plan", "plan_le_plus_regulier", "plan_marge_max", "rentable"):
        assert js[k] == py[k]
    assert len(py["plans"]) == len(js["plans"])
    for fp, fj in zip(py["plans"], js["plans"]):
        assert fp["nom"] == fj["nom"] and fp["gagnants_requis"] == fj["gagnants_requis"]
        assert [t["paris"] for t in fp["composition"]] == [t["paris"] for t in fj["composition"]]
        assert abs(fp["esperance_gain"] - fj["esperance_gain"]) < 1e-3
        assert abs(fp["proba_profit"] - fj["proba_profit"]) < 1e-3


# ---------- Plusieurs répartitions par plan ----------
def sel_comp(odds, probs, comps):
    return [cand(i, o, p, competition=c) for i, (o, p, c) in enumerate(zip(odds, probs, comps))]


@pytest.mark.parametrize("strat", gt.STRATEGIES)
@pytest.mark.parametrize("t", [2, 3, 4])
def test_chaque_strategie_donne_une_partition_valide(strat, t):
    odds = [1.3 + 0.07 * i for i in range(12)]
    probs = [0.85 - 0.02 * i for i in range(12)]
    comps = ["A", "B", "C"] * 4
    groups = gt.plan_partition(odds, t, probs, comps, strat)
    assert sorted(i for g in groups for i in g) == list(range(12))
    assert [len(g) for g in groups] == gt.plan_sizes(12, t)


def test_ligues_separees_met_les_matchs_d_une_meme_ligue_dans_des_tickets_differents():
    g = gt.plan_partition([1.5, 1.6, 1.7, 1.8], 2, [0.7] * 4, ["A", "A", "B", "B"], "LIGUES_SEPAREES")
    for t in g:
        assert len({["A", "A", "B", "B"][i] for i in t}) == 2


def test_securite_groupee_rassemble_les_paris_les_plus_sürs():
    g = gt.plan_partition([1.5] * 4, 2, [0.9, 0.5, 0.9, 0.5], ["x"] * 4, "SECURITE_GROUPEE")
    assert g == [[0, 2], [1, 3]]


def test_securite_equilibree_rapproche_les_probabilites_des_tickets():
    probs = [0.9, 0.9, 0.5, 0.5]
    odds = [1.5] * 4
    eq = gt.plan_partition(odds, 2, probs, None, "SECURITE_EQUILIBREE")
    gr = gt.plan_partition(odds, 2, probs, None, "SECURITE_GROUPEE")
    ecart = lambda gs: abs(math.prod(probs[i] for i in gs[0]) - math.prod(probs[i] for i in gs[1]))
    assert ecart(eq) < ecart(gr)


def test_strategies_differentes_donnent_des_repartitions_differentes():
    odds = [1.2, 1.2, 3.0, 3.0]
    probs = [0.9, 0.9, 0.4, 0.4]
    cotes = gt.plan_partition(odds, 2, probs, ["A"] * 4, "COTES_EQUILIBREES")
    groupee = gt.plan_partition(odds, 2, probs, ["A"] * 4, "SECURITE_GROUPEE")
    assert cotes != groupee


def test_strategie_inconnue_refusee():
    with pytest.raises(ValueError):
        gt.plan_partition([1.5, 1.6], 2, [0.7, 0.7], None, "N_IMPORTE_QUOI")


def test_le_plan_retient_la_meilleure_variante_et_n_en_perd_aucune():
    odds = [1.25, 1.3, 1.9, 2.0, 1.4, 1.8, 1.55, 1.65, 1.35, 2.1, 1.45, 1.75]
    probs = [0.85, 0.8, 0.55, 0.52, 0.78, 0.6, 0.7, 0.66, 0.8, 0.5, 0.75, 0.6]
    a = gt.analyse_ticket(sel_comp(odds, probs, ["A", "A", "B", "B", "C", "C"] * 2))
    for p in a["plans"]:
        v = p["variantes"]
        assert sum(1 for x in v if x["choisie"]) == 1
        assert v[0]["strategie"] == "COTES_EQUILIBREES"
        ch = next(x for x in v if x["choisie"])
        cle = lambda x: (x["erreurs_garanties"] if x["erreurs_garanties"] is not None else -1, x["proba_profit"], x["esperance_gain"])
        assert all(cle(ch) >= cle(x) for x in v)
        assert p["strategie"] == ch["strategie"]
    assert any(len(p["variantes"]) > 1 for p in a["plans"])


def test_la_logique_existante_reste_identique_quand_toutes_les_variantes_sont_egales():
    a = gt.analyse_ticket(sel([1.7] * 12, [0.7] * 12))
    p4 = plan(a, "TICKETS_4X3")
    assert p4["strategie"] == "COTES_EQUILIBREES" and len(p4["variantes"]) <= 4
    assert p4["gagnants_requis"] == 1 and p4["erreurs_garanties"] == 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_python_et_javascript_choisissent_les_memes_repartitions(tmp_path):
    odds = [1.25, 1.3, 1.9, 2.0, 1.4, 1.8, 1.55, 1.65, 1.35, 2.1, 1.45, 1.75]
    probs = [0.85, 0.8, 0.55, 0.52, 0.78, 0.6, 0.7, 0.66, 0.8, 0.5, 0.75, 0.6]
    rows = sel_comp(odds, probs, ["A", "A", "B", "B", "C", "C"] * 2)
    py = gt.analyse_ticket(rows)
    legs = [gt.leg(x) for x in rows]
    racine = Path(__file__).resolve().parent.parent
    script = tmp_path / "run.js"
    script.write_text("const a=require(process.argv[2]).analyse(JSON.parse(process.argv[3]));console.log(JSON.stringify(a));", encoding="utf-8")
    res = subprocess.run(["node", str(script), str(racine / "tickets_analyse.js"), json.dumps(legs)], capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    for fp, fj in zip(py["plans"], js["plans"]):
        assert fp["strategie"] == fj["strategie"]
        assert [t["paris"] for t in fp["composition"]] == [t["paris"] for t in fj["composition"]]
        assert [v["strategie"] for v in fp["variantes"]] == [v["strategie"] for v in fj["variantes"]]


def test_journal_5_sur_5_est_conserve_dans_le_pool_et_mis_en_avant():
    j = cand(77, 1.60, None, source="journal", rang=None,
             marge_succes=-0.04, niveau="FORME_5_SUR_5",
             journal_frequency=1.0, journal_wins=5, journal_observations=5,
             journal_lower_bound=0.5655, journal_roi=0.30,
             probabilite_estimee=0.5655, probabilite_source="JOURNAL_WILSON",
             journal_team="Equipe Forte", journal_opportunity=True)
    v2 = cand(78, 1.60, 0.90, source="moteur_v2_6_10", rang="P1")
    data = {
        "sources": {
            "moteur_v2_6_10": {"top": [v2]},
            "moteur_v3": {"top": []},
            "journal": {"top": [j]},
        }
    }
    out = gt.build(data)
    assert any(x["source"] == "journal" for x in out["opportunites"])
    assert any(x["source"] == "journal" for x in out["pool"])
