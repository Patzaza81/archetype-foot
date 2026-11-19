# Mega Power — croisements de buts et similarité de profils : résultats (19/11/2026)

Statut : expériences seulement. Moteur non modifié, rien de fusionné. Aucune cote dans aucun calcul prédictif (la cote ≥ 1,26 n'est lue qu'après la prédiction, pour les comparaisons de pronostics). Scripts : `experiences_megapower/e7_*.py`, `e8_similarite.py`, `e9_controle.py`, `e10_confirmation.py` ; sorties : `experiences_megapower/sorties/`.

## 1. Protocole
- Données : bloc de saisons, 11 127 matchs analysables (≥ 4 matchs au même lieu), buts seulement. Découpage chronologique : A = 5 563 (jusqu'au 31/01/2026), B = 2 782 (jusqu'au 13/04/2026, choix de la régularisation), C = 2 782 (jusqu'au 16/10/2026, test jamais utilisé).
- Base de comparaison M0 : la probabilité du modèle actuel, recalibrée (a + b·logit P).
- Confirmation hors échantillon : modèles appris sur tout le bloc, testés sur 1 932 matchs de l'archive du 17/10 au 17/11/2026 (jamais vus).
- Mesure : gain de log-loss par match sur C (en 1e-4 ; > 0 = gain), avec erreur-type appariée. Marchés égaux ou complémentaires (1N/2, 12/N, ±2,5, BTTS) répètent le même résultat : ils comptent pour une seule expérience.

## 2. Croisements de buts (57 variables)
Variables testées : buts marqués et encaissés à domicile de A, à l'extérieur de B, et leurs inverses (A à l'extérieur, B à domicile), tous lieux, totaux de buts par lieu, 5 derniers matchs, écarts, rapports et ratios entre adversaires, croisements attaque × défense dans les deux sens (domicile A × extérieur B et inversement), régularité (écarts-types, parts de matchs sans but marqué/encaissé, parts de matchs à 3 buts ou plus), points par match, écart de classement, niveau de buts du championnat. Méthode : régression L1 (élimine les variables inutiles) et arbres de profondeur 2 (interactions).

