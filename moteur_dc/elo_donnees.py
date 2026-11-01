"""Données ClubElo pour la piste B′ (copie publique CC BY 4.0, voir data/clubelo/SOURCE.md) : lecture, rapprochement des noms Football-Data → ClubElo, Elo à une date.

Garde-fou 1 (Elo strictement antérieur) : `elo_veille(club, jour)` lit la valeur dont l'intervalle [From, To] contient la VEILLE du match, jamais le jour même ni après.
Le rapprochement exige le même pays (préfixe de la division Football-Data) et un nom identique après normalisation, ou un alias explicite ci-dessous.
"""
from __future__ import annotations

import csv
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "clubelo" / "historique"
PAYS_DIVISION = {"E0": "ENG", "E1": "ENG", "E2": "ENG", "E3": "ENG", "EC": "ENG", "SP1": "ESP", "SP2": "ESP", "I1": "ITA", "I2": "ITA", "D1": "GER", "D2": "GER", "F1": "FRA", "F2": "FRA"}
# noms Football-Data → noms ClubElo (uniquement ceux qui diffèrent après normalisation)
ALIAS = {"Ath Bilbao": "Bilbao", "Ath Madrid": "Atletico", "Nott'm Forest": "Forest", "Espanol": "Espanyol", "Vallecano": "Rayo Vallecano", "Bayern Munich": "Bayern",
         "Ein Frankfurt": "Frankfurt", "FC Koln": "Koeln", "M'gladbach": "Gladbach", "Schalke 04": "Schalke", "Werder Bremen": "Werder", "La Coruna": "Depor"}


def normaliser(nom: str) -> str:
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum())


def charger(dossier: Path = DOSSIER) -> dict[str, dict[str, Any]]:
    """{club: {"pays": …, "niveau": …, "periodes": [(from, to, elo), …] trié}}."""
    out: dict[str, dict[str, Any]] = {}
    for f in sorted(dossier.glob("*.csv")):
        with open(f, encoding="utf-8") as fh:
            lignes = list(csv.DictReader(fh))
        if not lignes:
            continue
        out[lignes[-1]["Club"]] = {"pays": lignes[-1]["Country"], "niveau": int(lignes[-1]["Level"]),
                                   "periodes": sorted((r["From"], r["To"], float(r["Elo"])) for r in lignes)}
    return out


def index_noms(elo: dict[str, dict[str, Any]]) -> dict[tuple[str, str], str]:
    return {(v["pays"], normaliser(k)): k for k, v in elo.items()}


def rapprocher(nom_fd: str, division: str, idx: dict[tuple[str, str], str]) -> str | None:
    """Nom ClubElo du club Football-Data `nom_fd` joué en `division`, ou None (pays inconnu, nom absent). Jamais de correspondance approximative."""
    pays = PAYS_DIVISION.get(division)
    if pays is None:
        return None
    return idx.get((pays, normaliser(ALIAS.get(nom_fd, nom_fd))))


def elo_veille(elo: dict[str, dict[str, Any]], club: str | None, jour: str) -> float | None:
    """Elo du club la veille de `jour` (AAAA-MM-JJ) ; None si le club n'a pas d'intervalle couvrant cette date."""
    if club is None or club not in elo:
        return None
    v = (date.fromisoformat(jour) - timedelta(days=1)).isoformat()
    for debut, fin, e in elo[club]["periodes"]:
        if debut <= v <= fin:
            return e
    return None
