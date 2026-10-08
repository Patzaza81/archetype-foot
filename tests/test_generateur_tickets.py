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
    chosen = gt.tirage_cible(rows, 10.0, "2026-10-08", "T")
    assert chosen, "un ticket doit sortir sans historique"
    product = math.prod(float(x["cote"]) for x in chosen)
    assert 10 / 1.25 <= product <= 10 * 1.25


def test_cote_totale_toujours_entre_2_et_20():
    rows = gt.dedupe(pool_sans_historique())
    for target in (2, 2.5, 3, 5, 7.3, 10, 15, 19.9, 20):
        chosen = gt.tirage_cible(rows, target, "2026-10-08", "T")
        if chosen:
            product = math.prod(float(x["cote"]) for x in chosen)
            assert 2.0 - 1e-9 <= product <= 20.0 + 1e-9, (target, product)


def test_cible_hors_intervalle_est_ramenee_dans_2_20():
    assert gt.clamp_target(1) == 2.0
    assert gt.clamp_target(50) == 20.0
    assert gt.clamp_target("abc") == 10.0
    rows = gt.dedupe(pool_sans_historique())
    for target in (0.5, 35):
        chosen = gt.tirage_cible(rows, target, "2026-10-08", "T")
        if chosen:
            product = math.prod(float(x["cote"]) for x in chosen)
            assert 2.0 - 1e-9 <= product <= 20.0 + 1e-9


def test_un_seul_pari_par_match_et_12_max():
    rows = gt.dedupe(pool_sans_historique())
    chosen = gt.tirage_cible(rows, 20.0, "2026-10-08", "T")
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
    assert gt.tirage_cible([cand(1, 2.0, 0.6)], 10.0, "g", "T") == []
    assert gt.tirage_ticket([cand(1, 2.0, 0.6)], 2, "g", "T") == []


def test_generateur_traite_les_sources_de_facon_identique():
    base = cand(900, 1.60, 0.70, rang="P1")
    base.update({
        "selection_evidence_rank": 3,
        "selection_evidence_lower_bound": 0.62,
        "selection_evidence_rate": 0.80,
        "selection_evidence_roi": 0.12,
        "selection_evidence_observations": 10,
        "selection_sample_rank": 0,
        "selection_rank": 3,
    })
    rows = []
    for source in ("moteur_v2_6_10", "moteur_v3", "journal"):
        x = dict(base, source=source, moteur=source if source != "journal" else None)
        rows.append(x)
    assert gt.candidate_rank(rows[0]) == gt.candidate_rank(rows[1]) == gt.candidate_rank(rows[2])


