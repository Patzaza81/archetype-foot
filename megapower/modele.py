"""Modèle de buts de MEGAPOWER v2 (aucune cote) : de l'historique des deux équipes aux probabilités de tous les marchés.

Couches (audit du 18/11/2026) :
  1. référentiel du championnat : buts (ou xG) moyens à domicile et à l'extérieur, rapprochés de la moyenne générale d'Omega quand la ligue a peu de matchs ;
  2. force de chaque équipe AU MÊME LIEU (attaque et vulnérabilité défensive), lue sur l'observation « xG mélangé aux buts » (xG réel seulement, jamais inventé) ;
  3. force des adversaires : chaque observation est divisée par ce que l'adversaire laisse normalement (notes attaque/défense de la ligue, calculées avec les seuls matchs d'avant) ;
  4. tendance : projection arithmétique (u+r) ou géométrique (q·u) des derniers indices, avec un poids appris (0 = aucune tendance) ;
  5. situation compétitive : écart de points par match, de différence de buts et de xG par match, avec un coefficient appris (0 = ignoré s'il n'apporte rien) ;
  6. croisement des quatre branches : λA = μdom × ATT(A, dom) × DEF(B, ext) ; λB = μext × ATT(B, ext) × DEF(A, dom) ;
  7. grille de scores Poisson corrigée Dixon-Coles (paramètre d'Omega) -> probabilité de chacun des marchés du catalogue ;
  8. trois scénarios : favorable / normal / catastrophe (les forces bougent de leur incertitude, on garde le pire et le meilleur pour chaque marché).
Aucun nombre n'est posé à la main : chaque paramètre est choisi sur la première moitié des matchs joués et vérifié sur la seconde (`ajuster`).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

import verif_pronostic as V
from moteur_omega import modele as OM

ROOT = Path(__file__).resolve().parent.parent
NMIN = V.NMIN                                   # règle de Patrick : au moins 4 matchs au même lieu pour chaque équipe, sinon pas d'analyse
NOMS, TABLE, NB = V.NOMS, V.TABLE, len(V.NOMS)
P_OMEGA = json.loads((ROOT / "moteur_omega" / "parametres.json").read_text(encoding="utf-8"))
RHO, G_DOM, G_EXT = P_OMEGA["rho"], P_OMEGA["global_dom"], P_OMEGA["global_ext"]
FENETRE_TENDANCE = 6
Z_SCENARIO = 1.0                                # un écart-type : « historiquement plausible » sans être extrême
PAR_DEFAUT = {"w_xg": 0.5, "m_equipe": 3.8756, "m_ligue": 50.0, "theta": 0.0, "tendance": "arith", "beta": 0.0, "ecart": None}


# ------------------------------------------------------------------------------------------------ observations
def _obs(r: dict, cote: str, w: float) -> float:
    """Ce que l'équipe a fait dans ce match : mélange xG / buts (buts seuls si le xG manque)."""
    g, x = (r["gf"], r["xgf"]) if cote == "f" else (r["ga"], r["xga"])
    return float(g) if x is None else w * x + (1 - w) * g


def index_ligues(matchs: list[dict]) -> dict:
    """(championnat, saison) -> {équipe: {date: enregistrement}} : l'union de tous les historiques connus de la ligue."""
    L: dict = {}
    for m in matchs:
        d = L.setdefault((m["competition"], m["saison"]), {})
        for cle, recs in ((m["cle_dom"], m["md"]), (m["cle_ext"], m["me"])):
            e = d.setdefault(cle, {})
            for r in recs:
                e.setdefault(r["date"], r)
    return L


def matchs_ligue(equipes: dict) -> list[dict]:
    """Matchs uniques de la ligue (une ligne par rencontre), vus du côté de chaque équipe connue."""
    vus, out = set(), []
    for eq, recs in equipes.items():
        for r in recs.values():
            dom, ext = (eq, r["adv"]) if r["dom"] else (r["adv"], eq)
            k = (r["date"], dom, ext)
            if k in vus or not r["adv"]:
                continue
            vus.add(k)
            out.append({"date": r["date"], "dom": dom, "ext": ext, "r": r})
    return sorted(out, key=lambda x: x["date"])


