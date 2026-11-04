# Étape 6 — découvertes indépendantes et valeur prédictive

Code : `regles_familles.py`. Chaque championnat est appris seul. Statistiques d'archive, **pas** une performance de moteur. **Aucune correction déployée.**

## 1. Regroupement des règles validées
Famille = règles de même signe dont les matchs se recouvrent (Jaccard ≥ 0,5) ou dont la plus petite est incluse à ≥ 80 % dans l'autre. Représentant = règle au z ultérieur maximal. Les autres membres sont `raffinement` (sous-ensemble dont le résidu diffère significativement du reste du représentant : information supplémentaire conservée) ou `redondante`.

| Marché | règles validées | familles indépendantes | raffinements conservés |
|---|---|---|---|
| dom | 25 | 9 | 2 |
| nul | 11 | 5 | 1 |
| ext | 40 | 8 | 11 |
| o15 | 7 | 3 | 2 |
| o25 | 12 | 5 | 5 |
| o35 | 4 | 2 | 1 |
| btts | 21 | 8 | 2 |
| **Total** | **120** | **40** | **24** |

- **120 règles validées = 40 découvertes indépendantes** (réparties sur 33 couples compétition × marché), dont 24 raffinements ; 56 règles sont redondantes.
- Couverture de l'union des familles d'un couple : moyenne 34%, médiane 26% des matchs.
- Relations entre familles d'un même couple : 1 paire complémentaire, 0 contradictoire, 0 chevauchante : les familles d'un couple sont presque toujours distinctes ou fusionnées.
- Reproductibilité : chaque famille est dans le sens annoncé sur toutes ses saisons d'évaluation (2 à 3) avec z cumulé > 1,96 (par construction de la validation).

### Les 40 familles indépendantes

