# Protocole BASE / SUPER BASE — version 3

- **Version 1** : commit `92d708a`, 12/10/2026 à 23 h 46 UTC. Elle déclare l'hypothèse H1 et fixe les tranches de cote. **Ces deux éléments sont inchangés en version 2.**
- **Version 2** : 13/10/2026. Corrections demandées par la première revue (§ 13). Seules les règles de méthode et de décision changent. Aucun résultat de la période de test (matchs à partir du 13/10, 0 h UTC) n'a été consulté pour écrire cette version.
- **Version 3** : 13/10/2026. Correction ciblée de la règle de décision de B0 (§ 9.2, 9.3, 9.5) et de la méthode d'intervalle (§ 7), demandée par la seconde revue. Rien d'autre ne change. Aucun résultat de la période de test n'a été consulté.
- **Statut** : PROJET, en validation finale. Aucun code n'est écrit avant validation explicite.
- **Périmètre** : couche d'analyse en lecture seule. Elle ne modifie ni V2.6.10, ni V3, ni le Journal, ni les indices existants, ni `main`. La future implémentation reste sur sa branche dédiée et n'écrit que dans `data/base/`.

## 1. Principe

Les moteurs produisent les pronostics. La couche BASE lit l'historique déjà réglé et mesure si une configuration de paris (marché + tranche de cote + au plus un filtre) a été rentable.

Elle affiche toujours séparément :
- la **rentabilité réelle** : ROI calculé avec la cote réelle de chaque pari. **C'est la mesure principale** ;
- le **taux de réussite** ;
- la **moyenne des probabilités implicites brutes** (1 ÷ cote, marge du bookmaker comprise). C'est un repère de lecture, ni un seuil garanti, ni une preuve d'avantage ;
- la **référence** : tous les matchs admis du même marché, de la même tranche et de la même période.

Quand les données sont insuffisantes, le statut est **NON ÉVALUÉ**. Aucune tranche de cote n'est ajustée après coup.

## 2. Hypothèse principale (déclarée en version 1, inchangée)

**H1 — « Moins de 3,5 buts », cote BetPawa entre 1,27 et 1,39 inclus. Configuration correspondante : B0.**

- H1 est la **seule hypothèse de confirmation** de ce protocole. Rien dans les données actuelles ne la montre rentable (§ 10).
- **Période de test** : matchs dont le coup d'envoi est postérieur au 13/10/2026, 0 h 00 UTC (après le commit `92d708a`).
- Les matchs antérieurs servent seulement à décrire l'état de départ (§ 10). Ils ne comptent jamais dans une décision.

## 3. Tranches de cote (fixées en version 1, inchangées)

Les cotes ont deux décimales. Bornes incluses.

| Tranche | Bornes | Rôle |
|---|---|---|
| T-1 | 1,20 – 1,26 | voisine, information seulement |
| **H1-a** | **1,27 – 1,33** | moitié basse de H1, information seulement |
| **H1-b** | **1,34 – 1,39** | moitié haute de H1, information seulement |
| T+1 | 1,40 – 1,46 | voisine, information seulement |

La décision porte sur **H1 entière (1,27 – 1,39)**. Les autres tranches ne reçoivent jamais de statut.

## 4. Données

### 4.1 Source unique : l'archive de test

Fichiers `data/archive_test/AAAA-MM-JJ.json.gz`, produits chaque nuit par le pipeline existant sur `main`. Champs utilisés :

| Champ | Usage |
|---|---|
| `cotes_betpawa.over_under_3.5.moins` | cote du pari |
| `cotes_betpawa.over_under_3.5.plus` | cote opposée, pour mesurer la marge du marché |
| `run.pris_le` | heure du relevé |
| `coup_d_envoi_utc` | heure du match |
| `score.buts_dom`, `score.buts_ext` | résultat |
| `equipe_dom.matchs`, `equipe_ext.matchs` | historiques figés avant le match (B4) |
| `moteur_en_production` | choix de V2.6.10 (B3) |

