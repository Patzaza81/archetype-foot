"""Découverte des indices — v2 : un PROTOCOLE PROPRE À CHAQUE MARCHÉ (26/10/2026). LECTURE SEULE : ne gèle rien, n'est appelée par aucun pipeline.

Socle commun = logique de l'étude des victoires (v1 : decouverte_marches.py). Ce qui devient propre à chaque marché, tiré de SES données (aucun seuil commun posé à la main) :
  - Effectifs minimaux : calcul de puissance entre le taux de base du marché p0 (A+B) et le niveau visé L (erreur 5 % unilatérale, puissance 80 %), avec la règle
    n·p ≥ 10 et n·(1−p) ≥ 10 qui rend les tests z valides. Un marché rare ou un petit écart exige plus de matchs ; un grand écart en exige moins.
    Le même calcul fixe l'effectif exigé en A, en B et en C (C planifié avec p0 de A+B : rien de C n'est lu avant le jugement).
  - Niveaux visés : 10 pas égaux entre le taux de base du marché et le plus haut taux qu'il atteint en A ET B avec l'effectif exigé (plus de grille commune 30–95 %).
  - Seuils (intervalles) : toutes les valeurs observées en A pour les variables discrètes, 1/40 de la distribution en A pour les continues ;
    on garde ceux dont l'effectif en A et en B atteint le plancher du marché (plus petit effectif exigé, quel que soit le niveau).
  - Caractéristiques propres au marché, en plus du socle : fréquence de L'ÉVÉNEMENT LUI-MÊME dans la série à domicile de l'équipe qui reçoit, dans la série
    à l'extérieur de l'équipe qui se déplace, leur moyenne, dans les scénarios appariés du moteur, et sa probabilité de Poisson tirée des niveaux du moteur.
    (Plus de 2,5 → fréquence des plus de 2,5 ; handicap −1,5 → fréquence des victoires par 2 buts ou plus ; multigoals 2-4 → fréquence des totaux 2 à 4…)
  - Combinaisons : 1 et 2 conditions exhaustives ; 3 conditions par faisceau MARCHÉ PAR NIVEAU (les paires les plus fréquentes qui atteignent le niveau
    inférieur avec l'effectif du niveau visé) ; sensibilité : faisceau triplé, on compte les choix qui changent. L'exhaustif à 3 conditions (≈ 10⁹–10¹⁰) est hors de portée.

Cotes, deux études SÉPARÉES :
  - S (principale, transposable à alpha qui analyse sans cote) : AUCUNE cote parmi les caractéristiques. Réglage A (2025) + B (janv.–mars 2026), contrôle C
    (avril–27/09/2026, jugé une fois), puis D = archive des cotes BetPawa FIGÉES pendant le run nocturne (28/09–25/10) pour la jouabilité et le rendement, à part.
  - F (cotes figées) : dans D seulement, cote BetPawa figée du marché (probabilité implicite) ajoutée aux caractéristiques. Réglage D1a (28/09–04/10) + D1b
    (05–11/10), contrôle D2 (12–25/10). Les cotes figées n'existent pas avant le 28/09 : petits effectifs. Les paramètres du moteur ont été réglés sur cette archive.
  - Les cotes moyennes de CLÔTURE Football-Data (v1) ne sont plus utilisées comme caractéristiques : ce n'est pas l'information disponible au run nocturne.

Commande : python -m alpha_serie.decouverte_marches_v2 --ecrire
"""
from __future__ import annotations

import json
import math
import random
import sys
import zlib
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from . import coeur, decouverte_marches as V1
from .etude_marches import baisse_significative, rendement
from .marches import test_du_marche

RACINE = V1.RACINE
SORTIE_JSON = RACINE / "data" / "etudes" / "decouverte_marches_v2_2026-10-26.json"
RAPPORT_MD = RACINE / "docs" / "DECOUVERTE_MARCHES_V2_RESULTATS.md"
Z_ALPHA, Z_PUISSANCE = 1.645, 0.8416      # conventions statistiques : erreur 5 % unilatérale, puissance 80 %
NORMALE = 10                              # n·p ≥ 10 et n·(1−p) ≥ 10 : validité des tests z
PAS_CONTINU = 40                          # variable continue : seuils aux 1/40 de sa distribution en A
FAISCEAU, FAISCEAU_CONTROLE = 60, 180     # paires prolongées à 3 conditions, par niveau ; contrôle de sensibilité
PAS_NIVEAUX = 10                          # niveaux visés : 10 pas égaux entre le taux de base du marché et le plus haut niveau démontrable
COTE_MIN = V1.COTE_MIN
COUPES_D = ("2026-10-05", "2026-10-12")   # étude F : D1a < 05/10 <= D1b < 12/10 <= D2
SPECIFIQUES = ("ev_dom", "ev_ext", "ev_series", "ev_scenarios", "ev_poisson")
ETUDES = {"S": {"labels": (("A", 0), ("B", 1), ("C", 2), ("D", 3)), "controle": "C", "cotes": 3, "jours": {"A": 365, "B": 90, "C": 180, "D": 28}},
          "F": {"labels": (("D1a", 0), ("D1b", 1), ("D2", 2)), "controle": "D2", "cotes": 2, "jours": {"D1a": 7, "D1b": 7, "D2": 14}}}


