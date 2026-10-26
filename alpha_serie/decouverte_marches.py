"""Découverte des indices de chaque marché avec la logique de l'étude des victoires (26/10/2026). LECTURE SEULE : ne gèle rien, n'est appelée par aucun pipeline.

Logique reproduite (scripts d'origine : etudes/victoires_scripts_origine/, voir docs/DECOUVERTE_MARCHES.md) :
  1. Population = TOUS les matchs analysés par alpha (pas seulement les paris que le moteur propose). Pour un marché, on sépare les matchs GAGNANTS (l'événement
     a lieu) des PERDANTS (il n'a pas lieu), d'après les scores réels.
  2. Caractéristiques larges, calculées avant le match, qui ne se limitent pas au moteur : séries à domicile / à l'extérieur (victoires, nuls, défaites, cages inviolées,
     matchs sans marquer, plus de 1,5 / 2,5 / 3,5, les deux marquent, écarts de buts, points), niveaux et paires du moteur, et probabilités implicites des cotes 1X2 et plus/moins 2,5.
  3. Recherche de configurations de 1 à 3 conditions (« caractéristique >= seuil » ou « <= seuil »), seuils pris sur les quantiles de A.
  4. Chronologie : A = avant 2026-01-01, B = 2026-01-01..2026-03-31 (réglage) ; C = 2026-04-01..2026-09-27 (contrôle, jugé UNE seule fois) ;
     D = archive BetPawa 2026-09-28..2026-10-25 (jeu à part, jamais mélangé, seul à avoir les cotes BetPawa d'avant match).
  5. Choix : pour chaque niveau de réussite visé L, la configuration la plus fréquente dont le taux atteint L à la fois sur A ET sur B (effectifs minimaux), puis jugement sur C.
  6. Comparaison à la référence : taux des matchs qui NE présentent PAS la configuration, sur la même période.
  7. Cotes et rentabilité évaluées séparément (taux de réussite ≠ rentabilité).
Contrôle de biais de sélection : la procédure complète est rejouée sur des résultats mélangés (permutation dans chaque période) ; elle ne doit presque rien « confirmer ».

Commande : python -m alpha_serie.decouverte_marches --ecrire
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from . import coeur, parametres as P, robustesse as RB
from .etude_marches import baisse_significative, rendement, wilson
from .marches import libelle, test_du_marche

RACINE = Path(__file__).resolve().parent.parent
SORTIE_JSON = RACINE / "data" / "etudes" / "decouverte_marches_2026-10-26.json"
FIN_A, FIN_B, DEBUT_D = "2026-01-01", "2026-04-01", "2026-09-28"
COTE_MIN = P.COTE_MIN
N_MIN_PERIODE = 60            # effectif minimal d'une configuration sur A et sur B (comme s1x2b.py)
N_MIN_C = 100                 # effectif minimal sur C pour parler de confirmation
QUANTILES = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95)
NIVEAUX_VISES = tuple(round(0.30 + 0.05 * i, 2) for i in range(0, 14))        # 30 % .. 95 %
Z95 = 1.645


# --- caractéristiques --------------------------------------------------------------------------------------------------------------------------
def _serie(gf: list[int], ga: list[int], p: str) -> dict[str, float]:
    n = len(gf)
    tot = [a + b for a, b in zip(gf, ga)]
    m = sum(tot) / n
    f = lambda c: sum(1 for a, b, t in zip(gf, ga, tot) if c(a, b, t)) / n
    return {f"{p}_gf": sum(gf) / n, f"{p}_ga": sum(ga) / n, f"{p}_tot": m, f"{p}_vic": f(lambda a, b, t: a > b), f"{p}_nul": f(lambda a, b, t: a == b),
            f"{p}_def": f(lambda a, b, t: a < b), f"{p}_cs": f(lambda a, b, t: b == 0), f"{p}_fts": f(lambda a, b, t: a == 0), f"{p}_o15": f(lambda a, b, t: t >= 2),
            f"{p}_o25": f(lambda a, b, t: t >= 3), f"{p}_o35": f(lambda a, b, t: t >= 4), f"{p}_btts": f(lambda a, b, t: a >= 1 and b >= 1),
            f"{p}_gd": sum(a - b for a, b in zip(gf, ga)) / n, f"{p}_v2": f(lambda a, b, t: a - b >= 2), f"{p}_d2": f(lambda a, b, t: b - a >= 2),
            f"{p}_pts": sum(3 * (a > b) + (a == b) for a, b in zip(gf, ga)) / n, f"{p}_sd": math.sqrt(sum((x - m) ** 2 for x in tot) / n)}


def _devig(odds: list[float]) -> list[float]:
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]


def caracteristiques(hm: list[int], hc: list[int], am: list[int], ac: list[int], niv: dict[str, float], off: list, de: list,
                     o1x2: list[float] | None, ou25: list[float] | None) -> dict[str, float]:
    """Toutes calculables AVANT le match. NaN = information absente (la condition est alors fausse)."""
    f: dict[str, float] = {}
    f.update(_serie(hm, hc, "h"))                 # équipe qui reçoit, à domicile
    f.update(_serie(am, ac, "a"))                 # équipe qui se déplace, à l'extérieur
    f.update({"x_dom": niv["dom"], "x_ext": niv["ext"], "x_tot": niv["total"], "x_d": niv["d"], "x_mn": min(niv["dom"], niv["ext"]), "x_mx": max(niv["dom"], niv["ext"]), "x_absd": abs(niv["d"])})
    pairs = [((o[0] + d[0]) / 2, (o[1] + d[1]) / 2) for o, d in zip(off, de)]
    n = len(pairs) or 1
    f.update({"p_h": sum(g > e for g, e in pairs) / n, "p_e": sum(e > g for g, e in pairs) / n, "p_o15": sum(g + e > 1.5 for g, e in pairs) / n,
              "p_o25": sum(g + e > 2.5 for g, e in pairs) / n, "p_o35": sum(g + e > 3.5 for g, e in pairs) / n, "p_btts": sum(g > 0.5 and e > 0.5 for g, e in pairs) / n})
    f.update({"s_gd": f["h_gd"] - f["a_gd"], "s_gf": f["h_gf"] - f["a_gf"], "s_tot": (f["h_tot"] + f["a_tot"]) / 2, "s_o25": (f["h_o25"] + f["a_o25"]) / 2,
              "s_o15": (f["h_o15"] + f["a_o15"]) / 2, "s_btts": (f["h_btts"] + f["a_btts"]) / 2, "s_cs": (f["h_cs"] + f["a_cs"]) / 2, "s_fts": (f["h_fts"] + f["a_fts"]) / 2,
              "s_pts": f["h_pts"] - f["a_pts"], "s_nul": (f["h_nul"] + f["a_nul"]) / 2})
    nan = float("nan")
    if o1x2:
        ph, pn, pa = _devig(o1x2)
        f.update({"m_ph": ph, "m_pn": pn, "m_pa": pa, "m_p1n": ph + pn, "m_pn2": pn + pa, "m_p12": ph + pa})
    else:
        f.update({k: nan for k in ("m_ph", "m_pn", "m_pa", "m_p1n", "m_pn2", "m_p12")})
    f["m_pover25"] = _devig(ou25)[0] if ou25 else nan
    return f


# --- événements (marchés) ----------------------------------------------------------------------------------------------------------------------
def evenements() -> dict[str, dict[str, Any]]:
    """Un événement par table de vérité distincte (« handicap -0,5 domicile » = « victoire domicile » : un seul événement, cotes de tous les équivalents)."""
    out: dict[str, dict[str, Any]] = {}
    vus: dict[tuple, str] = {}

    def ajouter(cle: tuple[str, str], pred, nom: str):
        sig = tuple(bool(pred(h, a)) for h in range(10) for a in range(10))
        if sig in vus:
            out[vus[sig]]["cles"].append(cle)
            return
        eid = f"{cle[0]}|{cle[1]}"
        vus[sig] = eid
        out[eid] = {"nom": nom, "cles": [cle], "pred": pred}

    for _, items in coeur.CATALOGUE.items():
        for g, s in items:
            pred = test_du_marche(g, s)
            if pred is not None:
                ajouter((g, s), pred, libelle(g, s))
    for lo, hi in P.charger()["multigoals"]["plages"]:
        ajouter(("multigoals", f"{lo}-{hi}"), (lambda h, a, lo=lo, hi=hi: lo <= h + a <= hi), f"Multigoals {lo}-{hi}")
    return out


# --- données -----------------------------------------------------------------------------------------------------------------------------------
def construire(evts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Rejeu reproductible, matchs strictement antérieurs. Football-Data s'arrête avant l'archive (même match dans les deux sources)."""
    params = P.charger()
    rows, vus = [], set()
    audit = {"lus": {"FD": 0, "ARCH": 0}, "ecartes_doublon_de_source": 0, "ids_en_double": 0, "matchs_en_double_meme_source": 0, "resultats_manquants": 0, "analyses": {"FD": 0, "ARCH": 0}}
    for src, charger in (("FD", RB.charger_bloc), ("ARCH", RB.charger_archive_archetype)):
        for m in charger():
            audit["lus"][src] += 1
            if src == "FD" and m["jour"] >= DEBUT_D:
                audit["ecartes_doublon_de_source"] += 1
                continue
            if not isinstance(m.get("h"), int) or not isinstance(m.get("a"), int):
                audit["resultats_manquants"] += 1
                continue
            if m["id"] in vus:
                audit["ids_en_double"] += 1
                continue
            vus.add(m["id"])
            try:
                r = coeur.analyser_match(m["dom"], m["ext"], m["jour"], params)
            except Exception:
                continue
            if r.get("statut") != "analyse":
                continue
            noms = (str(m.get("domicile") or m["id"].split("|")[-2]).lower(), str(m.get("exterieur") or m["id"].split("|")[-1]).lower())
            if (src, m["jour"], noms) in vus:
                audit["matchs_en_double_meme_source"] += 1
                continue
            vus.add((src, m["jour"], noms))
            hm, hc = coeur.serie_lieu(m["dom"], True, m["jour"])
            am, ac = coeur.serie_lieu(m["ext"], False, m["jour"])
            o1x2 = ou25 = None
            cotes: dict[str, float] = {}
            if src == "FD":
                fd = m.get("cotes_fd") or {}
                x = (fd.get("1x2_cloture") or {}).get("moy")
                if isinstance(x, list) and len(x) == 3 and all(isinstance(v, (int, float)) and v > 1 for v in x):
                    o1x2 = x
                y = (fd.get("plus_moins_2_5_cloture") or {}).get("moy")
                if isinstance(y, list) and len(y) == 2 and all(isinstance(v, (int, float)) and v > 1 for v in y):
                    ou25 = y
            else:
                c = m.get("cotes") or {}
                x = [(c.get("1x2") or {}).get(k) for k in ("1", "N", "2")]
                if all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1 for v in x):
                    o1x2 = x
                y = [(c.get("over_under_2.5") or {}).get(k) for k in ("plus", "moins")]
                if all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1 for v in y):
                    ou25 = y
                for eid, e in evts.items():
                    for cle in e["cles"]:
                        v = coeur.cote_de(c, cle)
                        if v:
                            cotes[eid] = float(v)
                            break
            audit["analyses"][src] += 1
            if src == "FD":                                   # cotes moyennes de CLÔTURE Football-Data : seulement 1X2 et plus/moins 2,5 (autre type de cote, jamais mélangé à BetPawa)
                for eid, e in evts.items():
                    for cle in e["cles"]:
                        if cle[0] == "1x2" and o1x2:
                            cotes[eid] = float(o1x2[("1", "N", "2").index(cle[1])])
                        elif cle == ("over_under_2.5", "plus") and ou25:
                            cotes[eid] = float(ou25[0])
                        elif cle == ("over_under_2.5", "moins") and ou25:
                            cotes[eid] = float(ou25[1])
            rows.append({"id": m["id"], "jour": m["jour"], "src": src, "h": m["h"], "a": m["a"], "cotes": cotes,
                         "f": caracteristiques(hm, hc, am, ac, r["niveaux"], r["scenarios_offensifs"], r["scenarios_defensifs"], o1x2, ou25)})
    rows.sort(key=lambda r: (r["jour"], r["id"]))
    noms = sorted(rows[0]["f"])
    X = np.array([[r["f"][k] for k in noms] for r in rows], dtype=np.float64)
    periode = np.array([3 if r["src"] == "ARCH" else (0 if r["jour"] < FIN_A else (1 if r["jour"] < FIN_B else 2)) for r in rows])
    return {"rows": rows, "noms": noms, "X": X, "periode": periode, "audit": audit,
            "H": np.array([r["h"] for r in rows]), "A_": np.array([r["a"] for r in rows])}


