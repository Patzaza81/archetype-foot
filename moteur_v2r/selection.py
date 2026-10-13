"""Sélection : EV calibrée >= seuil, dans une bande de cotes, au plus `max_par_match` paris par match.
Règle : si rien ne passe, le moteur ne propose RIEN (ne pas parier est le seul résultat sans perte garanti
quand aucun avantage n'est démontré)."""


def ev(p, cote, p_remb=0.0):
    """EV par unité misée ; le remboursement (push) est traité comme perte (conservateur)."""
    return p * (cote - 1) - (1 - p)


def choisir(lignes, seuil, cote_min, cote_max, max_par_match=1):
    """lignes: dicts avec mid, o (cote), ev. Retourne la sélection triée par EV décroissante."""
    par_match = {}
    for l in lignes:
        if l["ev"] >= seuil and cote_min <= l["o"] < cote_max:
            par_match.setdefault(l["mid"], []).append(l)
    out = []
    for mid in sorted(par_match):
        B = sorted(par_match[mid], key=lambda l: (-l["ev"], l["lib"]))
        out += B[:max_par_match]
    return out
