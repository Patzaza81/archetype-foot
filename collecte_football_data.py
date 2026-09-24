#!/usr/bin/env python3
"""
Collecte pure Football-Data.co.uk.

Responsabilités:
- découvrir les CSV réellement publiés par Football-Data.co.uk ;
- télécharger les saisons demandées ;
- conserver les fichiers bruts sans les réécrire ;
- normaliser les lignes match dans un contrat neutre ;
- écrire un manifeste de provenance.

Interdiction volontaire:
- aucun calcul de moyenne, xG dérivé, probabilité, EV, valeur ou signal ;
- aucune cote historique transformée en « ouverture/clôture » ;
- aucune fusion avec Matchendirect/BetPawa ;
- aucune décision de marché.

L'historique des saisons terminées est géré exclusivement par archive_football_data.py
et data/football_data/snapshots/. Ce collecteur ne télécharge plus la saison passée
dans le run quotidien. La saison courante peut être remplacée seulement si son
contenu distant a changé.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

INDEX_URLS = (
    "https://www.football-data.co.uk/downloadm.php",
    "https://www.football-data.co.uk/all_new_data.php",
)
BASE_URL = "https://www.football-data.co.uk/"
DEFAULT_ROOT = Path("data/football_data")

SEASON_RE = re.compile(r"/mmz4281/(?P<season>\d{4})/(?P<div>[A-Za-z0-9]+)\.csv$", re.I)

FIELD_MAP = {
    "Div": "competition_code",
    "Date": "date",
    "Time": "time",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "full_time_home_goals",
    "FTAG": "full_time_away_goals",
    "FTR": "full_time_result",
    "HTHG": "half_time_home_goals",
    "HTAG": "half_time_away_goals",
    "HTR": "half_time_result",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HC": "home_corners",
    "AC": "away_corners",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HY": "home_yellow_cards",
    "AY": "away_yellow_cards",
    "HR": "home_red_cards",
    "AR": "away_red_cards",
    "HxG": "home_xg",
    "AxG": "away_xg",
    "xG": "home_xg",
    "xG.1": "away_xg",
}

# Les colonnes de cotes Football-Data sont volontairement hors du contrat
# historique: la feuille de route interdit de les qualifier ouverture/clôture.
# Elles restent dans le CSV brut et seront gérées par le chantier des cotes
# relevées pendant le run.


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def season_code(year_start: int) -> str:
    return f"{year_start % 100:02d}{(year_start + 1) % 100:02d}"


def discover_urls(session: requests.Session, season_codes: set[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for index_url in INDEX_URLS:
        response = session.get(index_url, timeout=30)
        response.raise_for_status()
        for href in re.findall(r"""href\s*=\s*["']([^"']+\.csv)["']""", response.text, re.I):
            url = urljoin(index_url, href)
            match = SEASON_RE.search(url.replace("\\", "/"))
            if not match or match.group("season") not in season_codes:
                continue
            div = match.group("div").upper()
            found.setdefault(f"{match.group('season')}/{div}", url)
    return found


def download(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    data = response.content
    if not data:
        raise ValueError(f"Réponse vide: {url}")
    return data


def _clean(value: str | None):
    if value is None:
        return None
    value = value.strip()
    return value if value != "" else None


def _number(value: str | None):
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        # Une valeur non numérique reste absente plutôt que d'être devinée.
        return None


def normalize_row(row: dict[str, str | None], source_url: str, season: str, source_file: str) -> dict:
    out = {
        "source": "football-data.co.uk",
        "source_url": source_url,
        "source_file": source_file,
        "season": season,
    }
    for source_field, target_field in FIELD_MAP.items():
        if source_field not in row:
            continue
        value = _clean(row.get(source_field))
        if target_field in {"home_team", "away_team", "competition_code", "full_time_result", "half_time_result", "time"}:
            out[target_field] = value
        elif target_field == "date":
            # Normalisation de représentation uniquement; aucune agrégation.
            parsed = None
            if value:
                for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y %H:%M"):
                    try:
                        parsed = datetime.strptime(value, fmt).date().isoformat()
                        break
                    except ValueError:
                        pass
            out[target_field] = parsed
        else:
            out[target_field] = _number(value)

    # Les absences restent explicites et les champs non fournis ne sont pas
    # remplacés par zéro. Les champs de cotes ne sont pas injectés ici.
    return out


def normalize_csv(data: bytes, source_url: str, season: str, source_file: str) -> list[dict]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError(f"CSV sans en-tête: {source_url}")
    return [
        normalize_row(row, source_url, season, source_file)
        for row in reader
        if _clean(row.get("HomeTeam")) and _clean(row.get("AwayTeam"))
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def collect(
    *,
    root: Path = DEFAULT_ROOT,
    current_season: str | None = None,
    session: requests.Session | None = None,
) -> dict:
    if current_season is None:
        now = datetime.now(timezone.utc)
        year = now.year if now.month >= 7 else now.year - 1
        current_season = season_code(year)

    session = session or requests.Session()
    session.headers.update({"User-Agent": "ArchetypeFoot/football-data-collector"})
    wanted = {current_season}
    urls = discover_urls(session, wanted)

    manifest_path = root / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    files = manifest.setdefault("files", {})
    stats = {
        "discovered": len(urls),
        "downloaded": 0,
        "updated": 0,
        "skipped_immutable": 0,
        "errors": 0,
    }

    for key, url in sorted(urls.items()):
        season, div = key.split("/", 1)
        relative_raw = Path("raw") / season / f"{div}.csv"
        raw_path = root / relative_raw
        normalized_path = root / "normalized" / season / f"{div}.jsonl"
        existing = files.get(key)

        data = download(session, url)
        digest = sha256_bytes(data)
        old_hash = existing.get("sha256") if existing else None
        changed = old_hash != digest

        # La saison courante est mutable : on ne réécrit que si la source
        # distante a réellement changé, ou si le fichier local est incomplet.
        if raw_path.exists() and not changed and normalized_path.exists():
            stats["skipped_immutable"] += 1
            continue

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(data)
        rows = normalize_csv(data, url, season, raw_path.name)
        write_jsonl(normalized_path, rows)

        files[key] = {
            "season": season,
            "competition_code": div,
            "source_url": url,
            "sha256": digest,
            "downloaded_at_utc": now_utc(),
            "rows_normalized": len(rows),
            "immutable": False,
        }

        if old_hash is None:
            stats["downloaded"] += 1
        elif changed:
            stats["updated"] += 1

    manifest.update({
        "schema_version": 1,
        "source": "football-data.co.uk",
        "updated_at_utc": now_utc(),
        "historical_policy": "completed seasons are managed by archive_football_data.py snapshots",
        "current_season_policy": "current season may update when source bytes change",
        "files": files,
    })
    root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return stats
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--current-season", default=None)
    args = parser.parse_args()
    try:
        stats = collect(
            root=Path(args.root),
            current_season=args.current_season,
        )
    except Exception as exc:
        print(f"ERREUR collecte football-data: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
