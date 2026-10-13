"""Moteur Europe d'Archetype Foot (Ligue des champions, Europa League, Conférence League).

Même principe de calcul que le moteur V3 (forces lissées, Poisson, mêmes marchés, mêmes filtres de value), appliqué à
deux sources de matchs : l'historique européen du club (70 %) et son championnat (30 %).
Isolé : aucun branchement pipeline, aucun fichier V2/V3 modifié.
"""

from .core import evaluate_match_europe

__all__ = ["evaluate_match_europe"]
