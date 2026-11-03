"""Définition INDÉPENDANTE des marchés (audit du 02/11/2026) : relit la clé (groupe, sélection) et reconstruit le texte, la formule et la règle de règlement
sans passer par `marches.py`. Sert à prouver que chacun des marchés générés fait ce que son nom dit (`tests/test_moteur_omega_v3.py`, `audit.py`).

i = buts du domicile, j = buts de l'extérieur. Règlement : 1 gagné, 0 perdu, 2 remboursé.
"""
from __future__ import annotations

import re
from typing import Callable

Regle = Callable[[int, int], int]


def _b(x: bool) -> int:
    return 1 if x else 0


def _entier(solde: int) -> int:
    return 1 if solde > 0 else (2 if solde == 0 else 0)


def _num(t: str) -> str:
    return t.replace(".", ",")


def definition(g: str, s: str) -> tuple[str, str, Regle]:
    """(définition en français, formule, règle de règlement) du marché (g, s). Lève ValueError si la clé n'est pas un marché connu."""
    r: re.Match | None
    permis = {"plus": ("plus", "moins"), "oui": ("oui", "non")}
    if re.fullmatch(r"over_under_.*", g) and s not in permis["plus"]:
        raise ValueError(f"sélection inconnue pour {g} : {s}")
    if g.startswith("cages_inviolees_") and s not in permis["oui"]:
        raise ValueError(f"sélection inconnue pour {g} : {s}")
    if g == "btts" and s not in ("Oui", "Non"):
        raise ValueError(f"sélection inconnue pour {g} : {s}")
    if (g == "handicap_0" or re.fullmatch(r"handicap_-?\d+\.5", g)) and s not in ("domicile", "exterieur"):
        raise ValueError(f"sélection inconnue pour {g} : {s}")
    if g == "nombre_exact_buts" and not re.fullmatch(r"\d+\+?", s):
        raise ValueError(f"sélection inconnue pour {g} : {s}")
    if g == "1x2":
        f = {"1": ("le domicile gagne", "i > j", lambda i, j: _b(i > j)), "N": ("match nul", "i = j", lambda i, j: _b(i == j)), "2": ("l'extérieur gagne", "i < j", lambda i, j: _b(i < j))}[s]
        return f
    if g == "double_chance":
        return {"1N": ("domicile gagne ou nul", "i ≥ j", lambda i, j: _b(i >= j)), "N2": ("nul ou extérieur gagne", "i ≤ j", lambda i, j: _b(i <= j)),
                "12": ("pas de match nul", "i ≠ j", lambda i, j: _b(i != j))}[s]
    if g == "btts":
        return (("les deux équipes marquent", "i ≥ 1 et j ≥ 1", lambda i, j: _b(i >= 1 and j >= 1)) if s == "Oui"
                else ("au moins une équipe ne marque pas", "i = 0 ou j = 0", lambda i, j: _b(i == 0 or j == 0)))
    if g == "multigoal":
        lo, hi = {"0-1": (0, 1), "2-3": (2, 3), "4+": (4, 10 ** 6)}[s]
        return (f"total de buts entre {lo} et {hi}" if hi < 10 ** 6 else f"total de buts d'au moins {lo}", f"{lo} ≤ i + j ≤ {hi}" if hi < 10 ** 6 else f"i + j ≥ {lo}", lambda i, j: _b(lo <= i + j <= hi))
    if (r := re.fullmatch(r"over_under_(\d+)", g)):
        n = int(r.group(1))
        if s == "plus":
            return f"plus de {n} buts, remboursé si exactement {n}", f"i + j > {n} (remboursé si = {n})", lambda i, j: _entier(i + j - n)
        return f"moins de {n} buts, remboursé si exactement {n}", f"i + j < {n} (remboursé si = {n})", lambda i, j: _entier(n - (i + j))
    if (r := re.fullmatch(r"over_under_(\d+\.5)", g)):
        x = float(r.group(1))
        return ((f"plus de {_num(r.group(1))} buts dans le match", f"i + j > {_num(r.group(1))}", lambda i, j: _b(i + j > x)) if s == "plus"
                else (f"moins de {_num(r.group(1))} buts dans le match", f"i + j < {_num(r.group(1))}", lambda i, j: _b(i + j < x)))
    if (r := re.fullmatch(r"over_under_(domicile|exterieur)_(\d+\.5)", g)):
        x, dom = float(r.group(2)), r.group(1) == "domicile"
        v = "i" if dom else "j"
        eq = "le domicile" if dom else "l'extérieur"
        pick: Callable[[int, int], int] = (lambda i, j: i) if dom else (lambda i, j: j)
        return ((f"plus de {_num(r.group(2))} buts pour {eq}", f"{v} > {_num(r.group(2))}", lambda i, j: _b(pick(i, j) > x)) if s == "plus"
                else (f"moins de {_num(r.group(2))} buts pour {eq}", f"{v} < {_num(r.group(2))}", lambda i, j: _b(pick(i, j) < x)))
    if g == "cages_inviolees_domicile":
        return (("le domicile n'encaisse aucun but", "j = 0", lambda i, j: _b(j == 0)) if s == "oui" else ("le domicile encaisse au moins un but", "j ≥ 1", lambda i, j: _b(j >= 1)))
    if g == "cages_inviolees_exterieur":
        return (("l'extérieur n'encaisse aucun but", "i = 0", lambda i, j: _b(i == 0)) if s == "oui" else ("l'extérieur encaisse au moins un but", "i ≥ 1", lambda i, j: _b(i >= 1)))
    if g == "victoire_sans_encaisser_domicile":
        return "le domicile gagne sans encaisser", "i > j et j = 0", lambda i, j: _b(i > j and j == 0)
    if g == "victoire_sans_encaisser_exterieur":
        return "l'extérieur gagne sans encaisser", "j > i et i = 0", lambda i, j: _b(j > i and i == 0)
    if g == "handicap_0":
        return (("domicile gagne, remboursé si nul", "i > j (remboursé si i = j)", lambda i, j: _entier(i - j)) if s == "domicile"
                else ("extérieur gagne, remboursé si nul", "j > i (remboursé si i = j)", lambda i, j: _entier(j - i)))
    if (r := re.fullmatch(r"handicap_(-?\d+\.5)", g)):
        h = float(r.group(1))
        sg = f"{'+' if h > 0 else '−'}{_num(str(abs(h)))}"
        return ((f"domicile avec handicap {sg}", f"i + ({h:g}) > j".replace(".", ","), lambda i, j: _b(i + h > j)) if s == "domicile"
                else (f"extérieur avec handicap {'+' if -h > 0 else '−'}{_num(str(abs(h)))}", f"j + ({-h:g}) > i".replace(".", ","), lambda i, j: _b(i + h < j)))
    if (r := re.fullmatch(r"handicap_3issues_(-?\d+)", g)):
        h = int(r.group(1))
        return {"1": (f"handicap {h:+d} sur le domicile, issue 1", f"i + ({h}) > j", lambda i, j: _b(i + h > j)),
                "X": (f"handicap {h:+d} sur le domicile, issue X", f"i + ({h}) = j", lambda i, j: _b(i + h == j)),
                "2": (f"handicap {h:+d} sur le domicile, issue 2", f"i + ({h}) < j", lambda i, j: _b(i + h < j))}[s]
    if g == "nombre_exact_buts":
        if s.endswith("+"):
            n = int(s[:-1])
            return f"{n} buts ou plus dans le match", f"i + j ≥ {n}", lambda i, j: _b(i + j >= n)
        n = int(s)
        return f"exactement {n} but(s) dans le match", f"i + j = {n}", lambda i, j: _b(i + j == n)
    if g == "score_exact":
        if s == "autre":
            return "un autre score (6 buts ou plus pour une équipe)", "i ≥ 6 ou j ≥ 6", lambda i, j: _b(i >= 6 or j >= 6)
        a, b = (int(x) for x in s.split("-"))
        return f"score exact {a}-{b}", f"i = {a} et j = {b}", lambda i, j: _b(i == a and j == b)
    # combinés : « résultat | total », « résultat | les deux marquent », « les deux marquent | total »
    base = {"1": ("le domicile gagne", "i > j", lambda i, j: i > j), "N": ("nul", "i = j", lambda i, j: i == j), "2": ("l'extérieur gagne", "i < j", lambda i, j: i < j),
            "1N": ("domicile gagne ou nul", "i ≥ j", lambda i, j: i >= j), "N2": ("nul ou extérieur gagne", "i ≤ j", lambda i, j: i <= j), "12": ("pas de nul", "i ≠ j", lambda i, j: i != j),
            "Oui": ("les deux marquent", "i ≥ 1 et j ≥ 1", lambda i, j: i >= 1 and j >= 1), "Non": ("une équipe au moins ne marque pas", "i = 0 ou j = 0", lambda i, j: i == 0 or j == 0)}
    if (r := re.fullmatch(r"(dc|1x2|btts)_total_(\d+\.5)", g)):
        a, sens = s.split("|")
        x = float(r.group(2))
        t, ft, fn = base[a]
        plus = sens == "plus"
        return (f"{t} et {'plus' if plus else 'moins'} de {_num(r.group(2))} buts", f"({ft}) et i + j {'>' if plus else '<'} {_num(r.group(2))}",
                lambda i, j: _b(fn(i, j) and ((i + j > x) if plus else (i + j < x))))
    if g in ("dc_btts", "1x2_btts"):
        a, b = s.split("|")
        t1, f1, fn1 = base[a]
        t2, f2, fn2 = base[b]
        return f"{t1} et {t2}", f"({f1}) et ({f2})", lambda i, j: _b(fn1(i, j) and fn2(i, j))
    raise ValueError(f"marché inconnu : {g} / {s}")
