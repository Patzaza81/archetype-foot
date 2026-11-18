"""Outils communs des expériences d'audit Mega Power (18/11/2026). Aucune cote. Rien ici ne modifie le moteur."""
from __future__ import annotations
import math, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import verif_pronostic as V
from megapower import donnees as D, modele as M
from moteur_omega import modele as OM

import os
W, MEQ, MLIG, BETA_GD = 1.0, float(os.environ.get('AUDIT_MEQ', 16.0)), float(os.environ.get('AUDIT_MLIG', 10000.0)), float(os.environ.get('AUDIT_BETA', 0.3282445675994957))      # megapower v2 par défaut ; surchargés pour le bloc de saisons
RHO = M.RHO
NB = len(V.NOMS)
# marchés supplémentaires (multibuts) lus sur la grille de scores
MULTI = {"multibuts_1-3": (1, 3), "multibuts_2-4": (2, 4), "multibuts_1-4": (1, 4)}
TAB = np.zeros((11, 11, NB + len(MULTI)))
TAB[:, :, :NB] = V.TABLE
for j, (a, b) in enumerate(MULTI.values()):
    for h in range(11):
        for x in range(11):
            TAB[h, x, NB + j] = float(a <= h + x <= b)
NOMS = list(V.NOMS) + list(MULTI)
IDX = {n: i for i, n in enumerate(NOMS)}
CLES = ["1", "N", "2", "1N", "N2", "12", "total_plus_0.5", "total_plus_1.5", "total_plus_2.5", "total_moins_2.5", "total_moins_3.5", "total_moins_4.5",
        "btts_oui", "btts_non", "dom_plus_0.5", "ext_plus_0.5", "multibuts_1-3", "multibuts_2-4", "multibuts_1-4",
        "1N&total_plus_1.5", "N2&total_plus_1.5", "1N&total_moins_3.5", "N2&total_moins_3.5"]


def probas(la, lb):
    g = OM.grilles(np.maximum(la, .05), np.maximum(lb, .05), RHO)
    return np.einsum("nij,ijk->nk", g, TAB)


def wilson(h, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = h / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - r, c + r)


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def logloss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def charger():
    matchs, sc = D.lire_flux(), D.scores()
    lig = {k: M.Ligue(v) for k, v in M.index_ligues(matchs).items()}
    return matchs, sc, lig


def features(m, lig):
    """Tout ce que le moteur peut lire sur un match (avant le coup d'envoi), pour les expériences. None si moins de 4 matchs au même lieu."""
    A = [r for r in m["md"] if r["dom"]]
    B = [r for r in m["me"] if not r["dom"]]
    if min(len(A), len(B)) < 4:
        return None
    N = lig[(m["competition"], m["saison"])].notes(m["jour"], W, MEQ, MLIG)
    mu_h, mu_e, a, d = N["mu_h"], N["mu_e"], N["a"], N["d"]
    spec = {"attA": (A, "f", mu_h, d), "defA": (A, "a", mu_e, a), "attB": (B, "f", mu_e, d), "defB": (B, "a", mu_h, a)}
    F = {"mu_h": mu_h, "mu_e": mu_e, "jour": m["jour"], "id": m["id"], "comp": m["competition"]}
    for nom, (recs, cote, mu, notes) in spec.items():
        obs = [M._obs(r, cote, W) for r in recs]
        att = [mu * notes.get(r["adv"], 1.0) for r in recs]
        idx, z = M._indice(obs, att, MEQ)
        F[nom] = {"idx": idx, "z": z, "raw": obs, "se": float(np.std(z, ddof=1) / np.sqrt(len(z)))}
    if "_pts" not in m:
        m["_pts"] = (M._points(m["md"]), M._points(m["me"]))
    pa, pb = m["_pts"]
    sp = lambda p: None if p[3] is None else p[0] - p[3]
    F["ecarts"] = {"ppm": pa[0] - pb[0], "gd": pa[1] - pb[1], "xgd": None if pa[2] is None or pb[2] is None else pa[2] - pb[2],
                   "xpts": None if pa[3] is None or pb[3] is None else pa[3] - pb[3],
                   "surperf": None if sp(pa) is None or sp(pb) is None else sp(pa) - sp(pb)}
    # moyenne simple (méthode historique) : moyenne de ce que marque l'attaque et de ce que concède la défense d'en face, buts seulement
    F["simple"] = ((np.mean([r["gf"] for r in A]) + np.mean([r["ga"] for r in B])) / 2, (np.mean([r["gf"] for r in B]) + np.mean([r["ga"] for r in A])) / 2)
    F["n"] = (len(A), len(B))
    return F