def gagnants(d: dict[str, Any], e: dict[str, Any]) -> np.ndarray:
    return np.array([bool(e["pred"](h, a)) for h, a in zip(d["H"], d["A_"])])


# --- recherche ---------------------------------------------------------------------------------------------------------------------------------
def atomes(X: np.ndarray, noms: list[str], periode: np.ndarray) -> tuple[list[tuple[str, str, float]], np.ndarray]:
    """Conditions « caractéristique >= t » / « <= t », t pris sur les quantiles de A seule (aucune information de B, C ou D)."""
    liste, cols = [], []
    for j, nom in enumerate(noms):
        v = X[:, j]
        base = v[(periode == 0) & ~np.isnan(v)]
        if len(base) < 100:
            continue
        for t in sorted({round(float(q), 4) for q in np.quantile(base, QUANTILES)}):
            for op in (">=", "<="):
                liste.append((nom, op, t))
                cols.append(np.where(np.isnan(v), False, (v >= t - 1e-9) if op == ">=" else (v <= t + 1e-9)))
    return liste, np.array(cols).T


def _compter(M: np.ndarray, y: np.ndarray, per: np.ndarray, p: int) -> tuple[np.ndarray, np.ndarray]:
    Mp = M[per == p].astype(np.float32)
    yp = y[per == p].astype(np.float32)
    return Mp.T @ Mp, Mp.T @ (Mp * yp[:, None])


