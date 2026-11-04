# Étape 3 — exploitation des historiques, compétition par compétition

Généré par `pouvoir_predictif_v3.py` (aucun mélange de compétitions). Gain = perte log (fréquence historique − méthode) par match, saisons test 2324–2526, 38 compétitions, 1 824 tests, seuil corrigé z > 4,03. Statistiques d'archive, **pas** une performance de moteur.

## Gain moyen par méthode (moyenne des 38 compétitions)

| Marché | P1 | CAL | LOGI | TREE | GBM | SEL | enrichie > P1 |
|---|---|---|---|---|---|---|---|
| 1X2 | 0.0528 | 0.0520 | 0.0467 | 0.0489 | 0.0412 | 0.0502 | 24/38 |
| dom | 0.0441 | 0.0435 | 0.0411 | 0.0423 | 0.0385 | 0.0435 | 27/38 |
| nul | 0.0033 | 0.0027 | 0.0000 | 0.0013 | -0.0019 | 0.0017 | 19/38 |
| ext | 0.0382 | 0.0382 | 0.0354 | 0.0363 | 0.0318 | 0.0369 | 29/38 |
| o15 | 0.0039 | 0.0026 | -0.0010 | 0.0006 | -0.0041 | 0.0000 | 18/38 |
| o25 | 0.0056 | 0.0044 | 0.0005 | 0.0015 | -0.0037 | 0.0014 | 13/38 |
| o35 | 0.0053 | 0.0038 | -0.0007 | 0.0016 | -0.0036 | 0.0013 | 14/38 |
| btts | 0.0011 | -0.0001 | -0.0028 | -0.0022 | -0.0055 | -0.0021 | 18/38 |

## Lecture
- Les méthodes enrichies (calibration, logistique, arbres, arbres boostés) ne battent pas le Poisson de base P1 en moyenne : chaque compétition a trop peu de matchs (≈ 1 500 à 2 800) pour apprendre des interactions sans les sur-ajuster.
- La calibration simple de P1 (CAL) est la seule enrichie proche de P1 ; elle est la meilleure sur 1X2/ext dans plusieurs compétitions et gagne en nombre de compétitions à z > 1,96 pour o15, o25, o35.
- Variables déterminantes (arbres) : écart Elo pour dom ; total de buts attendu pour o25 ; buts attendus de l'extérieur pour BTTS ; le nul est surtout porté par P1 lui-même (peu de signal propre).
- Conditions découvertes (2 plus favorables + 2 plus défavorables par marché et compétition) : 766/1064 gardent le même signe sur toutes les saisons. Elles sont choisies sur tout l'historique : optimistes, seul le rejeu mesure leur apport réel (ci-dessus).

Détail par compétition, conditions, effectifs, fréquences par saison : `pouvoir_predictif_v3.json`.
