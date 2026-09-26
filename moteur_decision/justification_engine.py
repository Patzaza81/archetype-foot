# -*- coding: utf-8 -*-
"""Justifications déterministes fondées sur les observations réellement fournies.

Ce module ne décide pas si une opportunité est rentable. Il cherche seulement
des faits qui expliquent le marché. Si aucun fait pertinent n'est disponible,
le code obligatoire est JUSTIFICATION_INSUFFISANTE.
"""
from __future__ import annotations

def _avg(rows,key):
    vals=[float(r[key]) for r in rows if isinstance(r.get(key),(int,float)) and not isinstance(r.get(key),bool)]
    return sum(vals)/len(vals) if vals else None

def explain_market(market, home_rows, away_rows):
    code="JUSTIFICATION_INSUFFISANTE"
    facts=[]
    if "btts" in market:
        hg=sum(1 for r in home_rows if r.get("buts_marques",0)>0)
        ag=sum(1 for r in away_rows if r.get("buts_marques",0)>0)
        if home_rows and away_rows:
            facts.append(f"domicile marque dans {hg}/{len(home_rows)} matchs; extérieur marque dans {ag}/{len(away_rows)}")
            if hg>=max(1,len(home_rows)*0.7) and ag>=max(1,len(away_rows)*0.7):
                code="BTTS_SOUTENU_PAR_FREQUENCE_BUTS"
    elif market.startswith("over_") or market.startswith("under_"):
        g1=_avg(home_rows,"buts_marques"); g2=_avg(away_rows,"buts_marques")
        if g1 is not None and g2 is not None:
            facts.append(f"moyennes buts marqués: domicile {g1:.2f}, extérieur {g2:.2f}")
            code="TOTAL_SOUTENU_PAR_PROFIL_OFFENSIF"
    elif market in {"victoire","defaite","nul"}:
        g1=_avg(home_rows,"buts_marques"); g2=_avg(away_rows,"buts_marques")
        if g1 is not None and g2 is not None:
            facts.append(f"production offensive contextuelle: domicile {g1:.2f}, extérieur {g2:.2f}")
            code="RESULTAT_SOUTENU_PAR_DONNEES_CONTEXTUELLES"
    elif "buts_dom_" in market:
        g=_avg(home_rows,"buts_marques")
        if g is not None:
            facts.append(f"domicile marque {g:.2f} but/match dans son contexte")
            code="BUTS_DOM_SOUTENUS_PAR_HISTORIQUE"
    elif "buts_ext_" in market:
        g=_avg(away_rows,"buts_marques")
        if g is not None:
            facts.append(f"extérieur marque {g:.2f} but/match dans son contexte")
            code="BUTS_EXT_SOUTENUS_PAR_HISTORIQUE"
    return {"code":code,"facts":facts}

def require_justification(market, home_rows, away_rows):
    result=explain_market(market,home_rows,away_rows)
    if result["code"]=="JUSTIFICATION_INSUFFISANTE":
        return result
    return result