def projeter(seq, kind, decay=0.8):
    n = len(seq)
    if n < 2:
        return seq[-1]
    if kind == "arith":
        return seq[-1] + (seq[-1] - seq[0]) / (n - 1)
    if kind == "geo":
        return seq[-1] * (seq[-1] / seq[0]) ** (1 / (n - 1)) if min(seq) > 0 else seq[-1]
    if kind == "ols":
        b, a0 = np.polyfit(np.arange(n), seq, 1)
        return a0 + b * n
    if kind == "ewma":
        w = decay ** (n - 1 - np.arange(n))
        return float(np.average(seq, weights=w))
    if kind == "both":
        return (projeter(seq, "arith") + projeter(seq, "geo")) / 2
    raise ValueError(kind)


def ajuste(s, sp):
    """Indice de force corrigé de la tendance. sp = None (aucune) ou dict(type, theta, win, norm, decay)."""
    if sp is None or sp["theta"] == 0:
        return s["idx"]
    seq = (s["z"] if sp["norm"] else s["raw"])[-sp["win"]:]
    base = float(np.mean(seq))
    delta = projeter(seq, sp["type"], sp.get("decay", 0.8)) - base
    if sp["norm"]:
        return max(s["idx"] + sp["theta"] * delta, 0.05)
    return s["idx"] * max(1 + sp["theta"] * delta / max(base, 1e-6), 0.05)


def lambdas(F, sp=None, beta=BETA_GD, ecart="gd"):
    la = F["mu_h"] * ajuste(F["attA"], sp) * ajuste(F["defB"], sp)
    lb = F["mu_e"] * ajuste(F["attB"], sp) * ajuste(F["defA"], sp)
    if beta and F["ecarts"].get(ecart) is not None:
        g = F["ecarts"][ecart]
        la, lb = la * math.exp(beta * g / 2), lb * math.exp(-beta * g / 2)
    return la, lb


def perte_scores(la, lb, h, a):
    return -OM.log_vraisemblance(np.asarray(la), np.asarray(lb), np.asarray(h), np.asarray(a), RHO) / max(len(la), 1)


def charger_bloc():
    """Bloc de saisons Football-Data (data/bloc_saisons) : 16 558 matchs, 38 divisions, buts seulement (pas de xG). Les cotes du bloc ne sont JAMAIS lues.
    Retourne (matchs, scores, ligues) dans le même format que charger()."""
    import gzip, json, collections
    d = json.load(gzip.open(ROOT / "data" / "bloc_saisons" / "bloc_2526_2627.json.gz"))["liste"]
    d = sorted(d, key=lambda r: (r["date"], r["id"]))
    hist = collections.defaultdict(list)
    matchs, sc = [], {}
    jours = collections.defaultdict(list)
    for r in d:
        jours[r["date"]].append(r)
    for jour in sorted(jours):
        for r in jours[jour]:
            kd, ke = (r["saison"], r["division"], r["domicile"]), (r["saison"], r["division"], r["exterieur"])
            matchs.append({"id": r["id"], "jour": jour, "competition": r["division"], "saison": r["saison"], "domicile": r["domicile"], "exterieur": r["exterieur"],
                           "cle_dom": r["domicile"], "cle_ext": r["exterieur"], "md": list(hist[kd]), "me": list(hist[ke])})
            sc[r["id"]] = (r["buts_dom"], r["buts_ext"])
        for r in jours[jour]:          # l'historique n'est complété qu'APRÈS tous les matchs du jour : aucune fuite
            hist[(r["saison"], r["division"], r["domicile"])].append({"date": jour, "dom": True, "adv": r["exterieur"], "gf": r["buts_dom"], "ga": r["buts_ext"], "xgf": None, "xga": None})
            hist[(r["saison"], r["division"], r["exterieur"])].append({"date": jour, "dom": False, "adv": r["domicile"], "gf": r["buts_ext"], "ga": r["buts_dom"], "xgf": None, "xga": None})
    lig = {k: M.Ligue(v) for k, v in M.index_ligues(matchs).items()}
    return matchs, sc, lig
