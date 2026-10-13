# -*- coding: utf-8 -*-
"""Calibration et évaluation du moteur Europe (13/10/2026). Isolé : ni V2 ni V3 ne sont modifiés.

Entrée : la liste `matchs` de data/europe/entrees_europe.json (collecte_europe.execution(inclure_joues=True)).
  - entraîne le calibrateur Europe sur les matchs européens JOUÉS strictement avant `avant_le` (historiques déjà coupés
    avant la date de chaque match par la collecte) : mêmes seuils que V3, ≥ 300 observations ET ≥ 50 matchs distincts ;
  - évalue chaque match à venir : sélections, aperçu non calibré (comme V3), candidats écartés avec leurs raisons.
Sans calibration prête : aucune sélection (règle V3), mais l'aperçu non calibré est publié au format de la page V3
(data/europe/pronostics_europe.json -> pronostics_europe.html). NO DATA -> NO GO.

Usage : python calibration_europe.py [--entrees data/europe/entrees_europe.json] [--sortie data/europe/signaux_europe.json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

from moteur_europe import evaluate_match_europe
from moteur_europe.model import build_model_europe
from moteur_europe.preuves import preuves_europe
from moteur_europe.socle.calibration import CalibrationFit, IsotonicCalibrator
from moteur_europe.socle.decision import decide
from moteur_europe.socle.markets import derive_markets, gagne
from moteur_europe.rendu import MIN_MATCHS_CALIBRATION, RAISONS_FR, _signature_evenement_calibration, libelle


def score_joue(m):
    sc = m.get("score") or {}
    h, a = sc.get("buts_dom"), sc.get("buts_ext")
    return (h, a) if isinstance(h, int) and isinstance(a, int) else None


def entraine_calibration_europe(matchs, avant_le):
    """(calibrateur, nb_matchs). N'utilise que les matchs joués avant `avant_le` (AAAA-MM-JJ)."""
    ps, ys, nb = [], [], 0
    for m in matchs:
        sc = score_joue(m)
        if sc is None or str(m.get("date")) >= avant_le:
            continue
        e = m["entree"]
        try:
            probas = derive_markets(build_model_europe(e["europe_dom"], e["europe_ext"], e["ligue_dom"], e["ligue_ext"]),
                                    e.get("handicap_lines", ()))
        except ValueError:
            continue
        vues, vu = set(), False
        for mk, p in probas.items():
            issue = gagne(mk, *sc)
            if mk not in e["odds"] or issue is None or not (0 < p < 1):
                continue
            sig = _signature_evenement_calibration(mk)
            if not sig or sig in vues:
                continue
            vues.add(sig)
            ps.append(p)
            ys.append(1 if issue else 0)
            vu = True
        nb += vu
    cal = IsotonicCalibrator()
    cal.fit(ps, ys)
    if cal.fit_result.ready and nb < MIN_MATCHS_CALIBRATION:
        cal.fit_result = CalibrationFit(False, cal.fit_result.observations, "MATCHS_INSUFFISANTS", ())
    return cal, nb


def evalue_match_europe(m, calibrateur):
    """Un match à venir. Ne lève jamais : l'erreur est rendue dans `statut`."""
    base = {k: m.get(k) for k in ("match_id", "date", "competition_code", "domicile", "exterieur", "couverture")}
    base["heure"], base["competition"] = m.get("heure"), m.get("competition") or m.get("competition_code")
    e = m["entree"]
    if not e["odds"]:
        return {**base, "statut": "SANS_COTE", "selections": [], "candidats": []}
    evidence = preuves_europe(e["europe_dom"], e["europe_ext"], e["ligue_dom"], e["ligue_ext"], list(e["odds"]),
                              m.get("domicile") or "Domicile", m.get("exterieur") or "Extérieur")
    try:
        r = evaluate_match_europe(e, calibrator=calibrateur, evidence=evidence)
    except ValueError as err:
        return {**base, "statut": f"NON_EVALUE : {err}", "selections": [], "candidats": []}
    rejets = dict(r["rejected"])
    pret = calibrateur is not None and calibrateur.fit_result.ready
    cands = []
    for c in sorted(r["candidates"], key=lambda c: c["edv"], reverse=True):
        v = r["values"][c["market"]]
        cands.append({"marche": c["market"], "libelle": libelle(c["market"]), "cote": c["odds"],
                      "probabilite_brute": v.probability_raw, "probabilite": c["probability"], "calibree": c["calibrated"],
                      "edv": round(c["edv"], 1), "raisons": sorted(set(v.reasons) | set(rejets.get(c["market"], ())))})

    cands_tous = list(cands)

    def fmt(liste):
        return [{"marche": s.market, "libelle": libelle(s.market), "cote": s.odds, "probabilite": round(s.probability, 4),
                 "edge": s.edge, "edv": round(s.edv, 1), "justification": s.reason,
                 "raisons_saison": evidence.get(s.market, {}).get("raisons_saison", []),
                 "raisons_recent": evidence.get(s.market, {}).get("raisons_recent", []),
                 "indice_performance": r["indices_performance"].get(s.market)} for s in liste]
    selections = fmt(r["selected"])
    apercu = []
    if not selections and not pret:     # aperçu NON calibré : ce n'est pas une sélection
        apercu = fmt(decide([{**c, "calibrated": True} for c in r["candidates"]])[0])
    mod = r["model"]
    proches = sorted((c for c in cands_tous if 1.26 <= c["cote"] <= 1.74), key=lambda c: c["probabilite"], reverse=True)[:3]
    return {**base, "statut": "EVALUE", "proches": proches, "lambda_dom": round(mod.lambda_home, 3), "lambda_ext": round(mod.lambda_away, 3),
            "calibree": pret, "n_dom": mod.home_sample.current_n, "n_ext": mod.away_sample.current_n,
            "selections": selections, "apercu_non_calibre": apercu, "candidats": cands[:5]}


