# Piste A : criblage des paramètres du Module 1 sur les résidus de Dixon-Coles pur

Branche `moteur-dc-criblage` (depuis main). Ordre de Patrick du 31/10/2026. Fiche écrite et commitée AVANT tout calcul. Aucun changement du moteur ;
aucune fusion avant validation des résultats. Aucun test sur les 827 matchs d'archive (le taux de réussite n'y est pas détectable : ≈ 130 paris, erreur-type ≈ 4 points).

## Question
Parmi les paramètres du Module 1, lesquels portent un signal sur les buts que le Dixon-Coles pur (celui du moteur, effets neutres) ne contient pas déjà ?

## Données et découpage (strict)
- Apprentissage : Football-Data 2025-26. Test : Football-Data 2026-27, jamais utilisé ici pour régler quoi que ce soit.
- Dixon-Coles pur : `parametres.json` (σ, ξ, ρ appris au calibrage), effets neutres, marche avant hebdomadaire (`calibrage.marche_avant`).
  Chaque match est prédit avec les seuls matchs d'avant ; les paramètres du Module 1 sont ceux de `module1.tableau` au jour du match (matchs strictement antérieurs).
- Population : les matchs qui passent le contrat 1.5 (Filtre 0 compris), comme dans le moteur. Chaque match donne deux lignes (domicile, extérieur).

## Variables
- Un « paramètre » = une clé numérique du tableau du Module 1 (les clés par lieu `_dom` / `_ext` sont testées chacune). Pour une ligne (équipe X contre Y),
  deux colonnes : la valeur de X (propre) et la valeur de Y (adverse). Les clés textuelles sont encodées : score modal → 1 si 0-0 ou 1-1 (comme dans le moteur) ;
  série → longueur + type (V/N/D) ; profil → 5 indicatrices ; style → 3 indicatrices. Le champ texte `profil` (doublon de `profil_id`) n'est pas testé.
- Standardisation : moyenne et écart-type de l'apprentissage seulement, figés pour le test. Valeur manquante = moyenne d'apprentissage (0 après standardisation) ; leur nombre est publié.

## Modèle testé
- Résidu de Pearson de chaque ligne : r = (buts − λ) / √λ, λ du Dixon-Coles pur.
- Régression ridge de r sur les colonnes du paramètre (intercept non pénalisé). α choisi par validation croisée en BLOCS TEMPORELS : un bloc = un mois civil de 2025-26,
  chaque mois est laissé de côté à tour de rôle ; la grille de α s'étend par facteur 10 tant que l'optimum n'est pas intérieur (aucune borne posée à la main).
- Prédiction : λ̃ = λ · exp(ŝ / √λ), où ŝ est la sortie de la régression (égal au premier ordre à λ + √λ·ŝ, toujours positif, aucun plancher posé à la main).
  La grille de scores est celle du Dixon-Coles (mêmes ρ), seuls λ changent.
- Un test par paramètre (ses colonnes seules), plus un test de l'ensemble (toutes les colonnes, ridge commun).

## Mesure et décision
- Pour chaque match de 2026-27 : d = log-vraisemblance du score avec λ̃ − log-vraisemblance avec λ. Écart apparié, coefficients figés sur 2025-26.
- Intervalle à 95 % de la moyenne de d : bootstrap par rééchantillonnage des MATCHS (4 000 tirages, percentiles 2,5 % et 97,5 %).
- **Un paramètre est retenu seulement si la borne basse de son intervalle est > 0.** Sinon retiré.
- MDE recalculé pour CHAQUE paramètre : 1,96 · sd(d) / √n avec la sd de ses propres écarts (pas de valeur figée).
- Garde-fous publiés avec le tableau (ils ne changent pas la règle) :
  1. Comparaisons multiples : la règle ci-dessus appliquée à N paramètres laisse passer environ N × 2,5 % faux positifs. Le tableau donne aussi le p bootstrap et la décision après Holm.
  2. Placebo : le même pipeline est rejoué avec les lignes de variables permutées au hasard (apprentissage et test séparément) ; on publie combien de paramètres « passent » dans ces tirages, ce qui mesure le taux de faux positifs de la règle sur ces données.

## Suite prévue (déjà décidée par Patrick)
- Aucun paramètre ne passe : Dixon-Coles pur conservé ; on passe à B′ (Elo en moyenne du prior) avec garde-fous : Elo strictement antérieur au match, γ appris uniquement sur les compétitions couvertes (terme neutralisé sinon).
- 1 à 3 paramètres passent : ils sont gardés pour la piste B (prior hiérarchique avec les paramètres retenus).
- Plus de 3 : décision de Patrick.

## Limites annoncées d'avance
- Le test a un seul échantillon de 2026-27 (≈ 1 600 matchs), MDE de l'ordre de 0,001 pour un effet faible ; un effet plus petit ne sera pas vu, et « non retenu » ne veut pas dire « inutile ».
- La régression sur résidus teste un signal linéaire dans les paramètres ; un effet non linéaire n'est pas couvert.
- Les paramètres sont fortement liés entre eux (PPM, Pts, J…) : des paramètres redondants donneront des résultats proches, pas indépendants.
