# Règle n°1 du moteur Gamma : compatibilité des comportements historiques (protocole, 31/10/2026)

Règle de Patrick : l'objectif n'est pas de trouver les marchés aux meilleurs pourcentages, mais ceux dont les deux équipes, dans leurs
conditions (domicile / extérieur), ont un comportement historique compatible avec le pari. Branche `moteur-dc-compatibilite`. Aucune fusion sans ordre.

## Constat sur l'existant
La compatibilité existe déjà en partie : le Module 3 calcule `preuve` = k/n sur les matchs comparables (A à domicile + B à l'extérieur, score
orienté) et le Module 4 n'en fait qu'un avertissement Wilson. La règle revient à PROMOUVOIR cette preuve de « avertissement » à « critère de sélection ».

## Définitions (toutes tirées des données, aucune constante posée à la main)
- Comp_Dom(M) = k_dom/n_dom : part des matchs de A à domicile (strictement avant le jour) où l'événement du marché M s'est produit, du point de vue du match.
- Comp_Ext(M) = k_ext/n_ext : idem pour B à l'extérieur.
- Bornes de Wilson inférieures de chaque côté (n petit = compatibilité peu fiable, pas de seuil de n posé : la borne inférieure le traduit).
- Comp_Croisée(M) = min(borne inf. Wilson dom, borne inf. Wilson ext). Le min est la forme proposée par Patrick ; la moyenne et le produit sont testés
  comme variantes, déclarées d'avance. Aucun calcul n'utilise les probabilités Dixon-Coles (pas de circularité).
- Seuil de compatibilité : appris sur 2025-26 (voir ci-dessous), jamais posé.

## Corrections au protocole reçu (à valider par Patrick)
1. « Supérieur d'au moins 2 points » = constante arbitraire. Remplacée par : écart apparié de taux de réussite, intervalle de confiance bootstrap
   par match à 95 %, règle « retenu si la borne basse > 0 » (même règle que la piste A).
2. Comparer deux sélections de volumes différents est biaisé : les paris à P élevée gagnent plus souvent par construction. Comparaison à VOLUME ÉGAL :
   on prend, par match et par marché de la liste, les N meilleurs par Comp_Croisée contre les N meilleurs par P (N = nombre de paris que la règle actuelle retient
   sur 2025-26, et variantes de N déclarées d'avance). Deuxième lecture : réussite observée par tranche de P, à compatibilité égale (la compatibilité ajoute-t-elle
   de l'information au-delà de P ?). Test direct : régression logistique issue ~ logit(P) + Comp_Croisée, lue sur 2026-27.
3. « La piste A a échoué, donc les paramètres servent en compatibilité » ne se déduit pas : la piste A n'a trouvé aucun signal robuste (pas la preuve
   d'un échec) et la compatibilité est calculée sur les mêmes buts passés que Dixon-Coles. L'hypothèse à tester est donc que k/n apporte quelque chose
   en plus de P. Résultat nul possible et annoncé comme tel.
4. Seuil appris = « celui qui maximise la réussite » sélectionne du bruit. Le seuil est le plus petit niveau à partir duquel la réussite lissée (monotone, PAV, comme
   les seuils par marché) atteint la cible de réussite de Patrick (70 %), avec le minimum de prédictions du calibrage existant.

## Données et périodes
Calibrage : 2025-26 (matchs du bloc après contrat 1.5). Test : 2026-27, séparation stricte. Il s'agit de matchs d'archive/rejeu, pas de matchs réellement
tournés et gelés par Gamma : le rapport le dit en tête (règle de Patrick du 29/10 : exception demandée explicitement dans son message). Le nombre de
matchs, de paris et la période sont annoncés. Les cotes ne sont pas dans le rejeu : la cote ≥ 1,26 n'est donc pas appliquée ici, et le rapport le précise.
Les paris réels gelés (bilan_reel.py) restent la seule mesure de rentabilité.

## Livrables
Tableau : réussite (k/N, Wilson), écart apparié avec IC, volume égal, par variante (min / moyenne / produit) ; régression logistique ; exemples de
paris retenus avec Comp_Dom, Comp_Ext, Comp_Croisée et les statistiques justificatives ; liste des paris rejetés à P élevée.

## Résultats et lecture (31/10/2026) — détail chiffré : `DC_COMPATIBILITE_RESULTATS.md`, placebos : `dc_compatibilite_placebo*.json`
Archive/rejeu, 9 488 matchs de calibrage (2025-26), 1 598 matchs de test (2026-27, du 03/03 au 16/10/2026). Pas un bilan réel. Cotes non appliquées.

**Conclusion : RÉSULTAT NUL. Aucun signal de compatibilité au-delà de P.**
1. À nombre de paris égal, la sélection par compatibilité réussit MOINS que la sélection par P, pour les trois variantes (écarts de −2,5 à −4,3 points ; IC à 95 %
   entièrement négatif pour min et moyenne). C'est l'attendu si la compatibilité n'apporte rien : P étant bien calibrée (coef. logistique ≈ 1,0), trier par P maximise la réussite.
2. Régression « issue ~ logit(P) + compatibilité » : le gain brut (+0,00004 à +0,00017 par observation) est ILLUSOIRE. Le placebo (compatibilité mélangée entre matchs) donne
   le même gain et 35 à 40 % de faux « retenu » : la compatibilité brute identifie le type de marché, pas les équipes. Amendement post-hoc DÉCLARÉ : compatibilité centrée par marché.
   Résultat centré : gains +0,00001 / +0,00000 / +0,00000, IC contenant 0, MDE 0,00006 à 0,00010 ; placebos centrés dans le bruit (0 à 2 faux « retenu » sur 40).
3. Limite de puissance : le test ne verrait pas un gain inférieur à environ 0,0001 par observation ; une compatibilité utile mais plus faible resterait invisible.
4. Seuil de compatibilité appris : dégénéré (0,50, la plus basse tranche). La réussite poolée atteint déjà 70 % dès 0,50 (marchés faciles dominants). Ce seuil ne
   sélectionne donc rien ; les comparaisons à volume égal restent valides, pas la notion de « seuil de compatibilité ».
5. La règle « compatibilité remplace P comme critère » n'est PAS validée. La traçabilité (afficher k/n domicile et extérieur) reste possible comme information, sans changer la sélection.
