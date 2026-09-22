"""construit_etat_systeme.py -- consolide les deux bilans comportementaux du système.

Le fichier est volontairement descriptif : il ne lance aucun calibrage et ne
lit aucun ancien système de tickets. Il rassemble le bilan du moteur principal
moteur_v2_6_9 et celui de shrink_v1, actuellement en test.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

FICHIER_ETAT = "etat_systeme.json"
FICHIER_BILAN = "bilan_archetype_model.json"
FICHIER_BILAN_SHRINK = "bilan_shrink_v1.json"


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
        "bilan_shrink_v1": _charge_json_ou_vide(FICHIER_BILAN_SHRINK),
    }


def main() -> None:
    etat = construit_etat()
    with open(FICHIER_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)
    print("[etat systeme] etat_systeme.json généré -- deux bilans comportementaux consolidés.")


if __name__ == "__main__":
    main()
