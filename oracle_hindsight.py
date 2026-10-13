"""oracle_hindsight.py -- système « tricheur » d'évaluation (créé le 13/10/2026 sur demande de Patrick).

Principe : il connaît DÉJÀ les scores. Il reconstruit donc, match par match, les scénarios gagnants possibles à partir
des résultats réglés (cotes BetPawa du Journal + score final). Il ne sert JAMAIS à produire un pronostic : il fournit
trois repères pour évaluer une sélection (V2, V3, Journal, Europe, BASE, tickets) :
  1. PLAFOND  (oracle)  : ce qu'un moteur parfait, qui connaîtrait le score, aurait obtenu dans le même intervalle de cote ;
  2. HASARD   (plancher): ce qu'obtient un choix sans information dans le même intervalle de cote (toutes les cotes
                          de l'intervalle, tous marchés) -- c'est la marge du bookmaker qui s'y lit ;
  3. TICKETS GAGNANTS   : tickets construits à rebours, gagnants par construction, pour tester de bout en bout le
                          règlement des tickets (suivi_tickets) : un ticket « gagnant garanti » qui sort perdant
                          révèle un bug de règlement, pas un problème de moteur.
Détecteur de fuite : un moteur dont le ROI dépasse le plafond, ou s'en approche de façon suspecte, a vu le score.

Lecture seule : ne modifie ni les moteurs, ni le Journal, ni main. Bibliothèque standard uniquement.
Usage : python oracle_hindsight.py [--bande 1.30 1.60] [--tickets N PICKS GRAINE]
"""
from __future__ import annotations

import argparse
import math
import random
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import journal_rentabilite as J

BANDES = [(1.01, 1.10), (1.10, 1.20), (1.20, 1.30), (1.30, 1.40), (1.40, 1.50), (1.50, 1.60), (1.60, 1.80),
          (1.80, 2.00), (2.00, 2.50), (2.50, 3.00), (3.00, 5.00), (5.00, 999.0)]


def charge_paris() -> list[dict[str, Any]]:
    """Tous les paris réglés (remboursés exclus) des matchs BetPawa terminés."""
    matchs, _ = J.charge_matchs_betpawa()
    paris, _, _ = J.paris_depuis_matchs(matchs)
    return [p for p in paris if p["resultat"] != 0]


def dans_bande(p: Mapping[str, Any], bande: tuple[float, float]) -> bool:
    return bande[0] <= p["cote"] < bande[1]


