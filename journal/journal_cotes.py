from __future__ import annotations
from collections import defaultdict
from .journal_memoire import Historique

def tranche_cote(cote):
    if cote is None: return None
    c = float(cote)
    if c < 1.30: return "<1.30"
    if c < 1.50: return "1.30-1.49"
    if c < 1.75: return "1.50-1.74"
    if c < 2.00: return "1.75-1.99"
    if c < 2.50: return "2.00-2.49"
    if c < 3.00: return "2.50-2.99"
    return "3.00+"

def statistiques_prix(rows):
    groups = defaultdict(list)
    for row in rows:
        band = tranche_cote(row.cote)
        if band: groups[band].append(row.resultat)
    return {k: {"echantillon":len(v),"frequence":round(sum(v)/len(v),4)} for k,v in sorted(groups.items())}
