from pathlib import Path
import json
from archive_football_data import archive_snapshot

class FakeResponse:
    def __init__(self, content=b"", text=""):
        self.content = content
        self.text = text
    def raise_for_status(self):
        return None

class FakeSession:
    def __init__(self, pages, files):
        self.headers = {}
        self.pages = pages
        self.files = files
        self.calls = []
    def get(self, url, timeout):
        self.calls.append(url)
        if url in self.pages:
            return FakeResponse(text=self.pages[url])
        return FakeResponse(content=self.files[url])

def test_snapshot_archive_tous_les_csv_et_verrouille(tmp_path):
    season = "2526"
    index = 'href="/mmz4281/2526/F1.csv"><a href="/mmz4281/2526/E0.csv">x</a>'
    files = {
        "https://www.football-data.co.uk/mmz4281/2526/F1.csv": b"F1,data\n",
        "https://www.football-data.co.uk/mmz4281/2526/E0.csv": b"E0,data\n",
    }
    session = FakeSession(
        {"https://www.football-data.co.uk/downloadm.php": index,
         "https://www.football-data.co.uk/all_new_data.php": index},
        files,
    )
    out = archive_snapshot(season=season, root=tmp_path / "snapshots", session=session)
    assert out["status"] == "COMPLETE"
    assert out["downloaded"] == 2
    assert (tmp_path / "snapshots/2526/raw/F1.csv").read_bytes() == b"F1,data\n"
    assert (tmp_path / "snapshots/2526/raw/E0.csv").exists()
    assert (tmp_path / "snapshots/2526/_SNAPSHOT_COMPLETE.json").exists()

    # Un second passage ne doit déclencher aucun téléchargement.
    session2 = FakeSession({}, files)
    out2 = archive_snapshot(season=season, root=tmp_path / "snapshots", session=session2)
    assert out2["immutable"] is True
    assert out2["downloaded"] == 0
    assert session2.calls == []

def test_snapshot_incomplet_reprend_sans_ecraser(tmp_path):
    season = "2526"
    index = 'href="/mmz4281/2526/F1.csv"><a href="/mmz4281/2526/E0.csv">x</a>'
    files = {
        "https://www.football-data.co.uk/mmz4281/2526/F1.csv": b"F1,data\n",
        "https://www.football-data.co.uk/mmz4281/2526/E0.csv": b"E0,data\n",
    }
    session = FakeSession(
        {"https://www.football-data.co.uk/downloadm.php": index,
         "https://www.football-data.co.uk/all_new_data.php": index},
        {"https://www.football-data.co.uk/mmz4281/2526/F1.csv": b"F1,original\n"},
    )
    # F1 est déjà présent localement: il ne sera jamais remplacé.
    raw = tmp_path / "snapshots/2526/raw"
    raw.mkdir(parents=True)
    (raw / "F1.csv").write_bytes(b"F1,original\n")
    out = archive_snapshot(season=season, root=tmp_path / "snapshots", session=session)
    assert out["status"] == "INCOMPLETE"
    assert (raw / "F1.csv").read_bytes() == b"F1,original\n"


def test_catalogue_contient_code_nom_et_url_directe(tmp_path):
    season = "2526"
    index = '<a href="/mmz4281/2526/F1.csv">Ligue 1</a><a href="/mmz4281/2526/X9.csv">nouveau</a>'
    files = {
        "https://www.football-data.co.uk/mmz4281/2526/F1.csv": b"F1,data\n",
        "https://www.football-data.co.uk/mmz4281/2526/X9.csv": b"X9,data\n",
    }
    session = FakeSession(
        {"https://www.football-data.co.uk/downloadm.php": index,
         "https://www.football-data.co.uk/all_new_data.php": index},
        files,
    )
    out = archive_snapshot(season=season, root=tmp_path / "snapshots", session=session)
    assert out["status"] == "COMPLETE"
    catalogue = json.loads(
        (tmp_path / "snapshots/2526/catalogue.json").read_text(encoding="utf-8")
    )
    entries = {row["competition_code"]: row for row in catalogue["entries"]}
    assert entries["F1"]["country"] == "France"
    assert entries["F1"]["competition"] == "Ligue 1"
    assert entries["F1"]["source_url"].endswith("/2526/F1.csv")
    assert entries["X9"]["source_url"].endswith("/2526/X9.csv")
    assert entries["X9"]["country"] is None
    assert entries["X9"]["competition"] is None


# ---------------------------------------------------------------------------------------------------------------
# CORRECTIF 24/09/2026 : la vraie page downloadm.php ne publie qu'une archive « mmz4281/<saison>/data.zip » par
# saison (aucun lien CSV individuel). Cas qui doivent réussir et cas qui doivent échouer.
# ---------------------------------------------------------------------------------------------------------------
import io
import zipfile

