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
RE_HANDICAP3 = re.compile(r"^handicap3_domicile_(-?\d+(?:\.\d+)?)_(1|X|2)$")
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

    try:
        from moteur_v3.markets import gagne as gagne_v3
    except Exception:
        gagne_v3 = None

    def ev(marche: str, h: int, a: int) -> str | None:
        # AJOUT 12/10/2026 (audit) : « handicap3_domicile_{t}_{issue} » (nom produit par moteur_v3_pipeline.nom_site pour
        # le handicap à 3 choix) n'était reconnu par aucun évaluateur : 2 tickets sur 8 réglés étaient EXCLUS pour ce seul
        # motif. Il correspond à la clé V3 « handicap_{-t}_{issue} », réglée par la V3 elle-même.
        m3 = RE_HANDICAP3.match(marche or "")
        if m3 and gagne_v3:
            r = gagne_v3(f"handicap_{-float(m3.group(1)):g}_{m3.group(2)}", h, a)
            return None if r is None else ("WIN" if r else "LOSS")
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
    # AJOUT 12/10/2026 (audit) : « journal_team » est gardé pour régler « Victoire » / « Ne perd pas » du Journal
    # (le libellé seul ne dit pas de quelle équipe il s'agit).
    return {k: x.get(k) for k in ("match_id", "marche", "cote", "probabilite_estimee", "source", "rang", "domicile", "exterieur", "date",
                                  "journal_team")} | {"resultat": None}


def snapshot_analyse(a: dict[str, Any] | None) -> dict[str, Any] | None:
    if not a:
        return None
    return {k: a.get(k) for k in ("paris", "paris_justes_attendus", "plans", "meilleur_plan", "plan_le_plus_regulier", "plan_marge_max", "rentable")}


def a_un_score(entry: dict[str, Any], scores: dict[str, Any]) -> bool:
    return any(norm(j.get("match_id")) in scores for j in entry.get("jambes", []))


def portee(legs: list[dict[str, Any]]) -> str:
    """« meme_jour » : tous les matchs du ticket sont du même jour ; « melange » : dates différentes."""
    return "meme_jour" if len({norm(x.get("date"))[:10] for x in legs}) <= 1 else "melange"


def _empreinte(legs: list[dict[str, Any]]) -> frozenset:
    return frozenset((norm(x.get("match_id")) or norm(x.get("domicile")), norm(x.get("marche"))) for x in legs)


