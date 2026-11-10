"""Moteurs désactivés (config/moteurs_desactives.json). `python -m megapower.actifs <nom>` : code de sortie 0 si le moteur est actif, 1 s'il est désactivé."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CHEMIN = Path(__file__).resolve().parent.parent / "config" / "moteurs_desactives.json"


def desactives(chemin: Path = CHEMIN) -> dict[str, str]:
    try:
        return dict(json.loads(chemin.read_text(encoding="utf-8")).get("desactives") or {})
    except (OSError, ValueError):
        return {}                                   # fichier absent ou illisible : rien n'est désactivé (comportement d'avant)


def actif(nom: str, chemin: Path = CHEMIN) -> bool:
    return nom not in desactives(chemin)


if __name__ == "__main__":
    nom = sys.argv[1] if len(sys.argv) > 1 else ""
    if actif(nom):
        sys.exit(0)
    print(f"moteur {nom} désactivé : {desactives()[nom]}")
    sys.exit(1)
