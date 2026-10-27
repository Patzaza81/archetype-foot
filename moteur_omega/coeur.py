"""Cœur du moteur omega : analyse complète d'un match.

Quatre rôles séparés (cahier des charges, section 13) :
1. CROISEMENTS : décrivent les confrontations (attaque A × attaque B, défense A × défense B, attaque A × défense B, attaque B × défense A).
2. SCÉNARIO CONTRADICTOIRE : teste la résistance de chaque marché. Valeurs prises dans les échantillons réels des deux équipes (aucune valeur
   inventée) : buts candidats = (buts marqués par l'équipe + buts encaissés par l'adversaire) / 2, avec les extrêmes observés défavorables au
   marché (ex. Plus de 1,5 : plus faible attaque de chaque équipe × plus faible nombre de buts encaissés par l'adversaire). Lecture en buts
   entiers : le marché ne résiste que si tous les scores entiers possibles du scénario le font gagner. C'est un test, pas une probabilité.
3. POISSON / DIXON-COLES : probabilité de chaque marché, calibrée sur l'historique (`calibrage.py`).
4. SÉLECTION : probabilité calibrée >= seuil, cote BetPawa connue >= 1,25 ; accord avec la cote (la probabilité annoncée par BetPawa,
   marge retirée, atteint aussi le seuil) et filtres de résistance et de stabilité seulement si le calibrage a montré qu'ils apportent
   quelque chose hors échantillon (`parametres.json` → `selection`). Probabilité retenue = la plus prudente des deux (modèle, cote).
"""
from __future__ import annotations

import statistics
from typing import Any

import numpy as np

from . import marches as M
from . import modele as MO
from .donnees import References, MIN_MATCHS

COTE_MIN = 1.25                    # règle de Patrick (tous les moteurs) : aucun pronostic proposé sous 1,25


# --- 1. Croisements -------------------------------------------------------------------------------------------------
def _resume(v: list[int]) -> dict[str, Any]:
    return {"valeurs": list(v), "moyenne": round(statistics.fmean(v), 3) if v else None, "min": min(v) if v else None,
            "max": max(v) if v else None, "ecart_type": round(statistics.pstdev(v), 3) if len(v) > 1 else 0.0}


def croisements(s: dict[str, list[int]]) -> dict[str, Any]:
    gfa, gaa, gfb, gab = s["dom_marques"], s["dom_encaisses"], s["ext_marques"], s["ext_encaisses"]
    out = {
        "attaque_dom_x_attaque_ext": {"dom": _resume(gfa), "ext": _resume(gfb), "role": "descriptif"},
        "defense_dom_x_defense_ext": {"dom": _resume(gaa), "ext": _resume(gab), "role": "descriptif"},
        "attaque_dom_x_defense_ext": {"attaque": _resume(gfa), "defense": _resume(gab),
                                      "buts_candidats": round((statistics.fmean(gfa) + statistics.fmean(gab)) / 2, 3)},
        "attaque_ext_x_defense_dom": {"attaque": _resume(gfb), "defense": _resume(gaa),
                                      "buts_candidats": round((statistics.fmean(gfb) + statistics.fmean(gaa)) / 2, 3)},
    }
    sens_attaque = np.sign(statistics.fmean(gfa) - statistics.fmean(gfb))      # qui marque le plus
    sens_defense = np.sign(statistics.fmean(gab) - statistics.fmean(gaa))      # qui laisse le plus marquer l'adversaire
    out["convergence"] = {"sens_attaques": int(sens_attaque), "sens_defenses": int(sens_defense),
                          "convergent": bool(sens_attaque == sens_defense and sens_attaque != 0),
                          "ecart_dom": round(abs(statistics.fmean(gfa) - statistics.fmean(gab)), 3),
                          "ecart_ext": round(abs(statistics.fmean(gfb) - statistics.fmean(gaa)), 3)}
    return out


# --- 2. Scénario contradictoire --------------------------------------------------------------------------------------
def coins(s: dict[str, list[int]]) -> dict[str, float]:
    """Buts candidats extrêmes de chaque équipe, à partir des valeurs réellement observées dans les deux échantillons."""
    return {"dom_bas": (min(s["dom_marques"]) + min(s["ext_encaisses"])) / 2, "dom_haut": (max(s["dom_marques"]) + max(s["ext_encaisses"])) / 2,
            "ext_bas": (min(s["ext_marques"]) + min(s["dom_encaisses"])) / 2, "ext_haut": (max(s["ext_marques"]) + max(s["dom_encaisses"])) / 2}


