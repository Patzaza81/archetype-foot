"""Banc contre le marché sur Football-Data (cotes Bet365 d'ouverture lues dans les fichiers bruts, ÉVALUATION SEULEMENT).

Les cotes ne servent jamais à calculer un pronostic : elles jugent le moteur (log-vraisemblance 1X2 et Brier plus/moins 2,5 contre
le marché sans marge) et mesurent la règle « plus probable, cote >= 1,26 » sur les 5 marchés cotés (1X2, plus/moins 2,5).
Test = 40 % les plus récents (les paramètres du moteur sont appris sur les 60 % premiers).
Usage : python -m matrice_scenarios.banc_cotes_football_data
"""
from __future__ import annotations

import math

from . import comportement as C
from .football_data import load_football_data


def _derniers(histoire: list[dict], lieu: str, jour: str, n: int = 5) -> list[tuple[int, int]]:
    r = sorted([x for x in histoire if x["venue"] == lieu and str(x["date"])[:10] < jour], key=lambda x: x["date"])[-n:]
    return [(x["goals_for"], x["goals_against"]) for x in r]


def _sans_marge(*cotes: float) -> list[float]:
    inv = [1 / x for x in cotes]
    s = sum(inv)
    return [i / s for i in inv]


def evaluer() -> dict:
    fd, _ = load_football_data(with_proxy_odds=True)
    lignes = []
    for r in sorted(fd, key=lambda r: r["date"]):
        d, e = _derniers(r["home_history"], "home", r["date"]), _derniers(r["away_history"], "away", r["date"])
        if len(d) >= 3 and len(e) >= 3:
            lignes.append((r, d, e))
    test = [x for x in lignes[int(len(lignes) * 0.6):] if x[0].get("target_odds")]
    ll_m = ll_k = br_m = br_k = 0.0
    picks = []
    for r, d, e in test:
        t = r["target_odds"]
        g = C.grille(*C.buts_attendus(d, e), C.RHO)
        pm = [C.proba(g, lambda i, j: i > j), C.proba(g, lambda i, j: i == j), C.proba(g, lambda i, j: i < j)]
        mk = _sans_marge(t["home_win"], t["draw"], t["away_win"])
        gd, ge = r["home_goals"], r["away_goals"]
        k = 0 if gd > ge else (1 if gd == ge else 2)
        ll_m += math.log(pm[k])
        ll_k += math.log(mk[k])
        po = C.proba(g, lambda i, j: i + j > 2.5)
        y = int(gd + ge > 2.5)
        br_m += (po - y) ** 2
        br_k += (_sans_marge(t["over_2_5"], t["under_2_5"])[0] - y) ** 2
        cands = [(pm[0], t["home_win"], gd > ge), (pm[1], t["draw"], gd == ge), (pm[2], t["away_win"], gd < ge),
                 (po, t["over_2_5"], gd + ge > 2.5), (1 - po, t["under_2_5"], gd + ge < 2.5)]
        el = [c for c in cands if c[1] >= 1.26]
        if el:
            picks.append(max(el, key=lambda c: (c[0], c[1])))
    n, m = len(test), len(picks)
    cote = sum(p[1] for p in picks) / m
    return {"matchs_test_avec_cotes": n, "loglik_1x2_modele": round(ll_m / n, 4), "loglik_1x2_marche": round(ll_k / n, 4),
            "brier_plus2_5_modele": round(br_m / n, 4), "brier_plus2_5_marche": round(br_k / n, 4),
            "regle_cote_1_26": {"matchs": m, "reussite": round(sum(p[2] for p in picks) / m, 4), "annonce": round(sum(p[0] for p in picks) / m, 4),
                                "cote_moyenne": round(cote, 3), "reussite_requise": round(1 / cote, 4),
                                "roi_a_plat": round(sum((p[1] - 1) if p[2] else -1 for p in picks) / m, 4)}}


if __name__ == "__main__":
    import json
    print(json.dumps(evaluer(), ensure_ascii=False, indent=1))
