"""League-specific walk-forward Poisson baseline for 1X2 and total 2.5.

Every forecast uses only matches strictly earlier than the target match date.
This is a baseline to challenge, not a fixed final model; hyperparameters must
be selected on earlier chronological folds and tested on a later untouched fold.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import exp, factorial
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MatchResult:
    event_id: str
    date: str
    competition: str
    home: str
    away: str
    home_goals: int
    away_goals: int


def _poisson(lam: float, cap: int) -> list[float]:
    p = [exp(-lam)]
    for k in range(1, cap + 1):
        p.append(p[-1] * lam / k)
    # Fold the tiny omitted tail into the last score bucket.
    p[-1] += max(0.0, 1.0 - sum(p))
    return p


def _shrunk_average(values: list[int], prior_mean: float, prior_n: float, window: int) -> float:
    recent = values[-window:]
    denominator = len(recent) + prior_n
    return (sum(recent) + prior_n * prior_mean) / denominator if denominator > 0 else prior_mean


def predict_one(history: list[MatchResult], target: MatchResult, *, window: int = 8,
                prior_matches: float = 4.0, max_goals: int = 10) -> dict:
    """Estimate score rates from same-competition history; no cross-league pooling."""
    past = [m for m in history if m.competition == target.competition and m.date < target.date]
    if not past:
        return {"event_id": target.event_id, "date": target.date, "competition": target.competition,
                "n_league": 0, "lambda_home": None, "lambda_away": None,
                "probabilities": None, "status": "no_prior_league_data"}
    mu_h = sum(m.home_goals for m in past) / len(past)
    mu_a = sum(m.away_goals for m in past) / len(past)
    mu_h = max(mu_h, 0.05); mu_a = max(mu_a, 0.05)

    def team_values(team: str, venue: str, field: str) -> list[int]:
        if venue == "home":
            vals = [m.home_goals if field == "for" else m.away_goals for m in past if m.home == team]
        else:
            vals = [m.away_goals if field == "for" else m.home_goals for m in past if m.away == team]
        return vals

    h_for = _shrunk_average(team_values(target.home, "home", "for"), mu_h, prior_matches, window)
    h_against = _shrunk_average(team_values(target.home, "home", "against"), mu_a, prior_matches, window)
    a_for = _shrunk_average(team_values(target.away, "away", "for"), mu_a, prior_matches, window)
    a_against = _shrunk_average(team_values(target.away, "away", "against"), mu_h, prior_matches, window)

    attack_home = h_for / mu_h
    defence_away = a_against / mu_h
    attack_away = a_for / mu_a
    defence_home = h_against / mu_a
    lam_h = max(0.05, min(5.0, mu_h * attack_home * defence_away))
    lam_a = max(0.05, min(5.0, mu_a * attack_away * defence_home))

    ph, pa = _poisson(lam_h, max_goals), _poisson(lam_a, max_goals)
    p_home = p_draw = p_away = p_over = 0.0
    for hg, hp in enumerate(ph):
        for ag, ap in enumerate(pa):
            p = hp * ap
            if hg > ag: p_home += p
            elif hg == ag: p_draw += p
            else: p_away += p
            if hg + ag >= 3: p_over += p
    return {
        "event_id": target.event_id, "date": target.date, "competition": target.competition,
        "n_league": len(past), "lambda_home": lam_h, "lambda_away": lam_a,
        "probabilities": {"H": p_home, "D": p_draw, "A": p_away,
                          "over_2_5": p_over, "under_2_5": 1.0-p_over},
        "status": "forecast",
    }


def walk_forward(matches: Iterable[MatchResult], *, window: int = 8,
                 prior_matches: float = 4.0, max_goals: int = 10) -> list[dict]:
    ordered = sorted(matches, key=lambda m: (m.date, m.competition, m.event_id))
    history_by_league: dict[str, list[MatchResult]] = defaultdict(list)
    predictions = []
    for match in ordered:
        history = history_by_league[match.competition]
        predictions.append(predict_one(history, match, window=window,
                                        prior_matches=prior_matches, max_goals=max_goals))
        history.append(match)
    return predictions


def tune_parameters(matches: Iterable[MatchResult], *, train_end: str,
                    windows: tuple[int, ...] = (4, 6, 8, 12),
                    priors: tuple[float, ...] = (0.0, 2.0, 4.0, 8.0),
                    min_training_forecasts: int = 30) -> dict:
    """Choose window/shrinkage only from walk-forward forecasts before train_end."""
    ordered = sorted(matches, key=lambda m: (m.date, m.competition, m.event_id))
    training_matches = [m for m in ordered if m.date < train_end]
    outcomes = {m.event_id: m for m in training_matches}
    candidates = []
    for window in windows:
        for prior in priors:
            preds = walk_forward(training_matches, window=window, prior_matches=prior)
            losses_by_comp: dict[str, list[float]] = defaultdict(list)
            for p in preds:
                m = outcomes.get(p["event_id"])
                probs = p.get("probabilities")
                if m is None or probs is None:
                    continue
                actual = "H" if m.home_goals > m.away_goals else "A" if m.home_goals < m.away_goals else "D"
                loss_1x2 = sum((probs[s] - (1.0 if s == actual else 0.0))**2 for s in ("H", "D", "A")) / 3.0
                actual_over = 1.0 if m.home_goals + m.away_goals >= 3 else 0.0
                loss_total = (probs["over_2_5"] - actual_over)**2
                losses_by_comp[m.competition].append(0.5 * (loss_1x2 + loss_total))
            n = sum(len(v) for v in losses_by_comp.values())
            macro_scores = [sum(v)/len(v) for v in losses_by_comp.values() if v]
            score = sum(macro_scores)/len(macro_scores) if macro_scores else None
            candidates.append({"window": window, "prior_matches": prior, "n": n,
                               "competitions": len(macro_scores), "macro_brier_composite": score})
    eligible = [x for x in candidates if x["n"] >= min_training_forecasts and x["macro_brier_composite"] is not None]
    if not eligible:
        return {"selected": {"window": 8, "prior_matches": 4.0}, "status": "fallback_insufficient_training_history",
                "train_end_exclusive": train_end, "candidates": candidates}
    best = min(eligible, key=lambda x: (x["macro_brier_composite"], x["window"], x["prior_matches"]))
    return {"selected": {"window": best["window"], "prior_matches": best["prior_matches"]},
            "status": "selected_on_training_only", "train_end_exclusive": train_end,
            "objective": "macro-average by competition of 1X2 and total-2.5 Brier; no league-volume domination",
            "candidates": candidates}
