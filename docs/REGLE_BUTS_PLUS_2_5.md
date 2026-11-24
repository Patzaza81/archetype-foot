# Onglet « +2,5 buts » d'Analyse Verdict (23/11/2026, demande de Patrick)

Code : `verif_regle_plus25.py` (règle et étude), intégré à `verif_pronostic.py` (`fiche_match`, `page_donnees`, `selections_page`) et à `archetype_verif.js`.
Données : `data/verif_pronostics/regle_plus25.json` (réécrit par `python verif_regle_plus25.py`). Tests : `tests/test_verif_regle_plus25.py`.

## La règle (les quatre conditions ensemble)

Saison en cours, matchs joués avant le match, au moins **4 matchs au même lieu** pour chaque équipe :
1. le championnat compte au moins **2,88 buts par match** (matchs précédents du championnat, 10 au moins) ;
2. sur la saison, la **différence de buts par match** de l'équipe à domicile dépasse celle de l'équipe à l'extérieur d'au moins **1,09** ;
3. l'équipe à domicile a **marqué dans au moins 60 %** de ses matchs à domicile ;
4. l'équipe à l'extérieur marque **au plus 1,33 but par match** à l'extérieur.

La **cote n'entre pas dans la règle** (consigne de Patrick : la cote seulement à l'aboutissement). L'onglet ne montre que les matchs qui remplissent la règle et dont le « plus de 2,5 buts » Betpawa est coté **1,26 ou plus** (cote minimale de la page). Le verdict de la page n'est pas affiché.

## Origine des seuils

Paramètres de Patrick : buts marqués et encaissés de chaque équipe, comparés entre les deux, et moyenne de buts du championnat. Aucun seuil n'est posé à la main : recherche sur les matchs joués **avant le 01/02/2026** (`data/bloc_saisons`), seuils pris parmi les vingtiles des données, règle retenue seulement si elle tenait sur les deux moitiés de cette période ; puis vérification sur les matchs **à partir du 01/02/2026**, jamais vus pendant la recherche.

## Résultats (matchs déjà joués, `data/bloc_saisons`, 11 127 matchs évaluables)

- Période de recherche : 140 matchs, +2,5 réussi 80,7 %.
- **Matchs jamais vus (01/02 au 16/10/2026) : 159 matchs, +2,5 réussi 72,3 %** (intervalle 64,9 à 78,7 %), contre 53,9 % pour tous les matchs de la même période.
- Jamais vus et cote Football-Data ≥ 1,26 : 62 matchs, 71,0 %, cote moyenne 1,48. Les cotes Betpawa ne sont pas dans cet échantillon : le parallèle Betpawa se fera sur les sélections gelées.
- Hors règle (toute la période) : 52,1 %.

## Mesure réelle

La sélection « plus25 » est gelée avant chaque coup d'envoi (`data/verif_pronostics/journal_selections.jsonl`, comme les autres onglets) ; sa réussite réelle s'affiche dans le tableau de la page (« Onglet +2,5 buts ») quand des matchs sont terminés.

## Ce qui ne change pas

Aucun autre onglet ni marché : vérifié sur les 528 matchs de la page du 23/11/2026 (fiches identiques hors le champ `plus25`, aucun match ajouté ni retiré).
