from __future__ import annotations
from .journal_memoire import Historique

def _ewma(rows: list[Historique], alpha: float = 0.35):
    value = None
    for row in rows:
        x = 1.0 if row.resultat else 0.0
        value = x if value is None else alpha * x + (1.0 - alpha) * value
    return value

def regime(rows: list[Historique]):
    n = len(rows)
    if n < 3:
        return {"regime":"INSUFFISANT","niveau":"INSUFFISANT","echantillon":n,"frequence":None,"frequence_recente":None,"tendance":None,"sequence":[]}
    rows = sorted(rows, key=lambda x: x.date)
    recent = rows[-min(5, n):]
    base = rows[:-len(recent)]
    p_recent = _ewma(recent)
    p_base = _ewma(base) if base else p_recent
    delta = p_recent - p_base
    sequence = ["O" if r.resultat else "N" for r in rows[-8:]]
    if n < 5:
        state = "EMERGENCE"
    elif delta >= 0.18 and p_recent >= 0.62:
        state = "RENFORCEMENT"
    elif delta <= -0.18 and p_recent <= 0.48:
        state = "AFFAIBLISSEMENT"
    elif p_recent >= 0.68 and abs(delta) < 0.12:
        state = "PERSISTANT"
    elif p_recent <= 0.32 and abs(delta) < 0.12:
        state = "RECURRENT"
    else:
        state = "NEUTRE"
    niveau = "SOLIDE" if n >= 20 else "EXPLOITABLE" if n >= 10 else "FAIBLE" if n >= 5 else "INSUFFISANT"
    return {
        "regime":state,
        "niveau":niveau,
        "echantillon":n,
        "frequence":round(sum(r.resultat for r in rows)/n,4),
        "frequence_recente":round(p_recent,4),
        "tendance":round(delta,4),
        "sequence":sequence,
        "lissage":"EWMA",
    }
