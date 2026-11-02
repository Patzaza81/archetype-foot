"""Moteur Omega V3 — exploration statistique ouverte (spécification « Nouveau moteur Omega V1 » de Patrick, reçue le 02/11/2026).

Il REMPLACE le moteur DC derrière la page Gamma (ordre de Patrick du 02/11/2026). Autonome : aucun import d'un autre moteur, aucune cote dans l'exploration.

Principe : la matrice observe, les calculs mesurent, le moteur ne force jamais la conclusion. Quatre séquences de buts (attaque A, défense A, attaque B,
défense B ; A reçoit B ; au moins 5 matchs au même lieu chacune, toute la saison ensuite : règle de Patrick du 02/11/2026), n × n × n × n scénarios (625 à 5 matchs, 130 321 à 19) parcourus SANS suppression préalable, comptés sans les énumérer.

LECTURE DE LA SPÉCIFICATION (à connaître, elle n'est pas écrite noir sur blanc) :
- le score d'un scénario (attA_i, defA_l, attB_k, defB_j) est (attA_i, attB_k) : buts de A et buts de B ; l'écart « attA − attB » du §3.1 en est la marge ;
- les deux observations défensives ne changent donc pas le score : elles servent à MESURER la compatibilité (§5) : écart A = |attA_i − defB_j|,
  écart B = |attB_k − defA_l| ; le palier d'un scénario est fixé par le plus grand des deux écarts ;
- paliers CUMULATIFS (strict ⊂ intermédiaire ⊂ élargi) ; seuils en BUTS ENTIERS (0, 1, 2), paramétrables (`PARAMS_DEFAUT`) : une convention de lecture, pas une vérité statistique ;
- la fréquence brute d'un marché est donc la proportion de paires (attA, attB) qui le font gagner : une FRÉQUENCE COMBINATOIRE, jamais une probabilité (§10).

Le moteur ne produit PAS de probabilité prédictive : la sélection s'appuie sur la « fréquence robuste » g = la plus basse des fréquences brutes obtenues en retirant une
observation à la fois (§8.1), et sur un seuil de g APPRIS par marché sur l'archive (`calibrage.py`, protocole de Patrick du 30/10/2026 : réussite réelle visée 70 %).
Aucun coefficient posé à la main. Pas d'indice composite (§9) : les composantes sont affichées séparément.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any

import numpy as np

from . import definitions as Df, marches as M

NIVEAUX = ("strict", "intermediaire", "elargi")
PARAMS_DEFAUT: dict[str, Any] = {
    "ecart_max_niveau": {"strict": 0, "intermediaire": 1, "elargi": 2},   # buts entiers ; au-delà de « élargi » : incompatible (reste dans l'exploration brute)
    "min_scenarios_niveau": 25,       # = nombre de paires (attA, attB) (25 à 5 matchs, valeur conservée dans l'empreinte ; le seuil appliqué est len(attA) × len(attB)) : en dessous, un palier est SIGNALÉ « trop peu représenté », jamais utilisé pour décider
    "cote_min": 1.26,                 # décision de Patrick (30/10/2026) pour Gamma : cote BetPawa connue et ≥ 1,26, sinon le pari n'est pas jouable
    "pas_tranche": 0.05,
}
MARCHES_N = len(M.CLES)


class DonneesInsuffisantes(ValueError):
    """Les conditions minimales de la spécification (§2.3) ne sont pas réunies : aucune prédiction n'est fabriquée."""


# --- 3. Matrice exhaustive ---------------------------------------------------------------------------------------------
def combinaisons(att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int]) -> list[tuple[int, int, int, int, int, int, int, int]]:
    """TOUS les scénarios (i, l, k, j, attA_i, defA_l, attB_k, defB_j), sans filtre ni suppression. N = n(attA) × n(defA) × n(attB) × n(defB)."""
    return [(i, l, k, j, a, da, b, db) for i, a in enumerate(att_a) for l, da in enumerate(def_a) for k, b in enumerate(att_b) for j, db in enumerate(def_b)]


