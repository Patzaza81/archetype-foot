from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import re

@dataclass(frozen=True)
class Historique:
    date: str
    equipe: str
    championnat: str
    marche: str
    contexte: str
    resultat: bool
    cote: float | None = None

def _num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def evaluer_marche(marche: str, dom: float, ext: float):
    m = " ".join(str(marche).lower().replace("_", " ").split())
    total = dom + ext
    if m in {"1x2 - 1", "1x2 1", "victoire domicile"} or m.endswith(" - 1"): return dom > ext
    if m in {"1x2 - 2", "1x2 2", "victoire extérieur"} or m.endswith(" - 2"): return ext > dom
    if m in {"1x2 - x", "1x2 x", "match nul"} or m.endswith(" - x"): return dom == ext
    if "double chance - 1x" in m: return dom >= ext
    if "double chance - x2" in m: return ext >= dom
    if "double chance - 12" in m: return dom != ext
    if "btts - oui" in m: return dom > 0 and ext > 0
    if "btts - non" in m: return dom == 0 or ext == 0
    mm = re.search(r"(plus|over|moins|under) de?\s*([0-9]+(?:[.,][0-9]+)?)", m)
    if not mm: mm = re.search(r"(plus|over|moins|under)[ _-]*([0-9]+(?:[.,][0-9]+)?)", m)
    if mm:
        x = float(mm.group(2).replace(",", "."))
        return total > x if mm.group(1) in {"plus", "over"} else total < x
    if "équipe domicile" in m and "0.5" in m: return dom >= 1
    if "équipe extérieure" in m and "0.5" in m: return ext >= 1
    return None

def observations_depuis_match(e):
    score = e.get("score") or {}
    if not isinstance(score, dict): return []
    dom, ext = _num(score.get("buts_dom")), _num(score.get("buts_ext"))
    if dom is None or ext is None: return []
    markets = e.get("cotes_observees") or e.get("cotes_betpawa") or {}
    out = []
    for market, cote in markets.items():
        result = evaluer_marche(market, dom, ext)
        if result is None: continue
        try: c = float(cote)
        except (TypeError, ValueError): c = None
        out.append((market, bool(result), c))
    return out

def construire_historique(records: Iterable[dict], target_date: str | None = None):
    out = []
    for e in records:
        d = str(e.get("date") or "")
        if not d or (target_date and d >= target_date): continue
        for market, result, cote in observations_depuis_match(e):
            comp = " ".join(str(e.get("competition") or "").split())
            for team, ctx in ((e.get("domicile"), "DOMICILE"), (e.get("exterieur"), "EXTERIEUR")):
                if team:
                    out.append(Historique(d, str(team), comp, market, ctx, result, cote))
    out.sort(key=lambda x: x.date)
    return out

def resolve(records, team, market, competition=None, contexte=None, min_exact=3):
    rows = [r for r in records if r.equipe == team and r.marche == market]
    levels = []
    if competition and contexte:
        levels.append(("equipe+marche+competition+contexte", lambda r: r.championnat == competition and r.contexte == contexte))
    if contexte:
        levels.append(("equipe+marche+contexte", lambda r: r.contexte == contexte))
    if competition:
        levels.append(("equipe+marche+competition", lambda r: r.championnat == competition))
    levels.append(("equipe+marche", lambda r: True))
    for name, predicate in levels:
        sample = [r for r in rows if predicate(r)]
        if len(sample) >= min_exact: return name, sample
    return "insuffisant", []
