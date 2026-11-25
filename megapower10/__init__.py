"""MEGAPOWER 10+: independent high-odds discovery and validation engine."""
from .core import Quote, load_jsonl, validate_quotes, decision_snapshot, odds_band, evaluate, discovery_report, chronological_split

__all__ = ["Quote", "load_jsonl", "validate_quotes", "decision_snapshot", "odds_band", "evaluate", "discovery_report", "chronological_split"]