def matrice(att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int], params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """La matrice complète, scénario par scénario (§3.2 : quatre observations d'origine, score offensif, deux écarts, identifiant, résultat des marchés)."""
    p = params or PARAMS_DEFAUT
    out = []
    for i, l, k, j, a, da, b, db in combinaisons(att_a, def_a, att_b, def_b):
        e_a, e_b = abs(a - db), abs(b - da)
        out.append({"id": f"{i}-{l}-{k}-{j}", "att_a": a, "def_a": da, "att_b": b, "def_b": db, "score": [a, b], "marge": a - b,
                    "ecart_a": e_a, "ecart_b": e_b, "niveau": niveau(max(e_a, e_b), p), "marches": M.vecteur(a, b).tolist()})
    return out


def niveau(ecart: int, p: dict[str, Any]) -> str:
    """Palier le plus étroit qui contient le scénario (un scénario « strict » est aussi « intermédiaire » et « élargi » : paliers cumulatifs)."""
    for n in NIVEAUX:
        if ecart <= p["ecart_max_niveau"][n]:
            return n
    return "incompatible"


def histogrammes_enumeres(att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int], p: dict[str, Any]) -> dict[str, Counter]:
    """RÉFÉRENCE (lente) : parcourt les scénarios un à un. Sert à prouver que `histogrammes` donne exactement les mêmes comptes ; non utilisée par le moteur."""
    h: dict[str, Counter] = {"brute": Counter(), "strict": Counter(), "intermediaire": Counter(), "elargi": Counter(), "incompatible": Counter()}
    lim = p["ecart_max_niveau"]
    for _, _, _, _, a, da, b, db in combinaisons(att_a, def_a, att_b, def_b):
        e = max(abs(a - db), abs(b - da))
        h["brute"][(a, b)] += 1
        if e <= lim["elargi"]:
            h["elargi"][(a, b)] += 1
            if e <= lim["intermediaire"]:
                h["intermediaire"][(a, b)] += 1
                if e <= lim["strict"]:
                    h["strict"][(a, b)] += 1
        else:
            h["incompatible"][(a, b)] += 1
    return h


def histogrammes(att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int], p: dict[str, Any]) -> dict[str, Counter]:
    """Distribution des scores (attA, attB) : brute (tous les scénarios), puis par palier cumulatif, + les incompatibles.

    Calcul SANS énumérer les scénarios (profondeur variable, jusqu'à toute la saison : 19⁴ = 130 321 scénarios). Les quatre indices sont indépendants et le score ne dépend que de
    (attA_i, attB_k) : le nombre de scénarios de score (a, b) dont l'écart défensif maximal est ≤ L vaut
    [nb de attA égaux à a × nb de defB à au plus L buts de a] × [nb de attB égaux à b × nb de defA à au plus L buts de b]. Mêmes entiers que l'énumération
    (`histogrammes_enumeres`, comparée dans les tests)."""
    lim = p["ecart_max_niveau"]
    ca, cb = Counter(att_a), Counter(att_b)
    def cote(c: Counter, defense: list[int], seuil: int | None) -> dict[int, int]:
        return {v: n * (len(defense) if seuil is None else sum(1 for d in defense if abs(v - d) <= seuil)) for v, n in c.items()}
    A0, B0 = cote(ca, def_b, None), cote(cb, def_a, None)
    h: dict[str, Counter] = {"brute": Counter({(a, b): x * y for a, x in A0.items() for b, y in B0.items()})}
    for t in NIVEAUX:
        At, Bt = cote(ca, def_b, lim[t]), cote(cb, def_a, lim[t])
        h[t] = Counter({(a, b): x * y for a, x in At.items() for b, y in Bt.items() if x * y})
    Ae, Be = cote(ca, def_b, lim["elargi"]), cote(cb, def_a, lim["elargi"])
    h["incompatible"] = Counter({(a, b): A0[a] * B0[b] - Ae[a] * Be[b] for a in A0 for b in B0 if A0[a] * B0[b] - Ae[a] * Be[b]})
    return h