_SENS: dict[M.Cle, tuple[str | None, str | None]] = {}


def sens_defavorable(cle: M.Cle) -> tuple[str | None, str | None]:
    """Côté défavorable au marché pour chaque équipe : « bas » si le marché aime que l'équipe marque, « haut » s'il aime qu'elle marque peu,
    None si le marché n'est pas monotone (match nul, pas de nul) : alors les quatre combinaisons extrêmes sont testées."""
    if cle not in _SENS:
        t = M.test_du_marche(*cle)
        r = range(7)

        def sens(axe: int) -> str | None:
            croit = all(not t(i, j) or t(i + (axe == 0), j + (axe == 1)) for i in r for j in r)
            decroit = all(not t(i + (axe == 0), j + (axe == 1)) or t(i, j) for i in r for j in r)
            if croit and decroit:
                return "neutre"
            return "bas" if croit else "haut" if decroit else None
        _SENS[cle] = (sens(0), sens(1))
    return _SENS[cle]


def scenario_contradictoire(cle: M.Cle, c: dict[str, float]) -> dict[str, Any]:
    t = M.test_du_marche(*cle)
    sd, se = sens_defavorable(cle)
    tous = [(a, b) for a in ("bas", "haut") for b in ("bas", "haut")]
    a_tester = [(a, b) for a, b in tous if sd in (None, "neutre", a) and se in (None, "neutre", b)]
    if sd not in (None, "neutre") and se not in (None, "neutre"):
        a_tester = [(sd, se)]
    for a, b in a_tester:
        x, y = c[f"dom_{a}"], c[f"ext_{b}"]
        if not M.tient_en_buts_entiers(t, x, y):
            return {"statut": "FRAGILE", "dom": x, "ext": y, "cote_dom": a, "cote_ext": b}
    a, b = a_tester[0]
    return {"statut": "RESISTE", "dom": c[f"dom_{a}"], "ext": c[f"ext_{b}"], "cote_dom": a, "cote_ext": b}


# --- 3. Probabilités ---------------------------------------------------------------------------------------------------
def _probas_series(s: dict[str, list[int]], ref_dom: float, ref_ext: float, p: dict[str, Any], cles: list[M.Cle]) -> tuple[np.ndarray, float, float, np.ndarray]:
    la, lb = MO.buts_attendus(s, ref_dom, ref_ext, p)
    g = MO.grilles(np.array([la]), np.array([lb]), p["rho"])
    brut = MO.probas(g, cles)[0]
    cal = np.array([MO.calibrer(brut[k], (p.get("calibration") or {}).get("|".join(c))) for k, c in enumerate(cles)])
    return cal, la, lb, (brut, g[0])


