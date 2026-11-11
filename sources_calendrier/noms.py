"""Comparaison des noms d'équipes entre sources. Tout ce qui se corrige se corrige dans config/sources_noms.json (aucune règle cachée ailleurs)."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

CHEMIN = Path(__file__).resolve().parent.parent / "config" / "sources_noms.json"


@lru_cache(maxsize=4)
def regles(chemin: str = str(CHEMIN)) -> dict:
    try:
        d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"mots_ignores": set(d.get("mots_ignores") or []), "marqueurs": {k: v for k, v in (d.get("marqueurs") or {}).items()},
            "equivalents": {_brut(k): _brut(v) for k, v in (d.get("equivalents") or {}).items()}}


def _brut(nom: str) -> str:
    s = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def decoupe(nom: str, chemin: str = str(CHEMIN)) -> tuple[frozenset, frozenset]:
    """-> (mots du nom, marqueurs). Marqueurs = ce qui distingue une AUTRE équipe du même club : féminines, jeunes (u17…u23), réserve."""
    r = regles(chemin)
    b = r["equivalents"].get(_brut(nom), _brut(nom))
    mots, marques = set(), set()
    for t in b.split():
        if t in r["marqueurs"]:
            marques.add(r["marqueurs"][t])
        elif re.fullmatch(r"u\d{2}", t):
            marques.add(t)
        elif t not in r["mots_ignores"]:
            mots.add(t)
    return frozenset(mots), frozenset(marques)


def meme_equipe(a: str, b: str, chemin: str = str(CHEMIN)) -> bool:
    """Vrai si les deux noms désignent la même équipe : mêmes marqueurs, et mêmes mots — ou tous les mots du nom le plus court dans le plus long
    (« Washington » / « Washington Spirit »). Un nom vide ne concorde avec rien."""
    ma, qa = decoupe(a, chemin)
    mb, qb = decoupe(b, chemin)
    if not ma or not mb or qa != qb:
        return False
    return ma == mb or ma < mb or mb < ma
