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
    return (sum(recent) + prior_n * prior_mean) / (len(recent) + prior_n)


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
    history: list[MatchResult] = []
    predictions = []
    for match in ordered:
        predictions.append(predict_one(history, match, window=window,
                                        prior_matches=prior_matches, max_goals=max_goals))
        history.append(match)
    return predictions