class Ligue:
    """Notes d'une ligue à une date : μ domicile/extérieur et notes attaque/défense de chaque équipe (matchs strictement avant la date)."""

    def __init__(self, equipes: dict):
        self.matchs = matchs_ligue(equipes)
        self._cache: dict = {}

    def notes(self, jour: str, w: float, m_eq: float, m_lig: float) -> dict:
        cle = (jour, w, m_eq, m_lig)
        if cle in self._cache:
            return self._cache[cle]
        M = [x for x in self.matchs if x["date"] < jour]
        n = len(M)
        if n == 0:
            res = {"mu_h": G_DOM, "mu_e": G_EXT, "a": {}, "d": {}, "n": 0}
            self._cache[cle] = res
            return res
        gh = np.array([_obs(x["r"], "f" if x["r"]["dom"] else "a", w) for x in M])      # observation de l'équipe à domicile
        ge = np.array([_obs(x["r"], "a" if x["r"]["dom"] else "f", w) for x in M])      # observation de l'équipe à l'extérieur
        mu_h, mu_e = (gh.sum() + m_lig * G_DOM) / (n + m_lig), (ge.sum() + m_lig * G_EXT) / (n + m_lig)
        eq = sorted({x["dom"] for x in M} | {x["ext"] for x in M})
        pos = {e: i for i, e in enumerate(eq)}
        H, E = np.array([pos[x["dom"]] for x in M]), np.array([pos[x["ext"]] for x in M])
        T = len(eq)
        a, d = np.ones(T), np.ones(T)
        for _ in range(15):
            # attaque : buts marqués / ce que la défense d'en face laisse normalement
            den_a = np.bincount(H, mu_h * d[E], T) + np.bincount(E, mu_e * d[H], T)
            num_a = np.bincount(H, gh, T) + np.bincount(E, ge, T)
            cnt = np.bincount(H, minlength=T) + np.bincount(E, minlength=T)
            k = den_a / np.maximum(cnt, 1)
            a = (num_a + m_eq * k) / np.maximum(den_a + m_eq * k, 1e-9)
            den_d = np.bincount(E, mu_h * a[H], T) + np.bincount(H, mu_e * a[E], T)
            num_d = np.bincount(E, gh, T) + np.bincount(H, ge, T)
            k = den_d / np.maximum(cnt, 1)
            d = (num_d + m_eq * k) / np.maximum(den_d + m_eq * k, 1e-9)
            a, d = a / a.mean(), d / d.mean()
        res = {"mu_h": float(mu_h), "mu_e": float(mu_e), "a": dict(zip(eq, a.tolist())), "d": dict(zip(eq, d.tolist())), "n": n}
        self._cache[cle] = res
        return res


# ------------------------------------------------------------------------------------------------ composantes d'un match
def _indice(obs: list[float], attendu: list[float], m_eq: float) -> tuple[float, list[float]]:
    """Indice de force = observé / attendu, rapproché de 1 par m_eq matchs « neutres » ; renvoie aussi la série des rapports dans l'ordre du temps."""
    e = sum(attendu) / len(attendu)
    return (sum(obs) + m_eq * e) / (sum(attendu) + m_eq * e), [o / max(a, 1e-6) for o, a in zip(obs, attendu)]


def _points(recs: list[dict]) -> tuple[float, float, float | None, float | None]:
    """(points par match, différence de buts par match, xGD par match, xPts par match) sur la saison, tous lieux ; None si aucun xG."""
    n = len(recs)
    ppm = sum(3 if r["gf"] > r["ga"] else 1 if r["gf"] == r["ga"] else 0 for r in recs) / n
    gd = sum(r["gf"] - r["ga"] for r in recs) / n
    X = [r for r in recs if r["xgf"] is not None]
    if not X:
        return ppm, gd, None, None
    xgd = sum(r["xgf"] - r["xga"] for r in X) / len(X)
    for r in X:
        if "_xp" not in r:                                  # points attendus du match : 3 × P(victoire) + P(nul), d'après les xG des deux équipes
            g = OM.grilles(np.array([max(r["xgf"], .05)]), np.array([max(r["xga"], .05)]), 0.0)[0]
            r["_xp"] = float(3 * np.tril(g, -1).sum() + np.trace(g))
    return ppm, gd, xgd, float(np.mean([r["_xp"] for r in X]))


