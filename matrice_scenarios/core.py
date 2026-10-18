"""Découverte contrôlée de scénarios prédictifs sur données pré-match normalisées.

Aucune dépendance tierce. Ce module ne modifie aucun moteur ni donnée de production.
Chaque enregistrement est un match unique avec score final et informations disponibles
avant le coup d'envoi. Les historiques d'équipes doivent contenir des matchs datés.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import random
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
TARGETS = (
    "home_not_lose", "away_not_lose", "home_win", "away_win", "draw",
    "home_scores_1plus", "home_scores_2plus", "home_scores_3plus",
    "away_scores_1plus", "away_scores_2plus", "away_scores_3plus",
    "both_score", "under_2_5", "under_3_5", "over_1_5", "over_2_5",
)
WINDOWS = (2, 3, 5, 8, 10)
MIN_DISCOVERY_SUPPORT = 30
MIN_EVAL_SUPPORT = 30
# 16 cibles par règle : 5000 scénarios ne donnaient que ~300 règles, moins que le nombre de variables.
DEFAULT_MAX_CANDIDATES = 20000
# Graine fixe : l'échantillonnage des interactions est déterministe et ne dépend que de la découverte.
DISCOVERY_SEED = 20261018
# Critères de sélection gelés a priori ; ils n'utilisent jamais le segment test.
SELECTION_CRITERIA = {"train_q_bh_max": 0.10, "validation_min_n": MIN_EVAL_SUPPORT, "validation_lift_min_exclusive": 0.0}
_THRESHOLDS = (0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100)


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_score(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _as_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _parse_ts(value: Any) -> datetime | None:
    """Horodatage ISO 8601 -> datetime UTC (accepte 'Z' et '+00:00'); None si absent ou illisible."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def prematch_timing_issue(record: dict) -> str | None:
    """Raison du refus si la capture (cotes, classement, historique) n'est pas PROUVÉE antérieure
    au coup d'envoi ; None sinon. Les sources normalisées sans `snapshot_at` suivent le contrat
    documenté (la provenance pré-match y est déclarée par l'appelant, la matrice ne peut pas la prouver)."""
    if "snapshot_at" not in record:
        return None
    snapshot, kickoff = _parse_ts(record.get("snapshot_at")), _parse_ts(record.get("kickoff_at"))
    if snapshot is None:
        return "CAPTURE_SANS_HORODATAGE"
    if kickoff is None:
        return "COUP_D_ENVOI_ABSENT"
    if snapshot >= kickoff:
        return "CAPTURE_APRES_COUP_D_ENVOI"
    return None


def validate_record(record: Any) -> tuple[bool, str]:
    """Valide la structure minimale; les enregistrements ambigus sont refusés, jamais devinés."""
    if not isinstance(record, dict):
        return False, "ENREGISTREMENT_NON_OBJET"
    for key in ("match_id", "date", "home_team", "away_team"):
        if not str(record.get(key, "")).strip():
            return False, f"CHAMP_ABSENT:{key}"
    if _as_date(record.get("date")) is None:
        return False, "DATE_INVALIDE"
    if record["home_team"] == record["away_team"]:
        return False, "EQUIPES_IDENTIQUES"
    if not _valid_score(record.get("home_goals")) or not _valid_score(record.get("away_goals")):
        return False, "SCORE_ABSENT_OU_INVALIDE"
    if not isinstance(record.get("home_history", []), list) or not isinstance(record.get("away_history", []), list):
        return False, "HISTORIQUE_INVALIDE"
    timing = prematch_timing_issue(record)
    if timing:
        return False, timing
    return True, "OK"


def _archive_history(team_block: Any) -> list[dict]:
    if not isinstance(team_block, dict) or team_block.get("statut") != "OK":
        return []
    out = []
    for match in team_block.get("matchs") or []:
        if not isinstance(match, dict):
            continue
        out.append({
            "date": match.get("date"),
            "goals_for": match.get("buts_marques"),
            "goals_against": match.get("buts_encaisses"),
            "venue": "home" if match.get("domicile") is True else "away",
            "opponent": match.get("adversaire"),
            "opponent_rank": match.get("rang_adversaire"),
        })
    return out


def _archive_target_odds(item: dict) -> dict[str, float]:
    """Mapping explicite depuis les clés réelles de parse_betpawa.py / cotes_archive.py."""
    raw = item.get("cotes_betpawa") or {}
    observed = item.get("cotes_observees") or {}
    mapping = {
        "home_win": (("1x2", "1"), "1X2 - 1"),
        "draw": (("1x2", "N"), "1X2 - X"),
        "away_win": (("1x2", "2"), "1X2 - 2"),
        "home_not_lose": (("double_chance", "1N"), "Double chance - 1X"),
        "away_not_lose": (("double_chance", "N2"), "Double chance - X2"),
        "both_score": (("btts", "Oui"), "BTTS - oui"),
        "under_2_5": (("over_under_2.5", "moins"), "Moins de 2.5 buts"),
        "under_3_5": (("over_under_3.5", "moins"), "Moins de 3.5 buts"),
        "over_1_5": (("over_under_1.5", "plus"), "Plus de 1.5 buts"),
        "over_2_5": (("over_under_2.5", "plus"), "Plus de 2.5 buts"),
        "home_scores_1plus": (("over_under_domicile_0.5", "plus"), "Plus de 0.5 buts - Domicile"),
        "home_scores_2plus": (("over_under_domicile_1.5", "plus"), "Plus de 1.5 buts - Domicile"),
        "home_scores_3plus": (("over_under_domicile_2.5", "plus"), "Plus de 2.5 buts - Domicile"),
        "away_scores_1plus": (("over_under_exterieur_0.5", "plus"), "Plus de 0.5 buts - Extérieur"),
        "away_scores_2plus": (("over_under_exterieur_1.5", "plus"), "Plus de 1.5 buts - Extérieur"),
        "away_scores_3plus": (("over_under_exterieur_2.5", "plus"), "Plus de 2.5 buts - Extérieur"),
    }
    result = {}
    for target, ((group, issue), observed_label) in mapping.items():
        value = (raw.get(group) or {}).get(issue)
        if not _num(value) or value <= 1:
            value = observed.get(observed_label)
        if _num(value) and value > 1:
            result[target] = float(value)
    return result


