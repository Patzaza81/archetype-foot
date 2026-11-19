# Mega Power — recherche exhaustive des croisements et audit final (19/11/2026)

Statut : expériences seulement. Moteur non modifié, rien de fusionné. Aucune cote dans aucun calcul prédictif. Scripts : `experiences_megapower/e11_*.py`, `e12_stats.py` ; sorties : `experiences_megapower/sorties/e11_*.txt`, `e12_stats.txt`.

## 1. Ce qui a été fait cette fois
- Table de 117 variables par match, calculées uniquement avec des résultats déjà connus avant le match (11 127 matchs du bloc de saisons) :
  - buts marqués/encaissés à domicile, à l'extérieur, tous lieux, et les inverses (A à l'extérieur, B à domicile) ;
  - total de buts des matchs à domicile, à l'extérieur, 3 et 5 derniers matchs ;
  - écarts, rapports, croisements attaque × défense dans les deux sens, sommes et différences de croisements ;
  - formes de résultats : victoires, nuls, défaites, plus de 1,5 / 2,5 / 3,5 buts, les deux équipes marquent, cages inviolées, victoires et défaites par 2 buts ou plus ;
  - face-à-face des deux équipes, repos, densité de matchs, avantage du terrain propre à chaque équipe, régularité, écart de classement, niveau du championnat.
- Recherche « dans tous les sens » : 99 variables seules + tous les produits de deux variables = 5 049 configurations testées par marché. Base de comparaison : le modèle actuel + la fréquence récente du marché dans le championnat.
- 66 événements distincts du catalogue (tous les marchés du catalogue sont couverts à l'équivalence près : cage inviolée = équipe marque, etc.).
- Preuve exigée : seuil de Bonferroni sur les 5 049 configurations (Z ≥ 4,42) sur A et B ensemble, puis jugement sur C (jamais utilisé).
- Complément : tirs, tirs cadrés, corners, mi-temps, cartons, sur les 5 676 matchs où ils existent.

## 2. Résultats
- Configurations qui franchissent le seuil : peu, presque toujours des variables seules, rarement des produits.
- Les mêmes reviennent partout : le croisement inverse (A à l'extérieur × B à domicile : `x3`, `d34`, `sd34`), les buts marqués par A à l'extérieur (`agf_A`), l'avantage du terrain de B (`B_homeadv`), l'écart de points par match, la défense de B à l'extérieur.
- Sur C, aucun gain n'atteint 2 erreurs-types après ajout à la base. Meilleurs : 1N & +2,5 buts +27±16, domicile −1,5 buts +24±15, ±2,5 buts +22±12, 1N & +1,5 buts +19±11, −3,5 buts +18±11. Les blocs de C sont instables (ex. 1N & +2,5 : +76 / −25 / +31).
- Victoire, nul, 2, doubles chances : rien de fiable (1 : +6±14 ; nul : −14±8 ; 2 : +12±12 ; 12 : −14±8).
- Tirs, corners, mi-temps, cartons (5 676 matchs) : rien de significatif. Meilleur : domicile marque +38±20, blocs +6/+34/+75, donc non validé.
- Face-à-face, repos, formes de résultats : aucune configuration retenue sur les marchés de résultat.
- Ce qui reste utile : la fréquence récente du marché dans le championnat (déjà trouvée). Elle apporte, sur C, +34 (−1,5 buts), +32 (−3,5), +25 (−4,5 et ±2,5), +20 (BTTS), +17 (12 & +3,5), +16 (12 & −1,5).

Conclusion : aucun croisement supplémentaire n'est démontré. Seul le niveau récent du championnat améliore les marchés de buts.

## 3. Audit final : demandé / fait / manquant
| Demandé | Statut |
|---|---|
| Buts marqués et encaissés à domicile, à l'extérieur | fait |
| Total de buts des matchs à domicile, à l'extérieur | fait |
| Marqués + encaissés tous lieux confondus | fait |
| Écarts entre productions, rapports et ratios entre adversaires | fait |
| Domicile de A × extérieur de B, et inversement | fait (croisement et inverse) |
| Périodes récentes | partiel : 3 et 5 derniers matchs seulement |
| Historique du championnat | fait (niveau de buts, fréquence récente par marché, 300 jours) |
| Effet sur chaque marché : 1, N, 2, doubles chances, buts, autres | fait sur 66 événements (tout le catalogue à l'équivalence près) |
| Découvrir des relations non prévues | fait (produits de 2 variables, face-à-face, repos, formes, tirs, corners) |
| Profils d'équipes et similarité sur les deux équipes ensemble | fait (voir le rapport précédent) |
| Fiabilité des similarités (nombre, dispersion, stabilité) | fait : aucune contribution propre |
| Validation chronologique, stabilité dans le temps | fait (A / B / C, 3 blocs dans C) |
| Stabilité entre championnats | non fait pour cette recherche |
| Cote minimale 1,26 | appliquée dans la confirmation sur l'archive du rapport précédent |

## 4. Omissions restantes (à connaître)
1. **Cote maximale par marché : non optimisée.** Trop peu de pronostics à cote ≥ 1,26 sur 5 semaines d'archive, et le bloc n'a pas de cotes Betpawa.
2. **xG non testé** : absent du bloc, présent sur ~14 % des observations de l'archive.
3. **Confirmation hors échantillon incomplète** : la table de 57 variables a été confirmée sur l'archive (rapport précédent). Les nouvelles variables (formes, face-à-face, repos, tirs) n'ont été jugées que sur C du bloc. Le face-à-face n'existe que dans le bloc.
4. **Seulement des produits de deux variables** et des arbres de profondeur 2 (rapport précédent). Pas de triplets, pas d'autres formes non linéaires.
5. **Périodes récentes** : seulement 3 et 5 derniers matchs et la fréquence du championnat sur 300 jours. Pas d'autre fenêtre ni de pondération décroissante dans cette recherche.
6. **Constantes posées, non optimisées** : 4 pseudo-matchs pour les lieux rares, lissage de la fréquence du championnat (50 pseudo-matchs, 2 pour le modèle), 300 jours, k de la similarité testés parmi 20, 50, 100, 300. Elles contredisent ta règle « tout paramètre appris sur les données » ; à corriger si une règle est retenue.
7. **Un seul découpage A / B / C**, pas de validation marche avant jour par jour pour ces recherches.
8. **Stabilité par championnat** : non mesurée (trop peu de matchs par championnat).
9. **Marchés exclus** : ceux dont le taux est sous 8 % ou au-dessus de 95 %, et tout ce qui n'est pas dans le catalogue (corners, cartons, mi-temps, score exact).
10. **Qualité de l'adversaire** : les croisements de cette recherche utilisent des moyennes brutes normalisées par le championnat. La base (modèle actuel) corrige l'adversaire, mais les croisements eux-mêmes ne sont pas corrigés.
