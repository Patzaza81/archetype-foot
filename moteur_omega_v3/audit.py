"""Audit d'Omega V3 (directives de Patrick du 02/11/2026) : `python -m moteur_omega_v3.audit` → docs/omega_v3_audit.json + docs/omega_v3_marches_exemple.csv.

Règles :
- les seuils ne sont JAMAIS appris sur la réserve chronologique ; la réserve (30 % des matchs les plus récents, même coupe que `calibrage.validation`) ne sert qu'à lire ;
- aucune variante n'est choisie ici : toutes sont rapportées telles quelles ;
- une source par chiffre : chaque section dit d'où vient le nombre et comment il est calculé.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as K, coeur as C, definitions as Df, donnees as D, marches as M, variantes as V

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "omega_v3_audit.json"
CSV = ROOT / "docs" / "omega_v3_marches_exemple.csv"
EXEMPLE = ([2, 1, 3, 0, 2], [0, 1, 1, 2, 0], [1, 0, 2, 1, 3], [1, 2, 0, 1, 2])           # exemple fictif de la spécification (§2)
GRAINE = 20261102
NB_BOOT = 2000


# ---------------------------------------------------------------------------------------------------------------------------------
# 1. Matrice des 625 scénarios
# ---------------------------------------------------------------------------------------------------------------------------------
def audit_matrice() -> dict[str, Any]:
    att_a, def_a, att_b, def_b = EXEMPLE
    mat = C.matrice(att_a, def_a, att_b, def_b)
    a = C.analyser(att_a, def_a, att_b, def_b)
    paires = Counter((s["att_a"], s["att_b"]) for s in mat)
    # implémentation indépendante, sans numpy ni module du moteur : énumération brute des quatre boucles
    brut = [(x, y) for x in att_a for _ in def_a for y in att_b for _ in def_b]
    ref = {}
    for c in M.CLES:
        _, _, fn = Df.definition(*c)
        ref[c] = sum(1 for i, j in brut if fn(i, j) == 1)
    ecart_k = max(abs(m["k"] - ref[(m["cle"][0], m["cle"][1])]) for m in a["marches"])
    # formule de pondération marginale : P(attA = x) × P(attB = y), sans énumérer les scénarios
    pa, pb = Counter(att_a), Counter(att_b)
    marginal = {c: sum(pa[x] * pb[y] for x in pa for y in pb if Df.definition(*c)[2](x, y) == 1) / (len(att_a) * len(att_b)) for c in M.CLES}
    ecart_marg = max(abs(m["f"] - marginal[(m["cle"][0], m["cle"][1])]) for m in a["marches"])
    # le retrait d'une observation DÉFENSIVE ne change jamais la fréquence brute
    neutres = []
    for s in (1, 3):
        seqs = [list(att_a), list(def_a), list(att_b), list(def_b)]
        for r in range(5):
            red = [list(x) for x in seqs]
            del red[s][r]
            f, _ = C._frequences(C.histogrammes(*red, C.PARAMS_DEFAUT)["brute"])
            neutres.append(float(np.abs(f - np.array([m["f"] for m in a["marches"]])).max()))
    detail = [m for m in mat if m["id"] in ("0-0-0-0", "0-1-2-3", "2-2-4-1", "4-4-4-4", "1-3-0-2")]
    return {
        "exemple": {"att_a": att_a, "def_a": def_a, "att_b": att_b, "def_b": def_b, "source": "spécification Omega V1 §2 (valeurs fictives)"},
        "combinaisons": len(mat), "ids_uniques": len({m["id"] for m in mat}), "couples_attaque_distincts": len(paires), "repetitions_par_couple": sorted(set(paires.values())),
        "ecart_max_k_vs_enumeration_independante": ecart_k, "ecart_max_f_vs_ponderation_marginale": ecart_marg,
        "variation_max_f_si_on_retire_une_observation_defensive": max(neutres), "retraits_defensifs_testes": len(neutres),
        "niveaux": a["niveaux"], "scenarios_detailles": detail,
        "scenarios_incompatibles_presents_dans_le_brut": sum(1 for m in mat if m["niveau"] == "incompatible"),
        "top_scores": a["exploration"]["top_scores"][:5],
        "conclusion": ("La fréquence brute d'un marché est la fréquence des 25 couples (attA, attB), chacun répété 25 fois par les couples de défenses : "
                       "elle est égale à la formule de pondération marginale (écart numérique nul) et ne dépend d'AUCUNE observation défensive. "
                       "Pas de double comptage ni de pondération cachée ; mais les défenses n'ont aucun effet sur la fréquence brute ni sur la fréquence robuste g."),
    }


def tableau_marches() -> list[dict[str, Any]]:
    a = C.analyser(*EXEMPLE)
    out = []
    for m in a["marches"]:
        t, f, _ = Df.definition(m["cle"][0], m["cle"][1])
        nv = m["niveaux"]
        out.append({"groupe": m["cle"][0], "selection": m["cle"][1], "famille": m["famille"], "definition": t, "formule": f, "k": m["k"], "n": m["n"], "remboursés": m["remb"],
                    "f_brute": m["f"], "strict_k": nv["strict"]["k"], "strict_n": nv["strict"]["n"], "intermediaire_k": nv["intermediaire"]["k"], "intermediaire_n": nv["intermediaire"]["n"],
                    "elargi_k": nv["elargi"]["k"], "elargi_n": nv["elargi"]["n"], "incompatible_k": nv["incompatible"]["k"], "incompatible_n": nv["incompatible"]["n"],
                    "g": m["g"], "statut": m["statut"]})
    return out


def audit_marches() -> dict[str, Any]:
    ecarts = 0
    for c in M.CLES:
        _, _, fn = Df.definition(*c)
        for i in range(M.MAX_EQUIPE + 5):
            for j in range(M.MAX_EQUIPE + 5):
                ecarts += fn(i, j) != M.REGLES[c](i, j)
    l = D.charger_ligues()
    h = [m for v in l.matchs.values() for m in v]
    fam = Counter(M.famille(c) for c in M.CLES)
    groupes = Counter(c[0].split("_")[0] if not c[0].startswith(("over_under", "handicap", "cages")) else c[0].rsplit("_", 1)[0] if c[0][-1].isdigit() else c[0] for c in M.CLES)
    return {"marches": len(M.CLES), "uniques": len(set(M.CLES)), "familles": dict(fam), "ecarts_avec_definitions_independantes_sur_grille_14x14": int(ecarts),
            "max_observe_historique": {"buts_une_equipe": max(max(m["h"], m["a"]) for m in h), "total": max(m["h"] + m["a"] for m in h), "ecart": max(abs(m["h"] - m["a"]) for m in h), "matchs": len(h)},
            "bornes_du_moteur": {"buts_une_equipe": M.MAX_EQUIPE, "total": M.MAX_TOTAL, "ecart": M.MAX_ECART},
            "non_calculables": list(M.NON_CALCULABLES), "groupes": dict(groupes)}


# ---------------------------------------------------------------------------------------------------------------------------------
# Outils de mesure
# ---------------------------------------------------------------------------------------------------------------------------------
def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def brier_ll(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    q = np.clip(p, 1e-3, 1 - 1e-3)
    return float(np.mean((p - y) ** 2)), float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def boot_matchs(paris: list[dict[str, Any]], stat, nb: int = NB_BOOT) -> list[float] | None:
    """Intervalle à 95 % par rééchantillonnage des MATCHS (les paris d'un même match ne sont pas indépendants)."""
    if not paris:
        return None
    par: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for p in paris:
        par[p["match"]].append(p)
    ids = list(par)
    rng = np.random.default_rng(GRAINE)
    v = []
    for _ in range(nb):
        tir = rng.integers(0, len(ids), len(ids))
        v.append(stat([p for t in tir for p in par[ids[t]]]))
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]


