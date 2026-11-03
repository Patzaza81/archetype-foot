"""Cœur du moteur Europe-Gamma (03/11/2026) : méthode Gamma (séquences au même lieu, matrice exhaustive de scénarios, paliers de compatibilité défensive, fréquence robuste
par retrait d'une observation) appliquée à TROIS échantillons mélangés 20 % / 30 % / 50 % (voir donnees.py).

Pour chaque échantillon z : quatre séquences (attaque A, défense A, attaque B, défense B), chaque observation porte le poids de force de l'adversaire affronté.
Le score d'un scénario est (attaque A i, attaque B k) ; la défense ne sert qu'à la compatibilité (écart en buts entiers ≤ 0 / 1 / 2), exactement comme Gamma.
Comme les indices de défense sont indépendants de (i, k), la masse d'une paire (i, k) à un palier t est calculable sans énumérer les n⁴ scénarios :
    masse(i, k, t) = poids(i) × poids(k) × Σ_{j : |attA_i − défB_j| ≤ t} poids(j) × Σ_{l : |attB_k − défA_l| ≤ t} poids(l)
(brut : toutes les défenses). C'est l'énumération complète de Gamma, regroupée, sans aucun scénario supprimé.

Fréquence d'un marché = Σ_z π_z × fréquence_z, π_z = poids de base renormalisé sur les échantillons présents. Fréquence robuste g = minimum des fréquences obtenues en retirant
UNE observation à la fois dans l'une des quatre séquences de l'un des échantillons (et de la fréquence brute). Une fréquence n'est pas une probabilité.

Sélection : si un calibrage existe (seuil par marché appris), règle Gamma (g ≥ seuil, cote ≥ 1,26, jamais deux fois le même événement). Sans calibrage : « aperçu non calibré »,
le marché de plus forte fréquence robuste parmi ceux dont la cote est jouable ; il est étiqueté tel quel, aucun seuil n'est inventé.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any

import numpy as np

from . import marches as M

NIVEAUX = ("strict", "intermediaire", "elargi")
ECART = {"strict": 0, "intermediaire": 1, "elargi": 2}            # buts entiers, comme Gamma
BASE = {"prec": 0.20, "champ": 0.30, "eu": 0.50}                   # décision de Patrick (03/11/2026)
COTE_MIN = 1.26
PAS_TRANCHE = 0.05
NM = len(M.CLES)
TOL = 1e-9
assert abs(sum(BASE.values()) - 1.0) < 1e-12


class DonneesInsuffisantes(ValueError):
    pass


# --- Séquences ------------------------------------------------------------------------------------------------------
def sequences(obs_a: list[dict], obs_b: list[dict]) -> dict[str, list[tuple[int, float]]]:
    return {"att_a": [(o["marques"], o["poids"]) for o in obs_a], "def_a": [(o["encaisses"], o["poids"]) for o in obs_a],
            "att_b": [(o["marques"], o["poids"]) for o in obs_b], "def_b": [(o["encaisses"], o["poids"]) for o in obs_b]}


def histogramme(sq: dict[str, list[tuple[int, float]]], t: int | None) -> dict[tuple[int, int], float]:
    """Masse de chaque score (attaque A, attaque B) : brut (t=None) ou palier cumulatif d'écart ≤ t."""
    h: dict[tuple[int, int], float] = defaultdict(float)
    tot_dj, tot_dl = sum(w for _, w in sq["def_b"]), sum(w for _, w in sq["def_a"])
    for a, wa in sq["att_a"]:
        dj = tot_dj if t is None else sum(w for d, w in sq["def_b"] if abs(a - d) <= t)
        for b, wb in sq["att_b"]:
            dl = tot_dl if t is None else sum(w for d, w in sq["def_a"] if abs(b - d) <= t)
            m = wa * wb * dj * dl
            if m > 0:
                h[(a, b)] += m
    return h


def _gains(h: dict[tuple[int, int], float]) -> tuple[np.ndarray, np.ndarray, float]:
    w, r, n = np.zeros(NM), np.zeros(NM), 0.0
    for (i, j), c in sorted(h.items()):
        v = M.vecteur(i, j)
        w += c * (v == 1)
        r += c * (v == 2)
        n += c
    return w, r, n


