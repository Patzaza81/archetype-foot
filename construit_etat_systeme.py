"""Consolide l'état descriptif du moteur principal à partir du journal de rentabilité."""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

FICHIER_ETAT = "etat_systeme.json"
FICHIER_JOURNAL = "journal.json"


def construit_etat() -> dict[str, Any]:
    journal_path = Path(FICHIER_JOURNAL)
    if not journal_path.exists():
        bilan: dict[str, Any] = {}
    else:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        moteur = (journal.get("moteurs") or {}).get("moteur_v2_6_9") or {}
        g = moteur.get("global") or {}
        paris = int(g.get("paris") or 0)
        gagnes = int(g.get("gagnes") or 0)
        rembourses = int(g.get("rembourses") or 0)
        par_famille = {}
        for ligne in moteur.get("ligues") or []:
            segment = ligne.get("segment")
            if not segment:
                continue
            par_famille[segment] = {"resume": {
                "observations": int(ligne.get("paris") or 0),
                "gagnes": int(ligne.get("gagnes") or 0),
                "perdus": max(0, int(ligne.get("paris") or 0) - int(ligne.get("gagnes") or 0) - int(ligne.get("rembourses") or 0)),
                "roi_flat": ligne.get("roi"),
            }}
        bilan = {
            "global": {
                "observations": paris,
                "gagnes": gagnes,
                "perdus": max(0, paris - gagnes - rembourses),
                "roi_flat": g.get("roi"),
            },
            "par_famille": par_famille,
        }
    return {
        "genere_le": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bilan_comportemental": bilan,
    }


def main() -> None:
    Path(FICHIER_ETAT).write_text(
        json.dumps(construit_etat(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("[etat systeme] etat_systeme.json généré à partir du journal du moteur principal.")


if __name__ == "__main__":
    main()
