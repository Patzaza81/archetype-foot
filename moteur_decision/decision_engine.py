# -*- coding: utf-8 -*-
"""Couche de décision adaptative V1.

Elle ne fabrique aucune probabilité. Elle reçoit des opportunités déjà
évaluées et choisit un ensemble compatible avec les contraintes de risque.
Aucun classement global ni P1/P2/P3 fixe.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Sequence
from .risk_engine import deduplicate_candidates, exposure_group

@dataclass(frozen=True)
class Decision:
    market: str
    probability: float
    odds: float
    edge: float
    edv: float
    market_family: str
    exposure_group: str
    action: str
    justification_code: str

def _candidate(c):
    return Decision(
        market=c["market"], probability=c["probability"], odds=c["odds"],
        edge=c["edge"], edv=c["edv"],
        market_family=c.get("market_family") or exposure_group(c["market"]),
        exposure_group=c.get("exposure_group") or exposure_group(c["market"]),
        action="SELECTION",
        justification_code=c.get("justification_code") or "JUSTIFICATION_INSUFFISANTE",
    )

def decide(candidates: Sequence[Mapping], max_selections: int = 3):
    if max_selections < 1:
        raise ValueError("max_selections doit être positif")
    valid=[c for c in candidates if c.get("eligible") and c.get("justification_code")]
    # Une justification absente ne devient jamais artificiellement favorable.
    valid=[c for c in valid if c.get("justification_code")!="JUSTIFICATION_INSUFFISANTE"]
    valid=sorted(valid,key=lambda c:(float(c["edv"]),float(c["probability"]),float(c["edge"])),reverse=True)
    selected=[]
    used=set()
    for c in valid:
        d=_candidate(c)
        key=(d.market_family,d.exposure_group)
        if key in used:
            continue
        selected.append(d); used.add(key)
        if len(selected)>=max_selections:
            break
    return selected
