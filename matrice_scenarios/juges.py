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
                   "principal": x is principal}
    cands = list(vus.values())
    sc = m.get("score_final")
    if sc:
        for c in cands:
            c["gagne"] = bool(S.test_du_marche(c["groupe"], c["selection"])(sc["buts_dom"], sc["buts_ext"]))
    return {"match_id": m["match_id"], "date": m["date"], "heure": m.get("heure_cameroun"), "competition": m.get("competition"),
            "domicile": m["domicile"], "exterieur": m["exterieur"], "scores_extremes": prof["scores_extremes"],
            "series": {"domicile": len(dom), "exterieur": len(ext)}, "candidats": cands, "tendance_buts": prof["buts"], "favori": prof["favori"]}


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
                              "pronostic": resume(v["pronostic"]), "opportunite": resume(v["opportunite"])}
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
