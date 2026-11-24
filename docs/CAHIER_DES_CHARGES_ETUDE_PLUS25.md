# Cahier des charges : trouver, marché par marché, la meilleure approche à partir des 4 piliers de Patrick (premier cas : le « plus de 2,5 buts »)

Rédigé le 24/11/2026 (complété le même jour avec les 4 piliers) pour Patrick (fondateur d'ARCHETYPE Foot, Douala). Destinataire : un analyste (ChatGPT) qui a accès au dépôt `Patzaza81/archetype-foot` et refait l'étude de zéro, puis conclut.

## 1. Objectif

Trouver, avec des données réelles, la méthode qui sélectionne les matchs où il y aura **3 buts ou plus** avec le **taux de réussite le plus élevé et le plus constant**, sur des matchs jamais vus pendant la recherche, avec un nombre de matchs suffisant pour être utile.

L'étude ne se limite pas au +2,5 : elle doit **tester chaque marché séparément** (tous se calculent à partir des scores) et dire **quels marchés réagissent le mieux aux 4 piliers** (§ 3) : victoire domicile, victoire extérieur, double chance (1N, N2, 12), plus de 1,5 / 2,5 / 3,5 buts, moins de 2,5 / 3,5 / 4,5 buts, les deux équipes marquent, l'équipe à domicile marque 1 but ou plus / 2 buts ou plus, l'équipe à l'extérieur idem, combos double chance + plus de 1,5 / moins de 4,5 buts.

Questions finales auxquelles répondre : **« Pour chaque marché, quelle zone de valeurs des 4 piliers donne le meilleur taux de réussite, avec quels chiffres sur des matchs jamais vus ? » et « Quelle est la meilleure approche pour le +2,5 buts, et quelle est sa vraie fiabilité ? »**

## 2. Règles de Patrick (obligatoires)

1. **Aucune constante posée à la main.** Tout seuil, paramètre ou choix est tiré des données (quantiles, apprentissage, validation). Dire d'où vient chaque nombre.
2. **La cote intervient à la fin.** L'analyse des buts se fait sans cote. La cote ne sert qu'à l'étape finale (cote minimale **1,26**, jamais en dessous).
3. **Deux échantillons au moins :** un où l'on cherche (résultats connus), un autre jamais vu pendant la recherche. Une règle n'est retenue que si elle tient sur l'échantillon jamais vu.
4. **Minimum 4 matchs au même lieu** pour chaque équipe (domicile pour l'une, extérieur pour l'autre). Moins : match rejeté.
5. **Aucune affirmation non justifiée.** Chaque chiffre est calculé, avec le nombre de matchs, de réussis, et l'intervalle de Wilson à 95 %. Vérifier trois fois avant d'annoncer.
6. **Pas de bilan négatif sans piste suivante.** Si une approche échoue, en tester d'autres, de façon créative (voir § 6).
7. Réponses **courtes, précises, concrètes**. Pas de justification de l'échec, pas de bavardage.
8. **Ne rien modifier dans le dépôt, ne rien fusionner.** Travailler dans un dossier à part et livrer un rapport et le code.

## 3. Les 4 piliers de Patrick (base de toute l'analyse)

Sur la page Analyse Verdict, chaque match affiche, pour chaque équipe **dans le rôle du match**, deux moyennes et le nombre de matchs (exemple de Patrick, captures du 24/11/2026) :

| | Marque | Encaisse | Matchs |
|---|---|---|---|
| Équipe à **domicile**, à domicile | 2,6 | 1,6 | 8 |
| Équipe à **l'extérieur**, à l'extérieur | 1,0 | 1,3 | 6 |

Ce sont les **4 piliers** : `M_dom` (marque à domicile), `E_dom` (encaisse à domicile), `M_ext` (marque à l'extérieur), `E_ext` (encaisse à l'extérieur). Toute l'étude part d'eux. Ils sont calculés sur les matchs joués avant le match, saison en cours, au même lieu, 4 matchs au minimum.

**Ce qu'il faut exploiter : les écarts, rapports et intervalles entre ces 4 nombres.** Au minimum, calculer et tester :
- l'écart d'attaque `M_dom − M_ext` (ici +1,6) et le rapport `M_dom / M_ext` (ici 2,6 fois plus de buts marqués) ;
- l'écart de défense `E_dom − E_ext` (ici **+0,3 : l'équipe à domicile encaisse 0,3 de plus que l'adversaire** ; attention au sens, utiliser toujours l'écart signé et non la description orale) ;
- les croisements : attaque domicile contre défense extérieure `M_dom − E_ext` (ici +1,3), attaque extérieure contre défense domicile `M_ext − E_dom` (ici −0,6) ;
- les sommes `M_dom + M_ext` (buts marqués) et `E_dom + E_ext` (buts encaissés), et les croisements `M_dom + E_ext`, `M_ext + E_dom` (buts attendus de chaque côté) ;
- le **xG du championnat** (approché par la moyenne de buts par match du championnat avant le match ; ajouter le xG par équipe quand il existe), seul ou comparé aux piliers (écart entre les buts attendus d'une équipe et la moyenne du championnat) ;
- toute autre donnée utile (moyennes sur toute la saison, part de matchs où l'équipe marque, encaisse ou voit 3 buts ou plus, forme récente), à ajouter seulement si elle améliore les résultats de façon mesurable sur des matchs jamais vus.

**Méthode attendue (marché par marché) :**
1. Construire la table de milliers de cas : une ligne par match avec les 4 piliers, tous les écarts et rapports, le xG du championnat, le nombre de matchs, et le résultat 0/1 de CHAQUE marché (calculé depuis le score).
2. Pour chaque marché, découper chaque écart ou rapport en **intervalles** (quantiles des données, jamais des bornes posées à la main), puis des couples et triplets d'intervalles. Mesurer, dans chaque zone, le taux de réussite du marché avec nombre de matchs et intervalle de Wilson. Chercher les **corrélations** : quelle zone de quel écart déclenche quel marché ?
3. Exemple de patron à vérifier : « domicile marque 2,6 fois plus que l'extérieur et encaisse à peu près autant » → l'équipe à domicile gagne-t-elle, et avec quel taux sur des milliers de cas semblables ? Faire de même pour chaque schéma (attaque forte contre défense faible, deux défenses fortes, deux attaques faibles…) et dire quel marché en profite.
4. Garder une zone seulement si elle tient sur deux moitiés de la période de recherche, puis la **tester sur des matchs jamais vus** (§ 5).
5. À la fin seulement : appliquer la cote (≥ 1,26) pour chaque marché retenu et donner le nombre de matchs et le taux restants.

## 4. Données disponibles

| Donnée | Où | Contenu |
|---|---|---|
| Bloc Football-Data 2025-2027 | `data/bloc_saisons/bloc_2526_2627.json.gz` (clé `liste`, 16 558 matchs, 38 divisions, du 2025-01-23 au 2026-10-16) | `id, saison, division, date, domicile, exterieur, buts_dom, buts_ext, cotes` ; cotes Football-Data (1X2, plus/moins 2,5 : `cotes.plus_moins_2_5_cloture.moy[0]` = cote du plus de 2,5) |
| Flux du système avec cotes Betpawa | `data/archive_test/AAAA-MM-JJ.json.gz` (du 2026-09-28 au 2026-11-02) | un dictionnaire par jour ; par match : `cotes_betpawa.over_under_2.5.plus`, équipes, historiques d'équipes (`assemblage`) |
| Historique d'équipes (cache) | `data/assemblage/equipes.json` | matchs des équipes de la fenêtre J0 à J+3 (incomplet, pas une base de championnats) |
| Étude actuelle | `verif_regle_plus25.py`, `data/verif_pronostics/regle_plus25.json`, `data/verif_pronostics/modele_plus25.json`, `docs/REGLE_BUTS_PLUS_2_5.md` | fonction `cas_joues` (mesures sans fuite), modèle gelé, résultats |
| **Grand échantillon public** (hors dépôt) | GitHub `footballcsv/cache.soccerverse` (miroir nommé `france` dans nos essais, dossiers `AAAA-AA/eng.csv`, `de.csv`, `es.csv`, `it.csv`, `fr.csv`, `at.csv`, `nl.csv`, `pt.csv`, `br.csv`, `ar.csv`), `footballcsv/england`, `footballcsv/deutschland`, `footballcsv/espana` | colonnes `Date, Team 1, FT (ex. 2-1), Team 2` : résultats seulement, **sans cotes**, de 1888 à 2021 ; 78 279 matchs évaluables de 2000 à 2020 |

Limites à connaître :
- Les cotes n'existent que dans le bloc (Football-Data) et le flux (Betpawa). Sur 177 matchs communs les cotes Betpawa et Football-Data du plus de 2,5 sont identiques (rapport médian 1,00).
- Dans le système en production, les moyennes du championnat viennent du flux (matchs vus par le système), pas d'un championnat complet comme dans les études ci-dessus : à mesurer.
- Le grand échantillon contient des championnats d'hommes seulement ; la page en production contient aussi des championnats de femmes et des équipes réserves (Jong Ajax, Jong AZ…).

## 5. Protocole imposé

1. **Reproduire d'abord les chiffres de référence du § 7** avec ton propre code (sert à prouver que les données et le calcul sont les mêmes). Écart > 1 point : l'expliquer avant d'aller plus loin.
2. Découpage **dans le temps**, jamais au hasard : apprentissage → validation (choix des seuils) → test jamais vu. Ne jamais regarder le test pour choisir un modèle ou un seuil. Si le test a servi à choisir, le dire et recalculer sur un échantillon neuf.
3. Utiliser au moins **trois échantillons indépendants** : (a) grand échantillon public 2000-2021, (b) bloc Football-Data 2025-2026, (c) matchs du flux avec cotes Betpawa (28/09 au 02/11/2026) pour la mesure finale avec la cote.
4. Validation **glissante** (réapprendre chaque mois ou chaque saison sur le passé seulement) en plus du découpage unique, pour éviter un résultat dû au hasard d'une coupure.
5. Pour toute règle ou tout seuil : annoncer **nombre de matchs, nombre de réussis, taux, intervalle de Wilson 95 %**, et la période. Comparer au taux de **tous les matchs** de la même période (référence).
6. Stabilité : résultats **par période** (année) et **par championnat**. Dire si un seul championnat porte le résultat.
7. Compromis volume / fiabilité : donner la courbe (taux en fonction du nombre de matchs retenus), pas un seul point.

## 6. Pistes à explorer (liste minimale, en ajouter librement)

- Règles à seuils (conjonctions de 2 à 5 conditions, seuils pris parmi les quantiles des données, retenues seulement si elles tiennent sur deux moitiés de la période de recherche).
- Modèles de probabilité : régression logistique (avec et sans régularisation), arbres/gradient boosting simples, avec les mesures du § 3 et des croisements nouveaux.
- Modèles de forces d'équipes (attaque/défense ajustées à l'adversaire, Poisson ou Dixon-Coles) comme mesure supplémentaire.
- Seuil de probabilité appris sur les données (cible de Patrick : réussite de 70 % sur l'échantillon de validation), puis réappris chaque mois (version prospective).
- Étape finale avec la cote : bande de cotes, accord ou désaccord entre le modèle et le marché. Mesurer ce que la cote apporte en plus des statistiques.
- Segmenter : championnats à beaucoup de buts, début ou fin de saison, matchs à enjeu, équipes réserves, championnats de femmes.
- Toute idée nouvelle justifiée par les données (tendance récente, séries, xG des équipes quand il existe, etc.).

## 7. Référence à égaler ou battre (obtenue le 24/11/2026)

Cible : 3 buts ou plus (« plus de 2,5 »). Intervalle : Wilson 95 %.

| Méthode | Échantillon | Matchs retenus | Réussite |
|---|---|---|---|
| Règle à 5 conditions (championnat ≥ 2,88 buts, écart de différence de buts ≥ 1,09, domicile marque ≥ 60 %, extérieur marque ≤ 1,33, ≥ 57 % de matchs à 3 buts) | grand échantillon 2000-2020 | 729 | 64,7 % (61,2 à 68,1 %) ; tous les matchs : 48,9 % |
| Même règle | bloc 2025-2026 | 104 | 75,0 % ; tous : 53,9 % |
| **Modèle logistique** (29 mesures, appris sur 2000-2012, seuil de probabilité 0,6225 pris sur 2013-2016) | 2013-2016 (choix du seuil) | 265 | 70,9 % ; tous : 48,4 % |
| Même modèle | 2017-2021 (jamais vu) | 178 | 75,8 % ; tous : 49,7 % |
| Même modèle | bloc 2025-2026 (jamais vu) | 299 | 71,2 % (65,9 à 76,1 %) ; tous : 52,7 % |
| Même modèle + cote Football-Data entre 1,26 et 1,45 | bloc 2025-2026 | 44 | 79,5 % (65,5 à 88,9 %) |
| Même modèle + cote Football-Data au-dessus de 1,45 | bloc 2025-2026 | 40 | 37,5 % |
| Cote Football-Data seule entre 1,26 et 1,45 | bloc 2025-2026 (depuis le 01/02/2026) | 239 | 74,1 % |
| Page de vérification en production (modèle + cote Betpawa), 20 au 22/11/2026 | 18 matchs terminés | 18 | 8 réussis (44 %) : échantillon petit mais décevant ; cause non encore établie |

Constats déjà établis (à confirmer ou infirmer) :
- La **cote** (probabilité implicite du marché) prédit mieux le +2,5 que toutes les mesures de buts seules (indice AUC 0,601 contre 0,57 à 0,58) ; ajouter les mesures de buts à la cote n'améliore presque rien (0,603).
- Aucune méthode testée ne dépasse environ 75 % de réussite sur les matchs jamais vus avec un volume utile ; 90 % est hors d'atteinte pour le +2,5.
- Des variantes ont été comparées sur les mêmes matchs : leurs chiffres sont un peu favorables. D'où l'exigence d'un échantillon neuf.

## 8. Livrables

1. Un **rapport court** (2 pages maximum) : meilleure approche recommandée, tableau des résultats sur les trois échantillons (matchs, réussis, taux, Wilson, période), courbe volume/fiabilité, stabilité par année et par championnat, ce que la cote apporte.
2. Le **code reproductible** (Python 3.12, numpy ; scikit-learn accepté pour l'étude seulement : l'application en production n'utilise que numpy) dans un dossier à part, avec la commande qui régénère tous les chiffres.
3. La **réponse à la question finale** en cinq lignes, avec le niveau de certitude (petit échantillon, risque de sur-ajustement) dit clairement.
4. Un **tableau marché par marché** : pour chaque marché, la meilleure zone (ou règle) issue des 4 piliers, le nombre de matchs, le taux, Wilson, le résultat sur matchs jamais vus, puis avec la cote ≥ 1,26 ; classer les marchés du plus fiable au moins fiable.
5. Si une meilleure approche existe : la **spécification exacte** (mesures, formule ou règle, seuils appris et leur origine) pour qu'elle soit implémentée dans `verif_regle_plus25.py` sans ambiguïté.

## 9. Critères d'acceptation

- Les chiffres de référence du § 7 sont reproduits (à ± 1 point).
- Aucun seuil ou paramètre sans origine dans les données ; la cote n'entre qu'à la fin.
- Aucun résultat annoncé sans nombre de matchs, taux et intervalle.
- Le résultat final est mesuré sur un échantillon que la recherche n'a jamais vu, et la comparaison avec la référence est faite sur les mêmes matchs.
- Les deux écarts suivants sont expliqués ou mesurés : (a) pourquoi la page en production a réussi 8 sur 18 alors que l'étude annonce environ 70 % (domaine : championnats de femmes, équipes réserves, moyennes du championnat tirées du flux), (b) si le plafond de cote 1,45 tient avec les cotes Betpawa du flux.
- Le tableau marché par marché est livré, avec pour chaque marché des zones des 4 piliers (écarts, rapports, intervalles) tirées des données et testées sur matchs jamais vus.

## 10. Repères déjà obtenus sur d'autres marchés (étude du 23/11/2026, bloc 2025-2026, à reconfirmer)

- Double chance domicile (1N) et « l'équipe à domicile marque 1 but ou plus » : environ 90 % à 93 % de réussite sur des matchs jamais vus, mais surtout sur des matchs dont la cote est sous 1,26.
- Victoire et +2,5 : environ 70 % à 75 % au mieux sur des matchs jamais vus avec la cote ≥ 1,26.
- Ces repères sont à confirmer ou infirmer avec la méthode ci-dessus, sur le grand échantillon et sur le flux Betpawa.
