# Onglet « Catégories » d'Analyse Verdict (24/11/2026)

Page `pronostics_verif.html`, code `verif_categories.py` (mesures de la fiche, intervalles, classement), `verif_pronostic.py` (intégration, clé `categories` de chaque match), `archetype_verif.js` (affichage), table figée `data/verif_pronostics/categories_zones.json`. Tests : `tests/test_verif_categories.py`, exemples de référence `tests/categories_exemples.json` (88 fiches dont les valeurs et les marchés ont été calculés par le code de l'étude). Code de l'étude : `etudes/categories_2026_11/`.

## Demande de Patrick
Quand on a la fiche des deux équipes (les 4 piliers au lieu du match, le xG calculé sur l'ensemble du championnat en cours), trouver les intervalles favorables à chaque marché et classer directement le match, avec la plus grande marge de réussite. Chaque marché a sa propre approche et son propre seuil : rien n'est généralisé. La cote ne sert qu'à la fin (minimum 1,26). Aucune notion de gain.

## La fiche
- **Piliers au lieu du match** (4 matchs minimum pour chaque équipe, saison en cours, matchs strictement avant le match) : `hM`, `hC` = buts marqués / encaissés par match de l'équipe à domicile À DOMICILE ; `aM`, `aC` = de l'équipe à l'extérieur À L'EXTÉRIEUR. Dérivés : écarts (`dM`, `dC`), croisements (`A1` = hM − aC, `X1g` = hM + aC, ...), sommes (`SM`, `SC`), rapports.
- **xG** : calculé sur TOUS les lieux de la saison en cours, pas seulement le lieu du match. xG créé = 0,514 + 0,636 × buts marqués par match ; xG concédé = 0,678 + 0,523 × buts encaissés par match (droite apprise sur 316 équipes ayant au moins 8 matchs à xG réel). `EH` = (xG créé du domicile + xG concédé de l'extérieur) / 2, `EA` de même pour l'extérieur ; `EHm`, `EAm` = ces xG moins la moyenne de buts par équipe et par match du championnat en cours (`mu`).
- Le championnat est lu sur les matchs précédents (même jour exclu) ; **moins de 10 matchs de championnat = pas de xG** (minimum de 10 maintenu par Patrick le 24/11/2026 après essai à 5) : les intervalles qui utilisent le xG ou `mu` ne s'appliquent pas (aucune valeur inventée). Seuls les piliers restent disponibles.
- Variables : `A1` = buts marqués du domicile moins buts encaissés de l'extérieur ; `A2` = buts marqués de l'extérieur moins buts encaissés du domicile ; `EA` = xg attendu de l'extérieur ; `EAm` = xg attendu de l'extérieur moins la moyenne du championnat ; `EH` = xg attendu du domicile ; `EHm` = xg attendu du domicile moins la moyenne du championnat ; `ET` = xg attendu du match (total) ; `SC` = buts encaissés par match des deux équipes réunies ; `SM` = buts marqués par match des deux équipes réunies ; `TG` = total des quatre moyennes ; `X1g` = buts marqués du domicile plus buts encaissés de l'extérieur ; `X2g` = buts marqués de l'extérieur plus buts encaissés du domicile ; `aC` = buts encaissés par match de l'extérieur, dehors ; `aM` = buts marqués par match de l'extérieur, dehors ; `dC` = buts encaissés : domicile moins extérieur ; `dE` = xg attendu : domicile moins extérieur ; `dM` = buts marqués : domicile moins extérieur ; `gA` = buts attendus de l'extérieur moins son xg ; `gH` = buts attendus du domicile moins son xg ; `hC` = buts encaissés par match du domicile, à domicile ; `hM` = buts marqués par match du domicile, à domicile ; `mu` = buts par équipe et par match du championnat ; `rC` = rapport des buts encaissés (domicile / extérieur) ; `rE` = xg attendu : rapport domicile / extérieur ; `rM` = rapport des buts marqués (domicile / extérieur) ; `rX` = rapport x1g / x2g.

## Règle de sélection d'un marché
Le match tombe dans un intervalle favorable d'un marché (bornes « bas ≤ valeur < haut ») ET le marché est coté au moins `cote_min` (1,26) par Betpawa. **Exception décidée par Patrick le 24/11/2026 : 1,24 pour le plus de 1,5 seulement** (`COTE_MIN_MARCHE` dans `verif_categories.py`), car sa cote médiane est de 1,21 et seulement 30 % des matchs l'ont à 1,26 ou plus. Effet mesuré sur les matchs du 21 au 26/11 : 54 matchs dans un intervalle du plus de 1,5, dont 1 coté ≥ 1,26 et 3 cotés ≥ 1,24.
**Bande 1,24-1,25 pour les autres marchés (Patrick, 24/11/2026)** : pour chaque marché autre que le plus de 1,5, les **3 meilleurs matchs sur les 4 jours** dont la cote est de 1,24 ou 1,25 s'ajoutent aux matchs cotés 1,26 et plus ; rien n'est forcé s'il y en a moins de 3. « Meilleur » = marge la plus haute (borne basse de Wilson de la réussite de l'intervalle sur les matchs jamais vus). **Les « 4 jours »** (Patrick, 24/11/2026) : aujourd'hui et les 3 jours suivants (jour de Douala, UTC+1), fenêtre glissante recalculée à chaque génération de la page ; chaque marché a ses 3 places sur cette fenêtre ; un match qui figure deux fois dans la page compte une fois. Un match coté 1,24-1,25 hors de la fenêtre (déjà passé ou à plus de 3 jours) n'est pas retenu par cette règle ; le suivi réel se mesure sur la sélection gelée avant le coup d'envoi (journal). Les paris cotés 1,26 et plus ne sont jamais limités. Un pari de la bande porte `categorie.bande = true` et la page l'indique. Code : `verif_categories.limiter_bande` et `verif_pronostic.periode_4_jours`, appelés par `page_donnees`.

## Comment les intervalles ont été trouvés
- Données : le grand échantillon 2000-2021 (100 422 matchs de ligues d'hommes, résultats seulement) dont 78 279 matchs ont 4 matchs au même lieu pour chaque équipe ; piliers et xG calculés avec les seuls matchs précédents (jamais le jour du match). Apprentissage 2000-2012, validation 2013-2016 (recherche) ; **jamais vus pendant la recherche** : 2017-2020 (12 728 matchs) et saison 2025-26 (11 127 matchs, bloc Football-Data).
- Pour chaque marché : découpage en vingtiles des variables, intervalles à une et deux variables, recherche exhaustive à trois variables pour les victoires (441 millions de scénarios), puis couverture gloutonne (`cover.py`) : on ajoute des intervalles tant qu'ils atteignent le seuil du marché.
- **Version A** : l'ensemble des intervalles atteint le seuil avec certitude (borne basse de Wilson 95 %) sur la recherche entière. **Version B** : chaque intervalle atteint le seuil avec certitude sur chacune des deux moitiés de la recherche (élimine les intervalles fragiles).

## Seuils (Patrick) et version retenue
Seuils donnés par Patrick le 24/11/2026 : victoire domicile 70 %, victoire extérieur 60 %, plus de 1,5 buts 80 %, X1 90 %, X2 75 %, domicile marque 90 %, extérieur marque 80 %. **X1 + moins de 4,5 buts : 74 % jusqu'au 24/11 (version A, 4 intervalles, 4,6 % des matchs, aucun match à venir ce jour-là), puis 70 % version B (décision de Patrick, 24/11/2026, re-gel de ce seul marché ; `etudes/categories_2026_11/refreeze_x1m45.py`).**
**Choix de Claude, non donnés par Patrick, à corriger si besoin** : seuils des combinés selon sa logique (produit des seuils des deux parties, arrondi à 5) : X1 + plus de 1,5 = 70 %, X2 + plus de 1,5 = 60 % ; X2 + moins de 4,5 = 65 % (ce que les données permettent) ; version B partout, sauf version A pour X1 (90 %) et la victoire à l'extérieur (60 %) où B garde trop peu de matchs ou aucun. Les seuils des combinés X1 + plus de 1,5 (70 %), X2 + plus de 1,5 (60 %) et X2 + moins de 4,5 (65 %) restent des choix de Claude, que Patrick a laissés tels quels le 24/11 (« on suit ta proposition »).
Absents faute de seuil : « domicile marque 2+ », « extérieur marque 2+ » ; « plus de 2,5 buts » a son propre onglet (+2,5 buts).

| Marché | Catalogue | Seuil | Version | Intervalles | Réussite 2017-2020 | Réussite 2025-26 |
|---|---|---|---|---|---|---|
| Victoire domicile | `1` | 70 % | B | 1 | 72.8 % (1008, 7.9 % des matchs) | 71.2 % (784, 7.0 % des matchs) |
| Victoire extérieur | `2` | 60 % | A | 4 | 64.9 % (248, 1.9 % des matchs) | 62.2 % (143, 1.3 % des matchs) |
| Plus de 1,5 | `total_plus_1.5` | 80 % | B | 2 | 85.1 % (806, 6.3 % des matchs) | 85.5 % (799, 7.2 % des matchs) |
| X1 | `1N` | 90 % | A | 1 | 91.0 % (726, 5.7 % des matchs) | 88.9 % (486, 4.4 % des matchs) |
| X2 | `N2` | 75 % | B | 1 | 78.9 % (964, 7.6 % des matchs) | 78.8 % (655, 5.9 % des matchs) |
| Domicile marque 1+ | `dom_plus_0.5` | 90 % | B | 1 | 91.9 % (405, 3.2 % des matchs) | 94.6 % (296, 2.7 % des matchs) |
| Extérieur marque 1+ | `ext_plus_0.5` | 80 % | B | 1 | 84.5 % (665, 5.2 % des matchs) | 85.5 % (442, 4.0 % des matchs) |
| X1 + plus de 1,5 | `1N&total_plus_1.5` | 70 % | B | 1 | 72.2 % (1390, 10.9 % des matchs) | 70.4 % (1106, 9.9 % des matchs) |
| X2 + plus de 1,5 | `N2&total_plus_1.5` | 60 % | B | 1 | 69.3 % (462, 3.6 % des matchs) | 65.9 % (293, 2.6 % des matchs) |
| X1 + moins de 4,5 | `1N&total_moins_4.5` | 70 % | B | 1 | 71.6 % (3189, 25.1 % des matchs) | 70.5 % (2377, 21.4 % des matchs) |
| X2 + moins de 4,5 | `N2&total_moins_4.5` | 65 % | B | 1 | 68.3 % (665, 5.2 % des matchs) | 69.9 % (442, 4.0 % des matchs) |

## Intervalles figés

### Victoire domicile — seuil 70 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| 1.800 ≤ hM et 1.244 ≤ rE | 3310/4587 = 72.2 % | 734/1008 = 72.8 % | 558/784 = 71.2 % |

### Victoire extérieur — seuil 60 %, version A

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| EHm < -0.205 et 0.306 ≤ EAm | 442/686 = 64.4 % | 145/222 = 65.3 % | 72/107 = 67.3 % |
| 2.429 ≤ X1g < 2.533 et 2.974 ≤ ET < 3.067 | 49/70 = 70.0 % | 17/28 = 60.7 % | 17/36 = 47.2 % |
| hM < 1.091 et 3.846 ≤ SM | 17/18 = 94.4 % | 3/3 = 100.0 % | 3/4 = 75.0 % |
| 1.833 ≤ hC et 2.434 ≤ SC < 2.500 | 8/8 = 100.0 % | 0/1 = 0.0 % | 1/1 = 100.0 % |

### Plus de 1,5 — seuil 80 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| 2.200 ≤ hM et 1.559 ≤ EH | 2908/3554 = 81.8 % | 618/724 = 85.4 % | 610/710 = 85.9 % |
| -0.250 ≤ dC < 0.375 et 1.559 ≤ EH | 596/722 = 82.5 % | 159/187 = 85.0 % | 209/245 = 85.3 % |

### X1 — seuil 90 %, version A

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| 1.222 ≤ dM et 1.244 ≤ rE | 2982/3274 = 91.1 % | 661/726 = 91.0 % | 432/486 = 88.9 % |

### X2 — seuil 75 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| dE < -0.309 et 0.242 ≤ EAm | 3265/4227 = 77.2 % | 761/964 = 78.9 % | 516/655 = 78.8 % |

### Domicile marque 1+ — seuil 90 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| 3.500 ≤ SM et 1.244 ≤ rE | 1492/1616 = 92.3 % | 372/405 = 91.9 % | 280/296 = 94.6 % |

### Extérieur marque 1+ — seuil 80 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| EHm < -0.082 et 0.242 ≤ EAm | 2284/2762 = 82.7 % | 562/665 = 84.5 % | 378/442 = 85.5 % |

### X1 + plus de 1,5 — seuil 70 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| -0.857 ≤ A1 et 0.296 ≤ dE | 4435/6137 = 72.3 % | 1003/1390 = 72.2 % | 779/1106 = 70.4 % |

### X2 + plus de 1,5 — seuil 60 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| EHm < -0.145 et 0.242 ≤ EAm | 1109/1726 = 64.3 % | 320/462 = 69.3 % | 193/293 = 65.9 % |

### X1 + moins de 4,5 — seuil 70 %, version B (re-gel du 24/11/2026)

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| EA < 1.272 et 1.039 ≤ rE | 11428/15767 = 72.5 % | 2282/3189 = 71.6 % | 1676/2377 = 70.5 % |

**Ensemble** : 24,1 % des matchs en 2000-2016, 25,1 % en 2017-2020, 21,4 % en 2025-26. Ancienne version (74 %, A, 4 intervalles) : 4,6 % des matchs, 74,3 % / 74,9 %. La version A à 70 % (14 intervalles, 34,6 % des matchs) ne tenait que 69,9 % / 68,1 % sur les matchs jamais vus : écartée. Le nouvel intervalle n'utilise pas la moyenne du championnat (`mu`), donc la limite des championnats lus sur peu de matchs ne le touche pas.

### X2 + moins de 4,5 — seuil 65 %, version B

| Intervalle | 2000-2016 | 2017-2020 | Bloc 2025-26 |
|---|---|---|---|
| EHm < -0.082 et 0.242 ≤ EAm | 1888/2762 = 68.4 % | 454/665 = 68.3 % | 309/442 = 69.9 % |

## Minimum de matchs de championnat : 10 maintenu (Patrick, 24/11/2026)
Un essai à 5 matchs a été fait puis abandonné : sur les matchs réels des 7 derniers jours (540 matchs), il ne change aucune sélection (100 matchs, 149 paris dans les deux cas). Les seuils et les intervalles de l'étude sont inchangés.
**Ce que l'étude ne permet pas de mesurer** : dans les données de l'étude, le championnat comptait toujours au moins 33 matchs précédents (au moins 4 matchs au même lieu par équipe l'impose). Un championnat lu sur 5 matchs n'y existe pas. Simulation faite pour l'essai à 5 (24/11/2026, matchs jamais vus 2017-2020 et 2025-26, moyenne du championnat recalculée sur 5 matchs tirés au hasard parmi les précédents, `etudes/categories_2026_11/sim_mu5.py`) : les marchés dont les intervalles n'utilisent pas la moyenne du championnat ne changent pas ; les autres perdent des matchs et deux changent de niveau.

| Marché | Seuil | Étude (championnat complet) | Simulation (5 matchs) |
|---|---|---|---|
| Victoire extérieur | 60 % | 250/391 = 63,9 % | 122/190 = 64,2 % |
| X2 | 75 % | 1277/1619 = 78,9 % | 1195/1524 = 78,4 % |
| Extérieur marque 1+ | 80 % | 940/1107 = 84,9 % | 362/413 = 87,7 % |
| X2 + plus de 1,5 | 60 % | 513/755 = 67,9 % | 169/268 = 63,1 % |
| X1 + moins de 4,5 (ancienne version, 74 %) | 74 % | 1241/1668 = 74,4 % | 1839/2568 = 71,6 % |
| X2 + moins de 4,5 | 65 % | 763/1107 = 68,9 % | 279/413 = 67,6 % |

Victoire domicile, plus de 1,5, X1, domicile marque 1+ et X1 + plus de 1,5 : identiques (leurs intervalles n'utilisent pas la moyenne du championnat). L'ancienne version de X1 + moins de 4,5 (74 %) passait sous son seuil avec un championnat lu sur 5 matchs (intervalle 2 : `mu < 1,172`) ; la version 70 % B n'utilise pas `mu` et n'est pas concernée.

## Limites connues
- Les taux sont des taux passés mesurés sur des matchs jamais vus, pas des probabilités ; le bloc 2025-26 et le flux se recoupent dans le temps avec le suivi réel.
- Certaines réussites du bloc 2025-26 sont sous le seuil (X1 : 88,9 % pour 90 % ; victoire domicile, version B : 71,2 %) ; les intervalles étroits (ex. X1 + moins de 4,5, 2e et 4e intervalles) sont fragiles : 63 % sur 60 matchs et 6 sur 10 en 2017-2020.
- Le xG réel n'existe que sur très peu de matchs (3 594 lignes) : le xG des intervalles est estimé par la droite ci-dessus. Le championnat de la page est lu dans les historiques des équipes du flux : il peut être incomplet pour un championnat peu couvert, d'où le minimum de 10 matchs de championnat (voir ci-dessous).
- La saison complète d'une équipe (xG, tous lieux) vient de `saison_complete` : mêmes matchs que le tableau xG de la page.
- La cote Betpawa n'existe pas pour tous les marchés : seuls ceux qui en ont une, ≥ 1,26, sont montrés.
- Suivi réel : la commande `python verif_pronostic.py page` gèle la sélection « categories » de chaque match à venir (journal des sélections, empreintes chaînées) ; `bilan_selections` la mesure sur les matchs terminés (ligne « Onglet Catégories » du tableau de la page). Rien n'est mesuré tant qu'aucun match gelé n'est terminé.

## Régénérer
Les intervalles sont figés : ne pas les recalculer sans décision de Patrick. Pour les rejouer : `etudes/categories_2026_11/freeze_final.py` (nécessite les tables de l'étude construites par `build.py` à partir du dossier `etude_neutre` de la branche `etude-neutre`). Tout changement d'intervalle ou de seuil : mettre à jour `categories_zones.json`, ce document et `tests/test_verif_categories.py` ensemble.
