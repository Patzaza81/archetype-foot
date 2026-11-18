# Mega Power — audit des données et plan d'apprentissage rétrospectif (18/11/2026)

Statut : proposition. Moteur opérationnel non modifié, rien de fusionné (PR 171 comprise). Scripts : `experiences_megapower/a0_audit_donnees.py`, `a1_filtre126.py` ; sorties : `experiences_megapower/sorties/a0_*.txt`, `a1_*.txt`.

## 1. Constat n° 1 — le filtre « cote ≥ 1,26 » change tout
Mesure sur les pronostics de la v2 (marche avant 23/10 → 17/11, 1 591 matchs, 9 071 pronostics). La cote n'est lue qu'APRÈS le choix du pronostic, jamais dans un calcul.
- Cote connue pour 87,5 % des pronostics (7 939).
- Cote ≥ 1,26 : 2 501 pronostics seulement (27,6 %), sur 1 287 matchs.
- Réussite : 79,6 % (tous) → **69,3 % (cote ≥ 1,26)**. Sous 1,26 : 83,6 %.
- Marchés quasi éliminés : +0,5 buts (0 sur 79 pronostics), −4,5 buts (176 sur 971), équipe ext −2,5 (67 sur 804), équipe dom −2,5 (134 sur 815).
- Marchés qui restent en nombre : 12 (554 pronostics, 75,1 %), +1,5 buts (327, 71,6 %), −3,5 buts (237, 67,5 %), cage ext non (192, 69,8 %), cage dom non (191, 62,3 %), 1N (181, 66,3 %).
- Le « 79,6 % » de la v2 n'est donc pas la performance utile : à cote ≥ 1,26 elle est de 69,3 %. C'est la vraie référence à battre.

## 2. Constat n° 2 — ce que contiennent vraiment les données
Archive (`data/archive_test`, 55 jours, 28/09 → 21/11/2026) :
- 4 234 matchs, 3 558 joués, 2 379 joués et analysables (≥ 4 matchs au même lieu), 131 championnats analysables.
- Cotes Betpawa pour 3 511 des 3 558 matchs joués. Elles servent au filtre seulement.
- 25 719 observations d'équipe distinctes : 8 898 Football-Data, 16 821 Matchendirect.
- Variables riches (xG, tirs, tirs cadrés, corners, mi-temps, cartons) : présentes sur 13,6 % (xG) à 15,6 % (autres) des observations, uniquement celles de Football-Data. Matchendirect : buts seulement.
- Médiane de 14 matchs joués par championnat ; 24 championnats sur 126 ont au moins 30 matchs.

Bloc de saisons (`data/bloc_saisons`) :
- 16 558 matchs, 38 divisions, du 23/01/2025 au 16/10/2026.
- Buts, mi-temps et cartons sur 9 242 matchs ; tirs, tirs cadrés et corners sur 8 690. Pas de xG.
- Ses cotes ne sont pas Betpawa : elles ne peuvent pas servir au filtre 1,26 et ne seront pas lues.

Conséquence : pour 27 % des pronostics qui passent le filtre, l'archive offre ~2 500 cas en 26 jours, répartis sur 30 marchés. Chercher des interactions sur cela seul produirait du surapprentissage. L'apprentissage se fait donc sur le bloc (grand volume, sans cote), la validation finale sur l'archive avec le filtre 1,26.

## 3. Architecture d'apprentissage rétrospectif
Principe : les cotes ne servent qu'à filtrer les pronostics retenus ; l'apprentissage et le choix des règles se font sans cote.

