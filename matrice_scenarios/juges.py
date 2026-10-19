"""Phase finale « parieur professionnel » du moteur alpha : 5 juges déterministes -> pronostic validé / super marché / pas de pari.

Lecture seule, hors pipeline : n'écrit que `docs/juges_parametres.json`, `docs/juges_backtest.json` et `data/comportement/juges.json`.
Aucune IA : cinq contrôles en règles (rejouables sur l'archive). Les rôles viennent du conseil du 19/10/2026 :
  1. contrarien      : le scénario le plus coûteux (favori qui creuse l'écart, match qui s'ouvre, nul) fait-il perdre trop souvent ?
  2. premiers principes : après calibration réelle de la probabilité (Football-Data), la cote paie-t-elle ? (valeur > 0, seuil naturel)
  3. expansionniste  : aucun autre marché du même match n'est à la fois aussi sûr et mieux payé (non dominé)
  4. outsider        : une équipe muette, ou un score extrême des séries qui se reproduit, fait-il perdre trop souvent ?
  5. exécutant       : cote >= 1,26, marché lisible, cote cohérente avec la probabilité (pas de cote mal lue)
Règle de Patrick : un pari alpha non adapté n'est écarté que s'il est DANGEREUX (juge 1, 4 ou 5 en échec).
Aucun seuil posé à la main : seuils = quartile bas des pronostics principaux (juges 1 et 4) et 99e centile de l'écart
probabilité - 1/cote (juge 5), mesurés sur la 1re moitié des jours ; « super » = famille de marché au rendement réel positif
sur la 1re moitié (au moins 30 cas, minimum de support du projet) puis jugée sur la 2e, jamais vue.
Usage : python -m matrice_scenarios.juges backtest | page
"""
from __future__ import annotations

import gzip
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from . import comportement as C
from . import recalage as R
from . import scanner_marches as S
from .backtest_comportement import COTE_MIN, ROOT, historiques
from .page_comportement import PARAMS, charger_matchs, contredit_le_profil, cotes_fiables, evenement

PARAMETRES = ROOT / "docs" / "juges_parametres.json"
BACKTEST = ROOT / "docs" / "juges_backtest.json"
SORTIE = ROOT / "data" / "comportement" / "juges.json"
COMBINES = False          # combinés suspendus : leur cote Betpawa n'est pas collectée ; sans cote trouvée, le marché est suspendu (règle de Patrick)
SUPPORT_MIN = 30          # minimum de support du projet (docs/MATRICE_SCENARIOS.md)
JUGES = ("contrarien", "premiers_principes", "expansionniste", "outsider", "executant")


# ---------------------------------------------------------------- scénarios et survie

def scenarios(prof: dict[str, Any]) -> dict[str, np.ndarray]:
    """Scénarios de match, en masques sur la grille de scores (i = buts domicile, j = buts extérieur)."""
    n = len(prof["grille"])
    i, j = np.meshgrid(range(n), range(n), indexing="ij")
    f = prof["favori"]
    ecart = (i - j >= 2) if f == "domicile" else ((j - i >= 2) if f == "extérieur" else (abs(i - j) >= 2))
    out = {
        "favori_creuse": ecart,
        "match_s_ouvre": i + j >= round(prof["total_attendu"]) + 2,     # deux buts de plus que prévu
        "nul": i == j,
        "equipe_muette": (i == 0) | (j == 0),
    }
    if prof["scores_extremes"]:                                          # seulement si les séries en montrent un (définition de C.profil)
        out["score_extreme"] = (i >= 5) | (j >= 5) | (abs(i - j) >= 4)
    return out


def masque_du_marche(groupe: str, selection: str, n: int) -> np.ndarray | None:
    t = S.test_du_marche(groupe, selection)
    if t is None:
        return None
    return np.array([[bool(t(i, j)) for j in range(n)] for i in range(n)])


def masse_perte(grille: np.ndarray, gagne: np.ndarray, scen: np.ndarray) -> float:
    """Probabilité de PERDRE à cause du scénario (le scénario se produit ET le pari perd) : vraisemblance du scénario x perte.
    (La survie conditionnelle valait 0 pour tout « moins de » quand le match s'ouvre : elle ne départageait rien.)"""
    return float((grille * scen * ~gagne).sum())


