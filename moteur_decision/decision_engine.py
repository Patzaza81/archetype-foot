# -*- coding: utf-8 -*-
"""Politique de décision adaptative du noyau V1.

Le moteur ne fabrique ni probabilité ni valeur. Il reçoit des opportunités
déjà validées et construit un petit ensemble d'opportunités compatibles.

Principes:
- aucune hiérarchie P1/P2/P3;
- une opportunité par exposition concurrente;
- au maximum trois opportunités, mais moins si le marché ne le justifie pas;
- le choix à l'intérieur d'un même groupe est déterministe: EDV, puis
  probabilité, puis edge;
- les conflits explicitement déclarés par le moteur de marchés sont respectés;
- aucune combinaison de paris n'est fabriquée ici: les cotes jointes et la
  gestion de mise appartiennent à une couche portefeuille ultérieure.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Sequence

from .risk_engine import exposure_group


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
        market=str(c["market"]),
        probability=float(c["probability"]),
        odds=float(c["odds"]),
        edge=float(c["edge"]),
        edv=float(c["edv"]),
        market_family=c.get("market_family") or exposure_group(str(c["market"])),
        exposure_group=c.get("exposure_group") or exposure_group(str(c["market"])),
        action="SELECTION_SEPAREE",
        justification_code=c.get("justification_code") or "JUSTIFICATION_INSUFFISANTE",
    )


def _rank_within_exposure(c):
    """Ordre explicite uniquement pour départager des marchés concurrents."""
    return (float(c["edv"]), float(c["probability"]), float(c["edge"]), str(c["market"]))


def _conflicts(candidate, selected):
    conflicts = set(candidate.get("conflicts_with") or ())
    if not conflicts:
        return False
    selected_markets = {str(x.market) for x in selected}
    return bool(conflicts & selected_markets)


def decide(candidates: Sequence[Mapping], max_selections: int = 3):
    if max_selections < 1:
        raise ValueError("max_selections doit être positif")

    valid = []
    for c in candidates:
        if not c.get("eligible"):
            continue
        if c.get("justification_code") in (None, "", "JUSTIFICATION_INSUFFISANTE"):
            continue
        try:
            d = _candidate(c)
        except (KeyError, TypeError, ValueError):
            continue
        if d.probability < 0.60 or d.odds < 1.26 or d.odds > 1.74:
            continue
        valid.append(c)

    # Une seule opportunité est retenue dans une même exposition concurrente.
    # Ce n'est pas une perte silencieuse: on conserve les autres candidats
    # comme alternatives dans le diagnostic appelant.
    by_group = {}
    for c in valid:
        group = c.get("exposure_group") or exposure_group(str(c["market"]))
        by_group.setdefault(group, []).append(c)

    representatives = []
    for group, rows in by_group.items():
        representatives.append(max(rows, key=_rank_within_exposure))

    # Les groupes différents sont traités comme des opportunités distinctes.
    # Les conflits explicites priment sur la simple différence de groupe.
    representatives.sort(key=_rank_within_exposure, reverse=True)

    selected = []
    for c in representatives:
        if _conflicts(c, selected):
            continue
        selected.append(_candidate(c))
        if len(selected) >= max_selections:
            break

    return selected