def _gains(hist: Counter) -> tuple[np.ndarray, np.ndarray, int]:
    """(scénarios gagnants, remboursés, total) de chaque marché pour une distribution de scores."""
    w, r, n = np.zeros(MARCHES_N), np.zeros(MARCHES_N), 0
    for (i, j), c in sorted(hist.items()):
        v = M.vecteur(i, j)
        w += c * (v == 1)
        r += c * (v == 2)
        n += c
    return w, r, n


# --- 11. Cotes ---------------------------------------------------------------------------------------------------------
def lire_cote(cotes: dict | None, cle: M.Cle) -> float | None:
    v = ((cotes or {}).get(cle[0]) or {}).get(cle[1])
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1 else None


def analyse_cote(cotes: dict | None, cle: M.Cle) -> dict[str, Any]:
    """Cote, probabilité implicite 1 / cote, marge du bookmaker (seulement si toutes les issues du marché sont cotées), probabilité implicite corrigée."""
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


def p_calibree(g: float, tranches: list[dict[str, Any]] | None, pas: float) -> float | None:
    """Réussite RÉELLE lissée observée sur l'archive pour la tranche de g contenant g (§10 C : seule estimation « prédictive » du moteur, et seulement là où elle a été mesurée)."""
    for t in tranches or []:
        fin = t["debut"] + pas
        if t["debut"] <= g < fin - 1e-12 or (g >= 1.0 - 1e-12 and fin >= 1.0 - 1e-9):
            return t["reussite_lissee"]
    return None


# --- 9 et 12. Analyse d'un match -----------------------------------------------------------------------------------------
def valider_sequences(att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int], minimum: int = 5) -> None:
    for nom, s in (("attaque A", att_a), ("défense A", def_a), ("attaque B", att_b), ("défense B", def_b)):
        if len(s) < minimum:
            raise DonneesInsuffisantes(f"{nom} : {len(s)} observation(s), il en faut {minimum}")
        for x in s:
            if x is None or isinstance(x, bool) or not isinstance(x, int) or x < 0:
                raise DonneesInsuffisantes(f"{nom} : valeur invalide {x!r} (aucune donnée manquante n'est remplacée par zéro)")
    if len(att_a) != len(def_a) or len(att_b) != len(def_b):
        raise DonneesInsuffisantes("attaque et défense d'une équipe doivent venir des mêmes matchs")


def _frequences(hist: Counter) -> tuple[np.ndarray, int]:
    w, _, n = _gains(hist)
    return (w / n if n else np.full(MARCHES_N, np.nan)), n


