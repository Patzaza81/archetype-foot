"""Enjeu RÉEL d'un match de phase de ligue européenne, calculé sur le classement et les matchs restants (jamais supposé).

Format UEFA (règle du tournoi, pas un réglage) : 36 équipes, 8 matchs chacune ; rangs 1-8 = 1/8e de finale directs, 9-24 = play-off, 25-36 = éliminées.
Pour chaque frontière L (8 puis 24), une équipe est :
- « acquise »    si, même sans un point de plus, moins de L autres équipes peuvent la rejoindre ou la dépasser (égalité comptée comme dépassement possible) ;
- « perdue »     si, même avec tous les points restants, au moins L autres équipes ont déjà strictement plus de points ;
- « ouverte »    sinon.
L'enjeu est RÉEL si au moins une frontière est ouverte ; NUL si les deux sont décidées (zone fixée mathématiquement). Hors phase de ligue, ou classement absent : None (non calculé).
Le classement sert par ses POINTS (écart entre les deux équipes, distance de chaque équipe aux lignes), jamais par le rang. Les départages (différence de buts…) ne sont pas simulés : une égalité de points reste « ouverte » (prudent).
"""
from __future__ import annotations

from typing import Any

from .donnees import norm

MATCHS_PHASE = 8
FRONTIERES = (8, 24)
POINTS_VICTOIRE = 3


def _statut(pts: int, max_pts: int, autres: list[dict[str, int]], L: int) -> str:
    peuvent_rejoindre = sum(1 for o in autres if o["max"] >= pts)
    deja_devant = sum(1 for o in autres if o["pts"] > max_pts)
    if peuvent_rejoindre <= L - 1:
        return "acquise"
    if deja_devant >= L:
        return "perdue"
    return "ouverte"


def enjeu(classement: list[dict[str, Any]] | None, equipe: str) -> dict[str, Any] | None:
    rows = [r for r in classement or [] if isinstance(r.get("pts"), int) and isinstance(r.get("j"), int)]
    if len(rows) < 2 or max(r["j"] for r in rows) > MATCHS_PHASE:
        return None
    base = [{"nom": norm(r["equipe"]), "pts": r["pts"], "j": r["j"], "max": r["pts"] + POINTS_VICTOIRE * (MATCHS_PHASE - r["j"])} for r in rows]
    moi = next((b for b in base if b["nom"] == norm(equipe)), None)
    if moi is None:
        return None
    autres = [b for b in base if b is not moi]
    st = {str(L): _statut(moi["pts"], moi["max"], autres, L) for L in FRONTIERES}
    # distance en POINTS à chaque ligne (points de l'équipe qui occupe actuellement le rang L), jamais en rangs : le 15e et le 25e peuvent n'avoir qu'un point d'écart
    pts_tries = sorted((b["pts"] for b in base), reverse=True)
    ecart = {str(L): moi["pts"] - pts_tries[L - 1] for L in FRONTIERES}
    return {"equipe": equipe, "pts": moi["pts"], "j": moi["j"], "restants": MATCHS_PHASE - moi["j"], "ecart_ligne": ecart, "frontieres": st,
            "reel": any(v == "ouverte" for v in st.values())}


def ecart_points(classement: list[dict[str, Any]] | None, dom: str, ext: str) -> int | None:
    """Écart de points entre les deux équipes du match (domicile − extérieur) dans le même classement ; None si l'une manque."""
    pts = {norm(r["equipe"]): r["pts"] for r in classement or [] if isinstance(r.get("pts"), int)}
    a, b = pts.get(norm(dom)), pts.get(norm(ext))
    return None if a is None or b is None else a - b
