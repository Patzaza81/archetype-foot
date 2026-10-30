"""Catalogue des marchés du moteur DC (copie autonome de celui d'omega, 30/10/2026 : aucun import entre moteurs) : condition sur le score final, libellé, lecture en buts entiers.

Clé d'un marché = (groupe, sélection), au format des cotes BetPawa de l'archive (`cotes_betpawa`) : la cote se lit directement.
i = buts du domicile, j = buts de l'extérieur.

Marchés exclus (décisions de Patrick déjà prises sur les autres moteurs) : score exact, nombre exact de buts, plus/moins 5,5 et au-delà,
handicaps de 2,5 et plus, pair/impair, mi-temps, corners, cartons, buteurs.

Règle des buts entiers (Patrick, 27/10/2026) : « Plus de 1,5 » est ce qu'on affiche, le moteur calcule la valeur réelle : au moins 2 buts.
Il n'y a pas de demi-buts. Une valeur de scénario non entière (ex. 1,5 but) peut valoir 1 ou 2 buts : le marché ne tient dans ce scénario
que si TOUS les scores entiers possibles (arrondi inférieur et supérieur de chaque équipe) le font gagner.
"""
from __future__ import annotations

import math
from typing import Callable

Test = Callable[[int, int], bool]
Cle = tuple[str, str]

DC = {"1N": lambda i, j: i >= j, "N2": lambda i, j: i <= j, "12": lambda i, j: i != j}
R1X2 = {"1": lambda i, j: i > j, "N": lambda i, j: i == j, "2": lambda i, j: i < j}
BTTS = {"Oui": lambda i, j: i >= 1 and j >= 1, "Non": lambda i, j: i == 0 or j == 0}
LIGNES_TOTAL = ("1.5", "2.5", "3.5", "4.5")
LIGNES_EQUIPE = ("0.5", "1.5", "2.5")
LIGNES_HANDICAP = ("-1.5", "-0.5", "0.5", "1.5")
LIGNES_COMBO_TOTAL = ("1.5", "2.5", "3.5", "4.5")


def _total(ligne: float, plus: bool) -> Test:
    return (lambda i, j: i + j > ligne) if plus else (lambda i, j: i + j < ligne)


def _equipe(qui: str, ligne: float, plus: bool) -> Test:
    if qui == "domicile":
        return (lambda i, j: i > ligne) if plus else (lambda i, j: i < ligne)
    return (lambda i, j: j > ligne) if plus else (lambda i, j: j < ligne)


def test_du_marche(groupe: str, selection: str) -> Test | None:
    """Condition qui fait gagner la sélection ; None si le marché n'est pas lu par omega (jamais deviné)."""
    g, s = groupe, str(selection)
    if g == "1x2":
        return R1X2.get(s)
    if g == "double_chance":
        return DC.get(s)
    if g == "btts":
        return BTTS.get(s)
    if g == "cages_inviolees_domicile":
        return {"oui": lambda i, j: j == 0, "non": lambda i, j: j >= 1}.get(s)
    if g == "cages_inviolees_exterieur":
        return {"oui": lambda i, j: i == 0, "non": lambda i, j: i >= 1}.get(s)
    if g.startswith("over_under_"):
        reste = g[len("over_under_"):]
        for qui in ("domicile", "exterieur"):
            if reste.startswith(qui + "_"):
                ligne = reste[len(qui) + 1:]
                if ligne in LIGNES_EQUIPE and s in ("plus", "moins"):
                    return _equipe(qui, float(ligne), s == "plus")
                return None
        if reste in LIGNES_TOTAL and s in ("plus", "moins"):
            return _total(float(reste), s == "plus")
        return None
    if g.startswith("handicap_") and not g.startswith("handicap_3issues"):
        ligne = g[len("handicap_"):]
        if ligne in LIGNES_HANDICAP and s in ("domicile", "exterieur"):
            h = float(ligne)
            return (lambda i, j: i + h > j) if s == "domicile" else (lambda i, j: i + h < j)
        return None
    if "|" in s:                                   # combinés BetPawa : « 1N|plus », « 1|Oui »…
        a, b = s.split("|", 1)
        if g.startswith("dc_total_") or g.startswith("1x2_total_"):
            ligne = g.rsplit("_", 1)[1]
            r = DC.get(a) if g.startswith("dc_") else R1X2.get(a)
            if r is None or ligne not in LIGNES_COMBO_TOTAL or b not in ("plus", "moins"):
                return None
            t = _total(float(ligne), b == "plus")
            return lambda i, j: r(i, j) and t(i, j)
        if g in ("dc_btts", "1x2_btts"):
            r = DC.get(a) if g == "dc_btts" else R1X2.get(a)
            t = BTTS.get(b)
            if r is None or t is None:
                return None
            return lambda i, j: r(i, j) and t(i, j)
    return None


