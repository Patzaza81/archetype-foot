"""Module 1 du moteur DC : les 44 paramètres de chaque équipe du championnat (spécification de Patrick, version corrigée).

Tout est calculé avec les seuls matchs du championnat STRICTEMENT antérieurs au jour du match (anti-fuite), saison courante.
Les 44 paramètres sont tous produits (tableau de bord et contrat 1.5) ; ceux qui entrent dans le Module 2 sont : Forme_PPM (34) et PPM (10)
pour la décroissance temporelle, IE (38) pour les buts attendus, Amplitude (31) et Score modal (32) pour ρ, Profil (41) pour l'ajustement
croisé, CBD/CBE (42-43) comme références. La force de chacun de ces effets est apprise hors échantillon (calibrage.py), jamais posée à la main.

Précisions rendues nécessaires par la spécification (aucune valeur choisie) :
- Forme_PPM : formule de Patrick [PPM(1..J-5) + 1,5 × PPM(5 derniers)] / 2,5. Avec J ≤ 5 la première partie n'existe pas (division par 0 ou
  négative dans la formule reçue) : Forme_PPM = PPM des matchs joués (aucune pondération possible).
- Amplitude : écart-type du total de buts des matchs de l'équipe (détecte les « valises »).
- Score modal : score (buts pour - buts contre) le plus fréquent ; égalité départagée par le moins de buts puis l'ordre du texte (déterministe).
- Volatilité : part des matchs consécutifs dont le résultat (V/N/D) change.
- xPts (37) : Poisson simple — buts attendus = constante du championnat au lieu × (attaque de l'équipe au lieu / constante) × (défense de
  l'adversaire à son lieu / constante) ; une moyenne sans match vaut la constante. IE = points réels / xPts.
- Profil (41) : seuils de Patrick IE > 1,2 = Opportuniste ; sinon attaque (buts marqués par match) et défense (buts encaissés par match)
  comparées à la MÉDIANE du championnat : Rouleau (attaque ≥ médiane, défense meilleure), Offensif fragile (attaque ≥, défense pire),
  Mur (attaque <, défense meilleure), Victime (attaque <, défense pire). Style_Tag : Defensive si buts impliqués sous la médiane,
  Offensive_Volatile si au-dessus ET amplitude au-dessus de la médiane, sinon Balanced.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import median, pstdev
from typing import Any

import numpy as np

PROFILS = {1: "Rouleau", 2: "Offensif fragile", 3: "Mur", 4: "Opportuniste", 5: "Victime"}
IE_GACHE, IE_OPPORTUNISTE = 0.8, 1.2          # seuils de lecture de Patrick (Module 1, paramètre 38)
SCORES_FAIBLES_NULS = ("0-0", "1-1")          # cases dont ρ règle la fréquence dans le même sens (τ = 1 − λλρ et 1 − ρ)
_K = 12                                       # buts considérés pour xPts (masse au-delà négligeable)


_KS = np.arange(_K + 1)
_LF = np.array([math.lgamma(k + 1) for k in _KS])
_INF = np.tril(np.ones((_K + 1, _K + 1)), -1)                # i > j


def _pmf_mat(lam: np.ndarray) -> np.ndarray:
    lam = np.maximum(lam, 1e-6)[:, None]
    return np.exp(_KS * np.log(lam) - lam - _LF)


def _points(bp: int, bc: int) -> int:
    return 3 if bp > bc else (1 if bp == bc else 0)


def _res(bp: int, bc: int) -> str:
    return "V" if bp > bc else ("N" if bp == bc else "D")


def score_modal(scores: list[tuple[int, int]]) -> str | None:
    if not scores:
        return None
    c = Counter(f"{x}-{y}" for x, y in scores)
    return sorted(c, key=lambda s: (-c[s], sum(map(int, s.split("-"))), s))[0]


def amplitude(scores: list[tuple[int, int]]) -> float | None:
    return float(pstdev([x + y for x, y in scores])) if len(scores) >= 2 else None


def forme_ppm(points: list[int]) -> float | None:
    """Points dans l'ordre chronologique."""
    j = len(points)
    if j == 0:
        return None
    if j <= 5:
        return sum(points) / j
    return (sum(points[:-5]) / (j - 5) + 1.5 * sum(points[-5:]) / 5) / 2.5


def _stats(liste: list[dict]) -> dict[str, Any]:
    """Statistiques d'une liste de matchs vus par l'équipe : {bp, bc, ...}, ordre chronologique."""
    j = len(liste)
    if j == 0:
        return {"J": 0}
    bp = sum(m["bp"] for m in liste)
    bc = sum(m["bc"] for m in liste)
    v = sum(m["bp"] > m["bc"] for m in liste)
    n = sum(m["bp"] == m["bc"] for m in liste)
    pts = [_points(m["bp"], m["bc"]) for m in liste]
    sc = [(m["bp"], m["bc"]) for m in liste]
    return {"J": j, "V": v, "N": n, "D": j - v - n, "BP": bp, "BC": bc, "Pts": sum(pts), "PPM": sum(pts) / j, "MBM": bp / j, "MBE": bc / j,
            "TV": v / j, "TN": n / j, "TD": (j - v - n) / j, "MBI": (bp + bc) / j, "amplitude": amplitude(sc), "score_modal": score_modal(sc),
            "forme_ppm": forme_ppm(pts), "points_liste": pts}