# --- protocole statistique propre au marché ------------------------------------------------------------------------------------------------------
def n_min(p0: float, p1: float) -> float:
    """Effectif pour montrer qu'un taux p1 dépasse p0 (5 % unilatéral, puissance 80 %), et assez grand pour que les tests z soient valides."""
    if not (0 < p0 < 1) or not (p0 < p1 < 1):
        return math.inf
    a = Z_ALPHA * math.sqrt(p0 * (1 - p0)) + Z_PUISSANCE * math.sqrt(p1 * (1 - p1))
    return max(math.ceil((a / (p1 - p0)) ** 2), math.ceil(NORMALE / min(p1, 1 - p1)), math.ceil(NORMALE / min(p0, 1 - p0)))


def n_min_vec(p0: float, p1: np.ndarray) -> np.ndarray:
    p1 = np.asarray(p1, dtype=np.float64)
    ok = (p1 > p0) & (p1 < 1) & (0 < p0 < 1)
    q = np.where(ok, p1, 0.5)
    a = Z_ALPHA * math.sqrt(p0 * (1 - p0)) + Z_PUISSANCE * np.sqrt(q * (1 - q))
    puis = np.ceil((a / np.where(ok, q - p0, 1.0)) ** 2)
    norm = np.ceil(NORMALE / np.minimum(q, 1 - q))
    out = np.maximum(np.maximum(puis, norm), math.ceil(NORMALE / min(p0, 1 - p0)) if 0 < p0 < 1 else math.inf)
    return np.where(ok, out, np.inf)


def echelle(p0: float, haut: float) -> list[float]:
    """Niveaux visés propres au marché : du taux de base (exclu) au plus haut taux qu'il atteint en réglage 1 ET 2 avec l'effectif exigé (inclus)."""
    return sorted({round(p0 + (haut - p0) * k / PAS_NIVEAUX, 3) for k in range(1, PAS_NIVEAUX + 1)})


def plancher(p0: float) -> int:
    """Plus petit effectif exigé pour ce marché, quel que soit le niveau visé : en dessous, aucune configuration ne peut rien démontrer."""
    v = n_min_vec(p0, np.linspace(p0, 1, 2001)[1:-1])
    return int(v.min()) if np.isfinite(v.min()) else 10 ** 9


# --- caractéristiques propres au marché ----------------------------------------------------------------------------------------------------------
def _table(pred) -> np.ndarray:
    return np.array([[bool(pred(h, a)) for a in range(16)] for h in range(16)])


def miroir(rows: list[dict], pred) -> np.ndarray:
    """Fréquence de l'événement lui-même AVANT le match : série à domicile de l'équipe qui reçoit (score domicile-extérieur = marqués-encaissés),
    série à l'extérieur de l'équipe qui se déplace (score = encaissés-marqués), moyenne des deux, scénarios appariés du moteur, Poisson sur les niveaux."""
    T = _table(pred)
    t = lambda h, a: bool(T[h, a]) if h < 16 and a < 16 else bool(pred(h, a))
    out = np.full((len(rows), 5), np.nan)
    ks = np.arange(11)
    fact = np.array([math.factorial(k) for k in ks], dtype=np.float64)
    ld = np.array([r["niv"][0] for r in rows], dtype=np.float64)
    le = np.array([r["niv"][1] for r in rows], dtype=np.float64)
    pd_ = np.exp(-ld)[:, None] * ld[:, None] ** ks / fact
    pe_ = np.exp(-le)[:, None] * le[:, None] ** ks / fact
    out[:, 4] = np.einsum("ni,ij,nj->n", pd_, T[:11, :11].astype(np.float64), pe_)
    for i, r in enumerate(rows):
        hm, hc, am, ac = r["serie"]
        dom = [t(x, y) for x, y in zip(hm, hc)]
        ext = [t(y, x) for x, y in zip(am, ac)]
        n = min(len(hm), len(am))
        sc = [t(hm[-n:][k], am[-n:][k]) for k in range(n)] + [t(ac[-n:][k], hc[-n:][k]) for k in range(n)]
        a = sum(dom) / len(dom) if dom else np.nan
        b = sum(ext) / len(ext) if ext else np.nan
        out[i, :4] = (a, b, (a + b) / 2, sum(sc) / len(sc) if sc else np.nan)
    return out


def _multiplicite(g: str) -> tuple[list[tuple[str, str]], int] | None:
    sels = [(gg, ss) for items in coeur.CATALOGUE.values() for gg, ss in items if gg == g]
    preds = [test_du_marche(gg, ss) for gg, ss in sels]
    if not sels or any(p is None for p in preds):
        return None
    k = {sum(bool(p(h, a)) for p in preds) for h in range(10) for a in range(10)}
    return (sels, k.pop()) if len(k) == 1 else None


