# -*- coding: utf-8 -*-
"""Rapport des verdicts sur resultats REELS : uniquement les paris du journal gele avant le coup d'envoi, matchs termines.
Usage : python rapport_verdicts.py [jour_debut jour_fin]  (dates ISO, par defaut tout le journal) -> JSON sur stdout."""
import json, sys, collections
import verif_pronostic as V
import p1_page_donnees as pd

def tranches(valeurs, k=4):
    """Bornes de tranches de cote prises sur les donnees (quantiles), pas des constantes posees a la main."""
    v = sorted(valeurs); return sorted({round(v[min(len(v) - 1, (len(v) * i) // k)], 2) for i in range(1, k)})

def etiquette(x, bornes):
    for b in bornes:
        if x < b: return f"< {b}"
    return f">= {bornes[-1]}" if bornes else "toutes"

def stats(L):
    n = len(L); r = sum(e["gagne"] for e in L); lo, hi = V.wilson(r, n) if n else (0, 0)
    return {"paris": n, "reussis": r, "taux": round(r / n, 4) if n else None, "ic95": [round(lo, 3), round(hi, 3)],
            "rendement_mise_egale": round(sum((e["cote"] - 1) if e["gagne"] else -1 for e in L) / n, 4) if n else None}

def groupes(E, cle): 
    d = collections.defaultdict(list)
    for e in E: d[cle(e)].append(e)
    return {k: stats(v) for k, v in sorted(d.items(), key=lambda kv: -len(kv[1]))}

def rapport(debut=None, fin=None, chemin=V.JOURNAL, flux=V.FLUX):
    anom = V.verifier_journal(chemin)
    if anom: raise RuntimeError(f"journal gele non intact : {anom[:3]}")
    S = pd.scores(flux); J = [r for r in V.lire_journal(chemin) if (not debut or r["date"] >= debut) and (not fin or r["date"] <= fin)]
    E = []
    for r in J:
        sc = S.get(r["match_id"])
        if sc is None: continue
        E.append({**r, "gagne": bool(V.TABLE[min(sc["buts_dom"], V.CAP), min(sc["buts_ext"], V.CAP), V.IDX[r["marche"]]]), "famille": V.groupe(r["marche"])})
    out = {"periode": [min((r["date"] for r in J), default=None), max((r["date"] for r in J), default=None)], "paris_geles": len(J), "matchs_geles": len({r["match_id"] for r in J}),
           "paris_avec_resultat": len(E), "matchs_avec_resultat": len({e["match_id"] for e in E})}
    if not E: return out
    b = tranches([e["cote"] for e in E]); out["bornes_cote"] = b
    out.update({"global": stats(E), "par_verdict": groupes(E, lambda e: e["verdict"]), "par_cote": groupes(E, lambda e: etiquette(e["cote"], b)),
                "par_verdict_et_cote": groupes(E, lambda e: f'{e["verdict"]} | {etiquette(e["cote"], b)}'), "par_famille": groupes(E, lambda e: e["famille"]),
                "par_marche": groupes(E, lambda e: e["marche"]), "par_jour": groupes(E, lambda e: e["date"])})
    return out

if __name__ == "__main__":
    a = sys.argv[1:]; print(json.dumps(rapport(*(a[:2] if a else [])), ensure_ascii=False, indent=1))
