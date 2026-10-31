"""Cœur du moteur DC : enchaîne les modules de Patrick pour un match.

Module 1 (module1.py, 44 paramètres de chaque équipe) → Module 1.5 (contrat.py, match_input validé ; erreur = match exclu)
→ Module 2 (modele.py : Dixon-Coles pénalisé sur le championnat entier ; ajustements.py : Forme→xi, IE→λ, Amplitude/Score modal→ρ, Profil croisé→λ)
→ Module 3 (grille des scores, chaque marché = somme exacte de ses cases ; effectifs k/n et base du championnat)
→ Module 4 (selecteur.py). Module 5 (cotes, EV, Kelly) non branché : contraire à la règle du taux de réussite. La cote est seulement affichée.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from . import ajustements as AJ, contrat as C, donnees as D, marches as M, modele as MO, module1 as M1, selecteur as S

CLES: list[M.Cle] = M.catalogue()
TESTS = {c: M.test_du_marche(*c) for c in CLES}
MASQUES = np.stack([MO.masque(c, TESTS[c]) for c in CLES])        # (marchés, 11, 11)


def cle_txt(c: M.Cle) -> str:
    return f"{c[0]}|{c[1]}"


def cote_de(cotes: dict | None, cle: M.Cle) -> float | None:
    v = ((cotes or {}).get(cle[0]) or {}).get(cle[1])
    return float(v) if isinstance(v, (int, float)) and v > 1 else None


def comptes(scores: list[tuple[int, int]]) -> np.ndarray:
    g = np.zeros((MO.N_BUTS + 1, MO.N_BUTS + 1))
    for h, a in scores:
        g[min(h, MO.N_BUTS), min(a, MO.N_BUTS)] += 1
    return g


def bases_ligue(matchs: list[dict], jour: str) -> tuple[np.ndarray | None, int]:
    """Taux de base de chaque marché = fréquence dans le championnat cette saison, matchs strictement antérieurs au jour."""
    sc = [(m["h"], m["a"]) for m in matchs if m["date"] < jour and m.get("h") is not None]
    if not sc:
        return None, 0
    return np.einsum("ij,kij->k", comptes(sc), MASQUES) / len(sc), len(sc)


def effectifs(c: dict[str, Any]) -> tuple[np.ndarray, int]:
    """k par marché et n = matchs comparables : A à domicile (score pour-contre) + B à l'extérieur (score contre-pour : « 1 » = victoire du domicile)."""
    sc = [(x["buts_pour"], x["buts_contre"]) for x in c["equipe_domicile"]["historique_matchs_dom"]]
    sc += [(x["buts_contre"], x["buts_pour"]) for x in c["equipe_exterieur"]["historique_matchs_ext"]]
    return np.einsum("ij,kij->k", comptes(sc), MASQUES), len(sc)


# --- Ajustement ---------------------------------------------------------------------------------------------------
def ajuster_ligue(matchs: list[dict], jour: str, p: dict[str, Any], t: dict[str, Any] | None = None, depart: MO.Ajustement | None = None) -> MO.Ajustement | None:
    """Ajustement du championnat avec les seuls matchs STRICTEMENT antérieurs à `jour` ; xi modulé par la forme (Module 2)."""
    tr = [m for m in matchs if m["date"] < jour and m.get("h") is not None]
    if not tr:
        return None
    k = p.get("effets") or AJ.NEUTRES
    dom, ext = [m["dom"] for m in tr], [m["ext"] for m in tr]
    mult = None
    if k.get("forme"):
        t = t or M1.tableau(matchs, jour)
        mult = AJ.mult_xi(dom, ext, AJ.dynamique(t), k["forme"])
    return MO.ajuster(dom, ext, np.array([m["h"] for m in tr]), np.array([m["a"] for m in tr]), np.array([D.jours(m["date"], jour) for m in tr]),
                      p["sigma"], p["xi"], depart, p.get("rho"), mult)


# --- Analyse d'un match ---------------------------------------------------------------------------------------------
def analyser(m: dict[str, Any], matchs: list[dict], p: dict[str, Any], fit: MO.Ajustement | None = None, t: dict[str, Any] | None = None,
             bases: tuple | None = None) -> dict[str, Any]:
    """`matchs` = matchs du championnat ; `p` = paramètres appris (parametres.json) ; fit/t/bases = caches du jour (facultatifs)."""
    fiche = {"id": m["id"], "jour": m["jour"], "domicile": m["domicile"], "exterieur": m["exterieur"]}
    fiche.update(n_domicile=D.nb_matchs_lieu(matchs, m["eq_dom"], True, m["jour"]), n_exterieur=D.nb_matchs_lieu(matchs, m["eq_ext"], False, m["jour"]))
    t = t or M1.tableau(matchs, m["jour"])
    try:
        c = C.construire(matchs, m["eq_dom"], m["eq_ext"], m["jour"], t, m["id"])          # Module 1.5
    except ValueError as err:
        return {**fiche, "statut": "exclu", "raison": f"contrat 1.5 : {err}"}
    fit = fit or ajuster_ligue(matchs, m["jour"], p, t)
    k = p.get("effets") or AJ.NEUTRES
    lh0, la0 = fit.lambdas(m["eq_dom"], m["eq_ext"])
    exc = AJ.excedents(matchs, m["eq_dom"], m["eq_ext"], m["jour"], t, fit)
    f = AJ.facteurs(c, t, exc)
    lh, la, rho = AJ.appliquer(lh0, la0, fit.rho, f, k)
    g = MO.grille(lh, la, rho)
    P = np.einsum("ij,kij->k", g, MASQUES)                                             # Module 3
    base, n_ligue = bases or bases_ligue(matchs, m["jour"])
    K, n = effectifs(c)
    lignes = []
    for i, cl in enumerate(CLES):
        lignes.append({"cle": list(cl), "marche": M.libelle(cl), "famille": M.famille(cl), "valeur_reelle": M.valeur_reelle(cl),
                       "p": float(P[i]), "base": round(float(base[i]), 4) if base is not None else None, "cote": cote_de(m.get("cotes"), cl),
                       "preuve": {"k": int(K[i]), "n": n, "p_hat": round(float(K[i]) / n, 4)} if n else None})
    top = sorted(((float(g[i, j]), i, j) for i in range(6) for j in range(6)), reverse=True)[:5]
    eq = t["equipes"]
    return {**fiche, "statut": "analyse", "buts_attendus": {"dom": lh, "ext": la}, "buts_attendus_avant_effets": {"dom": lh0, "ext": la0},
            "modele": {"mu": fit.mu, "gamma": fit.gamma, "rho_commun": fit.rho, "rho": rho, "n_matchs_ligue": fit.n_matchs, "effets": k},
            "facteurs": {kk: round(v, 4) for kk, v in f.items()}, "excedents_profil": exc, "n_ligue": n_ligue,
            "contrat": c, "parametres_equipes": {"dom": eq[m["eq_dom"]], "ext": eq[m["eq_ext"]]},
            "scores_probables": [{"score": f"{i}-{j}", "p": round(q, 4)} for q, i, j in top], "marches": lignes, "p_marches": [round(float(x), 4) for x in P]}


def selectionner(a: dict[str, Any], p: dict[str, Any], emac: float | None = None) -> dict[str, Any]:
    return S.selectionner(a, p["emac"] if emac is None else emac, p.get("seuils_marche"))
