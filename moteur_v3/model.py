from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial, fsum, isfinite, sqrt
from typing import Any, Mapping, Sequence

MAX_CONTEXT = 12
MAX_GOALS = 12


@dataclass(frozen=True)
class Sample:
    current_n: int
    previous_n: int
    previous_weight: float
    level: str
    xg_complete: bool


@dataclass(frozen=True)
class GoalModel:
    lambda_home: float
    lambda_away: float
    first_home: float | None
    first_away: float | None
    second_home: float | None
    second_away: float | None
    score: tuple[tuple[float, ...], ...]
    first_score: tuple[tuple[float, ...], ...] | None
    second_score: tuple[tuple[float, ...], ...] | None
    home_sample: Sample
    away_sample: Sample
    degenerate_home: bool
    degenerate_away: bool
    diagnostics: dict[str, Any]


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(float(v))


def _valid(m: Mapping[str, Any]) -> bool:
    return (
        isinstance(m, Mapping)
        and _num(m.get("buts_marques"))
        and _num(m.get("buts_encaisses"))
        and m["buts_marques"] >= 0
        and m["buts_encaisses"] >= 0
    )


def _latest(rows: Sequence[Mapping[str, Any]], domicile: bool) -> list[Mapping[str, Any]]:
    out = [m for m in rows if _valid(m) and bool(m.get("domicile")) is domicile]
    out.sort(key=lambda m: str(m.get("date") or ""))
    return out[-MAX_CONTEXT:]