def configurations(M: np.ndarray, y: np.ndarray, per: np.ndarray, n_pair_cache: dict) -> dict[str, Any]:
    """Toutes les configurations de 1 et 2 conditions + extension à 3 conditions des 40 meilleures paires ; effectifs et réussites sur A et B (réglage SEUL)."""
    na = M.shape[1]
    Ms = {p: M[per == p].astype(np.float32) for p in (0, 1)}
    ys = {p: y[per == p].astype(np.float32) for p in (0, 1)}
    for p in (0, 1):
        if p not in n_pair_cache:
            n_pair_cache[p] = Ms[p].T @ Ms[p]
    nA, nB = n_pair_cache[0], n_pair_cache[1]
    kA, kB = Ms[0].T @ (Ms[0] * ys[0][:, None]), Ms[1].T @ (Ms[1] * ys[1][:, None])
    iu = np.triu_indices(na)                      # i <= j ; i == j : condition seule
    ok = (nA[iu] >= N_MIN_PERIODE) & (nB[iu] >= N_MIN_PERIODE)
    I, J = iu[0][ok], iu[1][ok]
    conds = [((int(i),) if i == j else (int(i), int(j))) for i, j in zip(I, J)]
    arr = {"nA": nA[I, J].astype(np.int64), "kA": kA[I, J].astype(np.int64), "nB": nB[I, J].astype(np.int64), "kB": kB[I, J].astype(np.int64)}
    pair_idx = [t for t, c in enumerate(conds) if len(c) == 2 and arr["nA"][t] >= 100 and arr["nB"][t] >= 100]
    pair_idx.sort(key=lambda t: -min(arr["kA"][t] / arr["nA"][t], arr["kB"][t] / arr["nB"][t]))
    extra = {"nA": [], "kA": [], "nB": [], "kB": []}
    for t in pair_idx[:40]:
        i, j = conds[t]
        mA, mB = Ms[0][:, i] * Ms[0][:, j], Ms[1][:, i] * Ms[1][:, j]
        nA3, kA3, nB3, kB3 = mA @ Ms[0], (mA * ys[0]) @ Ms[0], mB @ Ms[1], (mB * ys[1]) @ Ms[1]
        for c in np.where((nA3 >= N_MIN_PERIODE) & (nB3 >= N_MIN_PERIODE))[0]:
            if int(c) in (i, j):
                continue
            conds.append(tuple(sorted((i, j, int(c)))))
            extra["nA"].append(int(nA3[c])); extra["kA"].append(int(kA3[c])); extra["nB"].append(int(nB3[c])); extra["kB"].append(int(kB3[c]))
    for k in arr:
        arr[k] = np.concatenate([arr[k], np.array(extra[k], dtype=np.int64)])
    arr["conds"] = conds
    return arr


