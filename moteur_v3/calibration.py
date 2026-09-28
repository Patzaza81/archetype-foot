from __future__ import annotations

from dataclasses import dataclass
from math import log


@dataclass(frozen=True)
class CalibrationFit:
    ready: bool
    observations: int
    reason: str
    points: tuple[tuple[float, float], ...]


class IsotonicCalibrator:
    """Calibration monotone, entraînée uniquement sur observations antérieures.

    Ce composant ne connaît ni équipe, ni ligue, ni compétition. Le code
    appelant doit lui fournir exclusivement des observations disponibles avant
    le match à calibrer.
    """

    def __init__(self, minimum_observations: int = 300):
        if minimum_observations < 10:
            raise ValueError("minimum_observations_trop_faible")
        self.minimum_observations = minimum_observations
        self.fit_result = CalibrationFit(False, 0, "NON_ENTRAINEE", ())

    def fit(self, probabilities, outcomes) -> CalibrationFit:
        pairs = [(float(p), int(y)) for p, y in zip(probabilities, outcomes)
                 if 0 < float(p) < 1 and int(y) in (0, 1)]
        if len(pairs) < self.minimum_observations:
            self.fit_result = CalibrationFit(False, len(pairs), "ECHANTILLON_INSUFFISANT", ())
            return self.fit_result

        pairs.sort()
        blocks = [[p, p, y, 1] for p, y in pairs]
        i = 0
        while i < len(blocks) - 1:
            if blocks[i][2] / blocks[i][3] > blocks[i + 1][2] / blocks[i + 1][3]:
                n = blocks[i][3] + blocks[i + 1][3]
                blocks[i] = [
                    blocks[i][0],
                    blocks[i + 1][1],
                    blocks[i][2] + blocks[i + 1][2],
                    n,
                ]
                del blocks[i + 1]
                i = max(0, i - 1)
            else:
                i += 1

        points = tuple(
            ((lo + hi) / 2.0, successes / n)
            for lo, hi, successes, n in blocks
        )
        self.fit_result = CalibrationFit(True, len(pairs), "OK", points)
        return self.fit_result

    def predict(self, probability: float) -> float | None:
        if not self.fit_result.ready:
            return None
        p = min(max(float(probability), 0.0), 1.0)
        pts = self.fit_result.points
        if p <= pts[0][0]:
            return pts[0][1]
        if p >= pts[-1][0]:
            return pts[-1][1]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if x1 <= p <= x2:
                if x2 == x1:
                    return (y1 + y2) / 2
                t = (p - x1) / (x2 - x1)
                return y1 + t * (y2 - y1)
        return None
