#!/usr/bin/env python3
"""Crée un snapshot historique Football-Data complet et immuable.

Cette couche ne fait que découvrir, télécharger, vérifier et archiver les CSV
publiés par Football-Data.co.uk pour une saison terminée. Aucun calcul de
marché, moyenne, probabilité, EV, value ou signal n'est effectué.

Politique:
- tous les CSV découvrables pour la saison demandée sont archivés;
- un fichier déjà présent n'est jamais retéléchargé ni écrasé;
- le snapshot n'est marqué COMPLETE que si tous les fichiers découverts ont
  été téléchargés et vérifiés;
- un snapshot COMPLETE est ensuite en lecture seule pour ce collecteur;
- le moteur consomme le snapshot local, jamais le réseau.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

INDEX_URLS = (
    "https://www.football-data.co.uk/downloadm.php",
    "https://www.football-data.co.uk/all_new_data.php",
)
# CORRECTIF 24/09/2026 (vérifié sur la vraie page, diagnostic/sources/www_football_data_co_uk_downloadm_php.html) :
# pour une saison, downloadm.php ne publie PAS de lien CSV individuel mais une archive
# « mmz4281/<saison>/data.zip » contenant tous les CSV des divisions. Sans ce repli, la découverte ne trouvait
# aucun CSV et le snapshot 2526 échouait (« Aucun CSV Football-Data découvert »).
ZIP_RE = re.compile(r"/mmz4281/(?P<season>\d{4})/data\.zip$", re.I)
SEASON_RE = re.compile(r"/mmz4281/(?P<season>\d{4})/(?P<div>[A-Za-z0-9]+)\.csv$", re.I)
DEFAULT_ROOT = Path("data/football_data/snapshots")

COMPETITIONS = {
    "E0": ("England", "Premier League"),
    "E1": ("England", "Championship"),
    "E2": ("England", "League One"),
    "E3": ("England", "League Two"),
    "EC": ("England", "National League"),
    "SC0": ("Scotland", "Premiership"),
    "SC1": ("Scotland", "Championship"),
    "SC2": ("Scotland", "League One"),
    "SC3": ("Scotland", "League Two"),
    "D1": ("Germany", "Bundesliga"),
    "D2": ("Germany", "2. Bundesliga"),
    "I1": ("Italy", "Serie A"),
    "I2": ("Italy", "Serie B"),
    "SP1": ("Spain", "La Liga"),
    "SP2": ("Spain", "La Liga 2"),
    "F1": ("France", "Ligue 1"),
    "F2": ("France", "Ligue 2"),
    "N1": ("Netherlands", "Eredivisie"),
    "N2": ("Netherlands", "Eerste Divisie"),
    "B1": ("Belgium", "Jupiler Pro League"),
    "P1": ("Portugal", "Primeira Liga"),
    "T1": ("Turkey", "Super Lig"),
    "G1": ("Greece", "Super League"),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discover_urls(session: requests.Session, season: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for index_url in INDEX_URLS:
        response = session.get(index_url, timeout=30)
        response.raise_for_status()
        for href in re.findall(r"""href\s*=\s*["']([^"']+\.csv)["']""", response.text, re.I):
            url = urljoin(index_url, href)
            match = SEASON_RE.search(url.replace("\\", "/"))
            if not match or match.group("season") != season:
                continue
            div = match.group("div").upper()
            found.setdefault(div, url)
    return dict(sorted(found.items()))


def discover_zip(session: requests.Session, season: str) -> str | None:
    """URL de l'archive data.zip de la saison, telle que publiée sur les pages d'index (jamais construite)."""
    for index_url in INDEX_URLS:
        response = session.get(index_url, timeout=30)
        response.raise_for_status()
        for href in re.findall(r"""href\s*=\s*["']([^"']+\.zip)["']""", response.text, re.I):
            url = urljoin(index_url, href)
            match = ZIP_RE.search(url.replace("\\", "/"))
            if match and match.group("season") == season:
                return url
    return None


def csv_from_zip(data: bytes) -> dict[str, bytes]:
    """CSV contenus dans l'archive, par code de division (nom du fichier sans extension)."""
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            base = name.rsplit("/", 1)[-1]
            if base.lower().endswith(".csv") and base[:-4]:
                out[base[:-4].upper()] = archive.read(name)
    return dict(sorted(out.items()))


