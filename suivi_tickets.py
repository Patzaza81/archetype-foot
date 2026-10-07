"""Historique et suivi statistique des tickets générés.

Chaque ticket de `data/tickets.json` est enregistré (data/tickets_historique.json), puis réglé avec
les scores réels (historique_pronostics.json). Le bilan (data/tickets_bilan.json) compare, par scénario
et par plan de tickets disjoints, ce que le moteur prévoyait et ce qui s'est réellement passé.

Les tickets « VOTRE_TICKET_COTE_x » sont construits dans le navigateur : ils ne sont pas suivis."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Callable

from selection_adaptative import load_json, norm, num, score_history

TICKETS = Path("data/tickets.json")
HISTORIQUE = Path("data/tickets_historique.json")
BILAN = Path("data/tickets_bilan.json")
LIBELLE_SUR = re.compile(r"^(1x2 - [1x2]|double chance - (1x|x2|12)|btts - (oui|non)|(plus|moins) de \d+(\.\d+)? buts)$")


def evaluateur_defaut() -> Callable[[str, int, int], str | None]:
    """Règle un marché avec le même règlement que le reste du pipeline.

    Les tickets mélangent deux vocabulaires : noms canoniques/clés moteur (V3, ex. « over_2_5 »)
    et libellés d'affichage (V2, Journal, ex. « Plus de 2.5 buts », « Double chance - 1X »).
    Ordre : nom tel quel → clé moteur convertie → libellé d'affichage. Rien de reconnu → None
    (le ticket sera exclu des statistiques, jamais compté comme perdu par défaut)."""
    try:
        from archetype_model.learning.reglement import evaluer_marche
    except Exception:
        return lambda marche, h, a: None
    try:
        from branchement_moteur import nom_canonique
    except Exception:
        nom_canonique = lambda x: None  # noqa: E731
    try:
        from journal.journal_memoire import evaluer_marche as evaluer_libelle
    except Exception:
        evaluer_libelle = None

    def ev(marche: str, h: int, a: int) -> str | None:
        for nom in (marche, nom_canonique(marche)):
            if not nom:
                continue
            try:
                statut = evaluer_marche(nom, h, a).statut
            except Exception:
                continue
            if statut in ("WIN", "LOSS"):
                return statut
        # Liste blanche : le règlement par libellé du Journal est trop permissif (« Corners plus de 9.5 »
        # serait réglé sur les buts). On n'accepte que les libellés d'affichage connus.
        if evaluer_libelle and LIBELLE_SUR.match(norm(marche).lower()):
            try:
                ok = evaluer_libelle(marche, h, a)
            except Exception:
                ok = None
            if ok is not None:
                return "WIN" if ok else "LOSS"
        return None
    return ev


def date_min(legs: list[dict[str, Any]]) -> str:
    dates = sorted(norm(x.get("date"))[:10] for x in legs if norm(x.get("date")))
    return dates[0] if dates else "inconnue"


def cle(scenario: str, legs: list[dict[str, Any]]) -> str:
    return f"{date_min(legs)}|{scenario}"


def jambe(x: dict[str, Any]) -> dict[str, Any]:
    return {k: x.get(k) for k in ("match_id", "marche", "cote", "probabilite_estimee", "source", "rang", "domicile", "exterieur", "date")} | {"resultat": None}


def snapshot_analyse(a: dict[str, Any] | None) -> dict[str, Any] | None:
    if not a:
        return None
    return {k: a.get(k) for k in ("paris", "paris_justes_attendus", "plans", "meilleur_plan", "plan_le_plus_regulier", "plan_marge_max", "rentable")}


def a_un_score(entry: dict[str, Any], scores: dict[str, Any]) -> bool:
    return any(norm(j.get("match_id")) in scores for j in entry.get("jambes", []))


def enregistre(historique: list[dict[str, Any]], tickets: dict[str, Any], scores: dict[str, Any], maintenant: str) -> list[dict[str, Any]]:
    """Ajoute les tickets du jour. Une entrée encore PENDING et sans score connu est remplacée par la version
    la plus récente ; dès qu'un score existe ou que le ticket est réglé, elle est figée."""
    index = {e["cle"]: e for e in historique if isinstance(e, dict) and e.get("cle")}
    for t in tickets.get("scenarios", []) or []:
        sel = t.get("selection") or []
        if t.get("statut") != "OK" or not sel or not t.get("analyse"):
            continue
        k = cle(t["scenario"], sel)
        old = index.get(k)
        if old and (old.get("statut") != "PENDING" or a_un_score(old, scores)):
            continue
        index[k] = {
            "cle": k,
            "scenario": t["scenario"],
            "date": date_min(sel),
            "genere_le": tickets.get("genere_le") or maintenant,
            "statut": "PENDING",
            "cote_totale": (t.get("metrics") or {}).get("cote_totale"),
            "jambes": [jambe(x) for x in sel],
            "analyse": snapshot_analyse(t["analyse"]),
            "resultat": None,
        }
    return sorted(index.values(), key=lambda e: (e["date"], e["scenario"]))


