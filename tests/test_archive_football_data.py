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
        {"https://www.football-data.co.uk/downloadm.php": index},
        {"https://www.football-data.co.uk/mmz4281/2526/F1.csv": b"F1,original\n"},
    )
    # F1 est déjà présent localement: il ne sera jamais remplacé.
    raw = tmp_path / "snapshots/2526/raw"
    raw.mkdir(parents=True)
    (raw / "F1.csv").write_bytes(b"F1,original\n")
    out = archive_snapshot(season=season, root=tmp_path / "snapshots", session=session)
    assert out["status"] == "INCOMPLETE"
    assert (raw / "F1.csv").read_bytes() == b"F1,original\n"