def analyser(att_a: list[int], def_a: list[int], att_b: list[int], def_b: list[int], cotes: dict | None = None, calib: dict[str, Any] | None = None,
             params: dict[str, Any] | None = None, minimum: int = 5) -> dict[str, Any]:
    """Exploration complète d'un match à partir des quatre séquences. Déterministe : mêmes entrées, mêmes sorties."""
    p = params or PARAMS_DEFAUT
    valider_sequences(att_a, def_a, att_b, def_b, minimum)
    N = len(att_a) * len(def_a) * len(att_b) * len(def_b)               # nombre de scénarios (jamais énumérés : voir `histogrammes`)
    mini_niveau = len(att_a) * len(att_b)                                 # palier « trop peu représenté » sous le nombre de paires (attA, attB) : 25 à 5 matchs
    h = histogrammes(att_a, def_a, att_b, def_b, p)
    W, R, n_brut = _gains(h["brute"])
    assert n_brut == N and sum(h["brute"].values()) == N      # aucun scénario perdu ni compté deux fois
    # --- paliers de compatibilité (§5) ---
    niv: dict[str, Any] = {}
    for t in (*NIVEAUX, "incompatible"):
        w, r, n = _gains(h[t])
        niv[t] = {"w": w, "n": n, "f": (w / n if n else None), "faible": n < mini_niveau}
    # --- stabilité (§8.1) : une observation retirée à la fois dans chacune des quatre séquences ---
    seqs = [list(att_a), list(def_a), list(att_b), list(def_b)]
    F_loo, S_loo, retraits = [], [], []
    for s in range(4):
        if len(seqs[s]) < 2:
            continue
        for r in range(len(seqs[s])):
            red = [list(x) for x in seqs]
            del red[s][r]
            hh = histogrammes(*red, p)
            f, _ = _frequences(hh["brute"])
            fs, ns = _frequences(hh["strict"])
            F_loo.append(f)
            S_loo.append(fs)
            retraits.append([("attaque A", "défense A", "attaque B", "défense B")[s], r])
    F_loo_a = np.array(F_loo) if F_loo else np.empty((0, MARCHES_N))
    # --- concentration (§8.2) : part des scénarios gagnants qui contiennent une même observation ---
    ca, cb = Counter(att_a), Counter(att_b)
    gagne = {(a, b): M.vecteur(a, b) == 1 for a in ca for b in cb}
    sup_ab = sum(ca[a] * cb[b] * gagne[(a, b)] for a in ca for b in cb)                          # scénarios gagnants / (nb defA × nb defB)
    sup = sup_ab * (len(def_a) * len(def_b))
    part = np.zeros(MARCHES_N)
    for r in range(len(att_a)):                                                                  # scénarios gagnants qui contiennent l'observation r de attA
        c = sum(cb[b] * gagne[(att_a[r], b)] for b in cb)
        part = np.maximum(part, np.divide(c, sup_ab, out=np.zeros(MARCHES_N), where=sup_ab > 0))
    for r in range(len(att_b)):
        c = sum(ca[a] * gagne[(a, att_b[r])] for a in ca)
        part = np.maximum(part, np.divide(c, sup_ab, out=np.zeros(MARCHES_N), where=sup_ab > 0))
    if len(def_a):                                                                               # une observation défensive est dans 1 / n des scénarios, gagnants compris
        part = np.maximum(part, np.where(sup > 0, 1 / len(def_a), 0.0))
    if len(def_b):
        part = np.maximum(part, np.where(sup > 0, 1 / len(def_b), 0.0))
    paires = np.stack([M.vecteur(a, b) == 1 for a in set(att_a) for b in set(att_b)])  # (valeurs distinctes) : diversité des configurations offensives
    paires_n = len(set(att_a)) * len(set(att_b))
    f_brute = W / N
    out_m: list[dict[str, Any]] = []
    for k, c in enumerate(M.CLES):
        fl = F_loo_a[:, k] if len(F_loo_a) else np.array([f_brute[k]])
        f_min, f_max = float(min(fl.min(), f_brute[k])), float(max(fl.max(), f_brute[k]))
        g = f_min
        niveaux_m = {t: {"k": int(niv[t]["w"][k]), "n": niv[t]["n"], "f": (round(float(niv[t]["w"][k] / niv[t]["n"]), 4) if niv[t]["n"] else None), "faible": niv[t]["faible"]}
                     for t in (*NIVEAUX, "incompatible")}
        contradiction = [t for t in NIVEAUX if niv[t]["n"] >= mini_niveau and (niveaux_m[t]["f"] - 0.5) * (f_brute[k] - 0.5) < 0]
        sl = [x[k] for x in S_loo if not math.isnan(x[k])]
        out_m.append({
            "cle": [c[0], c[1]], "famille": M.famille(c), "k": int(W[k]), "n": N, "remb": int(R[k]), "f": round(float(f_brute[k]), 4),
            "niveaux": niveaux_m,
            "stabilite": {"f_min": round(f_min, 4), "f_max": round(f_max, 4), "amplitude": round(f_max - f_min, 4), "ecart_type": round(float(fl.std()), 4),
                          "strict_min": round(float(min(sl)), 4) if sl else None, "strict_max": round(float(max(sl)), 4) if sl else None, "dependance_unique": bool(f_min == 0.0 < f_brute[k])},
            "diversite": {"configurations_favorables": int(paires[:, k].sum()), "configurations": paires_n, "part_max_observation": round(float(part[k]), 4)},
            "g": round(g, 4), "contradiction": contradiction, **analyse_cote(cotes, c)})
    a: dict[str, Any] = {"entrees": {"att_a": list(att_a), "def_a": list(def_a), "att_b": list(att_b), "def_b": list(def_b)}, "combinaisons": N,
                         "scores_distincts": len(h["brute"]), "marches": out_m, "retraits": retraits}
    a["exploration"] = _exploration(h, N)
    a["niveaux"] = {t: {"n": niv[t]["n"], "part": round(niv[t]["n"] / N, 4), "faible": niv[t]["faible"]} for t in (*NIVEAUX, "incompatible")}
    a["verifications"] = verifier(a, h)
    decider(a, calib, p)
    a["conclusion"] = conclure(a)
    a["empreinte"] = empreinte(a["entrees"], p)
    return a


