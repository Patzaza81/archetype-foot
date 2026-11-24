# Onglet « +2,5 buts » d'Analyse Verdict (23/11/2026, demande de Patrick)

Code : `verif_regle_plus25.py` (règle et étude), intégré à `verif_pronostic.py` (`fiche_match`, `page_donnees`, `selections_page`) et à `archetype_verif.js`.
Données : `data/verif_pronostics/regle_plus25.json` (réécrit par `python verif_regle_plus25.py`). Tests : `tests/test_verif_regle_plus25.py`.

## La règle (les quatre conditions ensemble)

Saison en cours, matchs joués avant le match, au moins **4 matchs au même lieu** pour chaque équipe :
1. le championnat compte au moins **2,88 buts par match** (matchs précédents du championnat, 10 au moins) ;
2. sur la saison, la **différence de buts par match** de l'équipe à domicile dépasse celle de l'équipe à l'extérieur d'au moins **1,09** ;
3. l'équipe à domicile a **marqué dans au moins 60 %** de ses matchs à domicile ;
4. l'équipe à l'extérieur marque **au plus 1,33 but par match** à l'extérieur.

5. (24/11/2026, demande de Patrick après Viborg – Randers) dans les matchs des deux équipes à leur lieu (domicile de l'une + extérieur de l'autre), au moins **57 %** ont compté 3 buts ou plus. Viborg – Randers : 7 sur 13 (54 %), écarté.

La **cote n'entre pas dans la règle** (consigne de Patrick : la cote seulement à l'aboutissement). L'onglet ne montre que les matchs qui remplissent la règle et dont le « plus de 2,5 buts » Betpawa est coté **1,26 ou plus** (cote minimale de la page). Le verdict de la page n'est pas affiché.

## Origine des seuils

Paramètres de Patrick : buts marqués et encaissés de chaque équipe, comparés entre les deux, et moyenne de buts du championnat. Aucun seuil n'est posé à la main : recherche sur les matchs joués **avant le 01/02/2026** (`data/bloc_saisons`), seuils pris parmi les vingtiles des données, règle retenue seulement si elle tenait sur les deux moitiés de cette période ; puis vérification sur les matchs **à partir du 01/02/2026**, jamais vus pendant la recherche.

## Résultats (matchs déjà joués, `data/bloc_saisons`, 11 127 matchs évaluables)

- Période de recherche : 92 matchs, +2,5 réussi 83,7 %.
- **Matchs jamais vus (01/02 au 16/10/2026) : 104 matchs, +2,5 réussi 75,0 %** (intervalle 65,9 à 82,3 %), contre 53,9 % pour tous les matchs de la même période. Avant l'ajout de la condition 5 : 159 matchs à 72,3 %.
- Jamais vus et cote Football-Data ≥ 1,26 : 40 matchs, 67,5 % (avant : 62 matchs, 71,0 %), cote moyenne 1,46. Échantillon petit : la condition 5 gagne environ 3 points sur tous les matchs jamais vus mais n'améliore pas le sous-ensemble à cote ≥ 1,26.
- Page du 24/11/2026 : 18 matchs (27 avant), dont 14 terminés : 10 réussis ; les 9 matchs écartés : 5 réussis. Les cotes Betpawa ne sont pas dans cet échantillon : le parallèle Betpawa se fera sur les sélections gelées.
- Hors règle (toute la période) : 52,1 %.

## Mesure réelle

La sélection « plus25 » est gelée avant chaque coup d'envoi (`data/verif_pronostics/journal_selections.jsonl`, comme les autres onglets) ; sa réussite réelle s'affiche dans le tableau de la page (« Onglet +2,5 buts ») quand des matchs sont terminés.

## Ce qui ne change pas

Aucun autre onglet ni marché : vérifié sur les 528 matchs de la page du 23/11/2026 (fiches identiques hors le champ `plus25`, aucun match ajouté ni retiré).

## Étude de plafond (24/11/2026) : une autre méthode fait-elle mieux ?

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
- Règle et cote Football-Data entre 1,26 et 1,45 : 22 réussis sur 26 (84,6 %), contre 20 sur 35 (57,1 %) au-dessus de 1,45 (Fisher 0,027 ; les deux périodes vont dans le même sens). Échantillon petit (la cote Football-Data n'existe que pour une partie des matchs) et sens inverse sur la page du 24/11 avec les cotes Betpawa (5 sur 8 jusqu'à 1,45, 5 sur 6 au-dessus) : plafond de cote NON retenu, à revérifier quand les matchs avec cote Betpawa seront plus nombreux.
- Limite : les variantes ont été comparées sur les mêmes matchs jamais vus, les chiffres sont donc légèrement favorables à toutes. Scripts d'étude hors dépôt.
