from __future__ import annotations
from .journal_regimes import regime
from .journal_sequences import analyser_sequences
from .journal_memoire import resolve

def walk_forward(rows, min_history=5):
    rows = sorted(rows, key=lambda r: str(r.date))
    observations = []
    for i in range(min_history, len(rows)):
        past = rows[:i]
        r = regime(past)
        s = analyser_sequences(past)
        observations.append({
            "date_signal": rows[i].date,
            "echantillon_avant": len(past),
            "regime_avant": r["regime"],
            "niveau_avant": r["niveau"],
            "frequence_avant": r["frequence"],
            "tendance_avant": r["tendance"],
            "sequence_avant": s["sequence"],
            "resultat_apres": bool(rows[i].resultat),
        })
    return observations

def resume_validation(rows, min_history=5):
    replay = walk_forward(rows, min_history=min_history)
    by_state = {}
    for x in replay:
        state = x["regime_avant"]
        by_state.setdefault(state, []).append(x["resultat_apres"])
    states = {}
    for state, vals in by_state.items():
        states[state] = {
            "signaux": len(vals),
            "frequence_apres": round(sum(vals)/len(vals),4) if vals else None,
        }
    return {
        "methode": "walk_forward",
        "anti_fuite": True,
        "observations": len(replay),
        "par_regime": states,
    }

def validation_team_market(hist, team, market, competition=None, contexte=None):
    rows = [r for r in hist if r.equipe == team and r.marche == market]
    level, sample = resolve(rows, team, market, competition, contexte, min_exact=3)
    return {"niveau_retenu": level, "echantillon": len(sample), "resume": resume_validation(sample) if sample else {"observations":0}}