def _freq(h: dict[tuple[int, int], float]) -> tuple[np.ndarray, np.ndarray, float]:
    w, r, n = _gains(h)
    return (w / n, r / n, n) if n > 0 else (np.full(NM, np.nan), np.full(NM, np.nan), 0.0)


def _melange(parts: dict[str, tuple[np.ndarray, np.ndarray]], pi: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    f = sum(pi[z] * parts[z][0] for z in pi)
    r = sum(pi[z] * parts[z][1] for z in pi)
    return f, r


def pi_effectifs(presents: list[str]) -> dict[str, float]:
    s = sum(BASE[z] for z in presents)
    return {z: BASE[z] / s for z in presents}


# --- Analyse d'un match ----------------------------------------------------------------------------------------------
def valider(src: dict[str, dict[str, Any]], n_min: int) -> list[str]:
    presents = [z for z, s in src.items() if s["valide"]]
    for z in presents:
        for nom in ("A", "B"):
            if len(src[z][nom]) < n_min:
                raise DonneesInsuffisantes(f"échantillon {z} : {len(src[z][nom])} match(s) pour l'équipe {nom}, il en faut {n_min}")
    return presents


def analyser(src: dict[str, dict[str, Any]], cotes: dict | None = None, calib: dict[str, Any] | None = None, n_min: int = 3, min_echantillons: int = 2) -> dict[str, Any]:
    presents = valider(src, n_min)
    if len(presents) < min_echantillons:
        raise DonneesInsuffisantes(f"{len(presents)} échantillon(s) exploitable(s) sur 3 ; il en faut au moins {min_echantillons} (un échantillon seul n'est pas le mélange voulu)")
    pi = pi_effectifs(presents)
    sq = {z: sequences(src[z]["A"], src[z]["B"]) for z in presents}
    nominal = {z: len(sq[z]["att_a"]) * len(sq[z]["def_a"]) * len(sq[z]["att_b"]) * len(sq[z]["def_b"]) for z in presents}
    N = sum(pi[z] * nominal[z] for z in presents)                    # nombre de scénarios « équivalent » (affichage), jamais utilisé pour décider
    h = {z: {"brute": histogramme(sq[z], None), **{t: histogramme(sq[z], ECART[t]) for t in NIVEAUX}} for z in presents}
    brut = {z: _freq(h[z]["brute"]) for z in presents}
    F, R = _melange({z: brut[z][:2] for z in presents}, pi)
    # --- paliers : mélange sur les échantillons qui ont de la masse à ce palier, partie du brut conservée ---
    niv: dict[str, Any] = {}
    for t in NIVEAUX:
        parts = {z: _freq(h[z][t]) for z in presents}
        vivants = [z for z in presents if parts[z][2] > 0]
        if vivants:
            pt = pi_effectifs(vivants)
            ft, _ = _melange({z: parts[z][:2] for z in vivants}, pt)
            part = sum(pi[z] * parts[z][2] / brut[z][2] for z in presents)
        else:
            ft, part = None, 0.0
        niv[t] = {"f": ft, "part": part, "faible": len(vivants) < len(presents), "vivants": vivants}
    # --- stabilité : une observation retirée à la fois (4 séquences × chaque échantillon) ---
    F_loo, retraits = [], []
    for z in presents:
        for s in ("att_a", "def_a", "att_b", "def_b"):
            if len(sq[z][s]) < 2:
                continue
            for r in range(len(sq[z][s])):
                red = {k: list(v) for k, v in sq[z].items()}
                del red[s][r]
                fz, rz, nz = _freq(histogramme(red, None))
                if nz <= 0:
                    continue                                          # le retrait annule toute la masse (poids nuls) : variante sans information
                parts = {k: brut[k][:2] for k in presents}
                parts[z] = (fz, rz)
                F_loo.append(_melange(parts, pi)[0])
                retraits.append([z, s, r])
    FL = np.array(F_loo) if F_loo else np.empty((0, NM))
    out_m = []
    for k, c in enumerate(M.CLES):
        fl = FL[:, k] if len(FL) else np.array([F[k]])
        f_min, f_max = float(min(fl.min(), F[k])), float(max(fl.max(), F[k]))
        nm = {}
        for t in NIVEAUX:
            ft = niv[t]["f"]
            neq = int(round(N * niv[t]["part"]))
            nm[t] = {"k": int(round(ft[k] * neq)) if ft is not None else 0, "n": neq, "f": round(float(ft[k]), 4) if ft is not None else None, "faible": niv[t]["faible"]}
        contradiction = [t for t in NIVEAUX if niv[t]["f"] is not None and not niv[t]["faible"] and (niv[t]["f"][k] - 0.5) * (F[k] - 0.5) < 0]
        n_int = int(round(N))
        out_m.append({"cle": [c[0], c[1]], "famille": M.famille(c), "k": int(round(F[k] * N)), "n": n_int, "remb": int(round(R[k] * N)), "f": round(float(F[k]), 6),
                      "remb_f": round(float(R[k]), 6), "niveaux": nm,
                      "stabilite": {"f_min": round(f_min, 4), "f_max": round(f_max, 4), "amplitude": round(f_max - f_min, 4), "ecart_type": round(float(fl.std()), 4),
                                    "strict_min": None, "strict_max": None, "dependance_unique": bool(f_min == 0.0 < F[k])},
                      "diversite": {"configurations_favorables": 0, "configurations": 0, "part_max_observation": 0.0},
                      "g": round(f_min, 6), "contradiction": contradiction, **analyse_cote(cotes, c)})
    a: dict[str, Any] = {"echantillons": {z: {"poids_base": BASE[z], "poids_effectif": round(pi[z], 4), "n_a": len(src[z]["A"]), "n_b": len(src[z]["B"]), "scenarios": nominal[z]} for z in presents},
                         "absents": [z for z in src if z not in presents], "combinaisons": int(round(N)), "marches": out_m, "retraits": retraits,
                         "niveaux": {t: {"n": int(round(N * niv[t]["part"])), "part": round(niv[t]["part"], 4), "faible": niv[t]["faible"]} for t in NIVEAUX}}
    a["exploration"] = _exploration(h, pi, presents)
    a["scores_distincts"] = a["exploration"].pop("scores_distincts")
    a["verifications"] = verifier(a, F, R, h, pi, presents)
    decider(a, calib)
    a["conclusion"] = conclure(a)
    a["empreinte"] = hashlib.sha256(json.dumps([{z: src[z] for z in presents}, BASE, n_min], sort_keys=True, default=str).encode()).hexdigest()[:12]
    return a


def _exploration(h: dict, pi: dict[str, float], presents: list[str]) -> dict[str, Any]:
    mix: dict[tuple[int, int], float] = defaultdict(float)
    for z in presents:
        tot = sum(h[z]["brute"].values())
        for sc, c in h[z]["brute"].items():
            mix[sc] += pi[z] * c / tot
    ordre = sorted(mix.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [{"score": f"{i}-{j}", "occurrences": round(c, 4), "f": round(c, 4), "par_niveau": {t: None for t in NIVEAUX}} for (i, j), c in ordre[:10]]
    issues, buts_a, buts_b, totaux = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    for (i, j), c in mix.items():
        issues["A" if i > j else ("N" if i == j else "B")] += c
        buts_a[i] += c
        buts_b[j] += c
        totaux[i + j] += c
    arr = lambda d: {k: round(v, 4) for k, v in sorted(d.items())}          # noqa: E731
    return {"top_scores": top, "concentration_top3": round(sum(c for _, c in ordre[:3]), 4), "score_le_plus_frequent": top[0]["score"], "issues": arr(issues),
            "buts_a": arr(buts_a), "buts_b": arr(buts_b), "totaux": arr(totaux), "scores_distincts": len(mix)}


# --- Cotes ---------------------------------------------------------------------------------------------------------------
def lire_cote(cotes: dict | None, cle: M.Cle) -> float | None:
    v = ((cotes or {}).get(cle[0]) or {}).get(cle[1])
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1 else None


def analyse_cote(cotes: dict | None, cle: M.Cle) -> dict[str, Any]:
    c = lire_cote(cotes, cle)
    if c is None:
        return {"cote": None}
    out: dict[str, Any] = {"cote": c, "p_implicite": round(1 / c, 4), "marge": None, "p_implicite_corrigee": None}
    issues = M.issues_completes(cle)
    if issues:
        cs = [lire_cote(cotes, (cle[0], s)) for s in issues]
        if all(x is not None for x in cs):
            tot = sum(1 / x for x in cs)
            out["marge"] = round(tot - 1, 4)
            out["p_implicite_corrigee"] = round((1 / c) / tot, 4)
    return out


def p_calibree(g: float, tranches: list[dict[str, Any]] | None, pas: float = PAS_TRANCHE) -> float | None:
    for t in tranches or []:
        fin = t["debut"] + pas
        if t["debut"] <= g < fin - 1e-12 or (g >= 1.0 - 1e-12 and fin >= 1.0 - 1e-9):
            return t["reussite_lissee"]
    return None


# --- Contrôles mathématiques ------------------------------------------------------------------------------------------------
def verifier(a: dict[str, Any], F: np.ndarray, R: np.ndarray, h: dict, pi: dict[str, float], presents: list[str]) -> list[dict[str, Any]]:
    ms = {tuple(m["cle"]): m for m in a["marches"]}
    f = lambda g, s: ms[(g, s)]["f"]            # noqa: E731
    res: list[dict[str, Any]] = []

    def ajoute(nom: str, ok: bool, detail: str = "") -> None:
        res.append({"nom": nom, "ok": bool(ok), "detail": detail})

    ajoute("poids effectifs = 100 %", abs(sum(pi.values()) - 1) < TOL)
    ajoute("1X2 totalise 100 %", abs(f("1x2", "1") + f("1x2", "N") + f("1x2", "2") - 1) < 1e-5)
    ajoute("les deux marquent oui + non = 100 %", abs(f("btts", "Oui") + f("btts", "Non") - 1) < 1e-5)
    bad = [g for g in {m["cle"][0] for m in a["marches"] if m["cle"][0].startswith("over_under_") and m["cle"][0].endswith(".5") and m["cle"][0].count("_") == 2}
           if abs(f(g, "plus") + f(g, "moins") - 1) > 1e-5]
    ajoute("plus + moins = 100 % sur chaque ligne demi-but", not bad, ",".join(sorted(bad)))
    bad = [g for g in {m["cle"][0] for m in a["marches"] if m["cle"][0].startswith("over_under_") and m["cle"][0].count("_") == 2 and not m["cle"][0].endswith(".5")}
           if abs(f(g, "plus") + f(g, "moins") + ms[(g, "plus")]["remb_f"] - 1) > 1e-5]
    ajoute("lignes entières : gagné + perdu + remboursé = 100 %", not bad, ",".join(sorted(bad)))
    over = [f(f"over_under_{x:g}", "plus") for x in M.LIGNES_TOTAL]
    under = [f(f"over_under_{x:g}", "moins") for x in M.LIGNES_TOTAL]
    ajoute("plus de X décroissant avec la ligne", all(over[i] >= over[i + 1] - 1e-9 for i in range(len(over) - 1)))
    ajoute("moins de X croissant avec la ligne", all(under[i] <= under[i + 1] + 1e-9 for i in range(len(under) - 1)))
    ajoute("double chance cohérente avec le 1X2", abs(f("double_chance", "1N") - f("1x2", "1") - f("1x2", "N")) < 1e-5 and abs(f("double_chance", "12") - f("1x2", "1") - f("1x2", "2")) < 1e-5
           and abs(f("double_chance", "N2") - f("1x2", "2") - f("1x2", "N")) < 1e-5)
    ajoute("scores exacts couvrent 100 % de la distribution", abs(sum(m["f"] for m in a["marches"] if m["cle"][0] == "score_exact") - 1) < 1e-5)
    ajoute("aucune fréquence hors de [0 ; 1]", all(-1e-12 <= m["f"] <= 1 + 1e-12 for m in a["marches"]))
    ok = all(sum(h[z]["strict"].values()) <= sum(h[z]["intermediaire"].values()) + 1e-9 <= sum(h[z]["elargi"].values()) + 2e-9 <= sum(h[z]["brute"].values()) + 3e-9 for z in presents)
    ajoute("paliers emboîtés : strict ≤ intermédiaire ≤ élargi ≤ brut (par échantillon)", ok)
    ajoute("aucune masse perdue : somme brute > 0 pour chaque échantillon", all(sum(h[z]["brute"].values()) > 0 for z in presents))
    return res


# --- Décision -------------------------------------------------------------------------------------------------------------
def decider(a: dict[str, Any], calib: dict[str, Any] | None) -> None:
    seuils = (calib or {}).get("seuils") or {}
    cote_min = (calib or {}).get("cote_min", COTE_MIN)
    cands = []
    for m in a["marches"]:
        c = (m["cle"][0], m["cle"][1])
        s = seuils.get(M.cle_txt(c)) if calib else None
        m["seuil"] = s["seuil"] if s else None
        m["p_calibree"] = p_calibree(m["g"], s["tranches"]) if s else None
        if m["famille"] == "scores exacts":
            m["statut"], m["raison"], m["code"] = "rejete", "un score exact fréquent n'est jamais un pronostic retenu", 2
        elif calib:
            if not s or s["seuil"] is None:
                m["statut"], m["raison"], m["code"] = "rejete", "aucun seuil calibré pour ce marché", 0
            elif m["g"] < s["seuil"]:
                m["statut"], m["raison"], m["code"] = "rejete", f"fréquence robuste {m['g']:.0%} < seuil calibré {s['seuil']:.0%}", 1
            elif not m.get("cote"):
                m["statut"], m["raison"], m["code"] = "a_surveiller", "seuil atteint mais aucune cote disponible : pari injouable", 3
            elif m["cote"] < cote_min:
                m["statut"], m["raison"], m["code"] = "a_surveiller", f"seuil atteint mais cote {m['cote']:.2f} < {cote_min:.2f}".replace(".", ","), 4
            else:
                m["statut"], m["raison"], m["code"] = "retenu", "seuil atteint, cote jouable", 6
                cands.append(m)
        else:
            if not m.get("cote"):
                m["statut"], m["raison"], m["code"] = "non_evalue", "aperçu non calibré : aucune cote, pari injouable", 3
            elif m["cote"] < cote_min:
                m["statut"], m["raison"], m["code"] = "non_evalue", f"aperçu non calibré : cote {m['cote']:.2f} < {cote_min:.2f}".replace(".", ","), 4
            else:
                m["statut"], m["raison"], m["code"] = "apercu", "aperçu non calibré : fréquence robuste la plus haute parmi les marchés jouables", 7
                cands.append(m)
    cands.sort(key=lambda m: (-(m["p_calibree"] or 0), -m["g"], -m["f"], M.cle_txt(tuple(m["cle"]))))
    vus: dict[bytes, str] = {}
    for m in cands:
        e = M.evenement((m["cle"][0], m["cle"][1]))
        if e in vus:
            m["statut"], m["raison"], m["code"] = "a_surveiller", f"même événement que {vus[e]}", 5
        else:
            vus[e] = M.cle_txt((m["cle"][0], m["cle"][1]))
    gardes = [m for m in cands if m["statut"] in ("retenu", "apercu")]
    if not calib:
        for m in gardes[1:]:
            m["statut"], m["raison"], m["code"] = "non_evalue", "aperçu non calibré : seul le marché de tête est présenté", 7
        gardes = gardes[:1]
    a["retenus"] = gardes
    a["calibre"] = bool(calib)


def selection(a: dict[str, Any]) -> dict[str, Any]:
    r = a["retenus"]
    return {"principal": r[0] if r else None, "autres": r[1:], "raison": None if r else "AUCUN MARCHÉ RETENU", "apercu_non_calibre": not a.get("calibre")}


def conclure(a: dict[str, Any]) -> list[str]:
    ms = [m for m in a["marches"] if m["famille"] != "scores exacts"]
    top = sorted([m for m in ms if 0.0 < m["f"] < 1.0], key=lambda m: (-m["f"], M.cle_txt(tuple(m["cle"]))))[:3]
    ech = " ; ".join(f"{z} {v['poids_effectif']:.0%}" for z, v in a["echantillons"].items())
    L = [f"Échantillons utilisés et poids effectifs : {ech}" + (f" (absents : {', '.join(a['absents'])})" if a["absents"] else "") + ".",
         "Ce qui ressort le plus souvent (fréquence brute mélangée) : " + " ; ".join(f"{m['cle'][0]}/{m['cle'][1]} {m['f']:.0%}" for m in top) + ".",
         f"Dépend d'une seule observation : {sum(1 for m in ms if m['stabilite']['dependance_unique'])} marché(s). Contradictions brut/palier : {sum(1 for m in ms if m['contradiction'])} marché(s)."]
    r = a["retenus"]
    L.append(("Aperçu NON calibré : " if not a.get("calibre") and r else "Retenu : ") + (" ; ".join(f"{m['cle'][0]}/{m['cle'][1]}" for m in r) if r else "AUCUN MARCHÉ RETENU") + ".")
    return L
