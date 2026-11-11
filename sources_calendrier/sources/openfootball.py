"""openfootball (fichiers libres sur GitHub) : le calendrier complet de la saison de quelques grands championnats.
Constat du 11/11/2026 : les 9 fichiers suivis ont bien les matchs à venir, mais leurs scores s'arrêtent au 20/09/2026. C'est donc un calendrier de dernier recours, pas une source de résultats."""
from __future__ import annotations

import json

from ..modele import Match, sans_doublons

NOM = "openfootball"


def lire_fichier(brut: bytes, fichier: str, jours: set[str]) -> list[Match]:
    d = json.loads(brut)
    out = []
    for i, m in enumerate(d.get("matches") or []):
        if m.get("date") in jours and m.get("team1") and m.get("team2"):
            out.append(Match(NOM, f"{fichier}#{m['date']}#{m['team1']}#{m['team2']}", m["date"], m["team1"], m["team2"], None, d.get("name")))
    return out


def lire(jours: list[str], conf: dict, telecharger) -> tuple[list[Match], list[str]]:
    matchs, erreurs = [], []
    for f in conf.get("fichiers") or []:
        try:
            matchs += lire_fichier(telecharger(conf["url"].replace("{fichier}", f)), f, set(jours))
        except Exception as e:                                # noqa: BLE001 : un fichier en échec n'empêche pas les autres
            erreurs.append(f"{f} : {type(e).__name__} : {str(e)[:160]}")
    return sans_doublons(matchs), erreurs
