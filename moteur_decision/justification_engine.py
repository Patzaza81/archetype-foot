# -*- coding: utf-8 -*-
"""Justifications factuelles et spécifiques au marché."""
from __future__ import annotations

import re


def _avg(rows, key):
    vals = [
        float(r[key]) for r in rows
        if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)
    ]
    return sum(vals) / len(vals) if vals else None


def _frequency(rows, predicate):
    valid = [r for r in rows if isinstance(r, dict)]
    return sum(1 for r in valid if predicate(r)), len(valid)


def _pct(n, d):
    return 100.0 * n / d if d else None


def _threshold(market, prefix):
    m = re.search(rf"^{prefix}_(\d+)_(\d+)$", market)
    return (int(m.group(1)) + int(m.group(2)) / 10.0) if m else None


def _half_keys(market):
    if market.startswith("mi_temps_"):
        return market[len("mi_temps_"):], "buts_marques_mi_temps", "buts_encaisses_mi_temps"
    if market.startswith("2e_mi_temps_"):
        return market[len("2e_mi_temps_"):], "buts_marques_2e_mi_temps", "buts_encaisses_2e_mi_temps"
    return market, "buts_marques", "buts_encaisses"


def _result_frequency(rows, outcome, half=False):
    gf_key = "buts_marques_mi_temps" if half else "buts_marques"
    ga_key = "buts_encaisses_mi_temps" if half else "buts_encaisses"
    valid = [
        r for r in rows
        if isinstance(r.get(gf_key), (int, float))
        and isinstance(r.get(ga_key), (int, float))
    ]
    if outcome == "victoire":
        n = sum(float(r[gf_key]) > float(r[ga_key]) for r in valid)
    elif outcome == "nul":
        n = sum(float(r[gf_key]) == float(r[ga_key]) for r in valid)
    else:
        n = sum(float(r[gf_key]) < float(r[ga_key]) for r in valid)
    return n, len(valid)


