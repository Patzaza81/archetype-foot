# -*- coding: utf-8 -*-
"""Moteur « shrink_v1 » : corrige la sur-confiance mesurée sur les 501 matchs (écart de calibration jusqu'à -29 points
dans les tranches à forte probabilité annoncée). Cause probable : les moyennes d'équipe reposent sur 2 à 12 matchs
seulement (matchs_joues), donc très bruitées. Ce moteur tire chaque moyenne vers une référence commune (mu), d'autant
plus fort que l'équipe a peu de matchs derrière elle :

    valeur_corrigee = (valeur_brute * n_matchs + mu * K) / (n_matchs + K)

n_matchs grand (12) -> la correction pèse peu. n_matchs petit (2) -> la correction pèse beaucoup. K est le seul
paramètre du modèle (« combien de matchs vaut la référence commune ») : il est réglé par validation croisée, jamais
sur les mêmes matchs qu'il évalue (voir cv_shrink.py). mu (attaque et défense moyennes) est calculé UNIQUEMENT à
partir des équipes du pli d'entraînement — aucune fuite d'information du pli de test, ni d'aucun résultat de match
(mu vient des moyennes déjà connues avant le coup d'envoi, pas des scores).

Tout le reste est inchangé : formule des lambdas (moyenne attaque/défense croisée), bornage LAMBDA_MIN/MAX,
Poisson indépendant pour la matrice des scores. Seule l'entrée (les moyennes d'équipe) est corrigée avant le calcul."""
NOM = "shrink_v1"
VERSION = "1"

# Valeurs par défaut = réglées sur les 501 matchs complets (mu) et choisies par validation croisée hors-pli (K=4,
# Brier hors-pli 0.19200 contre 0.20026 sans correction ; IC95 du delta par match : [-0.01218 ; -0.00432], voir
# evaluation/cv_shrink.py). À reconstruire de la même façon si le jeu de matchs change — ne pas ajuster à l'œil.
MU_ATTAQUE = 1.4036259731619012
MU_DEFENSE = 1.4204383440910389
K = 4.0


def _shrink(valeur, n, mu, k):
    if not n or n <= 0:
        return valeur          # pas de matchs_joues connu : aucune correction possible, valeur brute conservée
    return (valeur * n + mu * k) / (n + k)


def lambdas(att_d, def_d, att_e, def_e, entree):
    n_d = (entree.get("equipe_dom") or {}).get("matchs_joues")
    n_e = (entree.get("equipe_ext") or {}).get("matchs_joues")
    att_d2 = _shrink(att_d, n_d, MU_ATTAQUE, K)
    def_d2 = _shrink(def_d, n_d, MU_DEFENSE, K)
    att_e2 = _shrink(att_e, n_e, MU_ATTAQUE, K)
    def_e2 = _shrink(def_e, n_e, MU_DEFENSE, K)
    ld = (att_d2 + def_e2) / 2.0
    le = (att_e2 + def_d2) / 2.0
    return ld, le


def matrice(ld, le, entree):
    from math import exp, factorial, fsum
    n = 21
    p = lambda k, l: (l ** k) * exp(-l) / factorial(k) if l > 0 else (1.0 if k == 0 else 0.0)
    pd = [p(i, ld) for i in range(n)]
    pe = [p(j, le) for j in range(n)]
    m = [[pd[i] * pe[j] for j in range(n)] for i in range(n)]
    t = fsum(c for r in m for c in r)
    return [[c / t for c in r] for r in m]
