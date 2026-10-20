"""Suivi du moteur alpha « séries » en production : pronostics GELÉS avant le coup d'envoi, résultats, bilan et données de la page.

- geler()     : pour chaque match futur (coup d'envoi > maintenant) analysable, ajoute UNE ligne « pronostic » horodatée au journal en AJOUT SEUL
                (les trois onglets avec cotes, jamais modifiée). Un match déjà gelé n'est jamais regelé ; un match dont le coup d'envoi est passé
                n'est jamais gelé (aucun pronostic a posteriori).
- resultats() : pour les matchs gelés dont le score est connu, ajoute une ligne « resultat » (gagné / perdu par sélection).
- bilan()     : réussite et rendement calculés UNIQUEMENT sur les pronostics gelés avant le match (le vrai test hors échantillon).
- page()      : `data/alpha_serie/pronostics.json`, lu tel quel par `pronostics_comportement.html` (le navigateur ne calcule rien).
Aucun lien avec V2, V3, V2R, Europe, le Journal ni le générateur de tickets. Usage : python -m alpha_serie.suivi [pipeline|geler|resultats|bilan|page]
"""
from __future__ import annotations

import glob
import gzip
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import coeur, parametres as P
from .marches import test_du_marche

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "alpha_serie"
JOURNAL = DOSSIER / "journal.jsonl"
BILAN = DOSSIER / "bilan.json"
PAGE = DOSSIER / "pronostics.json"
CLASSEMENTS = ROOT / "cache_classement.json"
ONGLETS = ("buts", "equipes", "multiscores")


def charger_matchs() -> list[dict[str, Any]]:
    out = []
    for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
        for x in json.load(gzip.open(f)).values():
            sc = x.get("score") or {}
            x["score_final"] = {"buts_dom": sc["buts_dom"], "buts_ext": sc["buts_ext"]} if sc.get("buts_dom") is not None else None
            out.append(x)
    return out


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


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "inconnu"
    except Exception:
        return "inconnu"


def _empreinte_params() -> str:
    f = P.FICHIER
    return hashlib.sha256(f.read_bytes()).hexdigest()[:12] if f.exists() else "defaut"


def _coup_d_envoi(m: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(m["coup_d_envoi_utc"]).replace("Z", "+00:00"))
    except Exception:
        return None


def _classements() -> dict[str, list]:
    try:
        d = json.loads(CLASSEMENTS.read_text(encoding="utf-8"))
        return {k: (v or {}).get("resultat") or [] for k, v in d.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _cle_competition(nom: Any) -> str:
    return " ".join(str(nom or "").lower().split())


def analyser(m: dict[str, Any], params: dict, classements: dict[str, list] | None = None) -> dict[str, Any]:
    """Étapes 1 et 2 pour un match de l'archive. Les alertes de graduation (nom d'équipe EXACT) n'ajoutent ni ne retirent aucun marché."""
    a = m.get("assemblage") or {}
    r = coeur.analyser_match(a.get("equipe_dom") or {}, a.get("equipe_ext") or {}, str(m["date"])[:10], params)
    fiche = {"match_id": m["match_id"], "date": m["date"], "heure": m.get("heure_cameroun"), "competition": " ".join(str(m.get("competition") or "").split()),
             "domicile": m["domicile"], "exterieur": m["exterieur"], "coup_d_envoi_utc": m.get("coup_d_envoi_utc"), "statut": r["statut"],
             "n_domicile": r["n_domicile"], "n_exterieur": r["n_exterieur"]}
    if r["statut"] != "analyse":
        return {**fiche, "raison": r["raison"], "onglets": {o: [] for o in ONGLETS}}
    e2 = coeur.choisir(r, m.get("cotes_betpawa") or {})
    grad = coeur.graduation((classements or {}).get(_cle_competition(m.get("competition"))), m["domicile"], m["exterieur"])
    onglets: dict[str, list] = {}
    for onglet, lst in e2["onglets"].items():
        onglets[onglet] = []
        for f in lst:
            ligne = {"cle": list(f["cle"]), "marche": f["marche"], "valeur": f["valeur"], "cote": f.get("cote"), "cote_a_lire": bool(f.get("cote_a_lire"))}
            for c in ("offensive", "defensive", "niveau", "scenarios", "sur"):
                if c in f:
                    ligne[c] = f[c]
            alerte = coeur.alerte_graduation(tuple(f["cle"]), grad)
            if alerte:
                ligne["alerte"] = alerte
            onglets[onglet].append(ligne)
    rejetes = [{"onglet": f["onglet"], "marche": f["marche"], "raison": f["raison"]} for f in r["rejetes"]] + \
              [{"onglet": f["onglet"], "marche": f["marche"], "raison": f["raison"]} for f in e2["ecartes_par_la_cote"]]
    return {**fiche, "k": r["k"], "niveaux": r["niveaux"], "scenarios_offensifs": r["scenarios_offensifs"], "scenarios_defensifs": r["scenarios_defensifs"],
            "onglets": onglets, "rejetes": rejetes, "graduation": grad}


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None, params: dict | None = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc)
    params = params or P.charger()
    deja = {l["match_id"] for l in _lire(journal) if l["type"] == "pronostic"}
    classements = _classements()
    nouveaux = []
    for m in (matchs if matchs is not None else charger_matchs()):
        ko = _coup_d_envoi(m)
        if ko is None or ko <= maintenant or m["match_id"] in deja or m.get("score_final"):
            continue
        r = analyser(m, params, classements)
        if r["statut"] != "analyse" or not any(r["onglets"].values()):
            continue
        nouveaux.append({"type": "pronostic", "gele_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "code": _commit(), "parametres": _empreinte_params(),
                         **{k: r[k] for k in ("match_id", "coup_d_envoi_utc", "date", "competition", "domicile", "exterieur", "k", "onglets")}})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def _gagne(cle: list[str], h: int, a: int) -> bool | None:
    g, s = cle
    if g == "multigoals":
        lo, hi = (int(x) for x in s.split("-"))
        return lo <= h + a <= hi
    if g == "multiscores":
        return bool(coeur.GROUPES_MULTISCORES[s](h, a))
    p = test_du_marche(g, s)
    return None if p is None else bool(p(h, a))