def proba_implicite(rows: list[dict], e: dict) -> np.ndarray:
    """Probabilité implicite de la cote BetPawa FIGÉE du marché (marge retirée sur le groupe de sélections). Absente : NaN."""
    out = np.full(len(rows), np.nan)
    for g, s in e["cles"]:
        m = _multiplicite(g)
        if m is None:
            continue
        sels, k = m
        for i, r in enumerate(rows):
            if not np.isnan(out[i]):
                continue
            c = r.get("cotes_brutes") or {}
            od = [coeur.cote_de(c, x) for x in sels]
            if all(od):
                inv = [1 / o for o in od]
                out[i] = inv[sels.index((g, s))] / sum(inv) * k
    return out


# --- seuils et configurations --------------------------------------------------------------------------------------------------------------------
def seuils(vA: np.ndarray) -> np.ndarray:
    u = np.unique(vA)
    if len(u) <= PAS_CONTINU:
        return u
    return np.unique(np.round(np.quantile(vA, np.arange(1, PAS_CONTINU) / PAS_CONTINU), 4))


def atomes(X: np.ndarray, noms: list[str], per: np.ndarray, plancher_: int) -> tuple[list[tuple[str, str, float]], np.ndarray]:
    """Conditions « >= t » / « <= t » ; t pris sur la 1re période de réglage SEULE ; gardées si l'effectif atteint le plancher en réglage 1 et 2 (aucun résultat lu)."""
    liste, cols = [], []
    for j, nom in enumerate(noms):
        v = X[:, j]
        vA = v[(per == 0) & ~np.isnan(v)]
        if len(vA) < plancher_:
            continue
        nA_tot = int(((per == 0) & ~np.isnan(v)).sum())
        for t in seuils(vA):
            for op in (">=", "<="):
                c = np.where(np.isnan(v), False, (v >= t - 1e-9) if op == ">=" else (v <= t + 1e-9))
                n0, n1 = int((c & (per == 0)).sum()), int((c & (per == 1)).sum())
                if n0 >= plancher_ and n1 >= plancher_ and n0 < nA_tot:
                    liste.append((nom, op, round(float(t), 4)))
                    cols.append(c)
    return liste, (np.array(cols).T if cols else np.zeros((len(per), 0), dtype=bool))


def configurations(M: np.ndarray, y: np.ndarray, per: np.ndarray, p0: float, plancher_: int, faisceau: int) -> dict[str, Any]:
    """1 et 2 conditions exhaustives, 3 conditions par faisceau par niveau. Effectifs et réussites sur les deux périodes de réglage SEULES."""
    Ms = {p: M[per == p].astype(np.float32) for p in (0, 1)}
    ys = {p: y[per == p].astype(np.float32) for p in (0, 1)}
    N = {p: Ms[p].T @ Ms[p] for p in (0, 1)}
    K = {p: Ms[p].T @ (Ms[p] * ys[p][:, None]) for p in (0, 1)}
    na = M.shape[1]
    iu = np.triu_indices(na)
    nA, nB = N[0][iu], N[1][iu]
    ok = (nA >= plancher_) & (nB >= plancher_)
    I, J = iu[0][ok].astype(np.int32), iu[1][ok].astype(np.int32)
    del iu
    nA, nB = N[0][I, J].astype(np.int64), N[1][I, J].astype(np.int64)
    kA, kB = K[0][I, J].astype(np.int64), K[1][I, J].astype(np.int64)
    Kc = np.full(len(I), -1, dtype=np.int32)
    r = np.minimum(kA / nA, kB / nB)
    dem = (r > p0) & (nA >= n_min_vec(p0, r)) & (nB >= n_min_vec(p0, r))
    echelle0 = echelle(p0, float(r[dem].max())) if dem.any() else []
    # faisceau : par niveau, les paires les plus fréquentes qui atteignent le niveau inférieur et ont l'effectif exigé au niveau visé
    paires = set()
    for li, L in enumerate(echelle0):
        bas = echelle0[li - 1] if li else p0
        nm = n_min(p0, L)
        idx = np.where((I != J) & (r >= bas) & (nA >= nm) & (nB >= nm))[0]
        for t in idx[np.argsort(-(nA[idx] + nB[idx]), kind="stable")[:faisceau]]:
            paires.add((int(I[t]), int(J[t])))
    vus3, ext = set(), {"I": [], "J": [], "K": [], "nA": [], "nB": [], "kA": [], "kB": []}
    for i, j in sorted(paires):
        mA, mB = Ms[0][:, i] * Ms[0][:, j], Ms[1][:, i] * Ms[1][:, j]
        nA3, kA3, nB3, kB3 = mA @ Ms[0], (mA * ys[0]) @ Ms[0], mB @ Ms[1], (mB * ys[1]) @ Ms[1]
        for c in np.where((nA3 >= plancher_) & (nB3 >= plancher_))[0]:
            c = int(c)
            if c in (i, j):
                continue
            tri = tuple(sorted((i, j, c)))
            if tri in vus3:
                continue
            vus3.add(tri)
            for k_, v in zip(("I", "J", "K", "nA", "nB", "kA", "kB"), (*tri, int(nA3[c]), int(nB3[c]), int(kA3[c]), int(kB3[c]))):
                ext[k_].append(v)
    I = np.concatenate([I, np.array(ext["I"], dtype=np.int32)])
    J = np.concatenate([J, np.array(ext["J"], dtype=np.int32)])
    Kc = np.concatenate([Kc, np.array(ext["K"], dtype=np.int32)])
    nA = np.concatenate([nA, np.array(ext["nA"], dtype=np.int64)])
    nB = np.concatenate([nB, np.array(ext["nB"], dtype=np.int64)])
    kA = np.concatenate([kA, np.array(ext["kA"], dtype=np.int64)])
    kB = np.concatenate([kB, np.array(ext["kB"], dtype=np.int64)])
    return {"I": I, "J": J, "K": Kc, "nA": nA, "nB": nB, "kA": kA, "kB": kB, "paires_prolongees": len(paires), "triplets": len(vus3)}