def _record_from_archive(item: Any) -> dict | None:
    """Convertit un enregistrement SCHEMA_VERSION 2 de archive_donnees_test.py."""
    if not isinstance(item, dict) or not isinstance(item.get("score"), dict):
        return None
    score = item["score"]
    hg, ag = score.get("buts_dom"), score.get("buts_ext")
    if not _valid_score(hg) or not _valid_score(ag):
        return None
    home, away = item.get("equipe_dom") or {}, item.get("equipe_ext") or {}
    target_odds = _archive_target_odds(item)
    kickoff = _parse_ts(item.get("coup_d_envoi_utc"))

    def _timed_rank(team: dict) -> Any:
        # Un classement n'est gardé que si son horodatage prouve qu'il précède le coup d'envoi.
        stamp = _parse_ts(team.get("classement_horodatage"))
        return team.get("rang") if (stamp is not None and kickoff is not None and stamp < kickoff) else None

    return {
        "match_id": item.get("match_id"), "date": item.get("date"),
        "league": item.get("competition") or item.get("competition_brute"),
        "home_team": item.get("domicile"), "away_team": item.get("exterieur"),
        "home_goals": hg, "away_goals": ag,
        "snapshot_at": (item.get("run") or {}).get("pris_le"),
        "kickoff_at": item.get("coup_d_envoi_utc"),
        "home_rank": _timed_rank(home), "away_rank": _timed_rank(away),
        "home_odds": target_odds.get("home_win"), "draw_odds": target_odds.get("draw"),
        "away_odds": target_odds.get("away_win"),
        "home_history": _archive_history(home), "away_history": _archive_history(away),
        "target_odds": target_odds,
        "source_archive": "data/archive_test",
    }


def load_dataset(path: str | Path) -> tuple[list[dict], dict]:
    """Charge JSON, JSONL ou directement le dossier data/archive_test/*.json.gz.

    Les archives non résolues sont comptées, jamais transformées en scores imaginés.
    Les doublons à scores contradictoires sont exclus ; les doublons identiques gardent
    la première occurrence et sont comptés.
    """
    p = Path(path)
    rejected = Counter()
    archive_unresolved = 0
    if p.is_dir():
        payload = []
        for file in sorted(p.glob("*.json.gz")):
            with gzip.open(file, "rt", encoding="utf-8") as stream:
                document = json.load(stream)
            if not isinstance(document, dict):
                rejected["ARCHIVE_FORMAT_INVALIDE"] += 1
                continue
            for item in document.values():
                converted = _record_from_archive(item)
                if converted is None:
                    archive_unresolved += 1
                    continue
                payload.append(converted)
    else:
        raw = p.read_text(encoding="utf-8")
        if not raw.strip():
            payload = []
        else:
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    payload = payload.get("matches", [])
            except json.JSONDecodeError:
                payload = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not isinstance(payload, list):
        raise ValueError("Le fichier doit contenir une liste JSON, {matches:[...]}, du JSONL ou un dossier archive_test.")
    valid = []
    for row in payload:
        ok, reason = validate_record(row)
        if not ok:
            rejected[reason] += 1
            continue
        valid.append(row)
    rows, duplicates, conflicts, date_shifted = _dedupe(valid, rejected)
    return rows, {
        "input_rows": len(payload), "unique_matches": len(rows),
        "duplicate_rows": duplicates, "conflicting_match_ids": conflicts,
        "date_shifted_duplicates": date_shifted,
        "archive_unresolved_or_missing_score": archive_unresolved,
        "rejected": dict(rejected),
    }


def _dup_signature(record: dict) -> tuple:
    """Identité d'un match pour détecter les vraies contradictions.

    Pour une source horodatée (archive), la date peut légitimement différer d'une copie à l'autre
    (même match listé sur deux jours) : le choix de la copie se fait alors sur la preuve pré-match,
    et seule une différence d'équipes ou de score est une contradiction. Sans horodatage, la date
    reste dans la signature (comportement strict d'origine)."""
    base = (record["home_team"], record["away_team"], record["home_goals"], record["away_goals"])
    return base if "snapshot_at" in record else (record["date"],) + base


def _dedupe(valid: list[dict], rejected: Counter) -> tuple[list[dict], int, int, int]:
    """Un match par match_id. Copies identiques : on garde la capture la plus tardive encore
    antérieure au coup d'envoi (ou la première si la source n'est pas horodatée). Copies
    contradictoires : toutes exclues et comptées. Retourne (lignes, doublons, conflits, doublons à date décalée)."""
    by_id: dict[str, list[dict]] = {}
    for row in valid:
        by_id.setdefault(str(row["match_id"]), []).append(row)
    rows, duplicates, conflicts, date_shifted = [], 0, 0, 0
    for versions in by_id.values():
        if len(versions) > 1:
            duplicates += len(versions) - 1
            if len({_dup_signature(v) for v in versions}) > 1:
                conflicts += 1
                rejected["DOUBLON_CONTRADICTOIRE"] += len(versions)
                continue
            if len({str(v["date"])[:10] for v in versions}) > 1:
                date_shifted += 1
        timed = [v for v in versions if "snapshot_at" in v]
        rows.append(max(timed, key=lambda v: _parse_ts(v["snapshot_at"])) if timed else versions[0])
    rows.sort(key=lambda r: (str(r["date"]), str(r["match_id"])))
    return rows, duplicates, conflicts, date_shifted

def _history_before(history: list, match_date: str) -> list[dict]:
    """Seuls les matchs strictement antérieurs à la date du match cible sont admissibles."""
    out = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        d = _as_date(item.get("date"))
        if d is None or d.isoformat() >= str(match_date)[:10]:
            continue
        gf, ga = item.get("goals_for"), item.get("goals_against")
        if not _valid_score(gf) or not _valid_score(ga):
            continue
        out.append({**item, "date": d.isoformat(), "goals_for": gf, "goals_against": ga})
    # If same date occurs twice, keep both only if they are genuinely separate matches.
    return sorted(out, key=lambda x: x["date"])


def _streak(history: list[dict], predicate) -> int:
    n = 0
    for m in reversed(history):
        if not predicate(m):
            break
        n += 1
    return n


