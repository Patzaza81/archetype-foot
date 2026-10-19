"""Matrice expérimentale de découverte de scénarios, indépendante des moteurs de production."""
from .core import (
    SCHEMA_VERSION, build_features, discover_scenarios, evaluate_scenario,
    load_dataset, run_experiment, validate_record,
)

__all__ = [
    "SCHEMA_VERSION", "build_features", "discover_scenarios",
    "evaluate_scenario", "load_dataset", "run_experiment", "validate_record",
]