def composantes(m: dict, lig: Ligue, w: float, m_eq: float, m_lig: float) -> dict | None:
    """Tout ce que le modèle lit sur un match. None si moins de NMIN matchs au même lieu pour une équipe."""
    A = [r for r in m["md"] if r["dom"]]
    B = [r for r in m["me"] if not r["dom"]]
    if min(len(A), len(B)) < NMIN:
        return None
    N = lig.notes(m["jour"], w, m_eq, m_lig)
    mu_h, mu_e = N["mu_h"], N["mu_e"]
    a, d = N["a"], N["d"]
    spec = {"attA": (A, "f", mu_h, d), "defA": (A, "a", mu_e, a), "attB": (B, "f", mu_e, d), "defB": (B, "a", mu_h, a)}
    out = {"mu_h": mu_h, "mu_e": mu_e, "n_dom": len(A), "n_ext": len(B)}
    for nom, (recs, cote, mu, notes) in spec.items():
        obs = [_obs(r, cote, w) for r in recs]
        att = [mu * notes.get(r["adv"], 1.0) for r in recs]
        idx, z = _indice(obs, att, m_eq)
        k = z[-FENETRE_TENDANCE:]
        fen = float(np.mean(k))
        arith = k[-1] + (k[-1] - k[0]) / (len(k) - 1) if len(k) > 1 else k[-1]
        geo = k[-1] * (k[-1] / k[0]) ** (1 / (len(k) - 1)) if len(k) > 1 and min(k) > 0 else k[-1]
        out[nom] = {"idx": idx, "fen": fen, "arith": float(arith), "geo": float(geo), "se": float(np.std(z, ddof=1) / np.sqrt(len(z))) if len(z) > 1 else 0.0}
    if "_pts" not in m:
        m["_pts"] = (_points(m["md"]), _points(m["me"]))
    pa, pb = m["_pts"]
    out["ecarts"] = {"ppm": pa[0] - pb[0], "gd": pa[1] - pb[1], "xgd": None if pa[2] is None or pb[2] is None else pa[2] - pb[2],
                     "xpts": None if pa[3] is None or pb[3] is None else pa[3] - pb[3]}
    return out


# ------------------------------------------------------------------------------------------------ buts attendus
def _force(c: dict, nom: str, theta: float, tendance: str) -> tuple[float, float]:
    """(indice corrigé de la tendance, incertitude relative)."""
    s = c[nom]
    v = s["idx"] + theta * (s[tendance] - s["fen"])
    return max(v, 0.05), s["se"] / max(s["idx"], 1e-6)


def lambdas(c: dict, P: dict) -> tuple[float, float, float, float]:
    """(λA, λB, incertitude relative de λA, de λB)."""
    aA, sA = _force(c, "attA", P["theta"], P["tendance"]); dB, sdB = _force(c, "defB", P["theta"], P["tendance"])
    aB, sB = _force(c, "attB", P["theta"], P["tendance"]); dA, sdA = _force(c, "defA", P["theta"], P["tendance"])
    la, lb = c["mu_h"] * aA * dB, c["mu_e"] * aB * dA
    if P.get("beta") and P.get("ecart"):
        g = c["ecarts"].get(P["ecart"])
        if g is not None:
            la, lb = la * np.exp(P["beta"] * g / 2), lb * np.exp(-P["beta"] * g / 2)
    return float(la), float(lb), float(np.hypot(sA, sdB)), float(np.hypot(sB, sdA))


def probas(la, lb) -> np.ndarray:
    """Probabilité de chaque marché du catalogue pour chaque couple (λA, λB) : tableau (n, marchés)."""
    g = OM.grilles(np.maximum(la, .05), np.maximum(lb, .05), RHO)
    return np.einsum("nij,ijk->nk", g, TABLE.astype(float))


def scenarios(la, lb, sa, sb) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(normal, favorable, catastrophe) pour chaque marché : les quatre coins de la boîte d'incertitude, le pire et le meilleur par marché."""
    la, lb, sa, sb = (np.asarray(v, float) for v in (la, lb, sa, sb))
    normal = probas(la, lb)
    coins = [probas(la * np.exp(i * Z_SCENARIO * sa), lb * np.exp(j * Z_SCENARIO * sb)) for i in (-1, 1) for j in (-1, 1)]
    return normal, np.max(coins, axis=0), np.min(coins, axis=0)


# ------------------------------------------------------------------------------------------------ évaluation et choix des paramètres
def perte(la, lb, h, a) -> float:
    """Moins le log de la probabilité du score réel, moyenné sur les matchs (plus bas = meilleur)."""
    return -OM.log_vraisemblance(np.asarray(la), np.asarray(lb), np.asarray(h), np.asarray(a), RHO) / max(len(la), 1)


def _evalue(matchs, scores, lignes, w, m_eq, m_lig, P) -> float:
    la, lb, h, a = [], [], [], []
    for m in matchs:
        c = composantes(m, lignes[(m["competition"], m["saison"])], w, m_eq, m_lig)
        if c is None:
            continue
        x, y, *_ = lambdas(c, P)
        la.append(x); lb.append(y); h.append(scores[m["id"]][0]); a.append(scores[m["id"]][1])
    return perte(la, lb, h, a) if la else float("inf")


