"""Cœur « fréquences » de v : scores au même lieu, verrou d'échantillon (inchangeable), coefficient k, alertes de musique.
Règles de Patrick : >= 4 matchs au même lieu pour les DEUX équipes sinon match exclu ; k = 0,8 (4 matchs), 0,9 (5), 1,0 (6 et +) ;
fenêtre des 12 derniers matchs au lieu ; cote minimale 1,26."""
import statistics
from collections import Counter

from .marches import market_def

FENETRE = 12
MIN_MATCHS = 4
COTE_MIN = 1.26


def coef_k(n):
    return None if n < MIN_MATCHS else {4: 0.8, 5: 0.9}.get(n, 1.0)


def lignes(hist, domicile, date_match):
    """Scores (marqués, encaissés) au lieu demandé, STRICTEMENT avant la date du match (aucune fuite du futur), du plus ancien au plus récent."""
    ms = [m for m in (hist or []) if m.get("domicile") is domicile and isinstance(m.get("buts_marques"), int)
          and isinstance(m.get("buts_encaisses"), int) and str(m.get("date") or "") < date_match]
    ms.sort(key=lambda m: str(m.get("date")))
    return [(m["buts_marques"], m["buts_encaisses"]) for m in ms]


def orienter(rows_dom_team, rows_ext_team):
    """Scores vus du match (domicile, extérieur) : l'équipe à l'extérieur a marqué a, encaissé h."""
    return list(rows_dom_team), [(ga, gf) for gf, ga in rows_ext_team]


def _valeurs(rows, serie):
    return [{"diff": h - a, "total": h + a, "h": h, "a": a, "btts": int(h > 0 and a > 0)}[serie] for h, a in rows]


def stabilite(vals, serie):
    n = len(vals)
    if serie == "btts":
        p = sum(vals) / n
        cov = max(p, 1 - p)
    else:
        cov = sum(c for _, c in Counter(vals).most_common(2)) / n
    return "stable" if cov >= 0.8 else ("moyenne" if cov >= 0.65 else "instable")


def alertes_musique(rows_h, rows_a, serie):
    """Alertes seulement (jamais un filtre) : musique instable, pic (écart >= 2 à la médiane), rupture (3 derniers vs avant >= 1)."""
    out = []
    for nom, rows in (("dom", rows_h), ("ext", rows_a)):
        v = _valeurs(rows, serie)
        if stabilite(v, serie) == "instable":
            out.append(f"{nom}:instable")
        if serie != "btts":
            med = statistics.median(v)
            if any(abs(x - med) >= 2 for x in v):
                out.append(f"{nom}:pic")
            if len(v) >= 6:
                recent, avant = v[-3:], v[:-3]
                if abs(sum(recent) / 3 - sum(avant) / len(avant)) >= 1:
                    out.append(f"{nom}:rupture")
    return out


def analyse(rows_dom_team, rows_ext_team, cotes):
    """(n_min, candidats) ; candidats = None si l'une des deux équipes a moins de 4 matchs au lieu (match exclu)."""
    n_min = min(len(rows_dom_team), len(rows_ext_team))
    k = coef_k(n_min)
    if k is None:
        return n_min, None
    rh, ra = orienter(rows_dom_team[-FENETRE:], rows_ext_team[-FENETRE:])
    cands = []
    for key, cote in cotes.items():
        md = market_def(key)
        if md is None or not isinstance(cote, (int, float)) or cote < COTE_MIN:
            continue
        pred, serie = md
        s_h = sum(pred(h, a) for h, a in rh) / len(rh)
        s_a = sum(pred(h, a) for h, a in ra) / len(ra)
        cands.append({"marche": key, "cote": float(cote), "sH": s_h, "sA": s_a, "k": k, "final_moy": (s_h + s_a) / 2 * k,
                      "alertes": alertes_musique(rh, ra, serie), "pred": pred})
    return n_min, cands
