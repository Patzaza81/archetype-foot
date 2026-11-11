"""Flux public d'ESPN (non officiel, sans clé) : tous les matchs de football d'un jour en une demande."""
from __future__ import annotations

import json
from datetime import date, timedelta

from ..modele import Match, sans_doublons

NOM = "espn"


def lire_reponse(brut: bytes) -> list[Match]:
    """Réponse du flux -> matchs. Un événement sans ses deux équipes ou sans date est ignoré (jamais deviné)."""
    out = []
    for e in json.loads(brut).get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        eq = {c.get("homeAway"): ((c.get("team") or {}).get("displayName") or (c.get("team") or {}).get("name")) for c in comp.get("competitors") or []}
        quand = str(e.get("date") or comp.get("date") or "")
        if not e.get("id") or not eq.get("home") or not eq.get("away") or len(quand) < 16:
            continue
        ligue = next((p[2:] for p in str(e.get("uid") or "").split("~") if p.startswith("l:")), None)
        out.append(Match(NOM, str(e["id"]), quand[:10], eq["home"], eq["away"], quand[:16] + ":00Z", f"ligue ESPN {ligue}" if ligue else None))
    return out


def lire(jours: list[str], conf: dict, telecharger) -> tuple[list[Match], list[str]]:
    """ESPN range les matchs par jour américain : on demande aussi la veille du premier jour, puis on ne garde qu'un exemplaire de chaque match."""
    if not jours:
        return [], []
    demandes = sorted({(date.fromisoformat(min(jours)) - timedelta(days=1)).isoformat(), *jours})
    matchs, erreurs, limite = [], [], int(conf.get("limite") or 1000)
    for j in demandes:
        url = conf["url"].replace("{AAAAMMJJ}", j.replace("-", "")).replace("{limite}", str(limite))
        try:
            L = lire_reponse(telecharger(url))
        except Exception as e:                                # noqa: BLE001 : un jour en échec n'empêche pas les autres
            erreurs.append(f"{j} : {type(e).__name__} : {str(e)[:160]}")
            continue
        if len(L) >= limite:
            erreurs.append(f"{j} : {len(L)} matchs = limite atteinte, la liste est peut-être coupée")
        matchs += L
    return sans_doublons(matchs), erreurs
