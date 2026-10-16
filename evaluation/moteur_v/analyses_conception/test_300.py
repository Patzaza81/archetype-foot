#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test À L'AVEUGLE de la version réglée du moteur v -- protocole figé le 16/10/2026, AVANT de voir un seul résultat.

Usage :  python3 -I test_300.py <dossier archive_test> <jeu_reglage_ids.json> [--test]

Règles figées (réglées en trichant sur les 440 matchs du 28/09 au 14/10, voir jeu_reglage_ids.json) :
  A : « Buts d'une équipe », cote 1,50-2,00, pourcentage final >= 60 %, marge sur 1/cote >= 5 points
  B : « Total buts »,        cote 1,26-1,74, pourcentage final >= 80 %, marge sur 1/cote >= 5 points
  C : moteur v tel que testé le 16/10 (variante A, retenus + alertes) -- témoin
Un seul pari par match (pourcentage final le plus haut, à égalité la cote la plus haute).

Matchs comptés : UNIQUEMENT ceux absents du jeu de réglage, avec score, cotes et >= 4 matchs au même lieu pour les deux équipes.
Le test s'arrête aux 300 premiers (par date). Aucun paramètre ne doit être modifié pendant le test.

Critère de décision fixé à l'avance, pour A et pour B séparément (C sert de témoin) :
  ADOPTÉE si, sur au moins 100 paris : ROI >= +5 % ET taux de réussite > probabilité implicite moyenne (1/cote).
  Sinon REJETÉE. Une règle adoptée doit ensuite être confirmée sur un second lot avant tout usage réel.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_sp = importlib.util.spec_from_file_location("mv", os.path.join(HERE, "moteur_v_test.py"))
mv = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(mv)

REGLES = {
    "A": {"familles": {"Buts d'une équipe"}, "cote": (1.5, 2.0), "t": 0.60, "marge": 0.05},
    "B": {"familles": {"Total buts"}, "cote": (1.26, 1.74), "t": 0.80, "marge": 0.05},
}
N_CIBLE = 300
if "--max" in sys.argv:  # ex. --max 600 : même protocole, plus de matchs (il faut 100 paris par règle pour décider)
    N_CIBLE = int(sys.argv[sys.argv.index("--max") + 1])
MIN_PARIS = 100
ROI_MIN = 0.05


def choisir_regle(cands, regle):
    """Un pari par match selon une règle figée. cands = candidats de mv.analyse."""
    ok = []
    for c in cands:
        if famille_de(c) not in regle["familles"]:
            continue
        lo, hi = regle["cote"]
        if not (lo - 1e-9 <= c["cote"] <= hi + 1e-9):
            continue
        f = c["final_moy"]
        if f < regle["t"] - 1e-9 or f - 1 / c["cote"] < regle["marge"] - 1e-9:
            continue
        ok.append(c)
    if not ok:
        return None
    return max(ok, key=lambda c: (round(c["final_moy"], 9), c["cote"]))


def famille_de(c):
    return mv.famille(c["marche"])


def lot_aveugle(dossier, ids_reglage):
    vus = mv.charger(dossier)
    lot = []
    for mid, e in vus.items():
        if mid in ids_reglage:
            continue
        sc = mv.score_reel(e)
        cotes = e.get("cotes_observees") or {}
        if sc is None or not cotes:
            continue
        d = e["date"]
        n, c = mv.analyse(mv.lignes(e["equipe_dom"], True, d), mv.lignes(e["equipe_ext"], False, d), cotes)
        if c is None:
            continue
        lot.append((d, mid, sc, c))
    lot.sort(key=lambda x: (x[0], x[1]))
    return lot[:N_CIBLE], len(lot)


def evaluer(lot):
    paris = {"A": [], "B": [], "C": []}
    for d, mid, (h, a), cands in lot:
        for nom, regle in REGLES.items():
            b = choisir_regle(cands, regle)
            if b:
                paris[nom].append({"cote": b["cote"], "gagne": bool(b["pred"](h, a)), "final": b["final_moy"]})
        st, b = mv.choisir(cands, "moy")
        if st in ("RETENU", "ALERTE"):
            paris["C"].append({"cote": b["cote"], "gagne": bool(b["pred"](h, a)), "final": b["final_moy"]})
    return paris


