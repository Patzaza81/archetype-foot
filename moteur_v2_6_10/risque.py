# -*- coding: utf-8 -*-
"""Alertes automatiques, SANS effet sur la sélection (affichage et diagnostic seulement).

Seuils repris du standard de justification du moteur V3 (docs/V3_PRIORITES_ET_JUSTIFICATION.md, §3). Une alerte ne
change ni la catégorie A-D, ni les désignations, ni les choix P1/P2/P3 : transformer une alerte en règle de rejet est
une décision du propriétaire, à prendre après mesure.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

ECART_MARCHE_ALERTE = 0.12     # écart modèle − marché (en probabilité) au-delà duquel une value bet est « inhabituelle »
BUTS_ATTENDUS_MIN = 1.8        # total λ domicile + λ extérieur
BUTS_ATTENDUS_MAX = 4.0


def alertes_ligne(ligne: Dict[str, Any]) -> List[str]:
    """Alertes d'un marché. Seules les value bets sont examinées (ce sont les candidats à la sélection)."""
    out: List[str] = []
    if ligne.get("is_value") and ligne.get("edge", 0.0) > ECART_MARCHE_ALERTE:
        out.append(f"Écart inhabituel avec le marché ({ligne['edge'] * 100:+.1f} points)")
    return out


def alertes_match(res: Dict[str, Any], statut_calibration: str = "NON_CALIBRE", raison: Optional[str] = None) -> List[str]:
    out: List[str] = []
    ld, le = res.get("lambda_dom"), res.get("lambda_ext")
    if isinstance(ld, (int, float)) and isinstance(le, (int, float)):
        total = ld + le
        if total < BUTS_ATTENDUS_MIN or total > BUTS_ATTENDUS_MAX:
            out.append(f"Buts attendus extrêmes (total {total:.2f})")
    if statut_calibration == "NON_CALIBRE":
        out.append("Probabilités non calibrées")
    elif statut_calibration != "CALIBRE":
        out.append(f"Calibrateur ignoré ({raison or statut_calibration})")
    return out
