# -*- coding: utf-8 -*-
"""Autotests de moteur_v2_6_10 : invariants et frontières du noyau, puis contrat du moteur complet.

Porte les autotests de l'ancien `moteur_v2_6_9.py --autotest` (mêmes valeurs, mêmes frontières) vers le noyau autonome.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import fsum

from . import noyau as n
from .core import NOM_MOTEUR, VERSION_MOTEUR, analyser_match as analyser_complet


def autotest() -> int:
    ok = True

    def check(cond: bool, msg: str) -> None:
        nonlocal ok
        print(("  OK   " if cond else "  ÉCHEC ") + msg)
        ok = ok and cond

    print("Autotests moteur_v2_6_10")
    n.HANDICAP_ENTIER_REMBOURSE = False
    mat = n.construire_matrice(1.6, 1.1)
    check(abs(fsum(c for r in mat for c in r) - 1.0) < 1e-12, "somme de la matrice = 1")
    for H in n.LIGNES_HANDICAP:
        wd, pu, we = n.handicap_probas(mat, H)
        check(abs(wd + pu + we - 1.0) < 1e-12, f"invariant P_win_dom + P_push + P_win_ext = 1 (H={H})")
        if H != int(H):
            check(pu == 0.0, f"P_push = 0 sur la ligne .5 (H={H})")
        else:
            check(pu > 0.0, f"P_push > 0 sur la ligne entière (H={H})")
    check(n.seuil_ev_min(3.50) == 0.09 and n.seuil_ev_min(3.49) == 0.07 and n.seuil_ev_min(2.50) == 0.07
          and n.seuil_ev_min(2.49) == 0.06, "frontières de seuil_ev_min")
    check(n.parse_handicap_key("handicap_dom_-2_0") == ("dom", -2.0), "parse handicap_dom_-2_0")
    check(n.parse_handicap_key("handicap_ext_+1_5") == ("ext", 1.5), "parse handicap_ext_+1_5")
    check(n.parse_handicap_key("handicap_nul_1_0") is None, "handicap_nul_X non reconnu")
    l1 = n.evaluer_ligne("x", 0.5299, 2.0, 0.5, 0.0)
    l2 = n.evaluer_ligne("x", 0.54, 2.0, 0.5, 0.0)
    check((not l1["is_value"]) and l2["is_value"], "frontière is_value (cote 2.00)")
    l3 = n.evaluer_ligne("h", 0.5, 2.0, 0.5, 0.2)
    check(abs(l3["ev"] - (0.5 * 2.0 - 1.0 + 0.2)) < 1e-12 and abs(l3["p_juste"] - 0.4) < 1e-12, "EV et p_juste avec push")

    # V1
    g, rej = n.verifier_v1_marge_groupe({"victoire": 2.0, "nul": 3.4, "defaite": 3.8}, {"1X2"}, 0)
    check("1X2" in g and not rej, "V1 : marge 1.057 acceptée")
    g, rej = n.verifier_v1_marge_groupe({"victoire": 1.5, "nul": 2.5, "defaite": 2.5}, {"1X2"}, 0)
    check("1X2" not in g and "1X2" in rej, "V1 : marge 1.467 rejetée (> 1.20)")
    g, rej = n.verifier_v1_marge_groupe({"victoire": 3.5, "nul": 4.0, "defaite": 4.0}, {"1X2"}, 0)
    check("1X2" not in g and "1X2" in rej, "V1 : marge 0.786 rejetée (< 1.00)")

    # V2
    hand = {"handicap_dom_-1_5": ("dom", -1.5), "handicap_ext_+1_5": ("ext", -1.5)}
    h, excl = n.verifier_v2_coherence_handicap(hand, {"handicap_dom_-1_5": 3.60, "handicap_ext_+1_5": 1.30}, 0)
    check(len(h) == 2 and not excl, "V2 : paire cohérente conservée")
    h, excl = n.verifier_v2_coherence_handicap(hand, {"handicap_dom_-1_5": 1.50, "handicap_ext_+1_5": 1.50}, 0)
    check(len(h) == 0 and len(excl) == 2 and all("V2" in e["raison"] for e in excl), "V2 : paire incohérente rejetée et tracée")

    # V3
    r, ex, av = n.verifier_v3_plausibilite({"victoire": 50.0}, {"victoire"}, 0)
    check(r == {"victoire"} and len(ex) == 1 and len(av) == 1, "V3 : victoire à 50.00 (> 30) → rejet + avertissement")
    r, ex, av = n.verifier_v3_plausibilite({"victoire": 2.0}, {"victoire"}, 0)
    check(not r and not ex and not av, "V3 : victoire à 2.00 → rien")

    # V4
    check(n.verifier_v4_fiabilite({}) == (None, None), "V4 : pas de meta → (None, None)")
    check(n.verifier_v4_fiabilite({"meta": {"fiabilite": " fallback "}}) == ("FALLBACK", "meta"), "V4 : valeur normalisée")
    base_eq = {"nom": "Z", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0}
    check(n.preparer_equipe({**base_eq, "matchs_joues": 12})[2:] == (12, []), "matchs_joues = 12 → n = 12")
    for bad in (0, -3, 2.5, "12", True):
        n_b, av_b = n.preparer_equipe({**base_eq, "matchs_joues": bad})[2:]
        check(n_b is None and len(av_b) == 1 and "matchs_joues invalide" in av_b[0], f"matchs_joues = {bad!r} → ignoré + avertissement")

    # V5
    for bad_v in (-0.1, 10.01):
        try:
            n.preparer_equipe({"nom": "Z", "buts_marques_moy": bad_v, "buts_encaisses_moy": 1.0})
            check(False, f"V5 : {bad_v} aurait dû lever")
        except ValueError as e:
            check("V5" in str(e), f"V5 : {bad_v} → rejet tracé")
    check(n.preparer_equipe({"nom": "Z", "buts_marques_moy": 10.0, "buts_encaisses_moy": 0})[:2] == (10.0, 0.0), "V5 : bornes inclusives")

    # V6
    ld6, le6, cl6 = n.calcul_lambdas_trace(1.5, 1.0, 1.0, 1.5)
    check(not cl6["dom"]["clamp_applique"] and abs(ld6 - 1.5) < 1e-12 and abs(le6 - 1.0) < 1e-12, "V6 : entrée normale → aucun clamp")
    ld6, le6, cl6 = n.calcul_lambdas_trace(0.0, 0.0, 0.0, 0.0)
    check(ld6 == n.LAMBDA_MIN and cl6["dom"]["clamp_applique"], "V6 : entrée nulle → clamp bas")

    # V7, V8, V10, V11
    pr7 = n.probas_standard(n.construire_matrice(1.6, 1.1))
    cotes_ok = {k: 1.0 / (pr7[k] * 1.05) for k in ("victoire", "nul", "defaite")}
    e7, av7 = n.verifier_v7_coherence_1x2(pr7, cotes_ok, {"1X2"})
    check(e7 is not None and e7 < n.SEUIL_COHERENCE_1X2 and av7 == [], "V7 : cotes alignées → pas d'avertissement")
    e7, av7 = n.verifier_v7_coherence_1x2(pr7, {"victoire": 5.0, "nul": 3.4, "defaite": 1.6}, {"1X2"})
    check(len(av7) == 1 and av7[0].startswith("V7"), "V7 : marché opposé au modèle → avertissement")
    t0 = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    check(n.verifier_v8_fraicheur({}, t0, 0) == [], "V8 : champ absent → silencieux")
    a8 = n.verifier_v8_fraicheur({"cotes_prises_le": "2026-09-19T06:00:00+00:00"}, t0, 0)
    check(len(a8) == 1 and "30.0 h" in a8[0], "V8 : cotes de 30 h → avertissement")
    check(n.verifier_v10_normalisation(1.6, 1.1) == [], "V10 : λ usuels → rien")
    check(len(n.verifier_v10_normalisation(10.0, 10.0)) == 1, "V10 : λ = 10/10 → avertissement")
    check(n.verifier_v11_statut_match({"statut": " Reporté "}, "2026-09-20", 0)[0] is False, "V11 : reporté → inactif")
    check(n.verifier_v11_statut_match({"date_match": "2026-09-21"}, "2026-09-20", 0)[0] is False, "V11 : autre date → inactif")
    check(n.verifier_v11_statut_match({}, "2026-09-20", 0) == (True, None), "V11 : aucun champ → actif")

    # Intégration noyau
    m = {"id": 0, "nom_dom": "A", "nom_ext": "B",
         "equipe_dom": {"nom": "A", "buts_marques_moy": 1.8, "buts_encaisses_moy": 1.0},
         "equipe_ext": {"nom": "B", "buts_marques_moy": 1.2, "buts_encaisses_moy": 1.4},
         "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "btts_oui": 1.85, "btts_non": 1.95,
                   "handicap_dom_-1_5": 3.6, "handicap_ext_+1_5": 1.3, "handicap_dom_-1_0": 2.9,
                   "handicap_ext_+1_0": 1.4, "handicap_nul_1_0": 4.0, "cote_bidon": "x"},
         "meta": {"fiabilite": "OK"}}
    r = n.analyser_match(m)
    par = {l["marche"]: l for l in r["inventaire"]}
    check(abs(par["handicap_dom_-1_5"]["proba_modele"] + par["handicap_ext_+1_5"]["proba_modele"] - 1.0) < 1e-12, "handicap -1.5 + +1.5 = 1")
    check("handicap_nul_1_0" in r["non_reconnues"], "handicap_nul_X → non_reconnues")
    check(r["statut_global"] in ("ECRASANT_JOUABLE", "COMPROMIS", "AUCUN"), "match complet analysé (pas de SKIP)")
    check("Fenêtre d'analyse inconnue" in r["avertissements_match"] and r["artefacts_match"] == [], "R4 : avertissement, pas artefact")
    m3 = {"id": 2, "nom_dom": "E", "nom_ext": "F",
          "equipe_dom": {"nom": "E", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0},
          "equipe_ext": {"nom": "F", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0},
          "cotes": {"victoire": 1.5, "nul": 2.5, "defaite": 2.5}}
    r3 = n.analyser_match(m3)
    check(r3["statut_global"] == "SKIP" and "V1/V2/V3 ont laissé" in (r3["raison_skip"] or ""), "groupe unique rejeté → SKIP tracé")
    check(n.analyser_match({**m, "id": 33, "statut": "reporte"}, "2026-09-20", t0)["statut_global"] == "SKIP", "V11 : intégration → SKIP")

    # Option 2 : l'égalité sur la ligne entière perd
    lp = n.evaluer_ligne("h", 0.5, 2.0, 0.5, 0.2, remboursement_push=False)
    check(abs(lp["ev"]) < 1e-12 and abs(lp["p_juste"] - 0.5) < 1e-12 and lp["push"] == 0.2, "Option 2 : EV = p·cote − 1")
    check(n.HANDICAP_ENTIER_REMBOURSE is False, "Défaut : l'égalité sur la ligne perd")

    # Moteur complet v2.6.10
    rc = analyser_complet(m)
    check(rc["moteur"] == NOM_MOTEUR == "moteur_v2_6_10" and rc["version_moteur"] == VERSION_MOTEUR == "2.6.10", "identité du moteur")
    check(rc["calibration"]["statut"] == "NON_CALIBRE", "sans calibrateur : NON_CALIBRE (jamais prétendu calibré)")
    check(set(n.resultat_vide(m)) <= set(rc), "le résultat est un sur-ensemble du schéma historique")
    rn = analyser_complet({**m, "cotes": {"victoire": 2.0}})
    check(rn["statut_global"] == "SKIP", "NO DATA : données insuffisantes → SKIP, aucune sélection")
    check(analyser_complet(m)["verdict"] == rc["verdict"], "reproductibilité : deux exécutions identiques")

    print("\nRésultat :", "TOUS LES TESTS PASSENT" if ok else "AU MOINS UN TEST ÉCHOUE")
    return 0 if ok else 1
