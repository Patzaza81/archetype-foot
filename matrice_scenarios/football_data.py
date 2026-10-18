"""Adaptateur lecture seule des archives Football-Data du dépôt vers le format de la matrice.

Sources lues (jamais modifiées) :
  - data/football_data/snapshots/<saison>/raw/*.csv et .../nouvelles_ligues/raw/*.csv (saisons terminées) ;
  - data/football_data/normalized/<saison>/*.jsonl (saison en cours).

Ces fichiers contiennent des RÉSULTATS et des dates, pas des cotes du run : le contrat du dépôt
(`data/football_data/CONTRAT.md`) précise que leurs colonnes de cotes ne sont pas interprétées comme
cotes d'ouverture ou de clôture. L'adaptateur n'en lit donc AUCUNE : les enregistrements produits n'ont
ni `target_odds` ni cote 1X2, et ne peuvent servir ni au ROI ni à la comparaison au marché.

Preuve pré-match : l'historique d'une équipe ne contient que des matchs terminés à une date strictement
antérieure à celle du match évalué (la matrice applique ce filtre dans `build_features`). Aucun horodatage
de capture n'existe pour ces sources ; cette limite est publiée dans le diagnostic.
"""
from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_fd_date(value: Any) -> str | None:
    text = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _country_by_code(root: Path) -> dict[str, tuple[str, str]]:
    """code de compétition -> (pays, compétition), lu dans les catalogues du dépôt."""
    mapping: dict[str, tuple[str, str]] = {}
    for path in sorted(root.glob("snapshots/*/catalogue.json")) + sorted(root.glob("snapshots/*/nouvelles_ligues/catalogue.json")):
        try:
            catalogue = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in catalogue.get("entries", []):
            code = entry.get("competition_code")
            if code and code not in mapping:
                mapping[code] = (str(entry.get("country") or code), str(entry.get("competition") or code))
    return mapping


def _read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig", errors="replace"))))


def _raw_rows(root: Path, countries: dict[str, tuple[str, str]]) -> tuple[list[dict], Counter]:
    rows, stats = [], Counter()
    for path in sorted(root.glob("snapshots/*/raw/*.csv")):
        code = path.stem
        country, competition = countries.get(code, (code, code))
        for row in _read_csv(path):
            day, hg, ag = _parse_fd_date(row.get("Date")), _int_or_none(row.get("FTHG")), _int_or_none(row.get("FTAG"))
            home, away = (row.get("HomeTeam") or "").strip(), (row.get("AwayTeam") or "").strip()
            if not (day and home and away) or hg is None or ag is None:
                stats["SANS_SCORE_OU_INCOMPLET"] += 1
                continue
            rows.append({"code": code, "country": country, "competition": competition, "date": day,
                         "home": home, "away": away, "hg": hg, "ag": ag, "source": f"snapshot:{path.parent.parent.name}"})
    for path in sorted(root.glob("snapshots/*/nouvelles_ligues/raw/*.csv")):
        code = path.stem
        for row in _read_csv(path):
            day, hg, ag = _parse_fd_date(row.get("Date")), _int_or_none(row.get("HG")), _int_or_none(row.get("AG"))
            home, away = (row.get("Home") or "").strip(), (row.get("Away") or "").strip()
            if not (day and home and away) or hg is None or ag is None:
                stats["SANS_SCORE_OU_INCOMPLET"] += 1
                continue
            rows.append({"code": code, "country": str(row.get("Country") or code), "competition": str(row.get("League") or code),
                         "date": day, "home": home, "away": away, "hg": hg, "ag": ag,
                         "source": f"snapshot:{path.parent.parent.parent.name}/nouvelles_ligues"})
    return rows, stats


