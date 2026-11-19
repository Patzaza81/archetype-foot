# Mega Power — étude statistique refaite (19/11/2026)

Statut : expériences seulement. Moteur non modifié, rien de fusionné. Aucune cote dans aucun calcul. Scripts : `experiences_megapower/e13_dc.py`, `e14_empilement.py`, `e15_pronostics.py`, `e16_seuils.py` ; sorties : `experiences_megapower/sorties/`.

## 1. Ce qui change par rapport aux études précédentes
- Variables 100 % connues seulement : résultats réels (buts, dates, équipes). Rien n'est comblé, rien n'est supposé : pas de repos, pas de face-à-face, pas de tirs ni corners.
- Plus de données : les 16 558 matchs du bloc (2 saisons) servent à construire les forces d'équipes, pas seulement les matchs de la saison en cours avec ≥ 4 matchs au même lieu.
- Un modèle d'équipes qui utilise TOUS les résultats connus de chaque équipe, domicile et extérieur ensemble, y compris la saison précédente, avec une attaque et une défense par équipe, un niveau de buts et un avantage du terrain par championnat (Poisson / Dixon-Coles régularisé).
- Validation honnête : le modèle est réajusté toutes les 2 semaines, uniquement avec des matchs antérieurs. Réglages (décroissance, régularisation) choisis sur V (01/09/2025 → 31/01/2026, 4 328 matchs). Jugement sur T (01/02/2026 → 16/10/2026, 5 478 matchs), jamais utilisé. Règle des 4 matchs au même lieu conservée.

## 2. Résultats
**Le modèle d'équipes seul** vaut le modèle actuel (perte sur les scores : 2,9438 contre 2,9427 sur T). **Les deux ensemble** sont meilleurs : moyenne des deux prévisions de buts 2,9355, soit −0,0072 par match.

**Par marché (67 marchés distincts, T)** : en combinant les deux modèles, la log-loss s'améliore sur 60 marchés sur 67 ; le gain dépasse 2 erreurs-types sur 39 ; une perte de plus de 2 erreurs-types sur 2 seulement. Gain moyen : +9,4 (en 1e-4 de log-loss par match). Principaux gains (± erreur-type) :
- −1,5 buts : +34,9±7,9 ; −3,5 buts : +26,5±8,5 ; −2,5 buts : +21,5±7,1 ; −4,5 buts : +16,5±8,6.
- Équipe extérieure −2,5 buts : +24,0±7,0 ; équipe extérieure −1,5 : +16,7±6,9 ; équipe domicile −1,5 : +19,1±5,8 ; équipe domicile −2,5 : +11,7±3,0.
- 1N & les deux marquent : +16,8±4,5 ; 1N & +1,5 buts : +15,2±3,1 ; N2 & BTTS non : +16,2±3,9 ; 1N & +3,5 buts : +19,1±4,7 ; N2 & −1,5 buts : +18,9±4,8.
- Victoire domicile : +3,4±1,0. 12 : 0,0±0,2. 1N : −2,8±0,6 (légèrement pire).
- Tous les blocs de T vont dans le même sens pour la plupart de ces marchés.
- La fréquence récente du championnat (trouvée avant) n'apporte plus rien en plus : le modèle d'équipes contient déjà le niveau de buts de chaque championnat (M2 ≈ M1 : +9,5 contre +9,4).

**Sur les pronostics retenus**, le gain est bien plus faible que sur les probabilités :
- À volume égal (10 % et 25 % des matchs les mieux classés), l'écart de réussite va de −0,7 à +2,9 points, intervalles de confiance à 95 % qui contiennent 0 pour tous les marchés (meilleurs : −3,5 buts +2,9 pts [−1,7 ; +7,9], −4,5 buts +2,4, N2 & −1,5 buts +2,2).
- Par seuil de fiabilité (sur 13 marchés) : même nombre de pronostics, même réussite (83,0 % → 83,1 % à 70 %, 89,1 % → 89,1 % à 80 %). Seul −3,5 buts progresse : à 0,80, réussite 78,9 % sur 303 pronostics → 80,4 % sur 372, borne basse de Wilson 73,9 % → 76,0 % ; à 0,75 : 74,8 % → 76,4 % (1 541 → 1 383 pronostics).
- Les deux méthodes annoncent environ 1 point de plus que la réussite réelle aux seuils élevés (biais de sélection).

## 3. Lecture
- Il y a une information supplémentaire réelle et mesurable : les forces d'équipes construites sur l'ensemble des résultats (deux lieux, saison précédente) corrigent le niveau de buts de chaque championnat et la force des équipes que le modèle actuel mesure mal.
- Cette information améliore les probabilités des marchés de buts et des combinés. Elle n'améliore pas encore, de façon prouvée, le choix des pronostics à publier : le classement des matchs change peu.
- Je ne conclus donc pas qu'il n'y a rien à améliorer : j'ai trouvé une amélioration réelle des probabilités. Je n'ai pas encore montré qu'elle augmente le taux de réussite des pronostics retenus.

## 4. Limites
- Un seul découpage V / T (huit mois de test). Les intervalles sur les pronostics retenus sont larges.
- Pas de confirmation sur l'archive Betpawa : les noms d'équipes de l'archive ne correspondent pas tous à ceux du bloc, et le filtre cote ≥ 1,26 n'a donc pas été appliqué à ce test.
- Cote maximale par marché : non optimisée.
- Deux paramètres du modèle d'équipes (demi-vie ≈ 270 jours, régularisation 0,003) ont été choisis sur V parmi 20 combinaisons ; le plateau est large (écarts de 0,0003 entre réglages voisins).
- Pas de variables supplémentaires dans le modèle d'équipes (effets propres à chaque lieu, enjeu, repos, xG) : à tester ensuite, avec des données complètes uniquement.