Le statut du match vient du champ `heure` de `historique_pronostics.json` : `REP` (reporté), `ANL` (annulé), `SUS` (suspendu).

### 4.2 Admission d'un match (avant tout calcul)

Chaque exclusion est comptée et listée match par match.

| Ordre | Condition | Motif |
|---|---|---|
| 1 | Cote « moins de 3,5 » absente | hors univers |
| 2 | `run.pris_le` ou `coup_d_envoi_utc` absent | `HORODATAGE_ABSENT` |
| 3 | `run.pris_le` ≥ `coup_d_envoi_utc` | `RELEVE_APRES_COUP_D_ENVOI` |
| 4 | Donnée incohérente (cote non numérique ou ≤ 1, score mal formé, même match avec deux scores différents) | `ERREUR_COLLECTE` |
| 5 | Empreinte modifiée après la première observation (§ 5) | `MODIFICATION_DETECTEE` |

**Un match = une ligne.** Un même match peut figurer dans plusieurs fichiers journaliers (constat : 3 cas dans H1 avant le test). On garde le relevé admis le plus récent avant le coup d'envoi. Les autres relevés sont listés comme doublons.

### 4.3 Résultats manquants (jamais une perte, jamais une exclusion silencieuse)

| Statut | Condition | Traitement |
|---|---|---|
| `REGLE` | score présent | compté |
| `NON_REGLE` | pas de score, moins de 7 jours après le coup d'envoi | en attente, compté à part |
| `ANNULE` | statut source `REP` ou `ANL` | sorti du calcul, listé |
| `SUSPENDU` | statut source `SUS` | en attente ; réglé si un score apparaît |
| `RESULTAT_MANQUANT` | pas de score, pas de statut source, plus de 7 jours | probable erreur de collecte, listé match par match |

**Limite connue** : le statut source est lu sur la liste Matchendirect au moment de la collecte. Il peut être périmé. Un match marqué `REP` qui reçoit plus tard un score est traité comme `REGLE`.

**Contrôle de sensibilité à chaque point de contrôle** : le ROI est recalculé deux fois, en comptant tous les `NON_REGLE`, `SUSPENDU` et `RESULTAT_MANQUANT` d'abord comme perdus, puis comme gagnés. Si le statut change entre ces deux calculs, le résultat est **NON CONCLUANT (résultats manquants)**.

### 4.4 Conservation des paris perdants

Tout match admis et réglé entre dans les calculs, gagné ou perdu. Aucune ligne n'est retirée après le résultat.

## 5. Traçabilité

### 5.1 Ce qu'on empreinte

Pour chaque match de l'archive, deux empreintes SHA-256, calculées sur le JSON du match trié par clés :
- **avant-match** : tous les champs sauf `score` ;
- **score** : le champ `score` seul.

En plus, l'empreinte SHA-256 de chaque fichier journalier entier est relevée à chaque passage, pour l'audit.

### 5.2 Première observation

L'implémentation ne tourne pas chaque nuit (§ 12). La première observation est donc reconstruite depuis l'**historique Git de `main`**, où le pipeline commite l'archive chaque nuit :
- empreinte avant-match de référence = celle du **premier commit postérieur au coup d'envoi** qui contient le match ;
- empreinte score de référence = celle du **premier commit** où le score apparaît.

Ces empreintes, avec le commit et sa date, sont écrites dans un registre `data/base/empreintes.jsonl`. Le registre est en ajout seul : une ligne n'est jamais modifiée ni supprimée.

### 5.3 Détection

À chaque passage, l'empreinte actuelle de chaque match est comparée au registre :
- avant-match différente après le coup d'envoi, ou score différent après sa première écriture → événement `MODIFICATION_DETECTEE` ajouté au registre ;
- le match est exclu des décisions (§ 4.2) et le point de contrôle concerné est signalé.

### 5.4 Risque résiduel

`main` n'est pas une branche protégée : une réécriture de son historique (push forcé) fausserait la reconstruction. Activer la protection de `main` contre les push forcés réduirait ce risque. C'est une décision du propriétaire, non prise par ce protocole.