def test_combine(groupe: str, selection: str):
    """Marchés COMBINÉS de Betpawa (lus par parse_combines_betpawa.py) : « 1N|plus » = double chance 1N ET plus de la ligne, etc."""
    import re
    m = re.fullmatch(r"(dc|1x2)_(total_(\d+\.5)|btts)", groupe)
    if not m or "|" not in selection:
        return None
    issue, autre = selection.split("|", 1)
    r = {"dc": {"1N": lambda i, j: i >= j, "N2": lambda i, j: i <= j, "12": lambda i, j: i != j},
         "1x2": {"1": lambda i, j: i > j, "N": lambda i, j: i == j, "2": lambda i, j: i < j}}[m.group(1)].get(issue)
    if r is None:
        return None
    if m.group(3):
        if autre not in ("plus", "moins"):
            return None
        ligne = float(m.group(3))
        return lambda i, j: r(i, j) and ((i + j > ligne) if autre == "plus" else (i + j < ligne))
    if autre not in ("Oui", "Non"):
        return None
    return lambda i, j: r(i, j) and ((i >= 1 and j >= 1) if autre == "Oui" else (i == 0 or j == 0))


def libelle_combine(groupe: str, selection: str) -> str:
    issue, autre = selection.split("|", 1)
    nom = {"1N": "Domicile ne perd pas", "N2": "Extérieur ne perd pas", "12": "Pas de nul", "1": "Victoire domicile", "N": "Match nul", "2": "Victoire extérieur"}[issue]
    if "total" in groupe:
        return f"{nom} + {'plus' if autre == 'plus' else 'moins'} de {groupe.split('_')[-1].replace('.', ',')} buts"
    return f"{nom} + les deux marquent : {'oui' if autre == 'Oui' else 'non'}"


# ---------------------------------------------------------------- préparation d'un match

def preparer(m: dict[str, Any], courbes: dict[str, list]) -> dict[str, Any] | None:
    """Mêmes filtres qu'alpha (page_comportement.analyser_match), puis scores des juges pour chaque marché coté >= 1,26."""
    a = m.get("assemblage") or {}
    if "matchs" not in (a.get("equipe_dom") or {}) or "matchs" not in (a.get("equipe_ext") or {}):
        return None
    h = historiques(a["equipe_dom"], a["equipe_ext"], m["date"])
    if not h or not m.get("cotes_betpawa") or not cotes_fiables(m):
        return None
    dom, ext = h
    prof = C.profil(dom, ext)
    marches, _ = S.scanner(prof["grille"], m["cotes_betpawa"])
    marches = [x for x in marches if not contredit_le_profil(x["groupe"], x["selection"], prof["buts"])]
    principal = S.choisir(marches, COTE_MIN)
    if not principal:
        return None
    G = np.array(prof["grille"])
    scen = scenarios(prof)
    vus: dict[frozenset, dict] = {}
    for x in [principal] + [y for y in marches if y is not principal]:      # le principal d'alpha d'abord : jamais écrasé
        if x["cote"] < COTE_MIN:
            continue
        ev = evenement(x["groupe"], x["selection"])
        if ev is None:
            continue
        if ev in vus and (vus[ev]["principal"] or vus[ev]["cote"] >= x["cote"]):    # même événement : on garde le mieux payé
            continue
        W = masque_du_marche(x["groupe"], x["selection"], len(G))
        s = {k: masse_perte(G, W, v) for k, v in scen.items()}
        j1 = [1 - max(s[k] for k in ("favori_creuse", "match_s_ouvre", "nul"))]      # sûreté face au scénario le plus coûteux
        j4 = [1 - max(s[k] for k in ("equipe_muette", "score_extreme") if k in s)]
        fam = R.famille(x["groupe"])
        p_cal = R.appliquer(courbes.get(fam, []), x["probabilite"])
        vus[ev] = {"groupe": x["groupe"], "selection": x["selection"], "libelle": x["libelle"], "famille": fam, "cote": x["cote"],
                   "probabilite": round(x["probabilite"], 4), "p_calibree": round(p_cal, 4), "valeur": round(p_cal * x["cote"] - 1, 4),
                   "j1": round(min(j1), 4) if j1 else None, "j4": round(min(j4), 4) if j4 else None,
                   "ecart_cote": round(x["probabilite"] - 1 / x["cote"], 4), "pertes_par_scenario": {k: round(v, 3) for k, v in s.items()},
                   "principal": x is principal, "_W": W}
    for g, sels in (m.get("cotes_betpawa") or {}).items():          # combinés : seulement ceux dont la cote Betpawa est trouvée
        if not isinstance(sels, dict) or not (g.startswith("dc_") or g.startswith("1x2_")):
            continue
        for sel, cote in sels.items():
            t = test_combine(g, sel)
            if t is None or not isinstance(cote, (int, float)) or cote < COTE_MIN:
                continue
            W = np.array([[bool(t(i, j)) for j in range(len(G))] for i in range(len(G))])
            pj = float(G[W].sum())
            sc_ = {k: masse_perte(G, W, v) for k, v in scen.items()}
            j1 = 1 - max(sc_[k] for k in ("favori_creuse", "match_s_ouvre", "nul"))
            j4 = 1 - max(sc_[k] for k in ("equipe_muette", "score_extreme") if k in sc_)
            fam = "combine"
            vus[frozenset([("combine", g, sel)])] = {"groupe": g, "selection": sel, "libelle": libelle_combine(g, sel), "famille": fam, "cote": float(cote),
                   "probabilite": round(pj, 4), "p_calibree": round(pj, 4), "valeur": round(pj * float(cote) - 1, 4), "j1": round(j1, 4), "j4": round(j4, 4),
                   "ecart_cote": round(pj - 1 / float(cote), 4), "pertes_par_scenario": {k: round(v, 3) for k, v in sc_.items()}, "principal": False, "_W": W, "combine": True}
    cands = list(vus.values())
    sc = m.get("score_final")
    if sc:
        for c in cands:
            c["gagne"] = bool(S.test_du_marche(c["groupe"], c["selection"])(sc["buts_dom"], sc["buts_ext"]))
    return {"match_id": m["match_id"], "date": m["date"], "heure": m.get("heure_cameroun"), "competition": m.get("competition"),
            "domicile": m["domicile"], "exterieur": m["exterieur"], "scores_extremes": prof["scores_extremes"],
            "series": {"domicile": len(dom), "exterieur": len(ext)}, "candidats": cands, "tendance_buts": prof["buts"], "favori": prof["favori"], "_G": G, "_scen": scen,
            "total_attendu": prof["total_attendu"], "buts_attendus": prof["buts_attendus"]}