Résultats sur C (gain log-loss, ±erreur-type) :
- Marchés de résultat : aucun gain. 1 : −7±18 ; nul : −22±14 ; 2 : +3±10 ; 12 : −22±14. Les arbres sont pires (nul −40±14). Ton exemple (équipe qui marque beaucoup à domicile contre une équipe qui encaisse beaucoup à l'extérieur) est dans les variables testées (x1, d12, ld12) : il n'améliore pas la probabilité de victoire actuelle.
- Marchés de buts : gains sur +1,5 (+30±17), ±2,5 (+32±15), −3,5 (+23±7), BTTS (+17±12), −4,5 (+10±3), 1N&+1,5 (+39±16), 1N&−3,5 (+22±10). Les variables retenues sont d'abord le niveau de buts du championnat (`lig_tot`), les buts de A à l'extérieur, et le croisement inverse (A à l'extérieur × B à domicile, B à domicile × A à l'extérieur).
- Les arbres n'apportent pas mieux que la régression sur les marchés de buts.

## 3. Similarité de profils entre matchs
Profil de chaque match : 17 variables des deux équipes ensemble (attaque, défense, régularité, résultats, rapports de force, lieu). Voisins = matchs déjà joués les plus proches (k = 20, 50, 100 ou 300, choisi sur B). Deux réservoirs : même championnat (300 derniers jours) ou tous championnats.
- Tous championnats : aucun gain nulle part (|Δ| ≤ 6 et dans le bruit).
- Même championnat : gains sur +1,5 (+27±7), −3,5 (+27±10), BTTS (+24±9), −4,5 (+16±9), mais ils ne viennent PAS de la similarité. Les voisins proches ne font pas mieux que les voisins lointains (BTTS : +9 contre +44).
- Contrôle (E9) : une simple fréquence récente du marché dans le championnat donne le même gain (+1,5 : +27,6±7,6 ; −3,5 : +26,2±10 ; BTTS : +24,4±8,6 ; ±2,5 : +18,6±6 ; −4,5 : +19,6±7 ; domicile marque : +10,3±4). Ajouter la similarité par-dessus apporte 0 (+1,5 : −0,2±0,2 ; BTTS : 0,0±0,3 ; ±2,5 : −1,8±1,8).
- Conclusion : la similarité de profils n'a aucune contribution propre démontrée. Ce qu'elle capte, c'est le niveau de buts du championnat.

## 4. Ce qui est réel : le niveau récent du championnat, marché par marché
Le modèle actuel sous-estime ou sur-estime les marchés de buts selon le championnat. Recalibrer chaque marché de buts avec la fréquence récente de ce marché dans le championnat (300 jours) apporte un gain stable sur les trois blocs de C : +1,5 : +19/+48/+16 ; −3,5 : +14/+39/+26 ; BTTS : +12/+25/+36 ; ±2,5 : +10/+28/+18. Pour les marchés de résultat (1, N, 2, doubles chances) : aucun gain (≤ ±3).

## 5. Confirmation hors échantillon (archive 17/10 → 17/11, 1 932 matchs)
Gain de log-loss (a = fréquence du championnat ; d = croisements + fréquence) :
- +1,5 : +16±15 (a), +27±17 (d) ; BTTS : +14±14, +28±21 ; −4,5 : +21±16, +28±20 ; ±2,5 : +6±14, +18±21 ; +0,5 : +15±7, +16±10.
- −3,5 : −6±18, −1±21 : non confirmé.
- Résultat 1/N/2/12 : −6 à +10, dans le bruit.
- Aucun gain n'est significatif à 2 erreurs-types sur cet échantillon.
Pronostics à cote ≥ 1,26, 40 % les mieux classés, réussite M0 → M(a) / M(d) : +1,5 : 70,3 % → 72,6 % / 72,6 % (266 cas) ; −4,5 : 67,8 % → 72,2 % / 71,3 % (115) ; BTTS oui : 58,1 % → 57,5 % / 59,2 % (743) ; 1N : 67,0 % → 66,2 % / 67,4 % (488) ; 12 : 75,3 % → 75,1 % / 75,9 % (486). Les écarts sont de l'ordre de 1 à 4 points, au niveau du hasard.

## 6. Verdict (à valider)
- Croisements de buts pour les marchés de résultat : à ne pas intégrer. Gain nul, risque de surapprentissage.
- Similarité de profils : à ne pas intégrer. Aucune contribution propre.
- Fréquence récente du championnat, par marché de buts (+1,5, ±2,5, BTTS, −4,5, domicile marque) : candidate sérieuse. Gain réel sur C et dans le sens attendu sur l'archive, mais non significatif hors échantillon. Je ne l'intégrerais qu'après 3 à 4 semaines de journal gelé confirmant le gain.
- −3,5 buts : gain sur C non confirmé hors échantillon : rejeté pour l'instant.
- Croisements en plus de la fréquence du championnat : peut-être un apport supplémentaire sur les marchés de buts (d > a sur C), non démontré.

## 7. Limites et ce qui n'est pas fait
- Cote maximale par marché : non optimisée. L'archive n'a que quelques centaines de pronostics à cote ≥ 1,26 par marché sur 5 semaines, et le bloc n'a pas de cote Betpawa. Optimiser un plafond sur si peu serait du surapprentissage.
- Mémoire statistique par marché : non créée.
- Pas de xG dans le bloc ; l'archive ne l'a que sur ~14 % des observations. Les variables xG n'ont pas été testées ici.
- Une valeur fixe (K = 4 pseudo-matchs) rapproche de la moyenne les statistiques des lieux rares (A à l'extérieur, B à domicile). Non optimisée.
- Multiplicité : environ 17 marchés distincts × 3 variantes testés ; la preuve exigée serait ≥ 2,7 erreurs-types : seul +1,5 (3,6 par fréquence du championnat sur C) et BTTS (2,8) l'atteignent sur C, aucun hors échantillon.
