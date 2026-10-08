import datetime as dt

import calibrage_externe as ce


def rec(i, *, win=True, date="2026-08-01", odds=1.60, market="1X2 - 1", engine="moteur_v2_6_10", team="A"):
    return {
        "match_id": f"m{i}",
        "date_match": date,
        "equipe_dom": team,
        "equipe_ext": f"B{i}",
        "marche": market,
        "categorie": "SELECTED",
        "model_version": engine,
        "resultat_statut": "RESOLVED",
        "resultat_marche": "WIN" if win else "LOSS",
        "cote": odds,
        "probabilite": 0.72,
        "edge": 0.08,
        "edv": 0.12,
        "rang": "P1",
    }


def test_decouvre_configuration_marche_cote_lieu():
    rows = []
    for i in range(50):
        rows.append(rec(i, win=i < 46, date=f"2026-07-{(i % 28) + 1:02d}", team="A"))
    for i in range(50, 100):
        rows.append(rec(i, win=i < 80, odds=1.80, team="C"))
    intelligence = ce.discover_rules(rows)
    assert intelligence["compteurs"]["regles_retenues"] > 0
    assert intelligence["compteurs"]["actives"] > 0

    candidate = {
        "moteur": "moteur_v2_6_10",
        "marche": "1X2 - 1",
        "domicile": "A",
        "exterieur": "Nouveau",
        "cote": 1.62,
        "probabilite": 0.71,
        "rang": "P3",
    }
    before = candidate["probabilite"]
    out = ce.apply_rules(candidate, intelligence)
    assert out["probabilite"] == before
    assert out["calibrage_rang"] == 2
    assert out["calibrage_externe"]["statut"] == "ACTIVE"


def test_configuration_devenue_fragile_est_declassee():
    rows = []
    for i in range(40):
        rows.append(rec(i, win=i < 36, date="2026-04-01", team="A"))
    # Les 25 observations récentes cassent volontairement le pattern.
    for i in range(40, 65):
        rows.append(rec(i, win=False, date=f"2026-08-{(i - 39):02d}", team="A"))
    intelligence = ce.discover_rules(rows)
    declining = [r for r in intelligence["rules"] if r["statut"] == "DECLINANTE"]
    assert declining


def test_aucun_pattern_ne_force_un_candidat():
    intelligence = {"rules": []}
    candidate = {
        "moteur": "moteur_v3",
        "marche": "BTTS Oui",
        "cote": 1.69,
        "probabilite": 0.70,
        "domicile": "A",
        "exterieur": "B",
    }
    out = ce.apply_rules(candidate, intelligence)
    assert out["calibrage_rang"] == 0
    assert out["calibrage_externe"]["statut"] == "AUCUN_PATTERN"