def regle_plan(plan: dict[str, Any], gagnantes: list[bool]) -> dict[str, Any]:
    """Résultat réel d'un plan : mise au prorata de 1/cote, retour = Σ mise × cote des tickets gagnants."""
    gagnants = 0
    retour = 0.0
    for t in plan["composition"]:
        if all(gagnantes[i] for i in t["paris"]):
            gagnants += 1
            retour += t["mise"] * t["cote"]
    return {"nom": plan["nom"], "tickets_gagnants": gagnants, "retour": round(retour, 4),
            "profit": round(retour - 1.0, 4), "rentable": retour >= 1.0 - 1e-3}


def regle(entry: dict[str, Any], scores: dict[str, Any], evaluer: Callable[[str, int, int], str | None]) -> dict[str, Any]:
    """Règle un ticket. EXCLU si un pari est annulé/non reconnu (les cotes ne sont plus celles du plan)."""
    if entry.get("statut") in ("RESOLVED", "EXCLU"):
        return entry
    statuts: list[str | None] = []
    for j in entry["jambes"]:
        sc = scores.get(norm(j.get("match_id")))
        s = evaluer(norm(j.get("marche")), sc[0], sc[1]) if sc else None
        j["resultat"] = s if sc else None
        statuts.append(s if sc else "SANS_SCORE")
    if any(s not in ("WIN", "LOSS", "SANS_SCORE") for s in statuts):
        entry["statut"] = "EXCLU"
        entry["resultat"] = {"raison": "pari annulé ou marché non reconnu"}
        return entry
    if any(s == "SANS_SCORE" for s in statuts):
        return entry
    gagnantes = [s == "WIN" for s in statuts]
    plans = (entry.get("analyse") or {}).get("plans") or []
    entry["statut"] = "RESOLVED"
    entry["resultat"] = {
        "paris_justes": sum(gagnantes),
        "erreurs": len(gagnantes) - sum(gagnantes),
        "plans": [regle_plan(p, gagnantes) for p in plans],
    }
    return entry


