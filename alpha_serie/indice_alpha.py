"""Onglet « Indice Alpha » (26/10/2026, demande de Patrick) : un seul endroit pour consulter les indices de réussite de chaque marché.

Ce module NE CALCULE AUCUN pronostic et ne touche ni au moteur (`coeur.py`), ni aux tickets : il LIT les journaux gelés (`journal.jsonl` pour les bandes
1X2, `tickets_journal.jsonl` pour le « Plus de 1,5 » à chances maximales) et écrit `data/alpha_serie/indice_alpha.json`, que la page `indice_alpha.html` affiche.

Trois fichiers, trois rôles, jamais mélangés :
- `indices_registre.json` : les règles et leur état (en étude / en validation / validé), un indice = une entrée indépendante, avec l'historique de
  ses modifications. Une modification de règle ou de statut sans ligne d'historique correspondante est signalée (`alerte_registre`).
- les journaux gelés : les résultats réels (gel avant le coup d'envoi, défaites comprises) ;
- `reference_rejeu` : les chiffres de l'étude historique, présentés À PART et jamais additionnés au suivi réel.

Vue globale : un pari = un couple (match, indice). Un pari n'est compté qu'une fois ; les pourcentages des indices ne sont jamais additionnés ; le taux
global est celui des paris distincts réglés, avec les matchs concernés par plusieurs indices signalés.
Bibliothèque standard seulement.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import suivi, tickets

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "alpha_serie"
REGISTRE = DOSSIER / "indices_registre.json"
SORTIE = DOSSIER / "indice_alpha.json"
STATUTS = ("en_etude", "en_validation", "valide")
LIBELLE_STATUT = {"en_etude": "En étude", "en_validation": "En validation", "valide": "Validé"}


# --- statistiques --------------------------------------------------------------------------------------------------------------------------

def _semaine(jour: str) -> str:
    a = date.fromisoformat(jour).isocalendar()
    return "%d-S%02d" % (a[0], a[1])


def _bloc(g: int, n: int) -> dict[str, Any]:
    return {"matchs": n, "gagnes": g, "perdus": n - g, "taux": round(g / n, 4) if n else None, "wilson_bas_95": suivi.wilson_bas(g, n)}


def _par_semaine(paris: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Résultats de chaque semaine ISO, puis cumulés semaine après semaine."""
    sem: dict[str, list[bool]] = {}
    for p in paris:
        sem.setdefault(_semaine(p["date"]), []).append(p["gagne"])
    hebdo, cumul, n_c, g_c = [], [], 0, 0
    for k in sorted(sem):
        g, n = sum(sem[k]), len(sem[k])
        n_c, g_c = n_c + n, g_c + g
        hebdo.append({"semaine": k, **_bloc(g, n)})
        cumul.append({"semaine": k, **_bloc(g_c, n_c)})
    return hebdo, cumul


def _tendance(hebdo: list[dict[str, Any]]) -> dict[str, Any]:
    """Dernière semaine mesurée contre le cumul des semaines précédentes. « baisse » seulement si le taux de la dernière semaine passe sous la
    borne basse (95 %) du cumul précédent : aucun seuil posé à la main."""
    if len(hebdo) < 2:
        return {"signal": "insuffisant", "texte": "Moins de deux semaines mesurées : aucune tendance."}
    der, avant_g, avant_n = hebdo[-1], sum(h["gagnes"] for h in hebdo[:-1]), sum(h["matchs"] for h in hebdo[:-1])
    bas = suivi.wilson_bas(avant_g, avant_n)
    if bas is not None and der["taux"] is not None and der["taux"] < bas:
        return {"signal": "baisse", "semaine": der["semaine"], "taux_semaine": der["taux"], "borne_basse_cumul_precedent": bas,
                "texte": "La dernière semaine est sous la borne basse du cumul précédent."}
    return {"signal": "stable", "semaine": der["semaine"], "taux_semaine": der["taux"], "borne_basse_cumul_precedent": bas,
            "texte": "Pas de baisse détectée (la dernière semaine reste dans l'intervalle du cumul précédent)."}


