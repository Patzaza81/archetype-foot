# Étude complète Mega Power — classement, goal-average, réciproque, nature du championnat, cotes

Branche `megapower-audit`. Aucune modification du moteur. PR 171 non fusionnée. Aucune cote dans les modèles (cotes du bloc utilisées seulement après coup, E20).
Données : bloc 2 saisons, 11 127 matchs analysables (9 806 avec λ équipes), 38 divisions. Découpage chronologique A (01/09/25→31/01/26, 4 328), B (→12/04/26, 2 690), C test jamais utilisé (13/04→16/10/26, 2 788).
Scripts : `experiences_megapower/e18_table3.py` (50 variables : classement réel à la date, écart de points / rang, points par match, goal-average global et par lieu, forme, attaque/défense réciproques au même lieu corrigées de l'adversaire, nature du championnat), `e19_blocs.py`, `e20_cotes.py`. Sorties : `sorties/e19_blocs.txt`, `sorties/e20_cotes.txt`.

## 1. Apport de chaque famille (log-loss sur C, 27 marchés)
| Bloc ajouté | gain moyen (×1e-4) | marchés ≥ 2 erreurs-types |
|---|---|---|
| Modèle d'équipes | +17,0 | 12 / 27 |
| Classement réel + écart de points | −10,7 | 0 / 27 |
| Goal-average (global + par lieu) | −4,3 | 0 / 27 |
| Attaque/défense réciproques au même lieu | +5,1 | 3 / 27 |
| Nature du championnat | +7,3 | 8 / 27 |
Le gain cumulé final est faible (≈ +10 à +38 ×1e-4 sur les marchés de buts, ≈ 0 sur 1N/12/N). Seuls sont démontrés : modèle d'équipes et nature du championnat (marchés de buts).
Le classement et le goal-average n'apportent rien de démontré en plus du modèle actuel (déjà basé sur buts marqués/encaissés au même lieu, qui contient ces informations).

## 2. Intervalle de cote (cote ≥ 1,26, cotes de clôture du bloc)
Réussite réelle quasi monotone : plus la cote est basse, plus la réussite est haute. Sur C :
- 1N : 1,26–1,32 → 71 % ; 1,32–1,52 → 65–68 % ; 1,52–1,74 → 56 % ; > 1,74 → 42 %.
- N2 : 1,26–1,43 → 70,5 % ; 1,43–1,59 → 61 % ; 1,59–1,80 → 56 % ; > 1,8 → 47 %.
- 12 : 1,26–1,34 → 67–72 % ; > 1,34 → 65 % (n = 197).
- 1 : < 1,69 → 60 % ; 2 : < 2,28 → 53 %.
Aucune zone au-dessus de 75 %. Le maximum de réussite coïncide avec le minimum de cote : la cote maximale utile se règle selon l'objectif de réussite (ex. 1N ≤ 1,52 ≈ 65 %+, N2 ≤ 1,59 ≈ 61 %+). Le modèle actuel ajoute peu à la cote seule (moitié haute du modèle vs bande : écarts ≤ 3 points, dans l'IC).
Limite : la cote reflète déjà la force des équipes ; ce résultat décrit où la réussite est haute, il n'est pas une règle apprise sur les données du modèle.

## 3. Nature du championnat (10 divisions ≥ 300 matchs)
- +1,5 : de 62,6 % (ARG) à 83,2 % (CHN) ; BTTS 43,7 % → 64,4 % ; +2,5 35,8 % → 62,5 % : différences très significatives (p < 1e-11).
- 12 : 68,9 % → 77,6 % (p = 0,045, limite) ; 1N et N2 : pas de différence démontrée (p = 0,12 et 0,45).
=> La nature du championnat doit être un paramètre des marchés de buts (+1,5 par division : ARG à écarter ou à seuil plus strict), pas des marchés de victoire/double chance.

## 4. Conclusions honnêtes
- Démontré : modèle d'équipes (+ probabilités), nature du championnat pour les buts, cote basse = réussite haute.
- Non démontré : classement/écart de points, goal-average, réciproque au même lieu en plus du modèle actuel.
- Aucun marché ne dépasse ~72 % de façon stable sous le filtre 1,26 avec ces variables ; 12 reste ≈ 70 % (n = 5 400, IC ±1,2).
- Limites : 2 saisons seulement (2425 absente), pas de xG dans le bloc, cotes de clôture moyennes (≠ Betpawa), 10 divisions pour l'hétérogénéité.
- Mémoire statistique par marché : non créée (attend validation).