def conds_de(c: dict, t: int) -> tuple[int, ...]:
    i, j, k = int(c["I"][t]), int(c["J"][t]), int(c["K"][t])
    return tuple(sorted({i, j} | ({k} if k >= 0 else set())))


# --- jugement ------------------------------------------------------------------------------------------------------------------------------------
def juger(sel: np.ndarray, y: np.ndarray, per: np.ndarray, rows: list[dict], L: float, p0: float, eid: str, etude: str = "S") -> dict[str, Any]:
    """Jugé UNE fois sur la période de contrôle, avec l'effectif exigé PROPRE au marché et au niveau (planifié avec p0 du réglage)."""
    cfg = ETUDES[etude]
    out: dict[str, Any] = {}
    for lab, p in cfg["labels"]:
        s = V1.stats_periode(sel & (per == p), y)
        s["reference_matchs_sans_la_configuration"] = V1.stats_periode(~sel & (per == p), y)
        s["par_jour"] = round(s["matchs"] / cfg["jours"][lab], 2)
        out[lab] = s
    labs = [l for l, _ in cfg["labels"]]
    a, b, C = out[labs[0]], out[labs[1]], out[cfg["controle"]]
    pc_ = dict(cfg["labels"])[cfg["controle"]]
    temps: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for i in np.where(sel & (per == pc_))[0]:
        d = date.fromisoformat(rows[i]["jour"])
        k = rows[i]["jour"][:7] if etude == "S" else f"{d.isocalendar()[0]}-S{d.isocalendar()[1]:02d}"
        temps[k][0] += int(y[i])
        temps[k][1] += 1
    C["par_mois" if etude == "S" else "par_semaine"] = dict(sorted(temps.items()))
    q = cfg["cotes"]
    paris = [(bool(y[i]), rows[i]["cotes"][eid]) for i in np.where(sel & (per == q))[0] if eid in rows[i]["cotes"]]
    ja = [x for x in paris if x[1] >= COTE_MIN]
    ref = [(bool(y[i]), rows[i]["cotes"][eid]) for i in np.where(~sel & (per == q))[0] if eid in rows[i]["cotes"] and rows[i]["cotes"][eid] >= COTE_MIN]
    out["cotes_figees_betpawa"] = {"periode": dict((p, l) for l, p in cfg["labels"])[q], "avec_cote": len(paris), "jouables": len(ja),
                                   "rendement_jouables": rendement(ja), "reference_jouables_sans_la_configuration": rendement(ref)}
    nC, gC = C["matchs"], C["gagnes"]
    exige = n_min(p0, L)
    ref_t = C["reference_matchs_sans_la_configuration"]["taux"] or 0
    lift = nC > 0 and C["wilson_bas_95"] > ref_t
    sous = nC > 0 and V1._z_sous(gC, nC, L) > Z_ALPHA
    baisse = baisse_significative(a["gagnes"] + b["gagnes"], a["matchs"] + b["matchs"], gC, nC)
    if nC >= exige:
        if not lift:
            statut, raison = "rejetee", f"ne bat pas les matchs sans la configuration sur {cfg['controle']} (borne basse de Wilson)"
        elif sous:
            statut, raison = "rejetee", f"taux sur {cfg['controle']} significativement sous le niveau visé ({L:.1%})"
        elif baisse:
            statut, raison = "rejetee", f"baisse significative du réglage à {cfg['controle']}"
        else:
            statut, raison = "confirmee", f"bat les matchs sans la configuration, tient son niveau, pas de baisse ; {nC} matchs ≥ {exige} exigés"
    else:
        if nC > 0 and (C["taux"] or 0) > ref_t and not sous and not baisse:
            statut, raison = "a_confirmer", f"pas de signal contraire, mais {nC} matchs < {exige} exigés pour ce marché à ce niveau"
        else:
            statut, raison = "rejetee", f"{nC} matchs < {exige} exigés et " + ("baisse significative" if baisse else "sous le niveau visé" if sous else "ne fait pas mieux que les matchs sans la configuration")
    out.update({"statut": statut, "raison": raison, "niveau_vise": round(L, 4), "effectif_exige_par_periode": exige})
    return out


def _masque(X: np.ndarray, noms: list[str], conditions: list) -> np.ndarray:
    m = np.ones(X.shape[0], dtype=bool)
    for nom, op, t in conditions:
        v = X[:, noms.index(nom)]
        m &= np.where(np.isnan(v), False, (v >= t - 1e-9) if op == ">=" else (v <= t + 1e-9))
    return m