def resume_paris(paris: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(paris)
    if not n:
        return {"paris": 0}
    k = sum(p["gagne"] for p in paris)
    ann = [p["p"] for p in paris if p["p"] is not None]
    y = np.array([p["gagne"] for p in paris if p["p"] is not None], float)
    pp = np.array(ann)
    br, ll = brier_ll(pp, y) if len(pp) else (None, None)
    co = [p for p in paris if p.get("cote")]
    marche = ({"cote_moyenne": round(float(np.mean([p["cote"] for p in co])), 3), "implicite_moyenne_du_bookmaker": round(float(np.mean([1 / p["cote"] for p in co])), 4),
               "taux_sur_paris_cotes": round(sum(p["gagne"] for p in co) / len(co), 4),
               "rendement_mise_plate_information": round(sum(p["gagne"] * (p["cote"] - 1) - (1 - p["gagne"]) for p in co) / len(co), 4)} if co else {})
    return {**marche, "paris": n, "matchs": len({p["match"] for p in paris}), "reussites": k, "taux": round(k / n, 4), "annonce_moyenne": round(float(np.mean(ann)), 4) if ann else None,
            "ecart_annonce_moins_reel": round(float(np.mean(ann)) - k / n, 4) if ann else None, "wilson_95": wilson(k, n),
            "brier": round(br, 4) if br is not None else None, "log_loss": round(ll, 4) if ll is not None else None}


def decouper(ech: list[dict[str, Any]]) -> tuple[list, list, str]:
    ech = sorted(ech, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    coupe = ech[int(len(ech) * K.PART_DEV)]["m"]["jour"]
    return [x for x in ech if x["m"]["jour"] < coupe], [x for x in ech if x["m"]["jour"] >= coupe], coupe


def selectionner(entrees: list[dict[str, Any]], cal: dict[str, Any]) -> list[dict[str, Any]]:
    """Le code de production (`coeur.decider` + `coeur.selection`) appliqué à des g/f donnés (variantes) : mêmes seuils par marché, même cote minimale, mêmes doublons."""
    paris = []
    for x in entrees:
        marches = []
        for k, c in enumerate(M.CLES):
            marches.append({"cle": [c[0], c[1]], "famille": M.famille(c), "g": round(float(x["g"][k]), 4), "f": round(float(x["f"][k]), 4), **C.analyse_cote(x["m"].get("cotes"), c)})
        a = {"marches": marches}
        C.decider(a, cal, C.PARAMS_DEFAUT)
        sel = C.selection(a)
        for q, l in enumerate(([sel["principal"]] if sel["principal"] else []) + sel["autres"]):
            r = M.resultat((l["cle"][0], l["cle"][1]), x["m"]["h"], x["m"]["a"])
            if r == 2:
                continue
            paris.append({"match": x["m"]["id"], "jour": x["m"]["jour"], "ligue": x["m"]["ligue"], "cle": M.cle_txt((l["cle"][0], l["cle"][1])), "famille": l["famille"], "gagne": int(r == 1),
                          "p": l["p_calibree"], "g": l["g"], "cote": l["cote"], "principal": q == 0})
    return paris


def pas_de_fuite_marche(paris: list[dict[str, Any]]) -> dict[str, Any]:
    return {"marches_distincts": len({p["cle"] for p in paris})}


# ---------------------------------------------------------------------------------------------------------------------------------
# 2. Variantes du score d'un scénario
# ---------------------------------------------------------------------------------------------------------------------------------
def entrees_variante(ech: list[dict[str, Any]], variante: str) -> list[dict[str, Any]]:
    out = []
    for x in ech:
        s = x["sequences"]
        f, g = V.robuste(variante, [list(s["att_a"]), list(s["def_a"]), list(s["att_b"]), list(s["def_b"])])
        out.append({"m": x["m"], "g": g, "f": f, "y": x["y"], "sequences": s, "jouable": x["jouable"]})
    return out


def pool(L: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    g = np.concatenate([x["g"] for x in L])
    y = np.concatenate([x["y"] for x in L])
    j = y != 2
    return g[j], (y[j] == 1).astype(float)


def qualite_probabilite(dev: list, res: list) -> dict[str, Any]:
    """Fréquence (ou probabilité modélisée) prise pour une probabilité, puis réussite lissée apprise sur le développement ; toutes marchés et matchs de la réserve mélangés."""
    gd, yd = pool(dev)
    gr, yr = pool(res)
    bornes = [round(0.1 * q, 1) for q in range(10)]
    def tr(g: np.ndarray, b: float) -> np.ndarray:
        return (g >= b - 1e-12) & ((g < b + 0.1 - 1e-12) if b < 0.9 else (g <= 1 + 1e-12))
    pleines = [(b, int(tr(gd, b).sum()), float(yd[tr(gd, b)].sum())) for b in bornes if tr(gd, b).any()]
    lis = dict(zip([b for b, _, _ in pleines], K._pav([n for _, n, _ in pleines], [k for _, _, k in pleines])))
    p_cal = np.array([lis[min(lis, key=lambda x: (abs(x - min(int(v * 10), 9) / 10), x))] for v in gr])
    base = float(yd.mean())
    b1, l1 = brier_ll(gr, yr)
    b2, l2 = brier_ll(p_cal, yr)
    b0, l0 = brier_ll(np.full_like(yr, base), yr)
    return {"observations": int(len(yr)), "brier_brut": round(b1, 4), "log_loss_brut": round(l1, 4), "brier_calibre": round(b2, 4), "log_loss_calibre": round(l2, 4),
            "brier_constante_dev": round(b0, 4), "log_loss_constante_dev": round(l0, 4)}


def cles_initiales() -> list[int]:
    """Indices des marchés de la première version (174 marchés, lignes limitées) : permet de comparer les Brier de l'audit à ceux de la première validation."""
    import re
    ok = []
    for k, (g, s) in enumerate(M.CLES):
        if g.startswith(("handicap_3issues", "btts_total")) or g == "nombre_exact_buts":
            continue
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", g)]
        lim = 6.5 if g.startswith("over_under_") and "domicile" not in g and "exterieur" not in g else (4.5 if "domicile" in g or "exterieur" in g or g.startswith(("dc_total", "1x2_total")) else 3.5)
        if g.startswith("over_under_") and re.fullmatch(r"over_under_\d+", g):
            lim = 4
        if nums and abs(nums[-1]) > lim:
            continue
        ok.append(k)
    return ok


def qualite_par_sous_ensemble(dev: list, res: list, colonnes: list[int]) -> dict[str, Any]:
    def sub(L: list) -> list:
        return [{"g": x["g"][colonnes], "y": x["y"][colonnes]} for x in L]
    return qualite_probabilite(sub(dev), sub(res))


def evaluer_variante(ech: list, variante: str, jouable: bool = True) -> tuple[dict[str, Any], list, dict[str, Any]]:
    e = entrees_variante(ech, variante)
    dev, res, coupe = decouper(e)
    s = K.seuils(dev, jouable)
    cal = K.calib_de(s, dev)
    paris = selectionner(res, cal)
    return {"variante": variante, "population_calibrage": "jouable (cote >= 1,26)" if jouable else "toutes les observations", "coupe": coupe, "matchs_dev": len(dev), "matchs_reserve": len(res), "marches_avec_seuil": sum(1 for v in s.values() if v["seuil"] is not None),
            "probabilite": qualite_probabilite(dev, res), "probabilite_marches_de_la_premiere_version": qualite_par_sous_ensemble(dev, res, cles_initiales()),
            "probabilite_par_famille": {fam: qualite_par_sous_ensemble(dev, res, [k for k, c in enumerate(M.CLES) if M.famille(c) == fam]) for fam in sorted({M.famille(c) for c in M.CLES})},
            "selection_reserve": resume_paris(paris),
            "matchs_reserve_avec_pari": len({p["match"] for p in paris}), "ic_taux_matchs_95": boot_matchs(paris, lambda L: sum(p["gagne"] for p in L) / max(len(L), 1)),
            "ic_ecart_matchs_95": boot_matchs([p for p in paris if p["p"] is not None], lambda L: float(np.mean([p["p"] for p in L])) - sum(p["gagne"] for p in L) / max(len(L), 1))}, paris, cal


# ---------------------------------------------------------------------------------------------------------------------------------
# 4. Écart annoncé / observé (variante A = production)
# ---------------------------------------------------------------------------------------------------------------------------------
def ventilation_marches(paris: list[dict[str, Any]], res: list, dev: list, cal: dict[str, Any]) -> list[dict[str, Any]]:
    """Par marché : sélections, annoncé moyen, réussites, taux, écart, Brier, log loss des paris, Wilson ; + Brier/log loss sur TOUTES les observations de la réserve du marché."""
    par: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in paris:
        par[p["cle"]].append(p)
    out = []
    for cle, L in sorted(par.items(), key=lambda kv: -len(kv[1])):
        r = resume_paris(L)
        k = M.INDEX[M.cle_depuis_txt(cle)]
        tr = cal["seuils"].get(cle, {}).get("tranches")
        g = np.array([x["g"][k] for x in res])
        y = np.array([x["y"][k] for x in res])
        ok = y != 2
        pc = np.array([C.p_calibree(v, tr, C.PARAMS_DEFAUT["pas_tranche"]) if tr else None for v in g], dtype=object)
        dispo = ok & np.array([v is not None for v in pc])
        if dispo.any():
            b, ll = brier_ll(np.array(pc[dispo], float), (y[dispo] == 1).astype(float))
        else:
            b = ll = None
        out.append({"marche": cle, "seuil": cal["seuils"][cle]["seuil"], **r, "ecart_points": round(100 * r["ecart_annonce_moins_reel"], 1),
                    "observations_reserve_avec_probabilite": int(dispo.sum()), "brier_observations": round(b, 4) if b is not None else None, "log_loss_observations": round(ll, 4) if ll is not None else None})
    return out


def apparent(dev: list, cal: dict[str, Any]) -> dict[str, Any]:
    """Les seuils appris sur le développement appliqués AU développement lui-même : mesure l'optimisme de l'apprentissage (sélection des seuils et lissage sur les mêmes données)."""
    return resume_paris(selectionner(dev, cal))


def marche_avant(dev: list, part: float = 0.6, jouable: bool = True) -> dict[str, Any]:
    """Validation chronologique INTERNE au développement (la réserve n'est pas touchée) : seuils appris sur les 60 % anciens du développement, testés sur les 40 % récents."""
    dev = sorted(dev, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    k = int(len(dev) * part)
    coupe = dev[k]["m"]["jour"]
    a, b = [x for x in dev if x["m"]["jour"] < coupe], [x for x in dev if x["m"]["jour"] >= coupe]
    s = K.seuils(a, jouable)
    cal = K.calib_de(s, a)
    return {"coupe": coupe, "matchs_apprentissage": len(a), "matchs_test": len(b), "marches_avec_seuil": sum(1 for v in s.values() if v["seuil"] is not None),
            "en_echantillon": resume_paris(selectionner(a, cal)), "hors_echantillon": resume_paris(selectionner(b, cal))}


def stabilite_seuils(dev: list, jouable: bool = True) -> dict[str, Any]:
    """Les seuils changent-ils quand on retire la moitié la plus récente ou la plus ancienne du développement ?"""
    dev = sorted(dev, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    h = len(dev) // 2
    s_all, s_old, s_new = K.seuils(dev, jouable), K.seuils(dev[:h], jouable), K.seuils(dev[h:], jouable)
    rows = []
    for c in M.CLES:
        k = M.cle_txt(c)
        v = (s_all[k]["seuil"], s_old[k]["seuil"], s_new[k]["seuil"])
        if any(x is not None for x in v):
            rows.append({"marche": k, "tout": v[0], "moitie_ancienne": v[1], "moitie_recente": v[2], "predictions": s_all[k]["predictions"]})
    stables = sum(1 for r in rows if r["tout"] is not None and r["moitie_ancienne"] is not None and r["moitie_recente"] is not None)
    return {"marches_avec_au_moins_un_seuil": len(rows), "marches_avec_seuil_dans_les_trois": stables, "marches_seuil_tout_mais_absent_dans_une_moitie": sum(1 for r in rows if r["tout"] is not None and (r["moitie_ancienne"] is None or r["moitie_recente"] is None)),
            "marches_seuil_seulement_dans_une_moitie": sum(1 for r in rows if r["tout"] is None), "detail": rows}


def etapes_filtre(L: list, cal: dict[str, Any]) -> dict[str, Any]:
    """D'où vient l'écart : on part de TOUTES les cellules (match, marché) dont g atteint le seuil du marché, puis on ajoute les filtres de la sélection un par un.
    Annoncé = réussite lissée de la tranche de g (`coeur.p_calibree`) ; réel = résultat (remboursés exclus). Scores exacts exclus (jamais retenus)."""
    exact = {i for i, c in enumerate(M.CLES) if M.famille(c) == "scores exacts"}
    rows = []
    for x in L:
        for k, c in enumerate(M.CLES):
            s = cal["seuils"].get(M.cle_txt(c))
            if not s or s["seuil"] is None or k in exact or x["y"][k] == 2:
                continue
            g = round(float(x["g"][k]), 4)
            if g < s["seuil"]:
                continue
            p = C.p_calibree(g, s["tranches"], C.PARAMS_DEFAUT["pas_tranche"])
            if p is None:
                continue
            rows.append((p, int(x["y"][k] == 1), C.lire_cote(x["m"].get("cotes"), c)))
    def r(nom: str, R: list) -> dict[str, Any]:
        if not R:
            return {"etape": nom, "cellules": 0}
        p, y = float(np.mean([a for a, _, _ in R])), float(np.mean([b for _, b, _ in R]))
        return {"etape": nom, "cellules": len(R), "annonce": round(p, 4), "reel": round(y, 4), "ecart_points": round(100 * (p - y), 1)}
    cm = C.PARAMS_DEFAUT["cote_min"]
    sel = [q for q in rows if q[2] and q[2] >= cm]
    out = [r("toutes les cellules g >= seuil", rows), r("... dont la cote est connue", [q for q in rows if q[2]]), r("... sans cote (injouables)", [q for q in rows if not q[2]]),
           r(f"... cote >= {cm:g} (population jouable)", sel), r(f"... cote < {cm:g}", [q for q in rows if q[2] and q[2] < cm])]
    if sel:
        out.append({"etape": "population jouable : probabilité implicite moyenne du bookmaker (1 / cote, marge comprise)", "implicite_moyenne": round(float(np.mean([1 / q[2] for q in sel])), 4),
                    "cote_moyenne": round(float(np.mean([q[2] for q in sel])), 3)})
    return {"etapes": out}


def dependance(paris: list[dict[str, Any]]) -> dict[str, Any]:
    """Paris d'un même match : nombre, et part des paris IMPLIQUÉS par un autre pari du même match (A ⊂ B : si A gagne, B gagne ⇒ gains corrélés)."""
    par: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in paris:
        par[p["match"]].append(p)
    grille = {}
    def ev(cle: str) -> np.ndarray:
        if cle not in grille:
            c = M.cle_depuis_txt(cle)
            grille[cle] = np.array([[M.REGLES[c](i, j) == 1 for j in range(M.MAX_EQUIPE + 1)] for i in range(M.MAX_EQUIPE + 1)])
        return grille[cle]
    impl = 0
    for L in par.values():
        for p in L:
            for q in L:
                if p is not q and p["cle"] != q["cle"]:
                    a, b = ev(p["cle"]), ev(q["cle"])
                    if (a & ~b).sum() == 0 and (b & ~a).sum() > 0:          # A strictement contenu dans B
                        impl += 1
                        break
    n = [len(v) for v in par.values()]
    # corrélation intra-match des réussites (ANOVA à un facteur sur les paris)
    gm = np.mean([p["gagne"] for p in paris])
    sst = sum((p["gagne"] - gm) ** 2 for p in paris)
    ssb = sum(len(L) * (np.mean([p["gagne"] for p in L]) - gm) ** 2 for L in par.values())
    k = len(par)
    nbar = len(paris) / k
    msb, msw = ssb / max(k - 1, 1), (sst - ssb) / max(len(paris) - k, 1)
    icc = (msb - msw) / (msb + (nbar - 1) * msw) if msb + (nbar - 1) * msw else 0.0
    return {"matchs_avec_pari": k, "paris_par_match_moyen": round(float(np.mean(n)), 2), "paris_par_match_max": max(n), "paris_implique_par_un_autre_du_meme_match": impl,
            "part_implique": round(impl / len(paris), 4), "correlation_intra_match": round(float(icc), 4), "taille_effective_approx": round(len(paris) / (1 + (nbar - 1) * max(icc, 0)), 1)}


def decomposition(paris: list[dict[str, Any]]) -> dict[str, Any]:
    """Contribution de chaque marché / famille / jour / championnat à l'écart global (écart = annoncé moyen − taux réel, pondéré par le nombre de paris)."""
    N = len(paris)
    def contrib(cle: str) -> list[dict[str, Any]]:
        par: dict[Any, list] = defaultdict(list)
        for p in paris:
            par[p[cle]].append(p)
        rows = [{cle: k, "paris": len(L), "taux": round(sum(x["gagne"] for x in L) / len(L), 4), "annonce": round(float(np.mean([x["p"] for x in L])), 4),
                 "contribution_points": round(100 * len(L) / N * (float(np.mean([x["p"] for x in L])) - sum(x["gagne"] for x in L) / len(L)), 2)} for k, L in par.items()]
        return sorted(rows, key=lambda r: -r["contribution_points"])
    ligue = contrib("ligue")
    return {"par_famille": contrib("famille"), "par_jour": sorted(contrib("jour"), key=lambda r: r["jour"]), "par_championnat_top10_paris": sorted(ligue, key=lambda r: -r["paris"])[:10],
            "marches_plus_grosse_contribution_positive": contrib("cle")[:8], "marches_plus_grosse_contribution_negative": contrib("cle")[-5:]}


# ---------------------------------------------------------------------------------------------------------------------------------
# 5 et 6. Couverture, fuites
# ---------------------------------------------------------------------------------------------------------------------------------
def compte_lieu(matchs: list[dict], equipe: str, domicile: bool, m: dict) -> int:
    cle = "dom" if domicile else "ext"
    return sum(1 for h in matchs if h[cle] == equipe and h["date"] < m["jour"] and not D._est_le_match(h, m["eq_dom"], m["eq_ext"], m["jour"]))


def audit_couverture(ligues: D.Ligues, archive: list[dict[str, Any]]) -> dict[str, Any]:
    joues = [m for m in archive if m["h"] is not None]
    cause = Counter()
    par_equipe: Counter = Counter()
    par_comp: dict[str, Counter] = defaultdict(Counter)
    par_mois: dict[str, Counter] = defaultdict(Counter)
    manque = Counter()
    effectifs = []
    for m in joues:
        liste = ligues.matchs.get(m["ligue"])
        mois = m["jour"][:7]
        if not liste:
            cause["championnat sans match connu"] += 1
            par_comp[m["competition"]]["exclu"] += 1
            par_mois[mois]["exclu"] += 1
            continue
        na, nb = compte_lieu(liste, m["eq_dom"], True, m), compte_lieu(liste, m["eq_ext"], False, m)
        effectifs.append((na, nb))
        if na >= 5 and nb >= 5:
            par_comp[m["competition"]]["analysable"] += 1
            par_mois[mois]["analysable"] += 1
            continue
        c = "domicile < 5 matchs à domicile" if na < 5 and nb >= 5 else ("extérieur < 5 matchs à l'extérieur" if nb < 5 and na >= 5 else "les deux équipes < 5 matchs au lieu")
        cause[c] += 1
        if na < 5:
            par_equipe[m["domicile"]] += 1
            manque[5 - na] += 1
        if nb < 5:
            par_equipe[m["exterieur"]] += 1
            manque[5 - nb] += 1
        par_comp[m["competition"]]["exclu"] += 1
        par_mois[mois]["exclu"] += 1
    # profondeur de l'historique par équipe
    n_dom, n_ext = Counter(), Counter()
    for v in ligues.matchs.values():
        for h in v:
            n_dom[h["dom"]] += 1
            n_ext[h["ext"]] += 1
    equipes = set(n_dom) | set(n_ext)
    tot_equipe = Counter()
    for e in equipes:
        tot_equipe[n_dom[e] + n_ext[e]] += 1
    analysables = sum(1 for a, b in effectifs if a >= 5 and b >= 5)
    def cumul(seuil: int) -> int:
        return sum(1 for a, b in effectifs if a >= seuil and b >= seuil)
    fenetres = {f"au moins {s} au lieu": cumul(s) for s in (3, 4, 5, 6, 8, 10)}
    return {"matchs_joues_archive": len(joues), "analysables": analysables, "exclus": len(joues) - analysables, "causes": dict(cause),
            "deficit_matchs_manquants_par_equipe_exclue": {str(k): v for k, v in sorted(manque.items())},
            "equipes_les_plus_touchees": par_equipe.most_common(15),
            "par_championnat": {k: dict(v) for k, v in sorted(par_comp.items(), key=lambda kv: -(kv[1]["exclu"] + kv[1]["analysable"]))[:15]},
            "par_mois": {k: dict(v) for k, v in sorted(par_mois.items())}, "couverture_si_le_minimum_etait": fenetres,
            "profondeur_historique": {"equipes": len(equipes), "matchs_par_equipe": {str(k): v for k, v in sorted(tot_equipe.items())}}}


def audit_fuites(ligues: D.Ligues, archive: list[dict[str, Any]]) -> dict[str, Any]:
    import glob
    import gzip
    brut = 0
    ids = Counter()
    cotes_tardives = 0
    sans_ko = 0
    for f in sorted(glob.glob(str(D.ARCHIVE / "*.json.gz"))):
        for k, x in json.load(gzip.open(f)).items():
            brut += 1
            ids[str(x.get("match_id"))] += 1
            sc = x.get("score") or {}
            if sc.get("buts_dom") is not None:
                pris, ko = (x.get("run") or {}).get("pris_le"), x.get("coup_d_envoi_utc")
                if not pris or not ko:
                    sans_ko += 1
                elif str(pris) >= str(ko):
                    cotes_tardives += 1
    decalage = [m for m in archive if m["coup_d_envoi_utc"] and str(m["coup_d_envoi_utc"])[:10] != m["jour"]]
    soi_meme, soi_meme_score = [], 0
    meme_jour = 0
    for m in archive:
        for h in ligues.matchs.get(m["ligue"], []):
            if h["dom"] == m["eq_dom"] and h["ext"] == m["eq_ext"] and abs(D.jours(h["date"], m["jour"])) <= 1:
                if h["date"] == m["jour"]:
                    meme_jour += 1                       # normal : le résultat est dans l'historique le jour même, et `date < jour` l'écarte
                    continue
                soi_meme.append({"match": m["id"], "jour_archive": m["jour"], "date_historique": h["date"], "score_historique": [h["h"], h["a"]], "joue": m["h"] is not None,
                                 "sens": "veille (fuite possible avant le correctif)" if h["date"] < m["jour"] else "lendemain (jamais utilisé : date >= jour)"})
                soi_meme_score += int(m["h"] is not None and (h["h"], h["a"]) == (m["h"], m["a"]))
    dup = Counter()
    for v in ligues.matchs.values():
        c = Counter((h["date"], h["dom"], h["ext"]) for h in v)
        dup["doublons_exacts"] += sum(n - 1 for n in c.values() if n > 1)
        for h in v:
            dup["scores_extremes_8+_buts_total"] += int(h["h"] + h["a"] >= 8)
            dup["identite_non_resolue"] += int(str(h["dom"]).startswith("?") or str(h["ext"]).startswith("?"))
            dup["domicile_egal_exterieur"] += int(h["dom"] == h["ext"])
    # séquences réellement utilisées après correctif : dernière date < jour, ancienneté
    ages, anciens, hors_saison = [], 0, 0
    fautes = 0
    for m in archive:
        if m["h"] is None:
            continue
        try:
            s = D.sequences(ligues.matchs.get(m["ligue"]) or [], m["eq_dom"], m["eq_ext"], m["jour"])
        except ValueError:
            continue
        ds = [x["date"] for x in s["A"] + s["B"]]
        fautes += int(max(ds) >= m["jour"])
        age = D.jours(min(ds), m["jour"])
        ages.append(age)
        anciens += int(age > 150)
        hors_saison += int(min(ds) < "2026-07-01")
    # effet du correctif « le match n'est pas son propre précédent » : séquences recalculées sans lui
    change = []
    vrai = D._est_le_match
    try:
        D._est_le_match = lambda *a, **k: False
        for m in archive:
            if m["h"] is None:
                continue
            liste = ligues.matchs.get(m["ligue"]) or []
            try:
                avant = D.sequences(liste, m["eq_dom"], m["eq_ext"], m["jour"])
            except ValueError:
                avant = None
            D._est_le_match = vrai
            try:
                apres = D.sequences(liste, m["eq_dom"], m["eq_ext"], m["jour"])
            except ValueError:
                apres = None
            D._est_le_match = lambda *a, **k: False
            if (avant is None) != (apres is None) or (avant and apres and (avant["att_a"], avant["def_a"], avant["att_b"], avant["def_b"]) != (apres["att_a"], apres["def_a"], apres["att_b"], apres["def_b"])):
                change.append({"match": m["id"], "jour": m["jour"], "domicile": m["domicile"], "exterieur": m["exterieur"], "avant": avant is not None, "apres": apres is not None})
    finally:
        D._est_le_match = vrai
    q = np.percentile(ages, [0, 25, 50, 75, 90, 100]).tolist()
    return {"enregistrements_archive_bruts": brut, "match_id_en_double": sum(n - 1 for n in ids.values() if n > 1), "archive_dedoublonnee": len(archive),
            "joues_cotes_prises_apres_coup_d_envoi_ecartes": cotes_tardives, "joues_sans_horodatage_ecartes": sans_ko,
            "matchs_dont_le_jour_differe_de_la_date_UTC_du_coup_d_envoi": len(decalage), "exemples_decalage": [(m["jour"], m["coup_d_envoi_utc"]) for m in decalage[:3]],
            "le_match_figure_dans_l_historique_le_meme_jour_(ecarte_par_date_<_jour)": meme_jour,
            "le_match_figure_dans_l_historique_avec_une_date_differente_d_un_jour": len(soi_meme),
            "dont_a_la_veille_(entrait_dans_les_sequences_avant_le_correctif)": sum(1 for x in soi_meme if x["sens"].startswith("veille")),
            "dont_au_lendemain_(jamais_utilise)": sum(1 for x in soi_meme if x["sens"].startswith("lendemain")),
            "exemples_a_la_veille": [x for x in soi_meme if x["sens"].startswith("veille")][:5],
            "anomalies_historique": dict(dup), "sequences_avec_une_date_posterieure_ou_egale_au_jour": fautes,
            "anciennete_de_la_plus_vieille_observation_jours": dict(zip(["min", "p25", "mediane", "p75", "p90", "max"], [round(x) for x in q])),
            "matchs_dont_une_observation_a_plus_de_150_jours": anciens, "matchs_avec_une_observation_avant_le_01_07_2026": hors_saison, "matchs_analysables": len(ages), "matchs_dont_les_sequences_changent_avec_le_correctif": len(change), "detail_correctif": change}


def audit_ancien_saison(ech: list[dict[str, Any]]) -> dict[str, Any]:
    """Les matchs dont une observation date d'avant l'été 2026 (saison précédente pour la plupart des championnats européens) : performance des g sur la réserve, vs les autres. Descriptif."""
    dev, res, _ = decouper(ech)
    def vieux(x: dict[str, Any]) -> bool:
        return min(o["date"] for o in x["sequences"]["A"] + x["sequences"]["B"]) < "2026-07-01"
    s = K.seuils(dev)
    cal = K.calib_de(s, dev)
    out = {}
    for nom, L in (("avec_observation_avant_juillet", [x for x in res if vieux(x)]), ("saison_en_cours_seulement", [x for x in res if not vieux(x)])):
        out[nom] = {"matchs": len(L), "selection": resume_paris(selectionner(L, cal))}
    out["part_du_developpement_avec_observation_avant_juillet"] = round(sum(vieux(x) for x in dev) / len(dev), 4)
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# 5 bis. Variantes de couverture / de fenêtre
# ---------------------------------------------------------------------------------------------------------------------------------
def echantillon_fenetre(ligues: D.Ligues, archive: list[dict[str, Any]], minimum: int, fenetre: int) -> list[dict[str, Any]]:
    out = []
    for m in archive:
        if m["h"] is None or not ligues.matchs.get(m["ligue"]):
            continue
        liste = ligues.matchs[m["ligue"]]
        dispo = min(compte_lieu(liste, m["eq_dom"], True, m), compte_lieu(liste, m["eq_ext"], False, m))
        n = min(fenetre, dispo)
        if n < minimum:
            continue
        try:
            s = D.sequences(liste, m["eq_dom"], m["eq_ext"], m["jour"], n=n)
        except ValueError:
            continue
        f, g = V.robuste("A", [list(s["att_a"]), list(s["def_a"]), list(s["att_b"]), list(s["def_b"])])
        out.append({"m": m, "g": g, "f": f, "y": M.vecteur(m["h"], m["a"]), "sequences": s, "n": n, "jouable": K.jouables(m.get("cotes"))})
    return out


def evaluer_couverture(ligues: D.Ligues, archive: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for nom, minimum, fen in (("minimum 5 strict, fenêtre 5 (production)", 5, 5), ("minimum 5, fenêtre élargie à 8", 5, 8), ("minimum 5, fenêtre élargie à 10", 5, 10),
                              ("taille variable : minimum 3, fenêtre 5", 3, 5), ("taille variable : minimum 4, fenêtre 5", 4, 5)):
        e = echantillon_fenetre(ligues, archive, minimum, fen)
        dev, res, coupe = decouper(e)
        s = K.seuils(dev)
        cal = K.calib_de(s, dev)
        paris = selectionner(res, cal)
        n_par = {}
        for n in sorted({x["n"] for x in res}):
            ids = {x["m"]["id"] for x in res if x["n"] == n}
            n_par[str(n)] = {"matchs": len(ids), **resume_paris([p for p in paris if p["match"] in ids])}
        out[nom] = {"matchs": len(e), "matchs_dev": len(dev), "matchs_reserve": len(res), "marches_avec_seuil": sum(1 for v in s.values() if v["seuil"] is not None),
                    "selection_reserve": resume_paris(paris), "par_taille_echantillon": n_par}
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
def tout(log=print) -> dict[str, Any]:
    rapport: dict[str, Any] = {"date": "2026-11-02", "graine": GRAINE, "bootstrap": NB_BOOT}
    log("1. matrice")
    rapport["matrice"] = audit_matrice()
    tab = tableau_marches()
    with CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(tab[0]), delimiter=";")
        w.writeheader()
        w.writerows(tab)
    log("2. marchés")
    rapport["marches"] = audit_marches()
    ligues = D.charger_ligues()
    archive = D.charger_archive(ligues)
    log("3. échantillon (moteur de production)")
    ech, exclus = K.echantillon(log)
    dev, res, coupe = decouper(ech)
    rapport["echantillon"] = {"analysables": len(ech), "exclus": dict(exclus), "coupe": coupe, "developpement": len(dev), "reserve": len(res), "reserve_du": res[0]["m"]["jour"], "reserve_au": res[-1]["m"]["jour"]}
    log("4. variantes A / B / C (calibrage sur la population jouable = production)")
    var, paris_a, cal_a = {}, {}, {}
    for v in V.VARIANTES:
        var[v], paris_a[v], cal_a[v] = evaluer_variante(ech, v)
    rapport["variantes"] = var
    ancien, paris_ancien, cal_ancien = evaluer_variante(ech, "A", jouable=False)
    rapport["variante_A_ancien_calibrage_toutes_observations"] = ancien
    ea = entrees_variante(dev[:30], "A")
    rapport["controle_variante_A_vs_production_max_ecart_g"] = float(max(np.abs(e["g"] - x["g"]).max() for e, x in zip(ea, dev[:30])))
    log("5. écart annoncé / observé")
    def bloc(jouable: bool, p: list, cal: dict[str, Any]) -> dict[str, Any]:
        return {"reserve": resume_paris(p), "ic_taux_matchs_95": boot_matchs(p, lambda L: sum(q["gagne"] for q in L) / max(len(L), 1)),
                "ic_ecart_matchs_95": boot_matchs([q for q in p if q["p"] is not None], lambda L: float(np.mean([q["p"] for q in L])) - sum(q["gagne"] for q in L) / max(len(L), 1)),
                "apparent_developpement": apparent(dev, cal), "marche_avant_dans_le_developpement": marche_avant(dev, jouable=jouable), "stabilite_seuils": stabilite_seuils(dev, jouable),
                "etapes_filtre_developpement": etapes_filtre(dev, cal), "etapes_filtre_reserve": etapes_filtre(res, cal), "dependance": dependance(p),
                "decomposition": decomposition([q for q in p if q["p"] is not None]), "principal_seulement": resume_paris([q for q in p if q["principal"]]),
                "par_marche": ventilation_marches(p, res, dev, cal)}
    rapport["ecart_ancien_calibrage"] = bloc(False, paris_ancien, cal_ancien)
    rapport["ecart_calibrage_jouable"] = bloc(True, paris_a["A"], cal_a["A"])
    rapport["anciennete"] = audit_ancien_saison(ech)
    log("6. couverture et fuites")
    rapport["couverture"] = audit_couverture(ligues, archive)
    rapport["fuites"] = audit_fuites(ligues, archive)
    rapport["variantes_couverture"] = evaluer_couverture(ligues, archive)
    SORTIE.write_text(json.dumps(rapport, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    log(f"audit écrit : {SORTIE.relative_to(ROOT)}")
    return rapport


if __name__ == "__main__":
    tout()
