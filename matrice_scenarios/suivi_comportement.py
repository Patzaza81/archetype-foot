"""Suivi et archivage du moteur Comportement : journal en AJOUT SEUL, pronostics figés avant le coup d'envoi.

- geler()     : pour chaque match futur (coup d'envoi > maintenant) avec pronostic, ajoute une ligne « pronostic » horodatée, jamais modifiée.
                Un match déjà gelé n'est jamais regelé ; un match dont le coup d'envoi est passé n'est jamais gelé (pas de pronostic a posteriori).
- resultats() : pour les matchs gelés dont le score est connu, ajoute une ligne « resultat » (gagné / perdu par sélection).
- bilan()     : réussite calculée UNIQUEMENT sur les pronostics gelés avant le match (le vrai test hors échantillon).
Lecture seule vis-à-vis du reste : aucun lien avec V2, V3, V2R, Europe, Journal ni le pipeline. Usage : python -m matrice_scenarios.suivi_comportement [geler|resultats|bilan|tout]
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import page_comportement as P
from . import scanner_marches as S

JOURNAL = P.ROOT / "data" / "comportement" / "journal_comportement.jsonl"
BILAN = P.ROOT / "data" / "comportement" / "bilan_suivi.json"


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
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=P.ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "inconnu"
    except Exception:
        return "inconnu"


def _empreinte_params() -> str:
    return hashlib.sha256(P.PARAMS.read_bytes()).hexdigest()[:12]


def _coup_d_envoi(m: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(m["coup_d_envoi_utc"]).replace("Z", "+00:00"))
    except Exception:
        return None


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc)
    deja = {l["match_id"] for l in _lire(journal) if l["type"] == "pronostic"}
    params = json.loads(P.PARAMS.read_text(encoding="utf-8"))
    nouveaux = []
    for m in (matchs if matchs is not None else P.charger_matchs()):
        ko = _coup_d_envoi(m)
        if ko is None or ko <= maintenant or m["match_id"] in deja or m.get("score_final"):
            continue
        r = P.analyser_match(m, params)
        if r["statut"] != "OK" or not r["selections"]:
            continue
        nouveaux.append({"type": "pronostic", "match_id": m["match_id"], "gele_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "coup_d_envoi_utc": m["coup_d_envoi_utc"], "date": m["date"], "competition": m.get("competition"),
                         "domicile": m["domicile"], "exterieur": m["exterieur"], "selections": r["selections"],
                         "code": _commit(), "parametres": _empreinte_params()})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def resultats(journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None) -> int:
    lignes = _lire(journal)
    figes = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    nouveaux = []
    for m in (matchs if matchs is not None else P.charger_matchs()):
        sc = m.get("score_final")
        if m["match_id"] in figes and m["match_id"] not in faits and sc:
            gagnes = [bool(S.test_du_marche(s["groupe"], s["choix"])(sc["buts_dom"], sc["buts_ext"])) for s in figes[m["match_id"]]["selections"]]
            nouveaux.append({"type": "resultat", "match_id": m["match_id"], "score": sc, "gagnes": gagnes, "enregistre_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def bilan(journal: Path = JOURNAL, ecrire: bool = True) -> dict[str, Any]:
    lignes = _lire(journal)
    figes = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    princ = [res[k]["gagnes"][0] for k in res if k in figes]
    sec = [g for k in res if k in figes for g in res[k]["gagnes"][1:]]
    cotes = [figes[k]["selections"][0]["cote"] for k in res if k in figes]
    out = {"pronostics_geles": len(figes), "matchs_termines": len(princ), "en_attente": len(figes) - len(princ),
           "principal": {"cas": len(princ), "reussite": round(sum(princ) / len(princ), 4) if princ else None, "cote_moyenne": round(sum(cotes) / len(cotes), 3) if cotes else None},
           "autres_tendances": {"cas": len(sec), "reussite": round(sum(sec) / len(sec), 4) if sec else None},
           "note": "Calculé uniquement sur des pronostics gelés avant le coup d'envoi. Rentabilité nécessaire ≈ 1 / cote moyenne."}
    if ecrire:
        BILAN.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def quotidien(branche_donnees: str = "origin/main") -> dict[str, Any]:
    """Lancement automatique : lit l'archive la plus récente de `branche_donnees` (sans la fusionner ni la modifier), gèle les nouveaux
    pronostics, enregistre les résultats connus, met à jour le bilan. Ne fait ni commit ni push (voir docs)."""
    git = lambda *a: subprocess.run(["git", *a], cwd=P.ROOT, capture_output=True, text=True, timeout=300)
    git("fetch", "origin", branche_donnees.split("/")[-1])
    tmp = tempfile.mkdtemp(prefix="archive_main_")
    wt = os.path.join(tmp, "wt")
    try:
        r = git("worktree", "add", "--detach", wt, branche_donnees)
        if r.returncode != 0:
            raise RuntimeError(f"worktree impossible : {r.stderr.strip()}")
        os.environ["COMPORTEMENT_ARCHIVE"] = os.path.join(wt, "data", "archive_test")
        gele, resultat = geler(), resultats()
        page = P.ecrire_page()                                   # la page lit le même archive que le suivi
        return {"geles": gele, "resultats": resultat, "page_matchs": len(page["matchs"]), "bilan": bilan()}
    finally:
        os.environ.pop("COMPORTEMENT_ARCHIVE", None)
        git("worktree", "remove", "--force", wt)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if cmd == "quotidien":
        print(json.dumps(quotidien(), ensure_ascii=False, indent=1))
        raise SystemExit(0)
    if cmd in ("geler", "tout"):
        print("gelés :", geler())
    if cmd in ("resultats", "tout"):
        print("résultats ajoutés :", resultats())
    if cmd in ("bilan", "tout"):
        print(json.dumps(bilan(), ensure_ascii=False, indent=1))
