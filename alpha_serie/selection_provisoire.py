"""Sélection provisoire alpha (26/10/2026, décision de Patrick) : 8 marchés retenus, chacun à son niveau (normal ou maximal).

Règles GELÉES dans data/alpha_serie/selection_provisoire.json (origine : commit 576577e, docs/SELECTION_PROVISOIRE.md sur la branche etude-marches-rigueur).
- Ne recalcule rien d'alpha : part de la liste des marchés ADMIS par coeur.analyser_match (avant le filtre de cote) et la lit seulement.
- Normal = le marché admis par alpha. Maximal = en plus, au plus `echecs_max` match(s) passé(s) où l'événement a échoué dans les paires publiées.
- Cote : cote BetPawa figée au run nocturne (archive du jour), première trouvée dans l'ordre des clés équivalentes, >= cote_min ; sinon rien.
  Multigoals : sans cote BetPawa (la cote est affichée seulement si elle existe).
- Suivi : chaque nuit, gel AVANT le coup d'envoi (jamais regelé, défaites comprises) dans un journal à part, puis résultat et rendement
  séparés. N'écrit que dans ses propres fichiers ; aucun effet sur les pronostics, les tickets, le journal alpha ni les autres moteurs.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import coeur, parametres as P

ROOT = Path(__file__).resolve().parent.parent
REGLES = ROOT / "data" / "alpha_serie" / "selection_provisoire.json"
JOURNAL = ROOT / "data" / "alpha_serie" / "selection_provisoire_journal.jsonl"
PAGE = ROOT / "data" / "alpha_serie" / "selection_provisoire_page.json"


def charger_regles(fichier: Path = REGLES) -> list[dict[str, Any]]:
    return json.loads(fichier.read_text(encoding="utf-8"))["regles"]


def predicat(cle: list[str] | tuple[str, str]):
    g, s = cle
    if g == "multigoals":
        lo, hi = (int(x) for x in s.split("-"))
        return lambda h, a: lo <= h + a <= hi
    return coeur.test_du_marche(g, s)


def echecs(off: list, de: list, pred) -> int | None:
    """Matchs passés où l'événement a échoué. Équipe qui reçoit : (marqués off[i][0], encaissés de[i][1]) ; équipe qui se déplace :
    (encaissés de[i][0], marqués off[i][1]) en score domicile-extérieur. None si les paires manquent."""
    if not off or len(off) != len(de):
        return None
    return sum(not pred(o[0], d[1]) for o, d in zip(off, de)) + sum(not pred(d[0], o[1]) for o, d in zip(off, de))


def _cote(cotes: dict | None, cles: list[list[str]]) -> float | None:
    for c in cles:
        v = coeur.cote_de(cotes, tuple(c))
        if v:
            return round(float(v), 2)
    return None


def selections(r: dict[str, Any], cotes: dict | None, regles: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """r = résultat de coeur.analyser_match (marchés admis par alpha). Retourne les pronostics de la sélection provisoire pour ce match."""
    if r.get("statut") != "analyse":
        return []
    regles = regles if regles is not None else charger_regles()
    admis = {tuple(f["cle"]): f for o in ("buts", "equipes") for f in (r.get("onglets") or {}).get(o) or []}
    out = []
    for regle in regles:
        cle = next((tuple(c) for c in regle["cles"] if tuple(c) in admis), None)
        if cle is None:
            continue                                            # alpha ne publie pas ce marché pour ce match
        n_echecs = echecs(r.get("scenarios_offensifs") or [], r.get("scenarios_defensifs") or [], predicat(regle["cles"][0]))
        if regle["niveau"] == "maximal" and (n_echecs is None or n_echecs > regle["echecs_max"]):
            continue
        cote = _cote(cotes, regle["cles"])
        if not regle["sans_cote"] and (cote is None or cote < regle["cote_min"] - 1e-9):
            continue                                            # pas de cote figée exploitable : rien n'est affiché
        out.append({"regle": regle["id"], "marche": regle["nom"], "cle": list(cle), "niveau": regle["niveau"], "cote": cote, "echecs": n_echecs})
    return out


def _coup_d_envoi(m: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(m["coup_d_envoi_utc"]).replace("Z", "+00:00"))
    except Exception:
        return None


def _lire(journal: Path) -> list[dict[str, Any]]:
    if not journal.exists():
        return []
    return [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()]


def _ajouter(journal: Path, lignes: list[dict[str, Any]]) -> None:
    if not lignes:
        return
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n")


def geler(matchs: list[dict[str, Any]], maintenant: datetime | None = None, journal: Path = JOURNAL, params: dict | None = None,
          regles: list[dict[str, Any]] | None = None) -> int:
    """Gèle chaque pronostic de la sélection AVANT le coup d'envoi, avec sa cote figée ; un enregistrement par (match, règle), jamais regelé."""
    maintenant = maintenant or datetime.now(timezone.utc)
    params = params or P.charger()
    regles = regles if regles is not None else charger_regles()
    deja = {(l["match_id"], l["regle"]) for l in _lire(journal) if l["type"] == "selection"}
    nouveaux = []
    for m in matchs:
        ko = _coup_d_envoi(m)
        if ko is None or ko <= maintenant or m.get("score_final"):
            continue
        a = m.get("assemblage") or {}
        try:
            r = coeur.analyser_match(a.get("equipe_dom") or {}, a.get("equipe_ext") or {}, str(m["date"])[:10], params)
        except Exception:
            continue
        for s in selections(r, m.get("cotes_betpawa") or {}, regles):
            if (m["match_id"], s["regle"]) in deja:
                continue
            deja.add((m["match_id"], s["regle"]))
            nouveaux.append({"type": "selection", **s, "gele_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "cotes_prises_le": (m.get("run") or {}).get("pris_le"), "match_id": m["match_id"], "date": str(m["date"])[:10],
                             "heure": m.get("heure_cameroun"), "coup_d_envoi_utc": m.get("coup_d_envoi_utc"),
                             "competition": " ".join(str(m.get("competition") or "").split()), "domicile": m["domicile"], "exterieur": m["exterieur"]})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def regler(matchs: list[dict[str, Any]], journal: Path = JOURNAL, regles: list[dict[str, Any]] | None = None) -> int:
    """Ajoute le résultat réel des pronostics gelés dont le score est connu. Profit à mise 1 seulement si une cote a été figée."""
    lignes = _lire(journal)
    figes = {(l["match_id"], l["regle"]): l for l in lignes if l["type"] == "selection"}
    faits = {(l["match_id"], l["regle"]) for l in lignes if l["type"] == "resultat_selection"}
    scores = {m["match_id"]: m.get("score_final") for m in matchs if m.get("score_final")}
    nouveaux = []
    for k, l in figes.items():
        sc = scores.get(k[0])
        if k in faits or not sc:
            continue
        gagne = bool(predicat(l["cle"])(sc["buts_dom"], sc["buts_ext"]))
        nouveaux.append({"type": "resultat_selection", "match_id": k[0], "regle": k[1], "score": sc, "gagne": gagne,
                         "profit": (round(l["cote"] - 1, 2) if gagne else -1.0) if l.get("cote") else None,
                         "enregistre_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def wilson_bas(g: int, n: int, z: float = 1.96) -> float | None:
    if n <= 0:
        return None
    p = g / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def bilan(journal: Path = JOURNAL, regles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Suivi réel par marché : réussite et rendement SÉPARÉS (le rendement ne compte que les pronostics avec une cote figée)."""
    regles = regles if regles is not None else charger_regles()
    lignes = _lire(journal)
    res = {(l["match_id"], l["regle"]): l for l in lignes if l["type"] == "resultat_selection"}
    par: dict[str, dict[str, Any]] = {}
    for regle in regles:
        gel = [l for l in lignes if l["type"] == "selection" and l["regle"] == regle["id"]]
        regles_ = [res[(l["match_id"], l["regle"])] for l in gel if (l["match_id"], l["regle"]) in res]
        g = sum(1 for x in regles_ if x["gagne"])
        avec = [x for x in regles_ if x.get("profit") is not None]
        net = round(sum(x["profit"] for x in avec), 2)
        par[regle["id"]] = {"geles": len(gel), "regles": len(regles_), "en_attente": len(gel) - len(regles_), "gagnes": g, "perdus": len(regles_) - g,
                            "taux": round(g / len(regles_), 4) if regles_ else None, "wilson_bas_95": round(wilson_bas(g, len(regles_)), 4) if regles_ else None,
                            "paris_avec_cote": len(avec), "net": net if avec else None, "rendement": round(net / len(avec), 4) if avec else None}
    tot = [v for v in par.values()]
    n, g = sum(v["regles"] for v in tot), sum(v["gagnes"] for v in tot)
    return {"par_marche": par, "total": {"geles": sum(v["geles"] for v in tot), "regles": n, "gagnes": g, "taux": round(g / n, 4) if n else None,
                                          "wilson_bas_95": round(wilson_bas(g, n), 4) if n else None}}


def _solidite_pronostic(l: dict[str, Any], par_id: dict[str, dict[str, Any]], poids: dict[str, Any] | None) -> dict[str, float]:
    """Solidité (28/10/2026) du marché sélectionné, calculée à la lecture sur les matchs affichés des deux équipes (`solidite.py`). Affichage seulement :
    jamais écrite dans le journal gelé, aucune sélection modifiée. Rien si le match, les poids ou les matchs des équipes manquent."""
    m = par_id.get(str(l.get("match_id")))
    if not poids or not m:
        return {}
    from . import solidite as SOL, suivi
    a, jour = m.get("assemblage") or {}, str(m["date"])[:10]
    try:
        hd, he = suivi.historique_lieu(a.get("equipe_dom"), True, jour), suivi.historique_lieu(a.get("equipe_ext"), False, jour)
        r = SOL.probabilite(poids, str(l["regle"]).split("|"), hd, he)
    except Exception:                                  # noqa: BLE001
        r = None
    return {} if r is None else {"solidite": round(r, 4)}


def page(journal: Path = JOURNAL, sortie: Path = PAGE, regles_fichier: Path = REGLES, maintenant: datetime | None = None,
         matchs: list[dict[str, Any]] | None = None, solidite: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fichier de la page « Sélection » : les pronostics GELÉS (d'hier aux jours à venir), leur résultat s'il est connu, le suivi réel par marché
    et la référence historique (présentée à part, jamais comme une garantie)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    d_regles = json.loads(regles_fichier.read_text(encoding="utf-8"))
    regles = d_regles["regles"]
    lignes = _lire(journal)
    res = {(l["match_id"], l["regle"]): l for l in lignes if l["type"] == "resultat_selection"}
    depuis = (maintenant - timedelta(days=1)).strftime("%Y-%m-%d")
    ordre = {r["id"]: i for i, r in enumerate(regles)}
    pronos = []
    par_id = {str(m.get("match_id")): m for m in (matchs or []) if m.get("match_id")}
    for l in lignes:
        if l["type"] != "selection" or l["date"] < depuis:
            continue
        r = res.get((l["match_id"], l["regle"]))
        pronos.append({k: l.get(k) for k in ("regle", "marche", "niveau", "cote", "date", "heure", "coup_d_envoi_utc", "competition", "domicile", "exterieur", "match_id")}
                      | {"resultat": None if r is None else ("gagne" if r["gagne"] else "perdu"), "score": None if r is None else r["score"]}
                      | _solidite_pronostic(l, par_id, solidite))
    pronos.sort(key=lambda p: (p["coup_d_envoi_utc"] or "", p["domicile"], ordre.get(p["regle"], 99)))
    d = {"genere_le": maintenant.strftime("%Y-%m-%d %H:%M UTC"), "statut": d_regles["statut"], "source": d_regles["source"],
         "regles": [{k: r[k] for k in ("id", "nom", "niveau", "sans_cote", "cote_min", "reference_historique")} for r in regles],
         "pronostics": pronos, "suivi": bilan(journal, regles)}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d


def pipeline(matchs: list[dict[str, Any]], maintenant: datetime | None = None) -> dict[str, Any]:
    g = geler(matchs, maintenant)
    r = regler(matchs)
    from . import solidite as SOL
    d = page(maintenant=maintenant, matchs=matchs, solidite=SOL.charger())      # Solidité (28/10/2026) : poids écrits plus tôt dans le même passage de suivi.pipeline
    return {"geles": g, "regles": r, "affiches": len(d["pronostics"]), "suivi_total": d["suivi"]["total"]}
