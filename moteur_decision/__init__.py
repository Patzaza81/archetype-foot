"""Noyau V1 du moteur de décision Archetype Foot.
Indépendant de l'ancien moteur; non branché au pipeline de production.
"""
from .statistical_model import ModelOutput, build_model
from .market_engine import derive_goal_markets
from .value_engine import evaluate_market, filter_value_candidates
__all__ = ["ModelOutput", "build_model", "derive_goal_markets", "evaluate_market", "filter_value_candidates"]
