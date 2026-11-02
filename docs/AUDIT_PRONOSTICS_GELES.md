# Audit d'impact des pronostics Gamma gelés (01/11/2026, branche `moteur-dc-chargeur`, NON fusionnée)

Aucune fiche gelée n'a été modifiée (`data/dc/journal.jsonl` intact). Tout est rejoué à côté. Détail complet : `docs/audit_pronostics_geles.json`. Scripts : `docs/audit_gel/`.

## Périmètre (règle de Patrick du 29/10 : uniquement ce que le moteur a réellement gelé)
- **68 matchs avec au moins un pari, 97 paris** : dernière fiche gelée avant le coup d'envoi, gels du 30/10 15 h 12 UTC au 01/11 01 h 23 UTC, matchs du 30/10 au 03/11.
- **20 matchs terminés, 29 paris** ; 48 matchs / 68 paris pas encore réglés dans le journal.
- Échantillon petit et période courte (3 jours de gel) : ce sont des mesures d'impact, pas un bilan de rentabilité.

## Méthode
- Pour chaque fiche : rejeu avec le code actuel, cotes gelées et EMAC gelé, sur la version d'assemblage où **l'ancien chargeur reproduit exactement** les effectifs, les buts attendus et la taille du championnat gelés. Puis même rejeu avec le chargeur strict. Comparaison des deux.
- Reproduction : l'ancien chargeur retrouve la fiche gelée pour **67 matchs sur 68** (effectifs, buts attendus) et les paris gelés pour 65 sur 67. Le 68e (San Lorenzo – Libertad) n'est reproduit par aucune version d'assemblage commitée : **indéterminé**.
- Seules les cotes des paris gelés sont connues (les autres cotes de l'époque n'ont pas été gelées) : on mesure donc si chaque pari gelé survit, pas quels nouveaux paris apparaîtraient.

## Résultat
| Classe | Matchs | Paris | dont terminés (matchs / paris) |
|---|---|---|---|
| Non affecté (effectifs, buts attendus, probabilités identiques) | 51 | 75 | 17 / 24 |
| Affecté, probabilités modifiées, tous les paris maintenus | 14 | 17 | 3 / 5 |
| Affecté, match non analysable avec le chargeur strict (effectifs < 4) | 1 | 3 | 0 / 0 |
| Affecté, un pari retiré | 1 | 1 | 0 / 0 |
| Indéterminé | 1 | 1 | 0 / 0 |

- Écart de probabilité maximal par match affecté : **médiane 0,9 point, maximum 6,8 points** (Cercle Bruges – Antwerp).
- **Matchs terminés : 3 matchs, 5 paris touchés, tous encore valides** avec le chargeur strict (probabilité −0,6 à −1,1 point). Le bilan réel déjà réglé ne change pas de composition.
- **Matchs à venir : 12 matchs touchés.** Birmingham – Tottenham (féminin) devient non analysable (3 paris perdus) ; Coria – Arenas Getxo perd son pari (écart de 0,07 point au seuil).

