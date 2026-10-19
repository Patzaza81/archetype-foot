"""Règle de croisement de Patrick, appliquée telle quelle (sans moyenne ni calibration).

Pour un match, on aligne les derniers matchs des deux équipes (au même lieu) et on forme des « scores croisés » :
  1. marqués face à face : (buts marqués par le domicile, buts marqués par l'extérieur), match par match ;
  2. encaissés face à face : (buts que l'extérieur encaisse = ceux que le domicile peut marquer, buts que le domicile encaisse).
Chaque marché est comptabilisé sur l'ensemble de ces scores croisés ; on retient le marché qui se réalise le plus souvent
(à égalité : la cote la plus haute), parmi ceux dont la cote BetPawa est d'au moins 1,26.
Lecture seule, aucune règle activée.
"""
from __future__ import annotations

from typing import Any

from . import croisements as C
from . import pronostic_sur as P

COTE_MIN = 1.26


def scores_croises(domicile: list[tuple[int, int]], exterieur: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """`domicile` et `exterieur` : (buts marqués, buts encaissés) de chaque équipe, du plus ancien au plus récent."""
    k = min(len(domicile), len(exterieur))
    h, a = domicile[-k:], exterieur[-k:]
    marques = [(hg, ag) for (hg, _), (ag, _) in zip(h, a)]
    encaisses = [(ag_c, hg_c) for (_, hg_c), (_, ag_c) in zip(h, a)]
    return marques + encaisses


def frequences(croises: list[tuple[int, int]]) -> dict[str, float]:
    n = len(croises)
    return {m: sum(C.outcome({"home_goals": h, "away_goals": a}, m) for h, a in croises) / n for m in C.ALL_MARKETS}


def choisir(croises: list[tuple[int, int]], cotes: dict[str, float], cote_min: float = COTE_MIN) -> dict[str, Any] | None:
    f = frequences(croises)
    candidats = [(f[m], c, m) for m, c in cotes.items() if c >= cote_min and m in f]
    if not candidats:
        return None
    freq, cote, m = max(candidats)
    return {"marche": m, "libelle": P.LIBELLES[m], "frequence": round(freq, 3), "cote": cote, "scores_croises": len(croises)}