def _team_features(prefix: str, history: list[dict]) -> dict[str, float]:
    f: dict[str, float] = {f"{prefix}_history_n": float(len(history))}
    if not history:
        return f
    for window in WINDOWS:
        sample = history[-window:]
        n = len(sample)
        f[f"{prefix}_n_{window}"] = float(n)
        f[f"{prefix}_gf_avg_{window}"] = sum(m["goals_for"] for m in sample) / n
        f[f"{prefix}_ga_avg_{window}"] = sum(m["goals_against"] for m in sample) / n
        f[f"{prefix}_goal_diff_avg_{window}"] = sum(m["goals_for"] - m["goals_against"] for m in sample) / n
        f[f"{prefix}_score_rate_{window}"] = sum(m["goals_for"] >= 1 for m in sample) / n * 100
        f[f"{prefix}_concede_rate_{window}"] = sum(m["goals_against"] >= 1 for m in sample) / n * 100
        f[f"{prefix}_win_rate_{window}"] = sum(m["goals_for"] > m["goals_against"] for m in sample) / n * 100
        f[f"{prefix}_not_lose_rate_{window}"] = sum(m["goals_for"] >= m["goals_against"] for m in sample) / n * 100
        f[f"{prefix}_over_2_5_rate_{window}"] = sum(m["goals_for"] + m["goals_against"] > 2 for m in sample) / n * 100
    f[f"{prefix}_loss_streak"] = float(_streak(history, lambda m: m["goals_for"] < m["goals_against"]))
    f[f"{prefix}_not_lose_streak"] = float(_streak(history, lambda m: m["goals_for"] >= m["goals_against"]))
    f[f"{prefix}_score_streak"] = float(_streak(history, lambda m: m["goals_for"] >= 1))
    f[f"{prefix}_failed_score_streak"] = float(_streak(history, lambda m: m["goals_for"] == 0))
    f[f"{prefix}_concede_streak"] = float(_streak(history, lambda m: m["goals_against"] >= 1))
    # Dynamic transitions: what happened immediately before this fixture?
    last = history[-1]
    f[f"{prefix}_after_loss"] = float(last["goals_for"] < last["goals_against"])
    f[f"{prefix}_after_draw"] = float(last["goals_for"] == last["goals_against"])
    f[f"{prefix}_after_win"] = float(last["goals_for"] > last["goals_against"])
    f[f"{prefix}_after_away_loss"] = float(
        str(last.get("venue", "")).lower() == "away" and last["goals_for"] < last["goals_against"]
    )
    f[f"{prefix}_after_home_loss"] = float(
        str(last.get("venue", "")).lower() == "home" and last["goals_for"] < last["goals_against"]
    )
    f[f"{prefix}_after_heavy_loss"] = float(last["goals_against"] - last["goals_for"] >= 3)
    f[f"{prefix}_after_scoreless"] = float(last["goals_for"] == 0)
    f[f"{prefix}_after_scoring_2plus"] = float(last["goals_for"] >= 2)
    f[f"{prefix}_after_conceding_3plus"] = float(last["goals_against"] >= 3)
    recent3 = history[-3:]
    f[f"{prefix}_bad_run_3"] = float(len(recent3) == 3 and sum(
        m["goals_for"] < m["goals_against"] for m in recent3
    ) >= 2)
    f[f"{prefix}_recovery_candidate_3"] = float(len(recent3) == 3 and
        sum(m["goals_for"] < m["goals_against"] for m in recent3) >= 2 and
        last["goals_for"] >= 1)
    f[f"{prefix}_alternating_results_3"] = float(len(recent3) == 3 and len({
        1 if m["goals_for"] > m["goals_against"] else (-1 if m["goals_for"] < m["goals_against"] else 0)
        for m in recent3
    }) >= 2)
    # Lieu du match précédent et séries à domicile / à l'extérieur (« retour à domicile » = dernier
    # match à l'extérieur). Sans étiquette de lieu fiable, ces variables sont absentes : jamais devinées.
    def venue_of(m: dict) -> str | None:
        label = str(m.get("venue", "")).lower()
        return label if label in ("home", "away") else None
    if venue_of(last):
        f[f"{prefix}_last_venue_away"] = float(venue_of(last) == "away")
        f[f"{prefix}_last_venue_home"] = float(venue_of(last) == "home")
        f[f"{prefix}_away_streak"] = float(_streak(history, lambda m: venue_of(m) == "away"))
        f[f"{prefix}_home_streak"] = float(_streak(history, lambda m: venue_of(m) == "home"))
    # Marquer malgré les défaites : part des défaites des 5 derniers matchs où l'équipe a marqué.
    losses_5 = [m for m in history[-5:] if m["goals_for"] < m["goals_against"]]
    f[f"{prefix}_loss_count_5"] = float(len(losses_5))
    if losses_5:
        f[f"{prefix}_score_in_loss_rate_5"] = sum(m["goals_for"] >= 1 for m in losses_5) / len(losses_5) * 100
    # Venue-specific splits, when the source labels prior fixtures as home/away.
    for venue in ("home", "away"):
        subset = [m for m in history if str(m.get("venue", "")).lower() == venue]
        if subset:
            f[f"{prefix}_{venue}_n"] = float(len(subset))
            f[f"{prefix}_{venue}_gf_avg"] = sum(m["goals_for"] for m in subset) / len(subset)
            f[f"{prefix}_{venue}_ga_avg"] = sum(m["goals_against"] for m in subset) / len(subset)
            f[f"{prefix}_{venue}_not_lose_rate"] = sum(m["goals_for"] >= m["goals_against"] for m in subset) / len(subset) * 100
            f[f"{prefix}_{venue}_score_rate"] = sum(m["goals_for"] >= 1 for m in subset) / len(subset) * 100
    return f