def stabilite(s: dict[str, list[int]], ref_dom: float, ref_ext: float, p: dict[str, Any], cles: list[M.Cle]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Retrait successif de chaque match (un à la fois, dans chaque échantillon) : probabilités calibrées minimales et maximales, et
    nombre de retraits qui font passer le scénario contradictoire de RESISTE à FRAGILE (ou l'inverse)."""
    vals = []
    bascules = np.zeros(len(cles))
    base = [scenario_contradictoire(c, coins(s))["statut"] for c in cles]
    for cote in ("dom", "ext"):
        n = len(s[f"{cote}_marques"])
        for k in range(n):
            s2 = {kk: list(v) for kk, v in s.items()}
            del s2[f"{cote}_marques"][k]
            del s2[f"{cote}_encaisses"][k]
            vals.append(_probas_series(s2, ref_dom, ref_ext, p, cles)[0])
            cc = coins(s2)
            bascules += np.array([scenario_contradictoire(c, cc)["statut"] != base[i] for i, c in enumerate(cles)])
    v = np.array(vals)
    return v.min(axis=0), v.max(axis=0), bascules


# --- 4. Analyse et sélection -------------------------------------------------------------------------------------------
def cote_de(cotes: dict | None, cle: M.Cle) -> float | None:
    v = ((cotes or {}).get(cle[0]) or {}).get(cle[1])
    return float(v) if isinstance(v, (int, float)) and v > 1 else None


def _valides(groupe: dict | None) -> dict[str, float]:
    return {k: float(v) for k, v in (groupe or {}).items() if isinstance(v, (int, float)) and v > 1}


def proba_cote(cotes: dict | None, cle: M.Cle) -> float | None:
    """Probabilité annoncée par la cote BetPawa, marge du bookmaker retirée en normalisant les issues du même marché :
    1X2 (3 issues -> somme 1), double chance (somme 2), marchés à 2 issues (paire -> somme 1), combinés 1X2 (6 issues -> somme 1),
    combinés double chance (paire plus/moins ou oui/non ramenée à la probabilité de la double chance). Issues incomplètes : None (rien deviné)."""
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


def analyser(m: dict[str, Any], refs: References, p: dict[str, Any], cles: list[M.Cle] | None = None, avec_stabilite: bool = True) -> dict[str, Any]:
    cles = cles or M.catalogue()
    s = MO.series(m, p["fenetre"])
    fiche = {"id": m["id"], "jour": m["jour"], "domicile": m["domicile"], "exterieur": m["exterieur"],
             "n_domicile": len(s["dom_marques"]), "n_exterieur": len(s["ext_marques"])}
    if not MO.admissible(s):
        return {**fiche, "statut": "exclu", "raison": f"moins de {MIN_MATCHS} matchs au même lieu pour une des deux équipes"}
    ref_dom, ref_ext, n_ligue = MO.reference(refs, m, p)
    cal, la, lb, (brut, grille) = _probas_series(s, ref_dom, ref_ext, p, cles)
    c = coins(s)
    if avec_stabilite:
        pmin, pmax, bascules = stabilite(s, ref_dom, ref_ext, p, cles)
    else:
        pmin = pmax = cal
        bascules = np.zeros(len(cles))
    lignes = []
    for k, cle in enumerate(cles):
        sc = scenario_contradictoire(cle, c)
        cote = cote_de(m.get("cotes"), cle)
        pc = proba_cote(m.get("cotes"), cle)
        lignes.append({"cle": list(cle), "marche": M.libelle(cle), "onglet": M.onglet(cle), "famille": M.famille(cle),
                       "valeur_reelle": M.valeur_reelle(cle), "p_brut": float(brut[k]), "p": float(cal[k]),
                       "p_min": float(pmin[k]), "p_max": float(pmax[k]), "bascules_scenario": int(bascules[k]),
                       "resistance": sc["statut"], "scenario": {"dom": sc["dom"], "ext": sc["ext"]},
                       "cote": cote, "p_cote": pc, "p_retenue": float(min(cal[k], pc)) if pc is not None else None})
    top = sorted(((float(grille[i, j]), i, j) for i in range(5) for j in range(5)), reverse=True)[:5]
    return {**fiche, "statut": "analyse", "series": s, "croisements": croisements(s), "coins": c,
            "buts_attendus": {"dom": la, "ext": lb}, "reference_ligue": {"dom": ref_dom, "ext": ref_ext, "matchs": n_ligue},
            "scores_probables": [{"score": f"{i}-{j}", "p": round(q, 4)} for q, i, j in top], "marches": lignes}


def retenu(l: dict[str, Any], sel: dict[str, Any]) -> tuple[bool, str]:
    """Règle de sélection d'un marché (paramètres appris dans `selection`)."""
    if l["cote"] is None:
        return False, "cote BetPawa inconnue"
    if l["cote"] < COTE_MIN:
        return False, f"cote {l['cote']:g} sous 1,25"
    if l["p"] < sel["seuil"]:
        return False, f"probabilité du modèle {l['p']:.0%} sous le seuil {sel['seuil']:.0%}"
    if sel.get("exiger_accord_cote"):
        if l.get("p_cote") is None:
            return False, "probabilité de la cote illisible (issues du marché incomplètes)"
        if l["p_cote"] < sel["seuil"]:
            return False, f"la cote BetPawa n'annonce que {l['p_cote']:.0%} (sous {sel['seuil']:.0%})"
    if sel.get("exiger_resistance") and l["resistance"] != "RESISTE":
        return False, "ne résiste pas au scénario contradictoire"
    if sel.get("exiger_stabilite") and l["p_min"] < sel["seuil"]:
        return False, f"instable : tombe à {l['p_min']:.0%} si on retire un match"
    return True, "retenu"


def selectionner(a: dict[str, Any], sel: dict[str, Any]) -> dict[str, Any]:
    """Principal = marché retenu le plus probable ; autres = marchés retenus restants. Jamais deux fois le même événement."""
    if a["statut"] != "analyse":
        return {"principal": None, "autres": [], "raison": a.get("raison")}
    ok, vus = [], {}
    for l in a["marches"]:
        bon, raison = retenu(l, sel)
        l["decision"] = raison
        if bon:
            ok.append(l)
    ok.sort(key=lambda l: (-(l["p_retenue"] if l.get("p_retenue") is not None else l["p"]), -(l["cote"] or 0)))
    garde = []
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
