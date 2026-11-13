"""Marchés du moteur Omega V3 : générés à partir des SCORES possibles (spécification Omega V1, §6), jamais d'une liste de pronostics autorisés.

Un marché = une clé (groupe, sélection) au format des cotes BetPawa de l'archive (`cotes_betpawa`) quand ce marché y existe (la cote se lit
directement), sinon une clé propre (marché analysé mais sans cote : il ne peut pas être joué). Sa règle de règlement dit, pour un score final (i, j)
(i = buts du domicile, j = buts de l'extérieur) : 1 = gagné, 0 = perdu, 2 = remboursé (lignes entières, handicap 0 : « marchés à remboursement », §14.12).

Règle des buts entiers (Patrick, 27/10/2026) : « Plus de 1,5 » est l'affichage, la valeur réelle est « au moins 2 buts » ; il n'y a pas de demi-buts.
Lignes (fixes, pour qu'un marché ait toujours la même clé d'un match à l'autre et puisse être calibré) : elles montent jusqu'aux plus hautes valeurs
RÉELLEMENT observées dans l'historique (audit du 02/11/2026 : 9 buts pour une équipe, 10 au total, 9 buts d'écart ; un test échoue si l'historique les dépasse) :
totaux 0,5 à 9,5 et entiers 1 à 9 ; buts d'une équipe 0,5 à 8,5 ; handicaps ±0,5 à ±8,5 et handicap 0 ; handicaps à trois issues ±1 à ±9 ;
nombre exact de buts ; combinés double chance / 1N2 / les deux marquent × total (1,5 à 9,5) ; double chance / 1N2 × les deux marquent ;
tous les scores exacts de 0-0 à 5-5 + « autre score » (au-delà de 5 buts pour une équipe : 1,4 % des matchs, regroupé).

Marchés NON calculables avec les quatre séquences (jamais inventés, §6.7) : voir `NON_CALCULABLES`.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

Regle = Callable[[int, int], int]
Cle = tuple[str, str]

NON_CALCULABLES = (
    "résultat à la mi-temps (aucune donnée mi-temps dans les quatre séquences)",
    "équipe qui marque en premier (aucun modèle temporel)",
    "buteurs, corners, cartons (hors des buts marqués et encaissés)",
    "pair / impair (sans logique de tendance, exclu par décision de Patrick)",
)

# Plus hautes valeurs observées dans l'historique réel (data/assemblage, audit du 02/11/2026 ; relevées le 13/11/2026 : Spartans 1-10 Glasgow City, 08/11). Elles bornent les lignes générées : au-delà, le marché ne peut plus
# distinguer deux scores réels (« plus de X » toujours perdu, « moins de X » toujours gagné). `tests/test_moteur_omega_v3.py` échoue si l'historique les dépasse.
MAX_EQUIPE = 10
MAX_TOTAL = 11
MAX_ECART = 9
LIGNES_TOTAL = tuple(x + 0.5 for x in range(MAX_TOTAL))                              # 0,5 … 9,5
LIGNES_TOTAL_ENTIERES = tuple(range(1, MAX_TOTAL))                                   # 1 … 9
LIGNES_EQUIPE = tuple(x + 0.5 for x in range(MAX_EQUIPE))                            # 0,5 … 8,5
LIGNES_HANDICAP = tuple(-(x + 0.5) for x in reversed(range(MAX_ECART))) + tuple(x + 0.5 for x in range(MAX_ECART))      # ±0,5 … ±8,5
LIGNES_HANDICAP_3 = tuple(range(-MAX_ECART, 0)) + tuple(range(1, MAX_ECART + 1))     # ±1 … ±9 (handicap à trois issues : 1, X, 2)
LIGNES_COMBO = tuple(x + 0.5 for x in range(1, MAX_TOTAL))                           # 1,5 … 9,5
EXACT_MAX = 5                                                                        # nombre exact de buts : 0 … 5 puis « 6+ » (comme la source de cotes)
SCORE_MAX = 5


def _l(x: float) -> str:
    return f"{x:g}"


def _gagne(b: bool) -> int:
    return 1 if b else 0


def _entier(solde: int) -> int:
    """Ligne entière : solde > 0 gagné, = 0 remboursé, < 0 perdu."""
    return 1 if solde > 0 else (2 if solde == 0 else 0)


DC = {"1N": lambda i, j: i >= j, "N2": lambda i, j: i <= j, "12": lambda i, j: i != j}
R1X2 = {"1": lambda i, j: i > j, "N": lambda i, j: i == j, "2": lambda i, j: i < j}
BTTS = {"Oui": lambda i, j: i >= 1 and j >= 1, "Non": lambda i, j: i == 0 or j == 0}
MULTIGOAL = {"0-1": lambda i, j: i + j <= 1, "2-3": lambda i, j: 2 <= i + j <= 3, "4+": lambda i, j: i + j >= 4}


def _construire() -> list[tuple[Cle, Regle]]:
    m: list[tuple[Cle, Regle]] = []

    def ajoute(cle: Cle, f: Callable[[int, int], bool]) -> None:
        m.append((cle, lambda i, j, f=f: _gagne(f(i, j))))

    for s, f in R1X2.items():
        ajoute(("1x2", s), f)
    for s, f in DC.items():
        ajoute(("double_chance", s), f)
    for x in LIGNES_TOTAL:
        ajoute((f"over_under_{_l(x)}", "plus"), lambda i, j, x=x: i + j > x)
        ajoute((f"over_under_{_l(x)}", "moins"), lambda i, j, x=x: i + j < x)
    for n in LIGNES_TOTAL_ENTIERES:                       # lignes entières : remboursement si le total vaut exactement la ligne
        m.append(((f"over_under_{n}", "plus"), lambda i, j, n=n: _entier(i + j - n)))
        m.append(((f"over_under_{n}", "moins"), lambda i, j, n=n: _entier(n - (i + j))))
    for s, f in BTTS.items():
        ajoute(("btts", s), f)
    for s, f in MULTIGOAL.items():
        ajoute(("multigoal", s), f)
    for x in LIGNES_EQUIPE:
        ajoute((f"over_under_domicile_{_l(x)}", "plus"), lambda i, j, x=x: i > x)
        ajoute((f"over_under_domicile_{_l(x)}", "moins"), lambda i, j, x=x: i < x)
        ajoute((f"over_under_exterieur_{_l(x)}", "plus"), lambda i, j, x=x: j > x)
        ajoute((f"over_under_exterieur_{_l(x)}", "moins"), lambda i, j, x=x: j < x)
    ajoute(("cages_inviolees_domicile", "oui"), lambda i, j: j == 0)
    ajoute(("cages_inviolees_domicile", "non"), lambda i, j: j >= 1)
    ajoute(("cages_inviolees_exterieur", "oui"), lambda i, j: i == 0)
    ajoute(("cages_inviolees_exterieur", "non"), lambda i, j: i >= 1)
    ajoute(("victoire_sans_encaisser_domicile", "oui"), lambda i, j: i > j and j == 0)
    ajoute(("victoire_sans_encaisser_exterieur", "oui"), lambda i, j: j > i and i == 0)
    for h in LIGNES_HANDICAP:
        ajoute((f"handicap_{_l(h)}", "domicile"), lambda i, j, h=h: i + h > j)
        ajoute((f"handicap_{_l(h)}", "exterieur"), lambda i, j, h=h: i + h < j)
    m.append((("handicap_0", "domicile"), lambda i, j: _entier(i - j)))      # remboursé si nul (« draw no bet »)
    m.append((("handicap_0", "exterieur"), lambda i, j: _entier(j - i)))
    for x in LIGNES_COMBO:
        for d, fd in DC.items():
            ajoute((f"dc_total_{_l(x)}", f"{d}|plus"), lambda i, j, fd=fd, x=x: fd(i, j) and i + j > x)
            ajoute((f"dc_total_{_l(x)}", f"{d}|moins"), lambda i, j, fd=fd, x=x: fd(i, j) and i + j < x)
        for r, fr in R1X2.items():
            ajoute((f"1x2_total_{_l(x)}", f"{r}|plus"), lambda i, j, fr=fr, x=x: fr(i, j) and i + j > x)
            ajoute((f"1x2_total_{_l(x)}", f"{r}|moins"), lambda i, j, fr=fr, x=x: fr(i, j) and i + j < x)
    for d, fd in DC.items():
        for b, fb in BTTS.items():
            ajoute(("dc_btts", f"{d}|{b}"), lambda i, j, fd=fd, fb=fb: fd(i, j) and fb(i, j))
    for r, fr in R1X2.items():
        for b, fb in BTTS.items():
            ajoute(("1x2_btts", f"{r}|{b}"), lambda i, j, fr=fr, fb=fb: fr(i, j) and fb(i, j))
    for x in LIGNES_COMBO:                                  # les deux équipes marquent × total
        for b, fb in BTTS.items():
            ajoute((f"btts_total_{_l(x)}", f"{b}|plus"), lambda i, j, fb=fb, x=x: fb(i, j) and i + j > x)
            ajoute((f"btts_total_{_l(x)}", f"{b}|moins"), lambda i, j, fb=fb, x=x: fb(i, j) and i + j < x)
    for n in range(EXACT_MAX + 1):                          # nombre exact de buts du match (clés de la source de cotes : « 0 » … « 5 », « 6+ »)
        ajoute(("nombre_exact_buts", str(n)), lambda i, j, n=n: i + j == n)
    ajoute(("nombre_exact_buts", f"{EXACT_MAX + 1}+"), lambda i, j: i + j > EXACT_MAX)
    for h in LIGNES_HANDICAP_3:                             # handicap à trois issues : le handicap h s'ajoute aux buts du domicile
        ajoute((f"handicap_3issues_{h}", "1"), lambda i, j, h=h: i + h > j)
        ajoute((f"handicap_3issues_{h}", "X"), lambda i, j, h=h: i + h == j)
        ajoute((f"handicap_3issues_{h}", "2"), lambda i, j, h=h: i + h < j)
    for a in range(SCORE_MAX + 1):
        for b in range(SCORE_MAX + 1):
            ajoute(("score_exact", f"{a}-{b}"), lambda i, j, a=a, b=b: i == a and j == b)
    ajoute(("score_exact", "autre"), lambda i, j: i > SCORE_MAX or j > SCORE_MAX)
    return m


_MARCHES = _construire()
CLES: list[Cle] = [c for c, _ in _MARCHES]
REGLES: dict[Cle, Regle] = dict(_MARCHES)
INDEX: dict[Cle, int] = {c: k for k, c in enumerate(CLES)}
assert len(CLES) == len(set(CLES)), "clé de marché en double"

_CACHE: dict[tuple[int, int], np.ndarray] = {}


def vecteur(i: int, j: int) -> np.ndarray:
    """Résultat (1 gagné, 0 perdu, 2 remboursé) de TOUS les marchés pour le score (i, j) ; calculé une fois par score."""
    v = _CACHE.get((i, j))
    if v is None:
        v = np.array([f(i, j) for _, f in _MARCHES], dtype=np.int8)
        _CACHE[(i, j)] = v
    return v


def resultat(cle: Cle, i: int, j: int) -> int | None:
    """1 gagné, 0 perdu, 2 remboursé ; None si le marché n'est pas lu (jamais deviné)."""
    f = REGLES.get((cle[0], str(cle[1])))
    return f(i, j) if f else None


