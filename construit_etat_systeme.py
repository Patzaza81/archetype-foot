"""Consolide l'état de contrôle des deux moteurs à partir des journaux disponibles.

Le moteur V2 est le moteur de production. Le moteur V3 est suivi en parallèle comme
moteur expérimental : tant que sa calibration n'est pas prête, aucun ROI ou taux de
réussite ne doit être présenté comme une performance validée.
"""
from __future__ import annotations

import datetime
import gzip
import json
import re
from pathlib import Path
from typing import Any

FICHIER_ETAT = "etat_systeme.json"
FICHIER_JOURNAL = "journal.json"
FICHIER_V3 = Path("data/v3/pronostics_v3.json")
DOSSIER_JOURNAL_V3 = Path("data/v3/journal")


def _i(x: Any) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def _f(x: Any) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _charge_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def construit_v2(journal: dict[str, Any]) -> dict[str, Any]:
    moteur = (journal.get("moteurs") or {}).get("moteur_v2_6_9") or {}
    g = moteur.get("global") or {}
    paris = _i(g.get("paris"))
    gagnes = _i(g.get("gagnes"))
    rembourses = _i(g.get("rembourses"))

    par_marche = []
    for ligne in journal.get("segments", {}).get("marches", []) or []:
        segment = ligne.get("segment")
        if not segment:
            continue
        par_marche.append({
            "marche": segment,
            "observations": _i(ligne.get("paris")),
            "gagnes": _i(ligne.get("gagnes")),
            "perdus": max(0, _i(ligne.get("paris")) - _i(ligne.get("gagnes")) - _i(ligne.get("rembourses"))),
            "roi": _f(ligne.get("roi")),
            "reussite": _f(ligne.get("reussite")),
            "cote_moyenne": _f(ligne.get("cote_moyenne")),
            "statut": ligne.get("statut"),
        })
    par_marche.sort(key=lambda x: (-x["observations"], x["marche"]))

    return {
        "nom": "moteur_v2_6_9",
        "role": "PRODUCTION",
        "statut": "ACTIF",
        "global": {
            "observations": paris,
            "matchs": _i(g.get("matchs")),
            "gagnes": gagnes,
            "perdus": max(0, paris - gagnes - rembourses),
            "rembourses": rembourses,
            "roi": _f(g.get("roi")),
            "reussite": _f(g.get("reussite")),
            "cote_moyenne": _f(g.get("cote_moyenne")),
            "cote_min": _f(g.get("cote_min")),
            "cote_max": _f(g.get("cote_max")),
            "ic95": g.get("ic95"),
            "roi_moitie_1": _f(g.get("roi_moitie_1")),
            "roi_moitie_2": _f(g.get("roi_moitie_2")),
        },
        "par_marche": par_marche,
        "par_ligue": moteur.get("ligues") or [],
    }


