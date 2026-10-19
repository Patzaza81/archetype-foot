"""Validation statistique de la matrice : permutations, walk-forward, règles gelées, un pari par match.

Module isolé, lecture seule. Dépend de numpy (déjà requis par pandas dans requirements.txt) ; `core.py`
reste sans dépendance tierce. Rien ici n'écrit dans un moteur, le Journal ou le pipeline.

Garanties de conception
-----------------------
1. La découverte des règles (`core.discover_scenarios`) ne lit que les variables pré-match de la période de
   découverte, jamais un résultat. L'ensemble des règles ne dépend donc pas des scores : il est identique sous
   toutes les permutations, ce qui rend exact le test de permutation du pipeline complet.
2. Le biais d'exploration (des milliers de scénarios, 16 marchés) est traité de trois façons :
   - le test de permutation REJOUE la sélection (correction Benjamini-Hochberg, seuils, validation) sur des
     scores permutés et compare la statistique de test finale à cette loi nulle ;
   - pour des règles gelées avant l'échantillon indépendant, une correction max-T de type Westfall-Young
     donne des p-values ajustées par règle (contrôle du risque de faux positif sur toute la famille) ;
   - une règle n'est jugée que sur des matchs qu'elle n'a jamais servi à choisir.
3. Les 16 marchés d'un même match ne sont pas des preuves indépendantes : la permutation déplace le score
   complet d'un match (les 16 issues restent liées), et le portefeuille « un pari par match » n'autorise
   qu'un seul pari par match, avec un intervalle bootstrap par jour (les matchs d'un jour sont corrélés).
4. Deux lois nulles :
   - `marche` : les scores sont permutés à l'intérieur de strates de probabilité 1X2 du marché. Elle conserve
     tout ce que le prix des cotes sait déjà du résultat ; seule l'information EN PLUS du marché est testée.
     C'est la loi qui gouverne toute conclusion sur la rentabilité.
   - `libre` : permutation à l'intérieur de chaque championnat. Elle teste seulement « mieux que le hasard »,
     et sera presque toujours battue par les règles qui lisent les cotes (le marché est informatif).
5. Les cotes d'une évaluation sont exclusivement celles de l'archive du run (`target_odds`) ; Football-Data
   n'en fournit aucune (voir `football_data.py`) : sur cette source, seuls le taux de base et la stabilité
   sont testés, jamais le ROI.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from typing import Any, Callable

import numpy as np

from . import core
from .core import (MIN_DISCOVERY_SUPPORT, MIN_EVAL_SUPPORT, SELECTION_CRITERIA, TARGETS, build_features,
                   discover_scenarios)

N_TARGETS = len(TARGETS)
MIN_SETTLED_FOR_ROI = MIN_EVAL_SUPPORT  # paris réglés minimum par scénario pour que son ROI compte
# Critères de la décision « preuve de rentabilité » : définis AVANT de lire les résultats.
PROOF_MIN_SETTLED_PICKS = 300
PROOF_MIN_SPAN_DAYS = 56
PROOF_MIN_POSITIVE_BLOCK_SHARE = 2 / 3
PROOF_ALPHA = 0.05


# ------------------------------------------------------------------------------------------------
# Bases statistiques vectorisées (mêmes formules que core.py ; l'égalité est testée)
# ------------------------------------------------------------------------------------------------

def _normal_two_sided(z: np.ndarray) -> np.ndarray:
    t = 1.0 / (1.0 + 0.2316419 * z)
    density = 0.3989422804014327 * np.exp(-z * z / 2.0)
    tail = density * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    return np.clip(2.0 * tail, 0.0, 1.0)


def binomial_p_vec(wins: np.ndarray, n: np.ndarray, base: np.ndarray) -> np.ndarray:
    """Équivalent vectorisé de `core._binomial_p_approx` (tri uniquement, jamais preuve finale)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        sd = np.sqrt(n * base * (1.0 - base))
        z = np.abs(wins - n * base) / sd
        p = _normal_two_sided(z)
    invalid = (n <= 0) | ~np.isfinite(base) | (base <= 0) | (base >= 1) | ~(sd > 0)
    return np.where(invalid, 1.0, p)


def bh_vec(p: np.ndarray) -> np.ndarray:
    """Équivalent vectorisé de `core._bh_adjust` (Benjamini-Hochberg, monotone)."""
    n = len(p)
    if n == 0:
        return np.array([], dtype=float)
    order = np.argsort(p, kind="stable")
    adjusted = p[order] * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(adjusted, 1.0)
    return out


# ------------------------------------------------------------------------------------------------
# Matrice règles x matchs
# ------------------------------------------------------------------------------------------------

def _feature_columns(feature_rows: list[dict], names: set[str]) -> dict[str, np.ndarray]:
    columns: dict[str, np.ndarray] = {}
    for name in names:
        if name == "league":
            columns[name] = np.array([str(f.get("league") or "INCONNUE") for f in feature_rows], dtype=object)
        else:
            columns[name] = np.array([float(f[name]) if core._num(f.get(name)) else np.nan for f in feature_rows], dtype=float)
    return columns


