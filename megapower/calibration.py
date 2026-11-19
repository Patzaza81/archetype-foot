"""Calibrage de MEGAPOWER v2 : transformer la probabilité du modèle en fréquence RÉELLE observée, famille de marchés par famille.

Pour chaque famille, régression logistique sur les matchs joués :  logit(réussite réelle) = a + b·logit(P normale) + c·logit(P du scénario catastrophe).
La constance entre donc dans le calibrage : si le scénario catastrophe aide à prévoir la réussite réelle, son poids c est positif ; sinon il s'annule.
Aucun seuil n'est posé ici : `choisir` ne garde que ce qui est calibré au-dessus de la fiabilité demandée.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from . import modele as M

FIAB_Z = 1.645                                 # borne basse unilatérale à 95 %


def famille(nom: str) -> str:
    if "&" in nom:
        return ("double chance" if nom.split("&")[0] in ("1N", "N2", "12") else "victoire ou nul") + (" + les deux marquent" if "btts" in nom else " + total de buts")
    if nom in ("1", "N", "2"):
        return "victoire ou nul"
    if nom in ("1N", "N2", "12"):
        return "double chance"
    return {"total": "total de buts", "btts": "les deux marquent", "dom": "buts du domicile", "ext": "buts de l'extérieur", "cage": "cage inviolée"}[nom.split("_")[0]]


FAMILLE = np.array([famille(n) for n in M.NOMS])
FAMILLES = sorted(set(FAMILLE))


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _A(pn, pc, pl=None):
    """Colonnes : 1, logit(P normale), logit(P catastrophe) et, si fournie, logit(fréquence réelle récente du marché dans ce championnat = nature du championnat)."""
    cols = [np.ones(len(pn)), logit(pn), logit(pc)] + ([logit(pl)] if pl is not None else [])
    return np.column_stack(cols)


def _ajuster(A, y, ridge=1e-3):
    w0 = np.array([0.0, 1.0, 0.0] + [0.0] * (A.shape[1] - 3))
    f = lambda w: float((np.logaddexp(0, A @ w) - y * (A @ w)).sum() + ridge * ((w - w0) ** 2).sum())
    g = lambda w: A.T @ (1 / (1 + np.exp(-(A @ w))) - y) + 2 * ridge * (w - w0)
    return minimize(f, w0, jac=g, method="BFGS").x


def _cov(A, y, w, groupes):
    """Incertitude des coefficients en comptant un match comme une seule observation (ses marchés bougent ensemble)."""
    p = 1 / (1 + np.exp(-(A @ w)))
    H = (A * (p * (1 - p))[:, None]).T @ A + 2e-3 * np.eye(A.shape[1])
    _, inv = np.unique(groupes, return_inverse=True)
    G = np.zeros((inv.max() + 1, A.shape[1]))
    np.add.at(G, inv, A * (p - y)[:, None])
    Hi = np.linalg.inv(H)
    return Hi @ (G.T @ G) @ Hi


def apprendre(pn, pc, y, marche, groupes, pl=None) -> dict:
    """Un modèle par famille. pn, pc, y, marche, groupes : une valeur par ligne (match, marché)."""
    fam = FAMILLE[marche]
    out = {}
    for f in FAMILLES:
        m = fam == f
        if m.sum() < 50 or len(np.unique(y[m])) < 2:
            continue
        A = _A(pn[m], pc[m], None if pl is None else pl[m])
        w = _ajuster(A, y[m])
        out[f] = {"w": [float(v) for v in w], "cov": _cov(A, y[m], w, groupes[m]).tolist(), "lignes": int(m.sum()), "matchs": int(len(np.unique(groupes[m]))), "reussite": float(y[m].mean())}
    return out


def predire(cal: dict, pn, pc, marche, pl=None) -> tuple[np.ndarray, np.ndarray]:
    """(fréquence réelle attendue, sa borne basse à 95 %) pour chaque ligne ; NaN si la famille n'a pas été apprise."""
    fam = FAMILLE[marche]
    q, bas = np.full(len(pn), np.nan), np.full(len(pn), np.nan)
    sig = lambda v: 1 / (1 + np.exp(-v))
    for f, r in cal.items():
        m = fam == f
        if not m.any():
            continue
        A = _A(pn[m], pc[m], pl[m] if pl is not None and len(r["w"]) == 4 else None)
        eta = A @ np.array(r["w"])
        se = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", A, np.array(r["cov"]), A), 0))
        q[m], bas[m] = sig(eta), sig(eta - FIAB_Z * se)
    return q, bas


# ------------------------------------------------------------------------------------------------ sélection
def _inclusions() -> np.ndarray:
    """inc[i, j] = vrai si le marché i implique le marché j (toute grille de scores qui valide i valide aussi j), i ≠ j."""
    G = M.TABLE.reshape(-1, M.NB) > 0.5                      # (scores, marchés)
    inc = (G[:, :, None] <= G[:, None, :]).all(axis=0)
    np.fill_diagonal(inc, False)
    egaux = (G[:, :, None] == G[:, None, :]).all(axis=0)     # deux marchés identiques : on ne garde que le premier
    return inc & ~egaux


INCLUT = _inclusions()
IDENTIQUE = (M.TABLE.reshape(-1, M.NB)[:, :, None] == M.TABLE.reshape(-1, M.NB)[:, None, :]).all(axis=0) & ~np.eye(M.NB, dtype=bool)


def choisir(q: np.ndarray, ok: np.ndarray) -> list[int]:
    """Marchés retenus d'un match. `q` = fiabilité calibrée de chaque marché (NaN si inconnue), `ok` = marchés qui passent la barre.
    Jamais deux fois le même événement : si un marché en implique un autre retenu, on garde le plus précis (celui qui implique) ; deux marchés identiques : un seul.
    Résultat classé du plus fiable au moins fiable."""
    cand = [k for k in np.nonzero(ok)[0]]
    garde = []
    for k in cand:
        if any(INCLUT[j, k] for j in cand if j != k):          # un marché plus précis impliquant k passe aussi : k est redondant
            continue
        if any(IDENTIQUE[k, j] for j in garde):
            continue
        garde.append(k)
    return sorted(garde, key=lambda k: -q[k])
