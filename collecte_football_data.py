#!/usr/bin/env python3
"""
Collecte pure Football-Data.co.uk — saison en cours (étape A2 de la feuille de route du 24/09/2026).

Responsabilités (aucune autre) :
- découvrir, sur les pages d'index, les fichiers réellement publiés pour la saison en cours ;
- ne télécharger un fichier que s'il a changé (requête conditionnelle ETag / Last-Modified, puis empreinte SHA-256) ;
- conserver les fichiers bruts et produire une ligne normalisée par match (contrat neutre, champs absents = null) ;
- écrire un manifeste de provenance.

Interdit ici : moyenne, xG dérivé, probabilité, EV, valeur, signal, choix de marché, fusion avec
Matchendirect/BetPawa. Les saisons terminées sont gérées par archive_football_data.py (snapshots immuables).

CORRECTIF 24/09/2026 (vérifié sur les vraies pages, diagnostic/sources/) : la première version cherchait des liens
« mmz4281/<saison>/<DIV>.csv » sur downloadm.php et all_new_data.php ; ces pages n'en publient pas. Le run du 24/09 à
11:36 UTC n'a donc rien collecté (manifeste vide). Sources réellement publiées et utilisées maintenant :
- 22 divisions principales : archive « mmz4281/<saison>/data.zip » (lien lu sur downloadm.php) ;
- 16 championnats supplémentaires : « new/<CODE>.csv » (toutes saisons) sur les pages pays liées depuis
  all_new_data.php ; seules les lignes de la saison en cours sont gardées (règle de archive_football_data.filtre_saison).

DÉCISION DE PATRICK (24/09/2026) : pas de comparaison de cotes entre bookmakers, aucune API. Ce collecteur ne relève
donc AUCUNE cote. Football-Data est la source principale des données d'équipes ; les données manquantes sont complétées
par Matchendirect côté moteur ; un marché dont une donnée nécessaire manque est écarté.
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

import archive_football_data as afd

INDEX_URLS = (
    "https://www.football-data.co.uk/downloadm.php",
    "https://www.football-data.co.uk/all_new_data.php",
)
BASE_URL = "https://www.football-data.co.uk/"
DEFAULT_ROOT = Path("data/football_data")
PAUSE_S = 1.0

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
    # championnats supplémentaires (new/<CODE>.csv) : autres noms de colonnes, même contrat
    "Country": "country",
    "League": "competition",
    "Home": "home_team",
    "Away": "away_team",
    "HG": "full_time_home_goals",
    "AG": "full_time_away_goals",
    "Res": "full_time_result",
}
TEXTE = {"home_team", "away_team", "competition_code", "full_time_result", "half_time_result", "time",
         "country", "competition"}

# Les colonnes de cotes des CSV de résultats restent dans le CSV brut et ne sont jamais utilisées (décision du 24/09).


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def season_code(year_start: int) -> str:
    return f"{year_start % 100:02d}{(year_start + 1) % 100:02d}"


def saison_en_cours(maintenant: datetime | None = None) -> str:
    now = maintenant or datetime.now(timezone.utc)
    return season_code(now.year if now.month >= 7 else now.year - 1)


# ---------------------------------------------------------------------------------------------------------------
# Téléchargement conditionnel
# ---------------------------------------------------------------------------------------------------------------
def telecharge_si_change(session, url: str, precedent: dict | None, timeout: int = 90) -> tuple[bytes | None, dict]:
    """(contenu, entêtes_de_validation). contenu None = inchangé (304). Les entêtes ETag / Last-Modified reçus sont
    gardés pour la requête suivante."""
    entetes = {}
    if precedent:
        if precedent.get("etag"):
            entetes["If-None-Match"] = precedent["etag"]
        if precedent.get("last_modified"):
            entetes["If-Modified-Since"] = precedent["last_modified"]
    r = session.get(url, timeout=timeout, headers=entetes)
    if getattr(r, "status_code", 200) == 304:
        return None, {"etag": precedent.get("etag"), "last_modified": precedent.get("last_modified")}
    r.raise_for_status()
    if not r.content:
        raise ValueError(f"Réponse vide: {url}")
    h = getattr(r, "headers", {}) or {}
    return r.content, {"etag": h.get("ETag"), "last_modified": h.get("Last-Modified")}


# ---------------------------------------------------------------------------------------------------------------
# Normalisation (aucun calcul)
# ---------------------------------------------------------------------------------------------------------------
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
        return None  # une valeur non numérique reste absente plutôt que d'être devinée


def _date(value: str | None):
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def normalize_row(row: dict[str, str | None], source_url: str, season: str, source_file: str) -> dict:
    out = {"source": "football-data.co.uk", "source_url": source_url, "source_file": source_file, "season": season}
    for source_field, target_field in FIELD_MAP.items():
        if source_field not in row:
            continue
        value = _clean(row.get(source_field))
        if target_field in TEXTE:
            out[target_field] = value
        elif target_field == "date":
            out[target_field] = _date(value)
        else:
            out[target_field] = _number(value)
    return out


def _lecteur(data: bytes):
    texte = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(texte))
    if not reader.fieldnames:
        raise ValueError("CSV sans en-tête")
    reader.fieldnames = [f.strip().lstrip("\ufeff") for f in reader.fieldnames]
    return reader


def normalize_csv(data: bytes, source_url: str, season: str, source_file: str, competition_code: str | None = None) -> list[dict]:
    rows = []
    for row in _lecteur(data):
        dom = _clean(row.get("HomeTeam")) or _clean(row.get("Home"))
        ext = _clean(row.get("AwayTeam")) or _clean(row.get("Away"))
        if not (dom and ext):
            continue
        out = normalize_row(row, source_url, season, source_file)
        if competition_code and not out.get("competition_code"):
            out["competition_code"] = competition_code
        rows.append(out)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------------------------------------------
# Découverte (liens lus sur les pages, jamais construits)
# ---------------------------------------------------------------------------------------------------------------
def discover_zip(session, season: str) -> str | None:
    return afd.discover_zip(session, season)


def discover_new_leagues(session, pause: float = PAUSE_S) -> dict[str, str]:
    return afd.discover_new_leagues(session, pause=pause)


# ---------------------------------------------------------------------------------------------------------------
# Collecte
# ---------------------------------------------------------------------------------------------------------------
def _ecrit_division(root: Path, season: str, code: str, data: bytes, source_url: str, files: dict, meta: dict,
                    stats: dict, sous_dossier: str = "") -> None:
    cle = f"{season}/{sous_dossier}{code}"
    digest = sha256_bytes(data)
    raw_path = root / "raw" / season / sous_dossier / f"{code}.csv"
    norm_path = root / "normalized" / season / f"{code}.jsonl"
    ancien = files.get(cle)
    if ancien and ancien.get("sha256") == digest and raw_path.exists() and norm_path.exists():
        stats["unchanged"] += 1
        return
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(data)
    rows = normalize_csv(data, source_url, season, raw_path.name, competition_code=code)
    write_jsonl(norm_path, rows)
    # Fraîcheur visible (métadonnée, pas un calcul) : date du dernier match présent dans la source. Constat du
    # 24/09/2026 : Football-Data publie les résultats avec 1 à 4 jours de retard (divisions principales le lundi,
    # championnats supplémentaires le mardi) ; la Russie n'était plus mise à jour depuis le 04/08.
    dates = [r["date"] for r in rows if r.get("date")]
    files[cle] = dict(meta, season=season, competition_code=code, source_url=source_url, sha256=digest,
                      bytes=len(data), rows_normalized=len(rows), last_match_date=max(dates) if dates else None,
                      downloaded_at_utc=now_utc(), immutable=False)
    stats["updated" if ancien else "downloaded"] += 1


def collect(*, root: Path = DEFAULT_ROOT, current_season: str | None = None, session=None,
            pause: float = PAUSE_S) -> dict:
    season = current_season or saison_en_cours()
    session = session or requests.Session()
    if hasattr(session, "headers"):
        session.headers.update({"User-Agent": "ArchetypeFoot/football-data-collector"})
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.pop("odds_captures", None)
    files = manifest.setdefault("files", {})
    sources = manifest.setdefault("sources", {})
    stats = {"season": season, "discovered": 0, "downloaded": 0, "updated": 0, "unchanged": 0,
             "sources_not_modified": 0, "errors": {}}

    # 1) 22 divisions principales : archive data.zip de la saison
    try:
        zip_url = discover_zip(session, season)
        if not zip_url:
            raise RuntimeError(f"archive data.zip de la saison {season} introuvable sur les pages d'index")
        contenu, validation = telecharge_si_change(session, zip_url, sources.get(zip_url))
        if contenu is None:
            stats["sources_not_modified"] += 1
            stats["discovered"] += len([k for k in files if k.startswith(season + "/") and "/nouvelles_ligues/" not in k])
        else:
            csvs = afd.csv_from_zip(contenu)
            stats["discovered"] += len(csvs)
            for code, data in csvs.items():
                country, competition = afd.COMPETITIONS.get(code, (None, None))
                _ecrit_division(root, season, code, data, f"{zip_url}#{code}.csv", files,
                                {"country": country, "competition": competition,
                                 "source_last_modified": validation.get("last_modified")}, stats)
            sources[zip_url] = dict(validation, sha256=sha256_bytes(contenu), checked_at_utc=now_utc())
    except Exception as exc:
        stats["errors"]["principales"] = str(exc)

    # 2) championnats supplémentaires : new/<CODE>.csv, lignes de la saison en cours seulement
    try:
        urls = discover_new_leagues(session, pause=pause)
        stats["discovered"] += len(urls)
        for code, url in urls.items():
            try:
                contenu, validation = telecharge_si_change(session, url, sources.get(url))
                if contenu is None:
                    stats["sources_not_modified"] += 1
                    continue
                filtre, infos = afd.filtre_saison(contenu, season)
                sources[url] = dict(validation, sha256=sha256_bytes(contenu), checked_at_utc=now_utc())
                if infos["rows"] == 0:
                    stats["errors"][code] = "aucune ligne pour la saison en cours"
                    continue
                _ecrit_division(root, season, code, filtre, url, files,
                                {"country": infos["country"], "competition": infos["competition"],
                                 "season_label": infos["season_label"], "season_format": infos["season_format"],
                                 "source_last_modified": validation.get("last_modified")},
                                stats, sous_dossier="nouvelles_ligues/")
            except Exception as exc:
                stats["errors"][code] = str(exc)
    except Exception as exc:
        stats["errors"]["supplementaires"] = str(exc)

    manifest.update({
        "schema_version": 2,
        "source": "football-data.co.uk",
        "current_season": season,
        "updated_at_utc": now_utc(),
        "historical_policy": "completed seasons are managed by archive_football_data.py snapshots",
        "current_season_policy": "download only when the source changed (ETag/Last-Modified, then SHA-256)",
        "odds_policy": "no odds collected (decision of 24/09/2026: no bookmaker comparison, no API)",
        "last_run": stats,
    })
    root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--current-season", default=None)
    args = parser.parse_args()
    try:
        stats = collect(root=Path(args.root), current_season=args.current_season)
    except Exception as exc:
        print(f"ERREUR collecte football-data: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False))
    # Une source en échec est signalée mais ne bloque pas le pipeline : le moteur garde les données déjà collectées.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