def bilan(historique: list[dict[str, Any]], maintenant: str) -> dict[str, Any]:
    comptes = {"total": len(historique), "regles": 0, "en_attente": 0, "exclus": 0}
    par_scenario: dict[str, dict[str, Any]] = {}
    legs_vus: dict[tuple, dict[str, Any]] = {}
    for e in historique:
        st = e.get("statut")
        if st == "RESOLVED":
            comptes["regles"] += 1
        elif st == "EXCLU":
            comptes["exclus"] += 1
        else:
            comptes["en_attente"] += 1
            continue
        if st != "RESOLVED":
            continue
        analyse = e.get("analyse") or {}
        s = par_scenario.setdefault(e["scenario"], {"tickets": 0, "justes_attendus": 0.0, "justes_observes": 0,
                                                    "paris": 0, "erreurs": {}, "plans": {}})
        res = e["resultat"]
        s["tickets"] += 1
        s["paris"] += analyse.get("paris") or len(e["jambes"])
        s["justes_attendus"] += analyse.get("paris_justes_attendus") or 0.0
        s["justes_observes"] += res["paris_justes"]
        s["erreurs"][str(res["erreurs"])] = s["erreurs"].get(str(res["erreurs"]), 0) + 1
        prevus = {p["nom"]: p for p in analyse.get("plans") or []}
        for r in res["plans"]:
            pl = s["plans"].setdefault(r["nom"], {"tickets": 0, "rentables": 0, "profit_total": 0.0,
                                                  "proba_profit_prevue": 0.0, "esperance_prevue": 0.0})
            pv = prevus.get(r["nom"]) or {}
            pl["tickets"] += 1
            pl["rentables"] += 1 if r["rentable"] else 0
            pl["profit_total"] += r["profit"]
            pl["proba_profit_prevue"] += pv.get("proba_profit") or 0.0
            pl["esperance_prevue"] += pv.get("esperance_gain") or 0.0
        for j in e["jambes"]:
            if j.get("resultat") in ("WIN", "LOSS") and num(j.get("probabilite_estimee")) is not None:
                legs_vus[(norm(j.get("match_id")), norm(j.get("marche")), norm(j.get("source")))] = j
    scenarios = {}
    for nom, s in par_scenario.items():
        n = s["tickets"]
        scenarios[nom] = {
            "tickets_regles": n,
            "paris": s["paris"],
            "justes_attendus": round(s["justes_attendus"], 2),
            "justes_observes": s["justes_observes"],
            "erreurs": dict(sorted(s["erreurs"].items(), key=lambda kv: int(kv[0]))),
            "plans": {
                pn: {
                    "tickets_regles": p["tickets"],
                    "taux_rentable_observe": round(p["rentables"] / p["tickets"], 4),
                    "proba_profit_prevue": round(p["proba_profit_prevue"] / p["tickets"], 4),
                    "roi_observe": round(p["profit_total"] / p["tickets"], 4),
                    "esperance_prevue": round(p["esperance_prevue"] / p["tickets"], 4),
                } for pn, p in sorted(s["plans"].items())
            },
        }
    par_source: dict[str, dict[str, Any]] = {}
    for (_, _, src), j in legs_vus.items():
        d = par_source.setdefault(src or "inconnue", {"paris": 0, "justes": 0, "proba": 0.0})
        d["paris"] += 1
        d["justes"] += 1 if j["resultat"] == "WIN" else 0
        d["proba"] += num(j["probabilite_estimee"]) or 0.0
    sources = {k: {"paris": d["paris"], "taux_reussite": round(d["justes"] / d["paris"], 4),
                   "proba_moyenne_estimee": round(d["proba"] / d["paris"], 4)} for k, d in sorted(par_source.items())}
    return {"version": 1, "genere_le": maintenant, "comptes": comptes, "par_scenario": scenarios, "par_source": sources,
            "avertissement": "Petits échantillons : un écart entre prévu et observé n'est significatif qu'avec beaucoup de tickets réglés."}


def met_a_jour(tickets: dict[str, Any], historique: list[dict[str, Any]], scores: dict[str, Any],
               evaluer: Callable[[str, int, int], str | None], maintenant: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    h = enregistre(historique, tickets, scores, maintenant)
    h = [regle(e, scores, evaluer) for e in h]
    return h, bilan(h, maintenant)


def main() -> int:
    maintenant = dt.datetime.now(dt.timezone.utc).isoformat()
    tickets = load_json(TICKETS, {}) or {}
    ancien = load_json(HISTORIQUE, []) or []
    if not isinstance(ancien, list):
        ancien = []
    h, b = met_a_jour(tickets, ancien, score_history(), evaluateur_defaut(), maintenant)
    HISTORIQUE.parent.mkdir(parents=True, exist_ok=True)
    HISTORIQUE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")
    BILAN.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(b["comptes"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
