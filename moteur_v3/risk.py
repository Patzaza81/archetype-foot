from __future__ import annotations

from dataclasses import dataclass
from math import fsum


@dataclass(frozen=True)
class Risk:
    dispersion: float | None
    status: str
    eligible: bool
    reasons: tuple[str, ...]


def poisson_dispersion(values) -> float | None:
    """Indice variance/moyenne des buts observés."""
    vals = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) >= 0]
    if len(vals) < 3:
        return None
    mean = fsum(vals) / len(vals)
    if mean <= 0:
        return None
    variance = fsum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return variance / mean


def goal_context_dispersion(match_rows) -> float | None:
    """Mesure la surdispersion empirique du contexte, sans CV en pourcentage."""
    indices = []
    for key in ("buts_marques", "buts_encaisses"):
        value = poisson_dispersion([m.get(key) for m in match_rows if isinstance(m.get(key), (int, float))])
        if value is not None:
            indices.append(value)
    return max(indices) if indices else None


def assess(dispersion: float | None, probability: float) -> Risk:
    if dispersion is None:
        return Risk(None, "INCONNUE", False, ("DISPERSION_INSUFFISANTE",))
    if dispersion > 1.50:
        return Risk(dispersion, "SURDISPERSEE", False, ("SURDISPERSION_SUP_1_50",))
    if dispersion > 1.20 and probability < 0.67:
        return Risk(dispersion, "SURDISPERSEE_SOUS_CONTRAINTE", False,
                    ("SURDISPERSION_1_20_1_50_ET_P_INF_67",))
    return Risk(dispersion, "POISSON_COMPATIBLE" if dispersion <= 1.20 else "SURDISPERSEE_SOUS_CONTRAINTE", True, ())
