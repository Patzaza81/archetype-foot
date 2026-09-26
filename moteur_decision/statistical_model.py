# -*- coding: utf-8 -*-
"""Cœur statistique V1: matches historiques -> forces -> lambda -> matrices."""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, fsum, isfinite, sqrt
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

MAX_MATCHES_CONTEXT = 12
LAMBDA_MIN = 0.05
LAMBDA_MAX = 10.0
POISSON_MAX_GOALS = 20

@dataclass(frozen=True)
class SampleQuality:
    n_current: int
    n_previous: int
    effective_n: float
    level: str
    previous_weight: float
    xg_available: int
    missing_required: bool

@dataclass(frozen=True)
class ModelOutput:
    lambda_home: float
    lambda_away: float
    lambda_home_first_half: Optional[float]
    lambda_away_first_half: Optional[float]
    lambda_home_second_half: Optional[float]
    lambda_away_second_half: Optional[float]
    score_matrix: Tuple[Tuple[float, ...], ...]
    score_matrix_first_half: Optional[Tuple[Tuple[float, ...], ...]]
    score_matrix_second_half: Optional[Tuple[Tuple[float, ...], ...]]
    sample_home: SampleQuality
    sample_away: SampleQuality
    diagnostics: Dict[str, Any]

def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(float(v))

def _valid_match(m: Mapping[str, Any]) -> bool:
    return isinstance(m, Mapping) and _num(m.get("buts_marques")) and _num(m.get("buts_encaisses")) and float(m["buts_marques"]) >= 0 and float(m["buts_encaisses"]) >= 0

def _ordered_latest(matches: Iterable[Mapping[str, Any]], domicile: bool) -> List[Mapping[str, Any]]:
    rows = [m for m in matches if _valid_match(m) and bool(m.get("domicile")) is domicile]
    rows.sort(key=lambda m: str(m.get("date") or ""))
    return rows[-MAX_MATCHES_CONTEXT:]

def _rate(rows: Sequence[Mapping[str, Any]], key: str) -> Optional[float]:
    vals = [float(m[key]) for m in rows if _num(m.get(key))]
    return fsum(vals) / len(vals) if vals else None

