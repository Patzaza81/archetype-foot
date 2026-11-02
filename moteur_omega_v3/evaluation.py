"""Évaluation statistique des marchés, deux routes de sélection et combinaisons (mission du 02/11/2026). `python -m moteur_omega_v3.evaluation`

Aucune cote n'intervient dans la qualité d'un marché : la cote de BetPawa ne sert qu'à AIGUILLER (≥ 1,35 : route « principal » ; < 1,35 : route « combinaisons »).
Ni Edge, ni EV, ni EDV, ni rentabilité théorique : rien de tout cela n'est calculé ici.

Trois notions, toujours séparées (jamais fusionnées sous le mot « pourcentage ») :
  A  pourcentage ESTIMÉ par le moteur : f (fréquence des 25 couples de buts, c'est-à-dire la loi des scores du match) et g (la plus basse f en retirant une observation).
     Une fréquence brute n'est PAS une probabilité calibrée ; A n'est donné que comme estimation du moteur.
  B  fréquence HISTORIQUE observée : réussites ÷ matchs valides (remboursés exclus) de l'archive, globale et par période chronologique.
  C  réussite en VALIDATION CHRONOLOGIQUE : règle apprise sur les 70 % de matchs les plus anciens, appliquée telle quelle aux 30 % suivants.

Les règles dont le niveau n'est pas tranché (cible de réussite d'un marché principal, lecture du filtre à 81 %) sont des PARAMÈTRES passés en argument : le rapport donne
les chiffres de chaque lecture, aucune n'est gravée dans la production.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as K, coeur as C, definitions as Df, marches as M
from .audit import wilson

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "omega_v3_evaluation.json"
SORTIE_CSV = ROOT / "docs" / "omega_v3_marches_A_B_C.csv"
COTE_MIN_PRINCIPAL = 1.35          # Patrick, 02/11/2026 : cote individuelle minimale d'un marché principal
SEUIL_FILTRE_BAS = 0.81            # Patrick, 02/11/2026 : filtre des marchés à cote basse (lecture à trancher : voir `route_combinaison`)
NB_PERIODES = 3
MIN_OBS = K.MIN_PARIS              # 30, protocole de Patrick du 30/10/2026 (repris, pas inventé)
LECTURES = ("estimation", "historique", "les_deux")


# ---------------------------------------------------------------------------------------------------------------------------------
# Matrices de travail
# ---------------------------------------------------------------------------------------------------------------------------------
def matrices(ech: list[dict[str, Any]]) -> dict[str, Any]:
    """Séries triées par date : g, f, résultats, cotes (NaN = aucune cote BetPawa avant le coup d'envoi), jours, coupe chronologique 70/30."""
    ech = sorted(ech, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    jours = np.array([x["m"]["jour"] for x in ech])
    coupe = jours[int(len(ech) * K.PART_DEV)]
    cotes = np.array([[C.lire_cote(x["m"].get("cotes"), c) or np.nan for c in M.CLES] for x in ech])
    Y = np.array([x["y"] for x in ech])
    return {"ech": ech, "jours": jours, "coupe": str(coupe), "dev": jours < coupe, "res": jours >= coupe, "G": np.array([x["g"] for x in ech]), "F": np.array([x["f"] for x in ech]),
            "Y": Y, "V": Y != 2, "S": Y == 1, "cotes": cotes}


def _periodes(n: int, k: int = NB_PERIODES) -> list[np.ndarray]:
    """k périodes chronologiques d'effectif égal (indices des matchs triés par date)."""
    b = np.linspace(0, n, k + 1).astype(int)
    return [np.arange(b[i], b[i + 1]) for i in range(k)]


# ---------------------------------------------------------------------------------------------------------------------------------
# 1. Tableau marché par marché (A, B, C)
# ---------------------------------------------------------------------------------------------------------------------------------
def niveau_atteignable(g: np.ndarray, y: np.ndarray) -> dict[str, Any] | None:
    """Réussite la plus haute que le marché ait RÉELLEMENT tenue : sur les observations jouables, tranches de g de 5 points lissées (même PAV que le calibrage),
    on garde la meilleure tranche lissée portée par au moins MIN_OBS observations cumulées au-dessus d'elle. Propre à chaque marché, sans cible commune."""
    if len(g) < MIN_OBS:
        return None
    pas = K.PAS
    bornes = [round(0.5 + pas * k, 2) for k in range(int(round(0.5 / pas)))]
    tr = []
    for b in bornes:
        m = (g >= b - 1e-12) & ((g < b + pas - 1e-12) if b < bornes[-1] else (g <= 1.0 + 1e-12))
        if m.any():
            tr.append((b, int(m.sum()), float(y[m].sum())))
    if not tr:
        return None
    lisse = K._pav([n for _, n, _ in tr], [k for _, _, k in tr])
    best = None
    for (b, _, _), r in zip(tr, lisse):
        m = g >= b - 1e-12
        if m.sum() >= MIN_OBS and (best is None or r > best["reussite_lissee"]):
            best = {"seuil_g": b, "reussite_lissee": round(float(r), 4), "n": int(m.sum()), "reussite_brute": round(float(y[m].mean()), 4)}
    return best


def tableau_marches(mx: dict[str, Any], cible: float = K.REUSSITE_CIBLE) -> list[dict[str, Any]]:
    """Une ligne par marché généré (383) : identité, A, B (global et par période), C, stabilité, écart A−B, qualité des données, cote, seuil applicable, décision et raison."""
    G, F, V, S, cotes, dev, res, ech = mx["G"], mx["F"], mx["V"], mx["S"], mx["cotes"], mx["dev"], mx["res"], mx["ech"]
    n = len(ech)
    per = _periodes(n)
    initiales = {M.cle_txt(M.CLES[i]) for i in _cles_initiales()}
    rows = []
    for i, c in enumerate(M.CLES):
        txt = M.cle_txt(c)
        defin, formule, _ = Df.definition(c[0], c[1])
        v, s = V[:, i], S[:, i]
        nv, ns = int(v.sum()), int((s & v).sum())
        B = ns / nv if nv else None
        pp = []
        for p in per:
            vv = v[p]
            pp.append({"du": str(mx["jours"][p[0]]), "au": str(mx["jours"][p[-1]]), "n": int(vv.sum()), "succes": int((s[p] & vv).sum()),
                       "frequence": round(float((s[p] & vv).sum() / vv.sum()), 4) if vv.sum() else None})
        # stabilité : chaque période reste dans le bruit binomial (2 écarts-types) de la fréquence globale ; indéfinie sous MIN_OBS observations par période
        stable = None
        if B is not None and all(q["n"] >= MIN_OBS for q in pp):
            stable = all(abs(q["frequence"] - B) <= 2 * math.sqrt(max(B * (1 - B), 1e-9) / q["n"]) + 1e-12 for q in pp)
        cote = cotes[:, i]
        avec = ~np.isnan(cote)
        jouable = avec & (cote >= COTE_MIN_PRINCIPAL)
        bas = avec & (cote < COTE_MIN_PRINCIPAL)
        # niveau atteignable sur la population où le pari principal est possible (cote ≥ 1,35), développement seul, puis vérifié sur la réserve
        m_dev = dev & jouable & v
        niv = niveau_atteignable(G[m_dev, i], s[m_dev].astype(float))
        c_res = None
        if niv:
            m_res = res & jouable & v & (G[:, i] >= niv["seuil_g"] - 1e-12)
            c_res = {"n": int(m_res.sum()), "succes": int(s[m_res].sum()), "reussite": round(float(s[m_res].mean()), 4) if m_res.any() else None,
                     "wilson_95": wilson(int(s[m_res].sum()), int(m_res.sum()))}
        seuil_cible = _seuil_cible(G[m_dev, i], s[m_dev].astype(float), cible)
        rows.append({
            "id": txt, "initial_174": txt in initiales, "famille": M.famille(c), "libelle": M.libelle(c), "definition": defin, "formule": formule,
            "A_estime": {"f_moyen": round(float(F[v, i].mean()), 4) if nv else None, "g_moyen": round(float(G[v, i].mean()), 4) if nv else None},
            "B_historique": {"n_valides": nv, "succes": ns, "echecs": nv - ns, "rembourses": int((~v).sum()), "frequence": round(B, 4) if B is not None else None,
                             "wilson_95": wilson(ns, nv), "par_periode": pp},
            "ecart_A_moins_B": round(float(F[v, i].mean()) - B, 4) if nv else None,
            "stable": stable,
            "qualite": {"matchs_avec_cote": int(avec.sum()), "part_avec_cote": round(float(avec.mean()), 4), "cote_ge_1_35": int(jouable.sum()), "cote_lt_1_35": int(bas.sum()),
                        "cote_mediane": round(float(np.median(cote[avec])), 3) if avec.any() else None,
                        "derniere_collecte_jour": str(mx["jours"][np.where(avec)[0][-1]]) if avec.any() else None},
            "niveau_atteignable_dev_cote_ge_1_35": niv, "C_validation_reserve": c_res, "seuil_pour_cible": {"cible": cible, "seuil_g": seuil_cible},
        })
    return rows


def _seuil_cible(g: np.ndarray, y: np.ndarray, cible: float) -> float | None:
    """Même règle que le calibrage de production : première tranche de g (pas de 5 points dès 50 %) dont la réussite lissée atteint `cible`, avec au moins MIN_OBS observations au-dessus."""
    pas = K.PAS
    bornes = [round(0.5 + pas * k, 2) for k in range(int(round(0.5 / pas)))]
    tr = []
    for b in bornes:
        m = (g >= b - 1e-12) & ((g < b + pas - 1e-12) if b < bornes[-1] else (g <= 1.0 + 1e-12))
        if m.any():
            tr.append((b, int(m.sum()), float(y[m].sum())))
    if not tr:
        return None
    lisse = K._pav([n for _, n, _ in tr], [k for _, _, k in tr])
    for (b, _, _), r in zip(tr, lisse):
        if r >= cible and (g >= b - 1e-12).sum() >= MIN_OBS:
            return b
    return None


def _cles_initiales() -> list[int]:
    from .audit import cles_initiales
    return cles_initiales()


# ---------------------------------------------------------------------------------------------------------------------------------
# 2. Route principale (cote ≥ 1,35) : seuil propre à chaque marché
# ---------------------------------------------------------------------------------------------------------------------------------
def seuils_principaux(mx: dict[str, Any], cible: float, masque: np.ndarray, cote_min: float = COTE_MIN_PRINCIPAL) -> np.ndarray:
    """Seuil de g de chaque marché (NaN = aucun) appris sur `masque` (matchs), uniquement sur les observations où le pari est possible (cote ≥ cote_min)."""
    out = np.full(len(M.CLES), np.nan)
    for i in range(len(M.CLES)):
        m = masque & mx["V"][:, i] & (mx["cotes"][:, i] >= cote_min)
        t = _seuil_cible(mx["G"][m, i], mx["S"][m, i].astype(float), cible)
        if t is not None:
            out[i] = t
    return out


def evaluer_principal(mx: dict[str, Any], cible: float, cote_min: float = COTE_MIN_PRINCIPAL) -> dict[str, Any]:
    """Seuils appris sur le développement, appliqués aux matchs de la réserve avec les vraies cotes (≥ cote_min) : C = réussite observée."""
    th = seuils_principaux(mx, cible, mx["dev"], cote_min)
    adm = (mx["G"] >= np.where(np.isnan(th), 9, th)[None, :] - 1e-12) & (mx["cotes"] >= cote_min) & mx["V"] & mx["res"][:, None]
    n, k = int(adm.sum()), int((adm & mx["S"]).sum())
    ann = float(mx["G"][adm].mean()) if n else None
    return {"cible": cible, "cote_min": cote_min, "marches_avec_seuil": int((~np.isnan(th)).sum()), "paris": n, "matchs_avec_pari": int(adm.any(1).sum()), "matchs_reserve": int(mx["res"].sum()),
            "reussite_C": round(k / n, 4) if n else None, "wilson_95": wilson(k, n), "g_moyen_annonce": round(ann, 4) if ann is not None else None,
            "ecart_g_moins_reussite": round(ann - k / n, 4) if n else None}


# ---------------------------------------------------------------------------------------------------------------------------------
# 3. Route « combinaisons » (cote < 1,35, ou jamais cotée seule) : trois lectures du filtre à 81 %
# ---------------------------------------------------------------------------------------------------------------------------------
def route_combinaison(mx: dict[str, Any], lecture: str, seuil: float = SEUIL_FILTRE_BAS, min_obs: int = MIN_OBS, masque_hist: np.ndarray | None = None) -> np.ndarray:
    """Matrice booléenne (match × marché) des marchés ADMIS comme candidats de combinaison, pour une lecture du seuil :
      « estimation »  : g du match ≥ seuil ;
      « historique »  : fréquence historique B du marché (sur `masque_hist`, jamais sur les matchs évalués) ≥ seuil avec au moins `min_obs` matchs valides ;
      « les_deux »    : les deux. L'historique évite qu'un petit échantillon suffise : il faut `min_obs` matchs valides ET B ≥ seuil."""
    if lecture not in LECTURES:
        raise ValueError(f"lecture inconnue : {lecture}")
    G, V, S = mx["G"], mx["V"], mx["S"]
    mh = masque_hist if masque_hist is not None else mx["dev"]
    nv = (V & mh[:, None]).sum(0)
    ns = (S & V & mh[:, None]).sum(0)
    B = np.where(nv > 0, ns / np.maximum(nv, 1), np.nan)
    h_ok = (nv >= min_obs) & (B >= seuil)
    e_ok = G >= seuil - 1e-12
    if lecture == "estimation":
        return e_ok & (nv >= min_obs)[None, :] if min_obs else e_ok
    if lecture == "historique":
        return np.broadcast_to(h_ok[None, :], G.shape).copy()
    return e_ok & h_ok[None, :]


def evaluer_route_combinaison(mx: dict[str, Any], lecture: str, seuil: float = SEUIL_FILTRE_BAS) -> dict[str, Any]:
    adm = route_combinaison(mx, lecture, seuil)
    m = adm & (mx["cotes"] < COTE_MIN_PRINCIPAL) & mx["V"] & mx["res"][:, None]
    n, k = int(m.sum()), int((m & mx["S"]).sum())
    ann = float(mx["G"][m].mean()) if n else None
    return {"lecture": lecture, "seuil": seuil, "observations_reserve": n, "marches": len(set(np.where(m)[1])), "reussite": round(k / n, 4) if n else None, "wilson_95": wilson(k, n),
            "g_moyen_annonce": round(ann, 4) if ann is not None else None, "ecart_g_moins_reussite": round(ann - k / n, 4) if n else None}


# ---------------------------------------------------------------------------------------------------------------------------------
# 4. Combinaisons : événement joint
# ---------------------------------------------------------------------------------------------------------------------------------
GROUPES_FLUX = ("1x2_btts", "dc_btts", "1x2_total", "dc_total")      # combinés que BetPawa propose réellement dans le relevé (parse_combines_betpawa.py)


def composantes(c: M.Cle) -> list[M.Cle]:
    """Marchés simples dont la combinaison est l'intersection (sert à PROUVER que produit / minimum sont faux, jamais à calculer la probabilité)."""
    g, s = c
    if g in ("dc_btts", "1x2_btts"):
        a, b = s.split("|")
        return [("double_chance" if g == "dc_btts" else "1x2", a), ("btts", b)]
    t, lg = g.split("_total_")
    a, sens = s.split("|")
    return [("double_chance" if t == "dc" else "1x2" if t == "1x2" else "btts", a), (f"over_under_{lg}", sens)]


def combinaisons_proposees(mx: dict[str, Any]) -> list[int]:
    """Indices des combinés ayant eu au moins une cote RÉELLE avant le coup d'envoi dans l'archive : seuls ceux-là existent chez BetPawa. Les autres n'ont pas de cote : jamais publiés."""
    return [i for i, c in enumerate(M.CLES) if M.famille(c) == "combinés" and (~np.isnan(mx["cotes"][:, i])).any()]


def evaluer_combinaisons(mx: dict[str, Any]) -> dict[str, Any]:
    G, F, V, S, cotes, dev, res = mx["G"], mx["F"], mx["V"], mx["S"], mx["cotes"], mx["dev"], mx["res"]
    idx = combinaisons_proposees(mx)
    index = {c: i for i, c in enumerate(M.CLES)}
    paires = []
    for i in idx:
        try:
            paires.append((i, [index[x] for x in composantes(M.CLES[i])]))
        except KeyError:
            continue
    out: dict[str, Any] = {"generes": int(sum(1 for c in M.CLES if M.famille(c) == "combinés")), "proposes_par_betpawa": len(idx),
                           "groupes_proposes": sorted({M.CLES[i][0] for i in idx}), "groupes_sans_aucune_cote": sorted({c[0] for c in M.CLES if M.famille(c) == "combinés"} - {M.CLES[i][0] for i in idx}),
                           "observations_avec_cote": int((~np.isnan(cotes[:, idx])).sum()) if idx else 0}
    def mesure(fn) -> dict[str, Any]:
        P, Y = [], []
        for i, comp in paires:
            m = res & V[:, i] & ~np.isnan(cotes[:, i])
            P.append(fn(i, comp)[m])
            Y.append(S[m, i].astype(float))
        p, y = np.concatenate(P), np.concatenate(Y)
        return {"observations": int(len(p)), "annonce_moyenne": round(float(p.mean()), 4), "reel": round(float(y.mean()), 4), "ecart": round(float(p.mean() - y.mean()), 4), "brier": round(float(np.mean((p - y) ** 2)), 4)}
    out["methodes_reserve"] = {"evenement_joint_f": mesure(lambda i, c: F[:, i]), "evenement_joint_g": mesure(lambda i, c: G[:, i]),
                               "produit_des_pourcentages": mesure(lambda i, c: G[:, c[0]] * G[:, c[1]]), "minimum_des_pourcentages": mesure(lambda i, c: np.minimum(G[:, c[0]], G[:, c[1]]))}
    # réussite réelle par tranche de g de l'événement joint, développement puis réserve
    tr = []
    for lo in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        ligne: dict[str, Any] = {"tranche": f"{lo:.1f}-{lo + 0.1:.1f}"}
        for nom, sl in (("developpement", dev), ("reserve", res)):
            n = k = 0
            for i, _ in paires:
                m = sl & V[:, i] & ~np.isnan(cotes[:, i]) & (G[:, i] >= lo - 1e-12) & ((G[:, i] < lo + 0.1 - 1e-12) if lo < 0.9 else (G[:, i] <= 1.0))
                n += int(m.sum())
                k += int((m & S[:, i]).sum())
            ligne[nom] = {"n": n, "succes": k, "reussite": round(k / n, 4) if n else None}
        tr.append(ligne)
    out["reussite_par_tranche_g_joint"] = tr
    # une cote de combinaison n'est pas le produit des cotes de ses composantes
    rap = []
    for i, c in paires:
        a, b, z = cotes[:, c[0]], cotes[:, c[1]], cotes[:, i]
        ok = ~np.isnan(a) & ~np.isnan(b) & ~np.isnan(z)
        rap += list(z[ok] / (a[ok] * b[ok]))
    out["cote_reelle_sur_produit_des_cotes"] = {"observations": len(rap), "mediane": round(float(np.median(rap)), 3), "p5_p95": [round(float(x), 3) for x in np.percentile(rap, [5, 95])]} if rap else None
    out["part_cote_sous_1_35"] = round(float((cotes[:, idx] < COTE_MIN_PRINCIPAL).sum() / max(1, (~np.isnan(cotes[:, idx])).sum())), 4) if idx else None
    return out


def evenement_joint_exact(att_a: list[int], att_b: list[int], cle: M.Cle) -> float:
    """Probabilité de l'événement joint (« A marque au moins 1 ET plus de 1,5 buts », par exemple) par somme sur la loi des scores (attA ⊗ attB), sans produit de pourcentages
    individuels : la dépendance entre les deux conditions passe par le MÊME score. Un remboursement ne compte pas comme gagné."""
    n_a, n_b = len(att_a), len(att_b)
    return float(sum(1 for a in att_a for b in att_b if M.resultat(cle, a, b) == 1) / (n_a * n_b))


# ---------------------------------------------------------------------------------------------------------------------------------
# 6. Où g surestime-t-il ? (population jouable : cote ≥ 1,35, g ≥ 50 %)
# ---------------------------------------------------------------------------------------------------------------------------------
def _ligne(g: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    n = len(g)
    if n == 0:
        return {"n": 0}
    q = np.clip(g, 1e-3, 1 - 1e-3)
    return {"n": n, "g_moyen": round(float(g.mean()), 4), "reussite": round(float(y.mean()), 4), "ecart": round(float(g.mean() - y.mean()), 4), "wilson_95": wilson(int(y.sum()), n),
            "brier": round(float(np.mean((g - y) ** 2)), 4), "log_loss": round(float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))), 4)}