def _exploration(h: dict[str, Counter], N: int) -> dict[str, Any]:
    brut = sorted(h["brute"].items(), key=lambda kv: (-kv[1], kv[0]))                 # égalités : ordre croissant du score (déterministe, §7)
    def part(t: str) -> dict[str, float]:
        n = sum(h[t].values())
        return {f"{i}-{j}": round(c / n, 4) for (i, j), c in h[t].items()} if n else {}
    top = [{"score": f"{i}-{j}", "occurrences": c, "f": round(c / N, 4), "par_niveau": {t: part(t).get(f"{i}-{j}") for t in NIVEAUX}} for (i, j), c in brut[:10]]
    issues = Counter()
    for (i, j), c in h["brute"].items():
        issues["A" if i > j else ("N" if i == j else "B")] += c
    buts_a, buts_b, totaux = Counter(), Counter(), Counter()
    for (i, j), c in h["brute"].items():
        buts_a[i] += c
        buts_b[j] += c
        totaux[i + j] += c
    return {"top_scores": top, "concentration_top3": round(sum(c for _, c in brut[:3]) / N, 4), "score_le_plus_frequent": top[0]["score"],
            "issues": {k: issues.get(k, 0) for k in ("A", "N", "B")}, "buts_a": dict(sorted(buts_a.items())), "buts_b": dict(sorted(buts_b.items())), "totaux": dict(sorted(totaux.items()))}


