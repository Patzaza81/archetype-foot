"""Rapprochement entre la source de référence et une autre source : un pour un, jamais de choix au hasard."""
from __future__ import annotations

from datetime import date

from .modele import Match
from .noms import meme_equipe

ECART_JOURS_MAX = 1          # un match de la nuit n'a pas le même jour selon le fuseau de la source : jours voisins acceptés, pas plus


def _voisins(a: str, b: str) -> bool:
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= ECART_JOURS_MAX
    except ValueError:
        return False


def meme_match(a: Match, b: Match) -> bool:
    return _voisins(a.jour, b.jour) and meme_equipe(a.domicile, b.domicile) and meme_equipe(a.exterieur, b.exterieur)


def rapprocher(reference: list[Match], candidats: list[Match]) -> dict:
    """-> {"paires": {id_ref: Match candidat}, "ambigus": [id_ref…], "sans": [id_ref…]}.
    Une paire n'est retenue que si elle est unique DANS LES DEUX SENS : le match de référence n'a qu'un candidat, et ce candidat n'a que lui."""
    par_ref = {r.id_source: [c for c in candidats if meme_match(r, c)] for r in reference}
    par_cand: dict[tuple, list[str]] = {}
    for rid, L in par_ref.items():
        for c in L:
            par_cand.setdefault(c.cle(), []).append(rid)
    paires, ambigus, sans = {}, [], []
    for r in reference:
        L = par_ref[r.id_source]
        if not L:
            sans.append(r.id_source)
        elif len(L) == 1 and len(par_cand[L[0].cle()]) == 1:
            paires[r.id_source] = L[0]
        else:
            ambigus.append(r.id_source)
    return {"paires": paires, "ambigus": ambigus, "sans": sans}
