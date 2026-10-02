from __future__ import annotations
from .journal_memoire import Historique

def regime(rows: list[Historique]):
    n = len(rows)
    if n < 3:
        return {"regime":"INSUFFISANT","niveau":"INSUFFISANT","echantillon":n,"frequence":None,"frequence_recente":None,"tendance":None,"sequence":[]}
    rows = sorted(rows, key=lambda x: x.date)
    recent = rows[-min(5, n):]
    base = rows[:-len(recent)] or rows
    p_recent = sum(r.resultat for r in recent) / len(recent)
    p_base = sum(r.resultat for r in base) / len(base)
    delta = p_recent - p_base
    sequence = ["O" if r.resultat else "N" for r in rows[-8:]]
    if n < 5: state = "EMERGENCE"
    elif delta >= 0.20 and p_recent >= 0.60: state = "RENFORCEMENT"
    elif delta <= -0.20 and p_recent <= 0.50: state = "AFFAIBLISSEMENT"
    elif p_recent >= 0.70 and abs(delta) < 0.15: state = "PERSISTANT"
    elif p_recent <= 0.30 and abs(delta) < 0.15: state = "RECURRENT"
    else: state = "NEUTRE"
    niveau = "SOLIDE" if n >= 20 else "EXPLOITABLE" if n >= 10 else "FAIBLE" if n >= 5 else "INSUFFISANT"
    return {"regime":state,"niveau":niveau,"echantillon":n,"frequence":round(sum(r.resultat for r in rows)/n,4),"frequence_recente":round(p_recent,4),"tendance":round(delta,4),"sequence":sequence}
