# Correctif du chargeur de Gamma — identités (01/11/2026, branche `moteur-dc-chargeur`, NON fusionnée)

Suite de `docs/ENQUETE_ASSEMBLAGE.md` (branche `enquete-assemblage`, c9bc6dd). Fichier modifié : `moteur_dc/donnees.py` (classe `Ligues`) uniquement. Autres moteurs : aucun ne l'importe (vérifié : seuls `moteur_dc/*` appellent `Ligues` / `charger_ligues`).

## Ce qui change
1. **Rattachement strict d'un alias** : un nom d'adversaire inconnu n'est rattaché à un club que si le bloc de ce club NOMME explicitement l'équipe qui le cite (condition `o2 == t`). La ressemblance des scores ne suffit plus (un 0-0 est son propre inverse). Sans preuve explicite, l'alias reste une identité distincte « ? ».
2. **Quarantaine des erreurs de la source** : un match dont l'adversaire porte le nom de l'équipe elle-même est exclu des statistiques et listé dans `Ligues.quarantaine` (championnat, équipe, date, adversaire, score, raison).

## Preuves (données réelles, `docs/chargeur_identites_comparaison.json`)
| | assemblage `1dc1035` (31/10) | assemblage `6068a9d` (01/11) |
|---|---|---|
| Auto-rencontres, ancien → nouveau | 66 → 0 | 79 → 0 |
| dont fabriquées par l'ancien chargeur / erreurs de la source (quarantaine) | 61 / 5 | 77 / 2 |
| Matchs vus, ancien → nouveau | 9 275 → 9 302 | 8 424 → 8 462 |
| Clubs du cache fusionnés entre eux | 0 → 0 | 0 → 0 |
| Série B : identités / matchs | 20 → 20 / 90 → 90 | 18 → **20** / 81 → 82 |
| Virtus / Juve-Stabia / Cremonese / Mantova (matchs, vrai : 9 chacun) | 9 / 9 / 9 / 9 (inchangé) | 13 / 15 / 0 / 0 → **9 / 9 / 6 / 7** |

Quarantaine (erreurs de la source, hors statistiques) : `1dc1035` : Cerro-Largo (16/10), Cerro (11/04, 29/05), R. Montevideo (12/04), Yangon City (11/10) ; `6068a9d` : América Cali (26/04), Cerro (29/05). Les 5 + 2 matchs sont retirés des statistiques ; ce sont les seuls championnats qui « perdent » un match.

**Le problème dépassait la Série B.** Dans `6068a9d`, l'ancien chargeur a rattaché 112 alias à un club du cache que le chargeur strict ne rattache pas ; 106 n'ont une preuve que pour une partie des dates où l'alias est cité (donc faux), 6 n'ont qu'une citation (indécidable). Exemples : Ingolstadt rattaché à A. Aachen (preuve sur 1 date de 4), Fortuna Cologne à P. Münster (1 sur 4), Man City féminin à Tottenham (1 sur 5), Crawley Town à Gillingham (1 sur 8), **Alcorcón et Gimnàstic rattachés à Torremolinos, A. Madrid II à Águilas**. Dans `1dc1035` : 74 dont 70 faux.

## Conséquence sur les pronostics Gamma déjà gelés
Audité paris par paris dans `docs/AUDIT_PRONOSTICS_GELES.md` : sur 68 matchs / 97 paris gelés depuis le 30/10, 51 matchs ne changent pas, 15 sont affectés (écart de probabilité médian 0,9 point, maximum 6,8), 1 est indéterminé. Sur les 20 matchs déjà terminés (29 paris), 5 paris sont touchés et restent tous valides. La fiche gelée de Torremolinos – Águilas utilisait des matchs d'Alcorcón et de Gimnàstic ; avec le chargeur strict, 4 matchs à domicile et 4 à l'extérieur.

## Correction du 01/11 (retour de revue) : rattachement sur une seule citation
Le code rattache un alias avec une seule date de preuve (`len(top) == 1`). Ce n'est pas une faiblesse : la condition exige que l'autre équipe NOMME la nôtre le même jour avec le score inverse. Vérification indépendante par l'identifiant du match (`url_match`, `audit_identites.py`) : **les 21 alias rattachés (41 dans l'assemblage du 31/10) sont tous confirmés, aucun n'est contredit.** À l'inverse, **110 des rattachements de l'ancien chargeur (72 au 31/10) n'ont aucune preuve par identifiant.** Les « 6 cas à citation unique » du premier rapport étaient des rattachements de l'ancien chargeur que le strict ne fait pas ; 2 d'entre eux sont en réalité prouvés par l'identifiant (Sport Boys 2 / 2 Melgar, nommage croisé par alias) et pourraient être récupérés par une règle fondée sur l'identifiant. Non fait ici : décision de Patrick.

## Risque résiduel (coût du correctif)
Le rattachement strict peut laisser un club en deux identités (alias non reliés : 584 contre 510 en `1dc1035`, 911 contre 799 en `6068a9d`). C'est une perte de données, jamais une fausse donnée. Les matchs récupérés (+27, +38) ne rendent pas l'historique complet : l'instabilité du cache source reste entière (phase 2).

## Tests
`tests/test_chargeur_identites.py` (11) : alias rattaché quand l'autre équipe nomme la nôtre (scores 2-1, 0-0, 3-3) ; jamais sur la seule ressemblance (0-0, 1-1, 2-2) ; quarantaine (3 cas) ; Série B réelle (20 clubs, 9/9/6/7 matchs) ; tous championnats (0 auto-rencontre, 0 doublon, aucun club du cache fusionné). Avec l'ancien chargeur, 8 de ces tests échouent (vérifié) ; les 3 cas « rattaché » passent avec les deux.
