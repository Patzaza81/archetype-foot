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


def evaluer_bloc(bookmaker: str = "ps", moment: str = "cloture") -> dict:
    """Même jugement, sur le bloc de saisons (matchs + cotes d'ouverture ou de clôture, Pinnacle par défaut). Test = 40 % les plus récents.
    Ajoute le handicap asiatique sur les lignes en .5 (pas de remboursement possible)."""
    from . import bloc_saisons as B
    bloc = B.charger()
    matchs = bloc["liste"]
    hist: dict = {}
    for m in matchs:
        hist.setdefault(m["domicile"], []).append((m["date"], True, m["buts_dom"], m["buts_ext"]))
        hist.setdefault(m["exterieur"], []).append((m["date"], False, m["buts_ext"], m["buts_dom"]))

    def avant(eq: str, lieu: bool, jour: str) -> list[tuple[int, int]]:
        return [(g, c) for d, dom, g, c in sorted(x for x in hist[eq] if x[0] < jour and x[1] == lieu)[-5:]]
    lignes = []
    for m in matchs:
        d, e = avant(m["domicile"], True, m["date"]), avant(m["exterieur"], False, m["date"])
        if len(d) >= 3 and len(e) >= 3:
            lignes.append((m, d, e))
    test = lignes[int(len(lignes) * 0.6):]
    cle1, cle2, cleah = f"1x2_{moment}", f"plus_moins_2_5_{moment}", "handicap_asiatique_ouverture"
    acc = {"1x2": [0.0, 0.0, 0], "ou": [0.0, 0.0, 0], "ah": [0.0, 0.0, 0]}
    for m, d, e in test:
        g = C.grille(*C.buts_attendus(d, e), C.RHO)
        gd, ge = m["buts_dom"], m["buts_ext"]
        c1 = m["cotes"].get(cle1, {}).get(bookmaker)
        if c1:
            mk = _sans_marge(*c1)
            pm = [C.proba(g, lambda i, j: i > j), C.proba(g, lambda i, j: i == j), C.proba(g, lambda i, j: i < j)]
            k = 0 if gd > ge else (1 if gd == ge else 2)
            acc["1x2"][0] += math.log(pm[k]); acc["1x2"][1] += math.log(mk[k]); acc["1x2"][2] += 1
        c2 = m["cotes"].get(cle2, {}).get(bookmaker)
        if c2:
            po, y = C.proba(g, lambda i, j: i + j > 2.5), int(gd + ge > 2.5)
            acc["ou"][0] += (po - y) ** 2; acc["ou"][1] += (_sans_marge(*c2)[0] - y) ** 2; acc["ou"][2] += 1
        ah = m["cotes"].get(cleah, {})
        c3 = ah.get(bookmaker)
        if c3 and abs(ah["ligne_domicile"] * 2) % 2 == 1:          # ligne en .5 : pas de remboursement
            h = ah["ligne_domicile"]
            pd = C.proba(g, lambda i, j: i + h > j)
            y = int(gd + h > ge)
            acc["ah"][0] += (pd - y) ** 2; acc["ah"][1] += (_sans_marge(*c3)[0] - y) ** 2; acc["ah"][2] += 1
    r = lambda k: {"matchs": acc[k][2], "modele": round(acc[k][0] / acc[k][2], 4), "marche": round(acc[k][1] / acc[k][2], 4)} if acc[k][2] else None
    return {"bloc": bloc["saisons"], "bookmaker": bookmaker, "moment": moment, "matchs_test": len(test),
            "1x2_loglik (plus haut = mieux)": r("1x2"), "plus_moins_2_5_brier (plus bas = mieux)": r("ou"), "handicap_asiatique_demi_ligne_brier (plus bas = mieux)": r("ah")}