def test_build_retient_10_par_source_soit_30_et_les_tickets_utilisent_les_30():
    top = []
    for i in range(60):
        x = cand(i, 1.30 + (i % 10) * 0.12, 0.62 + (i % 8) * 0.03,
                 source=("moteur_v2_6_10", "moteur_v3", "journal")[i // 20], rang="P1")
        top.append(x)
    data = {"sources": {"moteur_v2_6_10": {"candidats": top[:20]}, "moteur_v3": {"candidats": top[20:40]},
                        "journal": {"candidats": top[40:60]}}}
    out = gt.build(data, graine="2026-10-08")
    assert out["candidats_total"] == 30 and out["candidats_retenus"] == 30
    assert out["sources"] == {"moteur_v2_6_10": 10, "moteur_v3": 10, "journal": 10}
    assert len(out["pool"]) == 30 and out["graine_tirage"] == "2026-10-08"
    assert all(s["metrics"]["matchs"] <= 12 for s in out["scenarios"])


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


def test_journal_5_sur_5_entre_dans_le_pool_avec_la_probabilite_lissee_mais_pas_avec_wilson():
    def journal(p, source_proba):
        return cand(77, 1.60, None, source="journal", rang=None, marge_succes=p - 0.625, niveau="FORME_5_SUR_5",
                    journal_frequency=1.0, journal_wins=5, journal_observations=5, journal_lower_bound=0.5655,
                    journal_roi=0.30, probabilite_estimee=p, probabilite_source=source_proba,
                    journal_team="Equipe Forte", journal_opportunity=True)
    v2 = cand(78, 1.60, 0.90, source="moteur_v2_6_10", rang="P1")
    def donnees(j):
        return {"sources": {"moteur_v2_6_10": {"candidats": [v2]}, "moteur_v3": {"candidats": []},
                            "journal": {"candidats": [j]}}}
    lisse = gt.build(donnees(journal(0.72, "JOURNAL_LISSE")))
    assert any(x["source"] == "journal" for x in lisse["pool"])          # 72 % contre 62,5 % implicite : jouable
    wilson = gt.build(donnees(journal(0.5655, "JOURNAL_WILSON")))
    assert not any(x["source"] == "journal" for x in wilson["pool"])     # 56,6 % contre 62,5 % : non jouable (état initial)

# --- AJOUT 08/10/2026 : tri par le générateur (10 par source), doublons remplacés, tirage au hasard ----------------------

def _jour(mid, source, odds=1.60, p=0.70, marche="over_under_total_2.5_over", **kw):
    return cand(mid, odds, p, source=source, rang="P1", marche=marche, **kw)


@pytest.mark.parametrize("marche,attendu", [
    ("Match à moins de 3,5 buts", "over_under_total_3.5_under"),
    ("Match à plus de 2,5 buts", "over_under_total_2.5_over"),
    ("Les deux équipes marquent", "btts_oui"),
    ("over_under_total_2.5_over", "over_under_total_2.5_over"),      # nom moteur : inchangé
])
def test_marche_canonique_traduit_le_journal_et_laisse_les_moteurs(marche, attendu):
    assert gt.marche_canonique({"marche": marche}) == attendu


def test_marche_canonique_equipe_domicile_ou_exterieur():
    base = {"domicile": "Alpha", "exterieur": "Beta"}
    assert gt.marche_canonique({**base, "marche": "Victoire", "journal_team": "Alpha"}) == "1x2_domicile"
    assert gt.marche_canonique({**base, "marche": "Ne perd pas (victoire ou nul)", "journal_team": "Beta"}) == "double_chance_X2"


@pytest.mark.parametrize("marche,extra", [
    ("Garde sa cage inviolée", {}),                       # équivalence incertaine : jamais traduit
    ("Marque 2 buts ou plus", {}),
    ("Victoire", {"journal_team": "Inconnue"}),            # équipe ni domicile ni extérieur
])
def test_marche_canonique_ne_traduit_pas_ce_qui_est_incertain(marche, extra):
    c = {"marche": marche, "domicile": "Alpha", "exterieur": "Beta", **extra}
    assert gt.marche_canonique(c) == marche.lower()


def test_pari_key_meme_pari_et_paris_differents():
    v3 = _jour(1, "moteur_v3", marche="over_under_total_2.5_over")
    j = _jour(1, "journal", marche="Match à plus de 2,5 buts")
    assert gt.pari_key(v3) == gt.pari_key(j)                                              # même pari, deux sources
    assert gt.pari_key(v3) != gt.pari_key(_jour(1, "journal", marche="Match à plus de 3,5 buts"))   # autre ligne
    assert gt.pari_key(v3) != gt.pari_key(_jour(2, "journal", marche="Match à plus de 2,5 buts"))   # autre match
    assert gt.pari_key(v3) != gt.pari_key(_jour(1, "journal", marche="Match à moins de 2,5 buts"))  # sens opposé


def test_v2_ne_garde_que_p1():
    v2 = [cand(i, 1.6, 0.70, rang=("P1", "P2", "P3")[i % 3]) for i in range(9)]
    retenus, _ = gt.selection_par_source({"sources": {"moteur_v2_6_10": {"candidats": v2}}})
    assert len(retenus["moteur_v2_6_10"]) == 3 and all(x["rang"] == "P1" for x in retenus["moteur_v2_6_10"])


def test_dix_par_source_au_maximum_et_rien_de_force():
    v3 = [_jour(i, "moteur_v3") for i in range(15)]
    journal = [_jour(100 + i, "journal") for i in range(3)]
    retenus, jouables = gt.selection_par_source({"sources": {"moteur_v3": {"candidats": v3}, "journal": {"candidats": journal}}})
    assert len(retenus["moteur_v3"]) == 10 and len(retenus["journal"]) == 3 and retenus["moteur_v2_6_10"] == []
    assert jouables == 18


def test_les_non_jouables_sont_exclus_avant_la_coupe():
    jouables = [_jour(i, "journal", odds=1.60, p=0.70) for i in range(4)]
    trop_chers = [_jour(10 + i, "journal", odds=3.50, p=0.90) for i in range(12)]       # cote hors 1,26–3,01
    sans_valeur = [_jour(30 + i, "journal", odds=1.60, p=0.40) for i in range(12)]       # chance < cote
    retenus, _ = gt.selection_par_source({"sources": {"journal": {"candidats": trop_chers + sans_valeur + jouables}}})
    assert len(retenus["journal"]) == 4


def test_doublon_reste_dans_la_meilleure_source_et_l_autre_prend_son_suivant():
    commun_v3 = _jour(1, "moteur_v3", p=0.80, marche="over_under_total_2.5_over")
    commun_j = _jour(1, "journal", p=0.72, marche="Match à plus de 2,5 buts")
    suivant_j = _jour(2, "journal", p=0.66, marche="Match à moins de 3,5 buts")
    for x in (commun_v3, commun_j, suivant_j):
        x["selection_evidence_rank"] = 0
    retenus, _ = gt.selection_par_source({"sources": {"moteur_v3": {"candidats": [commun_v3]},
                                                      "journal": {"candidats": [commun_j, suivant_j]}}})
    assert [x["marche"] for x in retenus["moteur_v3"]] == ["over_under_total_2.5_over"]
    assert [x["marche"] for x in retenus["journal"]] == ["Match à moins de 3,5 buts"]     # le doublon est remplacé
    assert retenus["moteur_v3"][0]["aussi_propose_par"] == ["journal"]


def test_doublon_sans_remplacant_laisse_la_place_vide():
    v3 = _jour(1, "moteur_v3", p=0.80)
    j = _jour(1, "journal", p=0.62, marche="Match à plus de 2,5 buts")
    retenus, _ = gt.selection_par_source({"sources": {"moteur_v3": {"candidats": [v3]}, "journal": {"candidats": [j]}}})
    assert len(retenus["moteur_v3"]) == 1 and retenus["journal"] == []


def _data_30():
    sources = {}
    for k, s in enumerate(gt.SOURCES):
        sources[s] = {"candidats": [_jour(100 * k + i, s, odds=1.40 + 0.08 * (i % 8), p=0.78 + 0.01 * (i % 5))
                                    for i in range(14)]}
    return {"sources": sources, "journal_calibrage": "lisse"}


def test_tirage_reproductible_avec_la_meme_graine_et_different_avec_une_autre():
    pool = [_jour(i, "moteur_v3", odds=1.4 + 0.05 * (i % 9)) for i in range(30)]
    a = gt.tirage_ticket(pool, 4, "2026-10-08", "T")
    assert [x["match_id"] for x in a] == [x["match_id"] for x in gt.tirage_ticket(pool, 4, "2026-10-08", "T")]
    autres = {tuple(x["match_id"] for x in gt.tirage_ticket(pool, 4, f"2026-10-{d:02d}", "T")) for d in range(1, 15)}
    assert len(autres) > 1


def test_tirage_exclut_les_matchs_interdits_et_garde_la_cote_dans_2_20():
    pool = [_jour(i, "moteur_v3", odds=1.5) for i in range(8)]
    interdits = {gt.match_key(pool[i]) for i in range(4)}
    chosen = gt.tirage_ticket(pool, 4, "g", "T", interdits)
    assert {x["match_id"] for x in chosen} == {"4", "5", "6", "7"}
    assert gt.tirage_ticket(pool, 5, "g", "T", interdits) == []              # pas assez de matchs : rien de forcé
    assert gt.tirage_ticket([_jour(i, "moteur_v3", odds=1.05) for i in range(3)], 2, "g", "T") == []   # produit < 2


def test_build_n_utilise_jamais_un_match_deux_fois_dans_les_tickets_du_jour():
    out = gt.build(_data_30(), graine="2026-10-08")
    vus = [x["cle_match"] for s in out["scenarios"] for x in s["selection"]]
    assert vus and len(vus) == len(set(vus))
    assert out["graine_tirage"] == "2026-10-08" and out["journal_calibrage"] == "lisse"


def test_build_est_reproductible_et_la_graine_change_les_tickets():
    d = _data_30()
    def compo(g):
        return [[x["cle_match"] for x in s["selection"]] for s in gt.build(d, graine=g)["scenarios"]]
    assert compo("2026-10-08") == compo("2026-10-08")
    assert any(compo("2026-10-08") != compo(f"2026-10-{k:02d}") for k in range(9, 20))


def test_aucune_regle_de_diversification_de_marches():
    # tous les paris sont du même marché : les tickets sortent quand même
    out = gt.build(_data_30(), graine="x")
    tickets = [s for s in out["scenarios"] if s["selection"]]
    assert tickets
    assert any(len({l["marche"] for l in s["selection"]}) == 1 and len(s["selection"]) >= 2 for s in tickets)


# ---------- plages de dates (4 plages cumulatives, heure du Cameroun) ----------
import datetime as _dt

MAINT = _dt.datetime(2026, 10, 8, 22, 0, tzinfo=gt.FUSEAU_CAMEROUN)


@pytest.mark.parametrize("date,heure", [
    ("2026-10-07", "20:00"),      # hier
    ("2026-10-08", "15:00"),      # aujourd'hui, déjà joué
    ("2026-10-08", "22:00"),      # aujourd'hui, commence maintenant
])
def test_match_deja_commence_est_exclu(date, heure):
    assert gt.deja_commence({"date": date, "heure": heure}, MAINT) is True


@pytest.mark.parametrize("date,heure", [
    ("2026-10-09", "00:30"),      # demain
    ("2026-10-08", "22:01"),      # aujourd'hui, pas encore commencé
    ("2026-10-08", None),         # heure inconnue : gardé
    ("2026-10-08", "abc"),        # heure illisible : gardé
])
def test_match_pas_commence_est_garde(date, heure):
    assert gt.deja_commence({"date": date, "heure": heure}, MAINT) is False


def test_dates_plages_quatre_jours_consecutifs():
    assert gt.dates_plages(MAINT) == ["2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"]


def _data_dates(par_jour=14):
    jours = ["2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"]
    sources = {}
    mid = 0
    for k, s in enumerate(gt.SOURCES):
        liste = []
        for j, jour in enumerate(jours):
            for i in range(par_jour):
                mid += 1
                liste.append(_jour(mid, s, odds=1.40 + 0.08 * (i % 8), p=0.78 + 0.01 * (i % 5),
                                   date=jour, heure="23:30"))
        sources[s] = {"candidats": liste}
    return {"sources": sources, "journal_calibrage": "lisse"}


def test_donnees_plage_garde_les_dates_et_exclut_les_commences():
    d = _data_dates(2)
    d["sources"]["moteur_v3"]["candidats"].append(_jour(999, "moteur_v3", date="2026-10-08", heure="09:00"))
    out = gt.donnees_plage(d, ["2026-10-08", "2026-10-09"], MAINT)
    for s in gt.SOURCES:
        assert {c["date"] for c in out["sources"][s]["candidats"]} <= {"2026-10-08", "2026-10-09"}
    assert all(c["match_id"] != "999" for c in out["sources"]["moteur_v3"]["candidats"])
    assert len(d["sources"]["moteur_v3"]["candidats"]) == 9      # l'original n'est pas modifié


def test_build_plages_donne_quatre_plages_cumulatives_avec_dates():
    r = gt.build_plages(_data_dates(), MAINT)
    assert [p["fin"] for p in r["plages"]] == ["2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"]
    assert all(p["debut"] == "2026-10-08" for p in r["plages"])
    assert [len(p["dates"]) for p in r["plages"]] == [1, 2, 3, 4]
    assert r["plage_par_defaut"] == r["plages"][-1]["id"]
    assert r["jour_present"] == "2026-10-08"


def test_chaque_plage_ne_contient_que_ses_dates_et_max_10_par_source():
    r = gt.build_plages(_data_dates(), MAINT)
    for p in r["plages"]:
        assert {x["date"] for x in p["pool"]} <= set(p["dates"])
        assert all(n <= 10 for n in p["sources"].values())
        assert len(p["pool"]) <= 30


def test_plage_plus_large_a_plus_de_choix_que_le_jour_seul():
    r = gt.build_plages(_data_dates(4), MAINT)
    assert len(r["plages"][0]["pool"]) < len(r["plages"][-1]["pool"]) == 30


def test_aucun_match_reutilise_dans_une_plage():
    r = gt.build_plages(_data_dates(), MAINT)
    for p in r["plages"]:
        cles = [x["cle_match"] for t in p["scenarios"] for x in t["selection"]]
        assert len(cles) == len(set(cles))


def test_le_haut_du_fichier_reprend_la_plage_la_plus_large_pour_le_suivi():
    r = gt.build_plages(_data_dates(), MAINT)
    assert r["scenarios"] == r["plages"][-1]["scenarios"]
    assert r["pool"] == r["plages"][-1]["pool"]


def test_jour_present_vide_ne_plante_pas_et_ne_force_rien():
    d = _data_dates()
    for s in gt.SOURCES:
        d["sources"][s]["candidats"] = [c for c in d["sources"][s]["candidats"] if c["date"] != "2026-10-08"]
    r = gt.build_plages(d, MAINT)
    assert r["plages"][0]["pool"] == []
    assert all(not t["selection"] for t in r["plages"][0]["scenarios"])
    assert len(r["plages"][1]["pool"]) > 0


def test_tirage_des_plages_reproductible_le_meme_jour():
    a = gt.build_plages(_data_dates(), MAINT)
    b = gt.build_plages(_data_dates(), MAINT)
    assert [[x["cle_match"] for x in t["selection"]] for t in a["plages"][2]["scenarios"]] == \
           [[x["cle_match"] for x in t["selection"]] for t in b["plages"][2]["scenarios"]]


# ---------- clé de match identique quelle que soit la source ----------
def _m(**kw):
    base = {"date": "2026-10-10", "domicile": "NE Revolution", "exterieur": "S. Sounders", "heure": "00:30"}
    base.update(kw)
    return base


@pytest.mark.parametrize("autre", [
    {"match_id": "abc123"},                                   # le moteur a un identifiant, le Journal non
    {"domicile": "ne revolution", "exterieur": "S Sounders"},  # casse et ponctuation
    {"heure": "01:30", "match_id": "zzz"},                    # autre heure et autre identifiant
    {"domicile": "NÉ Revolution"},                             # accent
])
def test_meme_match_meme_cle_quelle_que_soit_la_source(autre):
    assert gt.match_key(_m()) == gt.match_key(_m(**autre))


@pytest.mark.parametrize("autre", [
    {"exterieur": "Austin"},                                   # autre adversaire
    {"date": "2026-10-11"},                                    # autre jour
    {"domicile": "S. Sounders", "exterieur": "NE Revolution"}, # domicile et extérieur inversés
])
def test_matchs_differents_cles_differentes(autre):
    assert gt.match_key(_m()) != gt.match_key(_m(**autre))


def test_meme_match_journal_sans_id_et_moteur_avec_id_jamais_dans_le_meme_ticket():
    pool = [_jour(1, "moteur_v3", odds=1.5, domicile="Alpha", exterieur="Beta", date="2026-10-10", match_id="id1"),
            _jour(2, "journal", odds=1.5, domicile="Alpha", exterieur="Beta", date="2026-10-10", match_id=None,
                  marche="Match à moins de 3,5 buts")] + \
           [_jour(10 + i, "moteur_v3", odds=1.5, domicile=f"D{i}", exterieur=f"E{i}", date="2026-10-10") for i in range(6)]
    for g in range(30):
        chosen = gt.tirage_ticket(pool, 4, f"g{g}", "T")
        cles = [gt.match_key(x) for x in chosen]
        assert len(cles) == len(set(cles))