def decouvrir(X: np.ndarray, noms: list[str], per: np.ndarray, rows: list[dict], y: np.ndarray, eid: str, etude: str, faisceau: int = FAISCEAU) -> dict[str, Any]:
    reg = (per == 0) | (per == 1)
    p0 = float(y[reg].mean()) if reg.any() else float("nan")
    pl = plancher(p0)
    proto: dict[str, Any] = {"taux_de_base_reglage": round(p0, 4), "plancher_effectif": pl}
    if not math.isfinite(pl) or pl >= 10 ** 9 or int(((per == 0) & y).sum()) == 0:
        return {"etudie": False, "protocole": proto, "raison": "taux de base nul ou plein sur le réglage"}
    at, M = atomes(X, noms, per, pl)
    proto.update({"conditions_elementaires": len(at), "caracteristiques_utilisees": sorted({a[0] for a in at})})
    if M.shape[1] == 0:
        return {"etudie": False, "protocole": proto, "raison": f"aucun seuil n'atteint l'effectif plancher du marché ({pl} matchs par période de réglage)"}
    c = configurations(M, y, per, p0, pl, faisceau)
    rA, rB = c["kA"] / c["nA"], c["kB"] / c["nB"]
    r = np.minimum(rA, rB)
    dem = (r > p0) & (c["nA"] >= n_min_vec(p0, r)) & (c["nB"] >= n_min_vec(p0, r))
    proto.update({"configurations_comparees": int(len(r)), "configurations_demontrables": int(dem.sum()), "paires_prolongees_a_3": c["paires_prolongees"], "triplets": c["triplets"]})
    if not dem.any():
        return {"etudie": True, "protocole": proto, "frontiere": [], "raison": "aucune configuration ne dépasse le taux de base avec l'effectif exigé, en réglage 1 ET 2"}
    niveaux = echelle(p0, float(r[dem].max()))
    proto["niveaux_vises"] = [{"niveau": L, "effectif_exige_par_periode": n_min(p0, L)} for L in niveaux]
    front, vus = [], set()
    for L in sorted(niveaux, reverse=True):
        nm = n_min(p0, L)
        idx = np.where((rA >= L - 1e-9) & (rB >= L - 1e-9) & (c["nA"] >= nm) & (c["nB"] >= nm))[0]
        if len(idx) == 0:
            continue
        o = np.lexsort((-r[idx], -(c["nA"][idx] + c["nB"][idx])))
        best = conds_de(c, int(idx[o[0]]))
        if best in vus:
            continue
        vus.add(best)
        conds = [at[k] for k in best]
        j = juger(_masque(X, noms, conds), y, per, rows, L, p0, eid, etude)
        j.update({"configuration": " ET ".join(f"{n} {op} {t:g}" for n, op, t in conds), "conditions": [list(x) for x in conds],
                  "nombre_de_conditions": len(conds), "specifique_au_marche": any(x[0] in SPECIFIQUES or x[0] == "ev_cote_figee" for x in conds)})
        front.append(j)
    front.sort(key=lambda f: f["niveau_vise"])
    return {"etudie": True, "protocole": proto, "frontiere": front}


# --- données ---------------------------------------------------------------------------------------------------------------------------------------
def donnees_S(d: dict, e: dict) -> tuple[np.ndarray, list[str]]:
    """Socle SANS cote + caractéristiques propres au marché."""
    keep = [k for k, n in enumerate(d["noms"]) if not n.startswith("m_")]
    X = np.hstack([d["X"][:, keep], miroir(d["rows"], e["pred"])])
    return X, [d["noms"][k] for k in keep] + list(SPECIFIQUES)


def periodes_F(d: dict) -> np.ndarray:
    jours = np.array([r["jour"] for r in d["rows"]])
    p = np.full(len(jours), -1)
    D = d["periode"] == 3
    p[D & (jours < COUPES_D[0])] = 0
    p[D & (jours >= COUPES_D[0]) & (jours < COUPES_D[1])] = 1
    p[D & (jours >= COUPES_D[1])] = 2
    return p


def donnees_F(d: dict, e: dict) -> tuple[np.ndarray, list[str]]:
    """Dans D : socle + probabilités implicites 1X2 / plus-moins 2,5 (cotes figées BetPawa) + propres au marché + cote figée du marché lui-même."""
    X = np.hstack([d["X"], miroir(d["rows"], e["pred"]), proba_implicite(d["rows"], e)[:, None]])
    return X, list(d["noms"]) + list(SPECIFIQUES) + ["ev_cote_figee"]


