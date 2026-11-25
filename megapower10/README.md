# MEGAPOWER 10+ — moteur indépendant

Brique indépendante d'ARCHETYPE Foot. Elle ne modifie aucun moteur existant et ne lit aucun flux de production.

## Contrat impératif des sélections

- **Aucune recommandation, sélection de stratégie ou ligne de portefeuille sous 10.00.** La borne est inclusive : 10.00 est admissible, 9.99 est rejetée.
- Le contrôle est centralisé dans `core.py` et réappliqué dans l'évaluation des edges et l'étude chronologique ; les deux CLI refusent `--min-odds` inférieur à 10.00.
- Les cotes inférieures à 10.00 peuvent subsister uniquement comme données de référence nécessaires au calcul des probabilités de marché (de-vig) ; elles ne sont jamais des sélections ni des résultats de portefeuille.

## Moteur construit

- Adaptateur Football-Data : résultats historiques + cotes individuelles d'ouverture/clôture disponibles dans les CSV.
- Marchés couverts par cette première source : 1X2 et total 2,5.
- Bookmakers séparés ; colonnes Max et Avg exclues pour ne pas transformer un agrégat non simultané en cote exécutable.
- Modèle Poisson propre à chaque championnat, en marche avant : chaque match est prédit uniquement à partir des matchs strictement antérieurs de la même compétition.
- Probabilités bookmaker corrigées de la marge (de-vig) par événement, bookmaker, marché et phase.
- Mesure de l'écart modèle/marché, bandes de cotes, taux de réussite, ROI à mise constante, intervalle de Wilson et mouvement ouverture → clôture.
- Seuil d'écart choisi sur la validation seulement, puis évalué sur une période test chronologique non utilisée pour le choix. Segmentation supplémentaire par profondeur du marché (nombre de bookmakers observés).
- Aucun assemblage des meilleures cotes de plusieurs bookmakers.

## Lancer l'étude historique

À la racine du dépôt :

```bash
python -m megapower10.football_data_cli --root data/football_data --min-odds 10 --max-odds 1000 --min-support 30 --output data/megapower10/rapport.json
```

Le rapport contient deux lectures différentes :
1. le taux/ROI brut des cotes dans les bandes demandées ;
2. le résultat du signal prédictif Poisson contre la probabilité bookmaker corrigée de la marge, avec seuil gelé avant le test final.

Les bornes train/validation sont calculées par dates distinctes (60 % / 80 %) ou peuvent être fixées explicitement avec --train-end et --validation-end.

## Source et limites à respecter

Football-Data fournit des cotes d'ouverture/clôture, mais pas leur horodatage exact ni l'heure de capture. Ses conditions d'utilisation doivent être respectées : cette source ne doit pas être intégrée à une offre commerciale ou à un entraînement automatisé destiné à un produit commercial sans autorisation explicite du fournisseur. Ces observations servent à l'étude historique ; elles ne prouvent pas qu'un prix était encore disponible à une minute précise. Les prix d'ouverture et de clôture restent deux jeux séparés. Le mouvement ouverture → clôture n'est pas présenté comme un CLV horodaté.

La première version couvre 1X2 et total 2,5 uniquement. Les marchés exotiques (scores exacts, BTTS, corners, cartons, mi-temps, handicaps détaillés) nécessitent des archives dédiées et des règles de règlement propres à chaque marché.

## Contrat JSONL pour les futurs flux horodatés

Une ligne = un prix réellement observé chez un bookmaker :
- event_id, kickoff_utc (ISO-8601 avec fuseau), competition, market, selection ;
- bookmaker, captured_at_utc (ISO-8601 avec fuseau), odds (> 1), result (true/false/null), source ;
- phase distingue pré-match et in-play ; les relevés in-play ne sont pas mélangés au pré-match.

Les archives non horodatées doivent conserver leur phase opening ou closing et ne peuvent pas entrer dans la sélection d'un instant de décision.

