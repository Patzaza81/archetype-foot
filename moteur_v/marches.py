"""Lecture des libellés de marchés de cotes_observees. Chaque marché = prédicat(h, a) sur le score final (h domicile, a extérieur)."""
import re

_NUM = r"(-?\d+(?:\.\d+)?)"


def market_def(key):
    """Retourne (prédicat(h, a), série) ou None. La série ('diff', 'total', 'h', 'a', 'btts') sert aux alertes de musique."""
    m = re.fullmatch(r"1X2 - (1|X|2)", key)
    if m:
        return ({"1": lambda h, a: h > a, "X": lambda h, a: h == a, "2": lambda h, a: h < a}[m.group(1)], "diff")
    m = re.fullmatch(r"Double chance - (1X|X2|12)", key)
    if m:
        return ({"1X": lambda h, a: h >= a, "X2": lambda h, a: h <= a, "12": lambda h, a: h != a}[m.group(1)], "diff")
    m = re.fullmatch(r"BTTS - (oui|non)", key)
    if m:
        oui = m.group(1) == "oui"
        return ((lambda h, a: (h > 0 and a > 0) == oui), "btts")
    m = re.fullmatch(r"(Plus|Moins) de " + _NUM + r" buts - (Domicile|Extérieur)", key)
    if m:
        x, over, dom = float(m.group(2)), m.group(1) == "Plus", m.group(3) == "Domicile"
        if dom:
            return ((lambda h, a: h > x) if over else (lambda h, a: h < x), "h")
        return ((lambda h, a: a > x) if over else (lambda h, a: a < x), "a")
    m = re.fullmatch(r"(Plus|Moins) de " + _NUM + r" buts", key)
    if m:
        x, over = float(m.group(2)), m.group(1) == "Plus"
        return ((lambda h, a: h + a > x) if over else (lambda h, a: h + a < x), "total")
    m = re.fullmatch(r"Handicap " + _NUM + r" - (Domicile|Extérieur)", key)
    if m:                                   # la ligne affichée est celle du domicile ; l'extérieur reçoit l'issue opposée
        x, dom = float(m.group(1)), m.group(2) == "Domicile"
        if abs(x) > 1.5:
            return None
        return ((lambda h, a: h + x > a) if dom else (lambda h, a: h + x < a), "diff")
    m = re.fullmatch(r"Cage inviolée - (Domicile|Extérieur)", key)
    if m:
        dom = m.group(1) == "Domicile"
        return ((lambda h, a: a == 0) if dom else (lambda h, a: h == 0), "a" if dom else "h")
    m = re.fullmatch(r"Encaisse au moins \d+ but - (Domicile|Extérieur)", key)
    if m:
        dom = m.group(1) == "Domicile"
        return ((lambda h, a: a >= 1) if dom else (lambda h, a: h >= 1), "a" if dom else "h")
    return None                              # pair/impair et le reste : non lus


def famille(key):
    if key.startswith("1X2"):
        return "1X2"
    if key.startswith("Double chance"):
        return "Double chance"
    if key.startswith("BTTS"):
        return "BTTS"
    if key.startswith("Handicap"):
        return "Handicap"
    if key.startswith("Cage") or key.startswith("Encaisse"):
        return "Cage / encaisse"
    if " - Domicile" in key or " - Extérieur" in key:
        return "Buts d'une équipe"
    return "Total buts"


def gagne(marche, h, a):
    """True/False selon le score final ; None si le marché n'est pas lu."""
    md = market_def(marche)
    return None if md is None else bool(md[0](h, a))


def cote_cote(marche):
    """Côté parié d'un marché 1X2 / double chance : +1 domicile, -1 extérieur, 0 non concerné."""
    return {"1X2 - 1": 1, "1X2 - 2": -1, "Double chance - 1X": 1, "Double chance - X2": -1}.get(marche, 0)
