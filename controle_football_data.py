# -*- coding: utf-8 -*-
"""A4 (24/09/2026) — contrôles qualité des données Football-Data. LECTURE SEULE, aucune correction.

1. Concordance des scores avec Matchendirect : pour chaque match Football-Data dont les DEUX équipes sont reliées
   (data/correspondances/equipes.json), on cherche le match Matchendirect avec les mêmes équipes (noms reliés), même lieu,
   date à ± 1 jour — SANS regarder le score. Puis on compare les scores (final ; mi-temps quand les deux sources l'ont).
   Critère de la feuille de route : au moins 98 % d'accord. Chaque désaccord est listé, jamais corrigé à la main.
2. Doublons : un même match (mêmes équipes, même date) présent deux fois dans Football-Data.
3. Dates : date absente ou illisible ; date dans le futur ; écart de date avec Matchendirect (0 ou 1 jour attendu).

Sortie : data/controles/football_data.json (reconstruit à chaque run), affichée sur la page Système.
Bibliothèque standard uniquement. Usage : python controle_football_data.py
"""
import datetime
import json
import os
from collections import Counter, defaultdict

import assemblage_equipes as ae

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER_CORRESPONDANCES = os.path.join(RACINE, "data", "correspondances", "equipes.json")
SORTIE = os.path.join(RACINE, "data", "controles", "football_data.json")
SEUIL_ACCORD = 0.98
VERSION = "1.0.0"


def _index_noms(correspondances):
    """(division, nom Football-Data) -> nom Matchendirect normalisé."""
    return {(div, nom_fd): ae.normalise(v["matchendirect"])
            for div, info in (correspondances.get("divisions") or {}).items()
            for nom_fd, v in (info.get("equipes") or {}).items()}


def controle(fd, med, correspondances, aujourd_hui=None):
    aujourd_hui = aujourd_hui or datetime.datetime.now(datetime.timezone.utc).date()
    noms = _index_noms(correspondances)
    med_index = defaultdict(list)          # (dom normalisé, ext normalisé) -> matchs Matchendirect
    for n in med:
        med_index[(ae.normalise(n["domicile"]), ae.normalise(n["exterieur"]))].append(n)

    accords, desaccords, sans_pendant, ecarts = 0, [], 0, Counter()
    dates_invalides, dates_futures = [], []
    vus = Counter()
    for m in fd:
        d = ae._date(m.get("date"))
        ident = f'{m.get("competition_code")} {m.get("date")} {m.get("home_team")} - {m.get("away_team")}'
        if d is None:
            dates_invalides.append(ident)
            continue
        if d > aujourd_hui:
            dates_futures.append(ident)
        vus[(m.get("competition_code"), m.get("home_team"), m.get("away_team"), m.get("date"))] += 1
        div = m.get("competition_code")
        dom, ext = noms.get((div, m.get("home_team"))), noms.get((div, m.get("away_team")))
        if not (dom and ext):
            continue
        pendants = [n for n in med_index.get((dom, ext), []) if abs((n["date"] - d).days) <= ae.TOLERANCE_JOURS]
        if len(pendants) != 1:
            sans_pendant += 1
            continue
        n = pendants[0]
        ecarts[(n["date"] - d).days] += 1
        fd_score = (m.get("full_time_home_goals"), m.get("full_time_away_goals"))
        if fd_score == n["buts"]:
            accords += 1
        else:
            desaccords.append({"division": div, "date_football_data": m.get("date"), "date_matchendirect": n["date"].isoformat(),
                               "match": f'{m.get("home_team")} - {m.get("away_team")}',
                               "score_football_data": f"{fd_score[0]}-{fd_score[1]}",
                               "score_matchendirect": f'{n["buts"][0]}-{n["buts"][1]}'})
    compares = accords + len(desaccords)
    taux = accords / compares if compares else None
    doublons = [{"division": k[0], "match": f"{k[1]} - {k[2]}", "date": k[3], "fois": v} for k, v in vus.items() if v > 1]
    return {
        "version": VERSION,
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "critere": f"au moins {SEUIL_ACCORD:.0%} de scores identiques sur les matchs communs",
        "limite": "Les noms d'équipes sont reliés (A3) à partir de matchs au score identique : une équipe dont TOUS les "
                  "scores divergeraient ne serait jamais reliée, donc jamais comparée. Le taux est donc optimiste ; "
                  "chaque désaccord listé reste un signal réel à examiner.",
        "resume": {"matchs_football_data": len(fd), "matchs_communs_compares": compares, "accords": accords,
                   "desaccords": len(desaccords), "taux_accord": round(taux, 4) if taux is not None else None,
                   "critere_atteint": (taux is not None and taux >= SEUIL_ACCORD),
                   "communs_sans_pendant_unique": sans_pendant,
                   "ecart_de_date_jours": {str(k): v for k, v in sorted(ecarts.items())},
                   "doublons": len(doublons), "dates_invalides": len(dates_invalides), "dates_futures": len(dates_futures)},
        "desaccords": sorted(desaccords, key=lambda x: (x["division"], x["date_football_data"])),
        "doublons": doublons, "dates_invalides": dates_invalides[:50], "dates_futures": dates_futures[:50],
    }


def main():
    fd = ae.charge_football_data()
    med = ae.charge_matchendirect_resultats()
    corr = ae._lire(FICHIER_CORRESPONDANCES, {}) or {}
    rapport = controle(fd, med, corr)
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    r = rapport["resume"]
    taux = f'{r["taux_accord"]:.1%}' if r["taux_accord"] is not None else "n/a"
    print(f'[A4] {r["matchs_communs_compares"]} matchs communs comparés : {r["accords"]} accords, {r["desaccords"]} désaccords '
          f'({taux}, critère {"ATTEINT" if r["critere_atteint"] else "NON ATTEINT"}) ; doublons {r["doublons"]} ; '
          f'dates invalides {r["dates_invalides"]} ; dates futures {r["dates_futures"]} ; écarts de date {r["ecart_de_date_jours"]}')


if __name__ == "__main__":
    main()