# --- 14. Cohérence mathématique ---------------------------------------------------------------------------------------
def verifier(a: dict[str, Any], h: dict[str, Counter]) -> list[dict[str, Any]]:
    """Contrôles mathématiques automatiques (§14). Une erreur de CALCUL bloque la publication du match ; une limite de la méthode est seulement signalée."""
    ms = {tuple(m["cle"]): m for m in a["marches"]}
    f = lambda g, s: ms[(g, s)]["f"]            # noqa: E731
    k = lambda g, s: ms[(g, s)]["k"]            # noqa: E731
    N = a["combinaisons"]
    tol = 1e-9
    res: list[dict[str, Any]] = []
    def ajoute(nom: str, ok: bool, detail: str = "") -> None:
        res.append({"nom": nom, "ok": bool(ok), "detail": detail})
    ajoute("1X2 totalise 100 %", k("1x2", "1") + k("1x2", "N") + k("1x2", "2") == N)
    ajoute("les deux marquent oui + non = 100 %", k("btts", "Oui") + k("btts", "Non") == N)
    bad = [g for g in {m["cle"][0] for m in a["marches"] if m["cle"][0].startswith("over_under_") and m["cle"][0].endswith(".5") and m["cle"][0].count("_") == 2}
           if k(g, "plus") + k(g, "moins") != N]
    ajoute("plus + moins = 100 % sur chaque ligne demi-but", not bad, ",".join(sorted(bad)))
    bad = [g for g in {m["cle"][0] for m in a["marches"] if m["cle"][0].startswith("over_under_") and m["cle"][0].count("_") == 2 and not m["cle"][0].endswith(".5")}
           if ms[(g, "plus")]["k"] + ms[(g, "moins")]["k"] + ms[(g, "plus")]["remb"] != N]
    ajoute("lignes entières : gagné + perdu + remboursé = 100 %", not bad, ",".join(sorted(bad)))
    tot = [x for x in M.LIGNES_TOTAL]
    over = [f(f"over_under_{x:g}", "plus") for x in tot]
    under = [f(f"over_under_{x:g}", "moins") for x in tot]
    ajoute("plus de X décroissant avec la ligne", all(over[i] >= over[i + 1] - tol for i in range(len(over) - 1)))
    ajoute("moins de X croissant avec la ligne", all(under[i] <= under[i + 1] + tol for i in range(len(under) - 1)))
    for q in ("domicile", "exterieur"):
        o = [f(f"over_under_{q}_{x:g}", "plus") for x in M.LIGNES_EQUIPE]
        ajoute(f"buts de l'équipe ({q}) : plus de X décroissant", all(o[i] >= o[i + 1] - tol for i in range(len(o) - 1)))
    ajoute("double chance cohérente avec le 1X2", k("double_chance", "1N") == k("1x2", "1") + k("1x2", "N") and k("double_chance", "N2") == k("1x2", "2") + k("1x2", "N")
           and k("double_chance", "12") == k("1x2", "1") + k("1x2", "2"))
    ajoute("scores exacts couvrent 100 % de la distribution", sum(m["k"] for m in a["marches"] if m["cle"][0] == "score_exact") == N)
    ajoute("aucune fréquence hors de [0 ; 1]", all(0 <= m["f"] <= 1 and all(x["f"] is None or 0 <= x["f"] <= 1 for x in m["niveaux"].values()) for m in a["marches"]))
    ajoute("aucun scénario compté deux fois (somme brute = N)", sum(h["brute"].values()) == N)
    n_niv = {t: sum(h[t].values()) for t in h}
    ajoute("paliers emboîtés : strict ≤ intermédiaire ≤ élargi ≤ brut, et élargi + incompatible = brut",
           n_niv["strict"] <= n_niv["intermediaire"] <= n_niv["elargi"] <= N and n_niv["elargi"] + n_niv["incompatible"] == N)
    for t in (*NIVEAUX,):
        if n_niv[t]:
            ok = sum(ms[("1x2", s)]["niveaux"][t]["k"] for s in ("1", "N", "2")) == n_niv[t]
            ajoute(f"1X2 totalise 100 % dans le palier {t}", ok)
    return res


# --- 12. Statut final ---------------------------------------------------------------------------------------------------
def decider(a: dict[str, Any], calib: dict[str, Any] | None, p: dict[str, Any]) -> None:
    """Statut et raison de CHAQUE marché (rien n'est effacé). retenu = fréquence robuste g ≥ seuil APPRIS du marché, cote ≥ cote minimale, jamais deux fois le même événement.
    Sans calibrage le moteur n'évalue rien (indice descriptif et expérimental, §9). « AUCUN MARCHÉ RETENU » est un résultat valable."""
    seuils = (calib or {}).get("seuils") or {}
    cote_min = (calib or {}).get("cote_min", p["cote_min"])
    candidats = []
    for m in a["marches"]:
        c = (m["cle"][0], m["cle"][1])
        s = seuils.get(M.cle_txt(c))
        m["seuil"] = s["seuil"] if s else None
        m["p_calibree"] = p_calibree(m["g"], s["tranches"], p["pas_tranche"]) if s else None
        if not calib:
            m["statut"], m["raison"], m["code"] = "non_evalue", "aucun calibrage : indice descriptif seulement", 7
        elif m["famille"] == "scores exacts":
            m["statut"], m["raison"], m["code"] = "rejete", "un score exact fréquent n'est jamais un pronostic retenu (§7)", 2
        elif not s or s["seuil"] is None:
            m["statut"], m["raison"], m["code"] = "rejete", "aucun seuil calibré : ce marché n'a jamais atteint 70 % de réussite sur l'archive", 0
        elif m["g"] < s["seuil"]:
            m["statut"], m["raison"], m["code"] = "rejete", f"fréquence robuste {m['g']:.0%} < seuil calibré {s['seuil']:.0%}", 1
        elif not m.get("cote"):
            m["statut"], m["raison"], m["code"] = "a_surveiller", "seuil atteint mais aucune cote disponible : pari injouable", 3
        elif m["cote"] < cote_min:
            m["statut"], m["raison"], m["code"] = "a_surveiller", f"seuil atteint mais cote {m['cote']:.2f} < {cote_min:.2f}".replace(".", ","), 4
        else:
            m["statut"], m["raison"], m["code"] = "retenu", "seuil atteint, cote jouable", 6
            candidats.append(m)
    candidats.sort(key=lambda m: (-(m["p_calibree"] or 0), -m["g"], -m["f"], M.cle_txt(tuple(m["cle"]))))
    vus: dict[bytes, str] = {}
    for m in candidats:
        e = M.evenement((m["cle"][0], m["cle"][1]))
        if e in vus:
            m["statut"], m["raison"], m["code"] = "a_surveiller", f"même événement que {vus[e]}", 5
        else:
            vus[e] = M.cle_txt((m["cle"][0], m["cle"][1]))
    a["retenus"] = [m for m in candidats if m["statut"] == "retenu"]


