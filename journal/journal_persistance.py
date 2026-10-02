from __future__ import annotations

def _result_at(rows, offset):
    if offset <= 0 or len(rows) < offset:
        return None
    return bool(rows[offset-1].resultat)

def evaluer_persistance(rows, signal_index=None, horizons=(1,3,5,10,20)):
    rows = sorted(rows, key=lambda r: str(getattr(r, "date", "")))
    if signal_index is None:
        signal_index = len(rows) - 1
    result = {}
    for h in horizons:
        idx = signal_index + h
        if idx < len(rows):
            result[f"+{h}"] = {
                "disponible": True,
                "resultat": bool(rows[idx].resultat),
                "date": str(rows[idx].date),
            }
        else:
            result[f"+{h}"] = {"disponible": False}
    return result

def taux_persistance(rows, horizons=(1,3,5,10,20)):
    vals = []
    for h in horizons:
        outcomes = []
        for i in range(len(rows) - h):
            outcomes.append(bool(rows[i+h].resultat))
        if outcomes:
            vals.append((h, sum(outcomes)/len(outcomes)))
    return {f"+{h}": round(v,4) for h,v in vals}
