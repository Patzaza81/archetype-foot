"""Étude des deux réglages que les règles de l'utilisateur ne donnent pas : fenêtre (jours) et périmètre (tous les matchs ou officiels seulement).
Choisis sur des données, pas posés à la main :
  - matchs de qualification joués sur le terrain d'une équipe, 2010-2017 (réglage) ; 2018 et après (contrôle, jamais utilisé pour choisir) ;
  - pour chaque combinaison : erreur quadratique (Brier) de la « force » du verdict (moyenne des deux taux de passage) sur 10 marchés courants, mesurée sur les MÊMES matchs pour toutes les combinaisons
    (ceux où chaque équipe a au moins NMIN matchs au même lieu dans la plus petite fenêtre) ; la couverture de chaque combinaison est affichée à côté.
Usage : python -m moteur_selections.etude_parametres [fichier.csv] [--ecrire-config]"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_selections import donnees, verdict
import verif_pronostic as V

NMIN = 4                                     # règle de l'utilisateur (07/11/2026)
COTE_MIN = 1.26                              # règle de l'utilisateur (07/11/2026)
MARCHES = ["1", "2", "1N", "N2", "total_plus_1.5", "total_plus_2.5", "total_moins_2.5", "total_moins_3.5", "btts_oui", "btts_non"]
FENETRES = (365, 730, 1095, 1460, 1825, 2190)   # candidats : 1 à 6 ans (la première étude, arrêtée à 4 ans, avait son meilleur résultat au bord de la grille)
COUVERTURE_MIN = 0.5
PERIMETRES = (False, True)                   # officiels_seulement
DEBUT_CONTROLE = "2018-01-01"; DEBUT_REGLAGE = "2010-01-01"


def erreur(H, m, fen, off):
    SA = H.meme_lieu(m["domicile"], "dom", m["date"], fen, off); SB = H.meme_lieu(m["exterieur"], "ext", m["date"], fen, off)
    if len(SA) < NMIN or len(SB) < NMIN: return None
    E = []
    for mk in MARCHES:
        k = V.IDX[mk]; force = (verdict._reussis(SA, True, k) / len(SA) + verdict._reussis(SB, False, k) / len(SB)) / 2
        y = float(V.TABLE[min(m["buts_dom"], V.CAP), min(m["buts_ext"], V.CAP), k]); E.append((force - y) ** 2)
    return sum(E) / len(E)


def mesurer(H, matchs):
    """-> {(fenetre, officiels): [erreur ou None par match]}"""
    return {(f, o): [erreur(H, m, f, o) for m in matchs] for f in FENETRES for o in PERIMETRES}


def comparer(R, n):
    """Seules les combinaisons qui couvrent au moins la moitié des matchs sont comparées (une qui n'en lit qu'un tiers ne peut pas servir le moteur), sur les mêmes matchs.
    -> ({combinaison: résultats}, combinaison retenue). `ecart` = erreur moyenne moins celle de la meilleure, avec son erreur type (écart pris match par match)."""
    couv = {c: sum(x is not None for x in L) / n for c, L in R.items()}
    ok = [c for c in R if couv[c] >= COUVERTURE_MIN]
    communs = [i for i in range(n) if all(R[c][i] is not None for c in ok)]
    moy = {c: sum(R[c][i] for i in communs) / len(communs) for c in ok}
    best = min(ok, key=lambda c: moy[c]); out = {}
    for c in R:
        v = {"couverture": round(couv[c], 3), "comparee": c in ok, "brier": None, "ecart": None, "erreur_type": None, "matchs_communs": len(communs)}
        if c in ok:
            D = [R[c][i] - R[best][i] for i in communs]; m = sum(D) / len(D)
            v.update(brier=round(moy[c], 5), ecart=round(m, 5), erreur_type=round((sum((x - m) ** 2 for x in D) / (len(D) - 1)) ** 0.5 / len(D) ** 0.5, 5))
        out[c] = v
    # parcimonie : parmi les combinaisons dont l'écart avec la meilleure ne dépasse pas 1 erreur type (indiscernables d'elle), la fenêtre la plus courte (matchs les plus récents)
    proches = [c for c in ok if out[c]["ecart"] <= out[c]["erreur_type"]]
    return out, min(proches, key=lambda c: (c[0], moy[c]))


def etudier(chemin=donnees.CHEMIN):
    M = donnees.charger(chemin); H = donnees.Historique(M)
    Q = [m for m in M if m["competition"] == donnees.QUALIF and not m["neutre"]]
    reglage = [m for m in Q if DEBUT_REGLAGE <= m["date"] < DEBUT_CONTROLE]; controle = [m for m in Q if m["date"] >= DEBUT_CONTROLE]
    (A, choix), (B, _) = comparer(mesurer(H, reglage), len(reglage)), comparer(mesurer(H, controle), len(controle))
    return {"reglage": {"matchs": len(reglage), "du": reglage[0]["date"], "au": reglage[-1]["date"], "resultats": {f"{c[0]}j/{'officiels' if c[1] else 'tous'}": v for c, v in A.items()}},
            "controle": {"matchs": len(controle), "du": controle[0]["date"], "au": controle[-1]["date"], "resultats": {f"{c[0]}j/{'officiels' if c[1] else 'tous'}": v for c, v in B.items()}},
            "choix": {"fenetre_jours": choix[0], "officiels_seulement": choix[1]}, "marches": MARCHES, "nmin": NMIN}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    R = etudier(args[0] if args else donnees.CHEMIN)
    for t in ("reglage", "controle"):
        print(f"{t} : {R[t]['matchs']} matchs ({R[t]['du']} -> {R[t]['au']})")
        for c, v in R[t]["resultats"].items(): print(f"  {c:16} couverture {v['couverture']:.0%}  " + (f"brier {v['brier']}  écart {v['ecart']:+} ± {v['erreur_type']}  (sur {v['matchs_communs']} matchs communs)" if v["comparee"] else "non comparée (couverture < 50 %)"))
    print("choix :", R["choix"])
    if "--ecrire-config" in sys.argv:
        cfg = {"cote_min": COTE_MIN, "nmin": NMIN, **R["choix"],
               "origine": "cote_min et nmin : règles de l'utilisateur (07/11/2026) ; fenetre_jours et officiels_seulement : choisis par etude_parametres.py sur les qualifications 2010-2017 (data/selections/etude_parametres.json)"}
        os.makedirs(os.path.dirname(verdict.CONFIG), exist_ok=True)
        with open(verdict.CONFIG, "w", encoding="utf-8") as f: json.dump(cfg, f, ensure_ascii=False, indent=1)
        os.makedirs(donnees.DOSSIER, exist_ok=True)
        with open(os.path.join(donnees.DOSSIER, "etude_parametres.json"), "w", encoding="utf-8") as f: json.dump(R, f, ensure_ascii=False, indent=1)
        print("config écrite :", verdict.CONFIG)
