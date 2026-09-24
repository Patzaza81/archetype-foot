import json
from pathlib import Path

from collecte_football_data import normalize_row, normalize_csv


def test_normalize_row_ne_calcule_rien_et_preserve_absences():
    row = {
        "Div": "F1",
        "Date": "19/09/26",
        "Time": "20:00",
        "HomeTeam": "Marseille",
        "AwayTeam": "Rennes",
        "FTHG": "2",
        "FTAG": "1",
        "HTHG": "1",
        "HTAG": "0",
        "HS": "12",
        "AS": "7",
        "HST": "5",
        "AST": "2",
        "HC": "6",
        "AC": "3",
        "HY": "",
        "AY": "",
        "HxG": "1.31",
        "AxG": "0.72",
    }
    out = normalize_row(row, "https://example/F1.csv", "2526", "F1.csv")
    assert out["date"] == "2026-09-19"
    assert out["home_team"] == "Marseille"
    assert out["full_time_home_goals"] == 2
    assert out["half_time_home_goals"] == 1
    assert out["home_xg"] == 1.31
    assert out["away_xg"] == 0.72
    assert "total_goals" not in out
    assert "probability" not in out
    assert "ev" not in out
    assert "value" not in out
    assert "home_avg_goals" not in out
    assert out["home_yellow_cards"] is None


def test_normalize_csv_ne_remplace_pas_les_champs_absents():
    csv_bytes = (
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,HS,AS,HST,AST,HC,AC\n"
        "F1,19/09/26,A,B,1,0,0,0,,,,,2,1\n"
    ).encode("utf-8")
    rows = normalize_csv(csv_bytes, "https://example/F1.csv", "2526", "F1.csv")
    assert len(rows) == 1
    assert rows[0]["home_team"] == "A"
    assert rows[0]["home_corners"] == 2
    assert rows[0]["home_shots"] is None
    assert "odds" not in rows[0]
