# -*- coding: utf-8 -*-
"""Contrôles de stabilité et de corrélation du noyau V1.

Ce module ne choisit jamais un pari. Il mesure les contraintes qui doivent
être respectées avant la couche de décision.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional

@dataclass(frozen=True)
class RiskAssessment:
    dispersion: Optional[float]
    stability: str
    eligible: bool
    reasons: tuple[str, ...]

def coefficient_of_variation(values):
    vals=[float(v) for v in values if isinstance(v,(int,float)) and not isinstance(v,bool)]
    if len(vals)<2:
        return None
    mean=sum(vals)/len(vals)
    if mean<=0:
        return None
    variance=sum((v-mean)**2 for v in vals)/len(vals)
    return (variance**0.5/mean)*100.0

def assess_dispersion(values, probability: float) -> RiskAssessment:
    d=coefficient_of_variation(values)
    if d is None:
        return RiskAssessment(None,"INCONNUE",False,("DISPERSION_INSUFFISANTE",))
    if d>8:
        return RiskAssessment(d,"INSTABLE",False,("DISPERSION_SUP_8",))
    if d>5 and probability<0.67:
        return RiskAssessment(d,"SOUS_CONTRAINTE",False,("DISPERSION_5_8_ET_P_INF_67",))
    return RiskAssessment(d,"STABLE" if d<=5 else "SOUS_CONTRAINTE",True,())

def exposure_group(market: str) -> str:
    m=market.lower()
    if "1x2" in m or m in {"victoire","nul","defaite"}: return "resultat"
    if "dc_" in m: return "double_chance"
    if "btts" in m: return "btts"
    if "over_" in m or "under_" in m or "exact_goals" in m: return "buts_total"
    if "buts_dom_" in m: return "buts_domicile"
    if "buts_ext_" in m: return "buts_exterieur"
    if "handicap_3way" in m: return "handicap"
    if "clean_sheet" in m: return "clean_sheet"
    if "mi_temps" in m or "2e_mi_temps" in m: return "mi_temps"
    return "autre"

def deduplicate_candidates(candidates):
    """Garde au maximum une opportunité par famille + groupe d'exposition.

    En cas d'égalité, aucune préférence arbitraire n'est introduite: les deux
    sont retournées comme conflit à traiter par la couche décision.
    """
    groups={}
    conflicts=[]
    for c in candidates:
        key=(c.get("market_family") or exposure_group(c["market"]), c.get("exposure_group") or exposure_group(c["market"]))
        if key in groups:
            conflicts.append((groups[key],c))
        else:
            groups[key]=c
    return list(groups.values()), conflicts