def execution(entrees="data/europe/entrees_europe.json", sortie="data/europe/signaux_europe.json", aujourdhui=None,
              site="data/europe/pronostics_europe.json"):
    aujourdhui = aujourdhui or datetime.date.today()
    with open(entrees, encoding="utf-8") as f:
        matchs = json.load(f)["matchs"]
    cal, nb = entraine_calibration_europe(matchs, aujourdhui.isoformat())
    a_venir = [m for m in matchs if score_joue(m) is None]
    signaux = [evalue_match_europe(m, cal) for m in a_venir]
    bilan = {"genere_le": aujourdhui.isoformat(), "matchs_a_venir": len(signaux),
             "evalues": sum(1 for s in signaux if s["statut"] == "EVALUE"),
             "selections": sum(len(s["selections"]) for s in signaux),
             "calibration": {"prete": cal.fit_result.ready, "raison": cal.fit_result.reason,
                             "observations": cal.fit_result.observations, "matchs": nb}}
    os.makedirs(os.path.dirname(sortie) or ".", exist_ok=True)
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump({"bilan": bilan, "signaux": signaux}, f, ensure_ascii=False)
    if site:
        ecrit_pour_le_site(signaux, bilan, cal, nb, site)
    return bilan


RAISONS_MASQUEES = {"CALIBRATION_ABSENTE", "VALUE_NON_ELIGIBLE"}      # conséquences, pas des causes
MANQUES = (("europe_dom_domicile", "domicile", "match européen à domicile", "domicile"),
           ("europe_ext_exterieur", "exterieur", "match européen à l'extérieur", "exterieur"),
           ("ligue_dom_domicile", "domicile", "match de championnat à domicile", "domicile"),
           ("ligue_ext_exterieur", "exterieur", "match de championnat à l'extérieur", "exterieur"))


def _pl(n, mot):
    return f"{n} {mot}" if n < 2 else f"{n} {mot.replace('match ', 'matchs ', 1)}"


def autre_match(x):
    """Un match SANS aperçu, expliqué en français : pourquoi aucun pronostic (données manquantes ou filtres)."""
    base = {k: x.get(k) for k in ("match_id", "date", "heure", "competition", "domicile", "exterieur")}
    lignes = []
    if x["statut"] == "SANS_COTE":
        return {**base, "etat": "Pas de cotes BetPawa", "lignes": ["Aucune cote relevée pour ce match."]}
    if x["statut"].startswith("NON_EVALUE"):
        cv = x.get("couverture") or {}
        for cle, cote, mot, _ in MANQUES:
            n = cv.get(cle)
            if isinstance(n, int) and n < 3:
                equipe = x.get(cote)
                lignes.append(f"{equipe} : {_pl(n, mot)} (3 minimum)")
        return {**base, "etat": "Non évalué : historique insuffisant", "lignes": lignes or [x["statut"]]}
    lignes.append(f"Buts attendus : {x.get('lambda_dom')} – {x.get('lambda_ext')}")
    for c in x.get("proches", []):
        causes = [RAISONS_FR.get(r, r) for r in c["raisons"] if r not in RAISONS_MASQUEES]
        lignes.append(f"{c['libelle']} · cote {str(c['cote']).replace('.', ',')} · probabilité {round(100 * c['probabilite'])} % · refusé : "
                      + (" ; ".join(causes) if causes else "aucun défaut, en attente de calibration"))
    if not x.get("proches"):
        lignes.append("Aucun marché coté dans la fenêtre 1,26 – 1,74.")
    return {**base, "etat": "Évalué : aucun marché ne passe tous les filtres", "lignes": lignes}


def ecrit_pour_le_site(signaux, bilan, cal, nb_matchs, chemin):
    """Même format que data/v3/pronostics_v3.json : la page pronostics_europe.html réutilise archetype_v3.js tel quel."""
    from moteur_europe.rendu import signal_site
    signaux = sorted(signaux, key=lambda x: (str(x["date"]), str(x.get("heure") or ""), str(x["domicile"])))
    fit = cal.fit_result
    sortie = {"moteur": "moteur_europe", "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "calibration": {"prete": fit.ready, "observations": fit.observations, "matchs": nb_matchs,
                              "minimum_observations": cal.minimum_observations, "minimum_matchs": MIN_MATCHS_CALIBRATION,
                              "raison": fit.reason},
              "bilan": bilan, "signaux": [signal_site(x) for x in signaux if x["selections"] or x.get("apercu_non_calibre")],
              "autres": [autre_match(x) for x in signaux if not (x["selections"] or x.get("apercu_non_calibre"))]}
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entrees", default="data/europe/entrees_europe.json")
    p.add_argument("--sortie", default="data/europe/signaux_europe.json")
    p.add_argument("--site", default="data/europe/pronostics_europe.json")
    a = p.parse_args()
    print(json.dumps(execution(a.entrees, a.sortie, site=a.site), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