# --- sources (journaux gelés) --------------------------------------------------------------------------------------------------------------

def _source_bandes(regle: str, journal: Path = suivi.JOURNAL) -> dict[str, Any]:
    lignes = suivi._lire(journal)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat_bande" and l["regle"] == regle}
    vus: dict[str, dict] = {}
    doublons = 0
    for l in lignes:
        if l["type"] == "bande" and l["regle"] == regle:
            doublons += l["match_id"] in vus
            vus.setdefault(l["match_id"], l)
    paris = [{"id": ("%s|%s" % (k, regle)), "match_id": k, "date": l["date"], "gagne": res[k]["gagne"], "cote": l["cote"],
              "analyse_alpha": bool(l.get("analyse_alpha"))} for k, l in vus.items() if k in res]
    return {"geles": list(vus.values()), "paris": paris, "doublons": doublons, "dates_gelees": [l["date"] for l in vus.values()],
            "gel_apres_coup_d_envoi": sum(1 for l in vus.values() if not l.get("coup_d_envoi_utc") or l["gele_le"] >= l["coup_d_envoi_utc"])}


def _source_plus15_max(journal: Path = tickets.JOURNAL) -> dict[str, Any]:
    """« Plus de 1,5 » à chances maximales gelés dans les tickets (un match compté une fois, quel que soit le palier). Suivi limité aux paris
    qui sont réellement entrés dans un ticket gelé (cote BetPawa connue, créneau de 10 h à minuit)."""
    lignes = tickets._lire(journal)
    res = {l["jour"]: l for l in lignes if l["type"] == "resultat_tickets"}
    gel = {l["jour"]: l for l in lignes if l["type"] == "tickets"}
    geles: dict[tuple, dict] = {}
    regles: dict[tuple, bool] = {}
    for j, g in gel.items():
        for p in tickets.PALIERS:
            for i, c in enumerate(g.get(p, [])):
                if not c.get("chances_max"):
                    continue
                k = (j, c["match_id"])
                geles.setdefault(k, {"date": j, "match_id": c["match_id"], "cote": c.get("cote"), "gele_le": g.get("gele_le")})
                ok = (res.get(j) or {}).get(p, [])
                if i < len(ok) and ok[i] is not None:
                    regles[k] = bool(ok[i])
    paris = [{"id": "%s|%s|plus15" % (k[1], k[0]), "match_id": k[1], "date": k[0], "gagne": v, "cote": geles[k]["cote"]} for k, v in regles.items()]
    return {"geles": list(geles.values()), "paris": paris, "doublons": 0, "dates_gelees": [g["date"] for g in geles.values()], "gel_apres_coup_d_envoi": 0}


def _source_regle(marche: str, journal: Path = suivi.JOURNAL) -> dict[str, Any]:
    """Configuration découverte (decouverte.py) : seules les lignes gelées avec l'empreinte de la règle ACTUELLE comptent ; une règle modifiée repart de zéro."""
    regle = suivi.regles_decouvertes().get(marche)
    emp = suivi.empreinte_regle(regle) if regle else None
    lignes = suivi._lire(journal)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat_indice_regle" and l["indice"] == marche and l.get("empreinte_regle") == emp}
    vus: dict[str, dict] = {}
    doublons = 0
    for l in lignes:
        if l["type"] == "indice_regle" and l["indice"] == marche and l.get("empreinte_regle") == emp:
            doublons += l["match_id"] in vus
            vus.setdefault(l["match_id"], l)
    paris = [{"id": "%s|%s" % (k, marche), "match_id": k, "date": l["date"], "gagne": res[k]["gagne"], "cote": l.get("cote_betpawa")} for k, l in vus.items() if k in res]
    return {"geles": list(vus.values()), "paris": paris, "doublons": doublons, "dates_gelees": [l["date"] for l in vus.values()],
            "gel_apres_coup_d_envoi": sum(1 for l in vus.values() if not l.get("coup_d_envoi_utc") or l["gele_le"] >= l["coup_d_envoi_utc"])}


