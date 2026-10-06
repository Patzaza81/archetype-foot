# -*- coding: utf-8 -*-
"""Ligne de commande de moteur_v2_6_10.

    python -m moteur_v2_6_10 --autotest
    python -m moteur_v2_6_10 export_moteur/matchs_moteur_2026-09-22.json --date 2026-09-22 [--sortie rapport.json] [--sans-lissage]

Rejoue le calcul d'un fichier de matchs (JSON : liste, ou {"matchs": [...]}) et écrit un rapport JSON.
Remplace `python moteur_v2_6_9.py <fichier> --date ...` ; l'affichage détaillé de l'ancien outil n'est pas repris :
le rapport JSON contient tout (inventaire, verdict, alertes, calibration, lissage).
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone

from .autotest import autotest
from .core import VERSION_MOTEUR, analyser_match


def _arrondi(obj, nd=6):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _arrondi(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_arrondi(v, nd) for v in obj]
    return obj


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m moteur_v2_6_10", description="Moteur de value bets v2.6.10")
    ap.add_argument("fichier", nargs="?", help="JSON de matchs")
    ap.add_argument("--date", default=date.today().isoformat(), help="Date du run (YYYY-MM-DD), pour V11")
    ap.add_argument("--sortie", help="Chemin du rapport JSON (défaut : rapport_<date>.json)")
    ap.add_argument("--sans-lissage", action="store_true", help="Désactive le lissage (retrouve les moyennes brutes de la v2.6.9)")
    ap.add_argument("--autotest", action="store_true", help="Lance les autotests")
    args = ap.parse_args(argv)
    if args.autotest:
        return autotest()
    if not args.fichier:
        ap.error("fichier de matchs requis (ou --autotest)")
    with open(args.fichier, encoding="utf-8") as f:
        data = json.load(f)
    matchs = data.get("matchs", []) if isinstance(data, dict) else data
    maintenant = datetime.now(timezone.utc)
    resultats = []
    for m in matchs:
        try:
            res = analyser_match(m, args.date, maintenant, lisser=not args.sans_lissage)
        except Exception as e:  # une erreur inattendue ne doit pas arrêter les autres matchs
            res = {"id": m.get("id"), "statut_global": "SKIP", "raison_skip": f"Erreur inattendue : {e!r}"}
        resultats.append(res)
        print(f"Match {res.get('id')} — {res.get('nom_dom')} vs {res.get('nom_ext')} : {res['statut_global']}"
              + (f" ({res['raison_skip']})" if res.get("raison_skip") else ""))
    sortie = args.sortie or f"rapport_{args.date}.json"
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump({"date": args.date, "version_moteur": VERSION_MOTEUR, "matchs": _arrondi(resultats)}, f, ensure_ascii=False, indent=2)
    print(f"Rapport JSON écrit dans {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