| Compétition | Marché | Sens | Conditions du représentant | N | Couverture | Taux de réussite | P1 moyen | Résidu hors apprentissage | z | Saisons évaluées |
|---|---|---|---|---|---|---|---|---|---|---|
| ARG | dom | favorable | forme_bc_dom > 0.900 ; repos_diff <= -0.257 | 179 | 6% | 61.5% | 41.8% | +0.141 | 2.58 | 2 |
| ARG | ext | defavorable | forme_pts_ext <= 2.500 ; historique_min <= 188.500 | 2606 | 95% | 24.7% | 29.1% | -0.031 | 2.69 | 3 |
| B1 | nul | defavorable | mu_ext <= 0.973 ; repos_diff <= -0.011 | 96 | 6% | 5.2% | 20.6% | -0.091 | 2.13 | 2 |
| B1 | o25 | defavorable | mu_ext > 0.957 ; x_att_ext_def_dom <= 3.268 ; x_mu_total_solidite <= 11.925 (+1 raff.) | 1244 | 80% | 51.0% | 54.5% | -0.049 | 2.38 | 3 |
| BRA | dom | favorable | mu_dom > 1.313 ; mu_total > 2.307 ; dom_sans_marquer_dom > 0.176 | 554 | 29% | 59.4% | 49.8% | +0.071 | 3.02 | 2 |
| BRA | o35 | defavorable | x_att_dom_def_ext <= 2.349 ; -1.292 < logit_P1 <= -0.970 (+1 raff.) | 595 | 31% | 18.7% | 23.9% | -0.052 | 2.07 | 2 |
| D1 | nul | favorable | ext_sans_encaisser_ext <= 0.152 ; regularite_dom <= 1.351 (+1 raff.) | 444 | 29% | 33.3% | 22.7% | +0.107 | 2.78 | 2 |
| D1 | ext | favorable | forme_bp_ext > 1.900 ; x_sans_encaisser_les_deux <= 0.054 (+3 raff.) | 255 | 17% | 51.8% | 36.5% | +0.114 | 2.94 | 3 |
| E0 | o15 | favorable | dom_sans_encaisser_dom > 0.322 ; logit_P1 <= 0.960 | 156 | 8% | 85.3% | 67.9% | +0.134 | 2.46 | 3 |
| E1 | dom | favorable | elo_diff > 0.460 | 384 | 14% | 65.4% | 53.6% | +0.082 | 2.8 | 3 |
| E1 | btts | favorable | mu_total <= 2.439 ; x_marquent_les_deux <= 0.504 | 602 | 22% | 55.8% | 46.9% | +0.079 | 2.79 | 3 |
| EC | btts | defavorable | elo_diff <= -0.484 ; mu_total > 3.204 | 66 | 2% | 34.8% | 64.3% | -0.291 | 2.88 | 2 |
| EC | btts | favorable | mu_total <= 3.204 ; forme_pts_ext > 1.390 ; x_sans_encaisser_les_deux > 0.082 | 392 | 14% | 62.8% | 50.0% | +0.114 | 2.67 | 2 |
| EC | btts | defavorable | elo_diff > -0.116 ; mu_total > 3.204 ; h2h_buts > 2.781 | 189 | 7% | 47.1% | 63.3% | -0.132 | 2.51 | 2 |
| F1 | btts | defavorable | journee_min <= 27.500 ; x_mu_total_solidite > 7.850 (+1 raff.) | 561 | 33% | 48.7% | 56.9% | -0.075 | 2.35 | 2 |
| FIN | o25 | favorable | mu_ext <= 1.287 ; h2h_vict_dom <= 0.690 | 389 | 46% | 60.9% | 48.4% | +0.077 | 2.06 | 2 |
| G1 | dom | favorable | elo_diff > 0.626 ; mu_dom > 1.907 ; mu_total > 2.444 | 125 | 11% | 82.4% | 70.5% | +0.088 | 2.27 | 3 |
| G1 | dom | defavorable | elo_diff <= 0.626 ; x_att_ext_def_dom > 1.590 | 235 | 20% | 11.5% | 24.8% | -0.064 | 2.15 | 3 |
| G1 | o35 | favorable | regularite_dom > 1.557 | 66 | 6% | 47.0% | 26.3% | +0.269 | 3.12 | 2 |
| I1 | ext | defavorable | ext_sans_marquer_ext > 0.134 ; logit_P1 <= -0.281 (+3 raff.) | 1340 | 71% | 21.4% | 26.7% | -0.051 | 3.35 | 3 |
| I1 | ext | favorable | x_mu_total_solidite <= 10.126 ; logit_P1 > -0.281 | 457 | 24% | 62.1% | 52.4% | +0.077 | 2.4 | 2 |
| I2 | o25 | favorable | dom_sans_marquer_dom > 0.293 ; ext_sans_marquer_ext <= 0.427 (+2 raff.) | 407 | 21% | 51.1% | 43.5% | +0.096 | 2.74 | 3 |
| MEX | dom | favorable | elo_diff > -0.381 ; mu_dom > 1.611 ; x_marquent_les_deux <= 0.636 | 453 | 27% | 64.7% | 55.3% | +0.067 | 2.87 | 2 |
| MEX | dom | defavorable | elo_diff <= -0.381 ; regularite_dom <= 1.275 (+1 raff.) | 362 | 21% | 21.0% | 31.9% | -0.072 | 2.52 | 3 |
| MEX | ext | defavorable | elo_diff > -0.540 ; journee_min <= 29.500 (+2 raff.) | 1179 | 69% | 22.8% | 28.6% | -0.033 | 2.06 | 3 |
| NOR | btts | defavorable | mu_ext > 1.155 ; h2h_vict_dom <= 0.542 ; journee_min <= 5.500 (+1 raff.) | 157 | 13% | 48.4% | 59.9% | -0.112 | 2.08 | 2 |
| P1 | nul | favorable | dom_bc_domicile > 1.039 ; ext_bc_exterieur > 1.462 ; x_att_ext_def_dom <= 1.487 | 396 | 26% | 41.4% | 26.5% | +0.074 | 2.31 | 2 |
| ROU | nul | favorable | forme_bp_ext > 1.367 ; dom_bc_domicile > 0.767 ; journee_min <= 23.500 | 359 | 22% | 39.0% | 26.8% | +0.066 | 2.82 | 2 |
| SP1 | dom | favorable | elo_diff > 0.105 ; dom_bp_domicile > 1.685 | 372 | 20% | 76.1% | 62.8% | +0.126 | 3.59 | 2 |
| SP1 | dom | defavorable | elo_diff <= 0.105 ; mu_dom > 1.460 (+1 raff.) | 113 | 6% | 28.3% | 46.5% | -0.152 | 2.35 | 2 |
| SP1 | ext | defavorable | forme_pts_ext > 0.450 ; ext_bp_exterieur <= 1.267 ; ext_sans_marquer_ext <= 0.444 ; journee_min <= 26.500 | 685 | 36% | 20.3% | 27.5% | -0.048 | 2.69 | 3 |
| SP1 | o15 | favorable | dom_bp_domicile > 1.189 ; ext_bp_exterieur > 0.760 (+1 raff.) | 1220 | 64% | 76.0% | 72.7% | +0.061 | 2.8 | 2 |
| SP1 | o25 | favorable | dom_bc_domicile <= 1.265 ; x_sans_encaisser_les_deux <= 0.040 | 146 | 8% | 65.8% | 47.6% | +0.156 | 2.37 | 2 |
| SP1 | btts | favorable | ext_bp_exterieur <= 0.760 | 137 | 7% | 63.5% | 41.9% | +0.172 | 2.84 | 2 |
| SWE | o25 | favorable | forme_bp_ext > 1.100 ; h2h_buts <= 2.558 ; regularite_dom > 0.662 (+2 raff.) | 255 | 21% | 53.7% | 44.8% | +0.100 | 2.58 | 3 |
| T1 | nul | defavorable | regularite_ext > 1.107 ; journee_min > 8.500 ; x_att_dom_def_ext <= 1.910 | 125 | 7% | 5.6% | 24.3% | -0.117 | 2.36 | 2 |
| T1 | ext | favorable | elo_diff <= -1.090 ; ext_sans_marquer_ext > 0.140 | 164 | 9% | 74.4% | 47.3% | +0.183 | 4.42 | 3 |
| T1 | ext | defavorable | elo_diff > -1.090 ; dom_sans_encaisser_dom > 0.199 ; regularite_ext <= 1.710 ; x_mu_total_solidite > 6.335 | 1185 | 68% | 20.1% | 27.1% | -0.066 | 3.99 | 3 |
| USA | o15 | favorable | 1.433 < ext_bc_exterieur <= 1.962 ; journee_min > 9.500 (+1 raff.) | 1188 | 47% | 84.8% | 78.2% | +0.028 | 1.96 | 3 |
| USA | btts | favorable | mu_dom > 1.460 ; ext_bc_exterieur <= 1.900 ; journee_min > 8.500 ; x_att_dom_def_ext > 2.362 | 1057 | 42% | 65.9% | 56.6% | +0.062 | 3.65 | 2 |