def explain_market(market, home_rows, away_rows):
    """Retourne une justification seulement si une preuve directement liée au marché existe."""
    m = market.lower()
    code = "JUSTIFICATION_INSUFFISANTE"
    facts = []

    # Résultat et double chance: la fréquence correspond exactement à l'issue.
    if m in {"victoire", "nul", "defaite"}:
        hw, hn = _result_frequency(home_rows, m)
        aw, an = _result_frequency(away_rows, "victoire" if m == "victoire" else
                                   "nul" if m == "nul" else "defaite")
        if hn and an:
            facts.append(
                f"issue sélectionnée observée: domicile {hw}/{hn} ({_pct(hw,hn):.0f}%), "
                f"extérieur {aw}/{an} ({_pct(aw,an):.0f}%)"
            )
            code = "RESULTAT_SOUTENU_PAR_FREQUENCE_RESULTAT"

    elif m.startswith("dc_"):
        target = {"dc_1x": {"victoire", "nul"}, "dc_x2": {"nul", "defaite"},
                  "dc_12": {"victoire", "defaite"}}.get(m)
        if target:
            def dc(rows):
                vals = [_result_frequency(rows, x) for x in target]
                n = sum(x[0] for x in vals)
                d = vals[0][1] if vals else 0
                return n, d
            hn, hd = dc(home_rows)
            an, ad = dc(away_rows)
            if hd and ad:
                facts.append(
                    f"double chance {m[3:]} observée: domicile {hn}/{hd} ({_pct(hn,hd):.0f}%), "
                    f"extérieur {an}/{ad} ({_pct(an,ad):.0f}%)"
                )
                code = "DOUBLE_CHANCE_SOUTENUE_PAR_FREQUENCE"

    # BTTS: les deux équipes doivent avoir marqué dans le même match.
    elif "btts" in m:
        half = m.startswith("mi_temps_") or m.startswith("2e_mi_temps_")
        gf = "buts_marques_mi_temps" if m.startswith("mi_temps_") else "buts_marques"
        ga = "buts_encaisses_mi_temps" if m.startswith("mi_temps_") else "buts_encaisses"
        if m.startswith("2e_mi_temps_"):
            # Les données seconde mi-temps ne sont pas stockées directement.
            return {"code": code, "facts": facts}
        def bt(rows):
            valid=[r for r in rows if isinstance(r.get(gf),(int,float)) and isinstance(r.get(ga),(int,float))]
            n=sum(float(r[gf])>0 and float(r[ga])>0 for r in valid)
            return n,len(valid)
        hn,hd=bt(home_rows); an,ad=bt(away_rows)
        if hd and ad:
            facts.append(
                f"BTTS observé: domicile {hn}/{hd} ({_pct(hn,hd):.0f}%), "
                f"extérieur {an}/{ad} ({_pct(an,ad):.0f}%)"
            )
            code="BTTS_SOUTENU_PAR_FREQUENCE_DIRECTE"

    # Totaux exacts: la ligne du marché est recherchée dans les observations.
    elif m.startswith("over_") or m.startswith("under_"):
        line = _threshold(m, "over") if m.startswith("over_") else _threshold(m, "under")
        if line is not None:
            def total_freq(rows):
                valid=[r for r in rows if isinstance(r.get("buts_marques"),(int,float)) and isinstance(r.get("buts_encaisses"),(int,float))]
                n=sum((float(r["buts_marques"])+float(r["buts_encaisses"]) > line) if m.startswith("over_")
                      else (float(r["buts_marques"])+float(r["buts_encaisses"]) < line) for r in valid)
                return n,len(valid)
            hn,hd=total_freq(home_rows); an,ad=total_freq(away_rows)
            if hd and ad:
                facts.append(
                    f"{m} observé: domicile {hn}/{hd} ({_pct(hn,hd):.0f}%), "
                    f"extérieur {an}/{ad} ({_pct(an,ad):.0f}%)"
                )
                code="TOTAL_LIGNE_SOUTENU_PAR_FREQUENCE_DIRECTE"

    elif m.startswith("exact_goals_"):
        suffix=m[len("exact_goals_"):]
        target=6 if suffix=="6_plus" else int(suffix) if suffix.isdigit() else None
        if target is not None:
            def exact(rows):
                valid=[r for r in rows if isinstance(r.get("buts_marques"),(int,float)) and isinstance(r.get("buts_encaisses"),(int,float))]
                n=sum((float(r["buts_marques"])+float(r["buts_encaisses"]) >= 6) if target==6
                      else (float(r["buts_marques"])+float(r["buts_encaisses"]) == target) for r in valid)
                return n,len(valid)
            hn,hd=exact(home_rows); an,ad=exact(away_rows)
            if hd and ad:
                facts.append(
                    f"total exact sélectionné observé: domicile {hn}/{hd} ({_pct(hn,hd):.0f}%), "
                    f"extérieur {an}/{ad} ({_pct(an,ad):.0f}%)"
                )
                code="TOTAL_EXACT_SOUTENU_PAR_FREQUENCE"

    elif m.startswith("buts_dom_") or m.startswith("buts_ext_"):
        home = m.startswith("buts_dom_")
        rows = home_rows if home else away_rows
        side = "domicile" if home else "extérieur"
        prefix = "buts_dom_over" if home else "buts_ext_over"
        under_prefix = "buts_dom_under" if home else "buts_ext_under"
        over = m.startswith(prefix)
        line = _threshold(m, prefix) if over else _threshold(m, under_prefix)
        if line is not None:
            valid=[r for r in rows if isinstance(r.get("buts_marques"),(int,float))]
            n=sum(float(r["buts_marques"]) > line if over else float(r["buts_marques"]) < line for r in valid)
            if valid:
                facts.append(f"{m}: {side} {n}/{len(valid)} ({_pct(n,len(valid)):.0f}%)")
                code="BUTS_EQUIPE_SOUTENUS_PAR_FREQUENCE_LIGNE"

    elif "clean_sheet" in m:
        half = m.startswith("mi_temps_")
        if m.startswith("2e_mi_temps_"):
            return {"code": code, "facts": facts}
        key = "buts_encaisses_mi_temps" if half else "buts_encaisses"
        rows = home_rows if "clean_sheet_dom" in m else away_rows
        valid=[r for r in rows if isinstance(r.get(key),(int,float))]
        if valid:
            n=sum(float(r[key])==0 for r in valid)
            facts.append(f"cage inviolée dans {n}/{len(valid)} ({_pct(n,len(valid)):.0f}%)")
            code="CLEAN_SHEET_SOUTENU_PAR_FREQUENCE"

    elif "handicap_3way" in m:
        match = re.search(r"handicap_3way_(\d+(?:\.\d+)?)_(dom|nul|ext)$", m)
        if match:
            line=float(match.group(1)); outcome=match.group(2)
            valid_h=[r for r in home_rows if isinstance(r.get("buts_marques"),(int,float)) and isinstance(r.get("buts_encaisses"),(int,float))]
            valid_a=[r for r in away_rows if isinstance(r.get("buts_marques"),(int,float)) and isinstance(r.get("buts_encaisses"),(int,float))]
            if valid_h and valid_a:
                # Proxy strictement descriptif: écart de buts du contexte
                # correspondant à la ligne BetPawa, sans prétendre reconstruire
                # le résultat contre les adversaires futurs.
                hg=sum(float(r["buts_marques"])-float(r["buts_encaisses"]) > line for r in valid_h)
                ag=sum(float(r["buts_encaisses"])-float(r["buts_marques"]) >= line for r in valid_a)
                facts.append(
                    f"ligne handicap {line:g} choisie; écarts contextuels: "
                    f"domicile {hg}/{len(valid_h)} au-dessus de +{line:g}, "
                    f"extérieur {ag}/{len(valid_a)} à au moins +{line:g}"
                )
                code="HANDICAP_SOUTENU_PAR_ECART_CONTEXTUEL"

    return {"code": code, "facts": facts}


def require_justification(market, home_rows, away_rows):
    return explain_market(market, home_rows, away_rows)
