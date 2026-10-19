"""Pronostic « le plus sûr » : parmi les marchés dont la cote BetPawa est dans une fenêtre (1,10 à 1,25 par défaut),
on retient celui que le modèle de croisements juge le plus probable. La réussite passe avant tout.

Lecture seule, aucune règle activée. Probabilités : `analyse_match` (calibrées sur Football-Data, résultats seulement).
"""
from __future__ import annotations

from typing import Any


COTE_MIN, COTE_MAX = 1.10, 1.25
# marché du modèle -> (groupe de cotes BetPawa, sélection)
COTES = {
    "home_scores_1plus": ("over_under_domicile_0.5", "plus"), "away_scores_1plus": ("over_under_exterieur_0.5", "plus"),
    "both_score": ("btts", "Oui"), "over_2_5": ("over_under_2.5", "plus"), "under_2_5": ("over_under_2.5", "moins"),
    "home_win": ("1x2", "1"), "away_win": ("1x2", "2"), "draw": ("1x2", "N"),
    "home_not_lose": ("double_chance", "1N"), "away_not_lose": ("double_chance", "N2"),
    "over_1_5": ("over_under_1.5", "plus"), "under_3_5": ("over_under_3.5", "moins"),
    "under_4_5": ("over_under_4.5", "moins"), "under_5_5": ("over_under_5.5", "moins"),
}
LIBELLES = {
    "home_scores_1plus": "Domicile marque", "away_scores_1plus": "Extérieur marque", "both_score": "Les deux marquent",
    "over_2_5": "Over 2,5", "under_2_5": "Under 2,5", "home_win": "Victoire domicile", "away_win": "Victoire extérieur", "draw": "Nul",
    "home_not_lose": "Domicile ne perd pas (1N)", "away_not_lose": "Extérieur ne perd pas (N2)", "over_1_5": "Over 1,5",
    "under_3_5": "Under 3,5", "under_4_5": "Under 4,5", "under_5_5": "Under 5,5",
}


def cotes_du_match(cotes_betpawa: dict | None) -> dict[str, float]:
    out = {}
    for market, (group, selection) in COTES.items():
        value = ((cotes_betpawa or {}).get(group) or {}).get(selection)
        if isinstance(value, (int, float)) and value > 1:
            out[market] = float(value)
    return out


def choisir(analyse: dict[str, Any], cotes: dict[str, float], cote_min: float = COTE_MIN, cote_max: float = COTE_MAX) -> dict[str, Any] | None:
    """Marché le plus probable dont la cote est dans [cote_min, cote_max]. Égalité : la cote la plus haute. Aucun marché : None."""
    candidats = [(analyse["markets"][m]["probabilite"], c, m) for m, c in cotes.items() if cote_min <= c <= cote_max and m in analyse["markets"]]
    if not candidats:
        return None
    p, c, m = max(candidats)
    return {"marche": m, "libelle": LIBELLES[m], "probabilite": round(p, 3), "cote": c, "cote_equilibre": round(1 / p, 2)}
