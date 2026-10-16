#!/usr/bin/env python3
"""TEST À L'AVEUGLE de v, protocole figé le 16/10/2026, AVANT tout résultat neuf. Aucun paramètre modifiable pendant le test.
Usage : python evaluation/moteur_v/test_aveugle.py [--max N] [--jeu evaluation/moteur_v/jeu_reglage_ids.json] [--test]

Règles figées (réglées sur les 440 matchs du 28/09 au 14/10 listés dans jeu_reglage_ids.json) :
  S (« sûr »)   : probabilité calibrée (cote + force des adversaires) >= 0,76, verrou d'échantillon brut (75 % si 4-5 matchs, 72 % si 6+),
                  1 pari par match = la plus forte probabilité calibrée.
  V (« valeur »): cote 1,45-1,85, probabilité du calcul simple >= 0,75, 1 pari par match = la plus forte. HYPOTHÈSE (p = 0,06 non corrigé,
                  12 essais) : à prouver.
Matchs comptés : absents du jeu de réglage, avec score, cotes, >= 4 matchs au même lieu pour les deux équipes, triés par date.
Décision (S et V séparément) : ADOPTÉE si >= 100 paris ET ROI >= +5 % ET réussite > moyenne de 1/cote ; sinon REJETÉE ; < 100 paris =
PAS ENCORE JUGEABLE (on attend, on ne change rien). Une règle adoptée doit être confirmée sur un 2e lot avant tout usage réel.
Estimation : 100 paris V vers le 11/11/2026, 100 paris S vers le 20/11/2026 (≈ 26 matchs réglés par jour)."""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from moteur_v import coeur as C, modele as M  # noqa: E402
from moteur_v.donnees import charge  # noqa: E402

CAL2 = (-0.18, 0.89, 0.13)        # cote + probabilité « force des adversaires » (mesuré le 16/10/2026)
SEUIL_S = 0.76
VERROU = lambda n: 0.75 if n <= 5 else 0.72
V_COTE, V_PS = (1.45, 1.85), 0.75
MIN_PARIS, ROI_MIN = 100, 0.05


def p_cal2(cote, p_force):
    q = min(max(1 / cote, 1e-3), 1 - 1e-3)
    pf = min(max(p_force, 1e-3), 1 - 1e-3)
    return 1 / (1 + math.exp(-(CAL2[0] + CAL2[1] * math.log(q / (1 - q)) + CAL2[2] * math.log(pf / (1 - pf)))))


def choisir_s(cands, n_min, lam_force):
    if lam_force is None:
        return None
    ok = []
    for x in cands:
        pc = p_cal2(x["cote"], M.proba_marche(x["pred"], *lam_force))
        if pc >= SEUIL_S - 1e-9 and x["final_moy"] >= VERROU(n_min) - 1e-9:
            ok.append((pc, x))
    return max(ok, key=lambda t: (round(t[0], 9), round(t[1]["final_moy"], 9)))[1] if ok else None


def choisir_v(cands, lam_simple):
    ok = []
    for x in cands:
        if V_COTE[0] - 1e-9 <= x["cote"] <= V_COTE[1] + 1e-9:
            ps = M.proba_marche(x["pred"], *lam_simple)
            if ps >= V_PS - 1e-9:
                ok.append((ps, x))
    return max(ok, key=lambda t: (round(t[0], 9), t[1]["cote"]))[1] if ok else None


def verdict(p):
    n = len(p)
    if n < MIN_PARIS:
        return "PAS ENCORE JUGEABLE (moins de 100 paris)"
    roi = sum((x["cote"] - 1) if x["gagne"] else -1 for x in p) / n
    reussite = sum(x["gagne"] for x in p) / n
    impl = sum(1 / x["cote"] for x in p) / n
    return "ADOPTÉE (à confirmer sur un 2e lot)" if roi >= ROI_MIN and reussite > impl else "REJETÉE"


