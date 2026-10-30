"""Modèle du moteur DC : Dixon-Coles sur TOUS les matchs d'un championnat, vraisemblance pénalisée (shrinkage), décroissance temporelle.

Spécification corrigée (audit du 30/10/2026 des 5 modules reçus) :
- les forces ne s'estiment que sur le championnat entier (chaque match : équipe domicile, équipe extérieur, buts, date) ;
- λ_dom = exp(mu + gamma + att_dom + def_ext), λ_ext = exp(mu + att_ext + def_dom) ; `def` = faiblesse défensive (positive = encaisse plus) ;
- mu (niveau de buts) et gamma (avantage du terrain) sont des paramètres libres ; att et def sont tirés vers 0 (= la moyenne du championnat)
  par la pénalité (1 / 2σ²) Σ(att² + def²) ; ce terme rend aussi la solution unique (pas de contrainte à ajouter) ;
- correction τ de Dixon-Coles (1997) sur 0-0, 1-0, 0-1, 1-1 ; ρ estimé dans la même maximisation ;
- poids temporel w = exp(−xi × âge en jours). σ et xi ne sont PAS choisis sur la vraisemblance pondérée de l'échantillon (elle diverge) :
  ils sont choisis sur la vraisemblance prédictive HORS échantillon (calibrage.py).
Gradient analytique (rapide) ; aucun import d'un autre moteur.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

N_BUTS = 10                                    # grille des scores 0..10 (au-delà : masse négligeable, la grille est renormalisée)
_I = np.arange(N_BUTS + 1)
_LOGFACT = np.array([math.lgamma(k + 1) for k in _I])
RHO_BORNES = (-0.3, 0.3)                       # garde-fou numérique seulement quand ρ est estimé dans l'ajustement


@dataclass
class Ajustement:
    equipes: list[str]
    att: np.ndarray
    dfn: np.ndarray                            # faiblesse défensive
    mu: float
    gamma: float
    rho: float
    sigma: float
    xi: float
    n_matchs: int
    log_vraisemblance: float = 0.0
    indice: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.indice = {e: k for k, e in enumerate(self.equipes)}

    def lambdas(self, dom: str, ext: str) -> tuple[float, float]:
        """Buts attendus ; une équipe inconnue du championnat (aucun match) vaut la moyenne (force 0)."""
        a, b = self.indice.get(dom), self.indice.get(ext)
        ad, dd = (self.att[a], self.dfn[a]) if a is not None else (0.0, 0.0)
        ae, de = (self.att[b], self.dfn[b]) if b is not None else (0.0, 0.0)
        return math.exp(self.mu + self.gamma + ad + de), math.exp(self.mu + ae + dd)


def _tau(x: np.ndarray, y: np.ndarray, lh: np.ndarray, la: np.ndarray, rho: float) -> np.ndarray:
    t = np.ones_like(lh)
    m00, m10, m01, m11 = (x == 0) & (y == 0), (x == 1) & (y == 0), (x == 0) & (y == 1), (x == 1) & (y == 1)
    t[m00] = 1 - lh[m00] * la[m00] * rho
    t[m10] = 1 + la[m10] * rho
    t[m01] = 1 + lh[m01] * rho
    t[m11] = 1 - rho
    return np.maximum(t, 1e-9)


def ajuster(dom: list[str], ext: list[str], h: np.ndarray, a: np.ndarray, age_jours: np.ndarray, sigma: float, xi: float,
            depart: Ajustement | None = None, rho: float | None = None, mult_xi: np.ndarray | None = None) -> Ajustement:
    """Maximum de vraisemblance pénalisé. `age_jours` = jours entre le match et le jour de la prédiction (≥ 1 : strictement avant).
    `rho` donné = corrélation des scores faibles fixée (estimée une fois pour tous les championnats par vraisemblance prédictive, calibrage.py) ;
    sinon estimée ici. Un ρ libre par championnat se perd dans le bruit et peut rendre une case de score impossible (τ ≤ 0), ce qui a été constaté."""
    equipes = sorted(set(dom) | set(ext))
    idx = {e: k for k, e in enumerate(equipes)}
    n_eq = len(equipes)
    d = np.fromiter((idx[e] for e in dom), int, len(dom))
    e = np.fromiter((idx[x] for x in ext), int, len(ext))
    h, a = np.asarray(h, float), np.asarray(a, float)
    w = np.exp(-xi * np.asarray(age_jours, float) * (1.0 if mult_xi is None else np.asarray(mult_xi, float)))   # xi par match (forme, ajustements.py)
    hi, ai = h.astype(int), a.astype(int)
    pen = 1.0 / (2.0 * sigma ** 2)

    def decode(p):
        return p[:n_eq], p[n_eq:2 * n_eq], p[2 * n_eq], p[2 * n_eq + 1], p[2 * n_eq + 2]

    def f(p):
        att, dfn, mu, gam, rho = decode(p)
        eh = mu + gam + att[d] + dfn[e]
        ea = mu + att[e] + dfn[d]
        lh, la = np.exp(eh), np.exp(ea)
        tau = _tau(hi, ai, lh, la, rho)
        ll = w * (np.log(tau) + h * eh - lh - _logfact(hi) + a * ea - la - _logfact(ai))
        val = -ll.sum() + pen * (att @ att + dfn @ dfn)
        # gradient
        dlh = np.zeros_like(lh)
        dla = np.zeros_like(la)
        m00, m10, m01 = (hi == 0) & (ai == 0), (hi == 1) & (ai == 0), (hi == 0) & (ai == 1)
        dlh[m00] = -la[m00] * rho / tau[m00]
        dla[m00] = -lh[m00] * rho / tau[m00]
        dla[m10] = rho / tau[m10]
        dlh[m01] = rho / tau[m01]
        gh = w * (h - lh + lh * dlh)                  # d logL / d eta_dom
        ga = w * (a - la + la * dla)                  # d logL / d eta_ext
        drho = np.zeros_like(lh)
        m11 = (hi == 1) & (ai == 1)
        drho[m00] = -lh[m00] * la[m00] / tau[m00]
        drho[m10] = la[m10] / tau[m10]
        drho[m01] = lh[m01] / tau[m01]
        drho[m11] = -1.0 / tau[m11]
        g_att = np.bincount(d, gh, n_eq) + np.bincount(e, ga, n_eq)
        g_dfn = np.bincount(e, gh, n_eq) + np.bincount(d, ga, n_eq)
        g = np.concatenate([-g_att + 2 * pen * att, -g_dfn + 2 * pen * dfn,
                            [-(gh.sum() + ga.sum()), -gh.sum(), -(w * drho).sum()]])
        return val, g

    p0 = np.zeros(2 * n_eq + 3)
    p0[2 * n_eq] = math.log(max(float(np.average(np.concatenate([h, a]), weights=np.concatenate([w, w]))), 0.1))
    if depart is not None:
        for k, nom in enumerate(equipes):
            j = depart.indice.get(nom)
            if j is not None:
                p0[k], p0[n_eq + k] = depart.att[j], depart.dfn[j]
        p0[2 * n_eq:2 * n_eq + 2] = [depart.mu, depart.gamma]
        if rho is None:
            p0[-1] = depart.rho
    if rho is not None:
        p0[-1] = rho
    bornes = [(None, None)] * (2 * n_eq + 2) + [RHO_BORNES if rho is None else (rho, rho)]
    r = minimize(f, p0, jac=True, method="L-BFGS-B", bounds=bornes, options={"maxiter": 300})
    att, dfn, mu, gam, rho = decode(r.x)
    return Ajustement(equipes, att.copy(), dfn.copy(), float(mu), float(gam), float(rho), sigma, xi, len(h), float(-r.fun))


def _logfact(k: np.ndarray) -> np.ndarray:
    return _LOGFACT[np.minimum(k, N_BUTS)] if k.max(initial=0) <= N_BUTS else np.array([math.lgamma(x + 1) for x in k])


def _pmf(lam: float) -> np.ndarray:
    lam = max(lam, 1e-6)
    return np.exp(_I * math.log(lam) - lam - _LOGFACT)


def grille(lh: float, la: float, rho: float) -> np.ndarray:
    """Distribution des scores P(i, j), i = buts domicile, j = buts extérieur (0..10), correction τ, renormalisée."""
    g = np.outer(_pmf(lh), _pmf(la))
    g[0, 0] *= max(1 - lh * la * rho, 1e-6)
    g[1, 0] *= max(1 + la * rho, 1e-6)
    g[0, 1] *= max(1 + lh * rho, 1e-6)
    g[1, 1] *= max(1 - rho, 1e-6)
    return g / g.sum()


def grilles(lh: np.ndarray, la: np.ndarray, rho: np.ndarray) -> np.ndarray:
    """Version vectorisée de grille() : (n, 11, 11), ρ propre à chaque match."""
    lh, la, rho = (np.maximum(np.asarray(x, float), 1e-6) if k < 2 else np.asarray(x, float) for k, x in enumerate((lh, la, rho)))
    ph = np.exp(_I * np.log(lh)[:, None] - lh[:, None] - _LOGFACT)
    pa = np.exp(_I * np.log(la)[:, None] - la[:, None] - _LOGFACT)
    g = ph[:, :, None] * pa[:, None, :]
    g[:, 0, 0] *= np.maximum(1 - lh * la * rho, 1e-6)
    g[:, 1, 0] *= np.maximum(1 + la * rho, 1e-6)
    g[:, 0, 1] *= np.maximum(1 + lh * rho, 1e-6)
    g[:, 1, 1] *= np.maximum(1 - rho, 1e-6)
    return g / g.sum(axis=(1, 2), keepdims=True)


_MASQUES: dict[tuple, np.ndarray] = {}


def masque(cle: tuple, test) -> np.ndarray:
    if cle not in _MASQUES:
        _MASQUES[cle] = np.array([[bool(test(i, j)) for j in _I] for i in _I], dtype=float)
    return _MASQUES[cle]


def probas(g: np.ndarray, cles: list[tuple], tests: dict) -> np.ndarray:
    """Probabilité de chaque marché = somme exacte des cases de la grille qui le font gagner (les combinés comptent leurs cases une seule fois)."""
    return np.array([float((g * masque(c, tests[c])).sum()) for c in cles])


def log_vraisemblance_match(lh: float, la: float, rho: float, h: int, a: int) -> float:
    return math.log(max(grille(lh, la, rho)[min(h, N_BUTS), min(a, N_BUTS)], 1e-12))


# --- Calibrage des probabilités (régression isotone apprise par marché ; copie autonome de la méthode d'omega) ----------
def isotone(x: np.ndarray, y: np.ndarray) -> tuple[list[float], list[float]]:
    """Pool adjacent violators : points (probabilité brute moyenne, fréquence observée) de chaque bloc."""
    o = np.argsort(x)
    blocs: list[list[float]] = []
    for xi, yi in zip(x[o], y[o]):
        blocs.append([xi, yi, 1.0])
        while len(blocs) > 1 and blocs[-2][1] / blocs[-2][2] >= blocs[-1][1] / blocs[-1][2]:
            b = blocs.pop()
            blocs[-1] = [blocs[-1][0] + b[0], blocs[-1][1] + b[1], blocs[-1][2] + b[2]]
    return [round(b[0] / b[2], 6) for b in blocs], [round(b[1] / b[2], 6) for b in blocs]


def calibrer(p: float | np.ndarray, points: list[list[float]] | None) -> float | np.ndarray:
    """Probabilité calibrée (interpolation entre blocs) ; sans points appris, la probabilité brute est rendue telle quelle."""
    return p if not points else np.interp(p, points[0], points[1])
