import datetime as dt

import calibrage_externe as ce


def rec(i, *, win=True, date="2026-08-01", odds=1.60, market="1X2 - 1", engine="moteur_v2_6_10", team="A", competition="Ligue A"):
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
        "competition": competition,
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
    for i in range(60):
        rows.append(rec(i, win=i < 59, date="2026-04-01", team="A"))
    # Les 25 observations récentes cassent volontairement le pattern,
    # sans effacer immédiatement la force de l'historique complet.
    for i in range(60, 85):
        rows.append(rec(i, win=i < 65, date=f"2026-08-{(i - 59):02d}", team="A"))
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

def test_championnat_peut_devenir_un_signal_specifique():
    rows = []
    for i in range(50):
        rows.append(rec(i, win=i < 46, competition="Ligue A"))
    for i in range(50, 100):
        rows.append(rec(i, win=i < 80, competition="Ligue B"))

    intelligence = ce.discover_rules(rows)
    league_rules = [
        r for r in intelligence["rules"]
        if r["conditions"].get("competition") == "ligue a"
        and r["conditions"].get("market") == "1x2 - 1"
    ]
    assert league_rules
    assert any(r["statut"] == "ACTIVE" for r in league_rules)
    assert all((r.get("lift_vs_parent") or 0) >= ce.MIN_LIFT for r in league_rules)

    candidate = {
        "moteur": "moteur_v2_6_10",
        "marche": "1X2 - 1",
        "domicile": "A",
        "exterieur": "Nouveau",
        "competition": "Ligue A",
        "cote": 1.62,
        "probabilite": 0.71,
        "rang": "P3",
    }
    out = ce.apply_rules(candidate, intelligence)
    assert out["calibrage_rang"] == 2
    assert "competition=ligue a" in out["calibrage_externe"]["regle"]


def test_regle_surveillee_ne_passe_pas_le_filtre():
    intelligence = {
        "rules": [{
            "statut": "SURVEILLER",
            "id": "competition=ligue a + market=1x2 - 1",
            "conditions": {"competition": "ligue a", "market": "1x2 - 1"},
            "marge_vs_implicite": 0.03,
            "lift_vs_parent": 0.02,
            "borne_basse_95": 0.70,
            "observations": 40,
        }]
    }
    candidate = {
        "moteur": "moteur_v2_6_10",
        "marche": "1X2 - 1",
        "competition": "Ligue A",
        "cote": 1.62,
        "probabilite": 0.71,
    }
    out = ce.apply_rules(candidate, intelligence)
    assert out["calibrage_rang"] == 0
    assert out["calibrage_externe"]["statut"] == "AUCUN_PATTERN"