## 6. Configurations

### 6.1 Confirmation : B0 seule

| Code | Définition |
|---|---|
| **B0** | H1, tous les matchs admis |

### 6.2 Exploration : B1 à B4

Ces configurations sont **exploratoires**. Elles ne peuvent jamais recevoir le statut VALIDÉ dans ce protocole. Pour être confirmée, une configuration doit être déclarée comme hypothèse principale dans une nouvelle version, puis testée uniquement sur les matchs postérieurs à cette déclaration.

| Code | Filtre | Population admissible A(x) : matchs de B0 où le filtre pouvait répondre oui ou non |
|---|---|---|
| **B1** | V3 a donné à « moins de 3,5 » une probabilité ≥ 1 ÷ cote, calcul antérieur au coup d'envoi (`data/v3/journal/*.json`) | matchs de B0 où V3 a évalué « moins de 3,5 » avant le coup d'envoi |
| **B2** | pari « Match à moins de 3,5 buts » du Journal vu par le générateur avant le coup d'envoi (`data/selection_generateur_historique.json`) | matchs de B0 dont les deux équipes ont au moins 5 matchs antérieurs du même championnat dans la base du Journal (règle d'entrée `MIN_MATCHS_EQUIPE`) |
| **B3** | choix de production V2.6.10 « over_under_total_3.5_under » | matchs de B0 où V2.6.10 a produit au moins un choix de production |
| **B4** | les deux équipes ont au moins 3 matchs au même lieu | matchs de B0 dont les historiques d'équipe sont présents |

**Rapprochement** :
- B1 et B3 : par `match_id`.
- B2 : les paris du Journal n'ont pas de `match_id`. Rapprochement par date + noms normalisés (méthode de `suivi_selection_generateur.py`). Testé sur au moins 3 cas qui doivent correspondre et 3 qui ne doivent pas. Un pari non rapproché est compté `NON_RAPPROCHE`.

**Hors configurations** : les championnats pris un par un (93 dans H1 avant le test, trop peu de matchs chacun) sont affichés à titre descriptif, sans statut.

## 7. Mesures

| Mesure | Définition |
|---|---|
| Matchs | matchs distincts admis et réglés |
| ROI (mesure principale) | (Σ gains − Σ mises) ÷ Σ mises ; mise fixe de 1 ; cote réelle de chaque pari |
| Intervalle du ROI | deux méthodes, toutes deux regroupées par jour de match parce que les matchs d'un même jour ne sont pas indépendants : (1) bootstrap par jour, percentile, 100 000 tirages, graine fixe ; (2) intervalle de Student par grappes (estimateur ratio, erreur type par linéarisation, loi de Student à J − 1 degrés de liberté, J = nombre de jours). Voir § 9.5 pour leur usage et leurs limites |
| Réussite | gagnés ÷ réglés, intervalle de Wilson |
| Probabilité implicite brute moyenne | moyenne de 1 ÷ cote |
| Marge du marché | moyenne de (1 ÷ cote moins + 1 ÷ cote plus − 1), information seulement |

On ne retire jamais la marge pour fabriquer une « vraie probabilité ». Constat avant le test : la marge totale du marché « 3,5 buts » est de 8,4 % en moyenne et elle pèse surtout sur « plus de 3,5 ». Une répartition égale entre les deux côtés sous-estime la réussite réelle de « moins de 3,5 ».

## 8. Comparaisons pour B1 à B4

Chaque configuration exploratoire est comparée deux fois, sur la même période et avec les mêmes jours tirés dans le bootstrap :

| Comparaison | Calcul | Ce qu'elle permet de conclure | Ce qu'elle ne permet pas de conclure |
|---|---|---|---|
| **Générale** | ROI(Bx) − ROI(B0) | Suivre ce filtre aurait-il rapporté plus que parier toute la zone sur la période ? | Si l'écart vient du filtre ou de la population où le filtre s'applique (V3 ne couvre que certains championnats, par exemple) |
| **À population égale** | ROI(Bx) − ROI(A(x) hors Bx) | Parmi les matchs où le filtre pouvait décider, ceux qu'il retient font-ils mieux que ceux qu'il écarte ? C'est le vrai test de la valeur du filtre | Si le filtre resterait utile sur d'autres championnats ou d'autres périodes |