def _normalized_rows(root: Path, countries: dict[str, tuple[str, str]]) -> tuple[list[dict], Counter]:
    rows, stats = [], Counter()
    for path in sorted(root.glob("normalized/*/*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            code = str(item.get("competition_code") or path.stem)
            country, competition = countries.get(code, (str(item.get("country") or code), str(item.get("competition") or code)))
            hg, ag = _int_or_none(item.get("full_time_home_goals")), _int_or_none(item.get("full_time_away_goals"))
            day = _parse_fd_date(item.get("date"))
            home, away = str(item.get("home_team") or "").strip(), str(item.get("away_team") or "").strip()
            if not (day and home and away) or hg is None or ag is None:
                stats["SANS_SCORE_OU_INCOMPLET"] += 1
                continue
            rows.append({"code": code, "country": str(item.get("country") or country), "competition": str(item.get("competition") or competition),
                         "date": day, "home": home, "away": away, "hg": hg, "ag": ag, "source": f"normalized:{path.parent.name}"})
    return rows, stats


def load_football_data(root: str | Path = "data/football_data", *, until: str | None = None) -> tuple[list[dict], dict]:
    """Charge toutes les archives Football-Data en enregistrements de la matrice.

    `until` (AAAA-MM-JJ, inclus) écarte tout match plus récent : sert à geler une période avant un test externe.
    Les doublons (même compétition, date et équipes) sont fusionnés s'ils ont le même score et exclus s'ils se contredisent.
    """
    base = Path(root)
    countries = _country_by_code(base)
    raw, raw_stats = _raw_rows(base, countries)
    norm, norm_stats = _normalized_rows(base, countries)
    candidates = raw + norm
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in candidates:
        groups[(row["code"], row["date"], row["home"], row["away"])].append(row)
    rejected = Counter(raw_stats) + Counter(norm_stats)
    kept, duplicates, conflicts = [], 0, 0
    for versions in groups.values():
        if len(versions) > 1:
            duplicates += len(versions) - 1
            if len({(v["hg"], v["ag"]) for v in versions}) > 1:
                conflicts += 1
                rejected["DOUBLON_CONTRADICTOIRE"] += len(versions)
                continue
        kept.append(versions[0])
    if until is not None:
        before = len(kept)
        kept = [r for r in kept if r["date"] <= until]
        rejected["APRES_DATE_LIMITE"] += before - len(kept)
    kept.sort(key=lambda r: (r["date"], r["code"], r["home"], r["away"]))

    # Historique par équipe (pays + nom exact) : tous ses matchs terminés, partagés par référence.
    # `build_features` ne retient que les matchs strictement antérieurs à la date évaluée.
    history: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in kept:
        history[(r["country"], r["home"])].append({"date": r["date"], "goals_for": r["hg"], "goals_against": r["ag"], "venue": "home", "opponent": r["away"]})
        history[(r["country"], r["away"])].append({"date": r["date"], "goals_for": r["ag"], "goals_against": r["hg"], "venue": "away", "opponent": r["home"]})
    records = []
    for r in kept:
        records.append({
            "match_id": f'fd|{r["code"]}|{r["date"]}|{r["home"]}|{r["away"]}', "date": r["date"],
            "league": f'{r["country"]} : {r["competition"]}', "home_team": r["home"], "away_team": r["away"],
            "home_goals": r["hg"], "away_goals": r["ag"],
            "home_history": history[(r["country"], r["home"])], "away_history": history[(r["country"], r["away"])],
            "target_odds": {}, "source_archive": "football_data",
        })
    by_league = Counter(rec["league"] for rec in records)
    months = Counter(rec["date"][:7] for rec in records)
    return records, {
        "source": "data/football_data (résultats seulement ; aucune cote lue)",
        "matches": len(records), "duplicate_rows": duplicates, "conflicting_matches": conflicts,
        "rejected": dict(rejected), "leagues": len(by_league),
        "first_date": records[0]["date"] if records else None, "last_date": records[-1]["date"] if records else None,
        "matches_by_month": dict(sorted(months.items())),
        "prematch_proof": "dates strictement antérieures uniquement ; aucun horodatage de capture disponible pour cette source",
        "odds_used": False,
    }