def surestimation(mx: dict[str, Any], cote_min: float = COTE_MIN_PRINCIPAL, g_min: float = 0.5) -> dict[str, Any]:
    """Écart entre l'estimation g et la réussite réelle, par tranche de g, famille, période chronologique et effectif du marché. Constats, aucune correction."""
    G, S, V, cotes = mx["G"], mx["S"], mx["V"], mx["cotes"]
    pop = V & (cotes >= cote_min) & (G >= g_min)
    out: dict[str, Any] = {"population": f"cote >= {cote_min}, g >= {g_min}", "ensemble": _ligne(G[pop], S[pop].astype(float))}
    out["par_tranche_g"] = {f"{b:.2f}-{min(b + 0.1, 1.0):.2f}": _ligne(G[pop & (G >= b - 1e-12) & ((G < b + 0.1 - 1e-12) if b < 0.9 else (G <= 1.0))], S[pop & (G >= b - 1e-12) & ((G < b + 0.1 - 1e-12) if b < 0.9 else (G <= 1.0))].astype(float))
                            for b in (0.5, 0.6, 0.7, 0.8, 0.9)}
    fam = np.array([M.famille(c) for c in M.CLES])
    out["par_famille"] = {f: _ligne(G[pop & (fam == f)[None, :]], S[pop & (fam == f)[None, :]].astype(float)) for f in sorted(set(fam))}
    per = _periodes(len(mx["ech"]))
    out["par_periode"] = {f"{mx['jours'][p[0]]}→{mx['jours'][p[-1]]}": _ligne(G[p][pop[p]], S[p][pop[p]].astype(float)) for p in per}
    eff = pop.sum(0)
    classes = {"moins de 30 observations": eff < MIN_OBS, "30 à 99": (eff >= MIN_OBS) & (eff < 100), "100 et plus": eff >= 100}
    out["par_effectif_du_marche"] = {k: {**_ligne(G[:, c][pop[:, c]], S[:, c][pop[:, c]].astype(float)), "marches": int(c.sum())} for k, c in classes.items()}
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# 5. Sortie
# ---------------------------------------------------------------------------------------------------------------------------------
def ecrire_csv(rows: list[dict[str, Any]]) -> None:
    import csv
    cols = ["id", "initial_174", "famille", "definition", "A_f_moyen", "A_g_moyen", "B_n_valides", "B_succes", "B_echecs", "B_frequence", "B_periode1", "B_periode2", "B_periode3", "ecart_A_moins_B", "stable",
            "part_avec_cote", "cote_ge_1_35", "cote_lt_1_35", "cote_mediane", "derniere_collecte_jour", "niveau_atteignable", "niveau_atteignable_n", "C_n", "C_reussite", "seuil_pour_cible"]
    with SORTIE_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for r in rows:
            b, q, nv, c = r["B_historique"], r["qualite"], r["niveau_atteignable_dev_cote_ge_1_35"], r["C_validation_reserve"]
            w.writerow([r["id"], int(r["initial_174"]), r["famille"], r["definition"], r["A_estime"]["f_moyen"], r["A_estime"]["g_moyen"], b["n_valides"], b["succes"], b["echecs"], b["frequence"],
                        *[p["frequence"] for p in b["par_periode"]], r["ecart_A_moins_B"], r["stable"], q["part_avec_cote"], q["cote_ge_1_35"], q["cote_lt_1_35"], q["cote_mediane"], q["derniere_collecte_jour"],
                        nv and nv["reussite_lissee"], nv and nv["n"], c and c["n"], c and c["reussite"], r["seuil_pour_cible"]["seuil_g"]])


