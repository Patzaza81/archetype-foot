# Étape 5 — régularités durables, croisements, contextes, cartographie

Code : `regles_durables.py`. 38 compétitions, chacune apprise seule ; 7 marchés ; 33 variables (dont croisements attaque×défense, buts attendus×solidité, force×forme, régularité×sans encaisser, journée de saison). Statistiques d'archive, **pas** une performance de moteur. **Aucune correction déployée.**

Définitions : ensemble R_s = règles découvertes sur les matchs antérieurs à la saison s. Une règle est *durable* si une règle de même signe et de recouvrement ≥ 50 % (Jaccard sur les matchs) existe dans R_{s−1}. Une règle de la bibliothèque est `validee_chronologiquement` si ses ancêtres (appris avant 2324, 2425, 2526) mesurés sur ces saisons suivantes sont tous dans le sens annoncé (≥ 2 saisons) avec z cumulé > 1,96 ; sinon `exploratoire`.

## Phase 1 — durabilité (10888 règles rejouées sur 2324–2526)

| Catégorie | règles | part du résidu reproduite | signe reproduit |
|---|---|---|---|
| durables (J ≥ 0,5) | 1565 | 17% | 58% |
| non durables | 9323 | 6% | 55% |
| durables (J ≥ 0,7) | 812 | 14% | 56% |

