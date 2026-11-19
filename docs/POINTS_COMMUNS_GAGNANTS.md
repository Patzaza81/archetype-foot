# Mega Power — points communs des pronostics gagnants, filtre cote ≥ 1,26 appliqué (19/11/2026)

Statut : expériences seulement. Moteur non modifié, rien de fusionné. La cote ne sert qu'à garder les pronostics éligibles (cote Betpawa ≥ 1,26) : elle n'entre dans aucune variable ni aucun apprentissage. Script : `experiences_megapower/e17_gagnants.py` ; sortie complète : `sorties/e17_gagnants.txt`.

## Méthode
- Archive du 28/09 au 17/11/2026 : 2 379 matchs joués et analysables (≥ 4 matchs au même lieu). Pour chaque marché, on ne garde que les matchs dont la cote est ≥ 1,26 (éligibles).
- Découpage dans le temps : A (50 %), B (25 %), C (25 %, jamais utilisé).
- Points communs : pour chacune des 57 variables de buts (connues avant le match), on mesure si elle sépare les gagnants des perdants (AUC : 0,5 = aucune séparation). Elle n'est retenue que si elle va dans le même sens sur A, B et C.
- Amélioration de la sélection : un classement par régression L1 (variables + modèle actuel) appris sur A et B, jugé sur C contre le classement du modèle actuel, à volume égal.

## Ce que les gagnants ont en commun
**Victoire domicile (1)** — 2 194 éligibles, cote médiane 2,21, 42,8 % de réussite en test.
- L'équipe qui reçoit a un meilleur bilan de buts que l'adversaire (différence de buts par match : +0,17 chez les gagnants, −0,27 chez les perdants), un meilleur écart de points par match (+0,11 contre −0,20) et un meilleur croisement « A à l'extérieur × B à domicile » (+0,05 contre −0,15).
- Même sens sur A, B et C ; AUC 0,61–0,66.
**Victoire extérieur (2)** — 2 281 éligibles, cote médiane 3,18, 29,6 % en test.
- L'inverse : l'équipe qui reçoit a un bilan de buts inférieur (−0,44 chez les gagnants, +0,17 chez les perdants) ; AUC 0,68 dans le sens contraire.
**1N** — 1 509 éligibles : l'équipe qui reçoit n'est pas nettement plus faible (écart de buts −0,30 chez les gagnants, −0,62 chez les perdants) ; AUC 0,60–0,62.
**N2** — 1 992 éligibles : l'équipe qui reçoit n'est pas nettement plus forte (écart de buts −0,09 contre +0,27) ; AUC 0,60–0,65.
**12** — 1 519 éligibles : aucun point commun net (AUC ≤ 0,55).
**+1,5 buts** — 819 éligibles : aucun point commun stable.
**−3,5 buts** : points communs faibles (AUC ≤ 0,55).
**±2,5 buts** (2 231 éligibles) : le niveau de buts attendu, somme des croisements (2,10 contre 1,97) et niveau de buts du championnat ; AUC 0,55–0,57.
**BTTS** : buts marqués par A à l'extérieur, croisement « B à domicile × A à l'extérieur », niveau du championnat ; AUC 0,53–0,55.
**Équipe domicile −1,5 / équipe extérieure −1,5** : l'équipe visée est plus faible (écart de buts −0,11 contre +0,19) ou l'attaque adverse croisée avec la défense est plus faible (0,99 contre 1,12) ; AUC 0,58–0,61.
**1N & +1,5 buts** : écart de buts positif (+0,11 contre −0,27) ; AUC 0,57–0,63. **N2 & +1,5 buts** : écart de buts négatif (−0,25 contre +0,18) et B marque plus à l'extérieur (1,04 contre 0,89) ; AUC 0,55–0,62.
**1N & −4,5 buts** : écart de buts positif ; AUC 0,57–0,62.

## Ce qui est déjà dans Mega Power
Le point commun le plus fort des victoires est l'écart de différence de buts et de points par match entre les deux équipes. Mega Power l'utilise déjà (terme « écart de classement », coefficient appris). Le classement appris sur A et B ne trouve aucune variable en plus pour 1, 2, 1N, N2, 12 : les AUC sont identiques (1 : 0,627 → 0,627 ; 2 : 0,677 → 0,677 ; 1N : 0,607 ; N2 : 0,605).

## La sélection s'améliore-t-elle ? (C, à volume égal)
- Pas de gain démontré : tous les intervalles de confiance à 95 % de l'écart de réussite contiennent 0 (±10 à ±25 points, car 50 à 570 pronostics par marché sur C).
- Meilleurs signaux (non prouvés) : 1N & −3,5 buts AUC 0,610 → 0,637, top 20 % 54,9 % → 60,8 % ; 1N & −4,5 buts 0,621 → 0,638 ; ±2,5 buts 0,565 → 0,572.
- Détériorations : N2 & −3,5 buts 0,610 → 0,590 ; 12 & −4,5 buts 0,478 → 0,444 ; −3,5 buts 0,559 → 0,528.

## Constat important : l'effet du filtre 1,26
- Parmi les pronostics éligibles, le modèle sépare bien les victoires et doubles chances (AUC 0,60–0,68) mais mal les marchés de buts (AUC 0,41–0,57 ; +1,5 buts : 0,41 sur 205 matchs ; BTTS 0,51).
- Sur la victoire domicile, le top 20 % du modèle réussit 57,8 % contre 42,8 % pour l'ensemble des éligibles (+15 points). Pour la victoire extérieure : 50,0 % contre 29,6 % (+20 points). Pour N2 : 61,6 % contre 51,8 %. Pour 1N : 68,0 % contre 60,6 %.
- Lecture : sous le filtre 1,26, c'est sur la victoire et les doubles chances que Mega Power apporte une vraie information. Sur les marchés de buts, le modèle actuel ne départage presque pas les matchs éligibles.

## Limites
- 55 jours d'archive ; 50 à 570 matchs par marché sur C. Les intervalles sont larges.
- Variables de buts seulement (57). Le modèle d'équipes « tous résultats » (étude précédente) n'a pas pu être appliqué à l'archive : les noms d'équipes diffèrent de ceux du bloc.
- Cote maximale par marché : non optimisée.
- Marchés à moins de 200 éligibles (par exemple équipe extérieure −2,5 buts à 210, −4,5 buts à 332) : résultats non fiables.