1. **Population d'apprentissage par marché** : tous les matchs analysables (≥ 4 matchs au même lieu par équipe), issue réelle connue, sans cote. Cible = le marché réussit ou non.
2. **Variables candidates** (avant le match seulement, rien de présupposé) : buts marqués/encaissés et leurs moyennes même lieu et tous lieux, goal average, xG et xGA (là où ils existent), tirs, tirs cadrés, corners, buts de mi-temps, régularité (écart-type, part de matchs à 0 et à 3+ buts), forme récente, qualité de l'adversaire, écart de classement (gd, ppm), λ attendus du modèle actuel, probabilités du modèle actuel, championnat (effet de groupe contraint), nombre de matchs disponibles.
3. **Découverte** : comparer gagnants et perdants du marché, par marché. Outils : régression pénalisée (L1) pour éliminer les variables inutiles, arbres peu profonds pour proposer les interactions, puis seulement les interactions retenues sont testées à la main.
4. **Validation chronologique** : découpage A (découverte, premiers 50 %), B (confirmation, 25 %), C (test final jamais utilisé avant, 25 %). Pas de mélange aléatoire. Sur le bloc : A jusqu'au 31/01/2026, B jusqu'au 13/04/2026, C ensuite.
5. **Garde-fous contre le surapprentissage** : chaque configuration testée est comptée ; seuil de preuve relevé selon leur nombre ; une règle doit être positive sur A, B et C, pas seulement sur C.
6. **Validation finale** sur l'archive Betpawa, filtre 1,26 appliqué : le gain se mesure sur les pronostics qui survivent au filtre.
7. **Sélection** : une règle par marché, avec ses propres variables et seuils. Aucun seuil universel.

## 4. Mémoire statistique par marché
Un fichier indépendant par marché : `data/megapower/memoire/<marche>.json`, en ajout seulement (rien n'est effacé). Contenu :
- variables testées (avec leur effet mesuré et la période) ;
- configurations gagnantes et perdantes (conditions, n, réussites, intervalle de Wilson, période) ;
- règles validées (version, date de validation, empreinte des données) ;
- règles rejetées (raison : gain nul, instable dans le temps, trop peu de pronostics, négatif dans un championnat) ;
- compteur du nombre de configurations testées (pour la correction de comparaisons multiples).
Ces fichiers ne sont pas lus par le moteur tant que tu n'as pas validé. Ils n'existent pas encore.

## 5. Critères d'acceptation d'une règle (proposés, à valider)
- Gain mesuré par rapport à la v2 sur le même marché, sur la même période et avec le même filtre 1,26.
- Borne basse de l'intervalle de Wilson 95 % du gain strictement positive sur C.
- Au moins 100 pronostics sur C après filtre ; sinon la règle reste « à surveiller ».
- Positive sur A, B et C ; pas de semaine ou de tranche qui s'effondre.
- Pas négative de façon nette dans un championnat ayant ≥ 30 pronostics.
- Brier et log-loss pas dégradés.
- Elle ne contredit aucun test existant et reste explicable en une phrase.
- Sinon : règle rejetée et consignée dans la mémoire du marché.

## 6. Plan d'expérimentation
- **P0 (fait)** : audit des données et du filtre 1,26.
- **P1** : référence honnête. Mesurer, marché par marché, la v2 sous filtre 1,26 sur A/B/C. Fixer ce qu'il faut battre.
- **P2** : construire le jeu de variables sur le bloc (sans cote) et sur l'archive ; contrôle anti-fuite (aucune donnée du jour du match).
- **P3** : découverte par marché sur A, confirmation sur B ; marchés prioritaires : 12, +1,5 buts, −3,5 buts, 1N, N2, cage ext non, cage dom non, équipe dom marque, puis les autres.
- **P4** : test final sur C (bloc), puis sur l'archive avec filtre 1,26.
- **P5** : mémoire par marché + rapport par marché + proposition de règles. Rien n'entre dans le moteur avant ta validation.

## 7. Risques et points à trancher
- Gain probablement modeste : 8 semaines et 2 saisons, avec des variables riches sur 15 % des observations seulement. Je ne promets pas d'augmentation durable avant d'avoir testé.
- Les règles apprises sans cote ne savent pas quels pronostics passent 1,26 : le volume final dépendra du marché. Plusieurs marchés (+0,5 buts, −4,5 buts, équipes −2,5) seront presque vides sous ce filtre.
- Décision à prendre : la v2 reste la référence tant qu'une règle n'a pas passé les critères du §5.
- Décision à prendre : l'apprentissage utilise-t-il le bloc (sans cotes lues) en plus de l'archive ? Je le propose.