def tickets_a_suivre(tickets: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(clé, ticket) à enregistrer. Ajout 14/10/2026 (demande de Patrick) : en plus des tickets de la plus large plage
    (clés inchangées, `date|scénario`), on suit ceux de la plage du seul jour présent (clé `date|scénario|jour`), qui
    sont tous du même jour. Un ticket du jour identique (mêmes paris) à celui de la plage large n'est pas compté deux fois."""
    out: list[tuple[str, dict[str, Any]]] = []
    larges: dict[str, frozenset] = {}
    for t in tickets.get("scenarios", []) or []:
        sel = t.get("selection") or []
        if t.get("statut") == "OK" and sel and t.get("analyse"):
            k = cle(t["scenario"], sel)
            larges[t["scenario"]] = _empreinte(sel)
            out.append((k, t))
    plages = tickets.get("plages") or []
    if plages:
        for t in plages[0].get("scenarios", []) or []:
            sel = t.get("selection") or []
            if t.get("statut") != "OK" or not sel or not t.get("analyse"):
                continue
            if larges.get(t["scenario"]) == _empreinte(sel):
                continue
            out.append((cle(t["scenario"], sel) + "|jour", t))
    return out


def enregistre(historique: list[dict[str, Any]], tickets: dict[str, Any], scores: dict[str, Any], maintenant: str) -> list[dict[str, Any]]:
    """Ajoute les tickets du jour. Une entrée encore PENDING et sans score connu est remplacée par la version
    la plus récente ; dès qu'un score existe ou que le ticket est réglé, elle est figée."""
    index = {e["cle"]: e for e in historique if isinstance(e, dict) and e.get("cle")}
    for k, t in tickets_a_suivre(tickets):
        sel = t.get("selection") or []
        old = index.get(k)
        if old and (old.get("statut") != "PENDING" or a_un_score(old, scores)):
            continue
        index[k] = {
            "cle": k,
            "scenario": t["scenario"],
            "date": date_min(sel),
            "portee": portee(sel),
            "genere_le": tickets.get("genere_le") or maintenant,
            "statut": "PENDING",
            "cote_totale": (t.get("metrics") or {}).get("cote_totale"),
            "jambes": [jambe(x) for x in sel],
            "analyse": snapshot_analyse(t["analyse"]),
            "resultat": None,
        }
    return sorted(index.values(), key=lambda e: (e["date"], e["scenario"], e["cle"]))


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


def index_par_nom(matchs: list[dict[str, Any]] | None) -> dict[tuple, tuple[int, int]]:
    """Matchs terminés indexés par (date, domicile, extérieur) normalisés -- même clé que l'archive de sélection
    (suivi_selection_generateur.index_matchs). Équipes inversées = autre match."""
    import generateur_tickets as gt
    out: dict[tuple, tuple[int, int]] = {}
    for m in matchs or []:
        b = m.get("buts")
        if not b:
            continue
        out[(norm(m.get("date")), gt._nom_normalise(m.get("domicile")), gt._nom_normalise(m.get("exterieur")))] = (int(b[0]), int(b[1]))
    return out


def equipes_journal(archive_selection: dict[str, Any] | None) -> dict[tuple, str]:
    """(date, domicile, extérieur, marché) -> équipe suivie, lue dans l'archive des paris du générateur. Sert aux tickets
    enregistrés avant le 12/10 (leurs jambes n'ont pas « journal_team »)."""
    import generateur_tickets as gt
    out: dict[tuple, str] = {}
    for e in (archive_selection or {}).get("executions") or []:
        for p in e.get("paris") or []:
            if p.get("journal_team"):
                out[(norm(p.get("date")), gt._nom_normalise(p.get("domicile")), gt._nom_normalise(p.get("exterieur")),
                     norm(p.get("marche")))] = p["journal_team"]
    return out


def _score_jambe(j: dict[str, Any], scores: dict[str, Any], par_nom: dict[tuple, tuple[int, int]] | None):
    sc = scores.get(norm(j.get("match_id")))
    if sc or not par_nom:
        return sc
    import generateur_tickets as gt
    return par_nom.get((norm(j.get("date")), gt._nom_normalise(j.get("domicile")), gt._nom_normalise(j.get("exterieur"))))


def _evalue_jambe(j: dict[str, Any], h: int, a: int, evaluer: Callable[[str, int, int], str | None],
                  equipes: dict[tuple, str] | None) -> str | None:
    """Nom tel quel, puis nom canonique (libellés du Journal : « Match à moins de 3,5 buts », « Ne perd pas »...)."""
    s = evaluer(norm(j.get("marche")), h, a)
    if s in ("WIN", "LOSS") or str(j.get("source") or "").lower() != "journal":
        return s
    import generateur_tickets as gt
    p = dict(j)
    if not p.get("journal_team") and equipes:
        p["journal_team"] = equipes.get((norm(j.get("date")), gt._nom_normalise(j.get("domicile")),
                                         gt._nom_normalise(j.get("exterieur")), norm(j.get("marche"))))
    canon = gt.marche_canonique(p)
    essais = [canon] + ([canon[:-2] + canon[-2:].upper()] if canon.startswith("double_chance_") else [])
    for nom in essais:
        r = evaluer(nom, h, a)
        if r in ("WIN", "LOSS"):
            return r
    return s


def regle(entry: dict[str, Any], scores: dict[str, Any], evaluer: Callable[[str, int, int], str | None],
          par_nom: dict[tuple, tuple[int, int]] | None = None, equipes: dict[tuple, str] | None = None) -> dict[str, Any]:
    """Règle un ticket. EXCLU si un pari est annulé/non reconnu (les cotes ne sont plus celles du plan).

    CORRECTIF 12/10/2026 (audit) : les paris du Journal n'ont pas de match_id ; ils sont retrouvés par date + noms
    (`par_nom`) et leur libellé est traduit en nom canonique. Avant, tout ticket contenant un pari du Journal restait
    PENDING pour toujours (limite notée dans docs/CLAUDE_SELECTION.md)."""
    # Un ticket EXCLU est réévalué : l'exclusion venait d'un marché non reconnu, et le règlement est déterministe.
    if entry.get("statut") == "RESOLVED":
        return entry
    statuts: list[str | None] = []
    for j in entry["jambes"]:
        sc = _score_jambe(j, scores, par_nom)
        s = _evalue_jambe(j, sc[0], sc[1], evaluer, equipes) if sc else None
        j["resultat"] = s if sc else None
        statuts.append(s if sc else "SANS_SCORE")
    if any(s not in ("WIN", "LOSS", "SANS_SCORE") for s in statuts):
        entry["statut"] = "EXCLU"
        entry["resultat"] = {"raison": "pari annulé ou marché non reconnu"}
        return entry
    if any(s == "SANS_SCORE" for s in statuts):
        entry["statut"], entry["resultat"] = "PENDING", None   # un ancien EXCLU redevient en attente
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
    par_portee: dict[str, dict[str, int]] = {}
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
        pp = par_portee.setdefault(e.get("portee") or portee(e["jambes"]), {"tickets_regles": 0, "gagnants": 0, "paris": 0, "justes": 0})
        pp["tickets_regles"] += 1
        pp["gagnants"] += 1 if res["erreurs"] == 0 else 0
        pp["paris"] += len(e["jambes"])
        pp["justes"] += res["paris_justes"]
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
    return {"version": 1, "genere_le": maintenant, "comptes": comptes, "par_scenario": scenarios, "par_portee": dict(sorted(par_portee.items())), "par_source": sources,
            "avertissement": "Petits échantillons : un écart entre prévu et observé n'est significatif qu'avec beaucoup de tickets réglés."}


def met_a_jour(tickets: dict[str, Any], historique: list[dict[str, Any]], scores: dict[str, Any],
               evaluer: Callable[[str, int, int], str | None], maintenant: str,
               matchs: list[dict[str, Any]] | None = None, archive_selection: dict[str, Any] | None = None
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    h = enregistre(historique, tickets, scores, maintenant)
    par_nom, equipes = index_par_nom(matchs), equipes_journal(archive_selection)
    h = [regle(e, scores, evaluer, par_nom, equipes) for e in h]
    return h, bilan(h, maintenant)


def main() -> int:
    maintenant = dt.datetime.now(dt.timezone.utc).isoformat()
    tickets = load_json(TICKETS, {}) or {}
    ancien = load_json(HISTORIQUE, []) or []
    if not isinstance(ancien, list):
        ancien = []
    try:  # matchs terminés de toutes sources, pour retrouver les paris du Journal (sans match_id) par date + noms
        import journal_rentabilite as jr
        matchs = jr.charge_tous_resultats()
    except Exception as exc:  # noqa: BLE001 - les paris avec match_id restent réglés ; l'erreur est affichée
        print(f"[suivi tickets] matchs terminés non lus : {type(exc).__name__}: {exc}")
        matchs = []
    archive_selection = load_json(Path("data/selection_generateur_historique.json"), {}) or {}
    h, b = met_a_jour(tickets, ancien, score_history(), evaluateur_defaut(), maintenant, matchs, archive_selection)
    HISTORIQUE.parent.mkdir(parents=True, exist_ok=True)
    HISTORIQUE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")
    BILAN.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(b["comptes"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
