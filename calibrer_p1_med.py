"""Parametres P1 des championnats servis par Matchendirect (Eerste Divisie) -> data/calibration_p1/config_med.json.
Aucune valeur posee a la main : k (lissage) et demi-vie sont ceux de la grille de pouvoir_predictif qui minimisent la perte logarithmique 1X2 des predictions
chronologiques (chaque match predit avec les seuls matchs de dates strictement anterieures). Seules les saisons passees COMPLETES (data/eerste_divisie) sont notees ;
la premiere sert de rodage (aucune equipe n'a d'historique) et la saison en cours, incomplete, n'est jamais notee. Le protocole de calibration des marches
(selection 2324-2425, confirmation 2526) n'est pas applique a ces ligues : aucune correction n'est validee (P1 CONSERVE sur les 7 marches)."""
import json, os, sys
import numpy as np
import calibration_p1 as cp, p1_source_med as pm, pouvoir_predictif as pp

def calibrer(code, matchs=None):
    matchs = pm.historique(code) if matchs is None else matchs; Y = pp.issues(matchs); res = None
    completes = [s for s in sorted({x[1] for x in matchs}) if s in pm.saisons_passees(code)]
    notees = set(completes[1:]) or {x[1] for x in matchs}      # 1re saison = rodage ; historique sans saison passee (tests) : tout est note
    dans = np.array([x[1] in notees for x in matchs])
    for k in pp.K_GRILLE:
        for hl in pp.HL_GRILLE:
            P = pp.predire(matchs, "P1", k, hl); ok = ~np.isnan(P[:, 0]) & dans
            if not ok.any(): continue
            perte = float(pp.pertes(P[ok], Y[ok])[0][:, 0].mean())
            if res is None or perte < res["perte"]: res = {"k": k, "demi_vie_jours": hl, "perte": perte, "n": int(ok.sum())}
    if res is None: return None
    note = "Aucune calibration des marches : protocole de selection/confirmation non applique a cette ligue, P1 conserve."
    return {"p1": {"k": res["k"], "demi_vie_jours": res["demi_vie_jours"]}, "calibrage": {"source": "saisons passees completes (openfootball, Sofascore) + Matchendirect (saison en cours)", "saisons_notees": sorted(notees), "matchs_historique": len(matchs), "matchs_predits": res["n"], "perte_logarithmique_1x2": round(res["perte"], 5)},
            **{mk: {"statut": "P1 CONSERVE", "methode": "P1", "observation": note} for mk in cp.MARCHES}}

def main(chemin=cp.CHEMIN_MED):
    comps = {c: r for c in sorted(pm.COMPETITIONS_MED) if (r := calibrer(c)) is not None}
    doc = {"description": "Parametres P1 des championnats absents de Football-Data, lus dans l'assemblage Matchendirect (calibrer_p1_med.py). Fusionne par calibration_p1.charger.", "competitions": comps}
    with open(chemin, "w", encoding="utf-8") as f: json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc

if __name__ == "__main__":
    print(json.dumps({c: {**v["p1"], **v["calibrage"]} for c, v in main()["competitions"].items()}, ensure_ascii=False))