def build_features(record: dict) -> dict[str, Any]:
    """Construit les variables pré-match; toute forme est recalculée depuis l'historique daté."""
    match_date = str(record["date"])[:10]
    home_hist = _history_before(record.get("home_history", []), match_date)
    away_hist = _history_before(record.get("away_history", []), match_date)
    features: dict[str, Any] = {
        "match_id": str(record["match_id"]), "date": match_date,
        "league": str(record.get("league") or "INCONNUE"),
        "home_team": str(record["home_team"]), "away_team": str(record["away_team"]),
        "home_history_n": float(len(home_hist)), "away_history_n": float(len(away_hist)),
    }
    features.update(_team_features("home", home_hist))
    features.update(_team_features("away", away_hist))
    # Head-to-head is joined only on exact normalized team names and prior dates.
    def norm_name(value):
        return " ".join(str(value or "").split()).casefold()
    home_name, away_name = norm_name(record["home_team"]), norm_name(record["away_team"])
    h2h = []
    seen_h2h = set()
    for match in home_hist:
        if norm_name(match.get("opponent")) == away_name:
            key = (match["date"], match["goals_for"], match["goals_against"])
            if key not in seen_h2h:
                seen_h2h.add(key)
                h2h.append((match["date"], match["goals_for"], match["goals_against"]))
    for match in away_hist:
        if norm_name(match.get("opponent")) == home_name:
            # Away team's goals-for/against are reversed into current home-team orientation.
            key = (match["date"], match["goals_against"], match["goals_for"])
            if key not in seen_h2h:
                seen_h2h.add(key)
                h2h.append(key)
    h2h.sort(key=lambda item: item[0])
    features["h2h_n"] = float(len(h2h))
    if h2h:
        features["h2h_home_score_rate"] = sum(h >= 1 for _, h, _ in h2h) / len(h2h) * 100
        features["h2h_away_score_rate"] = sum(a >= 1 for _, _, a in h2h) / len(h2h) * 100
        features["h2h_home_not_lose_rate"] = sum(h >= a for _, h, a in h2h) / len(h2h) * 100
        features["h2h_home_win_rate"] = sum(h > a for _, h, a in h2h) / len(h2h) * 100
        features["h2h_over_2_5_rate"] = sum(h + a >= 3 for _, h, a in h2h) / len(h2h) * 100
    hr, ar = record.get("home_rank"), record.get("away_rank")
    if _num(hr) and _num(ar) and hr > 0 and ar > 0:
        features["rank_gap"] = float(ar - hr)  # positif = domicile mieux classé (rang inférieur)
        features["rank_gap_abs"] = float(abs(ar - hr))
        features["home_rank"] = float(hr)
        features["away_rank"] = float(ar)
    for k in ("home_odds", "draw_odds", "away_odds"):
        if _num(record.get(k)) and record[k] > 1:
            features[k] = float(record[k])
    odds = [record.get(k) for k in ("home_odds", "draw_odds", "away_odds")]
    if all(_num(x) and x > 1 for x in odds):
        inv = [1 / x for x in odds]
        total = sum(inv)
        features["market_home_prob"] = inv[0] / total * 100
        features["market_draw_prob"] = inv[1] / total * 100
        features["market_away_prob"] = inv[2] / total * 100
        features["market_fav_gap"] = abs(inv[0] - inv[2]) / total * 100
    # User-provided, explicitly pre-match numeric indicators can enrich future scenarios.
    for key, value in (record.get("prematch_features") or {}).items():
        if isinstance(key, str) and key.startswith("pre_") and _num(value):
            features[key] = float(value)
    return features


def outcome(record: dict, target: str) -> int:
    h, a = record["home_goals"], record["away_goals"]
    goals = h + a
    rules = {
        "home_not_lose": h >= a, "away_not_lose": a >= h,
        "home_win": h > a, "away_win": a > h, "draw": h == a,
        "home_scores_1plus": h >= 1, "home_scores_2plus": h >= 2, "home_scores_3plus": h >= 3,
        "away_scores_1plus": a >= 1, "away_scores_2plus": a >= 2, "away_scores_3plus": a >= 3,
        "both_score": h >= 1 and a >= 1,
        "under_2_5": goals <= 2, "under_3_5": goals <= 3,
        "over_1_5": goals >= 2, "over_2_5": goals >= 3,
    }
    if target not in rules:
        raise ValueError(f"Cible inconnue: {target}")
    return int(rules[target])


def _wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = successes / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / den
    return max(0.0, center - half), min(1.0, center + half)


def _condition_value(features: dict, condition: dict) -> bool:
    value = features.get(condition["feature"])
    op, threshold = condition["op"], condition["value"]
    if op == "eq":
        return value == threshold
    if not _num(value):
        return False
    if op == "ge": return value >= threshold
    if op == "le": return value <= threshold
    if op == "gt": return value > threshold
    if op == "lt": return value < threshold
    if op == "between": return threshold[0] <= value <= threshold[1]
    return False


def scenario_matches(features: dict, scenario: dict) -> bool:
    return all(_condition_value(features, c) for c in scenario["conditions"])


def _feature_conditions(feature_rows: list[dict]) -> list[dict]:
    numeric = sorted({k for row in feature_rows for k, v in row.items()
                      if k not in {"match_id", "date", "league", "home_team", "away_team"} and _num(v)})
    conditions = []
    # League identity is an explicit categorical dimension, not an assumed numeric ranking.
    league_counts = Counter(str(row.get("league") or "INCONNUE") for row in feature_rows)
    for league, count in sorted(league_counts.items()):
        if count >= MIN_DISCOVERY_SUPPORT and count <= len(feature_rows) * 0.95:
            conditions.append({"feature": "league", "op": "eq", "value": league})
    for name in numeric:
        values = [row[name] for row in feature_rows if _num(row.get(name))]
        if len(values) < MIN_DISCOVERY_SUPPORT:
            continue
        # Fixed, interpretable thresholds plus quantiles of the discovery period only.
        thresholds = set(t for t in _THRESHOLDS if min(values) <= t <= max(values))
        ordered = sorted(values)
        for q in (0.2, 0.35, 0.5, 0.65, 0.8):
            thresholds.add(round(ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))], 3))
        for threshold in sorted(thresholds):
            for op in ("ge", "le"):
                conditions.append({"feature": name, "op": op, "value": threshold})
    return conditions


def _condition_mask(features: list[dict], condition: dict) -> int:
    """Masque de bits (un bit par match de découverte) des matchs qui vérifient la condition."""
    mask = 0
    for index, row in enumerate(features):
        if _condition_value(row, condition):
            mask |= 1 << index
    return mask


def _rule_conditions(*conditions: dict) -> list[dict]:
    return sorted(conditions, key=lambda c: (c["feature"], c["op"], str(c["value"])))


