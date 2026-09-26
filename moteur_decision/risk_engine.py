# -*- coding: utf-8 -*-
"""Contrôles de stabilité et d'exposition du noyau V1."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RiskAssessment:
    dispersion: Optional[float]
    stability: str
    eligible: bool
    reasons: tuple[str, ...]


def coefficient_of_variation(values):
    vals = [float(v) for v in values
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    if mean <= 0:
        return None
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    return (variance ** 0.5 / mean) * 100.0


def assess_dispersion(values, probability: float) -> RiskAssessment:
    d = coefficient_of_variation(values)
    if d is None:
        return RiskAssessment(None, "INCONNUE", False, ("DISPERSION_INSUFFISANTE",))
    if d > 8:
        return RiskAssessment(d, "INSTABLE", False, ("DISPERSION_SUP_8",))
    if d > 5 and probability < 0.67:
        return RiskAssessment(
            d, "SOUS_CONTRAINTE", False,
            ("DISPERSION_5_8_ET_P_INF_67",)
        )
    return RiskAssessment(d, "STABLE" if d <= 5 else "SOUS_CONTRAINTE", True, ())


def exposure_group(market: str) -> str:
    m = market.lower()

    # Les résultats d'une même période sont concurrents entre eux.
    if m in {"victoire", "nul", "defaite"}:
        return "resultat_ft"
    if m.startswith("mi_temps_") and "dc_" not in m:
        return "resultat_mi_temps"
    if m.startswith("2e_mi_temps_") and "dc_" not in m:
        return "resultat_2e_mi_temps"

    if m.startswith("dc_"):
        return "double_chance_ft"
    if m.startswith("mi_temps_dc_"):
        return "double_chance_mi_temps"
    if m.startswith("2e_mi_temps_dc_"):
        return "double_chance_2e_mi_temps"

    if m.startswith("btts_"):
        return "btts_ft"
    if m.startswith("mi_temps_btts_"):
        return "btts_mi_temps"
    if m.startswith("2e_mi_temps_btts_"):
        return "btts_2e_mi_temps"

    if m.startswith("over_") or m.startswith("under_") or m.startswith("exact_goals_"):
        return "buts_total_ft"
    if m.startswith("mi_temps_over_") or m.startswith("mi_temps_under_"):
        return "buts_total_mi_temps"
    if m.startswith("2e_mi_temps_over_") or m.startswith("2e_mi_temps_under_"):
        return "buts_total_2e_mi_temps"

    if m.startswith("buts_dom_"):
        return "buts_domicile_ft"
    if m.startswith("buts_ext_"):
        return "buts_exterieur_ft"

    if m.startswith("handicap_3way_"):
        return "handicap_ft"
    if m.startswith("mi_temps_handicap_3way_"):
        return "handicap_mi_temps"
    if m.startswith("2e_mi_temps_handicap_3way_"):
        return "handicap_2e_mi_temps"

    if m.startswith("clean_sheet_dom"):
        return "clean_sheet_dom"
    if m.startswith("clean_sheet_ext"):
        return "clean_sheet_ext"
    if m.startswith("mi_temps_clean_sheet_"):
        return "clean_sheet_mi_temps"
    if m.startswith("2e_mi_temps_clean_sheet_"):
        return "clean_sheet_2e_mi_temps"

    return "autre"


def deduplicate_candidates(candidates):
    """Sépare représentants et conflits sans choisir silencieusement."""
    groups = {}
    conflicts = []
    for c in candidates:
        key = (
            c.get("market_family") or exposure_group(c["market"]),
            c.get("exposure_group") or exposure_group(c["market"]),
        )
        if key in groups:
            conflicts.append((groups[key], c))
        else:
            groups[key] = c
    return list(groups.values()), conflicts