def selection(a: dict[str, Any]) -> dict[str, Any]:
    """Principal = le plus fiable (réussite réelle calibrée, puis fréquence robuste) ; autres = le reste, du plus au moins fiable. Aucun retenu = aucun pari."""
    r = a["retenus"]
    return {"principal": r[0] if r else None, "autres": r[1:], "raison": None if r else "AUCUN MARCHÉ RETENU"}


# --- 16.E Conclusion ---------------------------------------------------------------------------------------------------
def _nom(c: list[str]) -> str:
    """Nom lisible d'un marché (définition française, sans les équipes : la conclusion est gelée sans noms)."""
    t = Df.definition(c[0], c[1])[0]
    return t[:1].upper() + t[1:]


def conclure(a: dict[str, Any]) -> list[str]:
    """Phrases de la conclusion (§16.E), en clair. Descriptif : rien ici n'est une probabilité."""
    L = []
    ms = [m for m in a["marches"] if m["famille"] != "scores exacts"]
    certains = [m for m in ms if m["f"] in (0.0, 1.0)]
    top = sorted([m for m in ms if 0.0 < m["f"] < 1.0], key=lambda m: (-m["f"], M.cle_txt(tuple(m["cle"]))))[:3]
    L.append("Ce qui ressort le plus souvent (fréquence brute, hors marchés vrais ou faux dans tous les scénarios) : " + " ; ".join(f"{_nom(m['cle'])} {m['f']:.0%}" for m in top)
             + f" sur {a['combinaisons']} scénarios. {len(certains)} marché(s) sont vrais ou faux dans 100 % des scénarios (lignes extrêmes) : ils ne disent rien du match.")
    stables = [m for m in ms if m["f"] >= 0.5 and m["stabilite"]["amplitude"] == 0.0]
    L.append(f"Stable quand on retire une observation : {len(stables)} marché(s) au-dessus de 50 %.")
    fragiles = [m for m in ms if m["stabilite"]["dependance_unique"]]
    L.append(f"Dépend d'une seule observation : {len(fragiles)} marché(s).")
    contra = [m for m in ms if m["contradiction"]]
    L.append(f"Contradictions entre le brut et un palier défensif : {len(contra)} marché(s).")
    r = a["retenus"]
    surv = sum(1 for m in a["marches"] if m["statut"] == "a_surveiller")
    L.append("Retenu : " + (" ; ".join(_nom(m["cle"]) for m in r) if r else "AUCUN MARCHÉ RETENU") + (f" ; {surv} à surveiller." if surv else "."))
    return L


def empreinte(entrees: dict[str, Any], p: dict[str, Any]) -> str:
    """Empreinte des entrées et des réglages : deux analyses de même empreinte doivent être identiques (reproductibilité, §14.11)."""
    return hashlib.sha256(json.dumps([entrees, p], sort_keys=True).encode()).hexdigest()[:12]
