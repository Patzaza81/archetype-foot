# -*- coding: utf-8 -*-
"""Justifications factuelles, spécifiques au marché sélectionné."""
from __future__ import annotations


def _avg(rows, key):
    vals = [
        float(r[key]) for r in rows
        if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)
    ]
    return sum(vals) / len(vals) if vals else None


def _frequency(rows, predicate):
    return (sum(1 for r in rows if predicate(r)), len(rows))


def _pct(n, d):
    return 100.0 * n / d if d else None


def explain_market(market, home_rows, away_rows):
    """Retourne uniquement des faits directement pertinents pour *market*."""
    m = market.lower()
    code = "JUSTIFICATION_INSUFFISANTE"
    facts = []

    # Résultats: on ne prétend pas prouver une victoire avec un seul chiffre;
    # on expose les productions offensive/défensive du contexte utilisé.
    if m in {"victoire", "nul", "defaite"}:
        hg = _avg(home_rows, "buts_marques")
        hd = _avg(home_rows, "buts_encaisses")
        ag = _avg(away_rows, "buts_marques")
        ad = _avg(away_rows, "buts_encaisses")
        if None not in (hg, hd, ag, ad):
            facts.append(
                f"contexte domicile: {hg:.2f} buts marqués et {hd:.2f} encaissés; "
                f"extérieur: {ag:.2f} marqués et {ad:.2f} encaissés"
            )
            code = "RESULTAT_SOUTENU_PAR_PROFIL_CONTEXTUEL"

    elif m.startswith("dc_"):
        hg = _avg(home_rows, "buts_marques")
        hd = _avg(home_rows, "buts_encaisses")
        ag = _avg(away_rows, "buts_marques")
        ad = _avg(away_rows, "buts_encaisses")
        if None not in (hg, hd, ag, ad):
            facts.append(
                f"profil contextuel: domicile {hg:.2f}/{hd:.2f} buts, "
                f"extérieur {ag:.2f}/{ad:.2f}"
            )
            code = "DOUBLE_CHANCE_SOUTENUE_PAR_PROFIL_CONTEXTUEL"

    elif "btts" in m:
        hg_n, hg_d = _frequency(home_rows, lambda r: float(r.get("buts_marques", 0)) > 0)
        ag_n, ag_d = _frequency(away_rows, lambda r: float(r.get("buts_marques", 0)) > 0)
        hga = _avg(home_rows, "buts_encaisses")
        aga = _avg(away_rows, "buts_encaisses")
        if hg_d and ag_d and hga is not None and aga is not None:
            facts.append(
                f"domicile marque dans {hg_n}/{hg_d} ({_pct(hg_n,hg_d):.0f}%) "
                f"et encaisse {hga:.2f}; extérieur marque dans {ag_n}/{ag_d} "
                f"({_pct(ag_n,ag_d):.0f}%) et encaisse {aga:.2f}"
            )
            code = "BTTS_SOUTENU_PAR_FREQUENCES_OFFENSIVES_DEFENSIVES"

    elif m.startswith("over_") or m.startswith("under_") or "exact_goals_" in m:
        hf = _avg(home_rows, "buts_marques")
        ha = _avg(home_rows, "buts_encaisses")
        af = _avg(away_rows, "buts_marques")
        aa = _avg(away_rows, "buts_encaisses")
        if None not in (hf, ha, af, aa):
            facts.append(
                f"total observé par contexte: domicile {hf+ha:.2f}, "
                f"extérieur {af+aa:.2f} buts/match"
            )
            code = "TOTAL_BUTS_SOUTENU_PAR_PROFIL_GOALS"

    elif m.startswith("buts_dom_"):
        gf = _avg(home_rows, "buts_marques")
        if gf is not None:
            facts.append(f"domicile marque {gf:.2f} but/match dans ses matchs à domicile")
            code = "BUTS_DOM_SOUTENUS_PAR_HISTORIQUE_OFFENSIF"

    elif m.startswith("buts_ext_"):
        gf = _avg(away_rows, "buts_marques")
        if gf is not None:
            facts.append(f"extérieur marque {gf:.2f} but/match dans ses matchs à l'extérieur")
            code = "BUTS_EXT_SOUTENUS_PAR_HISTORIQUE_OFFENSIF"

    elif "clean_sheet_dom" in m:
        n, d = _frequency(home_rows, lambda r: float(r.get("buts_encaisses", 0)) == 0)
        if d:
            facts.append(f"domicile garde sa cage inviolée dans {n}/{d} ({_pct(n,d):.0f}%)")
            code = "CLEAN_SHEET_DOM_SOUTENU_PAR_FREQUENCE"

    elif "clean_sheet_ext" in m:
        n, d = _frequency(away_rows, lambda r: float(r.get("buts_encaisses", 0)) == 0)
        if d:
            facts.append(f"extérieur garde sa cage inviolée dans {n}/{d} ({_pct(n,d):.0f}%)")
            code = "CLEAN_SHEET_EXT_SOUTENU_PAR_FREQUENCE"

    elif "handicap_3way" in m:
        # Le handicap exact est fourni par BetPawa; la justification reste
        # descriptive et ne réinterprète pas la ligne.
        hg = _avg(home_rows, "buts_marques")
        hd = _avg(home_rows, "buts_encaisses")
        ag = _avg(away_rows, "buts_marques")
        ad = _avg(away_rows, "buts_encaisses")
        if None not in (hg, hd, ag, ad):
            facts.append(
                f"écart moyen de contexte: domicile {hg-hd:+.2f}, "
                f"extérieur {ag-ad:+.2f} but/match"
            )
            code = "HANDICAP_SOUTENU_PAR_ECART_CONTEXTUEL"

    return {"code": code, "facts": facts}


def require_justification(market, home_rows, away_rows):
    return explain_market(market, home_rows, away_rows)