def evaluer_bloc_grand_test(bookmaker: str = "moy", moment: str = "cloture", min_test: int = 10000) -> dict:
    """Jugement sur AU MOINS `min_test` matchs jamais vus : on règle (mu, shrink, rho) sur la tranche la plus ancienne seulement,
    et tout le reste du bloc sert de test. Écart modèle-marché apparié par match (moyenne ± erreur-type), pas seulement deux moyennes."""
    from . import bloc_saisons as B
    matchs = B.charger()["liste"]
    hist: dict = {}
    for m in matchs:
        hist.setdefault(m["domicile"], []).append((m["date"], True, m["buts_dom"], m["buts_ext"]))
        hist.setdefault(m["exterieur"], []).append((m["date"], False, m["buts_ext"], m["buts_dom"]))
    for v in hist.values():
        v.sort()

    def avant(eq: str, lieu: bool, jour: str) -> list[tuple[int, int]]:
        return [(g, c) for d, dom, g, c in hist[eq] if d < jour and dom == lieu][-5:]
    lignes = []
    for m in matchs:
        d, e = avant(m["domicile"], True, m["date"]), avant(m["exterieur"], False, m["date"])
        if len(d) >= 3 and len(e) >= 3:
            lignes.append((m, d, e))
    lignes.sort(key=lambda x: x[0]["date"])
    k = len(lignes) - min_test
    if k < 500:
        return {"erreur": f"seulement {len(lignes)} matchs exploitables : pas assez pour {min_test} en test"}
    app, test = lignes[:k], lignes[k:]
    mu_d = sum(m["buts_dom"] for m, _, _ in app) / len(app)
    mu_e = sum(m["buts_ext"] for m, _, _ in app) / len(app)

    def ll(sample, sh, rho):
        t = 0.0
        for m, d, e in sample:
            g = C.grille(*C.buts_attendus(d, e, mu_dom=mu_d, mu_ext=mu_e, shrink=sh), rho)
            t += math.log(max(g[min(m["buts_dom"], 10)][min(m["buts_ext"], 10)], 1e-12))
        return t / len(sample)
    sh, rho = max(((ll(app[::2], s, r), s, r) for s in (1, 2, 4, 6, 8, 12) for r in (-0.15, -0.1, -0.05, 0.0, 0.05)))[1:]
    cle1, cle2, cleah = f"1x2_{moment}", f"plus_moins_2_5_{moment}", "handicap_asiatique_ouverture"
    diffs = {"1x2": [], "ou": [], "ah": []}
    for m, d, e in test:
        g = C.grille(*C.buts_attendus(d, e, mu_dom=mu_d, mu_ext=mu_e, shrink=sh), rho)
        gd, ge = m["buts_dom"], m["buts_ext"]
        c1 = m["cotes"].get(cle1, {}).get(bookmaker)
        if c1:
            mk = _sans_marge(*c1)
            pm = [C.proba(g, lambda i, j: i > j), C.proba(g, lambda i, j: i == j), C.proba(g, lambda i, j: i < j)]
            kk = 0 if gd > ge else (1 if gd == ge else 2)
            diffs["1x2"].append(math.log(pm[kk]) - math.log(mk[kk]))          # > 0 : le modèle fait mieux
        c2 = m["cotes"].get(cle2, {}).get(bookmaker)
        if c2:
            y = int(gd + ge > 2.5)
            diffs["ou"].append((_sans_marge(*c2)[0] - y) ** 2 - (C.proba(g, lambda i, j: i + j > 2.5) - y) ** 2)   # > 0 : le modèle fait mieux
        ah = m["cotes"].get(cleah, {})
        c3 = ah.get(bookmaker)
        if c3 and abs(ah["ligne_domicile"] * 2) % 2 == 1:
            h = ah["ligne_domicile"]
            y = int(gd + h > ge)
            diffs["ah"].append((_sans_marge(*c3)[0] - y) ** 2 - (C.proba(g, lambda i, j: i + h > j) - y) ** 2)

    def r(x):
        n = len(x)
        if n < 2:
            return None
        mo = sum(x) / n
        se = (sum((v - mo) ** 2 for v in x) / (n - 1) / n) ** 0.5
        return {"matchs": n, "ecart_moyen (>0 = modele meilleur)": round(mo, 5), "erreur_type": round(se, 5), "z": round(mo / se, 1)}
    return {"apprentissage": len(app), "test": len(test), "date_debut_test": test[0][0]["date"], "mu_dom": round(mu_d, 3), "mu_ext": round(mu_e, 3),
            "shrink": sh, "rho": rho, "bookmaker": bookmaker, "moment": moment,
            "1x2_logloss": r(diffs["1x2"]), "plus_moins_2_5_brier": r(diffs["ou"]), "handicap_asiatique_demi_ligne_brier": r(diffs["ah"])}
