from __future__ import annotations

from typing import Any, Mapping

from moteur_v3.calibration import IsotonicCalibrator
from moteur_v3.decision import decide
from moteur_v3.markets import derive_markets, pairwise_joint_probability
from moteur_v3.risk import goal_context_dispersion
from moteur_v3.value import evaluate

from .model import build_model_europe, derniers
from .performance import indice_performance_europe


def evaluate_match_europe(match: Mapping[str, Any], *, calibrator: IsotonicCalibrator | None = None,
                          evidence: Mapping[str, Mapping[str, Any]] | None = None):
    """Évalue un match européen. `match` : europe_dom, europe_ext, ligue_dom, ligue_ext (listes de matchs au format V3),
    odds, handicap_lines. Même chaîne que moteur_v3.core.evaluate_match : value, calibration, double contrôle,
    justification, dispersion, une sélection par exposition, 3 au maximum. Ne touche ni V2 ni V3."""
    eu_d, eu_e = match.get("europe_dom", ()), match.get("europe_ext", ())
    lg_d, lg_e = match.get("ligue_dom", ()), match.get("ligue_ext", ())
    model = build_model_europe(eu_d, eu_e, lg_d, lg_e)

    markets = derive_markets(model, match.get("handicap_lines", ()))
    odds = match.get("odds", {})
    joint = pairwise_joint_probability([m for m in markets if m in odds], model.score)
    utilises = derniers(eu_d, True) + derniers(lg_d, True) + derniers(eu_e, False) + derniers(lg_e, False)
    dispersion = goal_context_dispersion(utilises)

    raw_values, candidates = {}, []
    for market, probability in markets.items():
        if market not in odds:
            continue
        calibration = calibrator.predict(probability) if calibrator is not None else None
        value = evaluate(market, probability, float(odds[market]), calibrated_probability=calibration,
                         dispersion=dispersion)
        raw_values[market] = value
        ev = (evidence or {}).get(market, {})
        candidates.append({
            "market": market, "probability": value.probability, "odds": value.odds, "edge": value.edge,
            "edv": value.edv, "eligible": value.eligible, "calibrated": calibration is not None,
            "n_relevant": min(model.home_sample.current_n, model.away_sample.current_n),
            "family": ev.get("family", market.split("_", 1)[0]),
            "exposure_group": ev.get("exposure_group", market.split("_", 1)[0]),
            "double_control_ok": ev.get("double_control_ok", False), "justification": ev.get("justification"),
            "conflicts_with": ev.get("conflicts_with", ()),
            "joint_probability": {**joint, **ev.get("joint_probability", {})},
            "reliability": ev.get("reliability", 0),
        })

    selected, rejected, conflicts = decide(candidates)
    indices = {s.market: indice_performance_europe(s.market, eu_d, lg_d, eu_e, lg_e) for s in selected}
    return {
        "model": model, "probabilities_raw": markets, "values": raw_values, "candidates": candidates,
        "selected": selected, "rejected": rejected, "correlation_conflicts": conflicts,
        "indices_performance": indices,
        "diagnostics": {"moteur": "europe", "competition_ignored": False, "h2h_used": False,
                        "dispersion": dispersion,
                        "sample_gate": {"home_n": model.home_sample.current_n, "away_n": model.away_sample.current_n,
                                        "selection_possible": min(model.home_sample.current_n,
                                                                  model.away_sample.current_n) >= 3}},
    }
