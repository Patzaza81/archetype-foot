"""Piste B′ : prior Elo dans le Dixon-Coles pénalisé. Protocole : docs/DC_ELO_PROTOCOLE.md. Archive/rejeu Football-Data, PAS un bilan réel.

Périmètre (couverture mesurée, docs/DC_ELO_COUVERTURE.md) : les cinq premières divisions E0, SP1, I1, D1, F1 (les seules où l'Elo existe pour la plupart des équipes).
Comparaison appariée : MÊMES matchs (contrat 1.5 passé), MÊMES hyperparamètres (σ, ξ, ρ de parametres.json), sans les effets du Module 2 des deux côtés ;
seule différence : la pénalité (att − γE)² + (dfn − δE)². γ, δ globaux figés, appris sur 2025-26 seulement (recherche par coordonnées, départ (0, 0) = ridge actuel, aucune borne).
Usage : python -m moteur_dc.elo  → docs/DC_ELO_RESULTATS.md et .json
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as CAL, coeur, contrat as C, donnees as D, elo_donnees as ED, modele as MO, module1 as M1

ROOT = Path(__file__).resolve().parent.parent
DIVISIONS = ("E0", "SP1", "I1", "D1", "F1")
TIRAGES, GRAINE, PAS = 4000, 20261101, 0.05


def marche_avant(par_ligue: dict[str, list[dict]], p: dict[str, Any], elo: dict | None, idx: dict | None, coefs: tuple[float, float] | None,
                 pas_jours: int = 7) -> dict[str, dict[str, Any]]:
    """{id du match: {…, lh, la}} ; coefs None = Dixon-Coles pur (sans prior). Les matchs notés sont ceux qui passent le contrat 1.5."""
    out: dict[str, dict[str, Any]] = {}
    for lg, ms in par_ligue.items():
        division = lg.split("|")[2]
        ms = sorted(ms, key=lambda m: m["date"])
        depart = date.fromisoformat(ms[0]["date"])
        semaines: dict[date, list[dict]] = defaultdict(list)
        for m in ms:
            semaines[depart + timedelta(days=((date.fromisoformat(m["date"]) - depart).days // pas_jours) * pas_jours)].append(m)
        fit, passe = None, []
        for debut in sorted(semaines):
            jour = debut.isoformat()
            if passe:
                t = M1.tableau(passe, jour)
                dom, ext = [m["dom"] for m in passe], [m["ext"] for m in passe]
                e = None
                if coefs is not None:
                    e = {x: ED.elo_veille(elo, ED.rapprocher(x, division, idx), jour) for x in set(dom) | set(ext)}
                fit = MO.ajuster(dom, ext, np.array([m["h"] for m in passe]), np.array([m["a"] for m in passe]), np.array([D.jours(m["date"], jour) for m in passe]),
                                 p["sigma"], p["xi"], fit, p["rho"], None, e, coefs)
                for m in semaines[debut]:
                    try:
                        C.construire(passe, m["dom"], m["ext"], jour, t, m["id"])
                    except ValueError:
                        continue
                    lh, la = fit.lambdas(m["dom"], m["ext"])
                    out[m["id"]] = {"ligue": lg, "saison": m["saison"], "date": m["date"], "h": m["h"], "a": m["a"], "lh": lh, "la": la, "rho": fit.rho}
            passe.extend(semaines[debut])
    return out


def ll_match(r: dict[str, Any], c: float = 1.0) -> float:
    """Log-vraisemblance du score réel ; `c` multiplie les deux espérances de buts (variante centrée)."""
    g = MO.grille(r["lh"] * c, r["la"] * c, r["rho"])
    return math.log(max(float(g[r["h"], r["a"]]), 1e-12))


def ll_moyen(rows: dict[str, dict], ids: list[str]) -> float:
    return float(np.mean([ll_match(rows[i]) for i in ids]))


def apprendre(par_ligue, p, elo, idx, filtre=lambda d: True, log=print) -> tuple[tuple[float, float], list[dict]]:
    """Recherche par coordonnées de (γ, δ) sur `par_ligue` (apprentissage seulement) ; la grille s'étend tant que la vraisemblance prédictive s'améliore."""
    cache: dict[tuple, float] = {}

    def score(g: float, d: float) -> float:
        k = (round(g, 4), round(d, 4))
        if k not in cache:
            rows = marche_avant(par_ligue, p, elo, idx, k)
            cache[k] = float(np.mean([ll_match(r) for r in rows.values() if filtre(r["date"])]))
        return cache[k]

    cur = [0.0, 0.0]
    trace = []
    for passage in range(2):
        for i in (0, 1):
            meilleur = score(*cur)
            for sens in (+1, -1):
                pos = cur[i]
                while True:
                    cand = list(cur)
                    cand[i] = round(pos + sens * PAS, 4)
                    s = score(*cand)
                    if s > meilleur + 1e-12:
                        meilleur, pos = s, cand[i]
                    else:
                        break
                if pos != cur[i]:
                    cur[i] = pos
                    break
            trace.append({"passage": passage, "coord": "gamma" if i == 0 else "delta", "valeur": cur[i], "ll": round(meilleur, 6)})
            log(f"    {trace[-1]}")
    return (cur[0], cur[1]), trace


def bootstrap(delta: np.ndarray, rng) -> dict[str, float]:
    n = len(delta)
    c = rng.multinomial(n, np.full(n, 1.0 / n), size=TIRAGES)
    m = (c @ delta) / n
    sd = float(delta.std(ddof=1))
    return {"gain_moyen": float(delta.mean()), "ic95": [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))], "sd_match": sd,
            "mde": 1.96 * sd / math.sqrt(n), "n": n, "retenu": bool(np.percentile(m, 2.5) > 0)}


def p_marches(r: dict[str, Any], c: float = 1.0) -> np.ndarray:
    return np.einsum("ij,kij->k", MO.grille(r["lh"] * c, r["la"] * c, r["rho"]), coeur.MASQUES)


def lancer(log=print) -> dict[str, Any]:
    p = json.loads((Path(__file__).with_name("parametres.json")).read_text(encoding="utf-8"))
    elo = ED.charger()
    idx = ED.index_noms(elo)
    bloc = [m for m in D.charger_bloc() if m["ligue"].split("|")[2] in DIVISIONS]
    par = {s: defaultdict(list) for s in ("2526", "2627")}
    for m in bloc:
        par[m["saison"]][m["ligue"]].append(m)
    log(f"divisions {DIVISIONS} : {sum(len(v) for v in par['2526'].values())} matchs 2025-26, {sum(len(v) for v in par['2627'].values())} matchs 2026-27 (avant contrat)")
    pur = marche_avant(par["2526"], p, None, None, None)
    dates = sorted(r["date"] for r in pur.values())
    coupe = dates[len(dates) // 2]                 # date médiane des matchs notés de 2025-26, fixée avant tout résultat
    log(f"2025-26 : {len(pur)} matchs notés (contrat passé) ; coupe chronologique {coupe}. 2026-27 : saison trop jeune (aucun match ne passe le contrat 1.5 dans ces divisions).")
    sens = {}
    for nom, appr, test in (("principal", lambda d: d < coupe, lambda d: d >= coupe), ("inverse", lambda d: d >= coupe, lambda d: d < coupe)):
        log(f"  apprentissage {nom}")
        coefs, trace = apprendre(par["2526"], p, elo, idx, appr, log)
        avec = marche_avant(par["2526"], p, elo, idx, coefs)
        ids = sorted(i for i in set(pur) & set(avec) if test(pur[i]["date"]))
        delta = np.array([ll_match(avec[i]) - ll_match(pur[i]) for i in ids])
        rng = np.random.default_rng(GRAINE)
        tot_pur = sum(pur[i]["lh"] + pur[i]["la"] for i in ids)
        c = tot_pur / sum(avec[i]["lh"] + avec[i]["la"] for i in ids)
        dc = np.array([ll_match(avec[i], c) - ll_match(pur[i]) for i in ids])
        sens[nom] = {"coefs": list(coefs), "trace": trace, "n": len(ids), "periode": [min(pur[i]["date"] for i in ids), max(pur[i]["date"] for i in ids)],
                     "brut": bootstrap(delta, rng), "centre": {**bootstrap(dc, rng), "facteur_niveau": c}, "_ids": ids, "_avec": avec, "_delta": delta}
    P_ = sens["principal"]
    ids, avec = P_.pop("_ids"), P_.pop("_avec")
    delta = P_.pop("_delta")
    sens["inverse"].pop("_ids"), sens["inverse"].pop("_avec"), sens["inverse"].pop("_delta")
    res: dict[str, Any] = {"coupe": coupe, "matchs_notes_2526": len(pur), "principal": P_, "inverse": sens["inverse"]}
    test_pur, test_elo = pur, avec
    # par division
    res["par_division"] = {}
    for d in DIVISIONS:
        sel = [k for k, i in enumerate(ids) if test_pur[i]["ligue"].split("|")[2] == d]
        if len(sel) > 1:
            res["par_division"][d] = {"n": len(sel), "gain_moyen": float(delta[sel].mean())}
    # EMAC avec / sans (103 marchés)
    Y = CAL._resultats(np.array([test_pur[i]["h"] for i in ids]), np.array([test_pur[i]["a"] for i in ids]))
    P0 = np.stack([p_marches(test_pur[i]) for i in ids])
    P1 = np.stack([p_marches(test_elo[i]) for i in ids])
    res["emac"] = {"sans_elo": CAL.emac(P0.ravel(), Y.ravel().astype(float)), "avec_elo": CAL.emac(P1.ravel(), Y.ravel().astype(float))}
    # exemple de matrices
    ex = ids[0]
    res["exemple"] = {"id": ex, "ligue": test_pur[ex]["ligue"], "date": test_pur[ex]["date"], "score": [test_pur[ex]["h"], test_pur[ex]["a"]],
                      "pur": {"lh": test_pur[ex]["lh"], "la": test_pur[ex]["la"]}, "elo": {"lh": test_elo[ex]["lh"], "la": test_elo[ex]["la"]}}
    return res


def rapport_md(r: dict[str, Any]) -> str:
    P_, I_ = r["principal"], r["inverse"]
    def ligne(nom, x):
        return (f"| {nom} | {x['gain_moyen']:+.5f} | [{x['ic95'][0]:+.5f} ; {x['ic95'][1]:+.5f}] | {x['mde']:.5f} | {x['n']} | {'oui' if x['retenu'] else 'non'} |")
    L = ["# Piste B′ (prior Elo) — rapport", "",
         "> **Rejeu Football-Data (archive), PAS un bilan réel.** Périmètre : E0, SP1, I1, D1, F1 (les seules divisions où l'Elo existe). Source Elo : copie CC BY 4.0 de ClubElo (voir `data/clubelo/SOURCE.md`) ; "
         "l'API ClubElo est en panne.", "",
         "> **Écart au protocole, déclaré avant le résultat :** le test sur 2026-27 est IMPOSSIBLE dans ces divisions (la saison est trop jeune : aucun match ne passe le contrat 1.5, qui exige 4 matchs au lieu). "
         f"Le test est donc un découpage chronologique de 2025-26 à la date médiane des matchs notés ({r['coupe']}) : (γ, δ) appris AVANT la coupe, lus APRÈS, puis l'inverse comme contrôle de stabilité.", "",
         f"- 2025-26 : {r['matchs_notes_2526']} matchs notés (contrat passé). Test principal : **{P_['n']} matchs** ({P_['periode'][0]} → {P_['periode'][1]}). Échantillon petit : le test ne voit que de gros effets.",
         f"- (γ, δ) appris sur la 1re moitié : **{P_['coefs'][0]:+.2f} / {P_['coefs'][1]:+.2f}** ; appris sur la 2e moitié : **{I_['coefs'][0]:+.2f} / {I_['coefs'][1]:+.2f}** (départ (0, 0) = ridge actuel).", "",
         "## Gain de log-vraisemblance du score par match (Dixon-Coles avec prior Elo − Dixon-Coles pur), apparié", "",
         "| Lecture | Gain moyen | IC 95 % | MDE recalculé | n | Retenu |", "|---|---|---|---|---|---|",
         ligne("Principale (appris 1re moitié, lu 2e)", P_["brut"]), ligne(f"Principale centrée (niveau de buts égalé, facteur {P_['centre']['facteur_niveau']:.4f})", P_["centre"]),
         ligne("Inverse (appris 2e moitié, lu 1re)", I_["brut"]), ligne("Inverse centrée", I_["centre"]), "",
         "Règle : retenu si et seulement si la borne basse de l'IC 95 % est > 0 (comme la piste A).", "", "## Par division, lecture principale (gain moyen, n)", ""]
    for d, v in r["par_division"].items():
        L.append(f"- {d} : {v['gain_moyen']:+.5f} sur {v['n']} matchs")
    L += ["", f"## EMAC (103 marchés, lecture principale) : sans Elo {r['emac']['sans_elo']} — avec Elo {r['emac']['avec_elo']}", "",
          f"## Exemple de matrices : {r['exemple']['ligue']}, {r['exemple']['date']}, score réel {r['exemple']['score'][0]}-{r['exemple']['score'][1]}", "",
          f"- Dixon-Coles pur : buts attendus {r['exemple']['pur']['lh']:.2f} – {r['exemple']['pur']['la']:.2f}", f"- Avec prior Elo : buts attendus {r['exemple']['elo']['lh']:.2f} – {r['exemple']['elo']['la']:.2f}"]
    return "\n".join(L) + "\n"


def main() -> None:
    r = lancer()
    (ROOT / "docs" / "dc_elo_resultats.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    md = rapport_md(r)
    (ROOT / "docs" / "DC_ELO_RESULTATS.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
