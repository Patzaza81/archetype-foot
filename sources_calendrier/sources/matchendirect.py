"""Source principale : ce que scraper.py et scraper_semaine.py ont déjà écrit (lecture seule, aucun téléchargement ici)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..modele import Match, sans_doublons

NOM = "matchendirect"
RACINE = Path(__file__).resolve().parent.parent.parent
FEMININ = re.compile(r"f[ée]minin|femmes|women|\bwsl\b|\bdames\b", re.I)
JEUNES = re.compile(r"\bU ?(\d{2})\b", re.I)


def _nom(equipe: str, competition: str) -> str:
    """Matchendirect n'écrit pas toujours « féminines » ou « U19 » dans le nom de l'équipe : on le reprend du nom de la compétition, pour ne jamais confondre avec l'équipe première."""
    ajout = []
    if FEMININ.search(competition) and not FEMININ.search(equipe):
        ajout.append("féminines")
    j = JEUNES.search(competition)
    if j and not JEUNES.search(equipe):
        ajout.append(f"U{j.group(1)}")
    return " ".join([equipe, *ajout])


def lire(jours: list[str], conf: dict, telecharger=None, racine: Path = RACINE) -> tuple[list[Match], list[str]]:
    matchs, erreurs = [], []
    for f in conf.get("fichiers") or []:
        try:
            L = json.loads((racine / f).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            erreurs.append(f"{f} illisible : {type(e).__name__}")
            continue
        for m in L:
            if not m.get("match_id") or not m.get("domicile") or not m.get("exterieur") or m.get("date") not in jours:
                continue
            comp = " ".join(str(m.get("competition") or "").split())
            matchs.append(Match(NOM, m["match_id"], m["date"], _nom(m["domicile"], comp), _nom(m["exterieur"], comp), None, comp or None))
    return sans_doublons(matchs), erreurs
