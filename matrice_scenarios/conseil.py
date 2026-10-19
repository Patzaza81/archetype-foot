"""Conseil de modèles (architecture « LLM Council » transposée en conseillers statistiques, mesurables).

Conseillers indépendants (chacun donne une probabilité pour CHAQUE sélection cotée) :
- croisement : fréquence du marché sur les scores croisés (marqués / encaissés adverses) de Patrick
- poisson    : buts attendus -> distribution de scores (comportement.py)
- recent     : même modèle mais sur les 3 derniers matchs seulement (regard « court terme »)
- exterieur  : « l'étranger » : aucune info sur les équipes, seulement la distribution générale des scores
Relecture : le contradicteur mesure le désaccord entre conseillers. Président : tranche selon un mode ; aucun mode n'est
supposé meilleur : ils sont comparés sur les données (voir backtest).
"""
from __future__ import annotations

from typing import Any

from . import comportement as C
from .croisement_patrick import scores_croises
from .scanner_marches import scanner, test_du_marche

CONSEILLERS = ("croisement", "poisson", "recent", "exterieur")


def probas_par_conseiller(dom: list[tuple[int, int]], ext: list[tuple[int, int]], cotes_betpawa: dict) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]], list[str]]:
    """Retourne ({conseiller: {clé_marché: proba}}, marchés cotés, non_lus). Clé = 'groupe|sélection'."""
    base, non_lus = scanner(C.grille(*C.buts_attendus(dom, ext)), cotes_betpawa)
    croises = scores_croises(dom, ext)
    g_rec = C.grille(*C.buts_attendus(dom[-3:], ext[-3:]))
    g_ext = C.grille(C.MU_DOM, C.MU_EXT)
    out: dict[str, dict[str, float]] = {c: {} for c in CONSEILLERS}
    for m in base:
        k = f"{m['groupe']}|{m['selection']}"
        t = test_du_marche(m["groupe"], m["selection"])
        out["poisson"][k] = m["probabilite"]
        out["croisement"][k] = (sum(1 for h, a in croises if t(h, a)) + 0.5) / (len(croises) + 1)   # Laplace : jamais 0 ni 1
        out["recent"][k] = C.proba(g_rec, t)
        out["exterieur"][k] = C.proba(g_ext, t)
    return out, base, non_lus


def president(probas: dict[str, dict[str, float]], marches: list[dict[str, Any]], mode: str, cote_min: float = 1.26) -> dict[str, Any] | None:
    """Choisit parmi les marchés de cote >= cote_min. Modes : poisson (référence), moyenne, prudent (pire avis), unanime."""
    voix = ("croisement", "poisson", "recent")
    best = None
    for m in marches:
        if m["cote"] < cote_min:
            continue
        k = f"{m['groupe']}|{m['selection']}"
        v = [probas[c][k] for c in voix]
        score = {"poisson": probas["poisson"][k], "moyenne": sum(v) / 3, "prudent": min(v), "unanime": min(v) if max(v) - min(v) <= 0.15 else -1}[mode]
        if score < 0:
            continue
        cand = (round(score, 6), m["cote"], {**m, "score": score, "desaccord": round(max(v) - min(v), 3), "avis": {c: round(probas[c][k], 3) for c in CONSEILLERS}})
        if best is None or cand[:2] > best[:2]:
            best = cand
    return best[2] if best else None