def verdict(p):
    r = mv.resume(p)
    if r["n"] < MIN_PARIS:
        return "PAS ENCORE JUGEABLE (moins de 100 paris)"
    impl = sum(1 / x["cote"] for x in p) / len(p)
    if r["roi"] >= ROI_MIN and r["reussite"] > impl:
        return "ADOPTÉE (à confirmer sur un second lot)"
    return "REJETÉE"


def tests():
    ok = True

    def chk(nom, cond):
        nonlocal ok
        print(("OK   " if cond else "ECHEC"), nom)
        ok = ok and cond

    mk = lambda marche, cote, fin: {"marche": marche, "cote": cote, "final_moy": fin, "pred": lambda h, a: True}
    # 3 qui passent
    chk("A : buts équipe, cote 1,60, 70 %, marge 7,5 pts",
        choisir_regle([mk("Plus de 0.5 buts - Domicile", 1.60, 0.70)], REGLES["A"]) is not None)
    chk("B : total, cote 1,40, 85 %, marge 13 pts",
        choisir_regle([mk("Moins de 3.5 buts", 1.40, 0.85)], REGLES["B"]) is not None)
    chk("B : total, cote 1,74, 80 %, marge 22 pts (bords inclus)",
        choisir_regle([mk("Plus de 1.5 buts", 1.74, 0.80)], REGLES["B"]) is not None)
    # 3 qui échouent
    chk("A refuse un total de buts (mauvaise famille)",
        choisir_regle([mk("Plus de 1.5 buts", 1.60, 0.90)], REGLES["A"]) is None)
    chk("B refuse 79 % (sous le seuil)",
        choisir_regle([mk("Moins de 3.5 buts", 1.40, 0.79)], REGLES["B"]) is None)
    chk("A refuse une marge de 3 pts (cote 1,50, 70 % : 70 - 66,7)",
        choisir_regle([mk("Plus de 0.5 buts - Domicile", 1.50, 0.69)], REGLES["A"]) is None)
    chk("B refuse une cote de 1,20", choisir_regle([mk("Moins de 3.5 buts", 1.20, 0.95)], REGLES["B"]) is None)
    # choix : un seul pari, plus haut pourcentage
    best = choisir_regle([mk("Moins de 3.5 buts", 1.40, 0.82), mk("Plus de 1.5 buts", 1.50, 0.90)], REGLES["B"])
    chk("B garde le pourcentage le plus haut", best["marche"] == "Plus de 1.5 buts")
    # critère de décision
    chk("verdict : 80 paris = pas encore jugeable", verdict([{"cote": 1.5, "gagne": True}] * 80).startswith("PAS"))
    chk("verdict : 100 paris gagnés à 1,5 = adoptée", verdict([{"cote": 1.5, "gagne": True}] * 100).startswith("ADOPT"))
    chk("verdict : 100 paris, 60 % à 1,5 (ROI -10 %) = rejetée",
        verdict([{"cote": 1.5, "gagne": i < 60} for i in range(100)]) == "REJETÉE")
    print("TOUS LES TESTS OK" if ok else "DES TESTS ECHOUENT")
    return ok


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(0 if tests() else 1)
    ids = set(json.load(open(sys.argv[2])))
    lot, dispo = lot_aveugle(sys.argv[1], ids)
    print(f"Matchs réglés hors jeu de réglage : {dispo} (comptés : {len(lot)} sur {N_CIBLE})")
    if not lot:
        print("Aucun match neuf réglé pour l'instant.")
        sys.exit(0)
    print(f"Période : {lot[0][0]} -> {lot[-1][0]}")
    P = evaluer(lot)
    for nom, lib in (("A", "Buts d'une équipe 1,50-2,00"), ("B", "Total buts 1,26-1,74"), ("C", "Moteur v actuel (témoin)")):
        print(f"{nom} {lib}: {mv.fmt(mv.resume(P[nom]))}")
        if nom != "C":
            print(f"   -> {verdict(P[nom])}")
    if len(lot) < N_CIBLE:
        print(f"Test incomplet : encore {N_CIBLE - len(lot)} matchs à attendre avant de décider.")
