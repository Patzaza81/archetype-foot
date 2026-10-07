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
