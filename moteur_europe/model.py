from __future__ import annotations

from typing import Any, Mapping, Sequence

from moteur_v3.model import (GoalModel, MOYENNE_REFERENCE, _lisse, _sample, _strength, _valid, score_matrix)

# Décision de Patrick (13/10/2026) : derniers matchs européens 70 %, derniers matchs du championnat 30 %.
# 3 matchs minimum, 6 maximum, par source et au MÊME LIEU (principe V3). Constantes fixées à l'avance, jamais ajustées
# sur des résultats.
POIDS_EUROPE = 0.70
POIDS_CHAMPIONNAT = 0.30
N_MIN = 3
N_MAX = 6
assert abs(POIDS_EUROPE + POIDS_CHAMPIONNAT - 1.0) < 1e-12


def derniers(rows: Sequence[Mapping[str, Any]], domicile: bool, n_max: int = N_MAX) -> list[Mapping[str, Any]]:
    """Les n_max derniers matchs valides joués au lieu demandé, du plus ancien au plus récent."""
    out = [m for m in rows if _valid(m) and bool(m.get("domicile")) is domicile]
    out.sort(key=lambda m: str(m.get("date") or ""))
    return out[-n_max:]


def _force(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    s = _strength(rows)
    n = len(rows)
    return {"attack": _lisse(s["attack"], n), "defense": _lisse(s["defense"], n), "xg_complete": s["xg_complete"]}


def _melange(eu: dict[str, Any], lg: dict[str, Any], cle: str) -> float:
    return POIDS_EUROPE * eu[cle] + POIDS_CHAMPIONNAT * lg[cle]


def _lambdas(eu_d, lg_d, eu_e, lg_e) -> tuple[float, float]:
    """Chaque source est lissée vers 1,35 selon SA taille (formule V3), puis les deux sont mélangées 70/30 ;
    buts attendus = attaque × défense adverse / 1,35 (formes relatives de la V3)."""
    fd_eu, fd_lg, fe_eu, fe_lg = _force(eu_d), _force(lg_d), _force(eu_e), _force(lg_e)
    lh = _melange(fd_eu, fd_lg, "attack") * _melange(fe_eu, fe_lg, "defense") / MOYENNE_REFERENCE
    la = _melange(fe_eu, fe_lg, "attack") * _melange(fd_eu, fd_lg, "defense") / MOYENNE_REFERENCE
    return lh, la


def build_model_europe(europe_dom, europe_ext, ligue_dom, ligue_ext) -> GoalModel:
    """Modèle de buts d'un match européen. Lève ValueError si une des quatre listes a moins de N_MIN matchs au lieu voulu
    (NO DATA -> NO GO : jamais de repli silencieux sur une seule source)."""
    eu_d, eu_e = derniers(europe_dom, True), derniers(europe_ext, False)
    lg_d, lg_e = derniers(ligue_dom, True), derniers(ligue_ext, False)
    if len(eu_d) < N_MIN or len(eu_e) < N_MIN:
        raise ValueError("EUROPE_INSUFFISANT")
    if len(lg_d) < N_MIN or len(lg_e) < N_MIN:
        raise ValueError("CHAMPIONNAT_INSUFFISANT")

    lh, la = _lambdas(eu_d, lg_d, eu_e, lg_e)
    # Diagnostics de comparaison future (jamais utilisés dans la décision) : λ de chaque source seule.
    lh_eu, la_eu = _lambdas(eu_d, eu_d, eu_e, eu_e)
    lh_lg, la_lg = _lambdas(lg_d, lg_d, lg_e, lg_e)
    xg = _strength(eu_d)["xg_complete"] and _strength(lg_d)["xg_complete"]
    xg_e = _strength(eu_e)["xg_complete"] and _strength(lg_e)["xg_complete"]
    n_d, n_e = min(len(eu_d), len(lg_d)), min(len(eu_e), len(lg_e))
    return GoalModel(
        lh, la, None, None, None, None, score_matrix(lh, la), None, None,
        _sample(n_d, 0, 0.0, xg), _sample(n_e, 0, 0.0, xg_e), lh == 0.0, la == 0.0,
        {"poids_europe": POIDS_EUROPE, "poids_championnat": POIDS_CHAMPIONNAT,
         "europe_dom_n": len(eu_d), "europe_ext_n": len(eu_e), "championnat_dom_n": len(lg_d),
         "championnat_ext_n": len(lg_e),
         "europe_dom_dates": [m.get("date") for m in eu_d], "europe_ext_dates": [m.get("date") for m in eu_e],
         "championnat_dom_dates": [m.get("date") for m in lg_d], "championnat_ext_dates": [m.get("date") for m in lg_e],
         "lambda_europe_seule": (lh_eu, la_eu), "lambda_championnat_seul": (lh_lg, la_lg),
         "mi_temps": "non calculée (données de mi-temps absentes côté européen)",
         "h2h_used": False, "previous_season_used": False},
    )
