"""Statut SUPER FAVORI des paris modérés de v2r (décision de Patrick, 14/10/2026).

Indice (en %) = moyenne de deux parts, calculées sur les buts seulement :
- part des matchs de l'équipe à domicile, JOUÉS À DOMICILE, où le pari modéré aurait été gagné ;
- part des matchs de l'équipe à l'extérieur, JOUÉS À L'EXTÉRIEUR, où il aurait été gagné.
Indice >= 75 % -> SUPER FAVORI. Pas de pire scénario, pas de Poisson. Minimum 3 matchs au lieu par équipe, sinon pas
d'indice. Marchés sans indice (aucune lecture « buts » simple) : nul, pair/impair, « encaisse au moins 1 but »,
handicap à ligne entière. Autonome : seules les données de v2r (historiques de l'archive) entrent dans le calcul.
Information seulement : ne change ni le choix du pari, ni la cote, ni les règles de v2r."""
import re

SEUIL = 0.75
MIN_MATCHS_LIEU = 3


def fonction(lib):
    """Marge en buts du libellé pour un score (h, a) de l'équipe à domicile / à l'extérieur ; > 0 = pari gagné. None si non calculable."""
    m = re.fullmatch(r"(Plus|Moins) de (\d+(?:\.\d+)?) buts", lib)
    if m:
        x = float(m[2])
        return (lambda h, a: h + a - x) if m[1] == "Plus" else (lambda h, a: x - h - a)
    m = re.fullmatch(r"(Plus|Moins) de (\d+(?:\.\d+)?) buts - (Domicile|Extérieur)", lib)
    if m:
        x, dom = float(m[2]), m[3] == "Domicile"
        g = (lambda h, a: h) if dom else (lambda h, a: a)
        return (lambda h, a: g(h, a) - x) if m[1] == "Plus" else (lambda h, a: x - g(h, a))
    m = re.fullmatch(r"Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur)", lib)
    if m:
        x = float(m[1])
        if x == int(x):
            return None
        return (lambda h, a: h - a + x) if m[2] == "Domicile" else (lambda h, a: a - h + x)
    m = re.fullmatch(r"Cage inviolée - (Domicile|Extérieur)", lib)
    if m:
        return (lambda h, a: .5 - a) if m[1] == "Domicile" else (lambda h, a: .5 - h)
    return {"Double chance - 1X": lambda h, a: h - a + .5, "Double chance - X2": lambda h, a: a - h + .5,
            "Double chance - 12": lambda h, a: abs(h - a) - .5, "BTTS - non": lambda h, a: .5 - min(h, a),
            "BTTS - oui": lambda h, a: min(h, a) - .5, "1X2 - 1": lambda h, a: h - a - .5,
            "1X2 - 2": lambda h, a: a - h - .5}.get(lib)


def indice(lib, hd, he):
    """Indice en fraction (0 à 1) ou None. hd / he : historiques des deux équipes ({domicile, buts_marques, buts_encaisses})."""
    f = fonction(lib)
    if f is None:
        return None
    dom = [x for x in hd if x.get("domicile")]
    ext = [x for x in he if not x.get("domicile")]
    if len(dom) < MIN_MATCHS_LIEU or len(ext) < MIN_MATCHS_LIEU:
        return None
    a = sum(1 for x in dom if f(x["buts_marques"], x["buts_encaisses"]) > 0) / len(dom)
    b = sum(1 for x in ext if f(x["buts_encaisses"], x["buts_marques"]) > 0) / len(ext)
    return (a + b) / 2


def statut(lib, hd, he):
    """{indice_pct (0-100 ou None), super_favori (bool)}."""
    i = indice(lib, hd, he)
    return dict(indice_pct=None if i is None else round(i * 100, 1), super_favori=bool(i is not None and i >= SEUIL - 1e-9))