def catalogue() -> list[Cle]:
    """Tous les marchés lus par omega, dans l'ordre d'affichage."""
    c: list[Cle] = [("1x2", s) for s in ("1", "N", "2")] + [("double_chance", s) for s in ("1N", "N2", "12")]
    c += [(f"over_under_{x}", s) for x in LIGNES_TOTAL for s in ("plus", "moins")]
    c += [("btts", "Oui"), ("btts", "Non")]
    c += [(f"over_under_{q}_{x}", s) for q in ("domicile", "exterieur") for x in LIGNES_EQUIPE for s in ("plus", "moins")]
    c += [(f"cages_inviolees_{q}", s) for q in ("domicile", "exterieur") for s in ("oui", "non")]
    c += [(f"handicap_{x}", s) for x in LIGNES_HANDICAP for s in ("domicile", "exterieur")]
    c += [(f"dc_total_{x}", f"{d}|{s}") for x in LIGNES_COMBO_TOTAL for d in ("1N", "N2", "12") for s in ("plus", "moins")]
    c += [("dc_btts", f"{d}|{s}") for d in ("1N", "N2", "12") for s in ("Oui", "Non")]
    c += [(f"1x2_total_{x}", f"{r}|{s}") for x in LIGNES_COMBO_TOTAL for r in ("1", "N", "2") for s in ("plus", "moins")]
    c += [("1x2_btts", f"{r}|{s}") for r in ("1", "N", "2") for s in ("Oui", "Non")]
    return c


def famille(cle: Cle) -> str:
    g = cle[0]
    if g.startswith(("dc_", "1x2_total", "1x2_btts")):
        return "combinés"
    if g in ("1x2", "double_chance") or g.startswith("handicap_"):
        return "résultat"
    if g.startswith(("over_under_domicile", "over_under_exterieur", "cages_inviolees")):
        return "buts d'une équipe"
    return "buts du match"


def onglet(cle: Cle) -> str:
    """Trois onglets : buts, équipes (résultat et buts d'une équipe), combinés."""
    f = famille(cle)
    return {"buts du match": "buts", "combinés": "combines"}.get(f, "equipes")


def libelle(cle: Cle) -> str:
    g, s = cle
    noms = {"1x2": {"1": "Victoire domicile", "N": "Match nul", "2": "Victoire extérieur"},
            "double_chance": {"1N": "Domicile ne perd pas", "N2": "Extérieur ne perd pas", "12": "Pas de match nul"},
            "btts": {"Oui": "Les deux équipes marquent", "Non": "Les deux équipes ne marquent pas toutes les deux"},
            "cages_inviolees_domicile": {"oui": "Le domicile n'encaisse pas", "non": "Le domicile encaisse au moins 1 but"},
            "cages_inviolees_exterieur": {"oui": "L'extérieur n'encaisse pas", "non": "L'extérieur encaisse au moins 1 but"}}
    if g in noms:
        return noms[g][s]
    if g.startswith("over_under_"):
        reste = g[len("over_under_"):]
        qui = ""
        for q, mot in (("domicile_", " du domicile"), ("exterieur_", " de l'extérieur")):
            if reste.startswith(q):
                reste, qui = reste[len(q):], mot
        return f"{'Plus' if s == 'plus' else 'Moins'} de {reste.replace('.', ',')} buts{qui}"
    if g.startswith("handicap_"):
        h = float(g[len("handicap_"):])
        v = h if s == "domicile" else -h
        return f"Handicap {v:+g} {'domicile' if s == 'domicile' else 'extérieur'}".replace(".", ",")
    if "|" in s:
        a, b = s.split("|", 1)
        base = noms["double_chance"].get(a) if g.startswith("dc_") else noms["1x2"].get(a)
        if g.endswith("btts"):
            fin = "les deux marquent" if b == "Oui" else "les deux ne marquent pas"
        else:
            fin = f"{'plus' if b == 'plus' else 'moins'} de {g.rsplit('_', 1)[1].replace('.', ',')} buts"
        return f"{base} + {fin}"
    return f"{g} {s}"


def valeur_reelle(cle: Cle) -> str | None:
    """Traduction en buts entiers pour l'affichage (« Plus de 1,5 » = au moins 2 buts)."""
    g, s = cle
    if g.startswith("over_under_") and "|" not in s:
        ligne = float(g.rsplit("_", 1)[1])
        sujet = "dans le match"
        if "_domicile_" in g:
            sujet = "pour le domicile"
        elif "_exterieur_" in g:
            sujet = "pour l'extérieur"
        if s == "plus":
            return f"au moins {math.ceil(ligne)} but{'s' if math.ceil(ligne) > 1 else ''} {sujet}"
        n = math.floor(ligne)
        return f"au plus {n} but{'s' if n > 1 else ''} {sujet}" if n else f"aucun but {sujet}"
    return None


def signature(cle: Cle, max_buts: int = 10) -> frozenset:
    """Ensemble des scores gagnants : deux marchés de même signature sont le même événement (ex. handicap +0,5 et ne perd pas)."""
    t = test_du_marche(*cle)
    return frozenset((i, j) for i in range(max_buts + 1) for j in range(max_buts + 1) if t(i, j))


def tient_en_buts_entiers(t: Test, x: float, y: float) -> bool:
    """Le marché tient dans un scénario (x, y) non arrondi : tous les scores entiers possibles (arrondis bas/haut) le font gagner."""
    xs = {math.floor(x + 1e-9), math.ceil(x - 1e-9)}
    ys = {math.floor(y + 1e-9), math.ceil(y - 1e-9)}
    return all(t(i, j) for i in xs for j in ys)
