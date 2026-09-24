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


# ---------------------------------------------------------------------------------------------------------------
# A2 (24/09/2026) : collecte de la saison en cours sur les sources RÉELLEMENT publiées (data.zip, new/<CODE>.csv,
# fixtures). Cas qui doivent réussir et cas qui doivent échouer / ne rien faire.
# ---------------------------------------------------------------------------------------------------------------
import io as _io
import zipfile as _zipfile

import collecte_football_data as cfd

DOWNLOADM = "https://www.football-data.co.uk/downloadm.php"
ALLNEW = "https://www.football-data.co.uk/all_new_data.php"
ZIP = "https://www.football-data.co.uk/mmz4281/2627/data.zip"
USA_URL = "https://football-data.co.uk/new/USA.csv"
FIX = "https://www.football-data.co.uk/fixtures.csv"
NFIX = "https://www.football-data.co.uk/new_league_fixtures.csv"


class Rep:
    def __init__(self, content=b"", text="", status=200, headers=None):
        self.content, self.text, self.status_code, self.headers = content, text, status, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Session:
    """Simule le site : pages d'index, fichiers, et réponses 304 quand l'ETag envoyé est le bon."""
    def __init__(self, pages, fichiers, etags=None):
        self.headers, self.pages, self.fichiers, self.etags, self.appels = {}, pages, fichiers, etags or {}, []

    def get(self, url, timeout=30, headers=None):
        self.appels.append((url, dict(headers or {})))
        if url in self.pages:
            return Rep(text=self.pages[url])
        if url not in self.fichiers:
            return Rep(status=404)
        etag = self.etags.get(url)
        if etag and (headers or {}).get("If-None-Match") == etag:
            return Rep(status=304)
        return Rep(content=self.fichiers[url], headers={"ETag": etag} if etag else {})


def _zip(m):
    b = _io.BytesIO()
    with _zipfile.ZipFile(b, "w") as z:
        for n, c in m.items():
            z.writestr(n, c)
    return b.getvalue()


E0 = b"Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,HC,AC,B365H\nE0,20/09/2026,15:00,Arsenal,Leeds,2,0,1,0,7,2,1.3\n"
USA = (b"Country,League,Season,Date,Time,Home,Away,HG,AG,Res\n"
       b"USA,MLS,2025,01/03/2025,20:00,A,B,1,0,H\nUSA,MLS,2026,20/09/2026,20:00,Austin,San Diego,2,1,H\n")
FIXTURES = (b"Div,Date,Time,HomeTeam,AwayTeam,Referee,B365H,B365D,B365A,BFEH,BFED,BFEA\nE1,26/09/2026,15:00,Norwich,Leeds,,2.1,3.4,3.3,2.2,3.5,3.45\n"
            b"E1,19/09/2026,15:00,Derby,Hull,,2.0,3.3,3.6,2.1,3.4,3.7\n")
NFIXTURES = b"Country,League,Date,Time,Home,Away,PSH,PSD,PSA\nUSA,MLS,26/09/2026,01:30,Austin,San Diego,1.9,3.6,3.9\n"


def _site(etags=None, e0=E0):
    pages = {DOWNLOADM: '<a href="mmz4281/2627/data.zip">x</a><a href="mmz4281/2526/data.zip">y</a>',
             ALLNEW: '<a href="https://football-data.co.uk/usa.php">USA</a>',
             "https://football-data.co.uk/usa.php": '<a href="new/USA.csv">csv</a>'}
    return Session(pages, {ZIP: _zip({"E0.csv": e0}), USA_URL: USA, FIX: FIXTURES, NFIX: NFIXTURES}, etags)


def _jsonl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]


# --- doivent réussir -------------------------------------------------------------------------------------------------
def test_a2_collecte_principales_et_supplementaires_sans_aucune_cote(tmp_path):
    site = _site()
    st = cfd.collect(root=tmp_path, current_season="2627", session=site, pause=0)
    assert st["errors"] == {} and st["downloaded"] == 2
    e0 = _jsonl(tmp_path / "normalized/2627/E0.jsonl")[0]
    assert (e0["home_team"], e0["half_time_home_goals"], e0["home_corners"]) == ("Arsenal", 1, 7)
    assert "B365H" not in e0 and "odds" not in e0                          # pas de cotes historiques dans le contrat
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert man["files"]["2627/E0"]["last_match_date"] == "2026-09-20"     # fraîcheur visible
    assert man["files"]["2627/nouvelles_ligues/USA"]["last_match_date"] == "2026-09-20"
    usa = _jsonl(tmp_path / "normalized/2627/USA.jsonl")
    assert [(r["home_team"], r["season"]) for r in usa] == [("Austin", "2627")]   # saison civile 2026 seulement
    assert (usa[0]["country"], usa[0]["competition"], usa[0]["full_time_home_goals"]) == ("USA", "MLS", 2)
    assert not (tmp_path / "cotes_run").exists()                           # décision du 24/09 : aucune cote relevée
    assert site.appels and not any("fixtures" in u for u, _ in site.appels)   # jamais téléchargé


def test_a2_source_inchangee_304_rien_retelecharge(tmp_path):
    etags = {ZIP: '"z1"', USA_URL: '"u1"'}
    cfd.collect(root=tmp_path, current_season="2627", session=_site(etags), pause=0)
    s2 = _site(etags)
    st = cfd.collect(root=tmp_path, current_season="2627", session=s2, pause=0)
    assert st["sources_not_modified"] == 2 and st["downloaded"] == 0 and st["updated"] == 0
    assert (ZIP, {"If-None-Match": '"z1"'}) in s2.appels


def test_a2_seule_la_division_modifiee_est_reecrite(tmp_path):
    cfd.collect(root=tmp_path, current_season="2627", session=_site(), pause=0)
    nouveau = E0 + b"E0,21/09/2026,15:00,Chelsea,Fulham,1,1,0,0,5,5,1.9\n"
    st = cfd.collect(root=tmp_path, current_season="2627", session=_site(e0=nouveau), pause=0)
    assert st["updated"] == 1 and st["unchanged"] == 1                     # E0 réécrit, USA inchangé
    assert len(_jsonl(tmp_path / "normalized/2627/E0.jsonl")) == 2


# --- doivent échouer proprement ou ne rien faire ---------------------------------------------------------------------
def test_a2_pas_d_archive_de_la_saison_erreur_signalee_sans_invention(tmp_path):
    s = _site()
    s.pages[DOWNLOADM] = '<a href="mmz4281/2526/data.zip">ancienne saison seulement</a>'
    st = cfd.collect(root=tmp_path, current_season="2627", session=s, pause=0)
    assert "principales" in st["errors"] and not (tmp_path / "normalized/2627/E0.jsonl").exists()
    assert (tmp_path / "normalized/2627/USA.jsonl").exists()               # l'autre source continue


def test_saison_en_cours():
    from datetime import datetime, timezone
    assert cfd.saison_en_cours(datetime(2026, 9, 24, tzinfo=timezone.utc)) == "2627"
    assert cfd.saison_en_cours(datetime(2027, 3, 1, tzinfo=timezone.utc)) == "2627"
