from matrice_scenarios import pronostic_sur as P
from matrice_scenarios.croisements import outcome


def an(**probas):
    return {"markets": {m: {"probabilite": p} for m, p in probas.items()}}


def test_picks_most_probable_market_inside_the_odds_window():
    a = an(over_1_5=0.80, under_4_5=0.86, home_not_lose=0.75)
    assert P.choisir(a, {"over_1_5": 1.30, "under_4_5": 1.27, "home_not_lose": 1.60})["marche"] == "under_4_5"
    assert P.choisir(a, {"over_1_5": 1.30, "under_4_5": 1.25, "home_not_lose": 1.34})["marche"] == "over_1_5"  # 1,25 est exclu
    assert P.choisir(a, {"over_1_5": 1.12, "under_4_5": 1.10, "home_not_lose": 1.30})["marche"] == "home_not_lose"  # 1,10 et 1,12 exclus
    assert P.choisir(a, {"over_1_5": 1.26})["cote"] == 1.26  # 1,26 inclus
    assert P.choisir(a, {"under_4_5": 3.50})["cote"] == 3.50  # aucun plafond par défaut
    assert P.choisir(a, {"under_4_5": 1.36}, cote_max=1.35) is None  # plafond possible mais jamais imposé


def test_no_pick_when_nothing_is_in_the_window_or_no_odds():
    a = an(over_1_5=0.80, under_4_5=0.86)
    assert P.choisir(a, {"over_1_5": 1.25, "under_4_5": 1.09}) is None
    assert P.choisir(a, {}) is None
    assert P.choisir(a, {"under_5_5": 1.2}) is None  # marché inconnu du modèle


def test_tie_goes_to_higher_odds_and_pick_carries_breakeven():
    a = an(over_1_5=0.80, under_4_5=0.80)
    p = P.choisir(a, {"over_1_5": 1.28, "under_4_5": 1.34})
    assert p["marche"] == "under_4_5" and p["cote_equilibre"] == 1.25


def test_betpawa_odds_mapping_and_outcomes():
    raw = {"double_chance": {"1N": 1.2, "N2": 1.9}, "over_under_1.5": {"plus": 1.15, "moins": 5.0}, "over_under_4.5": {"moins": 1.2}, "btts": {"Oui": "x"}}
    c = P.cotes_du_match(raw)
    assert c == {"home_not_lose": 1.2, "away_not_lose": 1.9, "over_1_5": 1.15, "under_4_5": 1.2}
    assert P.cotes_du_match(None) == {}
    r = {"home_goals": 3, "away_goals": 2}
    assert outcome(r, "under_4_5") == 0 and outcome(r, "under_5_5") == 1 and outcome(r, "over_1_5") == 1
    assert outcome({"home_goals": 2, "away_goals": 2}, "under_4_5") == 1 and outcome({"home_goals": 0, "away_goals": 0}, "over_1_5") == 0


def test_every_match_with_recent_matches_gets_a_pick_and_fallback_uses_all_venues():
    import json
    cal = json.loads(P.A.CALIBRATION_FILE.read_text(encoding="utf-8"))
    def eq(rows):
        return {"matchs": [{"date": f"2026-0{i + 1}-10", "buts_marques": gf, "buts_encaisses": ga, "domicile": dom} for i, (gf, ga, dom) in enumerate(rows)]}
    cotes = {"over_under_1.5": {"plus": 1.30}, "over_under_3.5": {"moins": 1.40}}
    full = eq([(2, 1, True), (1, 0, True), (3, 1, True)])
    r = P.pronostic_complet(full, eq([(0, 1, False), (1, 1, False), (2, 2, False)]), cotes, "2026-09-01", cal)
    assert r and r["series"] == "même lieu" and r["cote"] >= 1.26
    mixed = eq([(2, 1, True), (1, 0, False), (3, 1, False)])  # un seul match à domicile : repli sur tous lieux
    r2 = P.pronostic_complet(mixed, eq([(0, 1, True), (1, 1, True), (2, 2, False)]), cotes, "2026-09-01", cal)
    assert r2 and r2["series"] == "tous lieux"
    assert P.pronostic_complet(eq([(1, 0, True)] * 2), full, cotes, "2026-09-01", cal) is None  # moins de 3 matchs
    assert P.pronostic_complet(full, full, {"over_under_1.5": {"plus": 1.10}}, "2026-09-01", cal) is None  # aucune cote d'au moins 1,26
    assert P.pronostic_complet(full, full, cotes, "2026-01-01", cal) is None  # rien avant la date : pas de fuite du futur