def tableau(matchs: list[dict], jour: str) -> dict[str, Any]:
    """Les 44 paramètres de chaque équipe + constantes du championnat, avec les matchs strictement antérieurs à `jour`.
    Retour : {"equipes": {nom: params}, "ligue": {...}}."""
    passe = sorted((m for m in matchs if m["date"] < jour and m.get("h") is not None), key=lambda m: m["date"])
    vues: dict[str, list[dict]] = defaultdict(list)
    for m in passe:
        vues[m["dom"]].append({"date": m["date"], "dom": True, "bp": m["h"], "bc": m["a"], "adv": m["ext"]})
        vues[m["ext"]].append({"date": m["date"], "dom": False, "bp": m["a"], "bc": m["h"], "adv": m["dom"]})
    nd = len(passe)
    cbd = sum(m["h"] for m in passe) / nd if nd else None
    cbe = sum(m["a"] for m in passe) / nd if nd else None
    tot = [m["h"] + m["a"] for m in passe]
    ligue = {"matchs": nd, "CBD": cbd, "CBE": cbe, "moyenne_buts": (sum(tot) / nd) if nd else None,
             "amplitude": float(pstdev(tot)) if nd >= 2 else None}
    st = {e: _stats(l) for e, l in vues.items()}
    lieu = {e: {"dom": _stats([x for x in l if x["dom"]]), "ext": _stats([x for x in l if not x["dom"]])} for e, l in vues.items()}

    # xPts (Poisson simple) et IE, global et par lieu
    def attendu(e: str, dom: bool, adv: str) -> tuple[float, float]:
        sd = lieu[e]["dom" if dom else "ext"]
        sa = lieu[adv]["ext" if dom else "dom"]
        cb_pour, cb_contre = (cbd, cbe) if dom else (cbe, cbd)
        att = (sd["MBM"] / cb_pour) if sd["J"] and cb_pour else 1.0
        dfa = (sa["MBE"] / cb_pour) if sa["J"] and cb_pour else 1.0
        att_adv = (sa["MBM"] / cb_contre) if sa["J"] and cb_contre else 1.0
        dfe = (sd["MBE"] / cb_contre) if sd["J"] and cb_contre else 1.0
        return (cb_pour or 0.0) * att * dfa, (cb_contre or 0.0) * att_adv * dfe

    xpts: dict[str, dict[str, float]] = {}
    lignes = [(e, x["dom"], *attendu(e, x["dom"], x["adv"])) for e, l in vues.items() for x in l]
    if lignes:
        lp = np.array([q[2] for q in lignes])
        lc = np.array([q[3] for q in lignes])
        pp, pc = _pmf_mat(lp), _pmf_mat(lc)
        pv = np.einsum("ni,nj,ij->n", pp, pc, _INF)          # P(buts pour > buts contre)
        pn = np.einsum("ni,ni->n", pp, pc)
        xp = 3 * pv + pn
        for (e, dom, _, _), v in zip(lignes, xp):
            acc = xpts.setdefault(e, {"tout": 0.0, "dom": 0.0, "ext": 0.0})
            acc["tout"] += float(v)
            acc["dom" if dom else "ext"] += float(v)

    def ie(pts: int, xp: float) -> float | None:
        return pts / xp if xp > 0 else None

    rad_ligue = (sum(s["BP"] for s in st.values()) / max(sum(s["BC"] for s in st.values()), 1)) if st else None
    med = {k: median([s[k] for s in st.values()]) for k in ("MBM", "MBE", "MBI")} if st else {}
    amps = [s["amplitude"] for s in st.values() if s["amplitude"] is not None]
    med_amp = median(amps) if amps else None
    classement = sorted(st, key=lambda e: (-st[e]["Pts"], -(st[e]["BP"] - st[e]["BC"]), -st[e]["BP"], e))
    rang = {e: k + 1 for k, e in enumerate(classement)}

    def rangs(cle: str, decroissant: bool) -> dict[str, int]:
        o = sorted(st, key=lambda e: ((-st[e][cle] if decroissant else st[e][cle]), e))
        return {e: k + 1 for k, e in enumerate(o)}

    r_att, r_def, r_forme, r_ppm = rangs("MBM", True), rangs("MBE", False), None, rangs("PPM", True)
    r_forme = {e: k + 1 for k, e in enumerate(sorted(st, key=lambda e: (-(st[e]["forme_ppm"] or 0), e)))}

    out: dict[str, dict[str, Any]] = {}
    for e, s in st.items():
        l = vues[e]
        res = [_res(x["bp"], x["bc"]) for x in l]
        streak = 0
        for r in reversed(res):
            if r == "D":
                break
            streak += 1
        serie = 1
        for r in reversed(res[:-1]):
            if r != res[-1]:
                break
            serie += 1
        vol = sum(a != b for a, b in zip(res, res[1:])) / (len(res) - 1) if len(res) > 1 else None
        ie_t = ie(s["Pts"], xpts[e]["tout"])
        if ie_t is not None and ie_t > IE_OPPORTUNISTE:
            profil = 4
        elif s["MBM"] >= med["MBM"]:
            profil = 1 if s["MBE"] < med["MBE"] else 2
        else:
            profil = 3 if s["MBE"] < med["MBE"] else 5
        if s["MBI"] < med["MBI"]:
            style = "Defensive"
        elif med_amp is not None and s["amplitude"] is not None and s["MBI"] > med["MBI"] and s["amplitude"] > med_amp:
            style = "Offensive_Volatile"
        else:
            style = "Balanced"
        sd, se = lieu[e]["dom"], lieu[e]["ext"]
        j = s["J"]
        p = {
            # bloc 1
            "position": rang[e], "Pts": s["Pts"], "J": j, "V": s["V"], "N": s["N"], "D": s["D"], "BP": s["BP"], "BC": s["BC"], "Diff": s["BP"] - s["BC"],
            # bloc 2
            "PPM": s["PPM"], "MBM": s["MBM"], "MBE": s["MBE"], "TV": s["TV"], "TN": s["TN"], "TD": s["TD"], "MBI": s["MBI"],
            "RD": (s["BP"] - s["BC"]) / j, "RAD": (s["BP"] / s["BC"]) if s["BC"] else rad_ligue,
            # bloc 3
            "J_dom": sd["J"], "J_ext": se["J"],
            "MBM_dom": sd.get("MBM"), "MBE_dom": sd.get("MBE"), "MBM_ext": se.get("MBM"), "MBE_ext": se.get("MBE"),
            "TV_dom": sd.get("TV"), "TV_ext": se.get("TV"), "TN_dom": sd.get("TN"), "TN_ext": se.get("TN"), "TD_dom": sd.get("TD"), "TD_ext": se.get("TD"),
            # bloc 4
            "clean_sheet": sum(x["bc"] == 0 for x in l) / j, "fts": sum(x["bp"] == 0 for x in l) / j,
            "plus_2_buts": sum(x["bp"] + x["bc"] >= 3 for x in l) / j, "moins_3_buts": sum(x["bp"] + x["bc"] <= 2 for x in l) / j,
            "btts": sum(x["bp"] >= 1 and x["bc"] >= 1 for x in l) / j, "amplitude": s["amplitude"], "score_modal": s["score_modal"],
            "amplitude_dom": sd.get("amplitude"), "amplitude_ext": se.get("amplitude"),
            "score_modal_dom": sd.get("score_modal"), "score_modal_ext": se.get("score_modal"),
            # bloc 5
            "points_totaux": s["Pts"], "forme_ppm": s["forme_ppm"], "forme_ppm_dom": sd.get("forme_ppm"), "forme_ppm_ext": se.get("forme_ppm"),
            "PPM_dom": sd.get("PPM"), "PPM_ext": se.get("PPM"),
            "streak_sans_defaite": streak, "serie": f"{serie}{res[-1]}", "volatilite": vol,
            # bloc 6
            "xPts": xpts[e]["tout"], "IE": ie_t, "IE_dom": ie(sd.get("Pts", 0), xpts[e]["dom"]), "IE_ext": ie(se.get("Pts", 0), xpts[e]["ext"]),
            "RC": (s["BP"] / s["Pts"]) if s["Pts"] else None,
            "rangs": {"classement": rang[e], "attaque": r_att[e], "defense": r_def[e], "forme": r_forme[e], "ppm": r_ppm[e]},
            "profil_id": profil, "profil": PROFILS[profil], "style_tag": style,
            # bloc 7
            "CBD": cbd, "CBE": cbe,
        }
        out[e] = p
    return {"equipes": out, "ligue": ligue, "jour": jour}


def gap(t: dict[str, Any], a: str, b: str) -> int | None:
    """Paramètre 44 : écart de points au classement entre A et B."""
    pa, pb = t["equipes"].get(a), t["equipes"].get(b)
    return (pa["Pts"] - pb["Pts"]) if pa and pb else None


def historique_lieu(matchs: list[dict], equipe: str, domicile: bool, jour: str, t: dict[str, Any]) -> list[dict[str, Any]]:
    """Historique chronologique au lieu (contrat 1.5) : date, adversaire, son style et son profil (au jour du match), buts pour / contre."""
    out = []
    for m in sorted((m for m in matchs if m["date"] < jour and m.get("h") is not None and m["dom" if domicile else "ext"] == equipe),
                    key=lambda m: m["date"]):
        adv = m["ext"] if domicile else m["dom"]
        pa = t["equipes"].get(adv) or {}
        out.append({"date": m["date"], "adversaire": adv, "adversaire_style": pa.get("style_tag"), "adversaire_profil": pa.get("profil_id"),
                    "buts_pour": m["h"] if domicile else m["a"], "buts_contre": m["a"] if domicile else m["h"]})
    return out
