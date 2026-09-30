"""Consolide l'état de contrôle des deux moteurs à partir des journaux disponibles.

Le moteur V2 est le moteur de production. Le moteur V3 est suivi en parallèle comme
moteur expérimental : tant que sa calibration n'est pas prête, aucun ROI ou taux de
réussite ne doit être présenté comme une performance validée.
"""
from __future__ import annotations

import datetime
import json
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


def construit_v3() -> dict[str, Any]:
    doc = _charge_json(FICHIER_V3, {})
    calibration = doc.get("calibration") or {}
    bilan = doc.get("bilan") or {}
    couverture = bilan.get("couverture") or {}
    matchs = doc.get("matchs") or []

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
