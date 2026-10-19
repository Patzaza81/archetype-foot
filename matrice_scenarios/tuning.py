"""Réglage orienté rentabilité de la matrice (isolé, lecture seule, rien n'est activé).

Principe anti-sur-apprentissage, fixé AVANT de regarder le test :
  - les règles sont découvertes sur le segment d'apprentissage seul ;
  - le réglage (choix des règles et de leur ordre de priorité) ne lit que apprentissage + validation ;
  - le segment de test n'est ouvert qu'une fois, pour mesurer ;
  - la même procédure est rejouée sur des scores permutés (nul « marché ») : le ROI du test n'a de valeur que s'il bat
    ce que la procédure obtient par hasard ;
  - les règles gelées sont ensuite évaluées sur une période et des cotes jamais vues (archive BetPawa).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from . import core
from .validation import Arena, _groups, cluster_bootstrap_mean, market_strata, p_value, permuted

ODDS_TARGETS = ("home_win", "draw", "away_win", "over_2_5", "under_2_5")
TUNING = {"min_settled_train": 60, "min_settled_validation": 40, "train_roi_min": 0.0, "validation_roi_min": 0.0,
          "score": "roi_validation - 1.28 * erreur_standard", "max_rules": 100}


def tune(arena: Arena, Y: np.ndarray) -> dict[str, Any]:
    """Sélectionne et ordonne les scénarios à partir d'apprentissage + validation uniquement."""
    from .validation import TARGETS
    allowed = np.array([TARGETS[t] in ODDS_TARGETS for t in arena.tgt_idx])
    tr, va = arena.table(Y, "train"), arena.table(Y, "validation")
    with np.errstate(invalid="ignore", divide="ignore"):
        se = np.where(va["settled"] > 1, va["roi"] / va["t_roi"], np.nan)  # erreur standard du ROI de validation
        se = np.abs(se)
        score = va["roi"] - 1.28 * se
        ok = (allowed & (tr["settled"] >= TUNING["min_settled_train"]) & (va["settled"] >= TUNING["min_settled_validation"])
              & (tr["roi"] > TUNING["train_roi_min"]) & (va["roi"] > TUNING["validation_roi_min"]) & np.isfinite(score))
    chosen = np.nonzero(ok)[0]
    chosen = chosen[np.argsort(-score[chosen], kind="stable")][: TUNING["max_rules"]]
    return {"chosen": chosen, "score": score}


def portfolio(arena: Arena, Y: np.ndarray, split: str, order: np.ndarray) -> dict[str, Any]:
    positions, picked = arena.pick_one_bet(order, split, require_odds=True)
    if len(positions) == 0:
        return {"picks": 0, "roi": None, "hit_rate": None, "mean_odds": None, "values": np.array([]), "days": np.array([])}
    p = arena.picks(Y, split, positions, picked)
    ok = np.isfinite(p["roi"])
    return {"picks": int(ok.sum()), "roi": float(np.mean(p["roi"][ok])), "hit_rate": float(np.mean(p["hit"][ok])),
            "mean_odds": float(np.mean(p["odds"][ok])), "values": p["roi"][ok], "days": p["day"][ok]}


def tuned_procedure(arena: Arena, Y: np.ndarray) -> dict[str, Any]:
    t = tune(arena, Y)
    out = portfolio(arena, Y, "test", t["chosen"])
    out["rules"] = len(t["chosen"])
    out["chosen"] = t["chosen"]
    return out


def null_distribution(arena: Arena, strata: np.ndarray, repetitions: int, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    groups = _groups(strata)
    rois, rules, picks = [], [], []
    for _ in range(repetitions):
        r = tuned_procedure(arena, permuted(arena.Y, groups, rng))
        rois.append(r["roi"] if r["roi"] is not None else np.nan)
        rules.append(r["rules"])
        picks.append(r["picks"])
    return {"roi": np.array(rois), "rules": np.array(rules), "picks": np.array(picks)}


def run_tuning(records: list[dict], *, max_candidates: int = core.DEFAULT_MAX_CANDIDATES, repetitions: int = 200, seed: int = 20261018) -> dict[str, Any]:
    """Réglage sur `records` (cotes de substitut), mesure unique sur le test, nul marché imbriqué."""
    clean, _ = core._clean_records(records)
    feature_map = {str(r["match_id"]): core.build_features(r) for r in clean}
    train, validation, test = core._split_chronologically(clean)
    scenarios = core.discover_scenarios(train, feature_map, max_candidates=max_candidates)
    arena = Arena(clean, feature_map, scenarios, {"train": train, "validation": validation, "test": test})
    observed = tuned_procedure(arena, arena.Y)
    strata = market_strata(clean, feature_map)
    null = null_distribution(arena, strata, repetitions, seed)
    finite = null["roi"][np.isfinite(null["roi"])]
    boot = cluster_bootstrap_mean(observed["values"], observed["days"]) if observed["picks"] else None
    chosen = [arena.scenarios[k] for k in observed["chosen"]]
    return {
        "split": {"train": len(train), "validation": len(validation), "test": len(test),
                  "train_last_day": train[-1]["date"], "validation_last_day": validation[-1]["date"],
                  "test_first_day": test[0]["date"], "test_last_day": test[-1]["date"]},
        "tuning": TUNING, "scenarios_tested": len(scenarios), "rules_selected": observed["rules"],
        "test": {"picks": observed["picks"], "roi": observed["roi"], "hit_rate": observed["hit_rate"], "mean_odds": observed["mean_odds"], "bootstrap_by_day": boot},
        "null_market": {"draws": int(len(finite)), "mean_roi": float(finite.mean()) if len(finite) else None,
                        "p95_roi": float(np.percentile(finite, 95)) if len(finite) else None,
                        "p": p_value(observed["roi"], finite) if (observed["roi"] is not None and len(finite)) else None},
        "chosen": [{"conditions": s["conditions"], "target": s["target"]} for s in chosen],
    }


def evaluate_tuned_on(chosen: list[dict], records: list[dict]) -> dict[str, Any]:
    """Règles réglées (ordre = priorité) évaluées sur des données jamais vues, aux cotes archivées de ces données."""
    clean, _ = core._clean_records(records)
    feature_map = {str(r["match_id"]): core.build_features(r) for r in clean}
    arena = Arena(clean, feature_map, chosen, {"all": clean})
    out = portfolio(arena, arena.Y, "all", np.arange(len(chosen)))
    boot = cluster_bootstrap_mean(out["values"], out["days"]) if out["picks"] else None
    by_target: dict[str, int] = {}
    if out["picks"]:
        positions, picked = arena.pick_one_bet(np.arange(len(chosen)), "all", require_odds=True)
        from .validation import TARGETS
        for k in picked:
            name = TARGETS[arena.tgt_idx[k]]
            by_target[name] = by_target.get(name, 0) + 1
    return {"matches": len(clean), "picks": out["picks"], "roi": out["roi"], "hit_rate": out["hit_rate"], "mean_odds": out["mean_odds"],
            "bootstrap_by_day": boot, "picks_by_target": by_target, "first_day": clean[0]["date"], "last_day": clean[-1]["date"]}