def seuil_exploitation(d: dict, eid: str) -> dict[str, Any]:
    """Ce qu'Alpha peut exploiter : cotes BetPawa figées du marché dans D, jouables ≥ 1,25 ; taux d'équilibre = 1 / cote médiane. Information, jamais un critère de découverte."""
    o = sorted(r["cotes"][eid] for r, p in zip(d["rows"], d["periode"]) if p == 3 and eid in r["cotes"])
    j = [x for x in o if x >= COTE_MIN]
    if not j:
        return {"avec_cote": len(o), "jouables": 0}
    med = j[len(j) // 2]
    return {"avec_cote": len(o), "jouables": len(j), "cote_mediane_jouable": med, "taux_equilibre": round(1 / med, 4)}


def gagnants(d: dict, e: dict) -> np.ndarray:
    return V1.gagnants(d, e)


def permuter(y: np.ndarray, per: np.ndarray, graine: int) -> np.ndarray:
    rnd = random.Random(graine)
    y = y.copy()
    for p in sorted(set(per.tolist())):
        idx = np.where(per == p)[0]
        v = list(y[idx])
        rnd.shuffle(v)
        y[idx] = v
    return y


def etudier(d: dict, evts: dict, etude: str = "S", graine: int | None = None, faisceau: int = FAISCEAU, signal: bool = True) -> dict[str, Any]:
    per_all = d["periode"] if etude == "S" else periodes_F(d)
    out = {}
    for eid, e in evts.items():
        X, noms = (donnees_S if etude == "S" else donnees_F)(d, e)
        y = gagnants(d, e)
        if etude == "F":
            m = per_all >= 0
            X, per, rows, y = X[m], per_all[m], [r for r, k in zip(d["rows"], m) if k], y[m]
        else:
            per, rows = per_all, d["rows"]
        if graine is not None:
            y = permuter(y, per, graine + zlib.crc32(eid.encode()) % 997)
        r = decouvrir(X, noms, per, rows, y, eid, etude, faisceau)
        r["nom"] = e["nom"]
        if etude == "S" and graine is None and r.get("etudie"):
            dd = {"X": X, "periode": per, "noms": noms}
            r["gagnants_vs_perdants"] = V1.differences_gagnants_perdants(dd, y, k=8)
            r["propres_au_marche_gagnants_vs_perdants"] = [g for g in V1.differences_gagnants_perdants(dd, y, k=len(noms)) if g["caracteristique"] in SPECIFIQUES]
            r["seuil_exploitation_cotes_figees"] = seuil_exploitation(d, eid)
            if signal:
                r["signal_global"] = V1.signal_global(dd, y)
        out[eid] = r
    return out


def compter(res: dict) -> dict[str, int]:
    c = {"confirmee": 0, "a_confirmer": 0, "rejetee": 0, "configurations_jugees": 0, "marches_avec_confirmee": 0}
    for r in res.values():
        fr = r.get("frontiere") or []
        for f in fr:
            c["configurations_jugees"] += 1
            c[f["statut"]] += 1
        c["marches_avec_confirmee"] += any(f["statut"] == "confirmee" for f in fr)
    return c


def sensibilite(a: dict, b: dict) -> dict[str, Any]:
    """Faisceau standard contre faisceau triplé : combien de choix (marché, niveau) changent ?"""
    n = same = 0
    chg = []
    for eid in a:
        fa = {f["niveau_vise"]: f["configuration"] for f in a[eid].get("frontiere") or []}
        fb = {f["niveau_vise"]: f["configuration"] for f in b[eid].get("frontiere") or []}
        for L in sorted(set(fa) | set(fb)):
            n += 1
            if fa.get(L) == fb.get(L):
                same += 1
            else:
                chg.append({"marche": eid, "niveau": L, "faisceau_standard": fa.get(L), "faisceau_triple": fb.get(L)})
    return {"choix_compares": n, "identiques": same, "changements": chg, "statuts_standard": compter(a), "statuts_faisceau_triple": compter(b)}


def candidats_imposes(d: dict, evts: dict) -> dict[str, Any]:
    out = {}
    for eid, conds in V1.CANDIDATS_IMPOSES.items():
        e = evts[eid]
        X, noms = donnees_S(d, e)
        y, per = gagnants(d, e), d["periode"]
        sel = _masque(X, noms, conds)
        p0 = float(y[per <= 1].mean())
        L = min(V1.stats_periode(sel & (per == 0), y)["taux"], V1.stats_periode(sel & (per == 1), y)["taux"])
        j = juger(sel, y, per, d["rows"], L, p0, eid, "S")
        j.update({"nom": e["nom"], "configuration": " ET ".join(f"{n} {o} {t:g}" for n, o, t in conds),
                  "note": "règle imposée, non découverte ; choisie après lecture d'une étude précédente : C n'est pas indépendante pour elle"})
        out[eid] = j
    return out


# --- rapport -----------------------------------------------------------------------------------------------------------------------------------
pc = lambda x: "-" if x is None else f"{x:.1%}"


def _p(s: dict) -> str:
    return f"{s['gagnes']}/{s['matchs']} ({pc(s['taux'])})" if s["matchs"] else "0"


def _rend(cb: dict) -> str:
    rj = cb["rendement_jouables"]
    return f"{cb['jouables']} jouables, {('%+.0f%% [%+.0f ; %+.0f]' % (100 * rj['rendement'], 100 * rj['ic95'][0], 100 * rj['ic95'][1])) if rj.get('paris') else '-'}"


def rapport(o: dict) -> str:
    S, F = o["etude_S"], o["etude_F"]
    L = ["# Découverte par marché v2 — protocole propre à chaque marché (26/10/2026)", "",
         "Statut : ÉTUDE EN LECTURE SEULE. Aucun gel, aucune modification de production, aucune fusion. « Confirmée » = choisie sur le réglage, tient sur la période de contrôle jugée une fois ; seule une validation prospective gelée peut valider.", "",
         "## Résumé",
         f"- Étude S (sans cote, transposable) : {o['synthese_S']['configurations_jugees']} configurations jugées sur C — **{o['synthese_S']['confirmee']} confirmées** "
         f"({o['synthese_S']['marches_avec_confirmee']} marchés sur {len(S)}), {o['synthese_S']['a_confirmer']} à confirmer, {o['synthese_S']['rejetee']} rejetées.",
         f"- Contrôle par résultats mélangés (même procédure, {len(o['permutation_S'])} essais) : " + ", ".join(f"{x['confirmee']} confirmée(s) sur {x['configurations_jugees']}" for x in o["permutation_S"]) + ".",
         f"- Sensibilité du faisceau à 3 conditions ({FAISCEAU} → {FAISCEAU_CONTROLE} paires par niveau) : {o['sensibilite_faisceau']['identiques']} choix identiques sur {o['sensibilite_faisceau']['choix_compares']}.",
         f"- Étude F (cotes BetPawa figées, dans D seulement) : {o['synthese_F']['configurations_jugees']} jugées sur D2 — {o['synthese_F']['confirmee']} confirmées, {o['synthese_F']['a_confirmer']} à confirmer ; "
         "résultats mélangés : " + ", ".join(str(x["confirmee"]) for x in o["permutation_F"]) + " confirmée(s).",
         f"- Jeux : A {o['matchs']['A']}, B {o['matchs']['B']}, C {o['matchs']['C']}, D {o['matchs']['D']} (D1a {o['matchs_F']['D1a']}, D1b {o['matchs_F']['D1b']}, D2 {o['matchs_F']['D2']}).", "",
         "## Protocole : ce qui est propre à chaque marché et pourquoi",
         "- **Effectif exigé** = calcul de puissance entre le taux de base du marché (réglage) et le niveau visé, erreur 5 %, puissance 80 %, et n·p ≥ 10, n·(1−p) ≥ 10. Même calcul en réglage 1, réglage 2 et contrôle.",
         "- **Niveaux visés** = 10 pas égaux entre le taux de base du marché et le plus haut taux qu'il atteint en réglage 1 ET 2 avec l'effectif exigé.",
         "- **Seuils** = toutes les valeurs observées (variables discrètes) ou 1/40 de la distribution (continues) en réglage 1, gardés si l'effectif atteint le plancher du marché.",
         "- **Caractéristiques propres** = fréquence de l'événement lui-même : série domicile de l'équipe qui reçoit (`ev_dom`), série extérieur de l'équipe qui se déplace (`ev_ext`), moyenne (`ev_series`), scénarios appariés du moteur (`ev_scenarios`), Poisson sur les niveaux du moteur (`ev_poisson`) ; en F, cote figée du marché (`ev_cote_figee`).",
         "- **Seuil d'exploitation** = 1 / cote BetPawa figée médiane jouable du marché (D) : information sur ce qu'Alpha peut exploiter, jamais un critère de découverte.", "",
         "| Marché | Taux de base | Plancher | Seuils testés | Configurations | Niveaux visés (effectif exigé par période) | Seuil d'exploitation (D) |", "|---|---|---|---|---|---|---|"]
    for eid, r in S.items():
        pr = r["protocole"]
        se = r.get("seuil_exploitation_cotes_figees") or {}
        niv = ", ".join(f"{x['niveau']:.1%} ({x['effectif_exige_par_periode']})" for x in pr.get("niveaux_vises", []))
        L.append(f"| {r['nom']} | {pc(pr['taux_de_base_reglage'])} | {pr['plancher_effectif']} | {pr.get('conditions_elementaires', '-')} | {pr.get('configurations_comparees', '-'):,} | {niv or '-'} | "
                 f"{(pc(se['taux_equilibre']) + ' (cote ' + format(se['cote_mediane_jouable'], 'g') + ', ' + str(se['jouables']) + ' jouables)') if se.get('jouables') else 'pas de cote jouable'} |".replace(",", " ").replace("  ", ", "))
    L += ["", "## Étude S — résultats par marché (sans cote ; jouabilité sur les cotes figées D, à part)"]
    for eid, r in S.items():
        L.append(f"### {r['nom']}  (`{eid}`)")
        if not r.get("etudie") or not r.get("frontiere"):
            L += [f"- {r.get('raison', 'aucune configuration')}", ""]
            continue
        sp = r.get("propres_au_marche_gagnants_vs_perdants") or []
        if sp:
            L.append("- Caractéristiques propres (écart gagnants − perdants, réglage → contrôle) : " + "; ".join(f"{g['caracteristique']} {g['ecart_standardise_AB']:+.2f} → {g['ecart_standardise_C']:+.2f}" for g in sp))
        sg = r.get("signal_global") or {}
        if sg.get("logistique"):
            L.append(f"- Signal global sans cote sur C : AUC logistique {sg['logistique']['C']['auc']}, boosting {sg['boosting']['C']['auc']}.")
        L += ["", "| Niveau | Configuration | A | B | C | Sans config. (C) | Exigé | D | Cotes figées D | Statut |", "|---|---|---|---|---|---|---|---|---|---|"]
        for f in r["frontiere"]:
            L.append(f"| {f['niveau_vise']:.1%} | {f['configuration']}{' ★' if f['specifique_au_marche'] else ''} | {_p(f['A'])} | {_p(f['B'])} | {_p(f['C'])} | "
                     f"{pc(f['C']['reference_matchs_sans_la_configuration']['taux'])} | {f['effectif_exige_par_periode']} | {_p(f['D'])} | {_rend(f['cotes_figees_betpawa'])} | {f['statut'].replace('_', ' ')} |")
        L.append("")
    L += ["★ = utilise au moins une caractéristique propre au marché.", "", "## Étude F — cotes BetPawa figées (D seulement : réglage D1a + D1b, contrôle D2)"]
    for eid, r in F.items():
        fr = [f for f in r.get("frontiere") or [] if f["statut"] != "rejetee"]
        if not r.get("etudie"):
            L.append(f"- {r['nom']} : non étudié — {r.get('raison')}")
        elif not fr:
            L.append(f"- {r['nom']} : rien ne tient sur D2 ({len(r.get('frontiere') or [])} jugées) — plancher {r['protocole']['plancher_effectif']}")
        else:
            for f in fr:
                L.append(f"- {r['nom']} : **{f['statut'].replace('_', ' ')}** {f['niveau_vise']:.1%} — {f['configuration']} — D1a {_p(f['D1a'])}, D1b {_p(f['D1b'])}, D2 {_p(f['D2'])} "
                         f"(sans config. {pc(f['D2']['reference_matchs_sans_la_configuration']['taux'])}, exigé {f['effectif_exige_par_periode']}) ; cotes figées D2 : {_rend(f['cotes_figees_betpawa'])}")
    L += ["", "## Candidats imposés (même jugement, sans privilège)"]
    for eid, f in o["candidats_imposes"].items():
        L.append(f"- {f['nom']} — {f['configuration']} : niveau promis {f['niveau_vise']:.1%}, C {_p(f['C'])} contre {pc(f['C']['reference_matchs_sans_la_configuration']['taux'])} sans, exigé {f['effectif_exige_par_periode']} → **{f['statut'].replace('_', ' ')}** ({f['raison']}) ; cotes figées D : {_rend(f['cotes_figees_betpawa'])}. {f['note']}.")
    L += ["", "## Limites",
          "- Cotes figées BetPawa : seulement du 28/09 au 25/10/2026. Toute découverte qui utilise la cote (étude F) repose sur 4 semaines ; les paramètres du moteur ont été réglés sur cette même archive.",
          "- 3 conditions : faisceau, pas exhaustif ; la sensibilité au faisceau est mesurée ci-dessus.",
          "- Erreur 5 %, puissance 80 %, n·p ≥ 10, pas de 1/40, 10 niveaux : conventions statistiques communes, écrites ici ; tout le reste vient des données du marché.",
          "- Rien n'est validé : seule une validation prospective gelée avant match peut le faire.", "",
          "## Reproduction", "- `python -m alpha_serie.decouverte_marches_v2 --ecrire` ; `python -m pytest tests/test_decouverte_marches_v2.py -q`."]
    return "\n".join(L) + "\n"


def ecrire(permutations: int = 3) -> dict[str, Any]:
    evts = V1.evenements()
    d = V1.construire(evts)
    S = etudier(d, evts, "S")
    S3 = etudier(d, evts, "S", faisceau=FAISCEAU_CONTROLE, signal=False)
    F = etudier(d, evts, "F")
    pS = [compter(etudier(d, evts, "S", graine=1000 + g, signal=False)) for g in range(permutations)]
    pF = [compter(etudier(d, evts, "F", graine=2000 + g, signal=False)) for g in range(permutations)]
    pf = periodes_F(d)
    out = {"genere_le": "2026-10-26", "matchs": {n: int((d["periode"] == p).sum()) for n, p in (("A", 0), ("B", 1), ("C", 2), ("D", 3))},
           "matchs_F": {n: int((pf == p).sum()) for n, p in (("D1a", 0), ("D1b", 1), ("D2", 2))}, "audit_donnees": d["audit"],
           "conventions": {"z_alpha": Z_ALPHA, "z_puissance": Z_PUISSANCE, "normale": NORMALE, "pas_continu": PAS_CONTINU, "faisceau": FAISCEAU, "pas_niveaux": PAS_NIVEAUX},
           "synthese_S": compter(S), "synthese_F": compter(F), "permutation_S": pS, "permutation_F": pF, "sensibilite_faisceau": sensibilite(S, S3),
           "candidats_imposes": candidats_imposes(d, evts), "etude_S": S, "etude_F": F}
    SORTIE_JSON.parent.mkdir(parents=True, exist_ok=True)
    SORTIE_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)), encoding="utf-8")
    RAPPORT_MD.write_text(rapport(out), encoding="utf-8")
    return out


if __name__ == "__main__":
    if "--ecrire" in sys.argv:
        o = ecrire()
        print(json.dumps({k: o[k] for k in ("synthese_S", "synthese_F", "permutation_S", "permutation_F")}, ensure_ascii=False))
        print("sensibilite", o["sensibilite_faisceau"]["identiques"], "/", o["sensibilite_faisceau"]["choix_compares"])