def _mean(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    vals = [float(m[key]) for m in rows if _num(m.get(key))]
    return fsum(vals) / len(vals) if vals else None


def _previous_weight(n: int, progress: float) -> float:
    if not 0 <= progress <= 1:
        raise ValueError("season_progress doit être dans [0,1]")
    if n >= 5:
        return 0.0
    return ((5 - n) / 5.0) * (1.0 - progress)


def _blend(current: float | None, previous: float | None, weight: float) -> float | None:
    if current is None:
        return previous
    if previous is None or weight <= 0:
        return current
    return (1 - weight) * current + weight * previous


def _sample(n: int, previous_n: int, weight: float, xg_complete: bool) -> Sample:
    if n == 0:
        level = "IMPOSSIBLE"
    elif n < 3:
        level = "TRES_FAIBLE"
    elif n < 5:
        level = "FAIBLE"
    elif n < 8:
        level = "UTILISABLE"
    elif n < 10:
        level = "SOLIDE"
    else:
        level = "TRES_SOLIDE"
    return Sample(n, previous_n, weight, level, xg_complete)


def _strength(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    gf, ga = _mean(rows, "buts_marques"), _mean(rows, "buts_encaisses")
    xg_values = [m.get("xg") for m in rows]
    xga_values = [m.get("xg_concede") for m in rows]
    complete = bool(rows) and all(_num(v) for v in xg_values) and all(_num(v) for v in xga_values)

    # xG/xGA ne sont pas ajoutés aux buts : quand ils sont complets, ils
    # constituent une deuxième mesure de la même force offensive/défensive.
    attack = sqrt(max(gf, 0) * max(_mean(rows, "xg"), 0)) if complete else gf
    defense = sqrt(max(ga, 0) * max(_mean(rows, "xg_concede"), 0)) if complete else ga

    return {
        "attack": attack,
        "defense": defense,
        "gf": gf,
        "ga": ga,
        "hf": _mean(rows, "buts_marques_mi_temps"),
        "ha": _mean(rows, "buts_encaisses_mi_temps"),
        "xg_complete": complete,
    }


def _lambda(attack: float | None, defense: float | None) -> float:
    if attack is None or defense is None:
        raise ValueError("Données insuffisantes pour lambda")
    # Aucun plancher footballistique : zéro reste zéro. La sélection est
    # bloquée plus loin si le modèle devient dégénéré.
    return sqrt(max(0.0, attack) * max(0.0, defense))


def poisson(lam: float, k: int) -> float:
    if lam < 0 or not isfinite(lam):
        raise ValueError("lambda invalide")
    return exp(-lam) * lam**k / factorial(k)


def score_matrix(lambda_home: float, lambda_away: float) -> tuple[tuple[float, ...], ...]:
    ph = [poisson(lambda_home, k) for k in range(MAX_GOALS + 1)]
    pa = [poisson(lambda_away, k) for k in range(MAX_GOALS + 1)]
    z = fsum(ph) * fsum(pa)
    if z <= 0:
        raise ValueError("matrice de score vide")
    return tuple(tuple(ph[h] * pa[a] / z for a in range(MAX_GOALS + 1))
                 for h in range(MAX_GOALS + 1))


def build_model(
    home_matches: Sequence[Mapping[str, Any]],
    away_matches: Sequence[Mapping[str, Any]],
    *,
    previous_home_matches: Sequence[Mapping[str, Any]] = (),
    previous_away_matches: Sequence[Mapping[str, Any]] = (),
    season_progress: float = 1.0,
    previous_context_compatible: bool = True,
) -> GoalModel:
    home = _latest(home_matches, True)
    away = _latest(away_matches, False)

    if not home or not away:
        raise ValueError("MATCHS_DOMICILE_OU_EXTERIEUR_ABSENTS")

    pw_h = _previous_weight(len(home), season_progress)
    pw_a = _previous_weight(len(away), season_progress)
    if not previous_context_compatible:
        pw_h = pw_a = 0.0

    prev_h = _latest(previous_home_matches, True)
    prev_a = _latest(previous_away_matches, False)

    hs, es = _strength(home), _strength(away)
    phs = _strength(prev_h) if prev_h else {}
    pas = _strength(prev_a) if prev_a else {}

    home_attack = _blend(hs["attack"], phs.get("attack"), pw_h)
    away_defence = _blend(es["defense"], pas.get("defense"), pw_a)
    away_attack = _blend(es["attack"], pas.get("attack"), pw_a)
    home_defence = _blend(hs["defense"], phs.get("defense"), pw_h)

    lh = _lambda(home_attack, away_defence)
    la = _lambda(away_attack, home_defence)
    matrix = score_matrix(lh, la)

    # Les données de mi-temps doivent exister des deux côtés. La seconde
    # moitié est ensuite le reliquat du match complet, jamais un second modèle
    # indépendant qui pourrait ne pas recomposer lambda.
    hf = _blend(hs["hf"], phs.get("hf"), pw_h)
    ha = _blend(hs["ha"], phs.get("ha"), pw_h)
    af = _blend(es["hf"], pas.get("hf"), pw_a)
    aa = _blend(es["ha"], pas.get("ha"), pw_a)

    first_h = first_a = None
    first_matrix = second_matrix = None
    if None not in (hf, ha, af, aa):
        first_h = _lambda(hf, aa)
        first_a = _lambda(af, ha)
        first_h = min(first_h, lh)
        first_a = min(first_a, la)
        first_matrix = score_matrix(first_h, first_a)
        second_h, second_a = lh - first_h, la - first_a
        second_matrix = score_matrix(second_h, second_a)
    else:
        second_h = second_a = None

    return GoalModel(
        lh, la, first_h, first_a, second_h, second_a,
        matrix, first_matrix, second_matrix,
        _sample(len(home), len(prev_h), pw_h, hs["xg_complete"]),
        _sample(len(away), len(prev_a), pw_a, es["xg_complete"]),
        lh == 0.0, la == 0.0,
        {
            "home_matches_used": len(home),
            "away_matches_used": len(away),
            "home_dates": [m.get("date") for m in home],
            "away_dates": [m.get("date") for m in away],
            "previous_home_weight": pw_h,
            "previous_away_weight": pw_a,
            "previous_context_compatible": previous_context_compatible,
            "previous_season_used": bool((pw_h and prev_h) or (pw_a and prev_a)),
            "xg_home_used": hs["xg_complete"],
            "xg_away_used": es["xg_complete"],
            "h2h_used": False,
        },
    )