Un filtre qui gagne la comparaison générale mais pas celle à population égale profite de sa population, pas de son jugement.

## 9. Décisions

### 9.1 Seuils de suivi

- **150 matchs réglés et 21 jours de matchs** : seuil minimal pour **afficher** des chiffres. En dessous : NON ÉVALUÉ.
- Ce seuil ne garantit aucune fiabilité. Seuls les intervalles d'incertitude décident.

### 9.2 Points de contrôle de B0 (fixés à l'avance)

- Un point de contrôle ne porte que sur les matchs joués **au moins 7 jours avant** le calcul. Les matchs plus récents, qui n'ont pas encore eu le temps de recevoir leur score, n'y entrent pas.
- **C1** : B0 atteint **300 matchs** admis et réglés **et 20 jours de matchs distincts** dans cette fenêtre.
- **C2** : B0 atteint **600 matchs** admis et réglés **et 40 jours de matchs distincts** dans cette fenêtre.
- Les minimums de jours sont nouveaux en version 3 : les intervalles regroupés par jour ne sont fiables qu'avec assez de jours (§ 9.5).
- Ordre de grandeur : environ 19 matchs admis par jour de match dans H1 d'après l'archive. C1 vers le 10 novembre, C2 vers le 1er décembre (fenêtre de 7 jours comprise). Ce n'est pas une promesse.
- Un statut ne change qu'à un point de contrôle. Les tableaux peuvent être consultés à tout moment, mais s'arrêter au premier bon chiffre fausserait le test.

### 9.3 Statuts de B0 (hypothèse principale)

**Correction de la version 2** : la v2 affirmait qu'avec des intervalles à 99 % aux deux contrôles, le risque global restait au plus de 1 %. Cette garantie n'était pas établie : elle supposait des intervalles à couverture exacte, ce que le bootstrap par jour ne fournit pas avec peu de jours (§ 9.5). La règle est remplacée par la suivante.

**Règle** : à chacun des deux contrôles, intervalles **à 99,5 %** (bilatéraux), calculés par les **deux** méthodes du § 7.
- VALIDÉ exige que les deux bornes basses soient > 0 ;
- DÉFAVORABLE exige que les deux bornes hautes soient < 0.

**Correction du risque global (Bonferroni)** : chaque contrôle admet au plus 0,25 % de risque de VALIDÉ à tort et 0,25 % de DÉFAVORABLE à tort. Sur deux contrôles, la somme de ces risques donne au plus 0,5 % pour un VALIDÉ à tort, et au plus 1 % pour une conclusion fausse dans un sens ou dans l'autre. Cette somme reste valable même si les deux contrôles sont liés (C2 contient les matchs de C1). Elle suppose que chaque intervalle atteint sa couverture annoncée : c'est l'objet du § 9.5.

| Statut | Condition |
|---|---|
| NON ÉVALUÉ | moins de 150 matchs réglés ou moins de 21 jours |
| EN COURS | assez de matchs pour afficher, point de contrôle pas encore atteint |
| NON CONCLUANT | le contrôle de sensibilité (§ 4.3) change la conclusion, ou plus de 5 % des matchs admis de la fenêtre sont sans résultat (`SUSPENDU` ou `RESULTAT_MANQUANT`) |
| DÉFAVORABLE | bornes hautes à 99,5 % < 0 par les deux méthodes |
| NEUTRE | ni DÉFAVORABLE ni VALIDÉ |
| **VALIDÉ** | bornes basses à 99,5 % > 0 par les deux méthodes |

