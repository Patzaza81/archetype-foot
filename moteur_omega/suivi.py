"""Suivi du moteur omega en production. Usage : python -m moteur_omega.suivi [pipeline|geler|resultats|page]

- geler()     : pour chaque match à venir (coup d'envoi > maintenant) de l'archive, analyse + sélection, puis AJOUT d'une ligne « pronostic »
                horodatée au journal `data/omega/journal.jsonl` (ajout seul, aucune ligne modifiée). Une nouvelle ligne n'est ajoutée que si la
                sélection a changé (nouvelles cotes) ; c'est la DERNIÈRE ligne écrite avant le coup d'envoi qui compte. Aucun pronostic après le coup d'envoi.
- resultats() : pour les pronostics dont le score est connu, ajoute UNE ligne « resultat » (gagné / perdu par pari), jamais modifiée.
- page()      : `data/omega/pronostics.json`, lu tel quel par `pronostics_omega.html` (le navigateur ne calcule rien) ; bilan calculé
                uniquement sur les pronostics gelés avant le match.
Aucun lien avec V2, V3, V2R, v, Europe, l'alpha, le Journal ni le générateur de tickets.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import coeur, donnees as D, historique as H, indice as IND, marches as M, ponderation as PO

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "omega"
JOURNAL = DOSSIER / "journal.jsonl"
PAGE = DOSSIER / "pronostics.json"
PARAMS = Path(__file__).with_name("parametres.json")
VALIDATION = ROOT / "docs" / "omega_validation.json"
HISTORIQUE = ROOT / "docs" / "omega_historique.json"
JOURS_REGLES_AFFICHES = 7


def charger_parametres(chemin: Path = PARAMS) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _empreinte(chemin: Path = PARAMS) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:12] if chemin.exists() else "absent"


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "inconnu"
    except Exception:
        return "inconnu"


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


def _ko(x: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception:
        return None


def _pari(l: dict[str, Any]) -> dict[str, Any]:
    return {"cle": l["cle"], "marche": l["marche"], "valeur_reelle": l.get("valeur_reelle"), "famille": l["famille"], "cote": l["cote"],
            "p": round(l["p_retenue"] if l.get("p_retenue") is not None else l["p"], 4), "p_modele": round(l["p"], 4),
            "p_cote": round(l["p_cote"], 4) if l.get("p_cote") is not None else None, "p_min": round(l["p_min"], 4),
            "resistance": l["resistance"], "scenario": l["scenario"]}


def _sur_derniers(cle: list[str], derniers: dict[str, Any] | None) -> dict[str, Any] | None:
    t = M.test_du_marche(*cle)
    return D.pari_sur_derniers(t, derniers) if t else None


def fiche(m: dict[str, Any], a: dict[str, Any], s: dict[str, Any]) -> dict[str, Any]:
    """Ce qui est gelé et affiché pour un match (tout ce qu'il faut pour auditer la décision)."""
    out = {"match_id": m.get("match_id") or m["id"], "jour": m["jour"], "heure": m.get("heure"), "coup_d_envoi_utc": m.get("coup_d_envoi_utc"),
           "competition": m.get("competition"), "domicile": m["domicile"], "exterieur": m["exterieur"], "statut": a["statut"],
           "n_domicile": a["n_domicile"], "n_exterieur": a["n_exterieur"]}
    if a["statut"] != "analyse":
        return {**out, "raison": a.get("raison"), "principal": None, "autres": []}
    ser = a["series"]
    cr = a["croisements"]
    dm = D.derniers_matchs(m)
    return {**out, "principal": _pari(s["principal"]) if s["principal"] else None, "autres": [_pari(x) for x in s["autres"]],
            "pari_sur_derniers": _sur_derniers(s["principal"]["cle"], dm) if s["principal"] else None,
            "raison": s.get("raison"), "buts_attendus": {k: round(v, 3) for k, v in a["buts_attendus"].items()},
            "series": ser, "derniers_matchs": dm, "coins": a["coins"], "convergence": cr["convergence"], "scores_probables": a["scores_probables"],
            "meilleur_modele": _meilleurs_sans_cote(a)}


def _meilleurs_sans_cote(a: dict[str, Any]) -> list[dict[str, Any]]:
    """Lecture du modèle seul (information) : les 3 marchés les plus probables, même sans cote ou sous 1,25."""
    lst = sorted(a["marches"], key=lambda l: -l["p"])[:3]
    return [{"marche": l["marche"], "p_modele": round(l["p"], 4), "cote": l["cote"], "decision": l.get("decision")} for l in lst]


def _cle_selection(f: dict[str, Any]) -> str:
    p = f.get("principal") or {}
    return json.dumps([p.get("cle"), p.get("cote"), [(x["cle"], x["cote"]) for x in f.get("autres") or []]], sort_keys=True)


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, matchs: list[dict] | None = None, refs: D.References | None = None,
          params: dict[str, Any] | None = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc)
    params = params or charger_parametres()
    if matchs is None:
        matchs, refs = D.charger_archive(avec_futurs=True)
    dernier: dict[str, str] = {}
    for l in _lire(journal):
        if l["type"] == "pronostic":
            dernier[l["match_id"]] = _cle_selection(l["fiche"])
    nouveaux = []
    for m in matchs:
        ko = _ko(m.get("coup_d_envoi_utc"))
        if ko is None or ko <= maintenant or m.get("h") is not None:
            continue
        a = coeur.analyser(m, refs, params)
        s = coeur.selectionner(a, params["selection"])
        f = fiche(m, a, s)
        if dernier.get(f["match_id"]) == _cle_selection(f):
            continue
        nouveaux.append({"type": "pronostic", "match_id": f["match_id"], "gele_le": maintenant.isoformat(timespec="seconds"),
                         "commit": _commit(), "parametres": _empreinte(), "version": params.get("version"), "fiche": f})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def derniers_pronostics(lignes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pour chaque match, la DERNIÈRE ligne « pronostic » écrite avant le coup d'envoi."""
    out: dict[str, dict] = {}
    for l in lignes:
        if l["type"] != "pronostic":
            continue
        ko = _ko(l["fiche"].get("coup_d_envoi_utc"))
        gel = _ko(l["gele_le"])
        if ko is None or gel is None or gel >= ko:
            continue
        out[l["match_id"]] = l
    return out


def resultats(journal: Path = JOURNAL, matchs: list[dict] | None = None) -> int:
    lignes = _lire(journal)
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    if matchs is None:
        matchs, _ = D.charger_archive(avec_futurs=False)
    scores = {str(m.get("match_id") or m["id"]): (m["h"], m["a"]) for m in matchs if m.get("h") is not None}
    nouveaux = []
    for mid, l in derniers_pronostics(lignes).items():
        if mid in faits or mid not in scores:
            continue
        h, a = scores[mid]
        f = l["fiche"]
        paris = ([("principal", f["principal"])] if f.get("principal") else []) + [("autre", x) for x in f.get("autres") or []]
        regles = [{"role": r, "marche": p["marche"], "cle": p["cle"], "cote": p["cote"], "p": p["p"],
                   "gagne": bool(M.test_du_marche(*p["cle"])(h, a))} for r, p in paris]
        nouveaux.append({"type": "resultat", "match_id": mid, "score": [h, a], "regle_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "paris": regles})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def _stats(paris: list[dict[str, Any]]) -> dict[str, Any]:
    if not paris:
        return {"regles": 0}
    g = sum(p["gagne"] for p in paris)
    gain = sum((p["cote"] - 1) if p["gagne"] else -1 for p in paris)
    return {"regles": len(paris), "gagnes": g, "reussite": round(g / len(paris), 4), "annonce": round(sum(p["p"] for p in paris) / len(paris), 4),
            "cote_moyenne": round(sum(p["cote"] for p in paris) / len(paris), 3), "rendement": round(gain / len(paris), 4)}


def bilan(lignes: list[dict[str, Any]]) -> dict[str, Any]:
    res = [l for l in lignes if l["type"] == "resultat"]
    princ = [p for l in res for p in l["paris"] if p["role"] == "principal"]
    autres = [p for l in res for p in l["paris"] if p["role"] == "autre"]
    return {"principal": _stats(princ), "autres": _stats(autres), "matchs_regles": len(res)}


def _ajouter_solidite(f: dict[str, Any]) -> None:
    """Solidité (28/10/2026, ordre de Patrick) : indice de réserve du pari (`indice.py`), calculé à la lecture depuis les séries gelées du match.
    Affichage seulement : jamais écrit dans le journal, ne change ni la sélection ni les pronostics. Les paris sont copiés avant d'être complétés."""
    ser = f.get("series")
    if not ser:
        return
    for k in ("principal",):
        if f.get(k):
            f[k] = dict(f[k])
    f["autres"] = [dict(x) for x in f.get("autres") or []]
    for p in ([f["principal"]] if f.get("principal") else []) + f["autres"]:
        try:
            r = IND.indice_pari(tuple(p["cle"]), ser)
        except Exception:                                      # noqa: BLE001
            r = None
        if r is not None:
            p["solidite"] = r["indice"]


def page(maintenant: datetime | None = None, journal: Path = JOURNAL, sortie: Path = PAGE, matchs: list[dict] | None = None,
         refs: D.References | None = None, ponderation: dict[str, Any] | None = None) -> dict[str, Any]:
    maintenant = maintenant or datetime.now(timezone.utc)
    lignes = _lire(journal)
    # Pronostics gelés avant l'ajout de l'affichage des derniers matchs : on les complète ICI, à la lecture, depuis l'archive (journal inchangé).
    par_id = {str(m.get("match_id") or m["id"]): m for m in (matchs or [])}
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    tous: dict[str, dict] = {}
    for l in lignes:                                          # dernière version connue de chaque match (avant ou après coup d'envoi : affichage)
        if l["type"] == "pronostic":
            tous[l["match_id"]] = l
    gels = derniers_pronostics(lignes)
    a_venir, en_cours, reglees, sans = [], [], [], 0
    for mid, l in tous.items():
        f = dict((gels.get(mid) or l)["fiche"])
        if "derniers_matchs" not in f and mid in par_id:
            f["derniers_matchs"] = D.derniers_matchs(par_id[mid])
        if "pari_sur_derniers" not in f and f.get("principal") and f.get("derniers_matchs"):
            f["pari_sur_derniers"] = _sur_derniers(f["principal"]["cle"], f["derniers_matchs"])
        ko = _ko(f.get("coup_d_envoi_utc"))
        if ko is None:
            continue
        _ajouter_solidite(f)
        if ponderation and refs is not None and mid in par_id and ko > maintenant and f.get("principal"):
            # Marché pondéré : affichage seulement (calculé à la lecture avec les cotes de l'archive), jamais écrit dans le journal.
            try:
                pn = PO.choisir(par_id[mid], coeur.analyser(par_id[mid], refs, charger_parametres(), avec_stabilite=False), ponderation)
            except Exception:                                  # noqa: BLE001
                pn = None
            if pn:
                f["pondere"] = {**pn, "harmonie": PO.harmonie(f["principal"]["cle"], pn["cle"])}
        if not f.get("principal"):
            if ko > maintenant:
                sans += 1
            continue
        if mid in res:
            if ko < maintenant - timedelta(days=JOURS_REGLES_AFFICHES):
                continue
            r = res[mid]
            f["score"] = r["score"]
            gagnes = {json.dumps(p["cle"]): p["gagne"] for p in r["paris"]}
            for p in [f["principal"]] + f["autres"]:
                p["resultat"] = "WIN" if gagnes.get(json.dumps(p["cle"])) else "LOSS"
            reglees.append(f)
        elif ko > maintenant:
            a_venir.append(f)
        elif ko > maintenant - timedelta(hours=6):
            en_cours.append(f)
    try:
        v = json.loads(VALIDATION.read_text(encoding="utf-8"))["test_archive"]
        val = {"n": v["selection_reserve"]["principal"]["n"], "reussite": v["selection_reserve"]["principal"]["reussite"],
               "annonce": v["selection_reserve"]["principal"]["probabilite_retenue"], "rendement": v["selection_reserve"]["principal"]["rendement"],
               "matchs": v["matchs_reserve"], "du": v["coupe"], "au": v["au"]}
    except Exception:
        val = None
    try:
        hist = json.loads(HISTORIQUE.read_text(encoding="utf-8"))
    except Exception:
        hist = None
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "historique": hist, "version": charger_parametres().get("version") if PARAMS.exists() else None,
           "statut": "observation", "seuil": charger_parametres()["selection"]["seuil"] if PARAMS.exists() else None,
           "validation": val, "bilan": bilan(lignes), "sans_pronostic": sans,
           "a_venir": sorted(a_venir, key=lambda f: str(f.get("coup_d_envoi_utc"))),
           "en_cours": sorted(en_cours, key=lambda f: str(f.get("coup_d_envoi_utc"))),
           "reglees": sorted(reglees, key=lambda f: str(f.get("coup_d_envoi_utc")), reverse=True)}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def pipeline() -> None:
    matchs, refs = D.charger_archive(avec_futurs=True)
    n = geler(matchs=matchs, refs=refs)
    r = resultats(matchs=matchs)
    try:                                                       # réussite par type de pari (affichage) ; ne bloque jamais le reste
        H.ecrire(matchs=matchs, refs=refs)
    except Exception as e:                                     # noqa: BLE001
        print(f"omega : historique non mis à jour ({e})")
    pond = None
    try:                                                       # marché pondéré (affichage) ; ne bloque jamais le reste
        pond = PO.ecrire(matchs=matchs, refs=refs)
    except Exception as e:                                     # noqa: BLE001
        print(f"omega : pondération non mise à jour ({e})")
        pond = PO.charger()
    p = page(matchs=matchs, refs=refs, ponderation=pond)
    print(f"omega : {n} pronostic(s) gelé(s), {r} résultat(s) réglé(s), {len(p['a_venir'])} pari(s) à venir, {p['sans_pronostic']} match(s) sans pronostic")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    {"pipeline": pipeline, "geler": lambda: print(geler()), "resultats": lambda: print(resultats()), "page": lambda: print(len(page()["a_venir"]))}[cmd]()
