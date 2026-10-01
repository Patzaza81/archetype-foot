#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare moteur_v2_6_9 et moteur_v2_6_10 sur les MÊMES matchs figés et les MÊMES scores (protocole evaluation/README.md).

    python evaluation/compare_moteurs_v2.py evaluation/snapshot_historique_moteur_v2_6_9.json \
                                            evaluation/scores_historique_moteur_v2_6_9.json
    python evaluation/compare_moteurs_v2.py SNAPSHOT SCORES --calibration-chrono 0.6 [--json sortie.json]

Principe : chaque moteur est rejoué sur les `entree_moteur` exactes du snapshot (aucun nouveau scraping, aucun réglage sur les
scores), puis mesuré par `evaluation_moteur.evalue` (même règlement, mêmes indicateurs, mêmes intervalles par match).

Variantes comparées :
    v2.6.9                                  le moteur actuel du site
    v2.6.10 (lissage)                       moyennes lissées vers 1,35 (K = 4, fixés à l'avance), sans calibration
    v2.6.10 (lissage + calibration)         seulement avec --calibration-chrono F

--calibration-chrono F (0 < F < 1) : le calibrateur est appris sur les F premiers matchs (ordre chronologique, avec score)
puis TOUTES les variantes sont mesurées sur les matchs restants : la calibration n'est jamais évaluée sur ses propres données.

À lire avec prudence : les « choix publiés » sont ici SIMULÉS avec la sélection P1/P2/P3 de `branchement_moteur.selectionne`,
mais SANS le filtre de justification (la bibliothèque a besoin des matchs bruts, absents du snapshot). C'est identique pour
les trois variantes, donc la comparaison est loyale, mais ces choix ne sont pas ceux affichés sur le site.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

import branchement_moteur as bm  # noqa: E402
import evaluation_moteur as ev  # noqa: E402
import moteur_v2_6_9 as v269  # noqa: E402
import moteur_v2_6_10 as v2610  # noqa: E402
from archetype_model.learning.reglement import evaluer_marche  # noqa: E402

Analyse = Callable[[Dict[str, Any], str, datetime.datetime], Dict[str, Any]]


def _heure(m: Dict[str, Any], snapshot: Dict[str, Any]) -> datetime.datetime:
    brut = (m.get("donnees_du_run") or {}).get("heure_utc") or snapshot.get("construit_le")
    return datetime.datetime.strptime(brut, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def rejoue(snapshot: Dict[str, Any], analyse: Analyse, ids: Optional[set] = None) -> Dict[str, Any]:
    """Snapshot comparable : inventaire du moteur + choix P1/P2/P3 simulés (sans filtre de justification)."""
    matchs = []
    for m in snapshot["matchs"]:
        if ids is not None and m["id"] not in ids:
            continue
        entree = copy.deepcopy(m["entree_moteur"])
        res = analyse(entree, entree["date_match"], _heure(m, snapshot))
        if res["statut_global"] == "SKIP":
            continue
        inventaire, candidats = [], []
        for l in res["inventaire"]:
            canon = bm.nom_canonique(l["marche"])
            if canon is None:
                continue
            inventaire.append({"marche": canon, "marche_moteur": l["marche"], "famille": bm.famille_et_groupe(canon)[0],
                               "probabilite": l["proba_modele"], "p_juste": l["p_juste"], "cote": l["cote"], "edge": l["edge"],
                               "ev": l["ev"], "push": l.get("push", 0.0), "statut": l["statut"], "is_value": l["is_value"],
                               "categorie": l["categorie"]})
            if l["is_value"] and l["categorie"] != "D":
                candidats.append(bm.candidat_depuis_ligne(l, canon, res["avertissements_match"]))
        sel = bm.selectionne(candidats)
        choix = [{"rang": r, "marche": c["marche"], "cote": c["cote"], "probabilite": c["probabilite"], "edv": c["edv"],
                  "niveau": c["niveau"], "resume": None} for r, c in sel.items() if c]
        matchs.append(dict(m, inventaire=inventaire, choix_publies=choix, statut_global=res["statut_global"]))
    return dict(snapshot, matchs=matchs, nb_matchs=len(matchs))


def observations_d_apprentissage(snapshot: Dict[str, Any], attribues: Dict[str, Dict[str, Any]], ids: set) -> List[Dict[str, Any]]:
    """Observations (probabilité lissée non calibrée, résultat réel) des matchs d'apprentissage."""
    obs = []
    for m in snapshot["matchs"]:
        if m["id"] not in ids or m["id"] not in attribues:
            continue
        s = attribues[m["id"]]
        entree = copy.deepcopy(m["entree_moteur"])
        res = v2610.analyser_match(entree, entree["date_match"], _heure(m, snapshot))
        if res["statut_global"] == "SKIP":
            continue
        for l in res["inventaire"]:
            canon = bm.nom_canonique(l["marche"])
            if canon is None:
                continue
            statut = evaluer_marche(canon, s["buts_dom"], s["buts_ext"]).statut
            if statut in ("WIN", "LOSS"):
                obs.append({"match_id": m["id"], "marche": l["marche"], "proba": l["proba_modele"],
                            "gagne": statut == "WIN", "date": m["date"]})
    return obs


def resume(nom: str, rapport: Dict[str, Any]) -> List[str]:
    out = [f"── {nom} ──"]
    for g in ("choix_publies", "value_bets_hors_D", "tous_les_marches"):
        d = rapport["groupes"][g]
        s = d["stats"]
        if not s:
            out.append(f"   {g:18s} aucune ligne")
            continue
        iv = d["intervalles"] or {}
        out.append(f"   {g:18s} {s['n']:5d} lignes / {d['n_matchs']:3d} matchs | taux {ev._pct(s['taux'])} pour {ev._pct(s['p_modele'])} annoncé "
                   f"(écart {ev._pct(s['ecart_calibration'])}, {ev._iv(iv.get('ecart_calibration'))})")
        if "diff_brier" in s:
            out.append(f"   {'':18s} Brier modèle {s['brier_modele_meme_lignes']:.4f} | marché {s['brier_marche']:.4f} | "
                       f"différence {s['diff_brier']:+.4f} ({ev._iv(iv.get('diff_brier'), False)}) | ROI {ev._pct(s['roi'])} ({ev._iv(iv.get('roi'))})")
    for r, s in rapport["choix_par_rang"].items():
        out.append(f"   {r} : {s['n']} choix, {s['gagnes']} gagnés ({ev._pct(s['taux'])}) pour {ev._pct(s['p_modele'])} annoncé, ROI {ev._pct(s['roi'])}")
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshot")
    ap.add_argument("scores")
    ap.add_argument("--calibration-chrono", type=float, default=None, metavar="F")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    snapshot = json.load(open(args.snapshot, encoding="utf-8"))
    attribues = ev.charge_scores(args.scores, snapshot)
    integre = ev.integrite(args.snapshot)
    print(f"snapshot : {len(snapshot['matchs'])} matchs, {len(attribues)} avec score ; intégrité : "
          f"{'INTACT' if integre else 'NON VÉRIFIÉE' if integre is None else 'MODIFIÉ — comparaison à ne pas prendre en compte'}")

    ids_evalues = set(attribues)
    calibrateur = None
    if args.calibration_chrono is not None:
        if not 0 < args.calibration_chrono < 1:
            ap.error("--calibration-chrono doit être strictement entre 0 et 1")
        ordre = sorted((m for m in snapshot["matchs"] if m["id"] in attribues), key=lambda m: (m["date"], m["heure"], m["id"]))
        coupe = int(len(ordre) * args.calibration_chrono)
        apprentissage, ids_evalues = {m["id"] for m in ordre[:coupe]}, {m["id"] for m in ordre[coupe:]}
        calibrateur, diag = v2610.apprendre(observations_d_apprentissage(snapshot, attribues, apprentissage))
        print(f"calibration : apprise sur {len(apprentissage)} matchs ; diagnostic : {diag}")
        print(f"évaluation sur les {len(ids_evalues)} matchs suivants (jamais vus par le calibrateur)")
        if calibrateur is None:
            print("⚠ calibrateur non prêt (échantillon insuffisant) : la variante « + calibration » est omise.")

    variantes = [("v2.6.9", lambda e, d, t: v269.analyser_match(e, d, t)),
                 ("v2.6.10 (lissage)", lambda e, d, t: v2610.analyser_match(e, d, t))]
    if calibrateur is not None:
        variantes.append(("v2.6.10 (lissage + calibration)", lambda e, d, t: v2610.analyser_match(e, d, t, calibrateur=calibrateur)))

    sorties: Dict[str, Any] = {}
    attribues_eval = {i: s for i, s in attribues.items() if i in ids_evalues}
    for nom, analyse in variantes:
        snap = rejoue(snapshot, analyse, ids_evalues)
        rapport = ev.evalue(snap, attribues_eval)
        sorties[nom] = rapport
        print()
        print("\n".join(resume(nom, rapport)))
    print("\nRappel : choix simulés sans filtre de justification ; le ROI n'est concluant qu'à partir de "
          f"{ev.SEUIL_CONCLUSION_CHOIX} choix. Aucun paramètre n'a été réglé sur ces scores.")
    if args.json:
        json.dump(sorties, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
