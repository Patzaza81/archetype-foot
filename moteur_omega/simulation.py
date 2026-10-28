"""Matchs simulés dans les deux sens (méthode de Patrick, 28/10/2026) : badge « Accord » et « Alerte » des fiches omega.

Simulation : les matchs des deux équipes au même lieu (séries gelées du match) sont appariés dans l'ordre (les k derniers de chacune,
k = le plus petit des deux échantillons), et chaque paire donne deux scores simulés domicile – extérieur, en buts entiers :
- sens 1 (attaque du domicile × défense de l'extérieur) : buts marqués par le domicile – buts encaissés par l'extérieur ;
- sens 2 (attaque de l'extérieur × défense du domicile) : buts encaissés par le domicile – buts marqués par l'extérieur.
Indice d'un marché = nombre de scores simulés qui le valident, sur 2k.

Rôle validé par Patrick (28/10/2026) après le test sur l'archive : complément de la Solidité, jamais à sa place.
- « Accord » : le marché le plus solide (Solidité) et le plus fréquent dans la simulation sont le même, parmi les marchés cotés 1,39 et plus.
  Test du 28/10 (846 matchs de la période test) : 65,9 % gagnés quand les deux s'accordent, contre 60,6 % (Solidité) et 55,0 % (simulation)
  quand ils divergent.
- « Alerte » : le pari affiché passe dans moins de 6 matchs simulés sur 10. Seuil tiré du même test : pari de la Solidité avec une fréquence
  simulée sous 60 % = 58,9 % gagnés, rendement −11,0 % (146 paris), contre 64,5 % / −2,9 % entre 60 et 80 %.
Affichage seulement : ne touche ni à la sélection, ni au journal gelé, ni aux pronostics.
"""
from __future__ import annotations

from typing import Any

from . import coeur, marches as M, solidite as SO

SEUIL_ALERTE = 0.6


def scores_simules(s: dict[str, list[int]]) -> list[tuple[int, int]]:
    """Les 2k scores simulés (domicile, extérieur) ; liste vide si une série manque."""
    k = min(len(s.get("dom_marques") or []), len(s.get("ext_marques") or []))
    if not k:
        return []
    dm, dc = s["dom_marques"][-k:], s["dom_encaisses"][-k:]
    em, ec = s["ext_marques"][-k:], s["ext_encaisses"][-k:]
    return [(int(dm[i]), int(ec[i])) for i in range(k)] + [(int(dc[i]), int(em[i])) for i in range(k)]


def frequence(cle: Any, s: dict[str, list[int]]) -> dict[str, int] | None:
    """{"ok": scores simulés qui valident le marché, "n": nombre de scores simulés} ; None si le marché n'est pas lu ou sans série."""
    t = M.test_du_marche(*tuple(cle))
    sc = scores_simules(s)
    if t is None or not sc:
        return None
    return {"ok": sum(bool(t(h, a)) for h, a in sc), "n": len(sc)}


def marche_accord(s: dict[str, list[int]], cotes: dict | None, poids: dict[str, Any] | None,
                  cote_min: float = coeur.COTE_MIN) -> tuple[str, str] | None:
    """Clé du marché sur lequel la Solidité et la simulation s'accordent (le premier de chacune parmi les marchés cotés >= cote_min), sinon None."""
    if not poids or not cotes or not scores_simules(s):
        return None
    cand = []
    for cle in M.catalogue():
        cote = coeur.cote_de(cotes, cle)
        if cote is None or cote < cote_min:
            continue
        fr = frequence(cle, s)
        sol = SO.probabilite(poids, cle, s)
        if fr is None or sol is None:
            continue
        cand.append((tuple(cle), fr["ok"] / fr["n"], sol))
    if not cand:
        return None
    top_sol = max(cand, key=lambda c: (c[2], c[1]))
    top_sim = max(cand, key=lambda c: (c[1], c[2]))
    return top_sol[0] if top_sol[0] == top_sim[0] else None
