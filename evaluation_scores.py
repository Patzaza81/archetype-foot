#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluation_scores.py -- récupère les SCORES FINAUX des matchs d'un jeu d'évaluation (evaluation/snapshot_*.json).

Tourne chaque nuit dans le pipeline (étape après la vérification des résultats). Pour chaque match du snapshot dont le jour est
passé et dont le score n'est pas encore connu : une requête par date sur la page de résultats du site, puis rapprochement des DEUX
équipes avec la fonction éprouvée du pipeline (`resultats._trouve_score`, qui ne renvoie un score que si le match est TERMINÉ).
Un match reporté ou sans score reste « restant », jamais un score partiel.

Idempotent : les scores déjà trouvés sont conservés et jamais réécrits ; une date en échec réseau est simplement retentée à la
prochaine exécution. Sortie : evaluation/scores_<nom du snapshot>.json, lu par `evaluation_moteur.py --scores`.

    python evaluation_scores.py [SNAPSHOT.json ...]        # sans argument : tous les evaluation/snapshot_*.json
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

from archetype_model.learning.resultats import _parse_score, _trouve_score
from run_pipeline import aujourdhui_france
from scraper import fetch_html, parse_matches, url_resultat_foot

RACINE = os.path.dirname(os.path.abspath(__file__))


def chemin_scores(chemin_snapshot: str) -> str:
    dossier, nom = os.path.split(chemin_snapshot)
    base = nom[:-5] if nom.endswith(".json") else nom
    return os.path.join(dossier, "scores_" + (base[len("snapshot_"):] if base.startswith("snapshot_") else base) + ".json")


def recupere_scores(chemin_snapshot: str, chemin_sortie: Optional[str] = None, aujourdhui: Optional[datetime.date] = None,
                    fetch: Callable = fetch_html, parse: Callable = parse_matches, url_de_date: Callable = url_resultat_foot,
                    trouve: Callable = _trouve_score, maintenant: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    snapshot = json.load(open(chemin_snapshot, encoding="utf-8"))
    sortie = chemin_sortie or chemin_scores(chemin_snapshot)
    scores: Dict[str, Any] = {}
    if os.path.exists(sortie):
        scores = json.load(open(sortie, encoding="utf-8")).get("scores", {})
    aujourdhui = aujourdhui or aujourdhui_france()
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    par_date: Dict[datetime.date, List[Dict[str, Any]]] = {}
    futurs = 0
    for m in snapshot["matchs"]:
        if m["id"] in scores:
            continue
        d = datetime.date.fromisoformat(m["date"])
        if d >= aujourdhui:
            futurs += 1                                             # jour pas terminé : jamais interrogé
            continue
        par_date.setdefault(d, []).append(m)
    resume = {"snapshot": os.path.basename(chemin_snapshot), "deja_connus": len(scores), "nouveaux": 0, "restants": 0, "jour_pas_termine": futurs, "dates_en_echec": []}
    for d, matchs in sorted(par_date.items()):
        try:
            html, _ = fetch(url_de_date(d))
            page = parse(html, max_matchs=2000, date_label=d.isoformat())
        except Exception as exc:                                   # une date en échec ne bloque ni les autres ni le pipeline
            print(f"[scores évaluation] échec récupération {d} : {exc}", file=sys.stderr)
            resume["dates_en_echec"].append(d.isoformat())
            resume["restants"] += len(matchs)
            continue
        for m in matchs:
            score = trouve(page, m["domicile"], m["exterieur"])
            if score is None:
                resume["restants"] += 1
                continue
            try:
                bd, be = _parse_score(score)
            except (ValueError, AttributeError):
                resume["restants"] += 1
                continue
            scores[m["id"]] = {"buts_dom": bd, "buts_ext": be, "date": m["date"], "domicile": m["domicile"], "exterieur": m["exterieur"],
                               "recupere_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")}
            resume["nouveaux"] += 1
    tmp = sortie + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"snapshot": os.path.basename(chemin_snapshot), "scores": scores}, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, sortie)
    return resume


def main(argv: List[str]) -> int:
    snapshots = argv or sorted(glob.glob(os.path.join(RACINE, "evaluation", "snapshot_*.json")))
    for s in snapshots:
        r = recupere_scores(s)
        print(f"[scores évaluation] {r['snapshot']} : {r['nouveaux']} nouveau(x), {r['deja_connus']} déjà connu(s), {r['restants']} restant(s), "
              f"{r['jour_pas_termine']} match(s) du jour pas terminé, dates en échec : {r['dates_en_echec'] or 'aucune'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
