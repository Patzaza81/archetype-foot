# Rapport de fiabilité V2 / V3 — 22/10/2026

**Question** : les paris affichés « probabilité 80 % et plus », « indice 4/4 Sûr », « 3 étoiles » gagnent-ils vraiment à ce niveau ?
**Méthode** : paris GELÉS avant le match (V2 : `moteur_en_production.choix` de `data/archive_test` ; V3 : `data/v3/journal`), joints au score final, gagnés/perdus par `moteur_v3.markets.gagne`. Indice recalculé sur les séries d'AVANT le match (date strictement antérieure). Intervalles de Wilson à 95 %. Reproductible : `python evaluation/audit_fiabilite_v2_v3.py` (lecture seule).
**Échantillon** : V2 = 1 207 paris, 723 matchs (28/09 → 21/10) ; V3 = 158 paris, 146 matchs (04/10 → 20/10).

## Résultats principaux
| Paris | n | Réussite réelle | Annoncé par le moteur | Rendement à mise égale |
|---|---|---|---|---|
| V2 tous | 1 207 | 48,0 % [45–51] | 61,5 % | −10,9 % |
| V2 probabilité ≥ 80 % | 183 | 67,2 % [60–74] | 83,6 % | −7,8 % |
| V2 indice 4/4 | 97 | 60,8 % [51–70] | 79,2 % | −11,4 % |
| V2 ≥ 80 % ET 4/4 | 49 | 65,3 % [51–77] | 84,6 % | −11,2 % |
| V2 handicap +1,5 | 138 | 60,9 % [53–69] | 79,3 % | −11,3 % |
| V3 tous | 158 | 63,9 % [56–71] | 78,5 % | −6,5 % |
| V3 probabilité ≥ 80 % | 73 | 68,5 % [57–78] | 83,7 % | −5,7 % |
| V3 indice 4/4 | 41 | 68,3 % [53–80] | 81,0 % | 0,0 % |
| V3 ≥ 80 % ET 4/4 | 26 | 69,2 % [50–83] | 84,5 % | −2,1 % |

## Constats
1. **Les probabilités sont surestimées d'environ 15 points** sur toutes les bandes (60–70 %, 70–80 %, 80–90 %), V2 comme V3. Un « 88 % » se réalise environ 2 fois sur 3.
2. **L'indice 4/4 n'est pas « Sûr »** : 61 % (V2) et 68 % (V3). Il sépare bien les extrêmes en V2 (0/4 : 24 % ; 1/4 : 45 % ; 2/4 : 55 % ; 3/4 : 63 % ; 4/4 : 61 %) mais **4/4 ne fait pas mieux que 3/4**.
3. **La plupart des « 4/4 » reposent sur très peu de matchs** : V2 96 sur 167 indices maximaux (57 %) avec 3 matchs ou moins au même lieu ; V3 30 sur 67. Le cas Madura Utd. (3 matchs à domicile, 2 à l'extérieur, « fenêtre d'analyse trop courte ») est typique.
4. **Les probabilités ne distinguent presque pas mieux qu'une moyenne** : score de Brier V2 0,2471 contre 0,2496 pour une simple moyenne ; V3 0,2517 contre 0,2306 (pire que la moyenne).
5. **Étoiles** : V3 = taille de l'échantillon, pas la réussite (≤3 matchs : 69 %, 4 : 61 %, 5 : 42 %, 6+ : 76 %, aucun lien net). V2 « 3 étoiles » = catégorie A ; la catégorie n'est pas archivée. Approximation (probabilité ≥ 45 % et EV ≤ 20 %) : 55,6 % réel pour 69,6 % annoncé (n = 765) ; avec ≥ 80 % : 67,5 % pour 83,2 % (n = 151).
6. **Par marché** : V2 under 59 % (−2,2 %), over 43 % (−14,2 %), victoire 31 %, handicap 54 % ; V3 under 74 % (+7,4 %, n = 74), over 56 % (−18,5 %). Les « under » sont le seul groupe proche de l'équilibre.

## Limites (à lire avant de conclure)
- Période courte (17 à 24 jours) : les intervalles sont larges, les sous-groupes V3 ont 4 à 41 paris.
- Plusieurs paris d'un même match sont corrélés : les vrais intervalles sont plus larges que ceux affichés.
- Archive de test, pas de mises réelles : le rendement suppose la cote gelée.
- La catégorie V2 (étoiles) n'est pas dans l'archive : seule l'approximation ci-dessus est possible.
- Aucune rentabilité démontrée ; les écarts sont cohérents entre V2 et V3, ce qui les rend peu probablement dus au hasard.

## Pistes (non appliquées, à décider)
- Afficher la réussite réelle observée à côté de la probabilité, ou recalibrer la probabilité sur ces résultats (la calibration V3 existe déjà et ne corrige pas assez).
- Ne plus appeler « Sûr » un 4/4 appuyé sur 3 matchs ou moins ; afficher le nombre de matchs.
- Archiver la catégorie V2 avec chaque pari gelé pour mesurer les étoiles exactement.