## 2. Valeur prédictive : rejeu des familles figées sur les saisons ultérieures
Familles figées avant la saison t (règles apprises avant t, ancêtres évalués sur les saisons précédentes), correction = résidu moyen **mesuré hors apprentissage** (aucun paramètre ajusté), appliquée à P1 sur la saison t.

| Rejeu | couples avec familles | gain moyen de perte log vs P1 | couples à gain > 0 | écart de calibration avant → après | réussite avant → après |
|---|---|---|---|---|---|
| 2526, validation stricte (≥ 2 saisons) | 27 | -0.0038 | 9 | 0.0243 → 0.0208 | 62.6% → 62.4% |
| 2526, validation légère (≥ 1 saison) | 58 | -0.0094 | 10 | 0.0225 → 0.0349 | 64.6% → 63.8% |
| 2425, validation légère | 41 | -0.0104 | 15 | 0.0309 → 0.0350 | 64.5% → 64.6% |

- Les familles validées par leurs ancêtres **ne gagnent pas** en général la saison suivante : la sélection sur les saisons d'évaluation garde une part de bruit. Les seuls couples à gain positif sur les deux saisons rejouées : E1 dom (+0.0002 en 2526, +0.0027 en 2425), T1 ext (+0.0131 en 2526, +0.0277 en 2425).
- Combinaisons : sur 20 paires de familles d'un même couple, 4 font mieux que leur meilleure famille seule (synergie) ; la moyenne des familles couvrant le match fait aussi bien que la meilleure famille seule dans 59 % (stricte), 45 % (légère 2526) et 56 % (légère 2425) des couples. Pas de gain de combinaison établi.
- T1 extérieur est la seule découverte qui tient : 2 familles (écart Elo ≤ −1,09 ; écart Elo > −1,09 avec domicile qui encaisse peu) couvrent 95–98 % des matchs ; gain +0,0277 (2425) et +0,0131 (2526) de perte log par match ; écart de calibration 0,0297 → 0,0117 et 0,0237 → 0,0107.
- USA BTTS ne tient pas : une seule famille (6 règles), qui devient quasi générale (93 % des matchs en 2526) ; la correction (+0,062) dépasse l'écart restant (P1 0,580, fréquence 0,596) : 2526 donne −0,0057 de perte log, écart de calibration 0,016 → 0,049.

Détail par compétition et marché : `familles_regles.json`.