Un statut VALIDÉ n'est pas une garantie. Il redevient NEUTRE si le point de contrôle suivant ne le confirme pas. Il n'existe que deux contrôles : aucun troisième contrôle ne peut être ajouté sans nouvelle version du protocole et nouvelle correction du risque.

### 9.4 Statuts de B1 à B4 (exploration)

- Intervalles affichés à 95 %, sans correction : ils servent à repérer des pistes, pas à décider.
- Statuts possibles : NON ÉVALUÉ, EN COURS, **SIGNAL EXPLORATOIRE** (ROI > 0 et les deux comparaisons du § 8 positives), SANS SIGNAL.
- Un SIGNAL EXPLORATOIRE n'autorise rien : il justifie seulement de déclarer la configuration comme hypothèse principale dans une version suivante.

### 9.5 Méthode d'intervalle : vérification et limites

**Vérification par simulation (13/10/2026, script hors dépôt, à reproduire par l'implémentation)** :
- Hypothèse simulée : ROI réel nul. Chaque pari gagne avec une probabilité de 1 ÷ cote. Les cotes sont tirées dans la distribution réelle de H1 avant le test. Le nombre de matchs par jour suit une loi de Poisson de moyenne 19,5. Les jours sont indépendants.
- Mesure : part des simulations où la règle déclare VALIDÉ à l'un des deux contrôles. Cible : au plus 0,5 %.

| Jours aux contrôles | Bootstrap seul | Student par grappes seul | Les deux (règle retenue) | Simulations |
|---|---|---|---|---|
| 16 et 32 | 1,88 % | 0,85 % | 0,85 % | 6 000 |
| **20 et 40** | 1,45 % | 0,53 % | **0,53 %** | 6 000 |

À titre de comparaison, la règle de la v2 (99 % aux deux contrôles), avec le bootstrap seul, donnait 2,9 % de VALIDÉ à tort pour une garantie annoncée de 1 % (16 et 32 jours, 3 000 simulations).

**Conclusions** :
- Le bootstrap percentile par jour **sous-estime l'incertitude** avec 16 à 40 jours : seul, il ne tient pas la cible. Il est gardé comme seconde condition et pour l'affichage, jamais comme seul critère.
- L'intervalle de Student par grappes tient la cible à 20 et 40 jours (0,53 %, avec une erreur de simulation d'environ ± 0,1 point). D'où les minimums de jours du § 9.2.

**Puissance (même simulation, contrôles à 16 et 32 jours)** : si le ROI réel était de +5 %, la règle conclurait VALIDÉ dans environ 30 % des cas ; à +3 %, dans environ 8 %. Un avantage réel modeste a donc de grandes chances de rester NEUTRE. **NEUTRE ne veut pas dire « pas d'avantage »**, seulement « avantage non démontré ».

**Limites qui restent** :
- Les jours sont supposés indépendants. Une dépendance d'une semaine à l'autre (même championnat, même tendance) rendrait les intervalles trop étroits.
- La simulation suppose un ROI réel constant dans le temps.
- Les intervalles de Student reposent sur une approximation normale. Elle est raisonnable ici parce que le gain d'un pari est borné (entre −1 et +0,39 dans H1), mais elle n'est pas exacte.
- L'erreur de simulation (environ ± 0,1 point à 0,5 %) ne permet pas d'affirmer que le risque est strictement sous 0,5 %. Elle permet d'affirmer qu'il en est proche.

## 10. État de départ reproduit depuis les archives (description seulement)

Reproduction faite le 13/10/2026 avec les règles des § 4 et 7, sur les matchs de l'archive de test dont le coup d'envoi est antérieur au 13/10 0 h UTC. Le script de reproduction est hors dépôt. **L'implémentation devra refaire ce calcul avec ses propres tests et retrouver ces chiffres, ou expliquer tout écart.**

### 10.1 Admission dans H1 (avant le test)

| Catégorie | Matchs |
|---|---|
| Admis et réglés | 253 (après retrait de 3 doublons) |
| `NON_REGLE` (moins de 7 jours) | 38 |
| `RESULTAT_MANQUANT` | 2 |
| `RELEVE_APRES_COUP_D_ENVOI` | 11 |
| `HORODATAGE_ABSENT` | 7 |

