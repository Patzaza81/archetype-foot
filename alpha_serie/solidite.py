"""Solidité des marchés du moteur alpha (affichage, ordre de Patrick du 28/10/2026) : même principe que la Solidité d'omega
(`moteur_omega/solidite.py`), appliquée à TOUS les marchés que l'alpha affiche (buts, équipes, multigoals, multiscores, calibrés, combos).

Pour le MÊME TYPE DE MARCHÉ, croise la FRÉQUENCE (part des matchs récents où le pari passait) et les ÉCARTS DE BUTS (distance au basculement du score, voir
`moteur_omega/indice.py`) lus sur les matchs au même lieu AFFICHÉS sur la carte (tous les matchs à domicile de l'équipe qui reçoit, tous ceux de l'adversaire
à l'extérieur, avant le jour du match ; moyenne des deux équipes). Régression logistique de la réussite réelle, poids APPRIS sur l'archive (tous les marchés
des matchs joués ; jamais fixés à la main) et écrits dans docs/alpha_solidite.json à chaque passage du pipeline. N'utilise NI la cote NI la valeur de l'alpha.
Marché non appris : aucune solidité (rien n'est inventé). Affichage seulement : ne touche ni au moteur (`coeur.py`), ni au journal gelé, ni aux sélections.
Usage : python -m alpha_serie.solidite  -> docs/alpha_solidite.json
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from moteur_omega import indice as IND, marches as MO, solidite as SO

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "alpha_solidite.json"
MIN_MATCHS = 4          # règle de l'alpha : moins de 4 matchs pour une équipe, pas d'analyse


def _gagne(cle: list[str], h: int, a: int) -> bool | None:
    from . import suivi                      # import tardif : suivi importe ce module
    return suivi._gagne(cle, h, a)


@lru_cache(maxsize=None)
def table(cle: tuple[str, str]):
    """Table des distances au basculement du marché lu par l'alpha (None si marché illisible)."""
    if _gagne(list(cle), 0, 0) is None:
        return None
    return IND.table_depuis_test(lambda i, j: bool(_gagne(list(cle), i, j)))


def scores(hd: list[dict], he: list[dict]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Scores vus du domicile : matchs à domicile de l'équipe qui reçoit (marqués, encaissés), matchs à l'extérieur de l'adversaire (encaissés, marqués)."""
    return [(x["marques"], x["encaisses"]) for x in hd], [(x["encaisses"], x["marques"]) for x in he]


def mesures(cle: Any, hd: list[dict], he: list[dict]) -> dict[str, float] | None:
    dom, ext = scores(hd, he)
    return IND.mesures_table(table(tuple(cle)), dom, ext)


def probabilite(poids: dict[str, Any] | None, cle: Any, hd: list[dict], he: list[dict]) -> float | None:
    """Solidité (0 à 1) d'un marché de l'alpha ; None sans poids, marché non appris ou matchs manquants."""
    if not poids or len(hd) < MIN_MATCHS or len(he) < MIN_MATCHS:
        return None
    mk = poids.get("marches", {}).get(SO.cle_marche(cle))
    ms = mesures(cle, hd, he) if mk else None
    if not mk or ms is None:
        return None
    z = mk["niveau"] + poids["poids_frequence"] * SO._logit(ms["passe"]) + poids["poids_ecart"] * ms["ecart"] / mk["ecart_type_ecart"]
    return 1 / (1 + math.exp(-z))


def univers() -> list[tuple[str, str]]:
    """Marchés appris : ceux du catalogue omega que l'alpha sait lire, plus multigoals, multiscores et combos de l'alpha."""
    from . import calibrees, coeur
    cles = {tuple(c) for c in MO.catalogue() if _gagne(list(c), 0, 0) is not None}
    cles |= {("multigoals", f"{lo}-{hi}") for lo in range(1, 4) for hi in range(lo + 1, 7)}
    cles |= {("multiscores", g) for g in coeur.GROUPES_MULTISCORES}
    cles |= {tuple(v[0]) for v in calibrees._catalogue().values()}
    return sorted(c for c in cles if _gagne(list(c), 0, 0) is not None)


def lignes(matchs: list[dict[str, Any]]) -> list[tuple]:
    """(marché, fréquence, écart, réussite, jour) pour tous les marchés appris, sur les matchs joués de l'archive (équipes figées avant le coup d'envoi)."""
    from . import suivi
    cles = univers()
    out = []
    for m in matchs:
        sc = m.get("score_final")
        a = m.get("assemblage") or {}
        if not sc or sc.get("buts_dom") is None or not a.get("equipe_dom") or not a.get("equipe_ext"):
            continue
        jour = str(m["date"])[:10]
        hd, he = suivi.historique_lieu(a["equipe_dom"], True, jour), suivi.historique_lieu(a["equipe_ext"], False, jour)
        if len(hd) < MIN_MATCHS or len(he) < MIN_MATCHS:
            continue
        for cle in cles:
            ms = mesures(cle, hd, he)
            if ms is not None:
                out.append((SO.cle_marche(cle), ms["passe"], ms["ecart"], float(bool(_gagne(list(cle), sc["buts_dom"], sc["buts_ext"]))), jour))
    return out


def ajuster(matchs: list[dict[str, Any]]) -> dict[str, Any]:
    return SO.ajuster_lignes(lignes(matchs))


def charger(chemin: Path = SORTIE) -> dict[str, Any] | None:
    return SO.charger(chemin)


def ecrire(sortie: Path = SORTIE, matchs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from . import suivi
    out = ajuster(matchs if matchs is not None else suivi.charger_matchs())
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = ecrire()
    print(r["n_marches"], "marchés,", len(r["marches"]), "types, poids fréquence", r["poids_frequence"], "poids écart", r["poids_ecart"], "Brier", r["brier"])