## Règles de preuve

- ROI à mise constante de 1 unité ; commissions, limites et liquidité non fournies restent hors calcul.
- Wilson mesure l'incertitude du taux de réussite, pas celle du ROI.
- Les résultats sont ventilés par compétition, marché, bookmaker, phase et bande de cote.
- Aucun seuil ne sera promu sur sa performance test ; le test final n'intervient qu'après gel des choix.
- Une bonne performance rétrospective n'est pas une preuve de rentabilité future.


## Deuxième archive indépendante : Beat The Bookie

Le connecteur megapower10.beatthebookie lit closing_odds.csv.gz du [jeu public Beat The Bookie](https://www.kaggle.com/datasets/austro/beat-the-bookie-worldwide-football-dataset) : 479 440 matchs annoncés, 818 ligues, 2005–2015, cotes 1X2. Il sépare :
- les cotes moyennes, utilisées pour construire la probabilité de marché corrigée de la marge ;
- les meilleures cotes observées par issue, utilisées pour le ROI hypothétique, avec le bookmaker indiqué pour chaque issue.

Les meilleures cotes d'issues différentes ne sont jamais présentées comme un arbitrage simultané. Source sous CC BY-SA 4.0 : attribution et obligations de partage à l'identique à respecter.

Lancer localement :
```bash
python -m megapower10.beatthebookie_cli --input /chemin/closing_odds.csv.gz --min-odds 10 --max-odds 1000 --output beatthebookie-report.json
```

Le workflow GitHub MEGAPOWER 10+ — Beat The Bookie archive télécharge la source publique via KaggleHub et publie le rapport comme artefact.


## Résultats des replays indépendants — 25/11/2026

Les rapports JSON complets sont conservés dans les artefacts GitHub Actions :
- [Football-Data, 67 932 matchs](https://github.com/Patzaza81/archetype-foot/actions/runs/45532109149) — artefact `megapower10-historical-report`.
- [Beat The Bookie, 479 440 matchs / 818 ligues](https://github.com/Patzaza81/archetype-foot/actions/runs/45532439844) — artefact `megapower10-beatthebookie-report`.

| Replay | Prix bruts ≥10 | Réussite | ROI brut |
|---|---:|---:|---:|
| Football-Data ouverture | 7 444 | 4,81 % | −38,36 % |
| Football-Data clôture | 9 962 | 4,94 % | −36,27 % |
| Beat The Bookie, moyenne (référence non exécutable) | 24 497 | 4,17 % | −48,48 % |
| Beat The Bookie, meilleur prix observé (hypothétique) | 42 843 | 5,79 % | −24,48 % |

Sur Beat The Bookie, la sélection par seuils validés a donné 849 paris de test, 65 gagnés (7,66 %), −17,25 unités et −2,03 % de ROI ; cote moyenne 13,06. Son intervalle de Wilson à 95 % pour le taux de réussite est 6,05–9,64 %. Sur Football-Data, le portefeuille de test filtré était positif (+3,35 %) mais ne comptait que 164 paris. Ce résultat n'est pas confirmé par l'archive Beat The Bookie.

Sur le test Beat The Bookie, la qualité probabiliste du modèle est inférieure au marché : Brier 0,2058 contre 0,1943 ; log-loss 0,6002 contre 0,5723. Le même constat apparaît sur Football-Data. **MEGAPOWER 10+ est donc techniquement construit et testé, mais pas validé comme moteur rentable. Le benchmark de 40 % de réussite n'est pas atteint.** Aucun seuil ne doit être promu en production sur ces seuls résultats.

Ces archives historiques ne fournissent pas d'horodatage exact des prix. Le meilleur prix par issue de Beat The Bookie n'est pas une garantie d'exécution ni un arbitrage simultané. Les résultats sont bruts, sans commissions, limites ou contraintes de liquidité. Respecter la licence CC BY-SA 4.0 de Beat The Bookie.
