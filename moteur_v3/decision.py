
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Selection:
    market: str
    probability: float
    odds: float
    edge: float
    edv: float
    family: str
    exposure_group: str
    reason: str


def _group(c):
    return c.get("exposure_group") or c.get("family") or "autre"


def _dominated(a, b):
    return (
        b["probability"] >= a["probability"]
        and b["edv"] >= a["edv"]
        and b.get("reliability", 0) >= a.get("reliability", 0)
        and (
            b["probability"] > a["probability"]
            or b["edv"] > a["edv"]
            or b.get("reliability", 0) > a.get("reliability", 0)
        )
    )


def decide(candidates: Sequence[Mapping], max_selections: int = 3):
    if max_selections < 1:
        raise ValueError("MAX_SELECTIONS_INVALIDE")

    eligible = []
    rejected = []
    for c in candidates:
        reasons = []
        if not c.get("eligible"):
            reasons.append("VALUE_NON_ELIGIBLE")
        if not c.get("calibrated"):
            reasons.append("CALIBRATION_ABSENTE")
        if not c.get("double_control_ok"):
            reasons.append("DOUBLE_CONTROLE_ECHOUE_OU_ABSENT")
        if not c.get("justification"):
            reasons.append("JUSTIFICATION_INSUFFISANTE")
        if c.get("n_relevant", 0) < 3:
            reasons.append("N_LIEU_INF_3")
        if c.get("n_relevant", 0) < 5 and not (
            c.get("probability", 0) >= 0.67 and c.get("edv", 0) >= 7
        ):
            reasons.append("N_3_4_CONTROLE_STRICT_NON_SATISFAIT")
        if reasons:
            rejected.append((c.get("market"), tuple(reasons)))
        else:
            eligible.append(c)

    groups = {}
    for c in eligible:
        groups.setdefault(_group(c), []).append(c)
    representatives = [
        max(rows, key=lambda x: (
            float(x["probability"]),
            float(x["edv"]),
            float(x.get("reliability", 0)),
            str(x["market"]),
        ))
        for rows in groups.values()
    ]

    frontier = [c for c in representatives
                if not any(_dominated(c, other) for other in representatives if other is not c)]

    selected = []
    conflicts = []
    for c in frontier:
        blocked = False
        for s in selected:
            if c.get("conflicts_with") and s.market in set(c["conflicts_with"]):
                blocked = True
            if s.market in set(s.reason.split("\0")) if "\0" in s.reason else False:
                blocked = True
            pair = (s.market, c["market"])
            joint = c.get("joint_probability", {}).get(pair)
            if joint is None:
                joint = c.get("joint_probability", {}).get((c["market"], s.market))
            if joint is not None:
                denom = float(s.probability) * float(c["probability"])
                if denom > 0 and float(joint) / denom >= 1.50:
                    blocked = True
                    conflicts.append((c["market"], s.market, float(joint) / denom))
        if not blocked:
            selected.append(Selection(
                c["market"], float(c["probability"]), float(c["odds"]),
                float(c["edge"]), float(c["edv"]), str(c.get("family", "autre")),
                str(c.get("exposure_group", "autre")), str(c["justification"]),
            ))

    selected.sort(key=lambda x: (x.edv, x.probability, x.market), reverse=True)
    return selected[:max_selections], rejected, conflicts
