"""Backtest chronologique du classement du Journal : ancien (Wilson, lissé) contre nouveau (mode « preuves »).

Sans fuite : les candidats de chaque jour sont reconstruits avec les seuls matchs de date STRICTEMENT antérieure
(journal_classement.candidats_walk_forward) et le calibrage de chaque jour n'utilise que les jours passés.
Bibliothèque standard uniquement. Usage : python evaluation/backtest_journal_preuves.py [sortie.json]
"""
import json
import math
import os
import statistics as st
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import journal_classement as jc  # noqa: E402
import journal_rentabilite as jr  # noqa: E402

TOP = 15


def gagne(r):
    return 1.0 if r["resultat"] == 1 else 0.0


def cote_ok(r):
    return r["cote"] is not None and jc.COTE_MIN <= r["cote"] <= jc.COTE_MAX


def rang_ancien(r, p):
    """Classement de production avant la correction (generateur_tickets.candidate_rank, partie Journal)."""
    return (3 if r["joues"] >= 5 else 0, r["wilson"], r["frequence"], -999.0, r["joues"], p * r["cote"] - 1, -r["cote"])


def un_par_match(rows, cle):
    out, vus = [], set()
    for r in sorted(rows, key=cle, reverse=True):
        k = jc.cle_match(r)
        if k not in vus:
            vus.add(k)
            out.append(r)
    return out


def resume(nom, sel):
    n = len(sel)
    if not n:
        return {"variante": nom, "paris": 0, "jours": 0}
    profits = [r["profit"] for r, _ in sel]
    return {"variante": nom, "paris": n, "jours": len({r["date"] for r, _ in sel}),
            "reussite": round(sum(gagne(r) for r, _ in sel) / n, 3), "annoncee": round(st.mean(p for _, p in sel), 3),
            "implicite": round(st.mean(1 / r["cote"] for r, _ in sel), 3), "roi": round(st.mean(profits), 3),
            "erreur_std_roi": round(st.pstdev(profits) / math.sqrt(n), 3) if n > 1 else None}


def execute(R):
    jours = sorted({r["date"] for r in R})
    sel = {"ANCIEN_WILSON": [], "ANCIEN_LISSE": [], "PROBABILITE_SEULE": [], "NOUVEAU_PREUVES": []}
    for d in jours:
        jour = [r for r in R if r["date"] == d and cote_ok(r)]
        passes = [r for r in R if r["date"] < d]
        for nom, cle in (("ANCIEN_WILSON", "wilson"), ("ANCIEN_LISSE", "lissee")):
            pool = sorted([r for r in jour if r[cle] >= 1 / r["cote"]], key=lambda r: rang_ancien(r, r[cle]), reverse=True)[:TOP]
            sel[nom] += [(r, r[cle]) for r in pool]
        cal = jc.ajuste_calibrage(passes)
        if cal:
            retenus, _ = jc.selectionne(jour, cal)
            sel["NOUVEAU_PREUVES"] += [(r, r["p_cal"]) for r in retenus]
            pool = un_par_match(jour, lambda r: (jc.proba_calibree(cal, r["lissee"], 1 / r["cote"]), r["match_id"]))[:TOP]
            sel["PROBABILITE_SEULE"] += [(r, jc.proba_calibree(cal, r["lissee"], 1 / r["cote"])) for r in pool]
    out = {}
    for nom, s in sel.items():
        out[nom] = {"total": resume(nom, s), "par_cote": {
            f"{lo}-{hi}": resume(nom, [(r, p) for r, p in s if lo <= r["cote"] < hi]) for lo, hi in ((1.26, 1.5), (1.5, 2.0), (2.0, 3.01))}}
    out["TOUS_LES_CANDIDATS"] = {"total": resume("TOUS", [(r, r["lissee"]) for r in R if cote_ok(r)])}
    brier = {"wilson": [], "lissee": [], "marche_seul": [], "calibree": [], "moyenne_passee": []}
    for d in jours:
        passes = [r for r in R if r["date"] < d]
        cal = jc.ajuste_calibrage(passes)
        if not cal:
            continue
        m = sum(gagne(r) for r in passes) / len(passes)
        for r in (x for x in R if x["date"] == d and x["cote"]):
            y = gagne(r)
            brier["wilson"].append((r["wilson"] - y) ** 2)
            brier["lissee"].append((r["lissee"] - y) ** 2)
            brier["marche_seul"].append((1 / r["cote"] - y) ** 2)
            brier["calibree"].append((jc.proba_calibree(cal, r["lissee"], 1 / r["cote"]) - y) ** 2)
            brier["moyenne_passee"].append((m - y) ** 2)
    out["brier"] = {k: round(st.mean(v), 4) for k, v in brier.items() if v}
    out["brier_observations"] = len(brier["wilson"])
    out["candidats"] = len(R)
    out["periode"] = [jours[0], jours[-1]] if jours else None
    return out


def main():
    R = jc.candidats_walk_forward(jr, jr.charge_tous_resultats())
    res = execute(R)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
