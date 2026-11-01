# Conception : référentiel canonique, historique permanent, contrôles (v3, 01/11/2026)

**Étude de conception. Aucun code. Rien n'est fusionné.** Fiches gelées, bilans historiques et autres moteurs : non touchés. L'architecture finale doit être validée par Patrick avant toute implémentation.

Cette version v3 remplace la v2. Elle intègre les cinq décisions du 01/11 et les **trois corrections demandées le 01/11 après la v2** : A (cohérence P1/P2, §3), B (unicité des identifiants, §2.5), C (fiabilité de l'ingestion, §4.5 ; lien Football-Data ↔ Matchendirect = candidats puis vérification, §4.3). **L'implémentation de l'historique permanent attend la validation explicite de Patrick.**

## 0. Décisions de Patrick intégrées

| # | Décision | Où |
|---|---|---|
| 1 | Identifiants internes permanents pour clubs, compétitions, saisons ; Matchendirect et Football-Data = identifiants externes ; versions successives, brut jamais écrasé | §2, §4 |
| 2 | Étudier pages d'équipes ET résultats quotidiens ; aucun nouveau scraping avant comparaison | §5 |
| 3 | Rattachement par identifiant de match autorisé, traçable, réversible ; Sport Boys 2 / 2 Melgar récupérables | §3 |
| 4 | América Cali : correction par nouvelle version, original conservé | §7 |
| 5 | Six paris conservés ; trois informations distinctes (résultat, règle de l'époque, règle actuelle) ; 18/29 conservé, 12/23 = comparaison analytique | §9 |
| 6 | Hiérarchie compétition → édition (saison) → phase → matchs validée ; saison en deux temps (provisoire / confirmée / indéterminée) | §2.3, §2.4 |
| 7 | Collecte parallèle (7 à 14 jours), rejeu Omega/Alpha, correction de `_memes_equipes` : autorisés sur espaces et branches isolés, sous conditions | §5, §8.2, §13 |
| 8 | Corrections A, B, C de la v2 | §3, §2.5, §4.5 |

## 1. Principes

1. **Ajout seul.** Rien n'est modifié ni supprimé ; un changement est une nouvelle version qui référence la précédente.
2. **Le brut est intouchable.** Ce que la source a dit est conservé tel quel ; l'interprétation (identités, corrections) est une couche séparée.
3. **Idempotent.** Rejouer un run n'ajoute rien.
4. **Réversible.** L'état courant est le rejeu du journal des décisions ; annuler une décision, c'est ajouter une ligne d'annulation.
5. **Indépendant du cache des cotes.** Aucune purge du cache BetPawa ne peut toucher l'historique.
6. **Preuve avant fusion.** Hiérarchie des preuves (§3). Ressemblance de nom, de score ou de date : jamais une preuve.
7. **Chaque probabilité remonte à ses données.** Une fiche gelée porte la version d'historique utilisée.

## 2. Référentiel canonique

### 2.1 Identifiants
- **Interne** : opaque (`clb_000123`, `cmp_0045`, `sai_0045_2026`), attribué à la création, **jamais dérivé d'un nom, jamais réutilisé**, même après annulation.
- **Externes** : table `identifiants_externes` : `source` (matchendirect, football-data, …), `type` (club, compétition, match), `valeur` conservée sans transformation, `id_interne`, `preuve`, `version_regle`, `decide_le`, `statut` (actif / annulé), `remplace`.
- Un club peut avoir plusieurs identifiants externes actifs par source (changement d'identifiant) : le club interne ne change pas.

### 2.2 Clubs
- **Création** : au premier identifiant de club stable rencontré (identifiant Matchendirect de l'adresse d'équipe), un club interne est créé.
- **Rattachement d'un nom (alias) ou d'un identifiant d'une autre source** : uniquement par preuve (§3). Sans preuve : le nom reste « non résolu », conservé, exclu des statistiques de club.
- **Changement de source** : si Matchendirect change un identifiant, on ajoute le nouvel identifiant externe au même club, prouvé par un match commun. Si une source disparaît, ses identifiants passent à `inactif` ; l'historique et le club restent.
- **Fusion erronée** : une fusion est une ligne `fusion(a, b, preuve, version_regle, decide_le)`. L'annuler = ligne `annulation(fusion_id, raison, decide_le)`. L'état courant se recalcule ; les statistiques se recalculent « à la date X ». Rien n'est perdu, chaque fusion est auditable.

### 2.3 Compétitions
- Identifiant interne permanent ; noms externes multiples (nom Matchendirect, code Football-Data).
- **Constat** : une même compétition change de nom selon la phase (Ouverture/Clôture, Tour de championnat, Quadrangular) et les noms Matchendirect ne sont pas stables. On distingue donc **compétition** (permanente) → **édition** (saison) → **phase** (libellé externe).

### 2.4 Saisons (règle validée en deux temps)
- `saison_id` est lié à une compétition ; il porte début, fin, **état** et **source de la définition**.
- États : `confirmée` · `provisoire` · `indéterminée`.
  - **Football-Data** : `confirmée` par le code de saison de la source.
  - **Sans Football-Data** : les dates observées ne donnent qu'une période **`provisoire`** (période observée, pas limites décrétées). Elle devient `confirmée` seulement si (a) une source explicite établit les limites et les phases, ou (b) une validation documentée (qui, quand, preuve) est inscrite au référentiel.
  - **Incertaine** : `indéterminée`. Le match est conservé, **exclu des statistiques saisonnières**.
- **Aucune hypothèse de calendrier commun** (championnats d'été : Norvège, Suède, Japon, Amérique).
- **Interdit** : fusionner deux éditions parce que leurs dates se chevauchent. Une fusion d'éditions n'existe que comme décision documentée, réversible (§2.5).
- **Règle fixée par Patrick (01/11, 17:33)** : `confirmée` = statistiques normales ; `provisoire` = **compartiment distinct**, avec avertissement visible et possibilité d'exclusion ; `indéterminée` = exclue de toute statistique saisonnière. Une saison provisoire n'est jamais présentée comme confirmée ni mélangée silencieusement à une saison confirmée (les moteurs doivent exposer deux totaux séparés et l'état dans la fiche).

### 2.5 Contraintes d'unicité, changements d'identifiants, fusions et annulations (correction B)
| # | Contrainte |
|---|---|
| U1 | Un identifiant externe `(source, type, valeur)` désigne **au plus un** objet interne actif (club, compétition ou match). Toute écriture qui créerait un deuxième est refusée et journalisée. |
| U2 | Un club (ou une compétition) peut avoir plusieurs identifiants externes actifs pour une même source **seulement** par une ligne `changement_identifiant` avec preuve (match commun) et période de validité. Sans cette ligne : refus. |
| U3 | Un match n'a jamais deux identités internes actives pour la même `(source, identifiant du match)`. Deux créations simultanées : la seconde est refusée par la contrainte, pas par l'ordre d'arrivée. |
| U4 | Une fusion de clubs ne peut pas créer de cycle ni lier un club à deux cibles actives différentes. Une chaîne A→B→C est autorisée. |
| U5 | Les lignes d'identifiants ne sont **jamais modifiées**. Une fin de validité est une nouvelle ligne (`valide_du`, `valide_au`, statut `inactif` ou `annulé`). L'historique complet d'un identifiant est donc toujours reconstructible. |
| U6 | Le journal des fusions et annulations est **ordonné par numéro de séquence** strictement croissant (pas par l'horloge). L'état « à la date X » ou « au numéro N » est le rejeu des lignes jusqu'à X ou N. Rejouer deux fois donne le **même état** (même empreinte d'état) : ce test est obligatoire. |
| U7 | Une annulation ne vise qu'une fusion active. Une nouvelle fusion après annulation exige une **nouvelle preuve** et une nouvelle ligne ; l'ancienne reste visible. |
| U8 | Une preuve contradictoire (deux clubs prouvés pour un même alias, ou P1 et P2 en désaccord) empêche toute fusion automatique : ligne `conflit`, aucun rattachement. |

## 3. Preuves, rattachement, traçabilité (correction A : P1 et P2 harmonisées)

| Rang | Preuve | Définition | Statut |
|---|---|---|---|
| P1 | Identifiant de match | Le même identifiant de match d'une source figure dans les observations des deux équipes, **et** chacun des deux clubs est identifié par son identifiant de club (pas par un alias non prouvé) | prioritaire |
| P2 | Nommage croisé | Le bloc de l'autre équipe nomme la nôtre, même date, score inverse ; les deux observations sont citées et vérifiables | **seulement en l'absence de P1** |
| — | Nom ressemblant, score ressemblant, proximité de date | | **jamais suffisant** |
| — | Contradiction | | `conflit`, aucune fusion automatique (U8) |

**Règle de décision, dans cet ordre**
1. Chercher P1. Si elle existe et ne contredit rien : rattachement, `preuve.type = P1`.
2. Sans P1 : P2 est acceptée si (a) ses deux observations sont vérifiables, (b) **aucun autre club** ne satisfait aussi P2 pour le même alias, (c) aucune preuve contradictoire n'existe (P1 vers un autre club, observation incompatible). `preuve.type = P2`.
3. P1 et P2 en désaccord, ou deux clubs candidats : `conflit`, **aucun rattachement**.
4. Aucune preuve : « non résolu », exclu des statistiques de club.

Chaque rattachement écrit : identifiants concernés, source, **type de preuve réellement utilisé**, références des observations, `decide_le`, `version_regle`, statut.

**L'audit** (`audit_identites.py`, outil existant) doit, pour chaque rattachement : relire **la preuve annoncée** (P1 ou P2) et la revérifier ; chercher toute preuve contradictoire ; classer en `confirmé P1`, `confirmé P2`, `invalide`, `contredit`. Il n'exige pas P1 pour un rattachement fondé sur P2 valide. *État actuel : l'outil ne vérifie que P1. Il reste exact pour les 21 alias du chargeur strict (tous confirmés P1) ; son adaptation à P2 fait partie de l'implémentation, non faite ici.*

**Récupération de Sport Boys 2 / 2 Melgar** : le match du 15/04/2026 (3-1) porte le même identifiant dans les deux blocs ; chaque bloc l'écrit avec un alias en « 2 » (pas de nommage croisé, donc P2 échoue). P1 s'applique si les deux identités (Sport Boys, Melgar) sont chacune vérifiées par leur identifiant de club (c'est le cas : les deux ont leur adresse d'équipe). Mesuré : 2 alias sur 23 prouvés par P1 que le chargeur strict ne rattache pas.

**Mesure sur l'assemblage du 01/11** : 1 509 matchs vus par les deux équipes ; 23 alias prouvés par P1 ; le chargeur strict en rattache 21, tous confirmés ; l'ancien en rattachait 110 de plus sans preuve P1.

## 4. Historique permanent : contrat de données

### 4.1 Trois couches
1. **Brut** (immuable) : enregistrement exact de la source, avec `source`, `run_id`, `collecte_le`, `hash`. Un fichier par run, jamais réécrit.
2. **Observations** : une ligne par (match, source, observation), qui référence le brut. Exemple : les deux vues d'un même match (équipe A, équipe B) sont deux observations.
3. **Matchs consolidés** (versionnés) : voir 4.2.

### 4.2 Enregistrement de match consolidé
| Champ | Contenu |
|---|---|
| `match_id` | identifiant interne permanent (créé à la première observation) |
| `version` | 1, 2, … ; `remplace` = version précédente ; `raison` ; `cree_par` = version de règle + run |
| `competition_id`, `saison_id` | internes (§2) |
| `domicile_id`, `exterieur_id` | internes ; `null` si non résolu |
| `date` | date du match ; `heure_utc` si connue |
| `ids_externes` | liste : source, type=match, valeur sans transformation, adresse |
| `score_final`, `score_mi_temps` | `null` si inconnu, jamais 0 par défaut |
| `statut_sportif` | terminé / reporté / annulé / abandonné |
| `statut_validation` | `source_unique` · `confirmé` · `conflit` · `corrigé` · `quarantaine` |
| `observations` | références vers la couche 2 |

### 4.3 Clés et dédoublonnage
- Clé externe d'un match : `(source, identifiant du match de la source)`. Le même match vu des deux équipes se fusionne par cette clé.
- **Football-Data ↔ Matchendirect : candidats, puis vérification (jamais une fusion directe).**
  - *Recherche de candidats* : `(date ± 1 jour, domicile_id, exterieur_id)` ne sert qu'à **proposer** des candidats.
  - *Vérification exigée avant tout lien* : (a) scores finaux identiques (et mi-temps identiques quand les deux sources en ont), (b) le candidat est **unique des deux côtés**, (c) orientation identique (domicile/extérieur non inversés), (d) aucune autre observation du même couple de clubs dans la fenêtre de recherche.
  - *Limite assumée* : Football-Data et Matchendirect n'ont **aucun identifiant commun**. Le score n'est pas un identifiant ; un lien vérifié a un niveau de preuve inférieur à P1, il porte le statut **`verifie_inter_sources`** (distinct de P1 et de P2), enregistré avec : les deux identifiants externes, les observations brutes des deux sources, la méthode de rapprochement et sa **version**. Il est **révocable sans supprimer aucune observation d'origine**. Une égalité de score et une correspondance unique ne prouvent pas toujours le même événement (match rejoué, correction tardive) : au moindre doute, le lien reste **en attente de vérification**.
  - *Reporté* (écart de date > 1 jour, date absente) : candidats non vérifiés ; les deux observations restent séparées, aucun lien. *Inversé* (domicile et extérieur échangés entre sources) : `conflit`, jamais lié. *Rejoué* (même couple de clubs deux fois dans la fenêtre : reprise, match rejoué après abandon) : deux candidats ou plus ⇒ aucun lien automatique ; la version abandonnée garde son statut `abandonné`, la nouvelle est un autre match (autre identifiant de source).
  - *Pas de double comptage* : tant qu'aucun lien n'est vérifié, dans une compétition couverte par Football-Data, c'est Football-Data qui fait foi pour les statistiques ; l'observation Matchendirect non liée est conservée mais exclue.
- Deux observations du même identifiant de match doivent être **miroirs** (domicile opposé, buts échangés, même date). Sinon : `conflit` (§7).

### 4.4 Versionnement
- Une source qui change un score ou une date sur un même identifiant crée une nouvelle version ; l'ancienne reste, marquée `remplacée`.
- La purge du cache J0–J+3 ne lit ni n'écrit cette couche.

### 4.5 Fiabilité de l'ingestion (correction C)
**Unité de travail : le lot** `(source, jour)`.

| Risque | Garantie |
|---|---|
| Exécutions concurrentes | Un seul écrivain à la fois : verrou exclusif par espace de stockage (identifiant du run, début, durée de bail). Un verrou périmé n'est repris qu'après constat que son propriétaire n'est plus actif, et la reprise est écrite. Les workflows d'écriture partagent un groupe de concurrence (comme `pipeline-archetype-foot` aujourd'hui) ; la collecte parallèle a son propre groupe. Les lecteurs ne lisent **que** les lots publiés. |
| Écriture incomplète | Le lot s'écrit dans `en_cours/<run_id>/`. Un fichier `MANIFEST` est écrit **en dernier** : liste des fichiers, taille, sha256 de chacun, nombre d'observations, hash du lot, version de règle, hash du MANIFEST du lot précédent. Publication = renommage atomique vers `lots/<source>/<jour>/<run_id>/`. **Un lot sans MANIFEST valide n'existe pas.** |
| Interruption | Rien de visible n'a changé tant que le renommage n'a pas eu lieu. Les dossiers `en_cours` périmés sont nettoyés sans effet sur les lots publiés. |
| Reprise | On recommence le lot. Pas de point de reprise à croire sur parole : l'index des observations déjà ingérées est **reconstruit depuis les lots publiés** (vérité) ; `etat_ingestion` n'en est qu'un cache, reconstruit s'il est absent ou incohérent. |
| Double ingestion | Clé d'observation = `(source, identifiant source, sha256 du brut normalisé)`. L'ingestion est une **union par clé** : une clé déjà présente n'est pas ajoutée (le MANIFEST compte les observations ignorées). Rejouer un lot, avant ou après une reprise, ne change pas l'état. |
| Empreintes | Au démarrage et avant toute consolidation : recalcul du sha256 de chaque fichier de chaque lot et vérification de la chaîne de MANIFEST. Un écart **bloque** ; jamais de correction silencieuse. |
| Dépôt Git | Les lots publiés entrent dans un seul commit ; un push refusé est rejoué sans doublon (mêmes clés). |

**Test d'acceptation obligatoire** : interrompre le processus à chaque étape (points d'arrêt avant et après chaque écriture, avant et après le renommage), reprendre, puis comparer l'empreinte de l'état final à celle d'une exécution sans interruption : elle doit être identique. Idem pour deux exécutions simultanées.

## 5. Alimentation : comparaison des deux méthodes (mesures du 01/11, sans nouveau scraping)

| Critère | A. Pages d'équipes (déjà scrapées) | B. Résultats quotidiens Matchendirect |
|---|---|---|
| Couverture des compétitions | **133** compétitions dans l'assemblage ; **61 %** des clubs des 38 divisions Football-Data (407 sur 672) ; 5 divisions sans aucun club (IRL, CHN, RUS, SC2, SC3), 3 divisions complètes | **286** compétitions sur la page d'un jour (1 049 matchs le 01/11) contre 151 pour les seules matchs cotés |
| Dépend des cotes BetPawa | **Oui** : seules les équipes d'un match coté dans J0–J+3 | **Non** : tous les matchs de la page |
| Identifiant de match | Oui (100 % des 6 335 enregistrements Matchendirect) | Oui (`match_id` sur chaque ligne) ; **même espace d'identifiants** (le `match_id` d'archive = l'identifiant de `url_match`) |
| Identifiant de club | **Oui** (adresse d'équipe) | **Non** : la page ne donne que des noms de clubs → il faut un mapping nom → club, donc le risque d'alias déjà vu |
| Historique par club | Saison complète d'un coup (≈ 11 matchs par équipe) | Un jour à la fois ; l'historique se construit dans le temps, ou par remontée des jours passés |
| Doublons | Chaque match vu 2 fois (une par équipe) ; dédoublonné par identifiant | Chaque match vu 1 fois |
| Reports, corrections | Voient les corrections au prochain scraping de l'équipe | **Non mesuré** (nécessite plusieurs jours de collecte) |
| Coût | Déjà payé (scraping existant) | Déjà payé pour les cotés (page du jour) ; remontée du passé = nouveau scraping |
| Lien avec les matchs à pronostiquer | Direct (mêmes équipes) | Indirect (par nom) |

**Ce que les mesures disent**
- A donne les identifiants de clubs mais hérite de la couverture des cotes : insuffisant seul pour un historique de championnats.
- B donne la couverture et l'identifiant de match, mais pas d'identifiant de club : insuffisant seul pour l'identité.
- Les deux sont complémentaires : B pour la couverture sportive, A (ou les pages d'équipe) pour fournir l'identifiant de club qui prouve le nom. Le mapping nom → club de B se prouve par P1 contre les blocs de A.

**Ce que je n'ai pas pu mesurer** (la page quotidienne locale date du matin du 01/11 : seulement 18 matchs avec score) : la part de matchs terminés avec score final à J+1, le taux de noms de clubs non résolus, les reports et corrections.

### Collecte parallèle : autorisée le 01/11 (7 à 14 jours)
**Conditions de Patrick** : stockage séparé du pipeline ; aucune modification de `data/assemblage/equipes.json` ; aucune incidence sur Gamma, Alpha, Omega ; conservation des réponses brutes, identifiants, dates de collecte et empreintes ; aucune fusion d'identités à partir des seuls noms.

**Mesures** (une ligne par jour de collecte et par compétition) :
1. *Scores à J+1* : part des matchs de la page du jour J qui ont un score final à J+1, J+2, J+7.
2. *Reports* : matchs dont la date change, qui disparaissent ou réapparaissent d'une collecte à l'autre.
3. *Corrections* : même identifiant de match dont le score, la date ou les équipes changent entre deux collectes.
4. *Noms non résolus* : noms de clubs de la page qui ne se rattachent à aucun identifiant de club par P1 ou P2 (jamais par nom).
5. *Couverture* : compétitions et matchs par jour, comparés à ceux de la méthode A pour les mêmes jours.

**Livrable à la fin** : tableau comparatif A / B **chiffré** (pas une conclusion générale de complémentarité), avec la période, le nombre de jours, de compétitions et de matchs.

**Mise en œuvre** : voir §14 (contrainte : un déclenchement planifié ne tourne que depuis la branche par défaut).

## 6. Contrôles : quatre familles, chacune identifie la donnée fautive et sa provenance

Chaque anomalie est écrite : `famille`, `invariant`, `competition_id`, `match_id` / `club_id`, identifiants externes, `source`, `run_id`, `brut` (référence), `premiere_observation`.

| Famille | Invariant | Exemple mesuré | Action |
|---|---|---|---|
| **Erreur de source** | I-S1 aucun match d'une équipe contre elle-même | 27 auto-références brutes dans 22 blocs figés de l'archive (76 044 matchs, 0,04 %) | quarantaine de l'observation, exclue des statistiques, signalée à la première observation |
| | I-S2 **miroir** : deux observations du même identifiant de match sont symétriques | 1 cas (América Cali, 26/04) au 01/11 ; 3 cas au 31/10 (Cerro, Cerro Largo, Comerciantes/Melgar) sur 1 509 et 2 469 matchs vus des deux côtés | `conflit` ; correction par nouvelle version si P1 le permet (§7) |
| **Erreur d'identité** | I-I1 tout rattachement est prouvé par P1 (ou P2 à défaut) ; I-I2 aucun club ne fusionne avec un autre club du référentiel ; I-I3 un alias n'est rattaché qu'à un seul club | audit du 01/11 : 21/21 prouvés, 0 contredit ; ancien chargeur : 110 sans preuve | blocage |
| **Perte de couverture** | I-C1 monotonie : un match terminé présent à la version précédente est encore présent, ou remplacé/quarantaine avec raison ; I-C2 un championnat attendu n'est pas vide s'il avait des matchs | 22 matchs disparus et 11 championnats à zéro entre deux versions de l'assemblage ; 9,9 % des blocs lus par Omega/Alpha (646 sur 6 530) ont perdu au moins un match antérieur | rapport tant que l'historique permanent n'existe pas ; blocage ensuite |
| **Défaut du chargeur** | I-D1 après chargement : zéro auto-rencontre, zéro doublon, identités conservées, aucun match d'une équipe attribué à une autre | 79 auto-rencontres fabriquées avant le correctif, 0 après | blocage |

- Les contrôles I-C comparent des **ensembles d'identifiants**, pas des pourcentages : aucun seuil arbitraire.
- Le statut `quarantaine` est une propriété de l'observation (avec sa preuve et sa date), pas une exception codée. Une observation en quarantaine déjà signalée ne bloque plus le run suivant ; une nouvelle l'est une fois.
- **Compromis** : bloquer sur I-C1/I-C2 aujourd'hui bloquerait souvent (le cache tourne). Ils ne deviennent bloquants qu'après la mise en place de l'historique permanent.

## 7. Corrections de source : cas América Cali

Constat sur l'enregistrement du 26/04/2026 (identifiant `5y67q7a7…`, `cali-america-cali`) :
- Le bloc d'América Cali contient le match **à l'envers** : domicile = vrai, adversaire = « America Cali » (elle-même), 1-0. C'est la copie exacte de l'enregistrement du bloc de Cali (domicile, 1-0).
- Ce n'est pas une simple erreur de nom : l'**orientation et le score** sont ceux du point de vue de Cali. Le match réel est Cali – América Cali 1-0 ; du point de vue d'América Cali : à l'extérieur, 0-1.
- **Cause démontrée** : `scraper_details._memes_equipes` accepte « un nom contient l'autre » ; sur la page d'América Cali, « Cali » est pris pour l'équipe de la page. Même mécanisme pour Cerro / Cerro Largo (29/05 et 16/10). *Ce fichier est protégé : je ne le modifie pas ; correction à décider.*

Procédure proposée (aucune modification silencieuse) :
1. Garder l'observation brute erronée (couche 1, hash).
2. Créer la version corrigée du match : domicile = Cali, extérieur = América Cali, 1-0, `statut_validation = corrigé`, `raison` = « observation d'América Cali au miroir de celle de Cali ; identifiant du match `5y67q7a7…` » ; ancienne et nouvelle identité documentées.
3. Vérifier qu'aucun doublon n'est créé : le match corrigé a une seule clé `(matchendirect, 5y67q7a7…)` ; l'observation de Cali est déjà la bonne.
4. La quarantaine n'est pas définitive : tout cas corrigeable par P1 est corrigé ; sinon l'observation reste en quarantaine avec sa raison.

## 8. Compatibilité des moteurs

### 8.1 Gamma
- Aujourd'hui : `moteur_dc/donnees.py` reconstruit les championnats et les identités depuis `data/assemblage/equipes.json`. Il est la seule des trois lectures qui dépend d'identités reconstruites (union-find).
- Avec l'historique : plus de reconstruction d'identité pour les enregistrements Matchendirect (identifiants fournis). Les effectifs et buts attendus **changent** (plus de matchs, vrais adversaires) : les fiches futures diffèrent de celles d'aujourd'hui. Rejeu avant/après obligatoire ; chaque fiche porte la version d'historique.
- Audit d'impact du correctif : `docs/AUDIT_PRONOSTICS_GELES.md` (51 matchs inchangés sur 68, 15 affectés, médiane 0,9 point).

### 8.2 Omega et Alpha série : audit de lecture seule de leurs chargeurs
**Constat** : ni Omega (`moteur_omega/donnees.py`) ni Alpha (`alpha_serie/suivi.py`, `solidite.py`, `calibration.py`, `robustesse.py`) ne reconstruisent d'identités. Ils lisent, pour chaque match de l'archive, les blocs d'équipe **figés dans l'archive** (`assemblage.equipe_dom` / `equipe_ext`), match par match, à partir de la liste de matchs propre à chaque équipe. Ils n'utilisent le nom de l'adversaire que pour l'affichage. Le correctif du chargeur Gamma ne les concerne donc pas, et **ils n'étaient pas exposés aux fausses identités fabriquées**.

**Mais ils sont exposés à autre chose** (mesures sur les 38 fichiers d'archive, 6 903 blocs distincts, 76 044 matchs) :
- 27 auto-références brutes dans 22 blocs (les erreurs de source, §6) : leur score est celui d'un vrai match mal orienté dans le cas démontré (América Cali : score 1-0 du point de vue de Cali) ; ils entrent dans la série de l'équipe fautive à l'envers.
- **Historiques tronqués, figés dans l'archive** : 646 blocs sur 6 530 lus (9,9 %) ont perdu au moins un match antérieur (clé = date, lieu, score ; médiane 2 matchs, maximum 27) que contient une autre version de l'assemblage. Cette perte est **permanente** dans les entrées archivées (la version figée à l'époque est celle que lisent les moteurs). Mesure approximative : un même match dont la date a bougé de ± 1 jour compterait comme perte.
- Pas de doublon exact dans un bloc (0 sur 76 044).
- Alpha lit aussi le bloc de l'adversaire à l'extérieur, toujours depuis son propre bloc.

**Rejeu d'impact d'Omega et d'Alpha : autorisé le 01/11. Protocole** (même rigueur que pour Gamma) :
- Fiches gelées, journaux, cotes historiques : **lecture seule** ; tout est rejoué à côté.
- Trois lectures comparées : (1) **blocs originaux** figés dans l'archive (reproduction de la fiche gelée) ; (2) **meilleur historique reconstituable** (union des versions d'un même bloc, matchs identifiés sans nom) ; (3) blocs sans auto-références.
- Les deux effets sont **mesurés séparément** : historiques tronqués (lecture 2 contre 1), auto-références (lecture 3 contre 1). Le taux de blocs dégradés (9,9 %) ne vaut pas taux de pronostics affectés ; on mesure les fiches.
- Comparaison **marché par marché** des probabilités et des sélections retenues, avec les cotes gelées.
- Classement de chaque fiche : **non affectée / affectée / non reproductible / indéterminée**. « Non reproductible » = le rejeu avec les blocs originaux ne retrouve pas la fiche gelée ; elle n'est alors pas imputée à l'historique.
- Périmètre : uniquement les paris que chaque moteur a réellement gelés avant le coup d'envoi (règle du 29/10) ; pour Alpha, seulement les marchés que la page affiche.
- Livrable : `docs/AUDIT_PRONOSTICS_GELES_OMEGA_ALPHA.md` + JSON, sur une branche dédiée, aucune modification des moteurs.

### 8.3 Pipeline
`calculs.py`, `run_pipeline.py`, `scraper_details.py` : non touchés. Seraient concernés si validé : `precalcul.py` (point de purge) et `assemblage_equipes.py`.

## 9. Les six paris réglés hors règle actuelle (décision 5)

Aucune réécriture. Trois informations distinctes par pari, proposées pour le bilan réel (à ajouter par un code qui ne modifie pas le journal) :
1. **Résultat sportif** : gagné / perdu (lu dans la ligne `resultat`).
2. **Conformité à la règle de l'époque** : `validé` dans la décision enregistrée au gel, avec l'heure de gel et l'empreinte des paramètres.
3. **Conformité à la règle actuelle** (comparaison seulement) : recalculée avec les cotes gelées.

| Match | Pari | Cote gelée | Gelé le (UTC) / paramètres | Résultat | Règle de l'époque | Règle actuelle |
|---|---|---|---|---|---|---|
| Shakhtar – Obolon' (2-0) | Handicap +1,5 domicile | **absente** | 30/10 15:48 / `56de51045557` | gagné | validé | non : cote absente |
| | Domicile ne perd pas | **absente** | | gagné | validé | non : cote absente |
| | Moins de 1,5 buts de l'extérieur | 1,04 | | gagné | validé | non : cote < 1,26 |
| | Domicile ne perd pas + moins de 4,5 buts | 1,29 | | gagné | validé | non : marché sans seuil calibré |
| | Plus de 0,5 buts du domicile | **absente** | | gagné | validé (avertissement) | non : cote absente |
| Slaven – Istra (0-2) | Plus de 0,5 buts de l'extérieur | 1,23 | 30/10 16:58 / `bfd9adeafe5f` | gagné | validé | non : cote 1,23 < 1,26 |

**À savoir sur le bilan réel** : sur les 29 paris réglés, 18 gagnés (62,1 %). Ces six paris ont **tous gagné** : sans eux, 12 sur 23 (52,2 %). Les cotes absentes empêchent tout calcul de rendement pour trois d'entre eux. Le bilan doit afficher les deux chiffres. **Le 12/23 est une comparaison rétrospective, pas un bilan historique corrigé** : les six paris restent dans le journal et dans le bilan réel (18/29 = 62,1 %). **Les trois paris sans cote ne reçoivent aucun rendement estimé.** Le champ `commit` du journal ne dit pas quelle règle a gelé la fiche (il est celui du dépôt au lancement, pas du code exécuté : les lignes marquées `24f13a1` portent l'empreinte `bfd9adeafe5f`, alors que les paramètres de `24f13a1` ont l'empreinte `56de51045557`) : la règle de l'époque doit être identifiée par l'heure de gel et l'empreinte des paramètres, pas par `commit`.

## 10. Garanties demandées (récapitulatif)

| Garantie | Mécanisme |
|---|---|
| Versionnée | version par match, par identifiant externe, par règle ; journal des décisions |
| Idempotente | hash du brut ; rejeu sans effet |
| Réversible | fusion/annulation par lignes ; état = rejeu du journal |
| Indépendante des cotes | couche historique séparée ; la purge ne la lit pas |
| Reprise après interruption | publication par renommage atomique ; `etat_ingestion` |
| Traçable | brut + hash + run + preuve + version de règle pour chaque décision |
| Aucun seuil arbitraire | contrôles par comparaison d'ensembles d'identifiants |
| Unicité | U1–U8 (§2.5) |
| Preuves cohérentes | P1 prioritaire, P2 seulement sans P1 et sans contradiction ; l'audit revérifie la preuve utilisée (§3) |
| Ingestion fiable | verrou, lot + MANIFEST écrit en dernier, renommage atomique, union par clé d'observation, empreintes, test d'interruption (§4.5) |

## 11. Ordre et état (01/11/2026)

| Chantier | État | Où |
|---|---|---|
| Conception v3 (cette étude) | **livrée ; attend la validation explicite de Patrick** | ce document |
| Implémentation de l'historique permanent | **bloquée** jusqu'à validation de la v3 | — |
| Correction de `_memes_equipes` | faite et testée, branche `scraper-memes-equipes` | §13 |
| Rejeu d'impact Omega et Alpha | **fait et fusionné** (`docs/AUDIT_PRONOSTICS_GELES_OMEGA_ALPHA.md`) | §8.2 |
| Collecte parallèle de la méthode B (7 à 14 jours) | dépôt `archetype-foot-collecte` créé, code testé ; **workflow planifié à installer à la main** | §14 |
| Fusions | sur ordre explicite de Patrick (ordre du 01/11 22:20) | — |

## 12. Décisions du 01/11 (17:33) appliquées ; ce qui reste à valider

Appliquées dans ce document : saisons provisoires en compartiment distinct (§2.4) ; statut `verifie_inter_sources`, révocable, doute = en attente (§4.3) ; limites de `_memes_equipes` conservées (§13) ; dépôt séparé pour la collecte (§14).
Reste à valider par Patrick : la conception v3 complète, avant toute implémentation de l'historique permanent. Ces décisions ne valent pas cette validation.

## 13. Correction de `scraper_details._memes_equipes` (autorisée sous tests)

- **Cause** (démontrée) : sur la page de l'équipe T, une ligne `A - B` est attribuée au premier côté qui « ressemble » à T par inclusion de sous-chaîne. « Cali » est contenu dans « America Cali » : sur la page d'América Cali, le match Cali – América Cali est lu avec América Cali à domicile.
- **Portée** : `_memes_equipes` est aussi appelée par `corrige_dates_historique.py`, `enregistre_scores_historique.py`, `archetype_model/learning/resultats.py` et `archetype_model/h2h/h2h_stats.py`. **Sa règle globale n'est pas modifiée.** Seule la lecture d'une page d'équipe (`scraper_details`, boucle de lecture des lignes) change : un nouvel arbitrage de côté, sans changement de contrat ni de format de sortie.
- **Règle** : (1) égalité exacte (même normalisation que l'existant) avec un seul des deux côtés : c'est ce côté ; (2) sinon, ressemblance avec un seul côté : ce côté (comportement actuel) ; (3) ressemblance avec les deux côtés, ou égalité exacte avec les deux : **ambiguïté, ligne ignorée** (pas de donnée plutôt que fausse donnée). Pas de nouvelle heuristique de ressemblance.
- **Hors périmètre, signalé** : `moteur_europe/scraper_matchendirect.py` contient la même fonction et la même boucle (moteur Europe, non modifié) ; `h2h_stats.py` teste les deux côtés séparément.
- Tests, comparaison avant/après sur 9 pages réelles capturées, non-régression : voir le rapport de la branche.
- **Limites conservées (décision du 01/11)** : (1) le scraper du moteur Europe a encore une logique similaire ; (2) `h2h_stats.py` utilise deux tests séparés ; (3) les lignes ambiguës sont ignorées et peuvent créer une perte de données. Ces deux zones ne sont ni évaluées ni modifiées : **le problème n'est pas déclaré entièrement résolu** tant qu'elles ne sont pas auditées (audit en lecture seule à prévoir).

## 14. Collecte parallèle : mise en œuvre

- **Contrainte technique** : un déclenchement planifié (cron) d'un workflow GitHub ne s'exécute que depuis la **branche par défaut** (`main`). Ajouter un workflow planifié à ce dépôt reviendrait à fusionner dans `main`, ce qui est interdit sans ordre explicite, et créerait un lien avec le dépôt de production.
- **Option retenue pour respecter « stockage séparé, aucune connexion »** : un **dépôt distinct** (par exemple `archetype-foot-collecte`), avec son propre workflow planifié, qui n'écrit que dans son propre dépôt. Le code du collecteur est écrit et testé ici, sur une branche, sans toucher au pipeline.
- Ce bac à sable ne peut pas atteindre Matchendirect (réseau limité aux registres de paquets et à GitHub) : la collecte ne peut tourner que sur GitHub Actions.
- **État (01/11)** : dépôt privé `archetype-foot-collecte` créé sur ordre de Patrick. Contenu : collecteur autonome (pages brutes compressées avec sha256, URL finale, code HTTP, date/heure, `run_id`, manifeste écrit en dernier), analyseur sans fusion par les noms, rapport de mesure (couverture, score à J/J+1/J+2, reports, corrections, doublons, identités non résolues), comparaison A/B en lecture seule, 8 tests hors ligne. Le jeton de la session ne peut pas écrire dans `.github/workflows` : le workflow planifié est fourni dans `A_INSTALLER/collecte.yml` et doit être **créé à la main** sur GitHub. Il s'arrête de lui-même après le 16/11.
- Aucune donnée réelle n'a encore été collectée : le livrable final (comparaison A/B mesurée) viendra après 7 à 14 jours.
