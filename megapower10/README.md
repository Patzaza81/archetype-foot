# MEGAPOWER 10+ — moteur indépendant

Brique indépendante d'ARCHETYPE Foot. Elle ne modifie aucun moteur existant et ne lit aucun flux de production.

## Moteur construit

- Adaptateur Football-Data : résultats historiques + cotes individuelles d'ouverture/clôture disponibles dans les CSV.
- Marchés couverts par cette première source : 1X2 et total 2,5.
- Bookmakers séparés ; colonnes Max et Avg exclues pour ne pas transformer un agrégat non simultané en cote exécutable.
- Modèle Poisson propre à chaque championnat, en marche avant : chaque match est prédit uniquement à partir des matchs strictement antérieurs de la même compétition.
- Probabilités bookmaker corrigées de la marge (de-vig) par événement, bookmaker, marché et phase.
- Mesure de l'écart modèle/marché, bandes de cotes, taux de réussite, ROI à mise constante, intervalle de Wilson et mouvement ouverture → clôture.
- Seuil d'écart choisi sur la validation seulement, puis évalué sur une période test chronologique non utilisée pour le choix.
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