def resume(p):
    n = len(p)
    if not n:
        return "0 pari"
    w = sum(x["gagne"] for x in p)
    return (f"{n} paris, {w} gagnés = {w / n:.1%}, cote moy. {sum(x['cote'] for x in p) / n:.2f}, seuil de rentabilité moyen "
            f"{sum(1 / x['cote'] for x in p) / n:.1%}, ROI {sum((x['cote'] - 1) if x['gagne'] else -1 for x in p) / n:+.1%}")


def evaluer(matchs, entrees, ids, n_cible=100000):
    forces = M.Forces(entrees)
    lot = [m for m in matchs if m["id"] not in ids and m["h"] is not None]
    lot.sort(key=lambda m: (m["date"], m["id"]))
    P, vus = {"S": [], "V": []}, 0
    for m in lot:
        rd, re_ = C.lignes(m["hd"], True, m["date"]), C.lignes(m["he"], False, m["date"])
        n, cands = C.analyse(rd, re_, m["cotes"])
        if not cands:
            continue
        vus += 1
        if vus > n_cible:
            break
        s = choisir_s(cands, n, forces.lambdas(m["date"], m["dom"], m["ext"]))
        if s:
            P["S"].append({"cote": s["cote"], "gagne": bool(s["pred"](m["h"], m["a"]))})
        v = choisir_v(cands, M.lambdas_simples(rd[-C.FENETRE:], re_[-C.FENETRE:]))   # lignes brutes (point de vue de chaque équipe)
        if v:
            P["V"].append({"cote": v["cote"], "gagne": bool(v["pred"](m["h"], m["a"]))})
    return vus, P


def controles():
    ok = True

    def chk(nom, cond):
        nonlocal ok
        print(("OK   " if cond else "ECHEC"), nom)
        ok = ok and cond
    mk = lambda cote, f=lambda h, a: h + a >= 1: {"marche": "x", "cote": cote, "final_moy": 0.9, "pred": f}
    chk("V garde cote 1.60 (ps élevé)", choisir_v([mk(1.60)], (1.5, 1.2)) is not None)
    chk("V garde la borne 1.45", choisir_v([mk(1.45)], (1.5, 1.2)) is not None)
    chk("V garde la borne 1.85", choisir_v([mk(1.85)], (1.5, 1.2)) is not None)
    chk("V refuse cote 1.30", choisir_v([mk(1.30)], (1.5, 1.2)) is None)
    chk("V refuse cote 2.10", choisir_v([mk(2.10)], (1.5, 1.2)) is None)
    chk("V refuse ps < 0.75", choisir_v([mk(1.60)], (0.3, 0.3)) is None)
    chk("S garde cote 1.26 (calibré >= 0.76)", choisir_s([mk(1.26)], 8, (1.5, 1.2)) is not None)
    chk("S refuse cote 1.40", choisir_s([mk(1.40)], 8, (1.5, 1.2)) is None)
    chk("S refuse sans forces", choisir_s([mk(1.26)], 8, None) is None)
    chk("S verrou : final 0.74 refusé à 4-5 matchs", choisir_s([dict(mk(1.26), final_moy=0.74)], 5, (1.5, 1.2)) is None)
    chk("verdict 80 paris = pas jugeable", verdict([{"cote": 1.5, "gagne": True}] * 80).startswith("PAS"))
    chk("verdict 100 gagnés = adoptée", verdict([{"cote": 1.5, "gagne": True}] * 100).startswith("ADOPT"))
    chk("verdict 100 paris à 60 %, cote 1.5 = rejetée", verdict([{"cote": 1.5, "gagne": i < 60} for i in range(100)]) == "REJETÉE")
    print("TOUS LES TESTS OK" if ok else "DES TESTS ECHOUENT")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=100000)
    ap.add_argument("--jeu", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "jeu_reglage_ids.json"))
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        sys.exit(0 if controles() else 1)
    matchs, entrees = charge()
    vus, P = evaluer(matchs, entrees, set(json.load(open(a.jeu))), a.max)
    print(f"Matchs neufs comptés : {vus}")
    for nom, lib in (("S", "Sûr (calibré >= 0,76)"), ("V", "Valeur (cote 1,45-1,85, calcul simple >= 75 %)")):
        print(f"{nom} {lib}: {resume(P[nom])}\n   -> {verdict(P[nom])}")
