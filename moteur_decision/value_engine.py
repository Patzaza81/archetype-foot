# -*- coding: utf-8 -*-
"""Valeur calculée sur l'unique snapshot de cote disponible."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional

ODDS_MIN, ODDS_MAX = 1.26, 1.74

@dataclass(frozen=True)
class ValueResult:
    market: str
    probability: float
    odds: float
    implied_probability: float
    edge: float
    edv: float
    ev: float
    eligible: bool
    reason: str

def minimum_edv(probability: float) -> Optional[float]:
    if probability < .60: return None
    if probability < .63: return 12.0
    if probability < .67: return 10.0
    if probability < .71: return 7.0
    return 5.0

def evaluate_market(market: str, probability: float, odds: float, *, dispersion: Optional[float]=None) -> ValueResult:
    if not 0 < probability <= 1: raise ValueError("probabilité invalide")
    if odds <= 1: raise ValueError("cote invalide")
    implied=1.0/odds; edge=probability-implied; ev=odds*edge; edv=100.0*ev; threshold=minimum_edv(probability)
    reasons=[]; eligible=True
    if not ODDS_MIN <= odds <= ODDS_MAX: eligible=False; reasons.append("COTE_HORS_FENETRE")
    if threshold is None: eligible=False; reasons.append("PROBABILITE_INF_60")
    elif edv < threshold: eligible=False; reasons.append("EDV_INSUFFISANTE")
    if dispersion is not None and dispersion>8: eligible=False; reasons.append("DISPERSION_SUP_8")
    elif dispersion is not None and dispersion>5 and probability<.67:
        eligible=False; reasons.append("DISPERSION_REQUIERT_P_SUP_67")
    return ValueResult(market,probability,odds,implied,edge,edv,ev,eligible,"|".join(reasons) or "OK")

def filter_value_candidates(markets: Mapping[str,float], odds: Mapping[str,float], *, dispersion: Optional[float]=None):
    return [evaluate_market(k,p,float(odds[k]),dispersion=dispersion) for k,p in markets.items() if k in odds]
