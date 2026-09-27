
from __future__ import annotations

from typing import Any, Mapping

from .calibration import IsotonicCalibrator
from .markets import derive_markets, pairwise_joint_probability
from .model import build_model
from .risk import goal_context_dispersion
from .value import evaluate
from .decision import decide


def _validate_snapshot(snapshot: Mapping[str, Any] | None):
    if snapshot is None:
        return
    if snapshot.get("capture") != "nightly_run":
        raise ValueError("COTE_SNAPSHOT_CAPTURE_INVALIDE")
    if not snapshot.get("timestamp"):
        raise ValueError("COTE_SNAPSHOT_SANS_TIMESTAMP")
    if snapshot.get("source") != "BetPawa":
        raise ValueError("COTE_SNAPSHOT_SOURCE_INVALIDE")


def evaluate_match(
    match: Mapping[str, Any],
    *,
    calibrator: IsotonicCalibrator | None = None,
    evidence: Mapping[str, Mapping[str, Any]] | None = None,
):
    """Évalue un match sans toucher au pipeline.

    Le dictionnaire match contient les historiques, les cotes observées et les
    paramètres strictement nécessaires au moteur.
    """
    _validate_snapshot(match.get("odds_snapshot"))

    model = build_model(
        match.get("home_matches", ()),
        match.get("away_matches", ()),
        previous_home_matches=match.get("previous_home_matches", ()),
        previous_away_matches=match.get("previous_away_matches", ()),
        season_progress=float(match.get("season_progress", 1.0)),
        previous_context_compatible=bool(match.get("previous_context_compatible", True)),
    )

    markets = derive_markets(model, match.get("handicap_lines", ()))
    odds = match.get("odds", {})
    raw_values = {}
    candidates = []

    for market, probability in markets.items():
        if market not in odds:
            continue
        calibration = calibrator.predict(probability) if calibrator is not None else None
        dispersion = goal_context_dispersion(
            list(match.get("home_matches", ())) + list(match.get("away_matches", ()))
        )

        value = evaluate(
            market, probability, float(odds[market]),
            calibrated_probability=calibration,
            dispersion=dispersion,
        )
        raw_values[market] = value

        ev = (evidence or {}).get(market, {})
        candidates.append({
            "market": market,
            "probability": value.probability,
            "odds": value.odds,
            "edge": value.edge,
            "edv": value.edv,
            "eligible": value.eligible,
            "calibrated": calibration is not None,
            "n_relevant": min(model.home_sample.current_n, model.away_sample.current_n),
            "family": ev.get("family", market.split("_", 1)[0]),
            "exposure_group": ev.get("exposure_group", market.split("_", 1)[0]),
            "double_control_ok": ev.get("double_control_ok", False),
            "justification": ev.get("justification"),
            "conflicts_with": ev.get("conflicts_with", ()),
            "joint_probability": {**joint_full_time, **ev.get("joint_probability", {})},
            "reliability": ev.get("reliability", 0),
        })

    selected, rejected, conflicts = decide(candidates)

    return {
        "model": model,
        "probabilities_raw": markets,
        "values": raw_values,
        "candidates": candidates,
        "selected": selected,
        "rejected": rejected,
        "correlation_conflicts": conflicts,
        "diagnostics": {
            "competition_ignored": True,
            "h2h_used": False,
            "sample_gate": {
                "home_n": model.home_sample.current_n,
                "away_n": model.away_sample.current_n,
                "selection_possible": min(
                    model.home_sample.current_n, model.away_sample.current_n
                ) >= 3,
            },
        },
    }