### Matchs affectés
| Jour | Match | Effectifs gelé → strict | Buts attendus gelé → strict | Écart P max | Paris | Verdict |
|---|---|---|---|---|---|---|
| 10-30 | Al Shabab – Al Ahli (terminé) | [6, 6] → [6, 6] | [1.373, 1.986] → [1.368, 1.955] | 0.0084 | 2 | tous maintenus |
| 10-31 | Cannes – Valenciennes | [4, 5] → [4, 5] | [1.511, 0.813] → [1.481, 0.81] | 0.0102 | 1 | tous maintenus |
| 10-31 | Cavese – Picerno (terminé) | [5, 5] → [5, 5] | [1.89, 1.485] → [1.871, 1.471] | 0.0073 | 2 | tous maintenus |
| 10-31 | Giugliano – Caserte | [6, 5] → [6, 5] | [1.4, 1.822] → [1.385, 1.815] | 0.0052 | 1 | tous maintenus |
| 10-31 | Salford – Exeter City | [6, 6] → [6, 6] | [1.325, 0.791] → [1.335, 0.785] | 0.0047 | 1 | tous maintenus |
| 10-31 | Standard – Courtrai (terminé) | [4, 4] → [4, 4] | [2.024, 0.911] → [2.04, 0.941] | 0.012 | 1 | tous maintenus |
| 10-31 | Wealdstone – Southend Utd | [7, 8] → [7, 8] | [1.595, 2.0] → [1.612, 1.985] | 0.0064 | 1 | tous maintenus |
| 10-31 | Worthing – Sutton Utd | [8, 7] → [8, 7] | [2.039, 1.109] → [2.01, 1.125] | 0.0096 | 1 | tous maintenus |
| 11-01 | Birmingham – Tottenham | [4, 4] → [3, 3] | [1.38, 2.327] → — | — | 3 | match non analysable |
| 11-01 | CD Coria – Arenas Getxo | [4, 4] → [4, 4] | [2.256, 0.976] → [2.238, 0.972] | 0.005 | 1 | 1 pari retiré |
| 11-01 | Cercle Bruges – Antwerp | [4, 7] → [4, 4] | [1.831, 1.78] → [1.968, 1.586] | 0.0679 | 1 | tous maintenus |
| 11-01 | Torremolinos – Águilas | [6, 5] → [4, 4] | [1.815, 1.297] → [1.748, 1.226] | 0.0307 | 2 | tous maintenus |
| 11-02 | Penafiel – Feirense | [4, 4] → [4, 4] | [1.665, 0.854] → [1.669, 0.831] | 0.0099 | 1 | tous maintenus |
| 11-02 | Real Tomayapo – Blooming | [11, 11] → [11, 11] | [1.076, 1.018] → [1.098, 1.03] | 0.0092 | 1 | tous maintenus |
| 11-02 | Uni de Vinto – Always Ready | [17, 11] → [12, 11] | [1.105, 1.83] → [1.189, 1.874] | 0.0315 | 1 | tous maintenus |
| 11-03 | Northampton – Oldham | [6, 6] → [6, 6] | [1.254, 0.822] → [1.266, 0.823] | 0.0043 | 1 | tous maintenus |

### Paris maintenus mais fragiles (marge de probabilité sur le seuil calibré, avec le chargeur strict)
Wealdstone – Southend +0,6 point, Standard – Courtrai +0,7, Torremolinos – Águilas (+0,5 but de l'extérieur) +0,7, Al Shabab – Al Ahli (victoire extérieur) +0,8. Un écart d'un point suffit à les faire tomber : leur validité dépend du chargeur autant que du modèle.

## Pourquoi ces écarts : preuve sur les matchs retirés
Les historiques des équipes affectées contenaient des matchs attribués à un autre club, y compris des matchs d'une équipe contre elle-même :
- **Antwerp 13 → 9 matchs** : « Antwerp – Antwerp 1-4 » (30/08), « Cercle Bruges – Antwerp 3-3 » (14/08, pas son match), Lommel, La Louvière, Westerlo, Club Bruges.
- **Torremolinos 13 → 9** : « Torremolinos – Torremolinos 5-0 » (03/10), matchs d'Águilas, d'Antequera, de Teruel ; **Águilas 11 → 9**.
- **Uni de Vinto 30 → 23** : « Uni de Vinto – Uni de Vinto 0-2 » (12/05), matchs contre Real Oruro attribués à Vinto.
- Italie C (Latina/Cosenza, Dolomiti/Sorrento), Arabie (Neom/Al Riyadh, Al Fateh/Al Hazem), Angleterre 4e/5e divisions (Oldham/Port Vale, Aldershot/Scunthorpe), Bolivie (Real Oruro/ABB) : le **club adverse était faux**, donc la force estimée de l'adversaire l'était aussi.
Détail ligne par ligne : `causes_matchs_retires` dans le JSON.

## Constat à part, sans rapport avec le chargeur
Sur les 29 paris réglés, **6 ne passent pas la règle actuelle** : 5 paris de Shakhtar – Obolon (cote absente ou < 1,26, marché sans seuil) et 1 de Slaven – Istra (cote 1,23). Ils ont été gelés par des versions antérieures de la règle (30/10 après-midi). L'ancien chargeur donne le même résultat : ce n'est pas un effet des identités. À décider séparément : garder ces 6 paris dans le bilan ou les écarter.

## Ce que je n'ai pas pu établir
- San Lorenzo – Libertad : aucune version d'assemblage commitée ne reproduit la fiche gelée (probablement un assemblage jamais commité). Impact inconnu.
- Les nouveaux paris que le chargeur strict ferait apparaître : leurs cotes de l'époque n'existent pas.
- Les fiches des matchs à venir seront regelées à chaque passage du pipeline si la sélection change (ajout seul, anciennes lignes conservées). Tant que le chargeur strict n'est pas fusionné, le pipeline continue de produire avec l'ancien.
