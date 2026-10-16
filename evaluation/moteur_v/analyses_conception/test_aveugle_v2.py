#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST À L'AVEUGLE figé le 16/10/2026 -- moteur v calibré. Règles gelées, aucun paramètre modifiable pendant le test.
Usage : python3 -I test_aveugle_v2.py <archive_test> <jeu_reglage_ids.json> [--max N] [--test]

  S (« sûr »)   : moteur_v_calibre tel quel (seuil 0.76 calibré + force des adversaires + verrou d'échantillon + vetos).
  V (« valeur »): cote 1.45-1.85, probabilité du calcul simple (moyennes buts marqués/encaissés au même lieu) >= 0.75,
                  1 pari par match = celui dont ce calcul simple est le plus fort. HYPOTHÈSE (p=0.06 non corrigé, 12 essais) -- à prouver.
Matchs comptés : absents du jeu de réglage, avec score, cotes, >= 4 matchs au même lieu pour les deux équipes.
Décision (S et V séparément) : ADOPTÉE si >= 100 paris ET ROI >= +5 % ET réussite > moyenne de 1/cote. Sinon REJETÉE.
Si < 100 paris : PAS ENCORE JUGEABLE (on attend, on ne change rien). Une règle adoptée doit être confirmée sur un 2e lot.
"""
import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("c", os.path.join(HERE, "moteur_v_calibre.py")); c = importlib.util.module_from_spec(_s); _s.loader.exec_module(c)
mv = c.mv
V_COTE = (1.45, 1.85); V_PS = 0.75; MIN_PARIS = 100; ROI_MIN = 0.05
N_CIBLE = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 100000


def lambdas_simples(rh, ra):
    """Buts attendus par moyennes simples au même lieu : (marqués dom + encaissés ext)/2 et (marqués ext + encaissés dom)/2."""
    sH = sum(x[0] for x in rh) / len(rh); cH = sum(x[1] for x in rh) / len(rh)
    sA = sum(x[0] for x in ra) / len(ra); cA = sum(x[1] for x in ra) / len(ra)
    return max((sH + cA) / 2, .05), max((sA + cH) / 2, .05)


def choisir_v(cands, lh, la):
    ok = []
    for x in cands:
        if not (V_COTE[0] - 1e-9 <= x["cote"] <= V_COTE[1] + 1e-9): continue
        ps = c.proba_marche(x["pred"], lh, la)
        if ps >= V_PS - 1e-9: ok.append((ps, x))
    return max(ok, key=lambda t: (round(t[0], 9), t[1]["cote"]))[1] if ok else None


def verdict(p):
    r = mv.resume(p)
    if r["n"] < MIN_PARIS: return "PAS ENCORE JUGEABLE (moins de 100 paris)"
    impl = sum(1 / x["cote"] for x in p) / len(p)
    return "ADOPTÉE (à confirmer sur un 2e lot)" if r["roi"] >= ROI_MIN and r["reussite"] > impl else "REJETÉE"


def evaluer(dossier, ids):
    vus = mv.charger(dossier); frc = c.Forces(vus); cls = c.Classements(vus); lot = []
    for mid, e in vus.items():
        if mid in ids: continue
        sc = mv.score_reel(e); cotes = e.get("cotes_observees") or {}
        if sc is None or not cotes: continue
        rh = mv.lignes(e["equipe_dom"], True, e["date"]); ra = mv.lignes(e["equipe_ext"], False, e["date"])
        n, cands = mv.analyse(rh, ra, cotes)
        if cands is None: continue
        lot.append((e["date"], mid, sc, e, n, cands, rh, ra))
    lot.sort(key=lambda t: (t[0], t[1])); lot = lot[:N_CIBLE]; P = {"S": [], "V": []}
    for d, mid, (h, a), e, n, cands, rh, ra in lot:
        b = c.choisir_calibre(cands, n, c.ecart_points(e), c.SEUIL_CAL, True, cls.ecart_rang(e), True, True, frc.lambdas(e))
        if b: P["S"].append({"cote": b["cote"], "gagne": bool(b["pred"](h, a))})
        lh, la = lambdas_simples(rh[-mv.FENETRE:], ra[-mv.FENETRE:]); bv = choisir_v(cands, lh, la)
        if bv: P["V"].append({"cote": bv["cote"], "gagne": bool(bv["pred"](h, a))})
    return lot, P


def tests():
    ok = True
    def chk(nom, cond):
        nonlocal ok; print(("OK   " if cond else "ECHEC"), nom); ok = ok and cond
    mk = lambda cote: {"marche": "x", "cote": cote, "pred": lambda h, a: h + a >= 1}
    chk("V garde cote 1.60 si ps >= 0.75 (lambdas 1.5/1.2)", choisir_v([mk(1.60)], 1.5, 1.2) is not None)
    chk("V garde cote 1.45 (borne basse incluse)", choisir_v([mk(1.45)], 1.5, 1.2) is not None)
    chk("V garde cote 1.85 (borne haute incluse)", choisir_v([mk(1.85)], 1.5, 1.2) is not None)
    chk("V refuse cote 1.30 (hors bande)", choisir_v([mk(1.30)], 1.5, 1.2) is None)
    chk("V refuse cote 2.10 (hors bande)", choisir_v([mk(2.10)], 1.5, 1.2) is None)
    chk("V refuse si ps < 0.75 (lambdas 0.3/0.3)", choisir_v([mk(1.60)], 0.3, 0.3) is None)
    chk("lambdas simples : (3+1)/2 et (1+0)/2", lambdas_simples([(3, 0)], [(1, 1)]) == (2.0, 0.5))
    chk("verdict : 80 paris = pas encore jugeable", verdict([{"cote": 1.5, "gagne": True}] * 80).startswith("PAS"))
    chk("verdict : 100 paris gagnés = adoptée", verdict([{"cote": 1.5, "gagne": True}] * 100).startswith("ADOPT"))
    chk("verdict : 100 paris à 60 %, cote 1.5 = rejetée", verdict([{"cote": 1.5, "gagne": i < 60} for i in range(100)]) == "REJETÉE")
    print("TOUS LES TESTS OK" if ok else "DES TESTS ECHOUENT"); return ok


if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if tests() else 1)
    lot, P = evaluer(sys.argv[1], set(json.load(open(sys.argv[2]))))
    print(f"Matchs neufs comptés : {len(lot)}" + (f" ({lot[0][0]} -> {lot[-1][0]})" if lot else ""))
    for nom, lib in (("S", "Sûr (seuil 0.76 calibré)"), ("V", "Valeur (cote 1.45-1.85, calcul simple >= 75 %)")):
        print(f"{nom} {lib}: {mv.fmt(mv.resume(P[nom]))}\n   -> {verdict(P[nom])}")
