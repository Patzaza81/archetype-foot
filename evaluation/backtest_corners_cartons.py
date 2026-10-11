# -*- coding: utf-8 -*-
"""Backtest chronologique SANS FUITE de la formule corners / cartons (11/10/2026).

Rejoue la saison 2025-26 de Football-Data (data/football_data/snapshots/2526/raw/*.csv, 22 divisions) match par match :
chaque prévision n'utilise que les matchs antérieurs. Score = perte logarithmique sur les lignes « plus de » (total).
Les 40 premiers % des matchs servent à estimer, les 60 % suivants à juger ; baseline = moyenne de la division seule.

Usage : python evaluation/backtest_corners_cartons.py        (bibliothèque standard uniquement)
Résultats du 11/10/2026 (7 093 prévisions) : voir docs/CORNERS_CARTONS.md.
"""
import csv
import datetime
import glob
import math
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import corners_cartons as cc  # noqa: E402

GENRES = {"corners": ((4, 5), (8.5, 9.5, 10.5, 11.5)), "cartons": ((6, 7), (2.5, 3.5, 4.5, 5.5))}


def charge():
    rows = []
    for f in sorted(glob.glob(os.path.join(RACINE, "data", "football_data", "snapshots", "2526", "raw", "*.csv"))):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    rows.append((datetime.datetime.strptime(r["Date"], "%d/%m/%Y").date(), r["Div"], r["HomeTeam"], r["AwayTeam"],
                                 int(r["HC"]), int(r["AC"]), int(r["HY"]) + int(r["HR"]), int(r["AY"]) + int(r["AR"])))
                except (ValueError, KeyError, TypeError):
                    continue
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    return rows


def perte(sorties, alpha, lignes, debut):
    s = n = 0
    for mh, ma, yh, ya in sorties[debut:]:
        for l in lignes:
            p = min(max(cc.proba_plus_de(mh + ma, alpha, l), 1e-6), 1 - 1e-6)
            o = 1.0 if yh + ya > l else 0.0
            s += -(o * math.log(p) + (1 - o) * math.log(1 - p))
            n += 1
    return s / n


def main():
    rows = charge()
    print(f"{len(rows)} matchs avec corners et cartons")
    for genre, (idx, lignes) in GENRES.items():
        P = cc.PARAMETRES[genre]
        for k, c, nom in ((1e9, 1.0, "moyenne de la division seule"), (P["k"], P["c"], "formule retenue")):
            mod = cc.ModeleComptage(k, c)
            sorties = []
            for r in rows:
                pr = mod.predit(r[1], r[2], r[3])
                if pr:
                    sorties.append((pr[0], pr[1], r[idx[0]], r[idx[1]]))
                mod.observe(r[1], r[2], r[3], r[idx[0]], r[idx[1]])
            debut = int(len(sorties) * 0.4)
            print(f"{genre:8s} {nom:30s} k={k:g} c={c}  perte log (test) = {perte(sorties, P['alpha_total'], lignes, debut):.4f}")


if __name__ == "__main__":
    main()