import pytest

from archive_football_data import COMPETITIONS

INDEX_ZIP = '<A HREF="mmz4281/2526/data.zip">2025/2026</A><A HREF="mmz4281/2425/data.zip">2024/2025</A>'
ZIP_URL = "https://www.football-data.co.uk/mmz4281/2526/data.zip"


def _zip(membres):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for nom, contenu in membres.items():
            z.writestr(nom, contenu)
    return tampon.getvalue()


def _session_zip(contenu_zip):
    return FakeSession({"https://www.football-data.co.uk/downloadm.php": INDEX_ZIP,
                        "https://www.football-data.co.uk/all_new_data.php": ""}, {ZIP_URL: contenu_zip})


def test_zip_saison_archive_tous_les_csv(tmp_path):
    session = _session_zip(_zip({"E0.csv": b"E0,data\n", "N1.csv": b"N1,data\n", "P1.csv": b"P1,data\n"}))
    out = archive_snapshot(season="2526", root=tmp_path / "s", session=session)
    assert out["status"] == "COMPLETE" and out["discovered"] == 3 and out["downloaded"] == 3
    assert session.calls.count(ZIP_URL) == 1                       # une seule requête pour toute la saison
    manifest = json.loads((tmp_path / "s/2526/manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_archive"]["source_url"] == ZIP_URL and manifest["source_archive"]["csv_count"] == 3
    assert manifest["files"]["N1"]["source_url"] == ZIP_URL + "#N1.csv"
    assert (tmp_path / "s/2526/raw/P1.csv").read_bytes() == b"P1,data\n"


def test_zip_second_passage_aucun_telechargement(tmp_path):
    archive_snapshot(season="2526", root=tmp_path / "s", session=_session_zip(_zip({"E0.csv": b"x\n"})))
    session2 = FakeSession({}, {})
    out = archive_snapshot(season="2526", root=tmp_path / "s", session=session2)
    assert out["immutable"] is True and session2.calls == []


def test_zip_code_inconnu_non_attribue_et_portugal_correct(tmp_path):
    session = _session_zip(_zip({"X9.csv": b"x\n", "P1.csv": b"p\n"}))
    archive_snapshot(season="2526", root=tmp_path / "s", session=session)
    cat = {r["competition_code"]: r for r in json.loads((tmp_path / "s/2526/catalogue.json").read_text(encoding="utf-8"))["entries"]}
    assert cat["X9"]["country"] is None and cat["X9"]["competition"] is None
    assert COMPETITIONS["P1"] == ("Portugal", "Primeira Liga")


def test_zip_d_une_autre_saison_jamais_pris(tmp_path):
    session = FakeSession({"https://www.football-data.co.uk/downloadm.php": '<a href="mmz4281/2425/data.zip">x</a>',
                           "https://www.football-data.co.uk/all_new_data.php": ""}, {})
    with pytest.raises(RuntimeError, match="Aucun CSV"):
        archive_snapshot(season="2526", root=tmp_path / "s", session=session)


def test_zip_sans_csv_refuse(tmp_path):
    with pytest.raises(RuntimeError, match="Aucun CSV"):
        archive_snapshot(season="2526", root=tmp_path / "s", session=_session_zip(_zip({"lisezmoi.txt": b"x"})))


def test_zip_conflit_avec_un_fichier_local_refuse(tmp_path):
    racine = tmp_path / "s"
    archive_snapshot(season="2526", root=racine, session=_session_zip(_zip({"E0.csv": b"original\n", "F1.csv": b"f\n"})))
    # on retire le verrou et on altère un fichier : la reprise doit refuser, jamais écraser en silence
    (racine / "2526/_SNAPSHOT_COMPLETE.json").unlink()
    m = json.loads((racine / "2526/manifest.json").read_text(encoding="utf-8")); m["status"] = "INCOMPLETE"
    (racine / "2526/manifest.json").write_text(json.dumps(m), encoding="utf-8")
    (racine / "2526/raw/E0.csv").write_bytes(b"modifie\n")
    with pytest.raises(RuntimeError, match="Conflit"):
        archive_snapshot(season="2526", root=racine, session=_session_zip(_zip({"E0.csv": b"original\n", "F1.csv": b"f\n"})))


# ---------------------------------------------------------------------------------------------------------------
# AJOUT 24/09/2026 : championnats supplémentaires (new/<CODE>.csv, toutes saisons dans un seul fichier)
# ---------------------------------------------------------------------------------------------------------------
from archive_football_data import archive_new_leagues, filtre_saison

NEW_INDEX = ('<A HREF="https://football-data.co.uk/usa.php">USA</A><A HREF="https://football-data.co.uk/austria.php">AUT</A>'
             '<A HREF="https://football-data.co.uk/blog/x.php">blog</A><A HREF="new/Latest_Results.csv">x</A>')
USA = ("Country,League,Season,Date,Time,Home,Away,HG,AG,Res\n"
       "USA,MLS,2024,01/03/2024,20:00,A,B,1,0,H\nUSA,MLS,2025,01/03/2025,20:00,C,D,2,2,D\n"
       "USA,MLS,2025,02/03/2025,20:00,E,F,0,1,A\nUSA,MLS,2026,01/03/2026,20:00,G,H,3,0,H\n").encode()
AUT = ("\ufeffCountry,League,Season,Date,Time,Home,Away,HG,AG,Res\n"
       "Austria,Bundesliga,2024/2025,01/08/2024,18:00,A,B,1,1,D\nAustria,Bundesliga,2025/2026,01/08/2025,18:00,C,D,2,0,H\n"
       "Austria,Bundesliga,2026/2027,01/08/2026,18:00,E,F,0,0,D\n").encode()


def _session_new(fichiers):
    pages = {"https://www.football-data.co.uk/all_new_data.php": NEW_INDEX,
             "https://football-data.co.uk/usa.php": '<a href="new/USA.csv">csv</a>',
             "https://football-data.co.uk/austria.php": '<a href="new/AUT.csv">csv</a>'}
    return FakeSession(pages, fichiers)


def _lignes(p):
    return p.read_text(encoding="utf-8").strip().splitlines()[1:]


def test_new_saison_civile_et_a_cheval(tmp_path):
    s = _session_new({"https://football-data.co.uk/new/USA.csv": USA, "https://football-data.co.uk/new/AUT.csv": AUT})
    out = archive_new_leagues(season="2526", root=tmp_path / "s", session=s, pause=0)
    assert out["status"] == "COMPLETE" and out["discovered"] == 2 and out["downloaded"] == 2
    d = tmp_path / "s/2526/nouvelles_ligues"
    assert [l.split(",")[2] for l in _lignes(d / "raw/USA.csv")] == ["2025", "2025"]        # année civile 2025
    assert [l.split(",")[2] for l in _lignes(d / "raw/AUT.csv")] == ["2025/2026"]           # à cheval 2025/2026
    cat = {e["competition_code"]: e for e in json.loads((d / "catalogue.json").read_text(encoding="utf-8"))["entries"]}
    assert (cat["USA"]["country"], cat["USA"]["competition"]) == ("USA", "MLS")
    assert (d / "_SNAPSHOT_COMPLETE.json").exists()
    assert not (tmp_path / "s/2526/_SNAPSHOT_COMPLETE.json").exists()       # le snapshot principal n'est pas touché


def test_new_second_passage_aucune_requete(tmp_path):
    archive_new_leagues(season="2526", root=tmp_path / "s", pause=0, session=_session_new(
        {"https://football-data.co.uk/new/USA.csv": USA, "https://football-data.co.uk/new/AUT.csv": AUT}))
    s2 = FakeSession({}, {})
    assert archive_new_leagues(season="2526", root=tmp_path / "s", session=s2, pause=0)["immutable"] is True
    assert s2.calls == []


def test_new_latest_results_et_blog_jamais_pris(tmp_path):
    s = _session_new({"https://football-data.co.uk/new/USA.csv": USA, "https://football-data.co.uk/new/AUT.csv": AUT})
    archive_new_leagues(season="2526", root=tmp_path / "s", session=s, pause=0)
    assert not any("Latest_Results" in c or "/blog/" in c for c in s.calls)


def test_new_sans_colonne_saison_incomplet(tmp_path):
    s = _session_new({"https://football-data.co.uk/new/USA.csv": b"Country,Date,Home\nUSA,01/01/2025,A\n",
                      "https://football-data.co.uk/new/AUT.csv": AUT})
    out = archive_new_leagues(season="2526", root=tmp_path / "s", session=s, pause=0)
    assert out["status"] == "INCOMPLETE" and out["failed"] == 1
    assert not (tmp_path / "s/2526/nouvelles_ligues/_SNAPSHOT_COMPLETE.json").exists()


def test_new_aucune_ligne_pour_la_saison_note_vide_pas_invente(tmp_path):
    vieux = b"Country,League,Season,Date,Time,Home,Away,HG,AG,Res\nUSA,MLS,2019,01/03/2019,20:00,A,B,1,0,H\n"
    s = _session_new({"https://football-data.co.uk/new/USA.csv": vieux, "https://football-data.co.uk/new/AUT.csv": AUT})
    out = archive_new_leagues(season="2526", root=tmp_path / "s", session=s, pause=0)
    assert out["empty"] == 1 and not (tmp_path / "s/2526/nouvelles_ligues/raw/USA.csv").exists()


def test_filtre_saison_invalide_refuse():
    with pytest.raises(ValueError):
        filtre_saison(USA, "25-26")
