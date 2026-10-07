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


def fmt(a, nom):
    return next(f for f in a["formats"] if f["nom"] == nom)


def test_distribution_des_paris_justes_somme_a_un():
    a = gt.analyse_ticket(sel([1.5, 1.8, 2.0, 1.4], [0.7, 0.6, 0.55, 0.75]))
    assert abs(sum(a["probabilite_bonnes"]) - 1.0) < 1e-5
    assert len(a["probabilite_bonnes"]) == 5
    assert abs(a["paris_justes_attendus"] - (0.7 + 0.6 + 0.55 + 0.75)) < 1e-9


def test_esperance_systeme_egale_enumeration_exacte():
    odds, probs = [1.6, 1.9, 2.2, 1.5, 1.8], [0.66, 0.58, 0.5, 0.7, 0.6]
    a = gt.analyse_ticket(sel(odds, probs))
    n_, k = 5, 3
    ev = -1.0
    for outcome in itertools.product([0, 1], repeat=n_):
        pr = 1.0
        for ok, p in zip(outcome, probs):
            pr *= p if ok else 1 - p
        gain = 0.0
        for combo in itertools.combinations(range(n_), k):
            if all(outcome[i] for i in combo):
                gain += pr * 1.0 * odds[combo[0]] * odds[combo[1]] * odds[combo[2]]
        ev += gain / len(list(itertools.combinations(range(n_), k)))
    assert abs(fmt(a, "SYSTEME_3_SUR_5")["esperance_gain"] - round(ev, 4)) < 1e-4


@pytest.mark.parametrize("n_,k,cote,attendu", [
    (6, 4, 1.5, 5),     # 4 justes sur 6 ne rembourse pas un système 4 sur 6 : il en faut 5
    (12, 9, 1.5, 10),   # 9 justes sur 12 ne suffit pas : il en faut 10
    (6, 1, 1.5, 4),     # en paris simples à 1,50, 4 justes sur 6 remboursent exactement
])
def test_bonnes_requises_pour_ne_pas_perdre(n_, k, cote, attendu):
    a = gt.analyse_ticket(sel([cote] * n_, [0.7] * n_))
    nom = "SIMPLES" if k == 1 else f"SYSTEME_{k}_SUR_{n_}"
    f = fmt(a, nom)
    assert f["bonnes_requises"] == attendu
    assert f["erreurs_tolerees"] == n_ - attendu


def test_combine_ne_tolere_aucune_erreur():
    a = gt.analyse_ticket(sel([1.5, 1.6, 1.7], [0.7, 0.7, 0.7]))
    c = fmt(a, "COMBINE")
    assert c["bonnes_requises"] == 3 and c["erreurs_tolerees"] == 0


@pytest.mark.parametrize("rows", [
    sel([1.5, 1.6, 1.7], [0.40, 0.40, 0.40]),   # aucune valeur : rien de rentable
    sel([1.5, 1.5], [0.50, 0.50]),
    sel([2.0, 2.0, 2.0, 2.0], [0.30, 0.30, 0.30, 0.30]),
])
def test_ticket_sans_valeur_est_non_rentable(rows):
    a = gt.analyse_ticket(rows)
    assert a["rentable"] is False
    assert a["format_le_plus_regulier"] is None


@pytest.mark.parametrize("rows", [
    sel([1.5, 1.6, 1.7], [0.70, 0.70, 0.70]),
    sel([1.8, 2.0], [0.62, 0.60]),
    sel([1.5] * 6, [0.72] * 6),
])
def test_ticket_avec_valeur_est_rentable(rows):
    a = gt.analyse_ticket(rows)
    assert a["rentable"] is True
    assert a["format_le_plus_regulier"] is not None


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


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_python_et_javascript_calculent_la_meme_analyse(tmp_path):
    rows = sel([1.5, 1.8, 2.0, 1.4, 1.65, 2.2], [0.7, 0.6, 0.55, 0.75, 0.62, 0.5])
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
    assert js["meilleur_format"] == py["meilleur_format"]
    assert js["format_le_plus_regulier"] == py["format_le_plus_regulier"]
    assert js["rentable"] == py["rentable"]
    for fp, fj in zip(py["formats"], js["formats"]):
        assert fp["nom"] == fj["nom"] and fp["bonnes_requises"] == fj["bonnes_requises"]
        assert abs(fp["esperance_gain"] - fj["esperance_gain"]) < 1e-3
        assert abs(fp["proba_atteindre"] - fj["proba_atteindre"]) < 1e-3
