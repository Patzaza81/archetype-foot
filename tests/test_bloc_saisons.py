import pytest
from matrice_scenarios import bloc_saisons as B


@pytest.mark.parametrize("t,r", [("19/10/2026", "2026-10-19"), ("19/10/26", "2026-10-19"), ("01/02/2025", "2025-02-01")])
def test_date_valide(t, r):
    assert B.date_iso(t) == r


@pytest.mark.parametrize("t", ["", "2026-10-19", "32/13/2026", "abc"])
def test_date_invalide(t):
    assert B.date_iso(t) is None


@pytest.mark.parametrize("x,r", [("1.85", 1.85), ("12", 12.0), (" 2.10 ", 2.10), ("", None), ("0.9", None), ("n/a", None)])
def test_cote_valide_ou_rejetee(x, r):
    assert B._f(x) == r


def test_lire_csv_principal_et_cotes(tmp_path):
    f = tmp_path / "E0.csv"
    f.write_text("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,B365H,B365D,B365A,AHh,B365AHH,B365AHA\nE0,19/10/26,A,B,2,1,1.5,4.0,6.0,-0.5,1.9,1.95\nE0,20/10/26,C,D,,,,,,,,\n", encoding="utf-8")
    m = B.lire_csv(str(f), "2627")
    assert len(m) == 1 and m[0]["buts_dom"] == 2 and m[0]["cotes"]["1x2_ouverture"]["b365"] == [1.5, 4.0, 6.0]
    assert m[0]["cotes"]["handicap_asiatique_ouverture"]["ligne_domicile"] == -0.5


def test_match_sans_score_ou_sans_date_ignore(tmp_path):
    f = tmp_path / "X.csv"
    f.write_text("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nX,,A,B,1,0\nX,19/10/26,A,B,,\n", encoding="utf-8")
    assert B.lire_csv(str(f), "2627") == []


def _bloc():
    liste = [{"id": f"m{i}", "date": d, "domicile": a, "exterieur": b, "buts_dom": 1, "buts_ext": 0, "competition": "T", "cotes": {}}
             for i, (d, a, b) in enumerate([("2026-10-01", "A", "B"), ("2026-10-08", "B", "A"), ("2026-10-15", "A", "C"), ("2026-10-15", "C", "B")])]
    return {"liste": liste}


def test_entree_sans_fuite_meme_jour():
    b = _bloc()
    e = B.entree(b, b["liste"][2])               # A - C le 15/10 : l'autre match du 15/10 et le match lui-même sont exclus
    assert [h["date"] for h in e["historique_dom"]] == ["2026-10-01", "2026-10-08"] and e["historique_ext"] == []


def test_entree_orientation_des_buts():
    b = _bloc()
    e = B.entree(b, b["liste"][2])
    assert e["historique_dom"][0]["buts_marques"] == 1 and e["historique_dom"][1]["buts_marques"] == 0      # A gagne 1-0 à domicile, perd 0-1 chez B


def test_bloc_construit_coherent():
    try:
        b = B.charger()
    except ValueError:
        pytest.skip("bloc non construit")
    assert b["matchs"] == len(b["liste"]) > 10000 and b["du"] <= b["au"]
    assert len({m["id"] for m in b["liste"]}) == b["matchs"]


def test_grand_test_exige_assez_de_matchs():
    from matrice_scenarios.banc_cotes_football_data import evaluer_bloc_grand_test
    assert "erreur" in evaluer_bloc_grand_test(min_test=10**6)


def test_grand_test_10000_matchs_sans_chevauchement():
    from matrice_scenarios.banc_cotes_football_data import evaluer_bloc_grand_test
    r = evaluer_bloc_grand_test(min_test=10000)
    assert r["test"] == 10000 and r["apprentissage"] >= 500
    assert r["1x2_logloss"]["matchs"] > 5000