def resultats(journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None) -> int:
    lignes = _lire(journal)
    figes = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    nouveaux = []
    for m in (matchs if matchs is not None else charger_matchs()):
        sc = m.get("score_final")
        if m["match_id"] in figes and m["match_id"] not in faits and sc:
            gagnes = {o: [_gagne(s["cle"], sc["buts_dom"], sc["buts_ext"]) for s in figes[m["match_id"]]["onglets"].get(o, [])] for o in ONGLETS}
            nouveaux.append({"type": "resultat", "match_id": m["match_id"], "score": sc, "gagnes": gagnes,
                             "enregistre_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def bilan(journal: Path = JOURNAL, ecrire: bool = True) -> dict[str, Any]:
    lignes = _lire(journal)
    figes = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    out: dict[str, Any] = {"pronostics_geles": len(figes), "matchs_termines": len([k for k in res if k in figes]), "onglets": {}}
    for o in ONGLETS:
        cas = [(s, g) for k in res if k in figes for s, g in zip(figes[k]["onglets"].get(o, []), res[k]["gagnes"].get(o, [])) if g is not None]
        cotes = [(s["cote"], g) for s, g in cas if s.get("cote")]
        out["onglets"][o] = {"cas": len(cas), "reussite": round(sum(g for _, g in cas) / len(cas), 4) if cas else None,
                             "cote_moyenne": round(sum(c for c, _ in cotes) / len(cotes), 3) if cotes else None,
                             "rendement": round(sum((c - 1) if g else -1 for c, g in cotes) / len(cotes), 4) if cotes else None}
    out["note"] = "Calculé uniquement sur des pronostics gelés avant le coup d'envoi. Rentabilité nécessaire ≈ 1 / cote moyenne."
    if ecrire:
        BILAN.parent.mkdir(parents=True, exist_ok=True)
        BILAN.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def page(matchs: list[dict[str, Any]] | None = None, params: dict | None = None, sortie: Path = PAGE) -> dict[str, Any]:
    """Données de la page : tous les matchs de l'archive qui ont une analyse ; le moteur lit les équipes figées avant le coup d'envoi."""
    params = params or P.charger()
    classements = _classements()
    liste = []
    depuis = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")     # la page montre les matchs d'hier, d'aujourd'hui et à venir (fichier léger)
    for m in (matchs if matchs is not None else charger_matchs()):
        if str(m["date"])[:10] < depuis:
            continue
        r = analyser(m, params, classements)
        sc = m.get("score_final")
        liste.append({**r, "score": sc, "heure": m.get("heure_cameroun")})
    d = {"moteur": "alpha_serie", "statut": "OK", "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "promotion_allowed": False,
         "cote_min": P.COTE_MIN, "parametres": {"seuil_branche": params["seuil_branche"], "source": params.get("source"), "provisoire": params.get("provisoire", [])},
         "bilan_gele": bilan(ecrire=False), "matchs": liste}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d


def pipeline() -> dict[str, Any]:
    """Passage dans le pipeline nocturne : lit l'archive du dossier de travail, sans git. Le commit est fait par le pipeline."""
    matchs = charger_matchs()                        # chargée une seule fois : même archive pour le gel, les résultats et la page
    gele = geler(matchs=matchs)
    resultat = resultats(matchs=matchs)
    d = page(matchs=matchs)
    return {"geles": gele, "resultats": resultat, "page_matchs": len(d["matchs"]), "bilan": bilan()}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    if cmd == "pipeline":
        print(json.dumps(pipeline(), ensure_ascii=False, indent=1))
    elif cmd == "geler":
        print("gelés :", geler())
    elif cmd == "resultats":
        print("résultats ajoutés :", resultats())
    elif cmd == "bilan":
        print(json.dumps(bilan(), ensure_ascii=False, indent=1))
    elif cmd == "page":
        print(len(page()["matchs"]), "matchs écrits")
    else:
        raise SystemExit("commande inconnue : " + cmd)
