"""Cœur du moteur DC : ajustement du championnat, probabilités de tous les marchés, preuves empiriques, sélection.

Corrections de l'audit du 30/10/2026 (modules reçus) mises en œuvre ici :
- probabilités = grille Dixon-Coles du championnat entier (modele.py), marchés par somme exacte des cases ;
- la fréquence observée p̂ est lue sur les matchs RÉELS au même lieu des deux équipes (domicile de A, extérieur de B, score orienté pour que
  « 1 » veuille dire la même chose dans les deux séries) ; elle sert de PREUVE affichée (avec la base du championnat et un Z), jamais de filtre
  tant qu'un filtre n'a pas fait ses preuves hors échantillon ;
- la calibration est apprise (isotone par marché), l'erreur de calibration se mesure par tranche (calibrage.py), pas par |P − Y| ;
- aucune cote dans l'analyse : la cote ne sert qu'à choisir parmi les marchés (règle de Patrick). Cote minimale 1,39 imposée par lui (27/10/2026) ;
- pas de mise (Kelly) : le moteur ne cherche pas à battre la cote.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from . import donnees as D, marches as M, modele as MO

COTE_MIN = 1.39                       # ordre de Patrick (27/10/2026) : jamais moins ; seule valeur posée à la main
CLES: list[M.Cle] = M.catalogue()
TESTS = {c: M.test_du_marche(*c) for c in CLES}
MASQUES = np.stack([MO.masque(c, TESTS[c]) for c in CLES])        # (marchés, 11, 11)


def cle_txt(c: M.Cle) -> str:
    return f"{c[0]}|{c[1]}"


def cote_de(cotes: dict | None, cle: M.Cle) -> float | None:
    v = ((cotes or {}).get(cle[0]) or {}).get(cle[1])
    return float(v) if isinstance(v, (int, float)) and v > 1 else None


def _valides(groupe: dict | None) -> dict[str, float]:
    return {k: float(v) for k, v in (groupe or {}).items() if isinstance(v, (int, float)) and v > 1}


def proba_cote(cotes: dict | None, cle: M.Cle) -> float | None:
    """Probabilité annoncée par la cote, marge retirée en normalisant les issues du même marché ; issues incomplètes : None (rien deviné)."""
    g, s = cle
    vals = _valides((cotes or {}).get(g))
    c = vals.get(s)
    if c is None:
        return None
    inv = lambda x: 1.0 / x
    if g == "1x2":
        return inv(c) / sum(map(inv, vals.values())) if len(vals) == 3 else None
    if g == "double_chance":
        return 2 * inv(c) / sum(map(inv, vals.values())) if len(vals) == 3 else None
    if "|" in s:
        a = s.split("|", 1)[0]
        if g.startswith("1x2_"):
            return inv(c) / sum(map(inv, vals.values())) if len(vals) == 6 else None
        dc = _valides((cotes or {}).get("double_chance"))
        paire = [v for k, v in vals.items() if k.startswith(a + "|")]
        if len(paire) == 2 and len(dc) == 3:
            return inv(c) / sum(map(inv, paire)) * 2 * inv(dc[a]) / sum(map(inv, dc.values()))
        return None
    return inv(c) / sum(map(inv, vals.values())) if len(vals) == 2 else None


# --- Ajustement ---------------------------------------------------------------------------------------------------
def ajuster_ligue(matchs: list[dict], jour: str, sigma: float, xi: float, rho: float | None = None, depart: MO.Ajustement | None = None) -> MO.Ajustement | None:
    """Ajustement du championnat avec les seuls matchs STRICTEMENT antérieurs à `jour` (anti-fuite). None s'il n'y en a aucun."""
    tr = [m for m in matchs if m["date"] < jour]
    if not tr:
        return None
    return MO.ajuster([m["dom"] for m in tr], [m["ext"] for m in tr], np.array([m["h"] for m in tr]), np.array([m["a"] for m in tr]),
                      np.array([D.jours(m["date"], jour) for m in tr]), sigma, xi, depart, rho)


def probas_grille(fit: MO.Ajustement, dom: str, ext: str) -> tuple[np.ndarray, np.ndarray, float, float]:
    lh, la = fit.lambdas(dom, ext)
    g = MO.grille(lh, la, fit.rho)
    return np.einsum("ij,kij->k", g, MASQUES), g, lh, la


# --- Preuve empirique (descriptive) -------------------------------------------------------------------------------
def preuve(matchs: list[dict], dom: str, ext: str, jour: str, test, base: float | None) -> dict[str, Any] | None:
    """p̂ = fréquence observée du marché sur les matchs au même lieu des deux équipes : A à domicile (score marqués-encaissés), B à l'extérieur
    (score encaissés-marqués, donc « domicile gagne » veut dire la même chose dans les deux séries). n = nombre de matchs (essais), k = réussites.
    Z compare p̂ à la base du championnat (information : le test de significativité n'est pas un filtre)."""
    sa = [(m["h"], m["a"]) for m in matchs if m["dom"] == dom and m["date"] < jour]
    sb = [(m["h"], m["a"]) for m in matchs if m["ext"] == ext and m["date"] < jour]
    n = len(sa) + len(sb)
    if n == 0:
        return None
    k = sum(bool(test(i, j)) for i, j in sa + sb)
    ph = k / n
    z = (ph - base) / math.sqrt(base * (1 - base) / n) if base and 0 < base < 1 else None
    return {"k": k, "n": n, "p_hat": round(ph, 4), "z": round(z, 2) if z is not None else None}


def analyser(m: dict[str, Any], matchs: list[dict], p: dict[str, Any], fit: MO.Ajustement | None = None) -> dict[str, Any]:
    """Analyse d'un match. `matchs` = matchs du championnat ; `p` = paramètres appris (parametres.json)."""
    fiche = {"id": m["id"], "jour": m["jour"], "domicile": m["domicile"], "exterieur": m["exterieur"]}
    nd = D.nb_matchs_lieu(matchs, m["eq_dom"], True, m["jour"])
    ne = D.nb_matchs_lieu(matchs, m["eq_ext"], False, m["jour"])
    fiche.update(n_domicile=nd, n_exterieur=ne)
    if nd < D.MIN_MATCHS or ne < D.MIN_MATCHS:
        return {**fiche, "statut": "exclu", "raison": f"moins de {D.MIN_MATCHS} matchs au même lieu pour une des deux équipes"}
    fit = fit or ajuster_ligue(matchs, m["jour"], p["sigma"], p["xi"], p.get("rho"))
    brut, g, lh, la = probas_grille(fit, m["eq_dom"], m["eq_ext"])
    cal = np.array([float(MO.calibrer(brut[k], (p.get("calibration") or {}).get(cle_txt(c)))) for k, c in enumerate(CLES)])
    lignes = []
    for k, c in enumerate(CLES):
        base = (p.get("bases") or {}).get(cle_txt(c))
        cote = cote_de(m.get("cotes"), c)
        pc = proba_cote(m.get("cotes"), c)
        lignes.append({"cle": list(c), "marche": M.libelle(c), "famille": M.famille(c), "valeur_reelle": M.valeur_reelle(c),
                       "p_brut": float(brut[k]), "p": float(cal[k]), "base": base, "cote": cote, "p_cote": pc,
                       "preuve": preuve(matchs, m["eq_dom"], m["eq_ext"], m["jour"], TESTS[c], base)})
    top = sorted(((float(g[i, j]), i, j) for i in range(5) for j in range(5)), reverse=True)[:5]
    return {**fiche, "statut": "analyse", "buts_attendus": {"dom": lh, "ext": la},
            "modele": {"mu": fit.mu, "gamma": fit.gamma, "rho": fit.rho, "n_matchs_ligue": fit.n_matchs},
            "scores_probables": [{"score": f"{i}-{j}", "p": round(q, 4)} for q, i, j in top], "marches": lignes}


# --- Sélection ----------------------------------------------------------------------------------------------------
def retenu(l: dict[str, Any], sel: dict[str, Any]) -> tuple[bool, str]:
    if l["cote"] is None:
        return False, "cote BetPawa inconnue"
    cm = sel.get("cote_min", COTE_MIN)
    if l["cote"] < cm:
        return False, f"cote {l['cote']:g} sous {cm:g}".replace(".", ",")
    if l["p"] < sel["seuil"]:
        return False, f"probabilité {l['p']:.0%} sous le seuil {sel['seuil']:.0%}"
    if sel.get("exiger_accord_cote"):
        if l.get("p_cote") is None:
            return False, "probabilité de la cote illisible"
        if l["p_cote"] < sel["seuil"]:
            return False, f"la cote n'annonce que {l['p_cote']:.0%} (sous {sel['seuil']:.0%})"
    return True, "retenu"


def selectionner(a: dict[str, Any], sel: dict[str, Any]) -> dict[str, Any]:
    """Principal = marché retenu le plus probable ; autres = les autres marchés retenus ; jamais deux fois le même événement. Rien retenu : aucun pari."""
    if a["statut"] != "analyse":
        return {"principal": None, "autres": [], "raison": a.get("raison")}
    ok, vus, garde = [], {}, []
    for l in a["marches"]:
        bon, raison = retenu(l, sel)
        l["decision"] = raison
        if bon:
            ok.append(l)
    ok.sort(key=lambda l: (-(min(l["p"], l["p_cote"]) if sel.get("exiger_accord_cote") and l.get("p_cote") is not None else l["p"]), -(l["cote"] or 0)))
    for l in ok:
        sig = M.signature(tuple(l["cle"]))
        if sig in vus:
            l["decision"] = f"même événement que « {vus[sig]} »"
            continue
        vus[sig] = l["marche"]
        garde.append(l)
    if not garde:
        return {"principal": None, "autres": [], "raison": "aucun marché retenu"}
    return {"principal": garde[0], "autres": garde[1:], "raison": None}
