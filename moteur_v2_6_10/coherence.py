# -*- coding: utf-8 -*-
"""Cohérence des probabilités après calibration (défaut corrigé à l'audit du 01/10/2026).

Le calibrateur traite chaque marché séparément. Sans correction, les probabilités calibrées de marchés complémentaires ne
somment plus à 1 (mesuré à l'audit : 1X2 = 1,090 ; BTTS = 1,028 ; over/under 2,5 = 1,038) et les deux côtés d'un même
marché peuvent devenir « value » en même temps, ce qui est impossible. `harmonise` rétablit les identités logiques :

  1. chaque groupe COMPLET (1X2, BTTS, over/under d'une ligne, buts d'une équipe) est renormalisé pour sommer à 1 ;
     un groupe incomplet (marché retiré par V1 ou V3) n'est pas touché, comme dans le moteur de base ;
  2. la double chance est dérivée du 1X2 calibré (dc_1X = 1 + X, dc_X2 = X + 2, dc_12 = 1 + 2) ;
  3. les marchés mathématiquement équivalents prennent la valeur de leur représentant
     (clean sheet domicile = l'extérieur ne marque pas ; handicap ±0,5 = victoire / double chance / défaite).

Fonction pure : aucune dépendance au moteur de base (les groupes sont passés en argument).
"""
from __future__ import annotations

from typing import Dict, List, Mapping

from .calibration import marche_equivalent


def harmonise(probas: Mapping[str, float], groupes: Mapping[str, List[str]]) -> Dict[str, float]:
    out = dict(probas)
    for membres in groupes.values():
        if all(m in out for m in membres):
            somme = sum(out[m] for m in membres)
            if somme > 0:
                for m in membres:
                    out[m] = out[m] / somme
    if all(m in out for m in ("victoire", "nul", "defaite")):
        v, n, d = out["victoire"], out["nul"], out["defaite"]
        for cle, valeur in (("dc_1X", v + n), ("dc_X2", n + d), ("dc_12", v + d)):
            if cle in out:
                out[cle] = valeur
    for m in list(out):
        representant = marche_equivalent(m)
        if representant != m and representant in out:
            out[m] = out[representant]
    return out
