from __future__ import annotations

def _ordered(rows):
    return sorted(rows, key=lambda r: str(getattr(r, "date", "")))

def sequence(rows, max_len=12):
    rows = _ordered(rows)
    vals = [bool(r.resultat) for r in rows[-max_len:]]
    symbols = ["O" if x else "N" for x in vals]
    run_type = None
    run_length = 0
    if vals:
        run_type = vals[-1]
        for x in reversed(vals):
            if x != run_type:
                break
            run_length += 1
    return {
        "sequence": symbols,
        "longueur": len(symbols),
        "issue_dernier": "O" if vals[-1] else "N" if vals else None,
        "serie_actuelle": run_length,
        "type_serie": "SUCCES" if run_type is True else "ECHEC" if run_type is False else None,
    }

def transition(rows, window=5):
    rows = _ordered(rows)
    if len(rows) < 2:
        return {"rupture": False, "reprise": False, "avant": None, "apres": None}
    recent = rows[-window:]
    previous = rows[-2*window:-window]
    if not previous:
        return {"rupture": False, "reprise": False, "avant": None, "apres": None}
    p0 = sum(bool(r.resultat) for r in previous) / len(previous)
    p1 = sum(bool(r.resultat) for r in recent) / len(recent)

    rupture = (p0 >= 0.70 and p1 <= 0.40) or (p0 <= 0.30 and p1 >= 0.60)

    # Une reprise exige un vrai épisode intermédiaire de rupture :
    # ancien régime stable -> phase opposée -> retour du régime initial.
    reprise = False
    if len(rows) >= 3 * window:
        before = rows[-3*window:-2*window]
        p_before = sum(bool(r.resultat) for r in before) / len(before)
        reprise = (
            (p_before >= 0.70 and p0 <= 0.40 and p1 >= 0.60)
            or (p_before <= 0.30 and p0 >= 0.60 and p1 <= 0.40)
        )

    return {
        "rupture": rupture,
        "reprise": reprise,
        "avant": round(p0,4),
        "apres": round(p1,4),
    }

def analyser_sequences(rows):
    s = sequence(rows)
    t = transition(rows)
    return {**s, **t}