### 10.2 Résultats

| Ensemble | Matchs | Jours | Réussite (95 %) | Proba implicite brute | ROI (95 %, bootstrap par jour) |
|---|---|---|---|---|---|
| **B0** | 253 | 13 | 74,3 % (68,6 – 79,3) | 75,5 % | −1,5 % (−5,6 ; +2,3) |
| H1-a | 149 | 10 | 73,8 % | 77,0 % | −4,0 % |
| H1-b | 104 | 11 | 75,0 % | 73,4 % | +2,2 % |
| B4 | 175 | 13 | 76,6 % | 75,5 % | +1,7 % |
| A(B4) hors B4 | 78 | 9 | 69,2 % | 75,6 % | −8,5 % |
| B1 | 15 | 5 | 80,0 % | 75,3 % | +6,7 % |
| A(B1) hors B1 | 3 | 3 | — | — | — |
| B2 | 13 | 3 | 92,3 % | 75,8 % | +21,5 % |
| B3 | 14 | 6 | 71,4 % | 75,2 % | −4,7 % |

Avec 3 à 15 matchs et 3 à 6 jours, B1, B2 et B3 sont trop petits pour en tirer quoi que ce soit. B2 couvre 3 jours seulement : son intervalle par bootstrap n'a pas de sens.

### 10.3 Écarts avec les chiffres de l'audit du 12/10

| Élément | Audit | Reproduction | Cause de l'écart |
|---|---|---|---|
| Matchs dans H1 | 269 | 253 | l'audit n'appliquait ni les exclusions d'horodatage (18 matchs) ni le retrait des doublons (3) ; il comptait aussi les matchs selon la date du fichier et non selon le coup d'envoi |
| Réussite | 74,7 % | 74,3 % | conséquence des exclusions |
| Repère de cote | « seuil » 75,6 % | proba implicite brute 75,5 % | même quantité, terme corrigé |
| ROI | −1,0 % | −1,5 % | conséquence des exclusions |
| Marge | ≈ 5,8 % | 8,4 % | grandeurs différentes : l'audit mesurait la part de marge du côté « moins », la reproduction mesure la marge totale du marché |
| Volume mensuel | « environ 170 » (réponse du 12/10) | environ 550 à 600 | erreur de l'audit, déjà signalée en version 1 |

## 11. SUPER BASE

### 11.1 Ce que mesurent les indices existants (constat du 12/10)

- **Indice x/4** (`moteur_v3/performance.py`) : test sur la moyenne et le pire match de chaque équipe, au même lieu.
  - Définition modifiée le 10/10 (v3) puis le 12/10 (v4). L'archive des indices mélange les deux versions, et 625 lignes sur 1 027 y ont été calculées après coup.
  - Recalculé en v4 sur 845 matchs de l'archive de test, dans H1 : 4/4 = 72,1 % de réussite (43 matchs), 0/4 = 77,8 % (27 matchs).
  - Toutes cotes confondues : les 4/4 réussissent à 70,8 %, et la cote, marge retirée, prévoyait 70,6 %. Il reproduit l'information de la cote.
- **Niveau d'échantillon V3** : nombre de matchs au même lieu. Repris dans B4.
- **Niveaux PROUVE / ÉTABLI** (`selection_adaptative.py`) : ils dépendent de l'archive V3, jamais réglée à ce jour (§ 12).
- **`calibrage_externe.py`** : ses règles sont validées sur les données qui les ont fait découvrir. Il n'est pas utilisé.

Ces constats seront reproduits par l'implémentation avant tout usage, comme au § 10.

### 11.2 Règle d'entrée d'un indice