def texte(atomes_: list, conds: tuple[int, ...]) -> str:
    return " ET ".join(f"{atomes_[c][0]} {atomes_[c][1]} {atomes_[c][2]:g}" for c in conds)


def masque(M: np.ndarray, conds: tuple[int, ...]) -> np.ndarray:
    m = M[:, conds[0]].copy()
    for c in conds[1:]:
        m &= M[:, c]
    return m


def stats_periode(sel: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    n, g = int(sel.sum()), int((sel & y).sum())
    lo, hi = wilson(g, n)
    return {"matchs": n, "gagnes": g, "perdus": n - g, "taux": round(g / n, 4) if n else None, "wilson_bas_95": round(lo, 4) if n else None, "wilson_haut_95": round(hi, 4) if n else None}


def juger(sel: np.ndarray, y: np.ndarray, per: np.ndarray, rows: list[dict], niveau: float, evt_id: str, joursC: int, joursD: int) -> dict[str, Any]:
    """Jugement UNE fois sur C (et à part sur D) : effectifs, réussite, Wilson, comparaison aux matchs sans la configuration, stabilité, cotes."""
    out: dict[str, Any] = {}
    for nom, p in (("A", 0), ("B", 1), ("C", 2), ("D", 3)):
        in_p = per == p
        s = stats_periode(sel & in_p, y)
        comp = stats_periode(~sel & in_p, y)
        s["reference_matchs_sans_la_configuration"] = comp
        s["reference_tous_les_matchs"] = stats_periode(in_p, y)
        jours = {"A": 307, "B": 90, "C": joursC, "D": joursD}[nom]
        s["par_jour"] = round(s["matchs"] / jours, 2)
        out[nom] = s
    # stabilité sur C : par mois
    mois: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for i in np.where(sel & (per == 2))[0]:
        k = rows[i]["jour"][:7]
        mois[k][1] += 1
        mois[k][0] += int(y[i])
    out["C"]["par_mois"] = {k: v for k, v in sorted(mois.items())}
    fd = [(bool(y[i]), rows[i]["cotes"][evt_id]) for i in np.where(sel & (per == 2))[0] if evt_id in rows[i]["cotes"]]
    if fd:
        out["C"]["rendement_cotes_moyennes_cloture_football_data"] = rendement(fd)
    # cotes BetPawa de D (séparées) : paris proposés par la configuration, jouables >= 1,25
    paris = [(bool(y[i]), rows[i]["cotes"][evt_id]) for i in np.where(sel & (per == 3))[0] if evt_id in rows[i]["cotes"]]
    ja = [x for x in paris if x[1] >= COTE_MIN]
    ref = [(bool(y[i]), rows[i]["cotes"][evt_id]) for i in np.where(~sel & (per == 3))[0] if evt_id in rows[i]["cotes"] and rows[i]["cotes"][evt_id] >= COTE_MIN]
    out["D"]["cotes_betpawa"] = {"avec_cote": len(paris), "jouables": len(ja), "part_jouable": round(len(ja) / len(paris), 3) if paris else None,
                                 "rendement_jouables": rendement(ja), "reference_jouables_sans_la_configuration": rendement(ref)}
    A, B, C = out["A"], out["B"], out["C"]
    gAB, nAB = A["gagnes"] + B["gagnes"], A["matchs"] + B["matchs"]
    cs = C["matchs"]
    lift = C["wilson_bas_95"] is not None and C["wilson_bas_95"] > (C["reference_matchs_sans_la_configuration"]["taux"] or 0)
    sous_niveau = cs > 0 and C["taux"] is not None and _z_sous(C["gagnes"], cs, niveau) > Z95
    baisse = baisse_significative(gAB, nAB, C["gagnes"], cs)
    if cs < N_MIN_C:
        statut = "prometteuse_a_confirmer" if (cs >= 30 and lift and not sous_niveau and not baisse) else "rejetee"
        raison = f"effectif insuffisant sur C ({cs} < {N_MIN_C})" if statut == "rejetee" else f"effectif trop faible pour conclure ({cs} < {N_MIN_C}), pas de signal contraire"
    elif not lift:
        statut, raison = "rejetee", "ne bat pas les matchs sans la configuration (borne basse de Wilson sur C)"
    elif sous_niveau:
        statut, raison = "rejetee", f"taux sur C significativement sous le niveau visé ({niveau:.0%})"
    elif baisse:
        statut, raison = "rejetee", "baisse significative de A+B à C"
    else:
        statut, raison = "confirmee_sur_C", "bat les matchs sans la configuration, tient son niveau, pas de baisse significative"
    out.update({"statut": statut, "raison": raison, "niveau_vise": niveau})
    return out


def masque_conditions(d: dict[str, Any], conditions: list[tuple[str, str, float]]) -> np.ndarray:
    m = np.ones(len(d["rows"]), dtype=bool)
    for nom, op, t in conditions:
        v = d["X"][:, d["noms"].index(nom)]
        m &= np.where(np.isnan(v), False, (v >= t - 1e-9) if op == ">=" else (v <= t + 1e-9))
    return m


# Candidats imposés (Patrick, 26/10/2026). Ils n'ont PAS été découverts par la procédure : traités par la même fonction de jugement, au niveau que leur propre réglage promet.
CANDIDATS_IMPOSES = {"over_under_3.5|moins": [("x_tot", "<=", 2.8)], "double_chance|12": [("x_absd", ">=", 0.6)]}


def niveau_promis(sel: np.ndarray, y: np.ndarray, per: np.ndarray) -> float:
    """Plus haut niveau de la grille (par pas de 5 %) atteint à la fois sur A et sur B par la règle."""
    a, b = stats_periode(sel & (per == 0), y)["taux"], stats_periode(sel & (per == 1), y)["taux"]
    m = min(a or 0, b or 0)
    return max([n for n in NIVEAUX_VISES if n <= m + 1e-9] or [NIVEAUX_VISES[0]])


def evaluer_imposes(d: dict[str, Any], evts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    joursC = (date.fromisoformat("2026-09-27") - date.fromisoformat(FIN_B)).days + 1
    out = {}
    for eid, conds in CANDIDATS_IMPOSES.items():
        y = gagnants(d, evts[eid])
        sel = masque_conditions(d, conds)
        niv = niveau_promis(sel, y, d["periode"])
        j = juger(sel, y, d["periode"], d["rows"], niv, eid, joursC, 28)
        j.update({"configuration": " ET ".join(f"{n} {o} {t:g}" for n, o, t in conds), "nom": evts[eid]["nom"],
                  "note": "règle imposée, non découverte par la procédure ; choisie après lecture de résultats d'une étude précédente : la période C n'est pas indépendante pour elle"})
        out[eid] = j
    return out


def _z_sous(g: int, n: int, p0: float) -> float:
    """z unilatéral : le taux observé est-il significativement SOUS p0 ? (positif = oui)."""
    if n == 0 or p0 <= 0 or p0 >= 1:
        return 0.0
    return (p0 - g / n) / math.sqrt(p0 * (1 - p0) / n)


def decouvrir(d: dict[str, Any], atomes_: list, M: np.ndarray, evt_id: str, e: dict[str, Any], y: np.ndarray, cache: dict, joursC: int, joursD: int) -> dict[str, Any]:
    per, rows = d["periode"], d["rows"]
    base = {nom: stats_periode(per == p, y) for nom, p in (("A", 0), ("B", 1), ("C", 2), ("D", 3))}
    cands = configurations(M, y, per, cache)
    rA, rB = cands["kA"] / cands["nA"], cands["kB"] / cands["nB"]
    baseAB = (base["A"]["gagnes"] + base["B"]["gagnes"]) / (base["A"]["matchs"] + base["B"]["matchs"])
    front, vus = [], set()
    for niv in sorted(NIVEAUX_VISES, reverse=True):       # du niveau le plus haut au plus bas : une règle est étiquetée au plus haut niveau qu'elle atteint
        if niv <= baseAB + 0.02:
            continue
        idx = np.where((rA >= niv) & (rB >= niv))[0]
        if len(idx) == 0:
            continue
        o = np.lexsort((-np.minimum(rA[idx], rB[idx]), -(cands["nA"][idx] + cands["nB"][idx])))
        best = cands["conds"][int(idx[o[0]])]
        if best in vus:
            continue
        vus.add(best)
        j = juger(masque(M, best), y, per, rows, niv, evt_id, joursC, joursD)
        j.update({"configuration": texte(atomes_, best), "conditions": [list(atomes_[c]) for c in best], "configurations_comparees": len(cands["conds"])})
        front.append(j)
    front.sort(key=lambda f: f["niveau_vise"])
    return {"nom": e["nom"], "cles_equivalentes": [list(c) for c in e["cles"]], "populations": base, "taux_de_base_AB": round(baseAB, 4), "configurations_comparees": len(cands["conds"]), "frontiere": front}


def signal_global(d: dict[str, Any], y: np.ndarray) -> dict[str, Any]:
    """Comme coh.py / gb.py : existe-t-il un signal exploitable ? Modèles appris sur A, jugés sur B puis C (log-loss contre le taux de base, précision des meilleurs %)."""
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import log_loss, roc_auc_score
    except Exception:
        return {"disponible": False}
    X, per = d["X"], d["periode"]
    Xc = np.where(np.isnan(X), np.nanmedian(X[per == 0], axis=0), X)
    out: dict[str, Any] = {"disponible": True}
    tr = per == 0
    if y[tr].sum() < 50 or (~y[tr]).sum() < 50:
        return {"disponible": True, "note": "effectifs insuffisants"}
    mu, sg = Xc[tr].mean(0), Xc[tr].std(0) + 1e-9
    base_p = y[tr].mean()
    for nom, mod, Z in (("logistique", LogisticRegression(max_iter=2000, C=0.1), (Xc - mu) / sg),
                        ("boosting", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=120, min_samples_leaf=80, random_state=0), Xc)):
        mod.fit(Z[tr], y[tr])
        res = {}
        for lab, p in (("B", 1), ("C", 2)):
            te = per == p
            pr = np.clip(mod.predict_proba(Z[te])[:, 1], 1e-6, 1 - 1e-6)
            yy = y[te]
            o = np.argsort(-pr)
            res[lab] = {"log_loss": round(float(log_loss(yy, pr)), 4), "log_loss_taux_de_base": round(float(log_loss(yy, np.full(len(yy), base_p))), 4), "auc": round(float(roc_auc_score(yy, pr)), 4),
                        "meilleurs": {f"{int(f * 100)}%": [int(f * len(yy)), round(float(yy[o[:int(f * len(yy))]].mean()), 4)] for f in (0.02, 0.05, 0.10, 0.20)}, "taux_de_base": round(float(yy.mean()), 4)}
        out[nom] = res
    return out


def differences_gagnants_perdants(d: dict[str, Any], y: np.ndarray, k: int = 6) -> list[dict[str, Any]]:
    """« Ce que les gagnants ont en commun » : écart standardisé gagnants − perdants sur A+B (réglage), puis le même sur C. On garde ceux qui gardent leur signe."""
    X, per, noms = d["X"], d["periode"], d["noms"]
    ab, c = (per == 0) | (per == 1), per == 2
    out = []
    for j, nom in enumerate(noms):
        v = X[:, j]
        def diff(mask):
            a, b = v[mask & y & ~np.isnan(v)], v[mask & ~y & ~np.isnan(v)]
            if len(a) < 30 or len(b) < 30:
                return None
            s = math.sqrt((a.var() + b.var()) / 2) or 1.0
            return float((a.mean() - b.mean()) / s)
        dab, dc = diff(ab), diff(c)
        if dab is not None and dc is not None:
            out.append({"caracteristique": nom, "ecart_standardise_AB": round(dab, 3), "ecart_standardise_C": round(dc, 3), "meme_signe": (dab > 0) == (dc > 0)})
    out.sort(key=lambda r: -abs(r["ecart_standardise_AB"]))
    return out[:k]


def etudier(d: dict[str, Any], evts: dict[str, dict[str, Any]], y_override: dict[str, np.ndarray] | None = None, signal: bool = True) -> dict[str, Any]:
    atomes_, M = atomes(d["X"], d["noms"], d["periode"])
    cache: dict = {}
    joursC = (date.fromisoformat("2026-09-27") - date.fromisoformat(FIN_B)).days + 1
    joursD = 28
    res = {}
    for eid, e in evts.items():
        y = (y_override or {}).get(eid)
        if y is None:
            y = gagnants(d, e)
        base = float(y[d["periode"] <= 1].mean())
        if base < 0.08 or base > 0.97:
            res[eid] = {"nom": e["nom"], "etudie": False, "raison": f"taux de base {base:.1%} : trop rare ou trop fréquent pour des configurations utiles"}
            continue
        r = decouvrir(d, atomes_, M, eid, e, y, cache, joursC, joursD)
        r["etudie"] = True
        r["gagnants_vs_perdants"] = differences_gagnants_perdants(d, y)
        if signal:
            r["signal_global"] = signal_global(d, y)
        res[eid] = r
    return res


def permuter(d: dict[str, Any], evts: dict[str, dict[str, Any]], graine: int) -> dict[str, np.ndarray]:
    """Résultats mélangés à l'intérieur de chaque période : la procédure ne doit presque rien confirmer."""
    rnd = random.Random(graine)
    out = {}
    for eid, e in evts.items():
        y = gagnants(d, e).copy()
        for p in range(4):
            idx = np.where(d["periode"] == p)[0]
            vals = list(y[idx])
            rnd.shuffle(vals)
            y[idx] = vals
        out[eid] = y
    return out


def compter(res: dict[str, Any]) -> dict[str, int]:
    c = {"confirmee_sur_C": 0, "prometteuse_a_confirmer": 0, "rejetee": 0, "configurations_jugees": 0}
    for r in res.values():
        for f in r.get("frontiere", []) if r.get("etudie") else []:
            if f.get("configuration"):
                c["configurations_jugees"] += 1
                c[f["statut"]] += 1
    return c


RAPPORT_MD = RACINE / "docs" / "DECOUVERTE_MARCHES_RESULTATS.md"
pc = lambda x: "-" if x is None else f"{x:.1%}"


def _ligne_periode(s: dict[str, Any]) -> str:
    return f"{s['gagnes']}/{s['matchs']} ({pc(s['taux'])}, W {pc(s['wilson_bas_95'])})" if s["matchs"] else "0"


def rapport(o: dict[str, Any]) -> str:
    sy, a = o["synthese"], o["audit_donnees"]
    nul = o["controle_permutation"]["resultats_melanges"]
    L = ["# Découverte des indices par marché — résultats (26/10/2026)", "",
         "Statut : ÉTUDE EN LECTURE SEULE. Aucun gel, aucune modification de production. Rien n'est « validé » : « confirmée sur C » veut dire qu'une configuration choisie sur A et B tient sur la période indépendante C ; seul un gel avant match peut valider.", "",
         "## Résumé",
         f"- {o['evenements_etudies']} événements (marchés distincts) étudiés ; {sy['configurations_jugees']} configurations jugées une fois sur C : **{sy['confirmee_sur_C']} confirmées**, {sy['prometteuse_a_confirmer']} prometteuses (effectif insuffisant), {sy['rejetee']} rejetées.",
         f"- **Contrôle de biais de sélection** : la même procédure sur résultats mélangés dans chaque période ({len(nul)} essais) confirme {', '.join(str(n['confirmee_sur_C']) for n in nul)} configuration(s) sur {', '.join(str(n['configurations_jugees']) for n in nul)} jugées. "
         "Une procédure sans biais devrait confirmer presque rien : ce chiffre est la part de fausses confirmations à attendre.",
         f"- Jeux : A {o['matchs']['A']} matchs, B {o['matchs']['B']}, C {o['matchs']['C']}, D (archive BetPawa) {o['matchs']['D']}. Football-Data s'arrête au 27/09 ({a['ecartes_doublon_de_source']} lignes écartées : même match que l'archive). "
         f"Doublons d'identifiant {a['ids_en_double']}, même match en double {a['matchs_en_double_meme_source']}, résultats manquants {a['resultats_manquants']}.", "",
         "## Vue d'ensemble : meilleure configuration confirmée par marché (niveau visé le plus haut)",
         "| Marché | Taux de base A+B | Niveau visé | Configuration | A | B | C | Matchs sans la configuration (C) | D (BetPawa) | Statut |", "|---|---|---|---|---|---|---|---|---|---|"]
    for eid, r in o["marches"].items():
        if not r.get("etudie"):
            continue
        conf = [f for f in r["frontiere"] if f["statut"] != "rejetee"]
        f = conf[-1] if conf else None
        if f is None:
            L.append(f"| {r['nom']} | {pc(r['taux_de_base_AB'])} | - | aucune configuration ne tient sur C | - | - | - | - | - | rejetée |")
        else:
            L.append(f"| {r['nom']} | {pc(r['taux_de_base_AB'])} | {f['niveau_vise']:.0%} | {f['configuration']} | {_ligne_periode(f['A'])} | {_ligne_periode(f['B'])} | {_ligne_periode(f['C'])} | "
                     f"{pc(f['C']['reference_matchs_sans_la_configuration']['taux'])} | {_ligne_periode(f['D'])} | {f['statut'].replace('_', ' ')} |")
    L += ["", "## Rentabilité, séparée du taux de réussite (configurations confirmées ou prometteuses)",
          "| Marché | Niveau | Cotes BetPawa (D) : paris jouables ≥ 1,25 | Taux | Gains / pertes | Rendement net (IC 95 %) | Cotes moyennes de clôture Football-Data (C) |", "|---|---|---|---|---|---|---|"]
    for eid, r in o["marches"].items():
        if not r.get("etudie"):
            continue
        for f in [x for x in r["frontiere"] if x["statut"] != "rejetee"][-2:]:
            cb = f["D"]["cotes_betpawa"]
            rj = cb["rendement_jouables"]
            fd = f["C"].get("rendement_cotes_moyennes_cloture_football_data")
            L.append(f"| {r['nom']} | {f['niveau_vise']:.0%} | {cb['jouables']} sur {cb['avec_cote']} (part jouable {pc(cb['part_jouable'])}) | "
                     f"{pc(rj['gagnes'] / rj['paris']) if rj.get('paris') else '-'} | {rj.get('gains', '-')} / {rj.get('pertes', '-')} | "
                     f"{('%+.1f%% [%+.1f%% ; %+.1f%%]' % (100 * rj['rendement'], 100 * rj['ic95'][0], 100 * rj['ic95'][1])) if rj.get('paris') else '-'} | "
                     f"{('%+.1f%% sur %d paris' % (100 * fd['rendement'], fd['paris'])) if fd else 'sans objet'} |")
    L += ["", "## Candidats imposés (traités par la même fonction de jugement, sans privilège)"]
    for eid, f in o["candidats_imposes"].items():
        cb = f["D"]["cotes_betpawa"]
        rj = cb["rendement_jouables"]
        L += [f"### {f['nom']} — {f['configuration']} (niveau promis par son réglage : {f['niveau_vise']:.0%}) → **{f['statut'].replace('_', ' ')}**",
              f"- A : {_ligne_periode(f['A'])} ; B : {_ligne_periode(f['B'])} ; C : {_ligne_periode(f['C'])} ; D : {_ligne_periode(f['D'])}",
              f"- Matchs sans la configuration : A {pc(f['A']['reference_matchs_sans_la_configuration']['taux'])}, B {pc(f['B']['reference_matchs_sans_la_configuration']['taux'])}, C {pc(f['C']['reference_matchs_sans_la_configuration']['taux'])}, D {pc(f['D']['reference_matchs_sans_la_configuration']['taux'])}",
              f"- Raison : {f['raison']}. {f['note']}.",
              f"- Cotes BetPawa (D), jouables ≥ 1,25 : {cb['jouables']} sur {cb['avec_cote']} ; rendement {('%+.1f%% [%+.1f%% ; %+.1f%%]' % (100 * rj['rendement'], 100 * rj['ic95'][0], 100 * rj['ic95'][1])) if rj.get('paris') else '-'}", ""]
    L += ["## Détail par marché"]
    for eid, r in o["marches"].items():
        if not r.get("etudie"):
            L += [f"### {r['nom']} — non étudié", f"- {r['raison']}", ""]
            continue
        po = r["populations"]
        L += [f"### {r['nom']}  (`{eid}`)",
              f"- Gagnants / perdants : A {po['A']['gagnes']}/{po['A']['perdus']}, B {po['B']['gagnes']}/{po['B']['perdus']}, C {po['C']['gagnes']}/{po['C']['perdus']}, D {po['D']['gagnes']}/{po['D']['perdus']} ; {r['configurations_comparees']:,} configurations comparées.".replace(",", " ")]
        sg = r.get("signal_global") or {}
        if sg.get("logistique"):
            lg, bo = sg["logistique"]["C"], sg["boosting"]["C"]
            L.append(f"- Signal global sur C (modèles appris sur A) : logistique AUC {lg['auc']}, log-loss {lg['log_loss']} contre {lg['log_loss_taux_de_base']} (taux de base) ; boosting AUC {bo['auc']}, meilleurs 5 % → {pc(bo['meilleurs']['5%'][1])} (taux de base {pc(bo['taux_de_base'])}).")
        L.append("- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : " +
                 "; ".join(f"{g['caracteristique']} {g['ecart_standardise_AB']:+.2f} ({'oui' if g['meme_signe'] else 'non'})" for g in r["gagnants_vs_perdants"][:5]))
        L += ["", "| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |", "|---|---|---|---|---|---|---|---|"]
        for f in r["frontiere"]:
            L.append(f"| {f['niveau_vise']:.0%} | {f['configuration']} | {_ligne_periode(f['A'])} | {_ligne_periode(f['B'])} | {_ligne_periode(f['C'])} | {pc(f['C']['reference_matchs_sans_la_configuration']['taux'])} | {_ligne_periode(f['D'])} | {f['statut'].replace('_', ' ')} |")
        L.append("")
    L += ["## Limites",
          "- Statuts rétrospectifs ; la seule validation est un gel prospectif avant match (non fait ici).",
          "- La mention « prometteuse » = signal sans effectif suffisant sur C : à reprendre quand il y aura plus de données.",
          "- Les probabilités implicites (1X2, plus/moins 2,5) viennent des cotes moyennes de clôture Football-Data sur A, B, C et des cotes BetPawa d'avant match sur D : même idée, deux marges différentes ; D est présenté à part.",
          "- Archive BetPawa : 28 jours ; effectifs de jouables souvent < 100, intervalles de rendement larges.",
          "- Plusieurs marchés ont des cotes sous 1,25 : un taux élevé n'y est pas jouable (jugé à part de la réussite).", "",
          "## Reproduction", "- `python -m alpha_serie.decouverte_marches --ecrire` (rejeu des données ≈ 15 s ; recherche + contrôle par permutation : plusieurs minutes).",
          "- `python -m pytest tests/test_decouverte_marches.py -q`."]
    return "\n".join(L) + "\n"


def ecrire(permutations: int = 3) -> dict[str, Any]:
    evts = evenements()
    d = construire(evts)
    res = etudier(d, evts)
    nul = []
    for g in range(permutations):
        nul.append(compter(etudier(d, evts, y_override=permuter(d, evts, 1000 + g), signal=False)))
    out = {"genere_le": "2026-10-26", "periodes": {"A": f"< {FIN_A}", "B": f"{FIN_A} -> {FIN_B}", "C": f"{FIN_B} -> veille de {DEBUT_D}", "D": "archive BetPawa 2026-09-28 -> 2026-10-25"},
           "matchs": {n: int((d["periode"] == p).sum()) for n, p in (("A", 0), ("B", 1), ("C", 2), ("D", 3))}, "audit_donnees": d["audit"], "caracteristiques": d["noms"],
           "evenements_etudies": sum(1 for r in res.values() if r.get("etudie")), "synthese": compter(res), "controle_permutation": {"resultats_melanges": nul, "nombre": permutations}, "candidats_imposes": evaluer_imposes(d, evts), "marches": res}
    SORTIE_JSON.parent.mkdir(parents=True, exist_ok=True)
    SORTIE_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    RAPPORT_MD.write_text(rapport(out), encoding="utf-8")
    return out


if __name__ == "__main__":
    if "--ecrire" in sys.argv:
        o = ecrire()
        print(json.dumps({k: o[k] for k in ("matchs", "audit_donnees", "evenements_etudies", "synthese", "controle_permutation")}, ensure_ascii=False, indent=1))