def _condition_mask_np(columns: dict[str, np.ndarray], condition: dict) -> np.ndarray:
    """Même sémantique que `core._condition_value` : une valeur absente ne satisfait jamais une condition."""
    column, op, threshold = columns[condition["feature"]], condition["op"], condition["value"]
    with np.errstate(invalid="ignore"):
        if op == "eq":
            return np.asarray(column == threshold, dtype=bool)
        if op == "ge":
            return np.asarray(column >= threshold, dtype=bool)
        if op == "le":
            return np.asarray(column <= threshold, dtype=bool)
        if op == "gt":
            return np.asarray(column > threshold, dtype=bool)
        if op == "lt":
            return np.asarray(column < threshold, dtype=bool)
        if op == "between":
            return np.asarray((column >= threshold[0]) & (column <= threshold[1]), dtype=bool)
    return np.zeros(len(column), dtype=bool)


class Arena:
    """Règles distinctes x matchs, issues par cible et cotes réelles, prêtes pour les permutations.

    `scenarios` est la liste réelle (règle, cible) de la découverte : un budget tronqué ne donne pas toujours
    les 16 cibles d'une règle, la grille n'est donc jamais supposée complète. `splits` associe un nom de segment
    à ses enregistrements ; les segments ne sont jamais recalculés à partir des résultats.
    """

    def __init__(self, records: list[dict], feature_map: dict[str, dict], scenarios: list[dict],
                 splits: dict[str, list[dict]]):
        self.records = records
        n_matches = len(records)
        position = {str(r["match_id"]): i for i, r in enumerate(records)}
        self.idx = {name: np.array([position[str(r["match_id"])] for r in rows], dtype=int) for name, rows in splits.items()}
        rule_index: dict[str, int] = {}
        self.rules: list[list[dict]] = []
        rule_of, target_of = [], []
        target_index = {t: i for i, t in enumerate(TARGETS)}
        for s in scenarios:
            key = json.dumps(s["conditions"], sort_keys=True)
            if key not in rule_index:
                rule_index[key] = len(self.rules)
                self.rules.append(s["conditions"])
            rule_of.append(rule_index[key])
            target_of.append(target_index[s["target"]])
        self.rule_idx = np.array(rule_of, dtype=int)
        self.tgt_idx = np.array(target_of, dtype=int)
        self.scenarios = scenarios
        dtype = np.float64 if n_matches <= 6000 else np.float32
        feature_rows = [feature_map[str(r["match_id"])] for r in records]
        names = {c["feature"] for conds in self.rules for c in conds}
        columns = _feature_columns(feature_rows, names)
        cache: dict[str, np.ndarray] = {}
        full = np.ones((len(self.rules), n_matches), dtype=bool)
        for i, conditions in enumerate(self.rules):
            mask = np.ones(n_matches, dtype=bool)
            for condition in conditions:
                ckey = json.dumps(condition, sort_keys=True)
                if ckey not in cache:
                    cache[ckey] = _condition_mask_np(columns, condition)
                mask &= cache[ckey]
            full[i] = mask
        self.Rs = {name: full[:, idx].astype(dtype) for name, idx in self.idx.items()}
        self.n_rule = {name: matrix.sum(axis=1) for name, matrix in self.Rs.items()}
        self.dtype = dtype
        self.Y = np.zeros((N_TARGETS, n_matches), dtype=dtype)
        self.Ox = np.zeros((N_TARGETS, n_matches), dtype=dtype)
        self.H = np.zeros((N_TARGETS, n_matches), dtype=dtype)
        for i, record in enumerate(records):
            odds_map = record.get("target_odds") or {}
            for t, target in enumerate(TARGETS):
                self.Y[t, i] = core.outcome(record, target)
                odds = odds_map.get(target)
                if core._num(odds) and odds > 1:
                    self.Ox[t, i] = odds
                    self.H[t, i] = 1.0
        self.has_odds = bool(self.H.any())
        self.days = np.array([str(r["date"])[:10] for r in records])
        self.leagues = np.array([str(r.get("league") or "INCONNUE") for r in records], dtype=object)

    # -- statistiques par scénario et par segment -------------------------------------------------
    def table(self, Y: np.ndarray, split: str) -> dict[str, np.ndarray]:
        idx, Rs = self.idx[split], self.Rs[split]
        Ys = Y[:, idx]
        r, t = self.rule_idx, self.tgt_idx
        n = self.n_rule[split][r].astype(float)
        wins = (Rs @ Ys.T)[r, t].astype(float)
        base = Ys.mean(axis=1).astype(float) if len(idx) else np.full(N_TARGETS, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            hit = wins / n
            lift = hit - base[t]
            z_lift = lift / np.sqrt(base[t] * (1.0 - base[t]) / n)
        out = {"n": n, "wins": wins, "hit": hit, "base": base[t], "lift": lift, "z_lift": z_lift, "base_by_target": base}
        if self.has_odds:
            Hs = self.H[:, idx]
            gain = Hs * (Ys * self.Ox[:, idx] - 1.0)
            settled = (Rs @ Hs.T)[r, t].astype(float)
            pnl = (Rs @ gain.T)[r, t].astype(float)
            pnl2 = (Rs @ (gain * gain).T)[r, t].astype(float)
            with np.errstate(divide="ignore", invalid="ignore"):
                roi = pnl / settled
                variance = (pnl2 - settled * roi * roi) / (settled - 1.0)
                t_roi = roi / np.sqrt(variance / settled)
            out.update({"settled": settled, "pnl": pnl, "roi": roi, "t_roi": np.where(np.isfinite(t_roi), t_roi, np.nan)})
        return out

    def select(self, Y: np.ndarray, need_test: bool = True) -> dict[str, Any]:
        """Sélection gelée de `core.run_experiment`, vectorisée : le segment test n'entre dans aucun critère
        autre que l'effectif minimum (un compte de matchs, pas un résultat)."""
        train, validation = self.table(Y, "train"), self.table(Y, "validation")
        p = binomial_p_vec(train["wins"], train["n"], train["base"])
        scored = train["n"] >= MIN_DISCOVERY_SUPPORT
        q = np.ones(len(p))
        q[scored] = bh_vec(p[scored])
        with np.errstate(invalid="ignore"):
            selected = (scored & (validation["n"] >= SELECTION_CRITERIA["validation_min_n"])
                        & (q <= SELECTION_CRITERIA["train_q_bh_max"])
                        & (validation["lift"] > SELECTION_CRITERIA["validation_lift_min_exclusive"]))
        result = {"train": train, "validation": validation, "q": q, "p": p}
        if need_test:
            test = self.table(Y, "test")
            selected &= (validation["n"] >= MIN_EVAL_SUPPORT) & (test["n"] >= MIN_EVAL_SUPPORT)
            result["test"] = test
        result["selected"] = selected
        return result

    # -- un seul pari par match -------------------------------------------------------------------
    def pick_one_bet(self, ordered: np.ndarray, split: str, require_odds: bool) -> tuple[np.ndarray, np.ndarray]:
        """Pour chaque match du segment, le scénario déclenché de plus haute priorité (ordre d'entrée).
        Retourne (positions dans le segment, scénario choisi). Un match n'apparaît jamais deux fois."""
        if len(ordered) == 0:
            return np.array([], dtype=int), np.array([], dtype=int)
        trig = self.Rs[split][self.rule_idx[ordered]] > 0
        if require_odds:
            trig &= self.H[self.tgt_idx[ordered]][:, self.idx[split]] > 0
        first = trig.argmax(axis=0)
        positions = np.nonzero(trig.any(axis=0))[0]
        return positions, ordered[first[positions]]

    def picks(self, Y: np.ndarray, split: str, positions: np.ndarray, chosen: np.ndarray) -> dict[str, np.ndarray]:
        idx = self.idx[split]
        matches = idx[positions]
        t = self.tgt_idx[chosen]
        base = Y[:, idx].mean(axis=1)[t] if len(idx) else np.array([])
        y = Y[t, matches].astype(float)
        out = {"match": matches, "target": t, "hit": y, "excess": y - base, "day": self.days[matches], "league": self.leagues[matches]}
        if self.has_odds:
            has = self.H[t, matches] > 0
            out["odds"] = np.where(has, self.Ox[t, matches], np.nan).astype(float)
            out["roi"] = np.where(has, y * self.Ox[t, matches] - 1.0, np.nan)
        return out


# ------------------------------------------------------------------------------------------------
# Permutations
# ------------------------------------------------------------------------------------------------

def market_strata(records: list[dict], feature_map: dict[str, dict], home_bins: int = 10, away_bins: int = 3) -> np.ndarray:
    """Strates de probabilité 1X2 du marché (déciles domicile x terciles extérieur). Les matchs sans trio
    de cotes complet forment leur propre strate : ils ne sont mélangés qu'entre eux."""
    home = np.array([feature_map[str(r["match_id"])].get("market_home_prob", np.nan) for r in records], dtype=float)
    away = np.array([feature_map[str(r["match_id"])].get("market_away_prob", np.nan) for r in records], dtype=float)
    known = np.isfinite(home) & np.isfinite(away)
    labels = np.full(len(records), "SANS_COTES", dtype=object)
    if known.sum() >= home_bins * away_bins:
        h_edges = np.unique(np.quantile(home[known], np.linspace(0, 1, home_bins + 1)[1:-1]))
        a_edges = np.unique(np.quantile(away[known], np.linspace(0, 1, away_bins + 1)[1:-1]))
        labels[known] = [f"M{h}-{a}" for h, a in zip(np.digitize(home[known], h_edges), np.digitize(away[known], a_edges))]
    return labels


def league_strata(records: list[dict]) -> np.ndarray:
    return np.array([str(r.get("league") or "INCONNUE") for r in records], dtype=object)


def _groups(labels: np.ndarray) -> list[np.ndarray]:
    order: dict[Any, list[int]] = {}
    for i, label in enumerate(labels):
        order.setdefault(label, []).append(i)
    return [np.array(v, dtype=int) for v in order.values() if len(v) > 1]


def permuted(Y: np.ndarray, groups: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    """Déplace le score COMPLET de chaque match (donc ses 16 issues liées) au sein de sa strate.
    Les variables, les cotes, les dates et les segments restent attachés au match d'origine."""
    perm = np.arange(Y.shape[1])
    for g in groups:
        perm[g] = g[rng.permutation(len(g))]
    return Y[:, perm]


def p_value(observed: float, null: np.ndarray) -> float:
    """Valeur p de permutation unilatérale avec correction +1 (jamais exactement 0)."""
    null = np.asarray(null, dtype=float)
    return float((1 + np.sum(null >= observed - 1e-12)) / (1 + len(null)))


# ------------------------------------------------------------------------------------------------
# Statistiques de pipeline (observées et sous permutation)
# ------------------------------------------------------------------------------------------------

def pipeline_stats(arena: Arena, Y: np.ndarray) -> dict[str, float]:
    """Rejoue sélection + mesure test sur les issues `Y` et résume en statistiques scalaires."""
    sel = arena.select(Y)
    selected = np.nonzero(sel["selected"])[0]
    test = sel["test"]
    stats = {"selected": float(len(selected)), "mean_test_lift": 0.0, "mean_test_roi": 0.0, "max_test_roi": 0.0,
             "portfolio_picks": 0.0, "portfolio_excess": 0.0, "portfolio_roi": 0.0}
    if len(selected) == 0:
        return stats
    stats["mean_test_lift"] = float(np.nanmean(test["lift"][selected]))
    if arena.has_odds:
        ok = selected[test["settled"][selected] >= MIN_SETTLED_FOR_ROI]
        if len(ok):
            stats["mean_test_roi"] = float(np.nanmean(test["roi"][ok]))
            stats["max_test_roi"] = float(np.nanmax(test["roi"][ok]))
    order = selected[np.argsort(-sel["validation"]["lift"][selected], kind="stable")]
    positions, chosen = arena.pick_one_bet(order, "test", require_odds=arena.has_odds)
    if len(positions):
        picks = arena.picks(Y, "test", positions, chosen)
        stats["portfolio_picks"] = float(len(positions))
        stats["portfolio_excess"] = float(np.mean(picks["excess"]))
        if arena.has_odds and np.isfinite(picks["roi"]).any():
            stats["portfolio_roi"] = float(np.nanmean(picks["roi"]))
    return stats


def nested_permutation(arena: Arena, strata: np.ndarray, repetitions: int, seed: int) -> dict[str, np.ndarray]:
    """Loi nulle du pipeline complet : la sélection est REFAITE sur chaque jeu de scores permutés."""
    rng = np.random.default_rng(seed)
    groups = _groups(strata)
    draws = [pipeline_stats(arena, permuted(arena.Y, groups, rng)) for _ in range(repetitions)]
    return {key: np.array([d[key] for d in draws]) for key in draws[0]} if draws else {}


def compare_to_null(observed: dict[str, float], null: dict[str, np.ndarray]) -> dict[str, Any]:
    """Compare chaque statistique observée à sa loi nulle.

    Pour le NOMBRE de scénarios retenus et de paris, la valeur p est calculée sur tous les tirages. Pour les
    statistiques de performance (gain de taux, ROI), elle est calculée sur les seuls tirages où la sélection
    retient au moins un scénario : on ne récompense pas le fait que le hasard retienne moins de règles (cet effet
    est mesuré à part par `selected`). Si aucun tirage ne retient de règle, la valeur p est None (non calculable)."""
    out: dict[str, Any] = {}
    has = null["selected"] > 0
    for key, value in observed.items():
        draws = null[key]
        if key in ("selected", "portfolio_picks"):
            out[key] = {"observed": value, "null_mean": float(np.mean(draws)), "null_p95": float(np.percentile(draws, 95)),
                        "p": p_value(value, draws)}
            continue
        conditional = draws[has]
        out[key] = {
            "observed": value, "null_draws_with_selection": int(has.sum()),
            "null_mean": float(conditional.mean()) if has.any() else None,
            "null_p95": float(np.percentile(conditional, 95)) if has.any() else None,
            "p": p_value(value, conditional) if has.any() else None,
        }
    return out


# ------------------------------------------------------------------------------------------------
# Portefeuille « un pari par match » : IC bootstrap par jour, stabilité par championnat et période
# ------------------------------------------------------------------------------------------------

def cluster_bootstrap_mean(values: np.ndarray, days: np.ndarray, repetitions: int = 4000, seed: int = 11) -> dict[str, Any]:
    """Moyenne et IC95 en rééchantillonnant des JOURS entiers (les matchs d'un jour sont corrélés)."""
    keep = np.isfinite(values)
    values, days = values[keep], days[keep]
    if len(values) == 0:
        return {"n": 0, "mean": None, "ci95": None, "days": 0}
    unique, inverse = np.unique(days, return_inverse=True)
    sums, counts = np.bincount(inverse, weights=values), np.bincount(inverse)
    if len(unique) < 2:
        return {"n": int(len(values)), "mean": float(values.mean()), "ci95": None, "days": int(len(unique))}
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(unique), size=(repetitions, len(unique)))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return {"n": int(len(values)), "mean": float(values.mean()), "ci95": [float(low), float(high)], "days": int(len(unique))}


def _group_summary(values: np.ndarray, labels: np.ndarray, min_n: int) -> dict[str, Any]:
    rows = {}
    for label in sorted(set(labels.tolist())):
        v = values[(labels == label) & np.isfinite(values)]
        if len(v) >= min_n:
            rows[str(label)] = {"n": int(len(v)), "mean": float(v.mean())}
    positive = sum(1 for r in rows.values() if r["mean"] > 0)
    return {"groups": len(rows), "positive": positive, "share_positive": (positive / len(rows)) if rows else None,
            "min_n_per_group": min_n, "by_group": rows}


def portfolio_report(arena: Arena, Y: np.ndarray, split: str, ordered: np.ndarray, *, label_for: Callable[[int], str] | None = None,
                     bootstrap_seed: int = 11, min_group_n: int = 15) -> dict[str, Any]:
    positions, chosen = arena.pick_one_bet(ordered, split, require_odds=arena.has_odds)
    if len(positions) == 0:
        return {"picks": 0}
    p = arena.picks(Y, split, positions, chosen)
    n_matches = len(arena.idx[split])
    report: dict[str, Any] = {
        "picks": int(len(positions)), "matches_in_segment": int(n_matches), "distinct_matches": int(len(set(p["match"].tolist()))),
        "hit_rate": float(p["hit"].mean()), "excess_over_base": cluster_bootstrap_mean(p["excess"], p["day"], seed=bootstrap_seed),
        "by_target": dict(Counter(TARGETS[t] for t in p["target"])),
    }
    weeks = np.array([f"{date.fromisoformat(d).isocalendar()[0]}-S{date.fromisoformat(d).isocalendar()[1]:02d}" for d in p["day"]])
    report["excess_by_league"] = _group_summary(p["excess"], p["league"], min_group_n)
    report["excess_by_period"] = _group_summary(p["excess"], weeks, min_group_n)
    if arena.has_odds:
        settled = np.isfinite(p["roi"])
        report.update({
            "settled_bets": int(settled.sum()), "mean_odds": float(np.nanmean(p["odds"])) if settled.any() else None,
            "roi": cluster_bootstrap_mean(p["roi"], p["day"], seed=bootstrap_seed),
            "roi_by_league": _group_summary(p["roi"], p["league"], min_group_n),
            "roi_by_period": _group_summary(p["roi"], weeks, min_group_n),
        })
    return report


# ------------------------------------------------------------------------------------------------
# Walk-forward sur l'archive de test (avec cotes archivées)
# ------------------------------------------------------------------------------------------------

def _date_cut(rows: list[dict], fraction: float) -> int:
    """Indice de coupure sur un changement de date, le plus proche de `fraction` ; jamais le dernier jour entier."""
    boundaries = [i for i in range(1, len(rows)) if str(rows[i]["date"])[:10] != str(rows[i - 1]["date"])[:10]]
    if not boundaries:
        return max(1, int(len(rows) * fraction))
    target = int(len(rows) * fraction)
    return min(boundaries, key=lambda i: (abs(i - target), i))


def archive_walk_forward(records: list[dict], *, fractions: tuple[float, ...] = (0.6, 0.8, 1.0),
                         max_candidates: int = core.DEFAULT_MAX_CANDIDATES, repetitions: int = 1000, seed: int = 20261018) -> dict[str, Any]:
    clean, rejected = core._clean_records(records)
    feature_map = {str(r["match_id"]): build_features(r) for r in clean}
    folds = []
    for fraction in fractions:
        prefix = clean[:core._date_aligned_prefix(clean, fraction)]
        train, validation, test = core._split_chronologically(prefix)
        scenarios = discover_scenarios(train, feature_map, max_candidates=max_candidates)
        arena = Arena(prefix, feature_map, scenarios, {"train": train, "validation": validation, "test": test})
        observed = pipeline_stats(arena, arena.Y)
        sel = arena.select(arena.Y)
        selected = np.nonzero(sel["selected"])[0]
        order = selected[np.argsort(-sel["validation"]["lift"][selected], kind="stable")]
        nulls = {}
        for name, strata in (("marche", market_strata(prefix, feature_map)), ("libre", league_strata(prefix))):
            null = nested_permutation(arena, strata, repetitions, seed + (0 if name == "marche" else 1))
            nulls[name] = compare_to_null(observed, null)
        folds.append({
            "fraction": fraction, "matches_in_prefix": len(prefix),
            "split": {"train": len(train), "validation": len(validation), "test": len(test)},
            "test_days": sorted({str(r["date"])[:10] for r in test})[:1] + sorted({str(r["date"])[:10] for r in test})[-1:],
            "scenarios_tested": len(scenarios), "distinct_rules": len(arena.rules),
            "selected": int(len(selected)), "observed": observed,
            "permutation_marche": nulls["marche"], "permutation_libre": nulls["libre"],
            "portfolio_test": portfolio_report(arena, arena.Y, "test", order),
        })
    return {"mode": "ARCHIVE_WALK_FORWARD_NESTED_PERMUTATION", "repetitions": repetitions, "folds": folds,
            "rejected": dict(rejected)}


# ------------------------------------------------------------------------------------------------
# Walk-forward mensuel sur Football-Data (taux de base, sans cotes)
# ------------------------------------------------------------------------------------------------

def football_data_walk_forward(records: list[dict], *, test_months: list[str], max_candidates: int = core.DEFAULT_MAX_CANDIDATES,
                               repetitions: int = 200, seed: int = 20261019, train_fraction: float = 0.75,
                               progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Chaque mois de test est prédit avec des règles découvertes et choisies UNIQUEMENT sur les matchs
    antérieurs au premier jour du mois (découverte sur les 75 % les plus anciens, validation sur le reste)."""
    ordered = sorted(records, key=lambda r: (str(r["date"]), str(r["match_id"])))
    feature_map = {str(r["match_id"]): build_features(r) for r in ordered}
    folds = []
    for k, month in enumerate(test_months):
        start = f"{month}-01"
        pre = [r for r in ordered if str(r["date"]) < start]
        test = [r for r in ordered if str(r["date"])[:7] == month]
        cut = _date_cut(pre, train_fraction)
        train, validation = pre[:cut], pre[cut:]
        scenarios = discover_scenarios(train, feature_map, max_candidates=max_candidates)
        arena = Arena(pre + test, feature_map, scenarios, {"train": train, "validation": validation, "test": test})
        observed = pipeline_stats(arena, arena.Y)
        sel = arena.select(arena.Y)
        selected = np.nonzero(sel["selected"])[0]
        order = selected[np.argsort(-sel["validation"]["lift"][selected], kind="stable")]
        null = nested_permutation(arena, league_strata(pre + test), repetitions, seed + k)
        folds.append({
            "month": month, "split": {"train": len(train), "validation": len(validation), "test": len(test)},
            "train_last_day": str(train[-1]["date"])[:10], "validation_last_day": str(validation[-1]["date"])[:10],
            "scenarios_tested": len(scenarios), "distinct_rules": len(arena.rules), "selected": int(len(selected)),
            "observed": observed, "permutation_libre": compare_to_null(observed, null),
            "portfolio_test": portfolio_report(arena, arena.Y, "test", order, min_group_n=10),
            "_null": {key: value.tolist() for key, value in null.items()},
        })
        if progress:
            p_fold = folds[-1]["permutation_libre"]["mean_test_lift"]["p"]
            progress(f"{month}: sélectionnés={len(selected)} gain moyen test={observed['mean_test_lift']:+.4f} p={'n/a' if p_fold is None else f'{p_fold:.3f}'}")
    # Statistique poolée : moyenne des folds ; loi nulle = moyenne des tirages de même rang (plis permutés séparément).
    pooled = {}
    for key in ("mean_test_lift", "portfolio_excess"):
        used = [f for f in folds if f["selected"] > 0]
        stack = np.array([np.where(np.array(f["_null"]["selected"]) > 0, np.array(f["_null"][key]), np.nan) for f in used])
        with np.errstate(all="ignore"):
            null = np.nanmean(stack, axis=0) if len(used) else np.array([])
        null = null[np.isfinite(null)]
        obs = float(np.mean([f["observed"][key] for f in used])) if used else None
        pooled[key] = {"observed": obs, "folds_used": len(used), "null_draws": int(len(null)),
                       "null_mean": float(null.mean()) if len(null) else None,
                       "null_p95": float(np.percentile(null, 95)) if len(null) else None,
                       "p": p_value(obs, null) if len(null) and obs is not None else None}
    for f in folds:
        del f["_null"]
    significant = sum(1 for f in folds if (f["permutation_libre"]["mean_test_lift"]["p"] or 1.0) <= 0.05)
    return {"mode": "FOOTBALL_DATA_MONTHLY_WALK_FORWARD", "repetitions": repetitions, "folds": folds, "pooled": pooled,
            "folds_with_p_le_0_05": significant,
            "note": "Plis à fenêtre croissante : leurs données d'apprentissage se recoupent, donc la statistique poolée est indicative. Pas de cotes : aucun ROI."}


# ------------------------------------------------------------------------------------------------
# Règles gelées sur Football-Data, évaluées sur l'archive du run (jamais vue)
# ------------------------------------------------------------------------------------------------

def freeze_rules(records: list[dict], *, cutoff: str, max_candidates: int = core.DEFAULT_MAX_CANDIDATES,
                 train_fraction: float = 0.75) -> dict[str, Any]:
    """Découvre et choisit des règles sur les matchs du `cutoff` (inclus) ou avant, puis les fige."""
    pool = sorted((r for r in records if str(r["date"]) <= cutoff), key=lambda r: (str(r["date"]), str(r["match_id"])))
    feature_map = {str(r["match_id"]): build_features(r) for r in pool}
    cut = _date_cut(pool, train_fraction)
    train, validation = pool[:cut], pool[cut:]
    scenarios = discover_scenarios(train, feature_map, max_candidates=max_candidates)
    arena = Arena(pool, feature_map, scenarios, {"train": train, "validation": validation, "test": []})
    sel = arena.select(arena.Y, need_test=False)
    chosen = np.nonzero(sel["selected"])[0]
    chosen = chosen[np.argsort(-sel["validation"]["lift"][chosen], kind="stable")]
    frozen = [{
        "conditions": scenarios[k]["conditions"], "target": scenarios[k]["target"], "complexity": scenarios[k].get("complexity"),
        "priority_validation_lift": float(sel["validation"]["lift"][k]), "q_bh_train": float(sel["q"][k]),
        "train_n": int(sel["train"]["n"][k]), "validation_n": int(sel["validation"]["n"][k]),
    } for k in chosen]
    return {"cutoff": cutoff, "matches_used": len(pool), "train": len(train), "validation": len(validation),
            "last_train_day": str(train[-1]["date"])[:10], "last_validation_day": str(validation[-1]["date"])[:10],
            "scenarios_tested": len(scenarios), "distinct_rules": len(arena.rules), "frozen": frozen}


def evaluate_frozen(frozen: list[dict], records: list[dict], *, repetitions: int = 2000, seed: int = 20261020,
                    min_support: int = MIN_EVAL_SUPPORT, top: int = 25) -> dict[str, Any]:
    """Évalue des règles gelées sur un échantillon qu'elles n'ont jamais vu, avec correction max-T.

    La famille testée est définie par les EFFECTIFS (nombre de matchs déclenchés ≥ `min_support`), jamais par
    un résultat. Pour chaque règle, la p-value ajustée est la part des permutations dont le MEILLEUR score de
    toute la famille atteint le sien (Westfall-Young) : elle tient compte du nombre de règles et de leur
    corrélation (mêmes matchs, 16 marchés liés).
    """
    clean, rejected = core._clean_records(records)
    feature_map = {str(r["match_id"]): build_features(r) for r in clean}
    scenarios = [{"conditions": f["conditions"], "target": f["target"]} for f in frozen]
    arena = Arena(clean, feature_map, scenarios, {"all": clean})
    obs = arena.table(arena.Y, "all")
    family = obs["n"] >= min_support
    roi_family = family & (obs["settled"] >= MIN_SETTLED_FOR_ROI) if arena.has_odds else np.zeros(len(family), dtype=bool)
    groups_marche, groups_libre = _groups(market_strata(clean, feature_map)), _groups(league_strata(clean))
    result: dict[str, Any] = {
        "matches": len(clean), "rejected": dict(rejected), "frozen_scenarios": len(frozen),
        "family_size_lift": int(family.sum()), "family_size_roi": int(roi_family.sum()),
        "span_days": len({str(r["date"])[:10] for r in clean}),
        "first_day": min(str(r["date"])[:10] for r in clean) if clean else None,
        "last_day": max(str(r["date"])[:10] for r in clean) if clean else None,
    }
    priority_order = np.arange(len(frozen))  # `frozen` est déjà trié par priorité décroissante (validation seule)
    for name, groups in (("marche", groups_marche), ("libre", groups_libre)):
        rng = np.random.default_rng(seed + (0 if name == "marche" else 1))
        max_z, max_t, mean_lift, mean_roi, port_roi, port_excess = [], [], [], [], [], []
        eligible = priority_order[family]
        positions, chosen = arena.pick_one_bet(eligible, "all", require_odds=arena.has_odds)
        for _ in range(repetitions):
            Yp = permuted(arena.Y, groups, rng)
            tab = arena.table(Yp, "all")
            max_z.append(np.nanmax(tab["z_lift"][family]) if family.any() else -np.inf)
            mean_lift.append(np.nanmean(tab["lift"][family]) if family.any() else 0.0)
            if roi_family.any():
                max_t.append(np.nanmax(tab["t_roi"][roi_family]))
                mean_roi.append(np.nanmean(tab["roi"][roi_family]))
            if len(positions):
                pk = arena.picks(Yp, "all", positions, chosen)
                port_excess.append(float(np.mean(pk["excess"])))
                if arena.has_odds and np.isfinite(pk["roi"]).any():
                    port_roi.append(float(np.nanmean(pk["roi"])))
        max_z, max_t = np.array(max_z), np.array(max_t)
        adj_lift = np.array([p_value(z, max_z) if fam and np.isfinite(z) else np.nan for z, fam in zip(obs["z_lift"], family)])
        adj_roi = np.array([p_value(t, max_t) if fam and np.isfinite(t) else np.nan for t, fam in zip(obs["t_roi"], roi_family)]) if arena.has_odds else np.full(len(family), np.nan)
        block = {
            "mean_lift": {"observed": float(np.nanmean(obs["lift"][family])) if family.any() else None,
                          "p": p_value(float(np.nanmean(obs["lift"][family])), np.array(mean_lift)) if family.any() else None},
            "scenarios_adjusted_p_lift_le_0_05": int(np.sum(adj_lift <= 0.05)),
            "max_z_lift": {"observed": float(np.nanmax(obs["z_lift"][family])) if family.any() else None,
                           "null_p95": float(np.percentile(max_z, 95)) if len(max_z) else None},
        }
        if arena.has_odds and roi_family.any():
            block["mean_roi"] = {"observed": float(np.nanmean(obs["roi"][roi_family])), "null_mean": float(np.mean(mean_roi)),
                                 "p": p_value(float(np.nanmean(obs["roi"][roi_family])), np.array(mean_roi))}
            block["scenarios_adjusted_p_roi_le_0_05"] = int(np.sum(adj_roi <= 0.05))
            t_family = obs["t_roi"][roi_family]
            block["max_t_roi"] = {"observed": float(np.nanmax(t_family)) if np.isfinite(t_family).any() else None,
                                  "null_p95": float(np.percentile(max_t, 95))}
        if len(positions):
            pk = arena.picks(arena.Y, "all", positions, chosen)
            block["portfolio_excess"] = {"observed": float(np.mean(pk["excess"])), "p": p_value(float(np.mean(pk["excess"])), np.array(port_excess))}
            if arena.has_odds and np.isfinite(pk["roi"]).any():
                block["portfolio_roi"] = {"observed": float(np.nanmean(pk["roi"])), "null_mean": float(np.mean(port_roi)),
                                          "null_p95": float(np.percentile(port_roi, 95)), "p": p_value(float(np.nanmean(pk["roi"])), np.array(port_roi))}
        result[f"permutation_{name}"] = block
        result[f"_adj_{name}"] = (adj_lift, adj_roi)
    result["portfolio"] = portfolio_report(arena, arena.Y, "all", priority_order[family], min_group_n=15)
    result["portfolio_by_date_block"] = _date_blocks(arena, arena.Y, priority_order[family])
    # meilleures règles : par z (taux de base) et par t (ROI), avec p ajustées max-T sous la loi nulle du marché
    adj_lift, adj_roi = result.pop("_adj_marche")
    result.pop("_adj_libre")
    rows = []
    for k in range(len(frozen)):
        if not family[k]:
            continue
        row = {"conditions": frozen[k]["conditions"], "target": frozen[k]["target"], "complexity": frozen[k]["complexity"],
               "priority_validation_lift": frozen[k]["priority_validation_lift"], "n": int(obs["n"][k]),
               "hit_rate": float(obs["hit"][k]), "base_rate": float(obs["base"][k]), "lift": float(obs["lift"][k]),
               "z_lift": float(obs["z_lift"][k]), "p_adj_lift_marche": float(adj_lift[k])}
        if arena.has_odds:
            row.update({"settled": int(obs["settled"][k]), "roi": float(obs["roi"][k]) if np.isfinite(obs["roi"][k]) else None,
                        "t_roi": float(obs["t_roi"][k]) if np.isfinite(obs["t_roi"][k]) else None,
                        "p_adj_roi_marche": float(adj_roi[k]) if np.isfinite(adj_roi[k]) else None})
        rows.append(row)
    result["best_by_lift"] = sorted(rows, key=lambda r: -r["z_lift"])[:top]
    if arena.has_odds:
        result["best_by_roi"] = sorted((r for r in rows if r.get("t_roi") is not None), key=lambda r: -r["t_roi"])[:top]
    return result


def _date_blocks(arena: Arena, Y: np.ndarray, ordered: np.ndarray, blocks: int = 3) -> list[dict]:
    """Découpe l'échantillon indépendant en blocs chronologiques contigus (par jours entiers) et mesure
    le portefeuille un-pari-par-match dans chacun : stabilité dans le temps."""
    idx = arena.idx["all"]
    days = sorted({str(d) for d in arena.days[idx]})
    if len(days) < blocks:
        return []
    out = []
    positions, chosen = arena.pick_one_bet(ordered, "all", require_odds=arena.has_odds)
    picks = arena.picks(Y, "all", positions, chosen)
    edges = [days[round(i * len(days) / blocks)] for i in range(blocks)] + [days[-1] + "~"]
    for b in range(blocks):
        keep = (picks["day"] >= edges[b]) & (picks["day"] < edges[b + 1])
        row = {"from": edges[b], "to": days[min(len(days) - 1, round((b + 1) * len(days) / blocks) - 1)], "picks": int(keep.sum())}
        if keep.any():
            row["excess_over_base"] = float(picks["excess"][keep].mean())
            if arena.has_odds and np.isfinite(picks["roi"][keep]).any():
                row["roi"] = float(np.nanmean(picks["roi"][keep]))
        out.append(row)
    return out


# ------------------------------------------------------------------------------------------------
# Décision : preuve de rentabilité indépendante ? (critères fixés avant les résultats)
# ------------------------------------------------------------------------------------------------

def decide_verdict(transfer: dict[str, Any] | None) -> dict[str, Any]:
    """Applique les critères de preuve. Retourne le verdict ET chaque critère, pour que rien ne soit implicite."""
    criteria = {
        "echantillon_independant_et_gele": transfer is not None,
        "paris_regles_min": False, "duree_min_jours": False, "roi_positif": False,
        "ic95_bootstrap_roi_exclut_zero": False, "p_permutation_marche": False, "stabilite_dans_le_temps": False,
    }
    detail: dict[str, Any] = {"required": {"settled_picks": PROOF_MIN_SETTLED_PICKS, "span_days": PROOF_MIN_SPAN_DAYS,
                                           "positive_block_share": PROOF_MIN_POSITIVE_BLOCK_SHARE, "alpha": PROOF_ALPHA}}
    if transfer:
        port = transfer.get("portfolio", {})
        roi = port.get("roi") or {}
        criteria["paris_regles_min"] = (port.get("settled_bets") or 0) >= PROOF_MIN_SETTLED_PICKS
        criteria["duree_min_jours"] = (transfer.get("span_days") or 0) >= PROOF_MIN_SPAN_DAYS
        criteria["roi_positif"] = (roi.get("mean") or -1) > 0
        criteria["ic95_bootstrap_roi_exclut_zero"] = bool(roi.get("ci95") and roi["ci95"][0] > 0)
        p_roi = (transfer.get("permutation_marche", {}).get("portfolio_roi") or {}).get("p")
        criteria["p_permutation_marche"] = p_roi is not None and p_roi <= PROOF_ALPHA
        blocks = [b for b in transfer.get("portfolio_by_date_block", []) if "roi" in b]
        if blocks:
            share = sum(b["roi"] > 0 for b in blocks) / len(blocks)
            criteria["stabilite_dans_le_temps"] = share >= PROOF_MIN_POSITIVE_BLOCK_SHARE
            detail["positive_block_share"] = share
        detail.update({"settled_bets": port.get("settled_bets"), "span_days": transfer.get("span_days"), "roi": roi, "p_roi_marche": p_roi})
    if all(criteria.values()):
        verdict = "PREUVE_DE_RENTABILITE_INDEPENDANTE"
    elif not criteria["duree_min_jours"] or not criteria["paris_regles_min"]:
        verdict = "DONNEES_INSUFFISANTES"
    elif not criteria["roi_positif"]:
        verdict = "NON_RENTABLE"
    else:
        verdict = "NON_CONCLUANT"
    return {"verdict": verdict, "criteria": criteria, "detail": detail}