def discover_scenarios(records: list[dict], features_by_id: dict[str, dict] | None = None,
                       max_candidates: int = DEFAULT_MAX_CANDIDATES) -> list[dict]:
    """Découvre règles simples, paires et triplets avec support et budget explicites.

    Le budget (en scénarios = règle x cible) est réparti 40 % / 40 % / 20 %. Les règles simples
    sont prises en tourniquet sur toutes les variables ; les paires et triplets sont échantillonnés
    de façon déterministe (graine fixe) dans l'ensemble des conditions admissibles, jamais en
    tronquant un produit cartésien trié. Deux règles qui sélectionnent exactement les mêmes matchs
    de découverte ne comptent qu'une fois. Seuls les matchs de découverte sont lus."""
    if max_candidates < 1:
        return []
    rows = sorted(records, key=lambda r: (str(r["date"]), str(r["match_id"])))
    if features_by_id is None:
        features_by_id = {str(r["match_id"]): build_features(r) for r in rows}
    features = [features_by_id[str(r["match_id"])] for r in rows]
    n_rows = len(rows)
    max_support = n_rows * 0.95
    pool = []  # (condition, support, masque) ; une seule condition par ensemble de matchs
    seen_masks: set[int] = set()
    for condition in _feature_conditions(features):
        mask = _condition_mask(features, condition)
        support = mask.bit_count()
        if MIN_DISCOVERY_SUPPORT <= support <= max_support and mask not in seen_masks:
            seen_masks.add(mask)
            pool.append((condition, support, mask))
    pool.sort(key=lambda item: (abs(item[1] / max(1, n_rows) - 0.5),
                                item[0]["feature"], item[0]["op"], str(item[0]["value"])))
    if not pool:
        return []

    unary_budget = max(1, max_candidates * 4 // 10)
    pair_budget = max_candidates * 4 // 10
    triple_budget = max_candidates - unary_budget - pair_budget
    scenarios: list[dict] = []

    def add_rule(conditions: list[dict], support: int, complexity: int, limit: int, out: list[dict]) -> None:
        for target in TARGETS:
            if len(out) >= limit:
                return
            out.append({"scenario_id": _scenario_id(target, conditions), "target": target,
                        "conditions": conditions, "discovery_support": support, "complexity": complexity})

    # Règles simples : tourniquet sur les variables (ordre des variables mélangé par hachage),
    # les conditions de chaque variable allant de la plus équilibrée à la moins équilibrée.
    per_feature: dict[str, list[tuple[dict, int, int]]] = {}
    for item in pool:
        per_feature.setdefault(item[0]["feature"], []).append(item)
    feature_order = sorted(per_feature, key=lambda name: hashlib.sha256(f"{DISCOVERY_SEED}|{name}".encode()).hexdigest())
    unary: list[dict] = []
    rank = 0
    while len(unary) < unary_budget and any(len(per_feature[name]) > rank for name in feature_order):
        for name in feature_order:
            if len(per_feature[name]) > rank:
                condition, support, _mask = per_feature[name][rank]
                add_rule([condition], support, 1, unary_budget, unary)
            if len(unary) >= unary_budget:
                break
        rank += 1
    scenarios.extend(unary)
    if pair_budget <= 0 or len(pool) < 2:
        return scenarios[:max_candidates]

    rng = random.Random(DISCOVERY_SEED)
    accepted_masks: set[int] = set()
    pair_rules: list[tuple[list[dict], int, int]] = []
    pair_rows: list[dict] = []
    attempts, max_attempts = 0, 60 * max(1, pair_budget)
    while len(pair_rows) < pair_budget and attempts < max_attempts:
        attempts += 1
        (c1, _, m1), (c2, _, m2) = rng.choice(pool), rng.choice(pool)
        if c1["feature"] == c2["feature"]:
            continue
        mask = m1 & m2
        support = mask.bit_count()
        if support < MIN_DISCOVERY_SUPPORT or support > max_support or mask in accepted_masks or mask in seen_masks:
            continue
        accepted_masks.add(mask)
        conditions = _rule_conditions(c1, c2)
        pair_rules.append((conditions, support, mask))
        add_rule(conditions, support, 2, pair_budget, pair_rows)
    scenarios.extend(pair_rows)
    if triple_budget <= 0 or not pair_rules:
        return scenarios[:max_candidates]

    triple_rows: list[dict] = []
    attempts, max_attempts = 0, 60 * max(1, triple_budget)
    while len(triple_rows) < triple_budget and attempts < max_attempts:
        attempts += 1
        pair, _support, pair_mask = rng.choice(pair_rules)
        third, _s3, m3 = rng.choice(pool)
        if third["feature"] in {c["feature"] for c in pair}:
            continue
        mask = pair_mask & m3
        support = mask.bit_count()
        if support < MIN_DISCOVERY_SUPPORT or support > max_support or mask in accepted_masks or mask in seen_masks:
            continue
        accepted_masks.add(mask)
        add_rule(_rule_conditions(*pair, third), support, 3, triple_budget, triple_rows)
    scenarios.extend(triple_rows)
    return scenarios[:max_candidates]


def _scenario_id(target: str, conditions: list[dict]) -> str:
    payload = json.dumps({"target": target, "conditions": conditions}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _select_rows(scenario: dict, records: list[dict], features_by_id: dict[str, dict]) -> list[dict]:
    selected = []
    for row in records:
        f = features_by_id.get(str(row["match_id"]))
        if f and scenario_matches(f, scenario):
            selected.append(row)
    return selected


_ONE_X_TWO = {"home_win": "home_odds", "draw": "draw_odds", "away_win": "away_odds"}


def _market_probability(row: dict, target: str, odds: float) -> tuple[float, str]:
    """Probabilité implicite de la cote réelle. 1X2 : normalisée sans marge avec les trois cotes
    de CE match. Autres marchés : 1/cote brute, marge du bookmaker incluse (donc plus exigeante
    pour le scénario que la probabilité sans marge)."""
    if target in _ONE_X_TWO:
        trio = [row.get(k) for k in ("home_odds", "draw_odds", "away_odds")]
        if all(_num(x) and x > 1 for x in trio):
            return (1 / odds) / sum(1 / x for x in trio), "1x2_sans_marge"
    return 1 / odds, "brute_avec_marge"


def evaluate_scenario(scenario: dict, records: list[dict], features_by_id: dict[str, dict],
                      selected_rows: list[dict] | None = None, include_match_ids: bool = True) -> dict:
    rows = _select_rows(scenario, records, features_by_id) if selected_rows is None else selected_rows
    selected = [(row, outcome(row, scenario["target"])) for row in rows]
    n = len(selected)
    wins = sum(y for _, y in selected)
    lo, hi = _wilson(wins, n)
    result = {
        "scenario_id": scenario["scenario_id"], "target": scenario["target"],
        "conditions": scenario["conditions"], "complexity": scenario.get("complexity", len(scenario["conditions"])),
        "n": n, "wins": wins, "losses": n - wins,
        "hit_rate": wins / n if n else None, "wilson_95": [lo, hi],
        "leagues": len({str(r.get("league") or "INCONNUE") for r, _ in selected}),
    }
    if include_match_ids:
        result["match_ids"] = [str(r["match_id"]) for r, _ in selected]
    # Résultat économique uniquement avec la cote réelle de CETTE cible ; jamais de cote déduite
    # d'un autre marché. Mise plate de 1 : gain net = cote - 1, perte = -1.
    returns, odds_list, implied, odds_wins = [], [], [], 0
    basis = "aucune_cote"
    for row, won in selected:
        odds = (row.get("target_odds") or {}).get(scenario["target"])
        if _num(odds) and odds > 1:
            returns.append(float(odds) - 1 if won else -1.0)
            odds_list.append(float(odds))
            probability, basis = _market_probability(row, scenario["target"], float(odds))
            implied.append(probability)
            odds_wins += won
    k = len(returns)
    result["roi"] = sum(returns) / k if k else None
    result["roi_n"] = k
    result["settled_bets"] = k
    result["mean_odds"] = sum(odds_list) / k if k else None
    result["hit_rate_with_odds"] = odds_wins / k if k else None
    result["market_implied_rate"] = sum(implied) / k if k else None
    result["market_implied_basis"] = basis
    result["edge_vs_market"] = (odds_wins / k - sum(implied) / k) if k else None
    if k >= 2:
        mean = sum(returns) / k
        se = math.sqrt(sum((x - mean) ** 2 for x in returns) / (k - 1)) / math.sqrt(k)
        result["roi_ci95"] = [mean - 1.959963984540054 * se, mean + 1.959963984540054 * se]
    else:
        result["roi_ci95"] = None
    return result


def _split_chronologically(records: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """60/20/20 chronologique. Les deux coupures sont alignées sur des changements de date (le couple
    de frontières le plus proche des cibles) : aucun jour n'est partagé entre deux segments, sinon des résultats
    du jour servent à choisir des règles évaluées sur des matchs joués le même jour."""
    rows = sorted(records, key=lambda r: (str(r["date"]), str(r["match_id"])))
    if len(rows) < 5:
        return rows, [], []
    target_a, target_b = int(len(rows) * 0.60), int(len(rows) * 0.80)
    boundaries = [i for i in range(1, len(rows)) if str(rows[i]["date"])[:10] != str(rows[i - 1]["date"])[:10]]
    if len(boundaries) >= 2:
        a, b = min(((x, y) for x in boundaries for y in boundaries if y > x),
                   key=lambda pair: (abs(pair[0] - target_a) + abs(pair[1] - target_b), pair))
        return rows[:a], rows[a:b], rows[b:]
    # Moins de trois dates distinctes : découpe par rang, la fuite de jour est alors inévitable.
    a = max(1, target_a)
    b = min(max(a + 1, target_b), len(rows) - 1)
    return rows[:a], rows[a:b], rows[b:]


def _bh_adjust(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values, monotonically corrected."""
    n = len(p_values)
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted = [1.0] * n
    running = 1.0
    for rank_idx in range(n - 1, -1, -1):
        i = order[rank_idx]
        rank = rank_idx + 1
        running = min(running, p_values[i] * n / rank)
        adjusted[i] = min(1.0, running)
    return adjusted


def _binomial_p_approx(wins: int, n: int, baseline: float) -> float:
    """Approximation bilatérale normale; signal de tri uniquement, jamais preuve finale."""
    if n <= 0 or baseline <= 0 or baseline >= 1:
        return 1.0
    sd = math.sqrt(n * baseline * (1 - baseline))
    if sd == 0:
        return 1.0
    z = abs(wins - n * baseline) / sd
    # Abramowitz-Stegun approximation of two-sided normal tail.
    t = 1 / (1 + 0.2316419 * z)
    density = 0.3989422804014327 * math.exp(-z * z / 2)
    tail = density * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    return min(1.0, max(0.0, 2 * tail))


_DYNAMIC_MARKERS = ("after_", "bad_run", "recovery", "alternating", "streak")
_NON_FEATURE_KEYS = {"match_id", "date", "league", "home_team", "away_team"}


def _clean_records(records: list[dict]) -> tuple[list[dict], Counter]:
    """Validation structurelle + preuve pré-match + dédoublonnage, identiques pour toutes les entrées."""
    rejected: Counter = Counter()
    valid = []
    for row in records:
        ok, reason = validate_record(row)
        if ok:
            valid.append(row)
        else:
            rejected[reason] += 1
    clean, _dups, _conflicts, _shifted = _dedupe(valid, rejected)
    return clean, rejected


def _exploration_diagnostics(scenarios: list[dict], train_features: list[dict]) -> dict:
    """Ce qui a réellement été exploré, pour ne jamais confondre budget et couverture."""
    all_features = {k for row in train_features for k, v in row.items() if k not in _NON_FEATURE_KEYS and _num(v)}
    used_features = {c["feature"] for s in scenarios for c in s["conditions"]}
    by_complexity = {}
    for complexity in (1, 2, 3):
        group = [s for s in scenarios if s.get("complexity", 1) == complexity]
        rule_conditions = {json.dumps(s["conditions"], sort_keys=True): s["conditions"] for s in group}
        rules = set(rule_conditions)
        condition_counts = Counter(json.dumps(c, sort_keys=True) for conds in rule_conditions.values() for c in conds)
        rule_count = max(1, len(rules))
        by_complexity[str(complexity)] = {
            "scenarios": len(group), "distinct_rules": len(rules),
            "distinct_features": len({c["feature"] for s in group for c in s["conditions"]}),
            "most_used_condition_share_of_rules": (max(condition_counts.values()) / rule_count) if group else None,
        }
    dynamic_rules = {json.dumps(s["conditions"], sort_keys=True) for s in scenarios
                     if any(any(m in c["feature"] for m in _DYNAMIC_MARKERS) for c in s["conditions"])}
    return {
        "by_complexity": by_complexity,
        "numeric_features_available": len(all_features),
        "numeric_features_used_in_rules": len(used_features & all_features),
        "numeric_features_never_used": sorted(all_features - used_features),
        "rules_with_dynamic_feature": len(dynamic_rules),
        "note": "Échantillon déterministe et borné ; ce n'est pas l'exploration de toutes les combinaisons possibles.",
    }


def _compact(candidate: dict) -> dict:
    s, tr, va, te = candidate["scenario"], candidate["train"], candidate["validation"], candidate["test"]

    def part(r: dict) -> dict:
        return {k: r.get(k) for k in ("n", "hit_rate", "wilson_95", "settled_bets", "mean_odds", "roi", "roi_ci95",
                                      "market_implied_rate", "market_implied_basis", "edge_vs_market")}
    return {
        "scenario_id": s["scenario_id"], "target": s["target"], "complexity": s["complexity"],
        "conditions": s["conditions"], "q_bh_train": candidate["q_bh_approx"],
        "train": {"n": tr["n"], "hit_rate": tr["hit_rate"], "baseline": candidate["train_baseline"]},
        "validation": {**part(va), "baseline": candidate["validation_baseline"], "lift": candidate["validation_lift"]},
        "test": {**part(te), "baseline": candidate["test_baseline"], "lift": candidate["test_lift"]},
    }


def _test_outcome_stats(group: list[dict]) -> dict:
    """Résultats test d'un groupe de scénarios déjà choisis ; le test n'a servi à aucun choix."""
    measured = [c for c in group if c["test"]["n"] > 0 and c["test_lift"] is not None]
    lifts = [c["test_lift"] for c in measured]
    with_roi = [c for c in measured if c["test"]["settled_bets"] >= MIN_EVAL_SUPPORT and c["test"]["roi"] is not None]
    return {
        "scenarios": len(group), "with_test_matches": len(measured),
        "test_lift_positive": sum(x > 0 for x in lifts),
        "share_test_lift_positive": (sum(x > 0 for x in lifts) / len(lifts)) if lifts else None,
        "mean_test_lift": (sum(lifts) / len(lifts)) if lifts else None,
        "test_wilson_low_above_baseline": sum(
            1 for c in measured if c["test"]["wilson_95"][0] is not None and c["test"]["wilson_95"][0] > c["test_baseline"]),
        "with_min_settled_bets": len(with_roi),
        "roi_positive_with_min_settled_bets": sum(c["test"]["roi"] > 0 for c in with_roi),
        "roi_ci95_low_above_zero": sum(1 for c in with_roi if c["test"]["roi_ci95"] and c["test"]["roi_ci95"][0] > 0),
        "mean_roi_with_min_settled_bets": (sum(c["test"]["roi"] for c in with_roi) / len(with_roi)) if with_roi else None,
        "mean_edge_vs_market": (sum(c["test"]["edge_vs_market"] for c in with_roi) / len(with_roi)) if with_roi else None,
        "edge_vs_market_positive": sum(c["test"]["edge_vs_market"] > 0 for c in with_roi),
    }


def _uses_market_features(candidate: dict) -> bool:
    """Vrai si la règle lit une cote ou une probabilité de marché (information déjà dans le prix)."""
    return any(c["feature"].startswith("market_") or c["feature"].endswith("_odds")
               for c in candidate["scenario"]["conditions"])


def _selection_summary(candidates: list[dict], top: int = 20) -> dict:
    selected = [c for c in candidates if c["selected_on_validation"]]
    control = [c for c in candidates if c["status"] == "A_VALIDER" and not c["selected_on_validation"]]
    return {
        "criteria": dict(SELECTION_CRITERIA),
        "selected": len(selected),
        "distinct_rules": len({json.dumps(c["scenario"]["conditions"], sort_keys=True) for c in selected}),
        "by_target": dict(Counter(c["scenario"]["target"] for c in selected)),
        "selected_test": _test_outcome_stats(selected),
        "selected_with_market_features_test": _test_outcome_stats([c for c in selected if _uses_market_features(c)]),
        "selected_without_market_features_test": _test_outcome_stats([c for c in selected if not _uses_market_features(c)]),
        "control_not_selected_test": _test_outcome_stats(control),
        "top_by_validation_lift": [_compact(c) for c in selected[:top]],
        "interpretation": ("Un scénario sélectionné sur validation n'est prometteur que si son rendement test dépasse "
                           "nettement celui du groupe témoin ; sinon la sélection ne transmet aucune information."),
    }


def run_experiment(records: list[dict], max_candidates: int = DEFAULT_MAX_CANDIDATES,
                   detail_top: int = 200) -> dict:
    """Découverte train-only, choix sur validation, mesure finale sur test chronologique."""
    clean, rejected = _clean_records(records)
    train, validation, test = _split_chronologically(clean)
    feature_map = {str(r["match_id"]): build_features(r) for r in clean}
    scenarios = discover_scenarios(train, feature_map, max_candidates=max_candidates)
    split_baselines = {}
    for split_name, split_rows in (("train", train), ("validation", validation), ("test", test)):
        split_baselines[split_name] = {}
        for target in TARGETS:
            ys = [outcome(r, target) for r in split_rows]
            split_baselines[split_name][target] = sum(ys) / len(ys) if ys else None
    baseline_by_target = dict(split_baselines["train"])
    cache: dict[tuple[str, str], list[dict]] = {}

    def evaluate(s: dict, split_name: str, split_rows: list[dict], with_ids: bool = False) -> dict:
        key = (json.dumps(s["conditions"], sort_keys=True), split_name)
        if key not in cache:
            cache[key] = _select_rows(s, split_rows, feature_map)
        result = evaluate_scenario(s, split_rows, feature_map, selected_rows=cache[key], include_match_ids=with_ids)
        for repeated in ("scenario_id", "target", "conditions", "complexity"):
            result.pop(repeated, None)  # déjà portés par `scenario` ; évite de les répéter 3 fois par candidat
        return result

    scored = []
    pvals = []
    for s in scenarios:
        tr = evaluate(s, "train", train)
        if tr["n"] < MIN_DISCOVERY_SUPPORT or tr["hit_rate"] is None:
            continue
        base = baseline_by_target[s["target"]]
        p = _binomial_p_approx(tr["wins"], tr["n"], base) if base is not None else 1.0
        scored.append((s, tr, p))
        pvals.append(p)
    adjusted = _bh_adjust(pvals)
    candidates = []
    for (s, tr, p), q in zip(scored, adjusted):
        vr = evaluate(s, "validation", validation)
        te = evaluate(s, "test", test)
        base = baseline_by_target[s["target"]]
        eligible = (
            vr["n"] >= MIN_EVAL_SUPPORT and te["n"] >= MIN_EVAL_SUPPORT
            and vr["hit_rate"] is not None and te["hit_rate"] is not None
        )
        validation_base = split_baselines["validation"][s["target"]]
        test_base = split_baselines["test"][s["target"]]
        validation_lift = (vr["hit_rate"] - validation_base) if vr["hit_rate"] is not None and validation_base is not None else None
        # Sélection gelée : train + validation uniquement. Le test n'entre dans aucun critère.
        selected = bool(
            eligible and validation_lift is not None
            and q <= SELECTION_CRITERIA["train_q_bh_max"]
            and vr["n"] >= SELECTION_CRITERIA["validation_min_n"]
            and validation_lift > SELECTION_CRITERIA["validation_lift_min_exclusive"]
        )
        candidates.append({
            "scenario": s, "train": tr, "validation": vr, "test": te,
            "train_baseline": base,
            "validation_baseline": validation_base,
            "validation_lift": validation_lift,
            "test_baseline": test_base,
            "test_lift": (te["hit_rate"] - test_base) if te["hit_rate"] is not None and test_base is not None else None,
            "p_approx": p, "q_bh_approx": q,
            "status": "A_VALIDER" if eligible else "ECHANTILLON_INSUFFISANT",
            "selected_on_validation": selected,
            "promotion_allowed": False,
            "interpretation": "Exploratoire uniquement; la p-value est une approximation de tri, pas une preuve."
        })
    # Tri sur la validation seule, par écart au taux de base (et non par taux brut, qui favoriserait
    # les cibles banales comme « plus de 1,5 but »).
    candidates.sort(key=lambda c: (
        c["status"] != "A_VALIDER",
        -(c["validation_lift"] if c["validation_lift"] is not None else -1.0),
        -(c["validation"]["n"]),
        c["scenario"]["scenario_id"],
    ))
    # Les listes de matchs ne sont conservées que pour les meilleurs candidats : elles pèsent
    # ~20 Ko par candidat et rendaient le rapport inutilisable (108 Mo pour 5000 scénarios).
    for c in candidates[:detail_top]:
        for split_name, split_rows in (("train", train), ("validation", validation), ("test", test)):
            c[split_name]["match_ids"] = [str(r["match_id"]) for r in cache[(json.dumps(c["scenario"]["conditions"], sort_keys=True), split_name)]]
    digest_input = "\n".join(f'{r["match_id"]}|{r["date"]}|{r["home_goals"]}|{r["away_goals"]}' for r in clean)
    coverage = {
        "matches": len(clean),
        "home_history_available": sum(bool(feature_map[str(r["match_id"])].get("home_history_n", 0)) for r in clean),
        "away_history_available": sum(bool(feature_map[str(r["match_id"])].get("away_history_n", 0)) for r in clean),
        "both_ranks_available": sum("rank_gap" in feature_map[str(r["match_id"])] for r in clean),
        "head_to_head_available": sum(feature_map[str(r["match_id"])].get("h2h_n", 0) > 0 for r in clean),
        "full_1x2_odds_available": sum(all(_num(r.get(k)) and r[k] > 1 for k in ("home_odds", "draw_odds", "away_odds")) for r in clean),
        "target_odds_by_market": {target: sum(_num((r.get("target_odds") or {}).get(target)) and (r.get("target_odds") or {}).get(target) > 1 for r in clean) for target in TARGETS},
        "league_counts": dict(Counter(str(r.get("league") or "INCONNUE") for r in clean)),
    }

    def span(rows: list[dict]) -> dict:
        dates = sorted({str(r["date"])[:10] for r in rows})
        return {"first": dates[0] if dates else None, "last": dates[-1] if dates else None, "days": len(dates)}

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "EXPERIMENTAL_READ_ONLY",
        "dataset_sha256": hashlib.sha256(digest_input.encode()).hexdigest(),
        "coverage": coverage,
        "scenario_complexity_counts": dict(Counter(c["scenario"].get("complexity", 1) for c in candidates)),
        "exploration": _exploration_diagnostics(scenarios, [feature_map[str(r["match_id"])] for r in train]),
        "dataset": {"matches": len(clean), "rejected": dict(rejected),
                    "train_n": len(train), "validation_n": len(validation), "test_n": len(test),
                    "split_dates": {"train": span(train), "validation": span(validation), "test": span(test)},
                    "days_shared_between_splits": len(
                        ({str(r["date"])[:10] for r in train} & {str(r["date"])[:10] for r in validation})
                        | ({str(r["date"])[:10] for r in validation} & {str(r["date"])[:10] for r in test})
                        | ({str(r["date"])[:10] for r in train} & {str(r["date"])[:10] for r in test}))},
        "rules": {
            "strict_pre_match_history": True, "chronological_split": [0.60, 0.20, 0.20],
            "split_boundaries": "alignées sur un changement de date",
            "min_discovery_support": MIN_DISCOVERY_SUPPORT, "min_eval_support": MIN_EVAL_SUPPORT,
            "multiple_testing": "Benjamini-Hochberg; approximate p-values used for triage only",
            "auto_promotion": False, "production_changes": False,
        },
        "baseline_by_target": baseline_by_target,
        "baseline_by_split": split_baselines,
        "scenarios_tested": len(scenarios),
        "scenarios_with_minimum_train_support": len(scored),
        "selection": _selection_summary(candidates),
        "candidates": candidates,
    }


def _date_aligned_prefix(rows: list[dict], fraction: float) -> int:
    """Taille de préfixe la plus proche de `fraction`, terminée à une frontière de date."""
    boundaries = [i for i in range(1, len(rows)) if str(rows[i]["date"])[:10] != str(rows[i - 1]["date"])[:10]]
    boundaries.append(len(rows))
    target = int(len(rows) * fraction)
    return min(boundaries, key=lambda i: (abs(i - target), i))


def walk_forward(records: list[dict], fractions: tuple[float, ...] = (0.6, 0.8, 1.0),
                 max_candidates: int = DEFAULT_MAX_CANDIDATES) -> dict:
    """Validation chronologique glissante à origines croissantes. Chaque pli rejoue toute la chaîne
    (découverte, sélection gelée, test) sur le préfixe chronologique ; son test final est le dernier
    segment du préfixe, donc postérieur à tout ce qui a servi à choisir. Les tests des plis sont disjoints."""
    clean, _rejected = _clean_records(records)
    folds = []
    for fraction in fractions:
        prefix = clean[:_date_aligned_prefix(clean, fraction)]
        report = run_experiment(prefix, max_candidates=max_candidates, detail_top=0)
        _train, _validation, test = _split_chronologically(prefix)
        test_days = sorted({str(r["date"])[:10] for r in test})
        selection = report["selection"]
        folds.append({
            "fraction": fraction, "matches_in_prefix": len(prefix),
            "split": {k: report["dataset"][k] for k in ("train_n", "validation_n", "test_n")},
            "test_days": [test_days[0], test_days[-1]] if test_days else None,
            "selected": selection["selected"], "distinct_rules": selection["distinct_rules"],
            "selected_test": selection["selected_test"],
            "selected_without_market_features_test": selection["selected_without_market_features_test"],
            "control_not_selected_test": selection["control_not_selected_test"],
        })
    return {
        "mode": "WALK_FORWARD_EXPANDING", "fractions": list(fractions),
        "folds": folds,
        "note": "Peu de jours distincts : ces plis ne sont pas des saisons indépendantes ; lecture indicative uniquement.",
    }
