"""Découverte contrôlée de scénarios prédictifs sur données pré-match normalisées.

Aucune dépendance tierce. Ce module ne modifie aucun moteur ni donnée de production.
Chaque enregistrement est un match unique avec score final et informations disponibles
avant le coup d'envoi. Les historiques d'équipes doivent contenir des matchs datés.
"""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
TARGETS = (
    "home_not_lose", "away_not_lose", "home_win", "away_win", "draw",
    "home_scores_1plus", "home_scores_2plus", "home_scores_3plus",
    "away_scores_1plus", "away_scores_2plus", "away_scores_3plus",
    "both_score", "under_2_5", "under_3_5", "over_1_5", "over_2_5",
)
WINDOWS = (2, 3, 5, 8, 10)
MIN_DISCOVERY_SUPPORT = 30
MIN_EVAL_SUPPORT = 15
DEFAULT_MAX_CANDIDATES = 5000
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
    return {
        "match_id": item.get("match_id"), "date": item.get("date"),
        "league": item.get("competition") or item.get("competition_brute"),
        "home_team": item.get("domicile"), "away_team": item.get("exterieur"),
        "home_goals": hg, "away_goals": ag,
        "home_rank": home.get("rang"), "away_rank": away.get("rang"),
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
    by_id: dict[str, list[dict]] = {}
    for row in payload:
        ok, reason = validate_record(row)
        if not ok:
            rejected[reason] += 1
            continue
        by_id.setdefault(str(row["match_id"]), []).append(row)
    rows = []
    conflicts = 0
    duplicates = 0
    for mid, versions in by_id.items():
        if len(versions) > 1:
            duplicates += len(versions) - 1
            signatures = {(v["date"], v["home_team"], v["away_team"], v["home_goals"], v["away_goals"]) for v in versions}
            if len(signatures) > 1:
                conflicts += 1
                rejected["DOUBLON_CONTRADICTOIRE"] += len(versions)
                continue
        rows.append(versions[0])
    rows.sort(key=lambda r: (str(r["date"]), str(r["match_id"])))
    return rows, {
        "input_rows": len(payload), "unique_matches": len(rows),
        "duplicate_rows": duplicates, "conflicting_match_ids": conflicts,
        "archive_unresolved_or_missing_score": archive_unresolved,
        "rejected": dict(rejected),
    }

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


def discover_scenarios(records: list[dict], features_by_id: dict[str, dict] | None = None,
                       max_candidates: int = DEFAULT_MAX_CANDIDATES) -> list[dict]:
    """Découvre règles simples, paires et triplets avec support et budget explicites."""
    if max_candidates < 1:
        return []
    rows = sorted(records, key=lambda r: (str(r["date"]), str(r["match_id"])))
    if features_by_id is None:
        features_by_id = {str(r["match_id"]): build_features(r) for r in rows}
    features = [features_by_id[str(r["match_id"])] for r in rows]
    atomic = _feature_conditions(features)
    eligible = []
    for condition in atomic:
        support = sum(_condition_value(f, condition) for f in features)
        if MIN_DISCOVERY_SUPPORT <= support <= len(rows) * 0.95:
            eligible.append((condition, support))
    eligible.sort(key=lambda item: (
        abs(item[1] / max(1, len(rows)) - 0.5),
        item[0]["feature"], item[0]["op"], str(item[0]["value"])
    ))
    if not eligible:
        return []

    unary_budget = max(1, max_candidates * 4 // 10)
    pair_budget = max_candidates * 4 // 10
    triple_budget = max_candidates - unary_budget - pair_budget
    scenarios = []
    for condition, support in eligible:
        for target in TARGETS:
            scenarios.append({
                "scenario_id": _scenario_id(target, [condition]), "target": target,
                "conditions": [condition], "discovery_support": support, "complexity": 1,
            })
            if len(scenarios) >= unary_budget:
                break
        if len(scenarios) >= unary_budget:
            break
    if pair_budget <= 0 or len(eligible) < 2:
        return scenarios[:max_candidates]

    pair_conditions = []
    pair_rules = []
    seen_pairs = set()
    for (c1, _), (c2, _) in itertools.combinations(eligible, 2):
        if c1["feature"] == c2["feature"]:
            continue
        conditions = sorted([c1, c2], key=lambda c: (c["feature"], c["op"], str(c["value"])))
        key = tuple(json.dumps(c, sort_keys=True) for c in conditions)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        support = sum(all(_condition_value(f, cond) for cond in conditions) for f in features)
        if support < MIN_DISCOVERY_SUPPORT or support > len(rows) * 0.95:
            continue
        pair_conditions.append((conditions, support))
        for target in TARGETS:
            pair_rules.append({
                "scenario_id": _scenario_id(target, conditions), "target": target,
                "conditions": conditions, "discovery_support": support, "complexity": 2,
            })
            if len(pair_rules) >= pair_budget:
                break
        if len(pair_rules) >= pair_budget:
            break
    scenarios.extend(pair_rules)
    if triple_budget <= 0 or not pair_conditions:
        return scenarios[:max_candidates]

    triple_rules = []
    seen_triples = set()
    # Bounded, deterministic extension of supported pairs; no exhaustive Cartesian product.
    for pair, _pair_support in pair_conditions:
        used = {c["feature"] for c in pair}
        for third, _ in eligible:
            if third["feature"] in used:
                continue
            conditions = sorted(pair + [third], key=lambda c: (c["feature"], c["op"], str(c["value"])))
            key = tuple(json.dumps(c, sort_keys=True) for c in conditions)
            if key in seen_triples:
                continue
            seen_triples.add(key)
            support = sum(all(_condition_value(f, cond) for cond in conditions) for f in features)
            if support < MIN_DISCOVERY_SUPPORT or support > len(rows) * 0.95:
                continue
            for target in TARGETS:
                triple_rules.append({
                    "scenario_id": _scenario_id(target, conditions), "target": target,
                    "conditions": conditions, "discovery_support": support, "complexity": 3,
                })
                if len(triple_rules) >= triple_budget:
                    break
            if len(triple_rules) >= triple_budget:
                break
        if len(triple_rules) >= triple_budget:
            break
    scenarios.extend(triple_rules)
    return scenarios[:max_candidates]

def _scenario_id(target: str, conditions: list[dict]) -> str:
    payload = json.dumps({"target": target, "conditions": conditions}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def evaluate_scenario(scenario: dict, records: list[dict], features_by_id: dict[str, dict]) -> dict:
    selected = []
    for row in records:
        f = features_by_id.get(str(row["match_id"]))
        if f and scenario_matches(f, scenario):
            selected.append((row, outcome(row, scenario["target"])))
    n = len(selected)
    wins = sum(y for _, y in selected)
    lo, hi = _wilson(wins, n)
    result = {
        "scenario_id": scenario["scenario_id"], "target": scenario["target"],
        "conditions": scenario["conditions"], "complexity": scenario.get("complexity", len(scenario["conditions"])),
        "n": n, "wins": wins, "losses": n - wins,
        "hit_rate": wins / n if n else None, "wilson_95": [lo, hi],
        "leagues": len({str(r.get("league") or "INCONNUE") for r, _ in selected}),
        "match_ids": [str(r["match_id"]) for r, _ in selected],
    }
    # Economic result only when an odds field explicitly corresponds to this target.
    # Never derive/invent an odds price from an unrelated market.
    returns = []
    for row, won in selected:
        odds = (row.get("target_odds") or {}).get(scenario["target"])
        if _num(odds) and odds > 1:
            returns.append(float(odds) - 1 if won else -1.0)
    result["roi"] = sum(returns) / len(returns) if returns else None
    result["roi_n"] = len(returns)
    return result


def _split_chronologically(records: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    rows = sorted(records, key=lambda r: (str(r["date"]), str(r["match_id"])))
    if len(rows) < 5:
        return rows, [], []
    a = max(1, int(len(rows) * 0.60))
    b = max(a + 1, int(len(rows) * 0.80))
    b = min(b, len(rows) - 1)
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


def run_experiment(records: list[dict], max_candidates: int = DEFAULT_MAX_CANDIDATES) -> dict:
    """Découverte train-only, choix sur validation, mesure finale sur test chronologique."""
    valid = []
    rejected = Counter()
    for row in records:
        ok, reason = validate_record(row)
        if ok: valid.append(row)
        else: rejected[reason] += 1
    # Reuse loader's duplicate policy for in-memory inputs too.
    by_id: dict[str, list[dict]] = {}
    for r in valid: by_id.setdefault(str(r["match_id"]), []).append(r)
    clean = []
    for mid, versions in by_id.items():
        sig = {(v["date"], v["home_team"], v["away_team"], v["home_goals"], v["away_goals"]) for v in versions}
        if len(sig) > 1:
            rejected["DOUBLON_CONTRADICTOIRE"] += len(versions)
        else:
            clean.append(versions[0])
    clean.sort(key=lambda r: (str(r["date"]), str(r["match_id"])))
    train, validation, test = _split_chronologically(clean)
    feature_map = {str(r["match_id"]): build_features(r) for r in clean}
    scenarios = discover_scenarios(train, feature_map, max_candidates=max_candidates)
    baseline_by_target = {}
    split_baselines = {}
    for split_name, split_rows in (("train", train), ("validation", validation), ("test", test)):
        split_baselines[split_name] = {}
        for target in TARGETS:
            ys = [outcome(r, target) for r in split_rows]
            split_baselines[split_name][target] = sum(ys) / len(ys) if ys else None
            if split_name == "train":
                baseline_by_target[target] = split_baselines[split_name][target]
    scored = []
    pvals = []
    for s in scenarios:
        tr = evaluate_scenario(s, train, feature_map)
        if tr["n"] < MIN_DISCOVERY_SUPPORT or tr["hit_rate"] is None:
            continue
        base = baseline_by_target[s["target"]]
        p = _binomial_p_approx(tr["wins"], tr["n"], base) if base is not None else 1.0
        scored.append((s, tr, p))
        pvals.append(p)
    adjusted = _bh_adjust(pvals)
    candidates = []
    for (s, tr, p), q in zip(scored, adjusted):
        vr = evaluate_scenario(s, validation, feature_map)
        te = evaluate_scenario(s, test, feature_map)
        base = baseline_by_target[s["target"]]
        eligible = (
            vr["n"] >= MIN_EVAL_SUPPORT and te["n"] >= MIN_EVAL_SUPPORT
            and vr["hit_rate"] is not None and te["hit_rate"] is not None
        )
        validation_base = split_baselines["validation"][s["target"]]
        test_base = split_baselines["test"][s["target"]]
        candidates.append({
            "scenario": s, "train": tr, "validation": vr, "test": te,
            "train_baseline": base,
            "validation_baseline": validation_base,
            "validation_lift": (vr["hit_rate"] - validation_base) if vr["hit_rate"] is not None and validation_base is not None else None,
            "test_baseline": test_base,
            "test_lift": (te["hit_rate"] - test_base) if te["hit_rate"] is not None and test_base is not None else None,
            "p_approx": p, "q_bh_approx": q,
            "status": "A_VALIDER" if eligible else "ECHANTILLON_INSUFFISANT",
            "promotion_allowed": False,
            "interpretation": "Exploratoire uniquement; la p-value est une approximation de tri, pas une preuve."
        })
    candidates.sort(key=lambda c: (
        c["status"] != "A_VALIDER",
        -(c["validation"]["hit_rate"] or 0),
        -(c["validation"]["n"]),
        c["scenario"]["scenario_id"],
    ))
    digest_input = "\n".join(f'{r["match_id"]}|{r["date"]}|{r["home_goals"]}|{r["away_goals"]}' for r in clean)
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "EXPERIMENTAL_READ_ONLY",
        "dataset_sha256": hashlib.sha256(digest_input.encode()).hexdigest(),
        "dataset": {"matches": len(clean), "rejected": dict(rejected),
                    "train_n": len(train), "validation_n": len(validation), "test_n": len(test)},
        "rules": {
            "strict_pre_match_history": True, "chronological_split": [0.60, 0.20, 0.20],
            "min_discovery_support": MIN_DISCOVERY_SUPPORT, "min_eval_support": MIN_EVAL_SUPPORT,
            "multiple_testing": "Benjamini-Hochberg; approximate p-values used for triage only",
            "auto_promotion": False, "production_changes": False,
        },
        "baseline_by_target": baseline_by_target,
        "baseline_by_split": split_baselines,
        "scenarios_tested": len(scenarios),
        "scenarios_with_minimum_train_support": len(scored),
        "candidates": candidates,
    }
