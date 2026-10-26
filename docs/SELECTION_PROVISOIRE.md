# Sélection provisoire alpha par marché (26/10/2026) — NON branchée, NON gelée

Décision de Patrick (26/10/2026) : arrêter l'exploration et fixer des règles provisoires à partir des résultats existants. Rien n'est validé ; rien n'est en production.

## Règle commune
- Population : pronostics **publiés par alpha** (admission inchangée : branches ≥ 50 %, norme de niveau, aucun calcul modifié).
- **Niveau normal** = le pronostic publié par alpha. **Niveau maximal** = en plus, au plus 1 match passé où l'événement a échoué, dans les paires publiées (`scenarios_offensifs` o, `scenarios_defensifs` d) : match de l'équipe qui reçoit = score (o[0], d[1]) ; match de l'équipe qui se déplace = score (d[0], o[1]). Même définition que l'indice maximal gelé du Plus de 1,5 (`tickets.matchs_faibles`).
- Cote : cote BetPawa figée au run nocturne ≥ 1,25, sinon pas de pronostic. Multigoals : sans cote.
- Cible provisoire : 70 % (objectif le plus bas déjà fixé, bandes 1X2), atteinte en découverte (avant 01/04/2026), en contrôle (01/04–27/09/2026) **et** par les pronostics publiables de la fenêtre BetPawa (28/09–25/10/2026). Fréquence : assez de publiables pour qu'en 28 jours la borne basse de Wilson 95 % puisse atteindre 70 % au taux observé.
- Niveau choisi : le normal si les deux passent, sauf si le maximal a un taux publiable significativement plus haut (5 %, unilatéral) ; le seul qui passe sinon ; exclu si aucun.

## Retenus (8 marchés)
| Marché | Niveau | Historique (découverte / contrôle) | Publiables BetPawa | Fréquence | Rendement (IC 95 %) |
|---|---|---|---|---|---|
| Multigoals 1-4 | normal | 79,4 % / 7 319 ; 78,0 % / 3 997 | 77,3 % / 1 099 (sans cote) | 39,2/j | non mesurable |
| Double chance 12 | normal | 74,2 % / 6 850 ; 73,7 % / 3 796 | 73,1 % / 773 [69,9–76,1] | 27,6/j | −5 % [−9 ; −1] perte démontrée |
| Plus de 1,5 buts | normal | 78,0 % / 4 804 ; 79,2 % / 2 968 | 76,4 % / 191 [69,9–81,9] | 6,8/j | 0 % [−8 ; +8] |
| Handicap +1,5 domicile | normal | 87,3 % / 7 837 ; 87,3 % / 4 370 | 72,4 % / 156 [64,9–78,8] | 5,6/j | +3 % [−7 ; +13] |
| Moins de 4,5 buts | normal | 86,8 % / 7 698 ; 84,5 % / 4 227 | 71,6 % / 134 [63,5–78,6] | 4,8/j | −5 % [−15 ; +6] |
| Domicile plus de 0,5 | normal | 82,9 % / 3 799 ; 82,8 % / 2 441 | 74,2 % / 97 [64,7–81,9] | 3,5/j | −1 % [−13 ; +10] |
| Extérieur moins de 2,5 | normal | 87,7 % / 7 831 ; 86,2 % / 4 355 | 77,4 % / 84 [67,4–85,0] | 3,0/j | +6 % [−7 ; +18] |
| Domicile moins de 2,5 | maximal | 86,1 % / 2 592 ; 84,8 % / 1 129 | 73,9 % / 46 [59,7–84,4] | 1,6/j | +1 % [−16 ; +19] |

Exclus : 30 marchés publiés (preuves dans `data/etudes/selection_provisoire_2026-10-26.json`) ; 3 jamais publiés par alpha (plus de 4,5, nul, extérieur plus de 2,5).

## Limites
- La réussite des **publiables** n'est mesurable que sur 28 jours (fenêtre BetPawa), où les paramètres d'alpha ont été réglés : risque d'optimisme.
- Aucune rentabilité démontrée ; Double chance 12 est en perte démontrée.
- À 80 %, aucun marché ne tient avec une fréquence utile.

## Reproduction
`python etudes/selection_provisoire/niveaux.py && python etudes/selection_provisoire/provisoire.py`