def tout(log=print) -> dict[str, Any]:
    ech, exclus = K.echantillon(log)
    mx = matrices(ech)
    rows = tableau_marches(mx)
    out: dict[str, Any] = {"echantillon": {"matchs": len(ech), "coupe": mx["coupe"], "developpement": int(mx["dev"].sum()), "reserve": int(mx["res"].sum()), "exclus": dict(exclus)},
                           "marches": len(rows), "marches_initiaux_174": sum(r["initial_174"] for r in rows)}
    out["route_principale"] = [evaluer_principal(mx, c) for c in (0.55, 0.60, 0.65, 0.70, 0.75)]
    out["route_principale_cote_1_26_pour_comparaison"] = [evaluer_principal(mx, 0.70, 1.26)]
    out["route_combinaison"] = [evaluer_route_combinaison(mx, l) for l in LECTURES]
    out["combinaisons"] = evaluer_combinaisons(mx)
    out["niveau_atteignable"] = {"marches_avec_niveau": sum(1 for r in rows if r["niveau_atteignable_dev_cote_ge_1_35"]),
                                 "niveau_max": max((r["niveau_atteignable_dev_cote_ge_1_35"]["reussite_lissee"] for r in rows if r["niveau_atteignable_dev_cote_ge_1_35"]), default=None),
                                 "marches_au_moins_70": sum(1 for r in rows if r["niveau_atteignable_dev_cote_ge_1_35"] and r["niveau_atteignable_dev_cote_ge_1_35"]["reussite_lissee"] >= 0.70)}
    out["surestimation"] = surestimation(mx)
    out["stabilite"] = {"stables": sum(1 for r in rows if r["stable"] is True), "instables": sum(1 for r in rows if r["stable"] is False), "indetermines": sum(1 for r in rows if r["stable"] is None)}
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    SORTIE_CSV.parent.mkdir(exist_ok=True)
    ecrire_csv(rows)
    log(json.dumps({k: out[k] for k in ("route_principale", "route_combinaison", "niveau_atteignable", "stabilite")}, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    tout()