def cle_txt(c: Cle) -> str:
    return f"{c[0]}|{c[1]}"


def cle_depuis_txt(t: str) -> Cle:
    g, s = t.split("|", 1)
    return g, s


def libelle(c: Cle) -> str:
    return f"{c[0]} / {c[1]}"


def evenement(c: Cle) -> bytes:
    """Empreinte de l'ÉVÉNEMENT (ensemble des scores gagnants, remboursés compris) : deux marchés aux clés différentes mais de même empreinte
    sont le même pari (ex. cage inviolée de l'extérieur = l'extérieur marque « moins de 0,5 »). Sert à ne jamais proposer deux fois le même événement."""
    grille = np.array([[REGLES[c](i, j) for j in range(MAX_EQUIPE + 2)] for i in range(MAX_EQUIPE + 2)], dtype=np.int8)
    return grille.tobytes()


def famille(c: Cle) -> str:
    g = c[0]
    if g.startswith(("dc_", "1x2_total", "1x2_btts", "btts_total")):
        return "combinés"
    if g in ("1x2", "double_chance") or g.startswith(("handicap_", "victoire_sans")):
        return "résultat"
    if g.startswith(("over_under_domicile", "over_under_exterieur", "cages_inviolees")):
        return "buts d'une équipe"
    if g == "score_exact":
        return "scores exacts"
    return "buts du match"


# Groupes dont toutes les issues sont exclusives et exhaustives : la marge du bookmaker se lit en additionnant 1 / cote.
GROUPES_COMPLETS = {"1x2": ("1", "N", "2"), "btts": ("Oui", "Non"), "cages_inviolees_domicile": ("oui", "non"), "cages_inviolees_exterieur": ("oui", "non")}


def issues_completes(c: Cle) -> tuple[str, ...] | None:
    g = c[0]
    if g in GROUPES_COMPLETS:
        return GROUPES_COMPLETS[g]
    if g.startswith("over_under_") and g[len("over_under_"):].replace(".", "", 1).isdigit() and g.endswith(".5"):
        return ("plus", "moins")
    if g.startswith("over_under_domicile_") or g.startswith("over_under_exterieur_"):
        return ("plus", "moins")
    if g.startswith("handicap_3issues_"):
        return ("1", "X", "2")
    if g == "nombre_exact_buts":
        return tuple(str(n) for n in range(EXACT_MAX + 1)) + (f"{EXACT_MAX + 1}+",)
    if g.startswith("handicap_") and g != "handicap_0" and g.endswith(".5"):
        return ("domicile", "exterieur")
    return None
