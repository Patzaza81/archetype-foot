# Onglet « +2,5 buts » d'Analyse Verdict (23/11/2026, refait le 24/11/2026 : modèle de probabilité)

Code : `verif_regle_plus25.py` (modèle et étude), intégré à `verif_pronostic.py` (`fiche_match`, `page_donnees`, `selections_page`, `championnat_stats_avant`) et à `archetype_verif.js`.
Données : `data/verif_pronostics/modele_plus25.json` (modèle gelé), `data/verif_pronostics/regle_plus25.json` (étude, réécrite par `python verif_regle_plus25.py`). Tests : `tests/test_verif_regle_plus25.py`, `tests/modele_plus25_exemples.json`.

## La règle actuelle

Un match est retenu si, ensemble :
1. au moins **4 matchs au même lieu** pour chaque équipe et **10 matchs de championnat** déjà joués ;
2. la **probabilité de 3 buts ou plus** donnée par le modèle est au moins le **seuil** (`seuil` du fichier du modèle, 0,6225) ;
3. à la fin, la **cote du plus de 2,5 buts est entre 1,26 et 1,45** (le marché est d'accord).

Le modèle : régression logistique sur 29 mesures calculées sur les matchs joués avant le match (paramètres de Patrick) : buts marqués et encaissés de chaque équipe à son lieu et sur la saison, sommes et croisements (marqués d'un côté + encaissés de l'autre), part des matchs à 3 buts ou plus, part des matchs où l'équipe marque, encaisse, les deux marquent, différences de buts, moyenne de buts et part de matchs à 3 buts ou plus du championnat. Valeurs extrêmes ramenées aux bornes 0,5 % - 99,5 % de l'apprentissage.

## D'où viennent le modèle et le seuil (rien posé à la main)

- Apprentissage UNE FOIS sur 48 901 matchs de 2000 à 2012 (résultats publics sur GitHub : cache Soccerverse et footballcsv ; Angleterre 1 à 4, Allemagne 1 à 3, Espagne 1, Italie, France, Autriche, Pays-Bas, Portugal, Brésil, Argentine). Coefficients gelés dans `modele_plus25.json`.
- Seuil = plus petit seuil dont la précision sur 2013-2016 (au moins 100 matchs) atteint **70 %** (cible de Patrick, comme le moteur Gamma).
- Plafond de cote 1,45 : trouvé sur l'étude 2025-2026 (rupture de précision entre 1,35-1,45 et 1,45-1,6), reconfirmé avec le modèle.
- Cotes Betpawa et Football-Data identiques sur 177 matchs communs (rapport médian 1,00).

## Résultats sur des matchs jamais vus par le modèle

| Échantillon | Retenus | 3 buts ou plus | Tous les matchs |
|---|---|---|---|
| 2013-2016 (choix du seuil) | 265 | 70,9 % | 48,4 % |
| 2017-2021 (jamais vu) | 178 | 75,8 % | 49,7 % |
| 2025-2026, bloc Football-Data (jamais vu) | 299 | 71,2 % (intervalle 65,9 à 76,1 %) | 52,7 % |
| 2025-2026 avec cote de 1,26 à 1,45 | 44 | 79,5 % | |
| 2025-2026 avec cote au-dessus de 1,45 | 40 | 37,5 % (le marché désapprouve) | |

Ancienne règle à cinq conditions (championnat, écart de buts, domicile marque, extérieur marque peu, 57 % de matchs à 3 buts) : 64,7 % sur 729 matchs du grand échantillon, 75,0 % sur 104 matchs 2025-2026. Le modèle la bat sur les trois échantillons.

## Limites connues

- Mesure réelle de la page du 20 au 22/11/2026 : 8 matchs sur 18 terminés à 3 buts ou plus (44 %), échantillon petit (intervalle large) mais sous l'attendu ; à surveiller.
- Le modèle n'a pas été appris sur des championnats de femmes ni sur des équipes réserves (Jong Ajax, Jong AZ…), que la page retient aussi : écart de domaine non mesuré.
- Les moyennes du championnat de la page viennent du flux (matchs vus par le système), pas du championnat complet comme dans l'étude : à vérifier.
- La cote : 44 matchs avec cote Football-Data dans la bande, intervalle large (65,5 à 88,9 %).

## Historique : ancienne règle à cinq conditions et études du 24/11/2026

### Étude de plafond (24/11/2026) : une autre méthode fait-elle mieux ?

Demande de Patrick : étude profonde plutôt que des conditions ajoutées une à une. Banc : les 5 478 matchs jamais vus (01/02 au 16/10/2026, 4 matchs au même lieu, 53,9 % à 3 buts ou plus). Tous les modèles sont réappris chaque mois sur le passé seulement ; aucune cote dans les modèles de buts.

| Méthode | Résultat sur les matchs jamais vus |
|---|---|
| Force des équipes (attaque et défense ajustées à l'adversaire, Poisson, apprise sur toute la ligue) | AUC 0,570 |
| Régression sur les 5 mesures de la règle | AUC 0,577 |
| Même régression + force des équipes | AUC 0,578 (aucun gain) |
| Seuil de probabilité réappris chaque mois (cible 70 %, comme le moteur Gamma) | 137 matchs, 74,5 % |
| Règle à 5 conditions | 104 matchs, 75,0 % |
| À cote Football-Data ≥ 1,26 : seuil réappris / règle | 24 matchs 62,5 % / 40 matchs 67,5 % |

- Plafond : environ 75 % sur ces matchs, quelle que soit la méthode. La règle est déjà à ce niveau ; aucun modèle ne la bat de façon nette.
- La cote Football-Data (moyenne de clôture) porte plus d'information que tous les paramètres de buts : AUC 0,601 seule, 0,603 avec les 5 mesures (3 225 matchs avec cote). Cote seule entre 1,26 et 1,45 : 239 matchs, 74,1 %.
- Règle et cote Football-Data entre 1,26 et 1,45 : 22 réussis sur 26 (84,6 %), contre 20 sur 35 (57,1 %) au-dessus de 1,45 (Fisher 0,027 ; les deux périodes vont dans le même sens). Échantillon petit (la cote Football-Data n'existe que pour une partie des matchs) et sens inverse sur la page du 24/11 avec les cotes Betpawa (5 sur 8 jusqu'à 1,45, 5 sur 6 au-dessus) : plafond retenu malgré tout (condition 6) : sur 177 matchs communs les cotes Betpawa et Football-Data sont les mêmes, et 14 matchs ne pèsent pas face à 61. À revérifier avec les matchs Betpawa à venir.
- Limite : les variantes ont été comparées sur les mêmes matchs jamais vus, les chiffres sont donc légèrement favorables à toutes. Scripts d'étude hors dépôt.

### Test sur un grand échantillon indépendant (24/11/2026, demande de Patrick)

Source : résultats publics sur GitHub (cache Soccerverse et footballcsv : Angleterre 1 à 4, Allemagne 1 à 3, Espagne 1, Italie, France, Autriche, Pays-Bas, Portugal, Brésil, Argentine), saisons 2000 à 2020, 78 279 matchs évaluables (4 matchs au même lieu). Aucun de ces matchs n'a servi à chercher les seuils. Les conditions 1 à 5 sont testées telles quelles (la cote n'existe pas dans ces fichiers : condition 6 non testable ici).

- Règle (conditions 1 à 5) : 729 matchs, 472 à 3 buts ou plus = **64,7 %** (intervalle 61,2 à 68,1 %). Tous les matchs : 48,9 %. Hors règle : 48,7 %.
- Écart avec l'étude 2025-26 (75,0 % sur 104 matchs) : le grand échantillon dit environ 65 % ; 75 % était dans le haut de l'intervalle.
- Stable par période : 2000-04 59,7 %, 2005-09 65,1 %, 2010-14 62,9 %, 2015-19 71,0 %.
- Stable par championnat : Autriche 62,6 % (115), Allemagne 60,7 % (112), Pays-Bas 65,3 % (346), Espagne 71,2 % (59), Angleterre 67,6 % (34). Sans les Pays-Bas : 246 sur 383 = 64,2 %.
- Des championnats à peu de buts (France, Portugal, Argentine, Angleterre 4) n'ont aucun match retenu : la condition 1 les écarte.