def build_catalogue(season: str, urls: dict[str, str]) -> list[dict]:
    rows = []
    for div, url in urls.items():
        country, competition = COMPETITIONS.get(div, (None, None))
        rows.append({
            "competition_code": div,
            "country": country,
            "competition": competition,
            "season": season,
            "source_url": url,
            "discovery_source": "football-data.co.uk/downloadm.php|all_new_data.php"
                                + (" (archive data.zip de la saison)" if "#" in url else ""),
        })
    return rows


def download(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=90)
    response.raise_for_status()
    if not response.content:
        raise ValueError(f"Réponse vide: {url}")
    return response.content


def load_manifest(path: Path, season: str) -> dict:
    if not path.exists():
        return {
            "schema_version": 1,
            "source": "football-data.co.uk",
            "season": season,
            "status": "INCOMPLETE",
            "created_at_utc": now_utc(),
            "updated_at_utc": now_utc(),
            "files": {},
            "failed": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def archive_snapshot(
    *,
    season: str,
    root: Path = DEFAULT_ROOT,
    session: requests.Session | None = None,
) -> dict:
    snapshot = root / season
    raw_dir = snapshot / "raw"
    manifest_path = snapshot / "manifest.json"
    marker = snapshot / "_SNAPSHOT_COMPLETE.json"
    manifest = load_manifest(manifest_path, season)

    if marker.exists() or manifest.get("status") == "COMPLETE":
        return {
            "season": season,
            "status": "COMPLETE",
            "discovered": len(manifest.get("files", {})),
            "downloaded": 0,
            "skipped_existing": len(manifest.get("files", {})),
            "failed": 0,
            "immutable": True,
        }

    session = session or requests.Session()
    session.headers.update({"User-Agent": "ArchetypeFoot/football-data-snapshot"})
    urls = discover_urls(session, season)
    contenus_zip: dict[str, bytes] = {}
    zip_info: dict | None = None
    if not urls:
        zip_url = discover_zip(session, season)
        if zip_url:
            zip_data = download(session, zip_url)
            contenus_zip = csv_from_zip(zip_data)
            urls = {div: f"{zip_url}#{div}.csv" for div in contenus_zip}
            zip_info = {"source_url": zip_url, "sha256": sha256_bytes(zip_data), "bytes": len(zip_data),
                        "downloaded_at_utc": now_utc(), "csv_count": len(contenus_zip)}

    if not urls:
        raise RuntimeError(f"Aucun CSV Football-Data découvert pour la saison {season}")

    catalogue_path = snapshot / "catalogue.json"
    catalogue = {
        "schema_version": 1,
        "source": "football-data.co.uk",
        "season": season,
        "generated_at_utc": now_utc(),
        "entries": build_catalogue(season, urls),
    }
    snapshot.mkdir(parents=True, exist_ok=True)
    catalogue_path.write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    files = manifest.setdefault("files", {})
    failed: dict[str, str] = {}
    downloaded = 0
    skipped = 0

    for div, url in urls.items():
        path = raw_dir / f"{div}.csv"
        existing = files.get(div)

        if path.exists():
            data = path.read_bytes()
            digest = sha256_bytes(data)
            if existing and existing.get("sha256") not in (None, digest):
                raise RuntimeError(
                    f"Conflit d'archive pour {div}: le fichier local diffère du manifeste"
                )
            country, competition = COMPETITIONS.get(div, (None, None))
            files[div] = {
                "competition_code": div,
                "country": country,
                "competition": competition,
                "source_url": url,
                "sha256": digest,
                "bytes": len(data),
                "archived_at_utc": (existing or {}).get("archived_at_utc"),
                "immutable": True,
            }
            skipped += 1
            continue

        try:
            data = contenus_zip[div] if div in contenus_zip else download(session, url)
            digest = sha256_bytes(data)
            raw_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            country, competition = COMPETITIONS.get(div, (None, None))
            files[div] = {
                "competition_code": div,
                "country": country,
                "competition": competition,
                "source_url": url,
                "sha256": digest,
                "bytes": len(data),
                "archived_at_utc": now_utc(),
                "immutable": True,
            }
            downloaded += 1
        except Exception as exc:
            failed[div] = str(exc)

    manifest.update({
        "schema_version": 1,
        "source": "football-data.co.uk",
        "season": season,
        "status": "COMPLETE" if not failed and len(files) == len(urls) else "INCOMPLETE",
        "updated_at_utc": now_utc(),
        "discovered_count": len(urls),
        "archived_count": len(files),
        "failed": failed,
        "coverage": sorted(urls),
        "policy": "immutable completed-season snapshot; no overwrite and no redownload",
    })
    if zip_info:
        manifest["source_archive"] = zip_info
    snapshot.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if manifest["status"] == "COMPLETE":
        marker.write_text(
            json.dumps({
                "status": "COMPLETE",
                "season": season,
                "completed_at_utc": now_utc(),
                "files": len(files),
                "sha256_manifest": sha256_bytes(manifest_path.read_bytes()),
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return {
        "season": season,
        "status": manifest["status"],
        "discovered": len(urls),
        "downloaded": downloaded,
        "skipped_existing": skipped,
        "failed": len(failed),
        "immutable": manifest["status"] == "COMPLETE",
    }


# =====================================================================================================================
# AJOUT 24/09/2026 — Championnats supplémentaires (« new leagues ») : toutes les divisions publiées, pas seulement 22.
# =====================================================================================================================
# Vérifié sur les vraies pages (diagnostic/sources/) : all_new_data.php renvoie vers une page par pays (argentina.php,
# usa.php, ...) ; chaque page publie un fichier « new/<CODE>.csv » qui contient TOUTES les saisons de ce championnat
# (colonnes Country, League, Season, Date, Time, Home, Away, HG, AG, Res, puis des cotes). Ces fichiers ne sont pas
# dans l'archive data.zip de la saison.
#
# Rangement : sous-dossier séparé « <saison>/nouvelles_ligues/ » avec son propre manifeste, catalogue et verrou, pour ne
# JAMAIS toucher un snapshot principal déjà verrouillé. Pour chaque championnat, seules les lignes de la saison sont
# conservées (le fichier complet change pendant la saison en cours) ; l'empreinte SHA-256 du fichier téléchargé est
# gardée comme preuve de provenance.
#
# Correspondance des saisons (règle écrite, jamais devinée) : pour la saison « 2526 »,
#   - championnat à cheval sur deux années (valeurs « 2025/2026 ») -> lignes « 2025/2026 » ;
#   - championnat sur l'année civile (valeurs « 2025 ») -> lignes « 2025 » (dernière saison civile terminée).
NEW_INDEX_URL = "https://www.football-data.co.uk/all_new_data.php"
NEW_CSV_RE = re.compile(r"/new/(?P<code>[A-Za-z0-9]+)\.csv$", re.I)
NEW_EXCLUS = {"LATEST_RESULTS"}
PAUSE_ENTRE_PAGES_S = 1.0


def saison_libelles(season: str) -> tuple[str, str]:
    """« 2526 » -> (« 2025/2026 », « 2025 »)."""
    if not re.fullmatch(r"\d{4}", season):
        raise ValueError(f"Saison invalide : {season}")
    debut = 2000 + int(season[:2])
    return f"{debut}/{debut + 1}", str(debut)


def discover_new_leagues(session: requests.Session, pause: float = PAUSE_ENTRE_PAGES_S) -> dict[str, str]:
    """{CODE: URL new/CODE.csv} trouvés sur les pages liées depuis all_new_data.php (liens lus, jamais construits)."""
    import time
    response = session.get(NEW_INDEX_URL, timeout=30)
    response.raise_for_status()
    pages = []
    for href in re.findall(r"""href\s*=\s*["']([^"']+\.php)["']""", response.text, re.I):
        url = urljoin(NEW_INDEX_URL, href)
        if "football-data.co.uk/" in url and "/blog/" not in url and "/resources/" not in url and url not in pages:
            pages.append(url)
    found: dict[str, str] = {}
    for page in pages:
        try:
            r = session.get(page, timeout=30)
            r.raise_for_status()
        except Exception:  # une page indisponible n'invente rien : elle est simplement ignorée
            continue
        for href in re.findall(r"""href\s*=\s*["']([^"']+\.csv)["']""", r.text, re.I):
            url = urljoin(page, href)
            m = NEW_CSV_RE.search(url)
            if m and m.group("code").upper() not in NEW_EXCLUS:
                found.setdefault(m.group("code").upper(), url)
        if pause:
            time.sleep(pause)
    return dict(sorted(found.items()))


def filtre_saison(data: bytes, season: str) -> tuple[bytes, dict]:
    """Garde l'en-tête et les lignes de la saison. Renvoie (csv_filtré, infos). Lève ValueError si pas de colonne Season."""
    import csv
    texte = data.decode("utf-8-sig", errors="replace")
    lignes = texte.splitlines()
    if not lignes:
        raise ValueError("fichier vide")
    entete = next(csv.reader([lignes[0]]))
    noms = [c.strip() for c in entete]
    if "Season" not in noms:
        raise ValueError("colonne Season absente")
    i_saison = noms.index("Season")
    i_pays = noms.index("Country") if "Country" in noms else None
    i_ligue = noms.index("League") if "League" in noms else None
    a_cheval, civile = saison_libelles(season)
    gardees, pays, ligue = [], None, None
    for ligne in lignes[1:]:
        champs = next(csv.reader([ligne])) if ligne.strip() else []
        if len(champs) <= i_saison:
            continue
        v = champs[i_saison].strip().replace("-", "/")
        if v in (a_cheval, civile):
            gardees.append(ligne)
            if i_pays is not None and pays is None:
                pays = champs[i_pays].strip() or None
            if i_ligue is not None and ligue is None:
                ligue = champs[i_ligue].strip() or None
    # CORRECTIF 24/09/2026 : certains championnats ont changé de format (Argentine : « 2019/2020 » puis « 2020 »... ;
    # Japon : « 2025 » puis « 2026/2027 »). Le format se décide sur les lignes de la saison, pas sur tout le fichier :
    # lignes « AAAA/AAAA+1 » si elles existent, sinon lignes « AAAA ».
    compte = {a_cheval: 0, civile: 0}
    for l in gardees:
        compte[next(csv.reader([l]))[i_saison].strip().replace("-", "/")] += 1
    format_saison = "a_cheval" if compte[a_cheval] else "civile"
    libelle = a_cheval if format_saison == "a_cheval" else civile
    gardees = [l for l in gardees if next(csv.reader([l]))[i_saison].strip().replace("-", "/") == libelle]
    sortie = ("\n".join([lignes[0]] + gardees) + "\n").encode("utf-8")
    return sortie, {"season_label": libelle, "season_format": format_saison, "rows": len(gardees),
                    "country": pays, "competition": ligue}


def archive_new_leagues(*, season: str, root: Path = DEFAULT_ROOT, session: requests.Session | None = None,
                        pause: float = PAUSE_ENTRE_PAGES_S) -> dict:
    snapshot = root / season / "nouvelles_ligues"
    raw_dir = snapshot / "raw"
    manifest_path = snapshot / "manifest.json"
    marker = snapshot / "_SNAPSHOT_COMPLETE.json"
    manifest = load_manifest(manifest_path, season)
    if marker.exists() or manifest.get("status") == "COMPLETE":
        return {"season": season, "scope": "nouvelles_ligues", "status": "COMPLETE", "downloaded": 0, "immutable": True,
                "discovered": len(manifest.get("files", {})) + len(manifest.get("empty", {}))}
    session = session or requests.Session()
    session.headers.update({"User-Agent": "ArchetypeFoot/football-data-snapshot"})
    urls = discover_new_leagues(session, pause=pause)
    if not urls:
        raise RuntimeError("Aucun fichier de championnat supplémentaire découvert")
    files = manifest.setdefault("files", {})
    failed: dict[str, str] = {}
    empty: dict[str, dict] = {}
    downloaded = 0
    for code, url in urls.items():
        path = raw_dir / f"{code}.csv"
        if path.exists() and code in files:
            if sha256_bytes(path.read_bytes()) != files[code].get("sha256"):
                raise RuntimeError(f"Conflit d'archive pour {code}: le fichier local diffère du manifeste")
            continue
        if path.exists():
            raise RuntimeError(f"Conflit d'archive pour {code}: fichier local sans entrée de manifeste")
        try:
            data = download(session, url)
            filtre, infos = filtre_saison(data, season)
        except Exception as exc:
            failed[code] = str(exc)
            continue
        if infos["rows"] == 0:
            empty[code] = {"source_url": url, "source_sha256": sha256_bytes(data), "season_format": infos["season_format"]}
            continue
        raw_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(filtre)
        files[code] = {"competition_code": code, "country": infos["country"], "competition": infos["competition"],
                       "season_label": infos["season_label"], "season_format": infos["season_format"],
                       "rows": infos["rows"], "source_url": url, "source_sha256": sha256_bytes(data),
                       "source_bytes": len(data), "sha256": sha256_bytes(filtre), "bytes": len(filtre),
                       "archived_at_utc": now_utc(), "immutable": True}
        downloaded += 1
    manifest.update({"schema_version": 1, "source": "football-data.co.uk (championnats supplémentaires)",
                     "season": season, "updated_at_utc": now_utc(), "discovered_count": len(urls),
                     "archived_count": len(files), "empty": empty, "failed": failed,
                     "status": "COMPLETE" if not failed and len(files) + len(empty) == len(urls) else "INCOMPLETE",
                     "season_rule": "à cheval : « AAAA/AAAA+1 » ; année civile : « AAAA » (première année de la saison)",
                     "policy": "immutable completed-season snapshot; no overwrite and no redownload"})
    snapshot.mkdir(parents=True, exist_ok=True)
    catalogue = {"schema_version": 1, "source": "football-data.co.uk", "season": season, "generated_at_utc": now_utc(),
                 "entries": [{"competition_code": c, "country": f["country"], "competition": f["competition"],
                              "season_label": f["season_label"], "rows": f["rows"], "source_url": f["source_url"]}
                             for c, f in sorted(files.items())]}
    (snapshot / "catalogue.json").write_text(json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if manifest["status"] == "COMPLETE":
        marker.write_text(json.dumps({"status": "COMPLETE", "season": season, "scope": "nouvelles_ligues",
                                      "completed_at_utc": now_utc(), "files": len(files), "empty": sorted(empty),
                                      "sha256_manifest": sha256_bytes(manifest_path.read_bytes())},
                                     ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"season": season, "scope": "nouvelles_ligues", "status": manifest["status"], "discovered": len(urls),
            "downloaded": downloaded, "empty": len(empty), "failed": len(failed),
            "immutable": manifest["status"] == "COMPLETE"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True, help="Code Football-Data, ex. 2526")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--scope", choices=("toutes", "principales", "supplementaires"), default="toutes",
                        help="toutes (défaut) = 22 divisions principales + championnats supplémentaires")
    args = parser.parse_args()
    code = 0
    if args.scope in ("toutes", "principales"):
        try:
            print(json.dumps(archive_snapshot(season=args.season, root=Path(args.root)), ensure_ascii=False))
        except Exception as exc:
            print(f"ERREUR snapshot Football-Data (principales): {exc}", file=sys.stderr)
            code = 1
    if args.scope in ("toutes", "supplementaires"):
        try:
            print(json.dumps(archive_new_leagues(season=args.season, root=Path(args.root)), ensure_ascii=False))
        except Exception as exc:
            print(f"ERREUR snapshot Football-Data (supplémentaires): {exc}", file=sys.stderr)
            code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