# ---------------------------------------------------------------- seuils mesurés et jugement

def quartile_bas(valeurs: list[float]) -> float | None:
    v = sorted(x for x in valeurs if x is not None)
    return v[len(v) // 4] if v else None


def mesurer_seuils(prep: list[dict]) -> dict[str, Any]:
    """À partir des matchs de la 1re moitié seulement."""
    princ = [c for p in prep for c in p["candidats"] if c["principal"]]
    ecarts = sorted(c["ecart_cote"] for p in prep for c in p["candidats"])
    return {"q1_contrarien": quartile_bas([c["j1"] for c in princ]), "q1_outsider": quartile_bas([c["j4"] for c in princ]),
            "q99_ecart_cote": ecarts[int(len(ecarts) * 0.99)] if ecarts else None, "pronostics_principaux": len(princ)}


def juger_candidats(cands: list[dict], seuils: dict[str, Any]) -> None:
    """Ajoute à chaque candidat le verdict des cinq juges (True = passe)."""
    for c in cands:
        c["sure"] = min(x for x in (c["j1"], c["j4"]) if x is not None) if (c["j1"] is not None or c["j4"] is not None) else 0.0
    for c in cands:
        dominé = any(o is not c and o["sure"] >= c["sure"] and o["cote"] >= c["cote"] and (o["sure"] > c["sure"] or o["cote"] > c["cote"]) for o in cands)
        c["juges"] = {
            "contrarien": c["j1"] is None or c["j1"] >= seuils["q1_contrarien"],
            "premiers_principes": c["valeur"] > 0,
            "expansionniste": not dominé,
            "outsider": c["j4"] is None or c["j4"] >= seuils["q1_outsider"],
            "executant": c["cote"] >= COTE_MIN and c["ecart_cote"] <= seuils["q99_ecart_cote"],
        }
        c["nb_juges"] = sum(c["juges"].values())
        c["dangereux"] = not (c["juges"]["contrarien"] and c["juges"]["outsider"] and c["juges"]["executant"])


def verdict(p: dict[str, Any], supers: set[str], adapter: bool = False) -> dict[str, Any]:
    """Pronostic final du match. `pronostic` : le principal d'alpha ; s'il est dangereux ET que l'adaptation a fait ses preuves sur la 1re moitié
    (`adapter`), la meilleure adaptation non dangereuse ; sinon on le garde et on le marque `fragile`.
    `opportunite` : un marché qui passe les cinq juges (super marché si sa famille a fait ses preuves, sinon signal exploratoire)."""
    cands = p["candidats"]
    sains = [c for c in cands if not c["dangereux"]]
    principal = next((c for c in cands if c["principal"]), None)
    if principal is not None and (not principal["dangereux"] or not adapter):
        choix, origine = principal, "alpha"
    elif sains:
        choix, origine = max(sains, key=lambda c: (round(c["p_calibree"], 4), c["cote"])), "adapte"
    else:
        choix, origine = None, None
    parfaits = [c for c in cands if c["nb_juges"] == len(JUGES)]
    opp = max(parfaits, key=lambda c: (c["valeur"], c["cote"])) if parfaits else None
    statut = "pas_de_pari" if choix is None else "valide"
    niveau = None
    if opp is not None:
        niveau = "super" if opp["famille"] in supers else "exploratoire"
    return {"statut": statut, "origine": origine, "pronostic": choix, "opportunite": opp, "niveau_opportunite": niveau,
            "fragile": bool(choix is not None and choix["dangereux"])}


# ---------------------------------------------------------------- super marché (logique de Patrick)

SCENARIOS_TEXTE = {"favori_creuse": "le favori creuse l'écart", "match_s_ouvre": "le match s'ouvre", "nul": "un nul tombe",
                   "equipe_muette": "une équipe ne marque pas", "score_extreme": "un score extrême tombe"}


def _virgule(x: float) -> str:
    return str(round(float(x), 2)).replace(".", ",")


def _appui(c: dict, p: dict) -> str | None:
    """Ce que le match montre en faveur du marché (buts attendus du profil), seulement quand c'est dans le sens du marché."""
    import re
    m = re.fullmatch(r"over_under_(domicile_|exterieur_)?(\d+\.5)", c["groupe"])
    ba, tot = p.get("buts_attendus"), p.get("total_attendu")
    if m and ba and tot is not None:
        ligne = float(m.group(2))
        sujet, att = {None: ("le match", tot), "domicile_": (p["domicile"], ba[0]), "exterieur_": (p["exterieur"], ba[1])}[m.group(1)]
        if (c["selection"] == "moins" and att < ligne) or (c["selection"] == "plus" and att > ligne):
            pl = "s" if att >= 1.5 else ""
            return (f"{sujet} : {_virgule(att)} but{pl} attendu{pl}, de quoi appuyer ce marché." if m.group(1) else f"{_virgule(att)} buts attendus au total, de quoi appuyer ce marché.")
    m = re.fullmatch(r"cages_inviolees_(domicile|exterieur)", c["groupe"])
    if m and ba:
        att = ba[1] if m.group(1) == "domicile" else ba[0]          # la cage du domicile est inviolée si l'extérieur ne marque pas
        equipe = p["exterieur"] if m.group(1) == "domicile" else p["domicile"]
        if (c["selection"] == "oui" and att < 1.0) or (c["selection"] == "non" and att >= 1.0):
            return f"{equipe} : {_virgule(att)} but attendu seulement." if c["selection"] == "oui" else f"{equipe} : {_virgule(att)} but attendu, il peut trouver la faille."
    if c["groupe"] == "btts" and tot is not None:
        return f"{_virgule(tot)} buts attendus au total, un match où les deux équipes {'marquent' if c['selection'] == 'Oui' else 'ne marquent pas toutes les deux'}." if (
            (c["selection"] == "Oui" and tot >= 2.5) or (c["selection"] == "Non" and tot < 2.5)) else None
    return None


def raison(c: dict, princ: dict | None, p: dict) -> str:
    """Justification de parieur : pourquoi CE marché est retenu, en positif (aucune mention des juges, aucun découragement)."""
    t = []
    if c.get("combine"):
        t.append(f"Deux statistiques dans le même sens : {c['libelle'].lower()}, cote du combiné trouvée sur Betpawa.")
    if princ:
        t.append(f"Cote {_virgule(c['cote'])} contre {_virgule(princ['cote'])} pour le principal ({princ['libelle'].lower()}) : meilleur rendement pour une sûreté au moins égale.")
    a = _appui(c, p)
    if a:
        t.append(a)
    sol = [k for k, v in sorted((c.get("pertes_par_scenario") or {}).items(), key=lambda kv: kv[1]) if k in SCENARIOS_TEXTE][:2]
    if sol:
        t.append(f"Il reste bien placé même si {' ou si '.join(SCENARIOS_TEXTE[k] for k in sol)}.")
    return " ".join(t)


def jambe(c: dict) -> dict:
    return {k: c[k] for k in ("groupe", "selection", "libelle", "famille", "cote")}


def super_marche(p: dict[str, Any], seuils: dict[str, Any]) -> dict[str, Any] | None:
    """Un marché qui se démarque, sinon rien. Deux formes :
    - COMBINÉ : deux jambes de familles différentes qui vont dans le même sens (la probabilité d'avoir les deux dépasse le produit des
      probabilités : seuil naturel, aucune constante), chaque jambe non dangereuse, et le combiné survit aux scénarios (juges 1 et 4).
      La cote du combiné n'est pas dans nos données : à vérifier sur Betpawa (minimum 1,26).
    - SIMPLE : un autre marché que celui d'alpha qui passe les 5 juges et paie mieux que lui après calibration (valeur supérieure).
    Le combiné passe en premier ; jamais le marché d'alpha tel quel."""
    cands, G, scen = p["candidats"], p["_G"], p["_scen"]
    princ = next((c for c in cands if c["principal"]), None)
    sures = [c for c in cands if not c["dangereux"] and c["probabilite"] > 0]
    sure_ref = princ["sure"] if princ else 0.0          # se démarquer = aussi sûr que le pronostic d'alpha face aux scénarios, et mieux payé
    cote_ref = princ["cote"] if princ else COTE_MIN
    reels = [c for c in cands if c.get("combine") and c["nb_juges"] == len(JUGES) and c["sure"] >= sure_ref and c["cote"] > cote_ref]
    if reels:                                              # combiné réel (cote trouvée sur Betpawa) : passe avant tout
        o = max(reels, key=lambda c: (c["valeur"], c["cote"]))
        return {"type": "combine", "jambes": [jambe(o)], "cote_combine": o["cote"], "cote_min": COTE_MIN, "juges": o["juges"], "raison": raison(o, princ, p)}
    meilleur = None
    for a in range(len(sures) if COMBINES else 0):
        for b in range(a + 1, len(sures)):
            A, B = sures[a], sures[b]
            if A["famille"] == B["famille"] or A["groupe"] == B["groupe"]:
                continue
            WA, WB = A["_W"], B["_W"]
            W = WA & WB
            pj, pa, pb = float(G[W].sum()), float(G[WA].sum()), float(G[WB].sum())
            if pj <= pa * pb or pj >= min(pa, pb) - 1e-9:       # pas dans le même sens, ou une jambe contient l'autre (le combiné = une seule jambe)
                continue
            s_ = {k: masse_perte(G, W, v) for k, v in scen.items()}
            j1 = 1 - max(s_[k] for k in ("favori_creuse", "match_s_ouvre", "nul"))
            j4 = 1 - max(s_[k] for k in ("equipe_muette", "score_extreme") if k in s_)
            if j1 < seuils["q1_contrarien"] or j4 < seuils["q1_outsider"] or min(j1, j4) < sure_ref or A["cote"] * B["cote"] <= cote_ref:
                continue
            if meilleur is None or pj > meilleur[0]:
                meilleur = (pj, A, B, j1, j4)
    if meilleur:
        pj, A, B, j1, j4 = meilleur
        return {"type": "combine", "jambes": [jambe(A), jambe(B)], "cote_combine": "a_verifier", "cote_min": COTE_MIN,
                "juges": {"contrarien": True, "premiers_principes": True, "expansionniste": True, "outsider": True, "executant": True}}
    ref = princ["valeur"] if princ else float("-inf")
    autres = [c for c in cands if not c["principal"] and not c.get("combine") and c["nb_juges"] == len(JUGES) and c["valeur"] > ref and c["sure"] >= sure_ref and c["cote"] > cote_ref]
    if autres:
        o = max(autres, key=lambda c: (c["valeur"], c["cote"]))
        return {"type": "simple", "jambes": [jambe(o)], "cote_combine": None, "cote_min": COTE_MIN, "juges": o["juges"], "raison": raison(o, princ, p)}
    return None


# ---------------------------------------------------------------- chargement et statistiques

def courbes_calibration() -> dict[str, list]:
    return json.loads((ROOT / "docs" / "recalage_familles.json").read_text(encoding="utf-8"))["courbes"]


def preparer_tout(matchs: list[dict], courbes: dict[str, list]) -> list[dict]:
    return [p for m in matchs if (p := preparer(m, courbes))]


def stats(paris: list[tuple[str, dict]]) -> dict[str, Any]:
    """Réussite, cote moyenne, rendement à mise plate (vraies cotes) et intervalle de confiance par rééchantillonnage des JOURNÉES."""
    if not paris:
        return {"n": 0}
    n = len(paris)
    h = sum(c["gagne"] for _, c in paris)
    rend = sum((c["cote"] - 1) if c["gagne"] else -1 for _, c in paris) / n
    jours: dict[str, list] = defaultdict(list)
    for d, c in paris:
        jours[d].append(c)
    cles, rnd, taux, rd = list(jours), random.Random(0), [], []
    for _ in range(2000):
        tir = [c for k in (rnd.choice(cles) for _ in cles) for c in jours[k]]
        taux.append(sum(c["gagne"] for c in tir) / len(tir))
        rd.append(sum((c["cote"] - 1) if c["gagne"] else -1 for c in tir) / len(tir))
    taux.sort(); rd.sort()
    return {"n": n, "reussite": round(h / n, 4), "cote_moyenne": round(sum(c["cote"] for _, c in paris) / n, 3), "rendement": round(rend, 4),
            "ic95_reussite": [round(taux[50], 4), round(taux[1949], 4)], "ic95_rendement": [round(rd[50], 4), round(rd[1949], 4)]}


def moitie(prep: list[dict]) -> tuple[list[dict], list[dict], str]:
    jours = sorted({p["date"] for p in prep})
    cumul, coupe = 0, jours[-1]
    for d in jours:
        cumul += sum(1 for p in prep if p["date"] == d)
        if cumul >= len(prep) / 2:
            coupe = jours[min(jours.index(d) + 1, len(jours) - 1)]
            break
    return [p for p in prep if p["date"] < coupe], [p for p in prep if p["date"] >= coupe], coupe


def choisir_supers(apprentissage: list[dict]) -> dict[str, Any]:
    """Familles de marché dont les paris « cinq juges passés » ont un rendement réel positif sur la 1re moitié (>= 30 cas)."""
    par_fam: dict[str, list] = defaultdict(list)
    for p in apprentissage:
        parfaits = [c for c in p["candidats"] if c["nb_juges"] == len(JUGES) and "gagne" in c]
        if parfaits:
            c = max(parfaits, key=lambda c: (c["valeur"], c["cote"]))
            par_fam[c["famille"]].append((p["date"], c))
    detail = {f: stats(v) for f, v in par_fam.items()}
    return {"supers": sorted(f for f, s in detail.items() if s["n"] >= SUPPORT_MIN and s["rendement"] > 0), "detail_apprentissage": detail}


def backtest() -> dict[str, Any]:
    courbes = courbes_calibration()
    matchs = [m for m in charger_matchs() if m.get("score_final")]
    prep = preparer_tout(matchs, courbes)
    appr, test, coupe = moitie(prep)
    seuils = mesurer_seuils(appr)
    for p in prep:
        juger_candidats(p["candidats"], seuils)
    sup = choisir_supers(appr)
    supers = set(sup["supers"])
    # L'adaptation ne remplace le pronostic d'alpha que si, sur la 1re moitié, elle a réussi au moins autant qu'alpha sur les mêmes matchs.
    va = [(p, verdict(p, supers, True)) for p in appr]
    ad = stats([(p["date"], d["pronostic"]) for p, d in va if d["origine"] == "adapte"])
    al = stats([(p["date"], next(c for c in p["candidats"] if c["principal"])) for p, d in va if d["origine"] == "adapte"])
    adapter = bool(ad["n"] and ad["reussite"] >= al["reussite"])
    res: dict[str, Any] = {"jour_de_coupe": coupe, "matchs_apprentissage": len(appr), "matchs_test": len(test), "seuils": seuils,
                           "adaptation_active": adapter, "decision_adaptation_apprentissage": {"adaptations": ad, "alpha_sur_ces_matchs": al},
                           "supers": sup["supers"], "detail_apprentissage_par_famille": sup["detail_apprentissage"]}
    for nom, jeu in (("apprentissage", appr), ("test", test)):
        v = [(p, verdict(p, supers, adapter)) for p in jeu]
        info = [(p["date"], d["pronostic"]) for p, d in ((p, verdict(p, supers, True)) for p in jeu) if d["origine"] == "adapte"]
        alpha = [(p["date"], next(c for c in p["candidats"] if c["principal"])) for p in jeu]
        joues = [(p["date"], d["pronostic"]) for p, d in v if d["pronostic"]]
        meme = [(p["date"], next(c for c in p["candidats"] if c["principal"])) for p, d in v if d["pronostic"]]
        adaptes = [(p["date"], d["pronostic"]) for p, d in v if d["origine"] == "adapte"]
        alpha_sur_adaptes = [(p["date"], next(c for c in p["candidats"] if c["principal"])) for p, d in v if d["origine"] == "adapte"]
        res[nom] = {"alpha_brut": stats(alpha), "juges_pronostic": stats(joues), "alpha_sur_les_memes_matchs": stats(meme),
                    "pas_de_pari": sum(1 for _, d in v if d["statut"] == "pas_de_pari"), "matchs": len(jeu),
                    "adaptations": {"juges": stats(adaptes), "alpha_sur_ces_matchs": stats(alpha_sur_adaptes)},
                    "fragiles": stats([(p["date"], d["pronostic"]) for p, d in v if d["fragile"]]),
                    "non_fragiles": stats([(p["date"], d["pronostic"]) for p, d in v if d["pronostic"] and not d["fragile"]]),
                    "information_variante_adaptation": stats(info),
                    "super_marche": stats([(p["date"], d["opportunite"]) for p, d in v if d["niveau_opportunite"] == "super"]),
                    "signal_exploratoire": stats([(p["date"], d["opportunite"]) for p, d in v if d["niveau_opportunite"] == "exploratoire"]),
                    "opportunite_toutes_familles": stats([(p["date"], d["opportunite"]) for p, d in v if d["opportunite"]])}
    res["note"] = ("Seuils et familles « super » mesurés sur la 1re moitié ; la 2e moitié n'a servi qu'au jugement. Probabilité calibrée par les courbes "
                   "Football-Data (résultats seuls). Cotes BetPawa réelles de l'archive jouée ; marchés combinés (double chance + total) absents des cotes parsées.")
    PARAMETRES.write_text(json.dumps({"seuils": seuils, "supers": sup["supers"], "adaptation_active": adapter, "jour_de_coupe": coupe}, ensure_ascii=False, indent=1), encoding="utf-8")
    BACKTEST.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


# ---------------------------------------------------------------- page

def resume(c: dict | None) -> dict | None:
    if not c:
        return None
    return {k: c[k] for k in ("groupe", "selection", "libelle", "famille", "cote", "probabilite", "p_calibree", "valeur", "juges", "nb_juges")} | \
           ({"gagne": c["gagne"]} if "gagne" in c else {})


def ecrire_page() -> dict[str, Any]:
    """Verdict de chaque match à venir (ou joué) avec les paramètres figés du dernier backtest."""
    prm = json.loads(PARAMETRES.read_text(encoding="utf-8"))
    courbes, supers = courbes_calibration(), set(prm["supers"])
    out = {}
    dt = __import__("datetime")
    veille = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%d")      # la page n'affiche que les matchs à venir
    for p in preparer_tout(charger_matchs(), courbes):
        if str(p["date"]) < veille:
            continue
        juger_candidats(p["candidats"], prm["seuils"])
        v = verdict(p, supers, prm.get("adaptation_active", False))
        out[p["match_id"]] = {"statut": v["statut"], "origine": v["origine"], "fragile": v["fragile"], "niveau_opportunite": v["niveau_opportunite"],
                              "pronostic": resume(v["pronostic"]), "super": super_marche(p, prm["seuils"])}
    d = {"genere_le": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
         "supers": prm["supers"], "jour_de_coupe": prm["jour_de_coupe"], "promotion_allowed": False, "matchs": out}
    SORTIE.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "backtest"
    if cmd == "page":
        d = ecrire_page()
        print(len(d["matchs"]), "matchs jugés,", sum(1 for v in d["matchs"].values() if v["niveau_opportunite"]), "avec opportunité")
    else:
        r = backtest()
        print(json.dumps({k: r[k] for k in ("jour_de_coupe", "matchs_apprentissage", "matchs_test", "seuils", "supers", "test")}, ensure_ascii=False, indent=1))
