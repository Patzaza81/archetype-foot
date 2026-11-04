# Pouvoir prédictif — étape 2b (méthodes combinées)

Généré par `pouvoir_predictif_v2.py`. Gain = perte log (fréquence historique − méthode) par match, saisons test 2324–2526, tout choisi sur des matchs antérieurs (validation = saison précédente). Statistiques d'archive, **pas** une performance de moteur.

## Comparaison sur les mêmes matchs (gain moyen par compétition)

| Marché | P1 | POOL | SOT* | P1 (21 comp. à tirs) | SOT |
|---|---|---|---|---|---|
| 1X2 | 0.0544 | 0.0558 | – | 0.0622 | 0.0598 |
| dom | 0.0457 | 0.0460 | – | 0.0514 | 0.0506 |
| nul | 0.0034 | 0.0038 | – | 0.0039 | 0.0021 |
| ext | 0.0391 | 0.0403 | – | 0.0458 | 0.0451 |
| o15 | 0.0044 | 0.0039 | – | 0.0041 | -0.0004 |
| o25 | 0.0058 | 0.0068 | – | 0.0059 | 0.0034 |
| o35 | 0.0057 | 0.0067 | – | 0.0059 | 0.0018 |
| btts | 0.0021 | 0.0019 | – | 0.0016 | -0.0016 |

*SOT = base + tirs cadres attendus, seulement les 21 compétitions où HST/AST existent.

## Lecture
- Entraîner un méta-modèle sur la compétition seule (LOC) fait **moins bien** que P1 : trop peu de matchs.
- Mettre en commun toutes les compétitions (POOL) donne un petit gain sur 1X2, buts et BTTS : c'est la piste la plus générale.
- Les tirs cadres améliorent nettement 1X2/dom/ext là où ils existent, mais pas les buts ni BTTS.
- Nul, BTTS, plus de 1,5/2,5/3,5 buts : gains presque nuls, aucune méthode robuste sur l'ensemble.
- Choix automatique par validation (SEL) : moins bon que POOL fixe (le choix sur une saison est bruité).

Détail par compétition et marché : `pouvoir_predictif_v2.json`.