| Effectif de la règle (part de l'apprentissage) | durables : règles / reproduit / signe | non durables : règles / reproduit / signe |
|---|---|---|
| <10% | 409 | 1% | 53% | 4324 | 4% | 54% |
| 10-20% | 358 | 8% | 56% | 2553 | 4% | 54% |
| 20-30% | 203 | 20% | 56% | 1032 | 7% | 56% |
| >=30% | 595 | 24% | 65% | 1414 | 12% | 61% |

| Marché (règles durables) | règles | reproduit | signe |
|---|---|---|---|
| dom | 258 | 22% | 66% |
| nul | 206 | 8% | 53% |
| ext | 267 | 35% | 66% |
| o15 | 200 | 7% | 50% |
| o25 | 200 | 19% | 60% |
| o35 | 177 | 2% | 58% |
| btts | 257 | 10% | 52% |

## Bibliothèque (4174 règles à grand effectif retenues, apprises sur 2122–2526)

- Règles évaluables chronologiquement (≥ 2 saisons ultérieures mesurées sur ses ancêtres) : **376** ; validées : **120** (≈ 10 attendues par hasard, à 2,5 % par règle).
- Couples compétition × marché ayant au moins une règle validée : **33 sur 266**.
- Paires de règles contradictoires (signe opposé, ≥ 30 matchs en commun) : 616 ; complémentaires (même signe, recouvrement < 20 %) : 11744.
- Attention : plusieurs règles validées d'une même compétition sont des variantes proches (mêmes matchs) ; le nombre de découvertes indépendantes est plus petit que 120.

### Règles validées chronologiquement (meilleure par couple compétition × marché)

| Compétition | Marché | Sens | Conditions | N | Couverture | Taux de réussite | P1 moyen | z ultérieur | Saisons |
|---|---|---|---|---|---|---|---|---|---|
| ARG | dom | favorable (1 validées) | forme_bc_dom > 0.900 ; repos_diff <= -0.257 | 179 | 6% | 61.5% | 41.8% | 2.58 | 2 |
| ARG | ext | defavorable (5 validées) | forme_pts_ext <= 2.500 ; historique_min <= 188.500 | 2606 | 95% | 24.7% | 29.1% | 2.69 | 3 |
| B1 | nul | defavorable (3 validées) | mu_ext <= 0.973 ; repos_diff <= 0.112 ; x_mu_total_solidite > 6.305 | 168 | 11% | 6.6% | 20.2% | 2.13 | 2 |
| B1 | o25 | defavorable (2 validées) | mu_ext > 0.957 ; x_att_ext_def_dom <= 3.268 ; 5.393 < x_mu_total_solidite <= 11.925 | 1197 | 77% | 50.7% | 54.9% | 2.38 | 3 |
| BRA | dom | favorable (7 validées) | mu_dom > 1.313 ; mu_total > 2.307 ; dom_sans_marquer_dom > 0.176 | 554 | 29% | 59.4% | 49.8% | 3.02 | 2 |
| BRA | o35 | defavorable (3 validées) | mu_ext <= 1.380 ; x_att_dom_def_ext <= 2.349 ; -1.292 < logit_P1 <= -0.970 | 556 | 29% | 16.9% | 23.9% | 2.07 | 2 |
| D1 | nul | favorable (2 validées) | 0.097 < ext_sans_encaisser_ext <= 0.152 ; regularite_dom <= 1.351 | 309 | 20% | 36.6% | 22.5% | 2.78 | 2 |
| D1 | ext | favorable (5 validées) | forme_bp_ext > 1.900 ; h2h_buts > 2.995 ; x_sans_encaisser_les_deux <= 0.054 | 185 | 12% | 57.8% | 36.5% | 2.94 | 3 |
| E0 | o15 | favorable (2 validées) | dom_sans_encaisser_dom > 0.322 ; journee_min > 7.500 ; logit_P1 <= 0.960 | 116 | 6% | 89.7% | 68.2% | 2.46 | 3 |
| E1 | dom | favorable (1 validées) | elo_diff > 0.460 | 384 | 14% | 65.4% | 53.6% | 2.8 | 3 |
| E1 | btts | favorable (2 validées) | mu_total <= 2.439 ; x_marquent_les_deux <= 0.504 | 602 | 22% | 55.8% | 46.9% | 2.79 | 3 |
| EC | btts | defavorable (5 validées) | elo_diff <= -0.484 ; mu_total > 3.204 | 66 | 2% | 34.8% | 64.3% | 2.88 | 2 |
| F1 | btts | defavorable (2 validées) | journee_min <= 27.500 ; x_mu_total_solidite > 7.850 ; x_sans_encaisser_les_deux <= 0.056 | 355 | 21% | 43.4% | 56.8% | 2.35 | 2 |
| FIN | o25 | favorable (2 validées) | mu_ext <= 1.287 ; h2h_vict_dom <= 0.690 | 389 | 46% | 60.9% | 48.4% | 2.06 | 2 |
| G1 | dom | favorable (6 validées) | elo_diff > 0.626 ; mu_dom > 1.907 ; mu_total > 2.444 | 125 | 11% | 82.4% | 70.5% | 2.27 | 3 |
| G1 | o35 | favorable (1 validées) | regularite_dom > 1.557 | 66 | 6% | 47.0% | 26.3% | 3.12 | 2 |
| I1 | ext | defavorable (11 validées) | mu_dom > 1.027 ; ext_sans_marquer_ext > 0.134 ; journee_min <= 35.500 ; logit_P1 <= -0.281 | 1229 | 65% | 19.4% | 26.4% | 3.35 | 3 |
| I2 | o25 | favorable (3 validées) | forme_bc_dom <= 1.550 ; dom_sans_marquer_dom > 0.293 ; ext_sans_marquer_ext <= 0.427 | 260 | 14% | 55.8% | 42.8% | 2.74 | 3 |
| MEX | dom | favorable (5 validées) | elo_diff > -0.381 ; mu_dom > 1.611 ; x_marquent_les_deux <= 0.636 | 453 | 27% | 64.7% | 55.3% | 2.87 | 2 |
| MEX | ext | defavorable (3 validées) | elo_diff > -0.540 ; journee_min <= 29.500 ; x_mu_total_solidite > 5.247 | 968 | 57% | 20.9% | 28.5% | 2.06 | 3 |
| NOR | btts | defavorable (2 validées) | mu_ext > 1.155 ; h2h_vict_dom <= 0.542 ; regularite_dom <= 1.185 ; journee_min <= 5.500 | 106 | 9% | 38.7% | 59.5% | 2.08 | 2 |
| P1 | nul | favorable (2 validées) | dom_bc_domicile > 1.039 ; ext_bc_exterieur > 1.462 ; x_att_ext_def_dom <= 1.487 | 396 | 26% | 41.4% | 26.5% | 2.31 | 2 |
| ROU | nul | favorable (1 validées) | forme_bp_ext > 1.367 ; dom_bc_domicile > 0.767 ; journee_min <= 23.500 | 359 | 22% | 39.0% | 26.8% | 2.82 | 2 |
| SP1 | dom | favorable (5 validées) | elo_diff > 0.105 ; dom_bp_domicile > 1.685 | 372 | 20% | 76.1% | 62.8% | 3.59 | 2 |
| SP1 | ext | defavorable (6 validées) | forme_pts_ext > 0.450 ; ext_bp_exterieur <= 1.267 ; ext_sans_marquer_ext <= 0.444 ; journee_min <= 26.500 | 685 | 36% | 20.3% | 27.5% | 2.69 | 3 |
| SP1 | o15 | favorable (3 validées) | dom_bp_domicile > 1.189 ; ext_bp_exterieur > 0.760 ; x_att_dom_def_ext <= 2.237 | 660 | 35% | 77.1% | 70.2% | 2.8 | 2 |
| SP1 | o25 | favorable (2 validées) | dom_bc_domicile <= 1.265 ; x_sans_encaisser_les_deux <= 0.040 | 146 | 8% | 65.8% | 47.6% | 2.37 | 2 |
| SP1 | btts | favorable (4 validées) | ext_bp_exterieur <= 0.760 | 137 | 7% | 63.5% | 41.9% | 2.84 | 2 |
| SWE | o25 | favorable (3 validées) | forme_bp_ext > 1.100 ; h2h_buts <= 2.558 ; regularite_dom > 0.662 ; x_att_ext_def_dom > 1.003 | 195 | 16% | 60.0% | 46.0% | 2.58 | 3 |
| T1 | nul | defavorable (3 validées) | regularite_ext > 1.107 ; journee_min > 8.500 ; x_att_dom_def_ext <= 1.910 | 125 | 7% | 5.6% | 24.3% | 2.36 | 2 |
| T1 | ext | favorable (10 validées) | elo_diff <= -1.090 ; ext_sans_marquer_ext > 0.140 | 164 | 9% | 74.4% | 47.3% | 4.42 | 3 |
| USA | o15 | favorable (2 validées) | 1.433 < ext_bc_exterieur <= 1.962 ; ext_sans_marquer_ext > 0.275 ; journee_min > 9.500 | 665 | 26% | 87.8% | 78.0% | 1.96 | 3 |
| USA | btts | favorable (6 validées) | mu_dom > 1.460 ; ext_bc_exterieur <= 1.900 ; journee_min > 8.500 ; x_att_dom_def_ext > 2.362 | 1057 | 42% | 65.9% | 56.6% | 3.65 | 2 |

## Phase 3 — contextes de saison (tiers de journée appris sur le passé)

- Effets de stade testés : 2394 ; significatifs sur le passé : 259 ; signe retrouvé sur la saison suivante : 64% (contre 55% pour les non significatifs).
- Par tiers de saison (effets significatifs) : debut 55% (76), milieu 64% (80), fin 71% (103).
- Lecture : le comportement de fin de saison se reproduit mieux que celui du début, où les historiques sont courts.

## Lecture générale
- La durabilité fait la différence : les règles durables à grand effectif (≥ 20–30 % des matchs) reproduisent 20 à 24 % de leur résidu, contre 5–12 % pour les autres ; 1 règle sur 3 évaluable passe la validation chronologique.
- Marchés les plus structurés : extérieur (35 % reproduit) et domicile (22 %), puis plus de 2,5 buts (19 %). Le nul, plus de 1,5 et 3,5 buts, BTTS restent peu reproductibles.
- Ces règles sont des écarts à P1, pas des probabilités autonomes : elles désignent où P1 se trompe de façon reproductible. Non déployées.

Cartographie complète (12 règles par compétition et marché : conditions, effectif, couverture, taux de réussite, taux par saison, évaluations ultérieures, statut) : `cartographie_conditions.json`. Règles rejouées et contextes : `regles_durables_rejeu.json`.
