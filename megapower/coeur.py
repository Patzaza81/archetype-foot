"""Cœur de MEGAPOWER : apprendre, sur les résultats connus, ce que vaut vraiment un pari face à sa cote, puis ne garder que ce qui paie.

Constat mesuré (voir docs/MOTEUR_MEGAPOWER.md) : la cote du bookmaker contient déjà presque toute l'information ; ce qui compte est donc
  1. la VRAIE réussite d'un pari à une cote donnée, famille de marchés par famille (le bookmaker ne prend pas la même marge partout) ;
  2. l'ACCORD des quatre lectures (Verdict, Alpha, Omega, Gamma) : gardé seulement dans les familles où il améliore la prévision sur des matchs non vus.
Aucun seuil posé à la main : la réussite apprise × la cote donne le gain attendu pour 1 misé ; un pari est « sous observation » si ce gain est positif sur toute la
période ET sur chacune de ses deux moitiés ; il est « prouvé » si même la borne basse (95 %) du gain reste positive.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from . import signaux as S

LECTURES = (("Verdict", "v_dom", "v_ext"), ("Alpha", "a_att", "a_def"), ("Omega", "o_p", "o_p"), ("Gamma", "g_robuste", "g_robuste"))
Z95 = 1.96


def famille(nom: str) -> str:
    if "&" in nom:
        return ("double chance" if nom.split("&")[0] in ("1N", "N2", "12") else "victoire ou nul") + (" + les deux marquent" if "btts" in nom else " + total de buts")
    if nom in ("1", "N", "2"):
        return "victoire ou nul"
    if nom in ("1N", "N2", "12"):
        return "double chance"
    return {"total": "total de buts", "btts": "les deux marquent", "dom": "buts du domicile", "ext": "buts de l'extérieur", "cage": "cage inviolée"}[nom.split("_")[0]]


FAMILLE = np.array([famille(n) for n in S.NOMS])
FAMILLES = sorted(set(FAMILLE))


def accord(T: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """(nombre de lectures qui voient le pari plus probable que la cote ne le dit, nombre de lectures disponibles)."""
    q = 1 / T["cote"]
    pour, dispo = np.zeros(len(q)), np.zeros(len(q))
    for _, a, b in LECTURES:
        s = (T[a] + T[b]) / 2
        ok = ~np.isnan(s)
        pour += np.where(ok, s > q, 0)
        dispo += ok
    return pour, dispo


def _x(T: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    q = np.clip(1 / T["cote"], 1e-6, 1 - 1e-6)
    pour, dispo = accord(T)
    return np.log(q / (1 - q)), (pour > dispo / 2).astype(float)       # la cote, et « la majorité des lectures est pour »


def _ajuster(A: np.ndarray, y: np.ndarray) -> np.ndarray:
    f = lambda w: float((np.logaddexp(0, A @ w) - y * (A @ w)).sum())
    g = lambda w: A.T @ (1 / (1 + np.exp(-(A @ w))) - y)
    w0 = np.zeros(A.shape[1]); w0[1] = 1.0
    return minimize(f, w0, jac=g, method="BFGS").x


def _perte(A: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    return float((np.logaddexp(0, A @ w) - y * (A @ w)).mean())


def _matrice(x: np.ndarray, maj: np.ndarray, avec: bool) -> np.ndarray:
    return np.column_stack([np.ones(len(x)), x, maj] if avec else [np.ones(len(x)), x])


def _cov(A: np.ndarray, y: np.ndarray, w: np.ndarray, groupes: np.ndarray) -> np.ndarray:
    """Incertitude des coefficients, en comptant un match comme une seule observation (ses marchés bougent ensemble)."""
    p = 1 / (1 + np.exp(-(A @ w)))
    H = (A * (p * (1 - p))[:, None]).T @ A
    s = A * (p - y)[:, None]
    _, inv = np.unique(groupes, return_inverse=True)
    G = np.zeros((inv.max() + 1, A.shape[1]))
    np.add.at(G, inv, s)
    Hi = np.linalg.pinv(H)
    return Hi @ (G.T @ G) @ Hi


def apprendre(T: dict[str, np.ndarray], jours: np.ndarray, cote_min: float) -> dict:
    """Modèle par famille, appris sur tous les paris jouables (cote ≥ cote_min) des matchs joués. `jours` = jour du match de chaque ligne."""
    x, maj = _x(T)
    ok = ~np.isnan(T["y"]) & (T["cote"] >= cote_min)
    fam = FAMILLE[T["marche"]]
    dj = np.unique(jours[ok])
    out = {"cote_min": cote_min, "du": str(dj[0]), "au": str(dj[-1]), "matchs": int(len(np.unique(T["match"][ok]))), "paris": int(ok.sum()), "familles": {}}
    for f in FAMILLES:
        m = ok & (fam == f)
        if not m.any():
            continue
        df = np.unique(jours[m])
        coupe = df[len(df) // 2]                               # milieu de la période où cette famille est cotée (les combinés n'existent que depuis le 25/10)
        m1, m2 = m & (jours < coupe), m & (jours >= coupe)
        if min(m1.sum(), m2.sum()) < 2 or len(np.unique(T["y"][m1])) < 2 or len(np.unique(T["y"][m2])) < 2:
            continue
        # l'accord des lectures n'entre que s'il prévoit mieux les matchs de la 2e moitié à partir de la 1re
        pertes = {}
        for avec in (False, True):
            w = _ajuster(_matrice(x[m1], maj[m1], avec), T["y"][m1])
            pertes[avec] = _perte(_matrice(x[m2], maj[m2], avec), T["y"][m2], w)
        avec = pertes[True] < pertes[False]
        A = _matrice(x[m], maj[m], avec)
        w = _ajuster(A, T["y"][m])
        gain = np.where(T["y"][m] == 1, T["cote"][m] - 1, -1)
        out["familles"][f] = {"avec_accord": bool(avec), "w": [float(v) for v in w], "cov": _cov(A, T["y"][m], w, T["match"][m]).tolist(),
                              "w1": [float(v) for v in _ajuster(_matrice(x[m1], maj[m1], avec), T["y"][m1])],
                              "w2": [float(v) for v in _ajuster(_matrice(x[m2], maj[m2], avec), T["y"][m2])],
                              "coupe": str(coupe), "paris": int(m.sum()), "matchs": int(len(np.unique(T["match"][m]))), "reussite": float(T["y"][m].mean()), "rendement_de_tout_jouer": float(gain.mean()),
                              "perte_sans_accord": pertes[False], "perte_avec_accord": pertes[True]}
    return out


def juger(T: dict[str, np.ndarray], modele: dict) -> dict[str, np.ndarray]:
    """Pour chaque ligne : réussite apprise, gain attendu pour 1 misé (estimé, borne basse, sur chaque moitié), statut 2 = prouvé, 1 = sous observation, 0 = écarté."""
    x, maj = _x(T)
    fam = FAMILLE[T["marche"]]
    n = len(x)
    p, bas, g1, g2 = (np.full(n, np.nan) for _ in range(4))
    sig = lambda v: 1 / (1 + np.exp(-v))
    for f, r in modele["familles"].items():
        m = fam == f
        if not m.any():
            continue
        A = _matrice(x[m], maj[m], r["avec_accord"])
        eta = A @ np.array(r["w"])
        se = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", A, np.array(r["cov"]), A), 0))
        p[m], bas[m] = sig(eta), sig(eta - Z95 * se)
        g1[m], g2[m] = sig(A @ np.array(r["w1"])) * T["cote"][m] - 1, sig(A @ np.array(r["w2"])) * T["cote"][m] - 1
    gain, gain_bas = p * T["cote"] - 1, bas * T["cote"] - 1
    jouable = T["cote"] >= modele["cote_min"]
    obs = jouable & (gain >= 0) & (g1 >= 0) & (g2 >= 0)
    statut = np.where(jouable & (gain_bas >= 0), 2, np.where(obs, 1, 0))
    return {"p": p, "gain": gain, "gain_bas": gain_bas, "statut": statut}


def meilleur_par_match(T: dict[str, np.ndarray], J: dict[str, np.ndarray], statut_min: int = 1) -> np.ndarray:
    """Indices des lignes retenues : pour chaque match, le pari de statut le plus haut puis de gain attendu le plus haut (un seul pari par match)."""
    out = []
    ok = np.nonzero(J["statut"] >= statut_min)[0]
    for t in np.unique(T["match"][ok]):
        i = ok[T["match"][ok] == t]
        out.append(i[np.lexsort((-J["gain"][i], -J["statut"][i]))[0]])
    return np.array(out, dtype=int)
