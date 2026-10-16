#!/usr/bin/env python3
"""Rejoue le VRAI moteur v (package moteur_v) sur les 440 matchs du jeu de réglage : réussite du pronostic principal et des « autres »
par niveau. Sert à vérifier que le code du dépôt reproduit les mesures de conception (principal : SÛR 312 paris 74,7 % ; MOYEN 85 paris
65,9 % ; RISQUÉ 35 paris 54,3 % ; NON CALIBRÉ 8 paris 37,5 % ; autres : 1,4 par match en moyenne).
Usage : python evaluation/moteur_v/rejoue_niveaux.py [--jeu evaluation/moteur_v/jeu_reglage_ids.json]"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from moteur_v import marches as MK, modele as M, pronostics as P  # noqa: E402
from moteur_v.donnees import charge  # noqa: E402


def rejoue(ids):
    matchs, entrees = charge()
    forces, classements = M.Forces(entrees), M.Classements(entrees)
    res, nautres = collections.defaultdict(list), []
    for m in matchs:
        if m["id"] not in ids or m["h"] is None:
            continue
        l = P.proposer(m, forces, classements)
        if not l:
            continue
        nautres.append(len(l["autres"]))
        res[("principal", l["principal"]["niveau"])].append(MK.gagne(l["principal"]["marche"], m["h"], m["a"]))
        for p in l["autres"]:
            res[("autres", p["niveau"])].append(MK.gagne(p["marche"], m["h"], m["a"]))
    return res, nautres


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "jeu_reglage_ids.json"))
    a = ap.parse_args()
    res, na = rejoue(set(json.load(open(a.jeu))))
    print(f"matchs {len(na)} | autres par match : moyenne {sum(na) / len(na):.1f}, aucun autre : {sum(x == 0 for x in na)} matchs")
    for k in sorted(res):
        v = res[k]
        print(k, len(v), "paris, réussite %.1f%%" % (100 * sum(v) / len(v)))
