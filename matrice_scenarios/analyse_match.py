"""Analyse d'un match par croisements « marqué contre encaissé adverse », probabilités calibrées sur l'historique.

    python -m matrice_scenarios.analyse_match --domicile "1-1,1-2,0-3" --exterieur "0-1,0-1,2-1" --cotes both_score=1.7 home_win=3.1

Les scores sont écrits « pour-contre » du point de vue de l'équipe (ses buts d'abord), au même lieu que le match analysé
(domicile pour l'équipe qui reçoit, extérieur pour l'autre). 3 à 5 matchs par équipe.

Calibration : `calibrer()` découpe le score de chaque marché en tranches (bornes calculées sur les 60 % de dates les plus anciennes de
Football-Data, résultats seulement) et mesure le taux réel de réussite par tranche. La qualité hors échantillon (Brier contre taux de base)
est calculée sur les 40 % suivants et publiée dans le fichier. Lecture seule, aucune règle activée.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .croisements import ALL_MARKETS as MARKETS, _formulas, _stats, outcome, scores
from .football_data import load_football_data

CALIBRATION_FILE = Path(__file__).resolve().parent.parent / "docs" / "calibration_croisements.json"
BINS = 8
MIN_SAME = 3
SMOOTH = 20  # pseudo-observations au taux de base : évite les taux extrêmes sur petites tranches


def _bin(edges: list[float], value: float) -> int:
    return sum(value > e for e in edges)


def calibrer(records: list[dict]) -> dict[str, Any]:
    rows = [(r, s) for r in sorted(records, key=lambda x: str(x["date"])) if (s := scores(r, MIN_SAME)) is not None]
    cut = int(len(rows) * 0.6)
    cut_day = str(rows[cut][0]["date"])[:10]
    train = [x for x in rows if str(x[0]["date"])[:10] < cut_day]
    test = [x for x in rows if str(x[0]["date"])[:10] >= cut_day]

    def fit(sample: list, market: str) -> dict[str, Any]:
        values = sorted(s[market] for _, s in sample)
        edges = sorted({values[int(len(values) * k / BINS)] for k in range(1, BINS)})
        base = sum(outcome(r, market) for r, _ in sample) / len(sample)
        wins, counts = [0] * (len(edges) + 1), [0] * (len(edges) + 1)
        for r, s in sample:
            b = _bin(edges, s[market])
            counts[b] += 1
            wins[b] += outcome(r, market)
        return {"edges": edges, "n": counts, "base_rate": base,
                "rate": [(w + SMOOTH * base) / (c + SMOOTH) for w, c in zip(wins, counts)]}

    out: dict[str, Any] = {"source": "Football-Data, résultats seulement", "matches": len(rows), "train": len(train), "test": len(test),
                           "calibration_cutoff_day": cut_day, "min_same_venue": MIN_SAME, "window": 5, "markets": {}}
    for m in MARKETS:
        half = fit(train, m)
        brier_model = brier_base = 0.0
        for r, s in test:
            y = outcome(r, m)
            brier_model += (half["rate"][_bin(half["edges"], s[m])] - y) ** 2
            brier_base += (half["base_rate"] - y) ** 2
        final = fit(rows, m)
        final["out_of_sample"] = {"test_matches": len(test), "brier_model": round(brier_model / len(test), 5), "brier_taux_de_base": round(brier_base / len(test), 5),
                                  "amelioration_pct": round(100 * (1 - brier_model / brier_base), 2)}
        out["markets"][m] = final
    return out


def parse_scores(text: str) -> list[tuple[int, int]]:
    result = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if part:
            a, b = part.replace(" ", "").split("-")
            result.append((int(a), int(b)))
    return result


def analyser(domicile: list[tuple[int, int]], exterieur: list[tuple[int, int]], calibration: dict, cotes: dict[str, float] | None = None) -> dict[str, Any]:
    if not (MIN_SAME <= len(domicile) <= 5 and MIN_SAME <= len(exterieur) <= 5):
        raise ValueError(f"{MIN_SAME} à 5 matchs par équipe requis (reçu {len(domicile)} et {len(exterieur)})")
    rows_h = [{"goals_for": a, "goals_against": b} for a, b in domicile]
    rows_a = [{"goals_for": a, "goals_against": b} for a, b in exterieur]
    s = _formulas(_stats(rows_h), _stats(rows_a))
    out: dict[str, Any] = {"markets": {}, "warnings": []}
    if min(len(domicile), len(exterieur)) < 5:
        out["warnings"].append(f"Petit échantillon ({len(domicile)} et {len(exterieur)} matchs) : la calibration vient de 3 à 5 matchs, prudence.")
    for m in MARKETS:
        cal = calibration["markets"][m]
        b = _bin(cal["edges"], s[m])
        p, base = cal["rate"][b], cal["base_rate"]
        entry = {"probabilite": round(p, 3), "taux_de_base": round(base, 3), "ecart_vs_base": round(p - base, 3),
                 "cote_equilibre": round(1 / p, 2), "tranche": f"{b + 1}/{len(cal['rate'])}", "matchs_dans_la_tranche": cal["n"][b],
                 "gain_modele_vs_base_pct": cal["out_of_sample"]["amelioration_pct"]}
        if cotes and m in cotes:
            c = cotes[m]
            entry["cote_donnee"] = c
            entry["marge_sur_cote_equilibre"] = round(c * p - 1, 3)
            entry["lecture"] = "avantage apparent" if c * p - 1 > 0.05 else ("neutre" if c * p - 1 > -0.05 else "cote trop basse")
        out["markets"][m] = entry
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyse d'un match par croisements marqué/encaissé")
    parser.add_argument("--domicile", help='ex. "1-1,1-2,0-3" (buts de l\'équipe d\'abord, ses matchs à domicile)')
    parser.add_argument("--exterieur", help='ex. "0-1,0-1,2-1" (buts de l\'équipe d\'abord, ses matchs à l\'extérieur)')
    parser.add_argument("--cotes", nargs="*", default=[], help="marché=cote, ex. home_scores_1plus=1.35")
    parser.add_argument("--calibrer", action="store_true", help="recalcule la calibration depuis Football-Data")
    parser.add_argument("--football-data", default="data/football_data")
    args = parser.parse_args(argv)
    if args.calibrer:
        records, _ = load_football_data(args.football_data)
        CALIBRATION_FILE.write_text(json.dumps(calibrer(records), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"calibration écrite : {CALIBRATION_FILE}")
        return 0
    calibration = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    cotes = {k: float(v) for k, v in (x.split("=") for x in args.cotes)}
    print(json.dumps(analyser(parse_scores(args.domicile), parse_scores(args.exterieur), calibration, cotes), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
