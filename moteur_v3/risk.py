from __future__ import annotations

from dataclasses import dataclass
from math import fsum, sqrt


@dataclass(frozen=True)
class Risk:
    dispersion: float | None
    status: str
    eligible: bool
    reasons: tuple[str, ...]


def coefficient_variation(values) -> float | None:
    vals = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if len(vals) < 3:
        return None
    mean = fsum(vals) / len(vals)
    if mean <= 0:
        return None
    variance = fsum((v - mean) ** 2 for v in vals) / len(vals)
    return 100.0 * sqrt(variance) / mean


def goal_context_dispersion(match_rows) -> float | None:
    """Dispersion descriptive du contexte utilisé.

    Elle n'est pas un coefficient de prestige de compétition et ne dépend
    jamais du nom de la ligue. Elle est calculée séparément sur buts marqués
    et encaissés puis prend le maximum observé. Sa définition reste une
    variable de validation V3: elle ne doit pas être remplacée par un seuil
    optimisé sur le jeu figé.
    """
    series = []
    for key in ("buts_marques", "buts_encaisses"):
        vals = [m.get(key) for m in match_rows if isinstance(m.get(key), (int, float))]
        cv = coefficient_variation(vals)
        if cv is not None:
            series.append(cv)
    return max(series) if series else None


def assess(dispersion: float | None, probability: float) -> Risk:
    if dispersion is None:
        return Risk(None, "INCONNUE", False, ("DISPERSION_INSUFFISANTE",))
    if dispersion > 8:
        return Risk(dispersion, "INSTABLE", False, ("DISPERSION_SUP_8",))
    if dispersion > 5 and probability < 0.67:
        return Risk(dispersion, "SOUS_CONTRAINTE", False,
                    ("DISPERSION_5_8_ET_P_INF_67",))
    return Risk(dispersion, "STABLE" if dispersion <= 5 else "SOUS_CONTRAINTE", True, ())
