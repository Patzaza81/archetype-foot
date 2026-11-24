# Cahier des charges : trouver, marché par marché, la meilleure approche à partir des 4 piliers de Patrick

Rédigé le 24/11/2026 pour Patrick (fondateur d'ARCHETYPE Foot, Douala). Destinataire : un analyste indépendant qui travaille **uniquement avec les fichiers de ce dossier** et donne son propre avis. Ce document ne contient aucun résultat d'étude antérieure.

## 1. Objectif

Trouver, avec des données réelles, pour chaque marché du périmètre ci-dessous, la méthode qui sélectionne les matchs avec le **taux de réussite le plus élevé et le plus constant**, sur des matchs jamais vus pendant la recherche, avec un nombre de matchs suffisant pour être utile.

L'étude **teste chaque marché séparément** (tous se calculent à partir des scores) et dire **quels marchés réagissent le mieux aux 4 piliers** (§ 3). **Périmètre imposé par Patrick, rien d'autre, rien de moins :**
1. Victoire de l'équipe à domicile ; victoire de l'équipe à l'extérieur (pas de nul, pas de double chance dans cet onglet).
2. Double chance : X1 (domicile ou nul) ; X2 (extérieur ou nul).
3. Plus de 1,5 buts ; plus de 2,5 buts.
4. L'équipe à domicile marque au moins 0,5 but (1 but ou plus) ; au moins 1,5 but (2 buts ou plus) ; idem pour l'équipe à l'extérieur.
5. Combinés : X1 + plus de 1,5 buts ; X2 + plus de 1,5 buts ; X1 + moins de 4,5 buts ; X2 + moins de 4,5 buts (le marché « moins de 4,5 buts » seul n'est PAS étudié).
Chaque marché est évalué séparément, avec ses propres zones des 4 piliers, ses seuils appris, son compromis volume / fiabilité. Cotes Betpawa disponibles dans le flux : 1X2, double chance, plus/moins de 1,5 / 2,5 / 4,5, buts de l'équipe à domicile (0,5 et 1,5) ; **pas de cote pour l'équipe à l'extérieur ni pour les combinés** : pour ces marchés, dire que la cote ne peut pas être contrôlée au lieu de l'inventer.

Question finale à laquelle répondre : **« Pour chaque marché, quelle zone de valeurs des 4 piliers donne le meilleur taux de réussite, avec quels chiffres sur des matchs jamais vus ? »**

## 2. Règles de Patrick (obligatoires)

1. **Aucune constante posée à la main.** Tout seuil, paramètre ou choix est tiré des données (quantiles, apprentissage, validation). Dire d'où vient chaque nombre.
2. **La cote intervient à la fin.** L'analyse des buts se fait sans cote. La cote ne sert qu'à l'étape finale (cote minimale **1,26**, jamais en dessous).
3. **Deux échantillons au moins :** un où l'on cherche (résultats connus), un autre jamais vu pendant la recherche. Une règle n'est retenue que si elle tient sur l'échantillon jamais vu.
4. **Minimum 4 matchs au même lieu** pour chaque équipe (domicile pour l'une, extérieur pour l'autre). Moins : match rejeté.
5. **Aucune affirmation non justifiée.** Chaque chiffre est calculé, avec le nombre de matchs, de réussis, et l'intervalle de Wilson à 95 %. Vérifier trois fois avant d'annoncer.
6. **Pas de bilan négatif sans piste suivante.** Si une approche échoue, en tester d'autres, de façon créative.
7. Réponses **courtes, précises, concrètes**. Pas de justification de l'échec, pas de bavardage.
8. **Travailler uniquement avec les fichiers de ce dossier.** Aucune autre source, aucun résultat d'une étude précédente : l'avis attendu est indépendant. Livrer un rapport et le code.

## 3. Les 4 piliers de Patrick (base de toute l'analyse)

Sur la page Analyse Verdict, chaque match affiche, pour chaque équipe **dans le rôle du match**, deux moyennes et le nombre de matchs (exemple de Patrick, captures du 24/11/2026) :

| | Marque | Encaisse | Matchs |
|---|---|---|---|
| Équipe à **domicile**, à domicile | 2,6 | 1,6 | 8 |
| Équipe à **l'extérieur**, à l'extérieur | 1,0 | 1,3 | 6 |

Ce sont les **4 piliers** : `M_dom` (marque à domicile), `E_dom` (encaisse à domicile), `M_ext` (marque à l'extérieur), `E_ext` (encaisse à l'extérieur). Toute l'étude part d'eux. Ils sont calculés sur les matchs joués avant le match, saison en cours, au même lieu, 4 matchs au minimum.

**Règle des lieux (essentielle, à respecter partout) :**
- **Les 4 piliers ne comptent que les matchs joués à ce lieu.** Pour l'équipe à domicile : seulement ses matchs à domicile. Pour l'équipe à l'extérieur : seulement ses matchs à l'extérieur. Ses matchs à domicile ne comptent pas, ceux de l'autre équipe à l'extérieur non plus. Jamais de mélange (une équipe qui marque beaucoup chez elle mais peu dehors doit apparaître comme telle).
- **Le xG, lui, regroupe tous les matchs de la saison en cours, domicile ET extérieur, sans distinction de lieu** (xG créé moyen et xG concédé moyen par match, car le xG par lieu a trop peu de matchs). Il sert de lecture de tendance en plus des 4 piliers : xG créé supérieur aux buts marqués = attaque qui peut mieux faire ; xG concédé supérieur aux buts encaissés = défense chanceuse ; buts attendus d'une équipe = moyenne de ce que son attaque crée et de ce que la défense adverse concède.
- **Le xG du championnat** est la moyenne de xG par équipe et par match sur TOUS les matchs du championnat, domicile et extérieur confondus. On le compare au xG des équipes (une équipe au-dessus de la moyenne du championnat a une attaque ou une défense plus ouverte que la moyenne).
- **Où est le xG :** seulement dans `flux_historiques_equipes.csv` (colonnes `xg_cree`, `xg_concede`, équipes Football-Data, environ 1 match sur 5). Les autres fichiers n'ont pas de xG : pour eux, utiliser la moyenne de buts de la saison de l'équipe (tous lieux) comme approximation, et le dire.

**Ce qu'il faut exploiter : les écarts, rapports et intervalles entre ces 4 nombres.** Au minimum, calculer et tester :
- l'écart d'attaque `M_dom − M_ext` (ici +1,6) et le rapport `M_dom / M_ext` (ici 2,6 fois plus de buts marqués) ;
- l'écart de défense `E_dom − E_ext` (ici **+0,3 : l'équipe à domicile encaisse 0,3 de plus que l'adversaire** ; attention au sens, utiliser toujours l'écart signé et non la description orale) ;
- les croisements : attaque domicile contre défense extérieure `M_dom − E_ext` (ici +1,3), attaque extérieure contre défense domicile `M_ext − E_dom` (ici −0,6) ;
- les sommes `M_dom + M_ext` (buts marqués) et `E_dom + E_ext` (buts encaissés), et les croisements `M_dom + E_ext`, `M_ext + E_dom` (buts attendus de chaque côté) ;
- le **xG** de chaque équipe et du championnat, calculé sur tous les lieux (règle des lieux ci-dessus), seul ou comparé aux piliers (écart entre les buts attendus d'une équipe et la moyenne du championnat, écart xG − buts) ;
- toute autre donnée utile (moyennes sur toute la saison, part de matchs où l'équipe marque, encaisse ou voit 3 buts ou plus, forme récente), à ajouter seulement si elle améliore les résultats de façon mesurable sur des matchs jamais vus.

**Méthode attendue (marché par marché) :**
1. Construire la table de milliers de cas : une ligne par match avec les 4 piliers, tous les écarts et rapports, le xG du championnat, le nombre de matchs, et le résultat 0/1 de CHAQUE marché (calculé depuis le score).
2. Pour chaque marché, découper chaque écart ou rapport en **intervalles** (quantiles des données, jamais des bornes posées à la main), puis des couples et triplets d'intervalles. Mesurer, dans chaque zone, le taux de réussite du marché avec nombre de matchs et intervalle de Wilson. Chercher les **corrélations** : quelle zone de quel écart déclenche quel marché ?
3. Exemple de patron à vérifier : « domicile marque 2,6 fois plus que l'extérieur et encaisse à peu près autant » → l'équipe à domicile gagne-t-elle, et avec quel taux sur des milliers de cas semblables ? Faire de même pour chaque schéma (attaque forte contre défense faible, deux défenses fortes, deux attaques faibles…) et dire quel marché en profite.
4. Garder une zone seulement si elle tient sur deux moitiés de la période de recherche, puis la **tester sur des matchs jamais vus** (§ 5).
5. À la fin seulement : appliquer la cote (≥ 1,26) pour chaque marché retenu et donner le nombre de matchs et le taux restants.

## 4. Données fournies (seules sources autorisées)

| Fichier | Contenu |
|---|---|
| `bloc_matchs_footballdata.csv` | 16 558 matchs joués, 38 divisions, 2025-01-23 au 2026-10-16 : saison, division, date, équipes, buts, cotes de clôture Football-Data (1X2, plus/moins 2,5), parfois vides. Pas de xG. |
| `grand_echantillon_2000_2021.csv` | 100 422 matchs, résultats seulement, sans cotes ni xG, 2000 à 2021 (ligues d'hommes : eng, de, es, it, fr, at, nl, pt, br, ar et divisions inférieures de eng, de, es). |
| `flux_matchs_betpawa.csv` | 5 739 matchs du 28/09 au 02/11/2026 (4 820 avec score) avec cotes Betpawa : 1X2, double chance, plus/moins 1,5, 2,5, 4,5, BTTS, équipe à domicile plus de 0,5 et 1,5. Pas de cote pour l'équipe à l'extérieur ni pour les combinés. |
| `flux_historiques_equipes.csv` | 26 142 matchs d'équipes (équipe, saison, date, lieu, adversaire, buts marqués/encaissés, xG créé/concédé pour 3 594 lignes) : sert à calculer les 4 piliers au lieu du match et le xG tous lieux des matchs du flux Betpawa, avec les seuls matchs joués avant la date du match. |

Limites à connaître : les cotes n'existent que dans le bloc Football-Data et le flux Betpawa ; le grand échantillon ne contient que des championnats d'hommes ; les matchs de femmes et d'équipes réserves peuvent apparaître dans le flux Betpawa.

## 5. Protocole imposé

1. Découpage **dans le temps**, jamais au hasard : apprentissage → validation (choix des seuils) → test jamais vu. Ne jamais regarder le test pour choisir une règle ou un seuil. Si le test a servi à choisir, le dire et recalculer sur un échantillon neuf.
2. Utiliser au moins **trois échantillons indépendants** : (a) grand échantillon 2000-2021, (b) bloc Football-Data 2025-2026, (c) matchs du flux Betpawa (28/09 au 02/11/2026) pour la mesure finale avec la cote.
3. Validation **glissante** (réapprendre chaque mois ou chaque saison sur le passé seulement) en plus du découpage unique.
4. Pour toute règle ou tout seuil : annoncer **nombre de matchs, nombre de réussis, taux, intervalle de Wilson 95 %**, et la période. Comparer au taux de **tous les matchs** de la même période.
5. Stabilité : résultats **par période** (année) et **par championnat**. Dire si un seul championnat porte le résultat.
6. Compromis volume / fiabilité : donner la courbe (taux en fonction du nombre de matchs retenus), pas un seul point.

## 6. Méthode libre

Aucune méthode n'est imposée ni suggérée. Choisir les approches soi-même, justifier chaque choix par les données, et décrire brièvement celles qui ont été essayées puis abandonnées.

## 7. Livrables

1. Un **rapport court** (2 pages maximum) : approche recommandée, tableau des résultats sur les trois échantillons (matchs, réussis, taux, Wilson, période), courbe volume/fiabilité, stabilité par année et par championnat, ce que la cote apporte.
2. Le **code reproductible** (Python 3.12, numpy ; scikit-learn accepté pour l'étude) avec la commande qui régénère tous les chiffres.
3. Un **tableau marché par marché** : pour chaque marché, la meilleure zone (ou règle) issue des 4 piliers, le nombre de matchs, le taux, Wilson, le résultat sur matchs jamais vus, puis avec la cote ≥ 1,26 (ou « cote non contrôlable » pour l'équipe à l'extérieur et les combinés) ; classer les marchés du plus fiable au moins fiable.
4. La **réponse à la question finale** en cinq lignes, avec le niveau de certitude (petit échantillon, risque de sur-ajustement) dit clairement.
5. La **spécification exacte** de chaque règle retenue (mesures, formule, seuils appris et leur origine) pour pouvoir l'implémenter sans ambiguïté.

## 8. Critères d'acceptation

- Aucun seuil ou paramètre sans origine dans les données ; la cote n'entre qu'à la fin.
- Aucun résultat annoncé sans nombre de matchs, taux et intervalle.
- Le résultat final est mesuré sur un échantillon que la recherche n'a jamais vu.
- Le tableau marché par marché est livré, avec pour chaque marché des zones des 4 piliers (écarts, rapports, intervalles) tirées des données et testées sur matchs jamais vus.