def par_match(paris: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    d: dict[str, list] = defaultdict(list)
    for p in paris:
        d[p["match_id"]].append(p)
    return d


# --- 1. plafond (oracle) -----------------------------------------------------------------------------------------

def choix_oracle(paris_match: Sequence[Mapping[str, Any]], bande: tuple[float, float]) -> Mapping[str, Any] | None:
    """Le pari gagnant de la bande à la cote la plus haute (meilleur scénario gagnant). None si aucun ne gagne."""
    gagnants = [p for p in paris_match if p["resultat"] == 1 and dans_bande(p, bande)]
    return max(gagnants, key=lambda p: (p["cote"], p["marche"])) if gagnants else None


def plafond(paris: Sequence[Mapping[str, Any]], bande: tuple[float, float]) -> dict[str, Any]:
    """Oracle à UN pari par match : parmi les matchs qui ont au moins un pari dans la bande."""
    pm = par_match(paris)
    eligibles = [m for m, L in pm.items() if any(dans_bande(p, bande) for p in L)]
    choix = [c for c in (choix_oracle(pm[m], bande) for m in eligibles) if c]
    n = len(eligibles)
    return {"matchs_eligibles": n, "matchs_avec_gagnant": len(choix),
            "reussite": (len(choix) / n) if n else None,
            "roi": (sum(c["cote"] - 1 for c in choix) - (n - len(choix))) / n if n else None}


# --- 2. hasard (plancher) ----------------------------------------------------------------------------------------

def hasard(paris: Sequence[Mapping[str, Any]], bande: tuple[float, float]) -> dict[str, Any]:
    """Choix sans information : tous les paris de la bande, chacun avec le même poids (espérance exacte, sans tirage)."""
    L = [p for p in paris if dans_bande(p, bande)]
    n = len(L)
    if not n:
        return {"paris": 0, "reussite": None, "equilibre": None, "roi": None}
    return {"paris": n, "reussite": sum(p["resultat"] == 1 for p in L) / n,
            "equilibre": sum(1 / p["cote"] for p in L) / n, "roi": sum(p["profit"] for p in L) / n}


# --- évaluation d'une sélection ----------------------------------------------------------------------------------

def evalue(selection: Sequence[Mapping[str, Any]], paris: Sequence[Mapping[str, Any]],
           bande: tuple[float, float] | None = None) -> dict[str, Any]:
    """Compare une sélection (liste de paris réglés : match_id, cote, resultat, profit) au plafond et au hasard
    calculés sur les MÊMES matchs et la MÊME bande (par défaut : de la plus petite à la plus grande cote choisie).
    `capture` = (ROI moteur - ROI hasard) / (ROI oracle - ROI hasard) ; `fuite_suspecte` si ROI moteur >= ROI oracle."""
    sel = [p for p in selection if p["resultat"] != 0]
    if not sel:
        return {"paris": 0}
    if bande is None:
        bande = (min(p["cote"] for p in sel), max(p["cote"] for p in sel) + 1e-9)
    ids = {p["match_id"] for p in sel}
    univers = [p for p in paris if p["match_id"] in ids]
    o, h = plafond(univers, bande), hasard(univers, bande)
    n = len(sel)
    roi = sum(p["profit"] for p in sel) / n
    ecart = None if o["roi"] is None or h["roi"] is None or o["roi"] == h["roi"] else (roi - h["roi"]) / (o["roi"] - h["roi"])
    return {"paris": n, "reussite": sum(p["resultat"] == 1 for p in sel) / n, "roi": roi,
            "roi_hasard": h["roi"], "roi_oracle": o["roi"], "capture": ecart,
            "fuite_suspecte": o["roi"] is not None and roi >= o["roi"] - 1e-12 and n >= 20}


# --- 3. tickets gagnants par construction -----------------------------------------------------------------------

def tickets_gagnants(paris: Sequence[Mapping[str, Any]], bande: tuple[float, float], nb_tickets: int, picks: int,
                     graine: int = 0) -> list[list[Mapping[str, Any]]]:
    """Tickets de `picks` paris, tous gagnants, sur des matchs différents (jamais deux fois le même match, ni dans un
    ticket ni entre tickets). Tirage reproductible. Moins de tickets si les matchs manquent."""
    pm = par_match(paris)
    cand = {m: [p for p in L if p["resultat"] == 1 and dans_bande(p, bande)] for m, L in pm.items()}
    ids = sorted(m for m, L in cand.items() if L)
    rnd = random.Random(graine)
    rnd.shuffle(ids)
    tickets = []
    for t in range(nb_tickets):
        lot = ids[t * picks:(t + 1) * picks]
        if len(lot) < picks:
            break
        tickets.append([rnd.choice(sorted(cand[m], key=lambda p: p["marche"])) for m in lot])
    return tickets


def cote_ticket(ticket: Sequence[Mapping[str, Any]]) -> float:
    return math.prod(p["cote"] for p in ticket)


# --- rapport ----------------------------------------------------------------------------------------------------

def rapport(paris: Sequence[Mapping[str, Any]]) -> str:
    lignes = [f"{len(paris)} paris réglés, {len({p['match_id'] for p in paris})} matchs, "
              f"{min(p['date'] for p in paris)} -> {max(p['date'] for p in paris)}",
              "bande        matchs  oracle(1 pari/match)   hasard (tous les paris de la bande)",
              "                      réussite   ROI        paris   réussite  équilibre   ROI"]
    for b in BANDES:
        o, h = plafond(paris, b), hasard(paris, b)
        if not o["matchs_eligibles"]:
            continue
        lignes.append(f"{b[0]:.2f}-{min(b[1], 99):<5.2f} {o['matchs_eligibles']:6d}  {100 * o['reussite']:7.1f}%  {100 * o['roi']:+8.1f}%  "
                      f"{h['paris']:7d}  {100 * h['reussite']:7.1f}%  {100 * h['equilibre']:8.1f}%  {100 * h['roi']:+6.1f}%")
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bande", nargs=2, type=float, metavar=("MIN", "MAX"))
    ap.add_argument("--tickets", nargs=3, type=int, metavar=("N", "PICKS", "GRAINE"), help="tickets gagnants par construction")
    a = ap.parse_args(argv)
    paris = charge_paris()
    print(rapport(paris))
    if a.tickets:
        b = tuple(a.bande) if a.bande else (1.30, 1.60)
        for i, t in enumerate(tickets_gagnants(paris, b, a.tickets[0], a.tickets[1], a.tickets[2]), 1):
            print(f"ticket {i} (cote {cote_ticket(t):.2f}) : " + " | ".join(f"{p['date']} {p['marche']} @{p['cote']}" for p in t))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
