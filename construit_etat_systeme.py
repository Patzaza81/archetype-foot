"""construit_etat_systeme.py -- consolide le bilan du moteur de production.

Le fichier est descriptif : il ne lance aucun calibrage et ne charge aucun
moteur expérimental supprimé.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

FICHIER_ETAT = "etat_systeme.json"
FICHIER_BILAN = "bilan_archetype_model.json"
FICHIER_COMPARAISON = "data/comparaison_moteurs.json"
FICHIER_SELECTION = "data/selection_intelligence.json"


def _charge_json_ou_vide(chemin: str) -> Any:
    path = Path(chemin)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def construit_etat() -> dict[str, Any]:
    return {
        "genere_le": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bilan_comportemental": _charge_json_ou_vide(FICHIER_BILAN),
        "comparaison_moteurs": _charge_json_ou_vide(FICHIER_COMPARAISON),
        "selection_intelligence": _charge_json_ou_vide(FICHIER_SELECTION),
    }


def main() -> None:
    etat = construit_etat()
    with open(FICHIER_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)
    print("[etat systeme] etat_systeme.json généré -- état du moteur de production consolidé.")


if __name__ == "__main__":
    main()