SOURCES: dict[str, Callable[[str], dict[str, Any]]] = {
    "regle": lambda arg: _source_regle(arg),
    "bandes": lambda arg: _source_bandes(arg),
    "plus15_max": lambda arg: _source_plus15_max(),
}


# --- registre : seuils réels, empreinte, historique -----------------------------------------------------------------------------------------

def charger_registre(fichier: Path = REGISTRE) -> dict[str, Any]:
    return json.loads(fichier.read_text(encoding="utf-8"))


def _json(fichier: Path) -> dict[str, Any]:
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))
    except Exception:
        return {}


def seuils_reels(indice: dict[str, Any]) -> dict[str, Any]:
    """Les seuils viennent du fichier de règles que le moteur de suivi lit VRAIMENT (une seule source de vérité), jamais recopiés dans le registre."""
    nature, _, arg = str(indice.get("source", "")).partition(":")
    if nature == "bandes":
        r = (_json(suivi.BANDES).get("regles") or {}).get(arg) or {}
        return {"cote_min": r.get("cote_min"), "cote_max": r.get("cote_max"), "bornes": r.get("bornes"), "probabilite_min": None,
                "source_cotes": "BetPawa"}
    if nature == "regle":
        r = suivi.regles_decouvertes().get(arg)
        if not r:
            return {}
        from . import decouverte
        return {"conditions": r["regle"], "conditions_texte": decouverte.texte_conditions(r["regle"]), "empreinte_regle": suivi.empreinte_regle(r), "probabilite_min": None,
                "cote_min": None, "cote_max": None, "source_cotes": "BetPawa (cote enregistrée pour information, non filtrante)"}
    if nature == "plus15_max":
        f = _json(tickets.PLUS15)
        return {"total_attendu_min": f.get("palier_total_attendu"), "cote_min": f.get("cote_min"), "cote_max": None, "probabilite_min": None,
                "source_cotes": "BetPawa"}
    return {}


