# Étape 4 — rejeu chronologique des règles de conditions (par compétition, sans mélange)

Code : `regles_conditions.py` (+ `regles_conditions_grille.py`, exploratoire). Saisons test 2324–2526, 38 compétitions, 7 marchés. Règles découvertes sur le passé (arbres sur le résidu issue − P1), figées avant chaque saison, mesurées sur la saison suivante. Statistiques d'archive, **pas** une performance de moteur.

## Reproductibilité des règles figées (10047 règles testées)

| Effectif passé de la règle | règles | part du résidu reproduite | signe reproduit |
|---|---|---|---|
| 0–60 | 2555 | 5% | 55% |
| 60–120 | 2902 | 5% | 55% |
| 120–250 | 2511 | 9% | 57% |
| 250–500 | 1339 | 11% | 57% |
| ≥ 500 | 740 | 34% | 72% |

## Marchés (même table, par type)

| Marché | règles | part reproduite | signe reproduit |
|---|---|---|---|
| dom | 1530 | 16% | 60% |
| nul | 1436 | 8% | 54% |
| ext | 1478 | 16% | 59% |
| o15 | 1357 | 10% | 59% |
| o25 | 1403 | 9% | 57% |
| o35 | 1410 | 4% | 51% |
| btts | 1433 | 10% | 56% |

## Gain de perte log vs P1 avec corrections par règles (moyenne des 38 compétitions)

Validation en marche avant (lambda et effectif minimal choisis sans la saison test) : **aucun gain** (−0,0004 à −0,0008 selon le marché, 0 compétition avec avantage).

Cartographie exploratoire (sur les saisons test, **non validée**) — petite correction lambda=0,1 à 0,2 appliquée aux règles à grand effectif :

| Marché | meilleure combinaison | gain moyen | compétitions gain > 0 | compétitions z > 1,96 |
|---|---|---|---|---|
| dom | λ=0.1, effectif ≥ 0 % | +0.00046 | 27/38 | 6 |
| nul | λ=0.1, effectif ≥ 20 % | +0.00007 | 22/38 | 3 |
| ext | λ=0.2, effectif ≥ 20 % | +0.00033 | 25/38 | 3 |
| o15 | λ=0.1, effectif ≥ 10 % | +0.00017 | 20/38 | 2 |
| o25 | λ=0.2, effectif ≥ 20 % | +0.00028 | 24/38 | 2 |
| o35 | λ=0.1, effectif ≥ 20 % | +0.00003 | 18/38 | 4 |
| btts | λ=0.1, effectif ≥ 10 % | +0.00016 | 26/38 | 4 |

## Lecture
- Les règles de petite taille (< 250 matchs) ne se reproduisent presque pas : environ 5 à 11 % du résidu annoncé. Ce sont des artefacts de sélection.
- Les règles à grand effectif (≥ 500 matchs) se reproduisent nettement mieux (≈ 34 % du résidu, signe correct 72 %) : il existe une structure réelle au-delà de P1, mais faible.
- Ce signal est réel mais petit : appliqué fortement (lambda=1) il dégrade partout ; à lambda 0,1–0,2 il donne un gain minuscule, positif dans 18 à 27 compétitions selon le marché (meilleure combinaison par marché).
- La validation en marche avant ne sait pas encore choisir lambda et l'effectif minimal (trop peu de saisons de validation) : le gain de la cartographie reste une hypothèse à confirmer.
- Dérive des règles qui échouent : la variable qui change le plus est la taille de l'historique (début de saison) ; reproduction début de saison 56 %, fin de saison 57 % (signe).

Bibliothèque de règles par compétition et marché (étiquette `validee` / `hypothese`) : `bibliotheque_regles.json`. Détail des règles figées et de leur résultat : `regles_conditions_rejeu.json`. Résultats par compétition : `regles_conditions.json`.
