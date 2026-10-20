"""Lecture des marchés Betpawa : condition sur le score final (i = buts du domicile, j = buts de l'extérieur) et libellé français.

Groupes lus : 1X2, double chance, les deux marquent, totaux, totaux par équipe, handicaps (2 et 3 issues), cages inviolées, nombre exact de buts,
pair/impair, score exact. Un groupe ou une sélection inconnu renvoie None : il n'est jamais deviné.
"""
from __future__ import annotations

import re
from typing import Any, Callable


Test = Callable[[int, int], bool]


def test_du_marche(groupe: str, selection: str) -> Test | None:
    """Condition sur le score final (i = buts du domicile, j = buts de l'extérieur) qui fait gagner la sélection."""
    s = str(selection)
    if groupe == "1x2":
        return {"1": lambda i, j: i > j, "N": lambda i, j: i == j, "2": lambda i, j: i < j}.get(s)
    if groupe == "double_chance":
        return {"1N": lambda i, j: i >= j, "N2": lambda i, j: i <= j, "12": lambda i, j: i != j}.get(s)
    if groupe == "btts":
        return {"Oui": lambda i, j: i >= 1 and j >= 1, "Non": lambda i, j: i == 0 or j == 0}.get(s)
    if groupe == "pair_impair":
        return {"pair": lambda i, j: (i + j) % 2 == 0, "impair": lambda i, j: (i + j) % 2 == 1}.get(s)
    if groupe == "cages_inviolees_domicile":   # cage du domicile inviolée : l'extérieur ne marque pas
        return {"oui": lambda i, j: j == 0, "non": lambda i, j: j >= 1}.get(s)
    if groupe == "cages_inviolees_exterieur":
        return {"oui": lambda i, j: i == 0, "non": lambda i, j: i >= 1}.get(s)
    if groupe == "nombre_exact_buts":
        if s == "6+":
            return lambda i, j: i + j >= 6
        return (lambda i, j, n=int(s): i + j == n) if s.isdigit() else None
    if groupe == "score_exact":
        m = re.fullmatch(r"(\d+)-(\d+)", s)
        return (lambda i, j, a=int(m.group(1)), b=int(m.group(2)): i == a and j == b) if m else None
    m = re.fullmatch(r"over_under_(domicile_|exterieur_)?(\d+(?:\.\d+)?)", groupe)
    if m and s in ("plus", "moins"):
        ligne = float(m.group(2))
        if ligne != int(ligne) + 0.5:      # ligne entière : un score pile sur la ligne est remboursé, non modélisé -> non lu
            return None
        qui = {None: lambda i, j: i + j, "domicile_": lambda i, j: i, "exterieur_": lambda i, j: j}[m.group(1)]
        return (lambda i, j: qui(i, j) > ligne) if s == "plus" else (lambda i, j: qui(i, j) < ligne)
    m = re.fullmatch(r"handicap_(-?\d+(?:\.\d+)?)", groupe)          # 2 issues, ligne appliquée au domicile
    if m and s in ("domicile", "exterieur"):
        h = float(m.group(1))
        if h != int(h) + 0.5 and h != int(h) - 0.5:
            return None                    # ligne entière à 2 issues : remboursement possible, non modélisé -> non lu
        return (lambda i, j: i + h > j) if s == "domicile" else (lambda i, j: i + h < j)
    m = re.fullmatch(r"handicap_3issues_(-?\d+)", groupe)            # 3 issues, ligne entière appliquée au domicile
    if m and s in ("1", "X", "2"):
        h = int(m.group(1))
        return {"1": lambda i, j: i + h > j, "X": lambda i, j: i + h == j, "2": lambda i, j: i + h < j}[s]
    return None


def libelle(groupe: str, selection: str) -> str:
    s = str(selection)
    base = {"1x2": {"1": "Victoire domicile", "N": "Match nul", "2": "Victoire extérieur"},
            "double_chance": {"1N": "Domicile ne perd pas (1N)", "N2": "Extérieur ne perd pas (N2)", "12": "Pas de nul (12)"},
            "btts": {"Oui": "Les deux marquent : oui", "Non": "Les deux marquent : non"},
            "pair_impair": {"pair": "Total de buts pair", "impair": "Total de buts impair"},
            "cages_inviolees_domicile": {"oui": "Cage du domicile inviolée", "non": "Le domicile encaisse"},
            "cages_inviolees_exterieur": {"oui": "Cage de l'extérieur inviolée", "non": "L'extérieur encaisse"}}
    if groupe in base:
        return base[groupe].get(s, f"{groupe} {s}")
    if groupe == "nombre_exact_buts":
        return f"Exactement {s} buts"
    if groupe == "score_exact":
        return f"Score exact {s}"
    m = re.fullmatch(r"over_under_(domicile_|exterieur_)?(\d+(?:\.\d+)?)", groupe)
    if m:
        qui = {None: "", "domicile_": " du domicile", "exterieur_": " de l'extérieur"}[m.group(1)]
        return f"{'Plus' if s == 'plus' else 'Moins'} de {m.group(2).replace('.', ',')} buts{qui}"
    m = re.fullmatch(r"handicap_(-?\d+(?:\.\d+)?)", groupe)
    if m:
        h = float(m.group(1))
        return f"Handicap {h:+g} {'domicile' if s == 'domicile' else 'extérieur'}".replace(".", ",") if s == "domicile" else f"Handicap {-h:+g} extérieur".replace(".", ",")
    m = re.fullmatch(r"handicap_3issues_(-?\d+)", groupe)
    if m:
        return f"Handicap 3 issues domicile {int(m.group(1)):+d} : {{'1': 'domicile', 'X': 'nul', '2': 'extérieur'}}[s]".replace("{'1': 'domicile', 'X': 'nul', '2': 'extérieur'}[s]", {"1": "domicile", "X": "nul", "2": "extérieur"}[s])
    return f"{groupe} {s}"