def ajuster(matchs: list[dict], scores: dict) -> dict:
    """Choisit chaque paramètre sur la première moitié des matchs joués (en jours), puis mesure le résultat sur la seconde.
    Rend les paramètres et le rapport d'ablation (perte de chaque variante sur la seconde moitié)."""
    ligues = {k: Ligue(v) for k, v in index_ligues(matchs).items()}
    joues = [m for m in matchs if m["id"] in scores]
    jours = sorted({m["jour"] for m in joues})
    coupe = jours[len(jours) // 2]
    A, B = [m for m in joues if m["jour"] < coupe], [m for m in joues if m["jour"] >= coupe]
    P = dict(PAR_DEFAUT)
    # étape 1 : observation (xG / buts), adversaires, référentiel
    meilleur = None
    for w in (0.0, 0.5, 1.0):
        for m_eq in (2.0, P["m_equipe"], 8.0, 16.0, 32.0):
            for m_lig in (0.0, 50.0, 500.0, 2342.0, 10000.0):
                p = _evalue(A, scores, ligues, w, m_eq, m_lig, P)
                if meilleur is None or p < meilleur[0]:
                    meilleur = (p, w, m_eq, m_lig)
    _, w, m_eq, m_lig = meilleur
    P.update({"w_xg": w, "m_equipe": m_eq, "m_ligue": m_lig})
    # étape 2 : tendance (0 = aucune)
    cand = [(0.0, "arith")] + [(t, k) for t in (0.1, 0.25, 0.5) for k in ("arith", "geo")]
    pertes = {c: _evalue(A, scores, ligues, w, m_eq, m_lig, {**P, "theta": c[0], "tendance": c[1]}) for c in cand}
    P["theta"], P["tendance"] = min(pertes, key=pertes.get)
    # étape 3 : situation compétitive (coefficient ajusté sur A, gardé seulement s'il améliore B)
    ec = {}
    for nom in ("ppm", "gd", "xgd", "xpts"):
        def f(beta, nom=nom):
            return _evalue(A, scores, ligues, w, m_eq, m_lig, {**P, "beta": beta, "ecart": nom})
        beta = float(minimize_scalar(f, bounds=(-1.0, 1.0), method="bounded", options={"xatol": 1e-3}).x)
        ec[nom] = {"beta": beta, "perte_A": f(beta)}
    base_A = _evalue(A, scores, ligues, w, m_eq, m_lig, {**P, "beta": 0.0})
    best = min(ec, key=lambda k: ec[k]["perte_A"])
    ref_B = _evalue(B, scores, ligues, w, m_eq, m_lig, {**P, "beta": 0.0})
    essai_B = _evalue(B, scores, ligues, w, m_eq, m_lig, {**P, "beta": ec[best]["beta"], "ecart": best})
    garde = ec[best]["perte_A"] < base_A and essai_B < ref_B
    P["beta"], P["ecart"] = (ec[best]["beta"], best) if garde else (0.0, None)
    # ablation sur la seconde moitié : chaque couche retirée à tour de rôle
    pf = _evalue(B, scores, ligues, w, m_eq, m_lig, P)
    abl = {"complet": pf,
           "sans_xg": _evalue(B, scores, ligues, 0.0, m_eq, m_lig, P),
           "sans_tendance": _evalue(B, scores, ligues, w, m_eq, m_lig, {**P, "theta": 0.0}),
           "sans_classement": ref_B if P["ecart"] else pf,
           "sans_correction_adversaires": _sans_adversaires(B, scores, ligues, w, m_eq, m_lig, P)}
    return {"parametres": P, "coupe": coupe, "matchs_A": len(A), "matchs_B": len(B),
            "classement": {k: {"beta": round(v["beta"], 4), "perte_A": round(v["perte_A"], 5)} for k, v in ec.items()} | {"garde": bool(garde), "perte_B_sans": round(ref_B, 5), "perte_B_avec": round(essai_B, 5)},
            "ablation_seconde_moitie": {k: round(v, 5) for k, v in abl.items()}}


class _SansAdversaires(Ligue):
    """Même ligue, notes neutres : chaque adversaire vaut 1 (sert seulement à mesurer ce que la correction des adversaires apporte)."""
    def notes(self, jour, w, m_eq, m_lig):
        n = super().notes(jour, w, m_eq, m_lig)
        return {**n, "a": {}, "d": {}}


def _sans_adversaires(matchs, scores, lignes, w, m_eq, m_lig, P) -> float:
    neutres = {k: _SansAdversaires.__new__(_SansAdversaires) for k in lignes}
    for k, l in lignes.items():
        neutres[k].matchs, neutres[k]._cache = l.matchs, {}
    return _evalue(matchs, scores, neutres, w, m_eq, m_lig, P)
