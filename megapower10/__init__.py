"""MEGAPOWER 10+: independent high-odds discovery and validation engine."""
from .core import Quote, load_jsonl, validate_quotes, odds_band, evaluate

__all__ = ["Quote", "load_jsonl", "validate_quotes", "odds_band", "evaluate"]
