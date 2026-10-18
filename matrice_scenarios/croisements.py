"""Test des « croisements » (ce que l'équipe produit contre ce que l'adversaire concède, au même lieu).

Famille PETITE et FIXÉE D'AVANCE (8 marchés, une formule chacun, K derniers matchs au même lieu) : peu d'hypothèses = peu de bruit
de sélection. Le seuil (top 20 % du score) est calculé sur la première partie des dates seulement ; la mesure se fait sur la suite.
Lecture seule, aucune règle activée.
"""
from __future__ import annotations

import math
from typing import Any

from . import core

K = 5
MIN_SAME_VENUE = 4
TOP_SHARE = 0.20
TRAIN_SHARE = 0.60


def _last_same_venue(history: list[dict], venue: str, day: str) -> list[dict]:
    rows = [h for h in history if h.get("venue") == venue and str(h.get("date"))[:10] < day]
    rows.sort(key=lambda h: str(h["date"]))
    return rows[-K:]


def _stats(rows: list[dict]) -> dict[str, float]:
    n = len(rows)
    return {"scored": sum(h["goals_for"] >= 1 for h in rows) / n, "conceded": sum(h["goals_against"] >= 1 for h in rows) / n,
            "gf": sum(h["goals_for"] for h in rows) / n, "ga": sum(h["goals_against"] for h in rows) / n}


def scores(record: dict) -> dict[str, float] | None:
    day = str(record["date"])[:10]
    h = _last_same_venue(record.get("home_history") or [], "home", day)
    a = _last_same_venue(record.get("away_history") or [], "away", day)
    if len(h) < MIN_SAME_VENUE or len(a) < MIN_SAME_VENUE:
        return None
    hs, as_ = _stats(h), _stats(a)
    diff = (hs["gf"] - hs["ga"]) - (as_["gf"] - as_["ga"])
    total = (hs["gf"] + hs["ga"] + as_["gf"] + as_["ga"]) / 2
    return {
        "home_scores_1plus": hs["scored"] + as_["conceded"],
        "away_scores_1plus": as_["scored"] + hs["conceded"],
        "both_score": min(hs["scored"], as_["conceded"]) + min(as_["scored"], hs["conceded"]),
        "over_2_5": total, "under_2_5": -total,
        "home_win": diff, "away_win": -diff, "draw": -abs(diff),
    }


MARKETS = ("home_scores_1plus", "away_scores_1plus", "both_score", "over_2_5", "under_2_5", "home_win", "away_win", "draw")


def wilson(wins: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    z, p = 1.96, wins / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [(c - m) / d, (c + m) / d]


def evaluate(records: list[dict]) -> dict[str, Any]:
    rows = []
    for r in sorted(records, key=lambda x: str(x["date"])):
        s = scores(r)
        if s is not None:
            rows.append((r, s))
    cut_day = str(rows[int(len(rows) * TRAIN_SHARE)][0]["date"])[:10]
    train = [x for x in rows if str(x[0]["date"])[:10] < cut_day]
    test = [x for x in rows if str(x[0]["date"])[:10] >= cut_day]
    out: dict[str, Any] = {"matches_with_history": len(rows), "train": len(train), "test": len(test), "test_first_day": cut_day, "markets": {}}
    for m in MARKETS:
        values = sorted(s[m] for _, s in train)
        threshold = values[int(len(values) * (1 - TOP_SHARE))]
        picked = [(r, s) for r, s in test if s[m] >= threshold]
        base_all = sum(core.outcome(r, m) for r, _ in test) / len(test)
        wins = sum(core.outcome(r, m) for r, _ in picked)
        n = len(picked)
        entry: dict[str, Any] = {"threshold": round(threshold, 4), "picks": n, "hit_rate": round(wins / n, 4) if n else None,
                                 "base_rate_test": round(base_all, 4), "hit_ci95": [round(x, 4) for x in wilson(wins, n) or []],
                                 "breakeven_odds": round(n / wins, 3) if wins else None}
        odds = [(r["target_odds"].get(m), core.outcome(r, m)) for r, _ in picked if (r.get("target_odds") or {}).get(m)]
        if odds:
            pnl = [o * y - 1 for o, y in odds]
            entry["with_odds"] = {"bets": len(odds), "mean_odds": round(sum(o for o, _ in odds) / len(odds), 3), "roi": round(sum(pnl) / len(pnl), 4)}
            sd = (sum((x - sum(pnl) / len(pnl)) ** 2 for x in pnl) / max(1, len(pnl) - 1)) ** 0.5
            entry["with_odds"]["roi_ci95_naif"] = [round(sum(pnl) / len(pnl) - 1.96 * sd / len(pnl) ** 0.5, 4), round(sum(pnl) / len(pnl) + 1.96 * sd / len(pnl) ** 0.5, 4)]
        out["markets"][m] = entry
    return out