def _geometric_pair(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or a < 0 or b < 0:
        return None
    return sqrt(max(a, 0.0) * max(b, 0.0))

def _context_rates(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Optional[float]]:
    gf, ga = _rate(rows, "buts_marques"), _rate(rows, "buts_encaisses")
    xg_values = [m.get("xg") for m in rows]
    xga_values = [m.get("xg_concede") for m in rows]
    xg_complete = bool(rows) and all(_num(v) for v in xg_values) and all(_num(v) for v in xga_values)
    xg, xga = (_rate(rows, "xg"), _rate(rows, "xg_concede")) if xg_complete else (None, None)
    return {
        "gf": gf, "ga": ga,
        "attack": _geometric_pair(gf, xg) if xg is not None else gf,
        "defense": _geometric_pair(ga, xga) if xga is not None else ga,
        "hf": _rate(rows, "buts_marques_mi_temps"),
        "ha": _rate(rows, "buts_encaisses_mi_temps"),
        "xg_count": len(rows) if xg_complete else 0,
    }

def sample_quality(n_current: int, n_previous: int = 0, previous_weight: float = 0.0, xg_available: int = 0) -> SampleQuality:
    if not 0 <= previous_weight <= 1:
        raise ValueError("previous_weight doit être dans [0,1]")
    effective = float(n_current) + float(n_previous) * previous_weight
    if n_current == 0: level = "IMPOSSIBLE"
    elif n_current < 3: level = "TRES_FAIBLE"
    elif n_current < 5: level = "FAIBLE"
    elif n_current < 8: level = "UTILISABLE"
    elif n_current < 10: level = "SOLIDE"
    else: level = "TRES_SOLIDE"
    return SampleQuality(n_current, n_previous, effective, level, previous_weight, xg_available, n_current == 0)

def _blend(current: Optional[float], previous: Optional[float], weight: float) -> Optional[float]:
    if current is None: return previous
    if previous is None or weight <= 0: return current
    if not 0 <= weight <= 1: raise ValueError("weight saison précédente hors [0,1]")
    return (1.0 - weight) * current + weight * previous

def previous_season_weight(n_current: int, season_progress: float) -> float:
    """Poids déterministe de la saison précédente pour un contexte court."""
    if n_current < 0:
        raise ValueError("n_current invalide")
    if not 0.0 <= season_progress <= 1.0:
        raise ValueError("season_progress doit être dans [0,1]")
    if n_current >= 5:
        return 0.0
    return ((5.0 - float(n_current)) / 5.0) * (1.0 - season_progress)


def _lambda_from_context(home, away, previous_home, previous_away, previous_home_weight, previous_away_weight):
    ha = _blend(home["attack"], previous_home.get("attack") if previous_home else None, previous_home_weight)
    hd = _blend(away["defense"], previous_away.get("defense") if previous_away else None, previous_away_weight)
    aa = _blend(away["attack"], previous_away.get("attack") if previous_away else None, previous_away_weight)
    ad = _blend(home["defense"], previous_home.get("defense") if previous_home else None, previous_home_weight)
    if None in (ha, hd, aa, ad): raise ValueError("Données insuffisantes pour calculer lambda")
    lh, la = sqrt(max(ha, 0.0) * max(hd, 0.0)), sqrt(max(aa, 0.0) * max(ad, 0.0))
    return max(LAMBDA_MIN, min(LAMBDA_MAX, lh)), max(LAMBDA_MIN, min(LAMBDA_MAX, la))

def poisson_matrix(lambda_home: float, lambda_away: float, max_goals: int = POISSON_MAX_GOALS):
    if not (_num(lambda_home) and _num(lambda_away)) or lambda_home < 0 or lambda_away < 0:
        raise ValueError("lambda invalide")
    ph = [exp(-lambda_home) * lambda_home ** k / _factorial(k) for k in range(max_goals + 1)]
    pa = [exp(-lambda_away) * lambda_away ** k / _factorial(k) for k in range(max_goals + 1)]
    total = fsum(ph) * fsum(pa)
    if total <= 0: raise ValueError("matrice de Poisson vide")
    return tuple(tuple((ph[h] * pa[a]) / total for a in range(max_goals + 1)) for h in range(max_goals + 1))

def _factorial(n: int) -> int:
    out = 1
    for i in range(2, n + 1): out *= i
    return out

def build_model(
    home_matches,
    away_matches,
    *,
    previous_home_matches=(),
    previous_away_matches=(),
    previous_weight=0.0,
    season_progress: float | None = None,
    previous_context_compatible: bool = True,
) -> ModelOutput:
    home = _ordered_latest(home_matches, True)
    away = _ordered_latest(away_matches, False)
    if season_progress is not None:
        previous_home_weight = previous_season_weight(len(home), season_progress)
        previous_away_weight = previous_season_weight(len(away), season_progress)
    else:
        previous_home_weight = previous_weight
        previous_away_weight = previous_weight
    if not previous_context_compatible:
        previous_home_weight = previous_away_weight = 0.0
    prev_home = _ordered_latest(previous_home_matches, True)
    prev_away = _ordered_latest(previous_away_matches, False)
    if not home or not away: raise ValueError("Au moins un match domicile et un match extérieur sont nécessaires")
    hc, ac = _context_rates(home), _context_rates(away)
    phc = _context_rates(prev_home) if prev_home else None
    pac = _context_rates(prev_away) if prev_away else None
    lh, la = _lambda_from_context(hc, ac, phc, pac, previous_home_weight, previous_away_weight)
    matrix = poisson_matrix(lh, la)

    hf, af = _rate(home, "buts_marques_mi_temps"), _rate(away, "buts_marques_mi_temps")
    hfa, afa = _rate(home, "buts_encaisses_mi_temps"), _rate(away, "buts_encaisses_mi_temps")
    lhf = _blend(hf, _rate(prev_home, "buts_marques_mi_temps"), previous_home_weight)
    laf = _blend(af, _rate(prev_away, "buts_marques_mi_temps"), previous_away_weight)
    hdef = _blend(hfa, _rate(prev_home, "buts_encaisses_mi_temps"), previous_home_weight)
    adef = _blend(afa, _rate(prev_away, "buts_encaisses_mi_temps"), previous_away_weight)
    half_home = sqrt(max(lhf, 0) * max(adef, 0)) if lhf is not None and adef is not None else None
    half_away = sqrt(max(laf, 0) * max(hdef, 0)) if laf is not None and hdef is not None else None
    first_matrix = None
    if half_home is not None and half_away is not None:
        # Les composantes de mi-temps peuvent être nulles; seule la lambda
        # du match complet impose LAMBDA_MIN. Les deux moitiés doivent
        # exactement recomposer la lambda totale.
        half_home = min(half_home, max(0.0, lh))
        half_away = min(half_away, max(0.0, la))
        first_matrix = poisson_matrix(half_home, half_away)
    second_home = max(0.0, lh - half_home) if first_matrix is not None else None
    second_away = max(0.0, la - half_away) if first_matrix is not None else None
    second_matrix = poisson_matrix(second_home, second_away) if second_home is not None and second_away is not None else None

    return ModelOutput(
        lh, la, half_home, half_away, second_home, second_away,
        matrix, first_matrix, second_matrix,
        sample_quality(len(home), len(prev_home), previous_weight, hc["xg_count"] or 0),
        sample_quality(len(away), len(prev_away), previous_weight, ac["xg_count"] or 0),
        {"home_matches_used": len(home), "away_matches_used": len(away),
         "previous_home_weight": previous_home_weight,
         "previous_away_weight": previous_away_weight,
         "previous_context_compatible": bool(previous_context_compatible),
         "home_dates": [m.get("date") for m in home], "away_dates": [m.get("date") for m in away],
         "h2h_used": False,
         "xg_home_used": hc["xg_count"] == len(home),
         "xg_away_used": ac["xg_count"] == len(away),
         "previous_season_used": (previous_home_weight > 0 and bool(prev_home)) or (previous_away_weight > 0 and bool(prev_away))})