def empreinte(indice: dict[str, Any]) -> str:
    """Empreinte de ce qui définit l'indice : statut, source, conditions, objectif et seuils réels. Change dès qu'une règle change."""
    fond = {"statut": indice.get("statut"), "source": indice.get("source"), "conditions": indice.get("conditions"),
            "objectif_reussite": indice.get("objectif_reussite"), "seuils": seuils_reels(indice)}
    return hashlib.sha256(json.dumps(fond, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def verifier_registre(registre: dict[str, Any]) -> list[str]:
    """Anomalies du registre : indice dupliqué, statut inconnu, modification de règle ou de statut non tracée dans son historique."""
    alertes, vus = [], set()
    for i in registre.get("indices", []):
        if i.get("id") in vus:
            alertes.append("%s : identifiant en double" % i.get("id"))
        vus.add(i.get("id"))
        if i.get("statut") not in STATUTS:
            alertes.append("%s : statut inconnu (%s)" % (i.get("id"), i.get("statut")))
        hist = i.get("modifications") or []
        if not hist:
            alertes.append("%s : aucune ligne d'historique" % i.get("id"))
        elif hist[-1].get("empreinte_apres") != empreinte(i):
            alertes.append("%s : règle, seuil ou statut modifié sans ligne d'historique correspondante" % i.get("id"))
    return alertes


# --- rapport par indice -------------------------------------------------------------------------------------------------------------------

def _reference(indice: dict[str, Any]) -> dict[str, Any] | None:
    nature, _, arg = str(indice.get("source", "")).partition(":")
    if nature == "plus15_max":
        t = _json(tickets.PLUS15)
        x = t.get("tous")
        if x:
            return {"nature": "Rejeu historique (non gelé, observé avant la règle) : ce n'est PAS le suivi réel.", "matchs": x.get("matchs"),
                    "gagnes": x.get("reussis"), "taux": x.get("reussite"), "wilson_bas_95": x.get("wilson_bas"),
                    "periode": "bloc Football-Data 2025-2026 + archive ARCHETYPE", "source": t.get("source")}
    if nature == "regle":
        r = suivi.regles_decouvertes().get(arg)
        c = (r or {}).get("verification_C")
        if c:
            return {"nature": "Vérification chronologique de la recherche (règle apprise sur 2025, retenue sur janvier–mars 2026, vérifiée depuis le 01/04/2026) : ce n'est PAS le suivi réel.",
                    "matchs": c["matchs"], "gagnes": c["gagnes"], "taux": c["taux"], "wilson_bas_95": c["wilson_bas_95"],
                    "periode": "depuis le 01/04/2026", "source": "taux de base du marché sur la même période : %.1f %%" % (100 * r["taux_de_base_C"])}
    if nature == "bandes":
        ref = (_json(suivi.BANDES).get("reference_etude") or {}).get(arg, {}).get("tous_matchs_de_la_bande")
        if ref:
            return {"nature": "Fenêtre BetPawa observée AVANT le gel de la règle : point de départ, PAS une validation.", "matchs": ref["matchs"],
                    "gagnes": ref["gagnes"], "taux": round(ref["gagnes"] / ref["matchs"], 4), "wilson_bas_95": suivi.wilson_bas(ref["gagnes"], ref["matchs"]),
                    "periode": "28/09 – 25/10/2026"}
    return None


def _fiabilite(indice: dict[str, Any], mesure: dict[str, Any]) -> dict[str, str]:
    """Aucun indice n'est présenté comme fiable sans validation explicite ET sans que sa borne basse réelle atteigne son objectif."""
    obj, bas = indice.get("objectif_reussite"), mesure["wilson_bas_95"]
    if indice.get("statut") != "valide":
        return {"niveau": "non_fiable", "texte": "Pas encore fiable : %s." % LIBELLE_STATUT.get(indice.get("statut"), "statut inconnu").lower()}
    if bas is None:
        return {"niveau": "non_fiable", "texte": "Marqué validé mais aucun pari réglé : rien ne le prouve."}
    if obj is not None and bas < obj:
        return {"niveau": "a_confirmer", "texte": "Validé, mais la borne basse réelle (%.0f %%) est sous l'objectif (%.0f %%)." % (100 * bas, 100 * obj)}
    return {"niveau": "fiable", "texte": "Validé, borne basse réelle au niveau de l'objectif."}


def rapport_indice(indice: dict[str, Any], sources: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    nature, _, arg = str(indice.get("source", "")).partition(":")
    src = (sources or {}).get(indice["id"]) or (SOURCES[nature](arg) if nature in SOURCES else {"geles": [], "paris": [], "doublons": 0, "dates_gelees": [],
                                                                                                "gel_apres_coup_d_envoi": 0})
    paris = src["paris"]
    g, n = sum(p["gagne"] for p in paris), len(paris)
    mesure = _bloc(g, n)
    hebdo, cumul = _par_semaine(paris)
    dates = sorted(src["dates_gelees"])
    jours = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1 if dates else 0
    out = {"id": indice["id"], "nom": indice["nom"], "famille": indice.get("famille"), "marche": indice.get("marche"),
           "statut": indice.get("statut"), "statut_libelle": LIBELLE_STATUT.get(indice.get("statut"), "?"), "conditions": indice.get("conditions"),
           "seuils": seuils_reels(indice), "objectif_reussite": indice.get("objectif_reussite"), "limites": indice.get("limites"),
           "geles": len(src["geles"]), "en_attente": len(src["geles"]) - n, **mesure,
           "periode": {"debut": dates[0] if dates else None, "fin": dates[-1] if dates else None, "jours": jours},
           "par_jour": round(len(src["geles"]) / jours, 2) if jours else None,
           "par_semaine": hebdo, "cumule_par_semaine": cumul, "tendance": _tendance(hebdo),
           "reference_rejeu": _reference(indice), "fiabilite": _fiabilite(indice, mesure),
           "controles": {"doublons": src["doublons"], "gels_non_anterieurs_au_coup_d_envoi": src["gel_apres_coup_d_envoi"]},
           "empreinte": empreinte(indice), "modifications": indice.get("modifications") or []}
    if nature == "bandes":
        a = [p for p in paris if p.get("analyse_alpha")]
        out["dont_analyses_par_alpha"] = _bloc(sum(p["gagne"] for p in a), len(a))
    return out


# --- vue globale ------------------------------------------------------------------------------------------------------------------------

def vue_globale(rapports: list[dict[str, Any]], paris_par_indice: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Paris DISTINCTS réglés (un couple match + indice une seule fois). Les pourcentages des indices ne sont jamais additionnés."""
    distincts: dict[str, dict] = {}
    ecartes = 0
    for iid, lst in paris_par_indice.items():
        for p in lst:
            k = "%s|%s" % (iid, p["match_id"])
            if k in distincts:
                ecartes += 1
                continue
            distincts[k] = {**p, "indice": iid}
    par_match: dict[str, set] = {}
    for k, p in distincts.items():
        par_match.setdefault(p["match_id"], set()).add(p["indice"])
    paris = list(distincts.values())
    hebdo, _ = _par_semaine(paris)
    g = sum(p["gagne"] for p in paris)
    classe = sorted(rapports, key=lambda r: (r["wilson_bas_95"] is None, -(r["wilson_bas_95"] or 0)))
    return {"paris_distincts": _bloc(g, len(paris)), "matchs_distincts": len(par_match),
            "matchs_avec_plusieurs_indices": sum(1 for s in par_match.values() if len(s) > 1), "doublons_ecartes": ecartes,
            "par_semaine": hebdo,
            "classement": [{"id": r["id"], "nom": r["nom"], "statut": r["statut"], "statut_libelle": r["statut_libelle"], "matchs": r["matchs"],
                            "gagnes": r["gagnes"], "perdus": r["perdus"], "taux": r["taux"], "wilson_bas_95": r["wilson_bas_95"],
                            "par_jour": r["par_jour"], "periode": r["periode"], "tendance": r["tendance"]["signal"],
                            "fiabilite": r["fiabilite"]["niveau"], "en_attente": r["en_attente"]} for r in classe],
            "indices_en_baisse": [r["id"] for r in rapports if r["tendance"]["signal"] == "baisse"],
            "note": "Taux calculé sur des paris distincts (un match n'est compté qu'une fois par indice). Les pourcentages des indices ne sont pas additionnés "
                    "et le taux global ne remplace pas la lecture marché par marché."}


def construire(registre_fichier: Path = REGISTRE, sortie: Path | None = SORTIE, sources: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    registre = charger_registre(registre_fichier)
    rapports, paris = [], {}
    for i in registre["indices"]:
        nature, _, arg = str(i.get("source", "")).partition(":")
        src = (sources or {}).get(i["id"]) or (SOURCES[nature](arg) if nature in SOURCES else None)
        rapports.append(rapport_indice(i, {i["id"]: src} if src else None))
        paris[i["id"]] = (src or {}).get("paris", [])
    out = {"genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "avertissement": registre.get("avertissement"),
           "alerte_registre": verifier_registre(registre), "global": vue_globale(rapports, paris), "indices": rapports}
    if sortie is not None:
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--empreinte":
        print(next(empreinte(i) for i in charger_registre()["indices"] if i["id"] == sys.argv[2]))
        raise SystemExit
    r = construire()
    print(json.dumps({"alerte_registre": r["alerte_registre"], "global": r["global"]["paris_distincts"],
                      "indices": [(x["id"], x["geles"], x["matchs"]) for x in r["indices"]]}, ensure_ascii=False, indent=1))