Aucun indice n'est un critère SUPER BASE au départ. Un indice ne peut le devenir que si toutes ces conditions sont remplies :
1. Sa version est figée et déclarée dans une nouvelle version de ce protocole, avant le test.
2. Il est calculable avant le match pour tous les matchs de la BASE parente, pas seulement pour les sélections.
3. Sa BASE parente est VALIDÉE.
4. Sur les matchs postérieurs à sa déclaration, le sous-ensemble filtré par l'indice bat sa BASE parente **à population égale** (§ 8) : écart de ROI positif selon la règle du § 9.3 (deux méthodes, 99,5 %, au plus deux contrôles fixés à l'avance avec minimums de jours).

Tant que ces conditions ne sont pas remplies, l'indice reste affiché comme information, avec le statut NON ÉVALUÉ.

## 12. Mise en œuvre (après validation explicite de ce document)

**PR 45 : non nécessaire.**
- La BASE règle elle-même les paris V3 depuis `data/v3/journal/*.json` et les scores, en lecture seule.
- Effets mesurés de la PR 45 : 74 paris V3 réglés au lieu de 0, mais 11 candidats sur 23 changent de source de probabilité (exemple : 0,9055 devient 0,417 ; gain espéré de +0,28 à −0,41), ces candidats montent pourtant dans le classement, et le top 15 change de 3 paris.
- Elle reste une décision séparée.

**Implémentation** :
- Branche dédiée, jamais fusionnée sans décision explicite.
- Module `base_protocole.py` en lecture seule. Il écrit uniquement dans `data/base/` sur cette branche.
- **Tests dédiés** :
  - chaque motif d'exclusion du § 4.2 ;
  - chaque statut de résultat du § 4.3, dont : un résultat absent n'est jamais compté perdu ;
  - le retrait des doublons ;
  - le rapprochement du Journal : 3 cas qui doivent correspondre, 3 qui ne doivent pas ;
  - le registre d'empreintes : ajout seul, et détection d'une modification ;
  - un statut ne change qu'à un point de contrôle ;
  - le contrôle de sensibilité ;
  - la reproduction des chiffres du § 10 ;
  - la simulation du § 9.5 (même tableau, à l'erreur de simulation près).
- **Pas de workflow programmé** : GitHub ne lance les tâches programmées que depuis la branche principale, et cette branche ne doit pas changer. Le calcul est relancé à la demande ; la traçabilité repose sur l'historique Git (§ 5).
- **Aucune page du site** avant le point de contrôle C1.

## 13. Corrections apportées en version 2

| Point de la revue | Correction | Section |
|---|---|---|
| 1. Terme « seuil de rentabilité » | remplacé par « moyenne des probabilités implicites brutes » ; ROI réel = mesure principale | § 1, 7, 10 |
| 2. Comparaison à population égale | deux comparaisons pour B1 à B4, avec ce que chacune permet de conclure | § 6.2, 8 |
| 3. Tests multiples | B0 seule hypothèse de confirmation ; B1 à B4 exploratoires, sans statut VALIDÉ possible | § 2, 6, 9 |
| 4. Traçabilité | empreintes par match dès la première observation, registre en ajout seul, détection et exclusion | § 5 |
| 5. Seuil de 150 matchs | seuil d'affichage seulement ; décision par les intervalles | § 9.1 |
| 6. Résultats manquants | 5 statuts distincts, aucune perte par défaut, contrôle de sensibilité | § 4.3 |
| 7. Reproduction des chiffres | refaite depuis les archives, écarts documentés | § 10 |

### Correction apportée en version 3

| Point de la revue | Correction | Section |
|---|---|---|
| Risque global faux en v2 | 99,5 % à chaque contrôle, Bonferroni explicite, deux méthodes d'intervalle exigées, minimums de 20 et 40 jours, vérification par simulation et limites | § 7, 9.2, 9.3, 9.5, 11.2 |

## 14. Ce que ce protocole ne permet pas d'affirmer

- Que les cotes relevées étaient disponibles au moment de parier : relevé médian 8,6 h avant le match, pas de cote de clôture.
- Qu'un résultat sur BetPawa se transpose à un autre bookmaker.
- Qu'un statut VALIDÉ restera vrai : un marché peut s'ajuster.
