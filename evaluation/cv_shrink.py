#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validation croisée du moteur shrink_v1 (evaluation/modeles/shrink_v1.py) sur les 501 matchs avec résultat.

Pour chaque valeur de K (grille fixée AVANT ce calcul) : 5 répétitions x 5 plis. Dans chaque pli, mu_attaque et
mu_defense sont recalculés UNIQUEMENT à partir des équipes du pli d'entraînement (moyenne simple sur toutes les
apparitions domicile/extérieur des matchs d'entraînement) — jamais du pli évalué, jamais d'un résultat de match.
Chaque match des 501 n'est évalué qu'une seule fois par répétition, avec un mu appris sur les 4/5 restants.

Deux critères, calculés hors-pli (jamais sur les matchs ayant servi à apprendre mu) :
  1. Brier sur TOUS les marchés reconnus (calibration/qualité du modèle, peu sensible au bruit) -> sert à choisir K.
  2. ROI sur les value bets non-D (ce que le site publierait) -> donné à titre indicatif seulement, jamais pour choisir K :
     le nombre de value bets par pli est trop petit pour trancher dessus (leçon de la correction Benjamini-Hochberg).

K choisi = celui qui minimise le Brier hors-pli, moyenné sur les 5 répétitions. Comparé au moteur de référence
(Poisson brut, sans correction) évalué EXACTEMENT de la même façon (mêmes plis, même Brier) pour un delta honnête."""
import copy
import json
import random
import sys
import os

sys.path.insert(0, '.')
import moteur_v2_6_9 as moteur
import evaluation_moteur as ev
import branchement_moteur as bm
from archetype_model.learning.reglement import evaluer_marche
import evaluation.modeles.shrink_v1 as shrink

GRAINE = 20260922
N_REPETITIONS = 5
N_PLIS = 5
GRILLE_K = [0.0, 2.0, 4.0, 8.0, 12.0, 20.0, 35.0, 60.0]     # K=0 : aucune correction (référence Poisson brut)

src = json.load(open('evaluation/snapshot_historique_moteur_v2_6_9.json', encoding='utf-8'))
sc = json.load(open('evaluation/scores_historique_moteur_v2_6_9.json', encoding='utf-8'))['scores']
matchs = {m['id']: m for m in src['matchs'] if m['id'] in sc}
ids_tous = sorted(matchs)
assert len(ids_tous) == 501


def mu_du_pli(ids_train):
    """mu_attaque, mu_defense = moyenne simple des buts_marques_moy / buts_encaisses_moy de toutes les équipes
    (domicile ET extérieur) des matchs d'ENTRAÎNEMENT. Aucun résultat de match utilisé : uniquement les moyennes
    d'équipe déjà connues avant le coup d'envoi."""
    att, deff = [], []
    for i in ids_train:
        e = matchs[i]['entree_moteur']
        for cote in ('equipe_dom', 'equipe_ext'):
            att.append(e[cote]['buts_marques_moy'])
            deff.append(e[cote]['buts_encaisses_moy'])
    return sum(att) / len(att), sum(deff) / len(deff)


def evalue_match(mid, k_valeur, mu_att, mu_def):
    """Fait tourner le VRAI moteur (moteur_v2_6_9.analyser_match) avec les lambdas corrigés (shrink_v1), pour un
    match donné, un K et un mu fixés d'avance (venant du pli d'entraînement). Renvoie l'inventaire complet."""
    shrink.K, shrink.MU_ATTAQUE, shrink.MU_DEFENSE = k_valeur, mu_att, mu_def
    orig_trace = moteur.calcul_lambdas_trace

    def trace(att_d, def_d, att_e, def_e):
        ld_brut, le_brut = shrink.lambdas(att_d, def_d, att_e, def_e, entree_courante)
        ld = max(moteur.LAMBDA_MIN, min(moteur.LAMBDA_MAX, ld_brut))
        le = max(moteur.LAMBDA_MIN, min(moteur.LAMBDA_MAX, le_brut))
        return ld, le, {"dom": {"brut": ld_brut, "clampe": ld, "clamp_applique": ld != ld_brut},
                        "ext": {"brut": le_brut, "clampe": le, "clamp_applique": le != le_brut}}

    orig_matrice = moteur.construire_matrice
    moteur.construire_matrice = lambda ld, le: shrink.matrice(ld, le, entree_courante)
    moteur.calcul_lambdas_trace = trace
    m = matchs[mid]
    entree_courante = {k: v for k, v in m['entree_moteur'].items() if k != 'cotes'}
    import datetime
    dt = datetime.datetime.strptime(m['donnees_du_run']['heure_utc'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    try:
        res = moteur.analyser_match(copy.deepcopy(m['entree_moteur']), m['entree_moteur']['date_match'], dt)
    finally:
        moteur.construire_matrice, moteur.calcul_lambdas_trace = orig_matrice, orig_trace
    return res


def evalue_k(k_valeur, detail=False):
    rnd = random.Random(GRAINE)
    lignes_brier = []            # (p, gagne) sur TOUS les marchés reconnus, hors-pli
    lignes_value = {}            # {(repetition, mid): [(cote, gagne)]} value bets non-D, hors-pli
    brier_par_match = {}         # mid -> [(p, gagne), ...] regroupé sur les 5 répétitions (pour le test apparié)
    for rep in range(N_REPETITIONS):
        ids = ids_tous[:]
        rnd.shuffle(ids)
        taille = len(ids) // N_PLIS
        plis = [ids[p * taille:(p + 1) * taille] for p in range(N_PLIS - 1)] + [ids[(N_PLIS - 1) * taille:]]
        for pli_test in plis:
            ids_train = [i for i in ids if i not in pli_test]
            mu_att, mu_def = mu_du_pli(ids_train)
            for mid in pli_test:
                res = evalue_match(mid, k_valeur, mu_att, mu_def)
                if res['statut_global'] == 'SKIP':
                    continue
                dom, ext = sc[mid]['buts_dom'], sc[mid]['buts_ext']
                vv = []
                for l in res['inventaire']:
                    canon = bm.nom_canonique(l['marche'])
                    if canon is None:
                        continue
                    ev_r = evaluer_marche(canon, dom, ext)
                    if ev_r.statut not in ('WIN', 'LOSS'):
                        continue
                    gagne = 1 if ev_r.statut == 'WIN' else 0
                    lignes_brier.append((l['proba_modele'], gagne))
                    brier_par_match.setdefault(mid, []).append((l['proba_modele'], gagne))
                    if l['is_value'] and l['categorie'] != 'D':
                        vv.append((l['cote'], gagne))
                if vv:
                    lignes_value[(rep, mid)] = vv
    n_b = len(lignes_brier)
    brier = sum((p - g) ** 2 for p, g in lignes_brier) / n_b
    toutes_value = [x for v in lignes_value.values() for x in v]
    n_v = len(toutes_value)
    roi = sum((c - 1) if g else -1 for c, g in toutes_value) / n_v if n_v else None
    out = {"K": k_valeur, "n_brier": n_b, "brier": brier, "n_value": n_v, "roi_value": roi}
    if detail:
        out["brier_par_match"] = brier_par_match
    return out


def test_apparie_brier(par_match_a, par_match_b, n_boot=5000):
    """Delta de Brier (b - a) par rééchantillonnage des MATCHS (chaque match pèse une fois, même s'il contribue
    plusieurs lignes sur ses 5 répétitions). IC95 par percentile."""
    ids = sorted(set(par_match_a) & set(par_match_b))
    rnd = random.Random(GRAINE + 1)

    def moy(par_match, tirage):
        pts = [x for i in tirage for x in par_match[i]]
        return sum((p - g) ** 2 for p, g in pts) / len(pts)

    delta_obs = moy(par_match_b, ids) - moy(par_match_a, ids)
    deltas = []
    for _ in range(n_boot):
        tirage = [rnd.choice(ids) for _ in ids]
        deltas.append(moy(par_match_b, tirage) - moy(par_match_a, tirage))
    deltas.sort()
    lo, hi = deltas[int(0.025 * n_boot)], deltas[int(0.975 * n_boot) - 1]
    return {"n_matchs": len(ids), "delta": delta_obs, "ic95": (lo, hi)}


if __name__ == "__main__":
    resultats = []
    for k_valeur in GRILLE_K:
        r = evalue_k(k_valeur)
        resultats.append(r)
        roi_txt = f"{r['roi_value']*100:+.2f}%" if r['roi_value'] is not None else "—"
        print(f"K={k_valeur:6.1f}  Brier (n={r['n_brier']:5d}) = {r['brier']:.5f}   ROI value bets (n={r['n_value']:4d}) = {roi_txt}")
    json.dump(resultats, open('/tmp/cv_shrink_resultats.json', 'w'), ensure_ascii=False, indent=1)
    meilleur = min(resultats, key=lambda r: r['brier'])
    reference = next(r for r in resultats if r['K'] == 0.0)
    print(f"\nMeilleur K (Brier hors-pli minimal) : K={meilleur['K']}  Brier={meilleur['brier']:.5f}")
    print(f"Référence K=0 (aucune correction)   : Brier={reference['brier']:.5f}")
    print(f"Gain de Brier : {meilleur['brier'] - reference['brier']:+.5f} (négatif = mieux)")
