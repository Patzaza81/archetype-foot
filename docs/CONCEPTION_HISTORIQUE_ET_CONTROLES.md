# Conception : référentiel canonique, historique permanent, contrôles (v2, 01/11/2026)

**Étude de conception. Aucun code. Rien n'est fusionné.** Fiches gelées, bilans historiques et autres moteurs : non touchés. L'architecture finale doit être validée par Patrick avant toute implémentation.

Cette version intègre les cinq décisions du 01/11 (section 0), ajoute les mesures demandées (sections 5 et 8) et remplace la v1.

## 0. Décisions de Patrick intégrées

| # | Décision | Où |
|---|---|---|
| 1 | Identifiants internes permanents pour clubs, compétitions, saisons ; Matchendirect et Football-Data = identifiants externes ; versions successives, brut jamais écrasé | §2, §4 |
| 2 | Étudier pages d'équipes ET résultats quotidiens ; aucun nouveau scraping avant comparaison | §5 |
| 3 | Rattachement par identifiant de match autorisé, traçable, réversible ; Sport Boys 2 / 2 Melgar récupérables | §3 |
| 4 | América Cali : correction par nouvelle version, original conservé | §7 |
| 5 | Six paris conservés ; trois informations distinctes (résultat, règle de l'époque, règle actuelle) | §9 |

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

### 2.4 Saisons
- `saison_id` lié à une compétition, avec **début et fin explicites** et leur source (code Football-Data, ou dates observées).
- **Aucune hypothèse de calendrier commun.** Les championnats d'été (Norvège, Suède, Japon, Amérique) n'ont pas la même année de début que l'Europe.
- Une saison est `provisoire` tant qu'elle n'est pas close. Si la saison d'un match ne peut pas être établie, le match est conservé avec `saison_id = indéterminée` et exclu des statistiques de saison.
- **À valider par Patrick** : règle de définition pour les compétitions sans Football-Data (133 compétitions dans l'assemblage, 38 divisions Football-Data). Proposition : première et dernière date observées, confirmées par une déclaration explicite pour les compétitions à phases.

## 3. Preuves, rattachement, traçabilité

| Rang | Preuve | Statut |
|---|---|---|
| P1 | Même identifiant de match d'une source, vu par les deux équipes, **et** les deux identités vérifiées | prioritaire |
| P2 | Nommage croisé : le bloc de l'autre équipe nomme la nôtre, même date, score inverse | complémentaire, seulement si P1 est indisponible |
| — | Nom ressemblant, score ressemblant, proximité de date | **jamais suffisant** |
| — | Contradiction entre sources | `conflit`, aucune fusion automatique |

Chaque rattachement écrit : identifiants concernés, source, preuve (identifiant de match ou références des deux enregistrements), `decide_le`, `version_regle`, statut. Un contrôle indépendant (`audit_identites.py`, existant) vérifie que tout rattachement est prouvé par P1.

**Récupération de Sport Boys 2 / 2 Melgar** : le match du 15/04/2026 (3-1) porte le même identifiant dans les deux blocs ; chaque bloc l'écrit avec un alias en « 2 » (pas de nommage croisé, donc P2 échoue). P1 s'applique si les deux identités (Sport Boys, Melgar) sont chacune vérifiées. Mesuré : 2 alias sur 23 prouvés par P1 que le chargeur strict ne rattache pas.

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
- Football-Data ↔ Matchendirect : lien créé seulement après identification des deux clubs, sur `(date ± 1 jour, domicile_id, exterieur_id)`, avec preuve enregistrée. Deux candidats ou plus : `conflit`.
- Deux observations du même identifiant de match doivent être **miroirs** (domicile opposé, buts échangés, même date). Sinon : `conflit` (§7).

### 4.4 Mise à jour, versionnement, reprise
- Un run écrit dans un dossier temporaire, puis le publie en une seule opération de renommage ; un run interrompu ne laisse aucun état partiel visible.
- `etat_ingestion` : dernier `(source, jour)` traité ; reprise = continuer après ce point ; rejouer un jour déjà traité est sans effet (hash du brut identique).
- Une source qui change un score ou une date sur un même identifiant crée une nouvelle version ; l'ancienne reste, marquée `remplacée`.
- La purge du cache J0–J+3 ne lit ni n'écrit cette couche.

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

**Ce que je n'ai pas pu mesurer** (la page quotidienne locale date du matin du 01/11 : seulement 18 matchs avec score) : la part de matchs terminés avec score final à J+1, le taux de noms de clubs non résolus, les reports et corrections. La seule façon de les mesurer est une **collecte parallèle** sur plusieurs jours, écrite dans un dossier séparé, **sans lien avec le pipeline**. C'est un nouveau scraping, même isolé : **je ne le lance pas sans ton accord**.

**Recommandation** : décider l'architecture d'alimentation après cette collecte parallèle (7 à 14 jours), avec les quatre mesures ci-dessus.

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

**Ce que je n'ai pas fait** : mesurer l'effet de ces 9,9 % sur les probabilités d'Omega et d'Alpha, ni auditer leurs paramètres et leurs dépendances au-delà des chargeurs. Aucun moteur n'est modifié. À faire avant toute adaptation : rejeu des fiches gelées d'Omega et d'Alpha avec le meilleur historique connu (union des versions), même méthode que l'audit Gamma.

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

**À savoir sur le bilan réel** : sur les 29 paris réglés, 18 gagnés (62,1 %). Ces six paris ont **tous gagné** : sans eux, 12 sur 23 (52,2 %). Les cotes absentes empêchent tout calcul de rendement pour trois d'entre eux. Le bilan doit afficher les deux chiffres. Le champ `commit` du journal ne dit pas quelle règle a gelé la fiche (il est celui du dépôt au lancement, pas du code exécuté : les lignes marquées `24f13a1` portent l'empreinte `bfd9adeafe5f`, alors que les paramètres de `24f13a1` ont l'empreinte `56de51045557`) : la règle de l'époque doit être identifiée par l'heure de gel et l'empreinte des paramètres, pas par `commit`.

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

## 11. Ordre proposé

1. Valider ce document (référentiel, saisons des compétitions sans Football-Data, hiérarchie P1/P2).
2. Autoriser ou non la **collecte parallèle** de la méthode B (aucune intégration au pipeline).
3. Auditer Omega et Alpha par rejeu avec le meilleur historique connu.
4. Décider de la correction du scraper (`_memes_equipes`) : fichier protégé.
5. Implémentation par étapes (référentiel → brut/observations → consolidé → contrôles bloquants), chaque étape testée, comparée avant/après.
6. Fusion seulement sur ordre explicite.

## 12. Décisions à prendre par Patrick

1. Valider le référentiel (identifiants internes, éditions/phases) et la règle de saison pour les compétitions hors Football-Data.
2. Autoriser la collecte parallèle de B pendant 7 à 14 jours.
3. Autoriser l'audit d'impact d'Omega et d'Alpha par rejeu.
4. Autoriser (ou non) la correction de `scraper_details._memes_equipes` (mécanisme démontré pour 3 des 4 cas « miroir » observés : América Cali et les deux Cerro / Cerro Largo ; le 4e, Comerciantes / Melgar, a une date absente et n'est pas élucidé).
5. Valider la présentation du bilan en trois informations pour les six paris.