def _v3_marche_stats(doc: dict[str, Any]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for match in doc.get("matchs", []) or []:
        for candidat in match.get("candidats", []) or []:
            marche = candidat.get("marche")
            if not marche:
                continue
            s = stats.setdefault(marche, {
                "marche": marche, "calculs": 0, "apercus": 0, "selections": 0,
                "probabilites": [], "edv": [],
            })
            s["calculs"] += 1
            if match.get("apercu_non_calibre"):
                s["apercus"] += 1
            s["probabilites"].append(candidat.get("probabilite"))
            s["edv"].append(candidat.get("edv"))
        for rang in ("P1", "P2", "P3"):
            if (match.get("selections") or {}).get(rang):
                marche = (match["selections"][rang] or {}).get("marche")
                if marche:
                    stats.setdefault(marche, {
                        "marche": marche, "calculs": 0, "apercus": 0,
                        "selections": 0, "probabilites": [], "edv": [],
                    })["selections"] += 1

    out = []
    for s in stats.values():
        probs = [float(x) for x in s.pop("probabilites") if isinstance(x, (int, float))]
        edv = [float(x) for x in s.pop("edv") if isinstance(x, (int, float))]
        s["probabilite_moyenne"] = round(sum(probs) / len(probs), 4) if probs else None
        s["edv_moyenne"] = round(sum(edv) / len(edv), 3) if edv else None
        out.append(s)
    out.sort(key=lambda x: (-x["calculs"], x["marche"]))
    return out


def _v3_evolution(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Historique disponible des journaux V3, sans transformer des aperçus en performances."""
    lignes = []
    for path in sorted(DOSSIER_JOURNAL_V3.glob("*.json")):
        journal = _charge_json(path, {})
        if not isinstance(journal, dict):
            continue
        matchs = list(journal.values())
        lignes.append({
            "date": path.stem,
            "matchs": len(matchs),
            "evalues": sum(1 for m in matchs if (m.get("moteur_v3") or {}).get("statut") == "OK"),
            "selections": sum(
                1 for m in matchs
                if any((m.get("moteur_v3") or {}).get("selection", {}).get(r) for r in ("P1", "P2", "P3"))
            ),
            "apercus": sum(
                1 for m in matchs if (m.get("moteur_v3") or {}).get("apercu_non_calibre")
            ),
        })
    return lignes


def _charge_scores_archive() -> dict[str, tuple[int, int]]:
    """Indexe uniquement les scores réellement archivés pour régler les aperçus V3."""
    out: dict[str, tuple[int, int]] = {}
    dossier = Path("data/archive_test")
    for path in sorted(dossier.glob("*.json.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, EOFError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        for match_id, rec in doc.items():
            if not isinstance(rec, dict):
                continue
            score = rec.get("score") or {}
            h, a = score.get("buts_dom"), score.get("buts_ext")
            if isinstance(h, int) and isinstance(a, int):
                out[str(match_id)] = (h, a)
    return out


def _resultat_marche(marche: str, score: tuple[int, int]) -> bool | None:
    """Règle de règlement des marchés effectivement affichés en aperçu V3."""
    h, a = score
    total = h + a
    if marche == "1x2_1": return h > a
    if marche == "1x2_X": return h == a
    if marche == "1x2_2": return h < a
    if marche == "dc_1X": return h >= a
    if marche == "dc_X2": return h <= a
    if marche == "dc_12": return h != a
    if marche == "btts_yes": return h > 0 and a > 0
    if marche == "btts_no": return h == 0 or a == 0
    m = re.fullmatch(r"(over|under)_(\d+)_5", marche)
    if m:
        seuil = int(m.group(2)) + 0.5
        return total > seuil if m.group(1) == "over" else total < seuil
    m = re.fullmatch(r"(home|away)_(over|under)_(\d+)_5", marche)
    if m:
        buts = h if m.group(1) == "home" else a
        seuil = int(m.group(3)) + 0.5
        return buts > seuil if m.group(2) == "over" else buts < seuil
    m = re.fullmatch(r"handicap_(\d+(?:\.\d+)?)_(1|X|2)", marche)
    if m:
        ligne = float(m.group(1))
        diff = h - a
        if m.group(2) == "1": return diff > ligne
        if m.group(2) == "X": return diff == ligne
        return diff < ligne
    return None


def _v3_retrospective() -> dict[str, Any]:
    """Règle l'historique des APERÇUS réellement affichés, sans les confondre avec des sélections validées."""
    scores = _charge_scores_archive()
    total = wins = losses = pushes = 0
    mises = gains = 0.0
    seen: set[tuple[str, str]] = set()
    aujourd_hui = datetime.date.today().isoformat()
    par_marche: dict[str, dict[str, Any]] = {}
    par_date: dict[str, dict[str, Any]] = {}
    for path in sorted(DOSSIER_JOURNAL_V3.glob("*.json")):
        journal = _charge_json(path, {})
        if not isinstance(journal, dict):
            continue
        for match in journal.values():
            if not isinstance(match, dict):
                continue
            mid = str(match.get("match_id") or "")
            if str(match.get("date") or path.stem) > aujourd_hui:
                continue
            score = scores.get(mid)
            if score is None:
                continue
            for apercu in match.get("apercu_non_calibre") or []:
                marche = apercu.get("marche")
                cote = _f(apercu.get("cote"))
                if not marche or cote is None:
                    continue
                cle = (mid, str(marche))
                if cle in seen:
                    continue
                seen.add(cle)
                resultat = _resultat_marche(marche, score)
                if resultat is None:
                    continue
                total += 1
                s = par_marche.setdefault(marche, {"marche": marche, "observations": 0, "gagnes": 0, "perdus": 0, "rembourses": 0, "mise": 0.0, "gain_net": 0.0})
                d = par_date.setdefault(str(match.get("date") or path.stem), {"date": str(match.get("date") or path.stem), "observations": 0, "gagnes": 0, "perdus": 0, "rembourses": 0, "mise": 0.0, "gain_net": 0.0})
                s["observations"] += 1; d["observations"] += 1; mises += 1.0; s["mise"] += 1.0; d["mise"] += 1.0
                if resultat is True:
                    wins += 1; s["gagnes"] += 1; d["gagnes"] += 1
                    net = cote - 1.0; gains += net; s["gain_net"] += net; d["gain_net"] += net
                elif resultat is False:
                    losses += 1; s["perdus"] += 1; d["perdus"] += 1; s["gain_net"] -= 1.0; d["gain_net"] -= 1.0
                else:
                    pushes += 1; s["rembourses"] += 1; d["rembourses"] += 1
    def finalize(s):
        obs = s["observations"]
        s["taux_reussite"] = round(s["gagnes"] / obs, 4) if obs else None
        s["roi"] = round(s["gain_net"] / s["mise"], 4) if s["mise"] else None
        s["gain_net"] = round(s["gain_net"], 3)
        s.pop("mise", None)
        return s
    return {
        "methode": "Aperçus V3 réellement affichés, réglés uniquement quand un score est présent dans data/archive_test. Mise théorique 1 unité par aperçu. Les aperçus restent non calibrés et ne constituent pas des sélections validées.",
        "observations": total, "gagnes": wins, "perdus": losses, "rembourses": pushes,
        "taux_reussite": round(wins / total, 4) if total else None,
        "roi_theorique": round(gains / mises, 4) if mises else None,
        "gain_net_theorique": round(gains, 3),
        "par_marche": [finalize(v) for v in sorted(par_marche.values(), key=lambda x: (-x["observations"], x["marche"]))],
        "par_date": [finalize(v) for v in sorted(par_date.values(), key=lambda x: x["date"])],
    }


def construit_v3() -> dict[str, Any]:
    doc = _charge_json(FICHIER_V3, {})
    calibration = doc.get("calibration") or {}
    bilan = doc.get("bilan") or {}
    couverture = bilan.get("couverture") or {}
    matchs = doc.get("matchs") or []

    retro = _v3_retrospective()

    return {
        "nom": "moteur_v3",
        "role": "EXPERIMENTAL",
        "statut": doc.get("statut", "EXPÉRIMENTAL — NON VALIDÉ"),
        "genere_le": doc.get("genere_le"),
        "calibration": {
            "prete": bool(calibration.get("prete")),
            "observations": _i(calibration.get("observations")),
            "minimum_observations": _i(calibration.get("minimum_observations")),
            "matchs": _i(calibration.get("matchs")),
            "minimum_matchs": _i(calibration.get("minimum_matchs")),
            "raison": calibration.get("raison"),
        },
        "global": {
            "matchs": _i(bilan.get("matchs")),
            "evalues": _i((bilan.get("statuts") or {}).get("EVALUE")),
            "non_evalues": _i((bilan.get("statuts") or {}).get("NON_EVALUE")),
            "selections": _i(bilan.get("selections")),
            "matchs_avec_selection": _i(bilan.get("matchs_avec_selection")),
            "apercus_non_calibres": _i(bilan.get("matchs_en_apercu_non_calibre")),
            "marches_cotes_calcules": _i(couverture.get("marches_cotes_calcules")),
            "issues_betpawa": _i(couverture.get("issues_betpawa")),
        },
        "raisons_rejet": bilan.get("raisons_de_rejet") or {},
        "par_marche": _v3_marche_stats(doc),
        "evolution": _v3_evolution(doc),
        "retrospective": retro,
    }


def construit_etat() -> dict[str, Any]:
    journal = _charge_json(Path(FICHIER_JOURNAL), {})
    v2 = construit_v2(journal)
    v3 = construit_v3()

    return {
        "schema": "2.0",
        "genere_le": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "moteurs": {
            "moteur_v2_6_9": v2,
            "moteur_v3": v3,
        },
        # Compatibilité avec les consommateurs historiques de la page.
        "bilan_comportemental": v2,
        "bilan_v3": v3,
    }


def main() -> None:
    Path(FICHIER_ETAT).write_text(
        json.dumps(construit_etat(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("[etat systeme] état V2 + V3 généré.")


if __name__ == "__main__":
    main()
