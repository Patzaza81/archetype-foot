# Conception : historique permanent des championnats + contrôles du pipeline (01/11/2026)

**Étude seule. Aucun code n'est écrit pour cette conception. Rien n'est fusionné.** À valider par Patrick avant toute implémentation (phase 2 : « présenter le fonctionnement et les conséquences sur les moteurs existants »).

## 1. Ce que les données montrent (faits mesurés le 01/11/2026)

- Le cache `cache_equipes_saison.json` (1 075 équipes) n'est alimenté que pour les équipes d'un match **coté BetPawa dans J0–J+3**. Il est purgé par TTL (`precalcul.py`, `purge_equipes_expirees`). Son cycle de vie est celui des cotes, pas celui du sport.
- L'assemblage `data/assemblage/equipes.json` est **reconstruit à chaque run, jamais cumulé** (champ `regle`). Un match disparaît dès que son équipe sort du cache. Conséquence mesurée le 01/11 : 11 championnats à zéro match, 9 275 → 8 424 matchs.
- Les identifiants stables **existent déjà** dans les sources :
  - équipe : l'identifiant de 25 caractères dans l'adresse Matchendirect (`/equipe/aachen_ec35ufnr…html`) ;
  - match : l'identifiant dans `url_match` (`/live-score/…_9vc5rqfvidznnj4fz2nyuo55g.html`), présent sur **100 % des 6 335 enregistrements Matchendirect** de l'assemblage (les 5 833 enregistrements Football-Data n'en ont pas) ; le même match vu des deux côtés porte le même identifiant ;
  - match à venir : `match_id` de l'archive.
- Le chargeur n'utilise pas `url_match`. Il reconstruit les identités par date et score, puis (depuis le correctif) par nommage explicite. Vérifié : sur 1 509 matchs vus des deux côtés, l'identifiant prouve 23 alias ; le chargeur strict en rattache 21, tous confirmés ; l'ancien en rattachait 110 de plus **sans aucune preuve** (`audit_identites.py`).
- `data/correspondances/equipes.json` relie 595 équipes Football-Data ↔ Matchendirect en 36 divisions, **par ressemblance de nom + score/date** (48 non résolues). C'est la même famille de méthode que celle qui a produit les fausses identités ; elle n'est pas une source de référence.
- Football-Data couvre 407 équipes sur 1 075 ; 668 équipes (133 championnats au total) n'ont que Matchendirect.

## 2. Architecture cible (une responsabilité par étage, un contrat par étage)

1. **Sources sportives** : Matchendirect, Football-Data. Lecture seule, brut conservé avec provenance (source, identifiant source, date de collecte).
2. **Référentiel canonique** : un identifiant interne par club, par compétition, par saison. Les noms sont des attributs (liste d'alias avec provenance), jamais la clé. Clé club = identifiant Matchendirect de l'équipe quand il existe ; sinon identifiant interne créé une fois et jamais réutilisé.
3. **Réconciliation** : seule couche qui relie des identifiants entre eux (Football-Data ↔ Matchendirect, alias ↔ club). Chaque lien porte une **preuve vérifiable** : même identifiant de match, ou nommage explicite croisé. Pas de score de ressemblance. Un lien non prouvé reste « non résolu » et n'entre pas dans les statistiques. Les conflits sont listés, pas tranchés.
4. **Historique sportif permanent** : un enregistrement par match terminé, ajout seul, jamais supprimé par la purge du cache.
5. **Contrôle qualité et publication** : invariants (section 4). Rien n'est publié si un invariant de couche dérivée est violé.
6. **Moteurs** (Gamma, Alpha, Omega, futurs) : lisent l'historique par un adaptateur ; aucun ne reconstruit d'identités.

### Enregistrement de match (identité stable, indépendante des noms affichés)
`competition_id`, `saison_id`, `domicile_id`, `exterieur_id`, `date`, `source` + `source_id`, `score_final`, `statut_validation`, `vu_le` (première et dernière observation), `alias_vus` (noms écrits par chaque source).

`statut_validation` : `source_unique` (une seule vue) · `confirme` (deux vues indépendantes, même identifiant de match, ou Football-Data + Matchendirect prouvés) · `conflit` (deux vues, scores ou dates différents) · `quarantaine` (invariant violé dans la source, exclu des statistiques).

Choix à valider : identifiant de compétition = nom Matchendirect normalisé + code Football-Data quand il existe ; identifiant de saison = année de début de la fenêtre (Football-Data : `2627`). Aucune de ces deux clés n'est encore dans les sources de façon propre : à vérifier avant de s'engager.

## 3. Cycle de vie : mise à jour, dédoublonnage, reprise, réconciliation

- **Mise à jour** : à chaque run, les pages d'équipes déjà scrapées pour le cache alimentent aussi l'historique (aucune nouvelle dépendance, aucun scrapping supplémentaire). Ajout des seuls matchs terminés non encore connus.
- **Dédoublonnage** : clé `(competition_id, source, source_id)`. Le même match vu des deux équipes se fusionne par identifiant, pas par date et score. Football-Data ↔ Matchendirect : seulement après réconciliation des clubs, sur `(date ± 1 jour, domicile_id, exterieur_id)`.
- **Reprise** : idempotente. Rejouer un run n'ajoute rien. Un run interrompu reprend sans trou, car il ne fait qu'ajouter.
- **Correction d'une source** : un score ou une date qui change sur un même identifiant crée une nouvelle version de l'enregistrement et marque l'ancienne `remplacée` (jamais effacée). Les fiches Gamma gelées ne sont jamais réécrites : elles gardent l'identifiant de version d'historique utilisé (à ajouter à la fiche).
- **Purge** : ne touche que le cache des matchs à pronostiquer (J0–J+3, cotes). L'historique n'est jamais purgé automatiquement.
- **Limite connue** : une équipe qui n'a jamais eu de match coté n'est jamais scrapée. La couverture de l'historique reste donc partielle au départ et croît avec le temps. Pour combler : les pages de résultats quotidiens de Matchendirect (`moteur_europe/scraper_matchendirect.py` existe déjà) pourraient alimenter l'historique de tout un championnat. **Non testé ici** ; à examiner avant de décider.

## 4. Contrôles du pipeline (sans liste d'exceptions)

Principe : une anomalie est classée par **ce qu'elle viole et où elle apparaît**, pas par une liste de cas connus.

| Invariant | Couche | Si violé |
|---|---|---|
| I1 : aucun match d'une équipe contre elle-même | source | l'enregistrement passe en `quarantaine` (règle générale), exclu des statistiques, signalé avec son identifiant |
| I1 bis : même contrôle après chargement | dérivée | **blocage** (le correctif de chargeur rend ce cas impossible : tout cas est un défaut du code) |
| I2 : tout identifiant de match, de club, de compétition existe dans le référentiel | dérivée | blocage |
| I3 : un même identifiant de match n'a qu'un score et qu'une date | source | `conflit`, exclu des statistiques, signalé |
| I4 : tout alias rattaché à un club est prouvé par un identifiant de match | dérivée | blocage (déjà vérifié par `audit_identites.py` : 21/21 prouvés, 0 contredit) |
| I5 : aucun club ne fusionne avec un autre club du référentiel | dérivée | blocage |
| I6 : monotonie : un match terminé présent dans la version précédente est encore présent, ou marqué `remplacé`/`quarantaine` avec sa raison | dérivée | blocage = perte non expliquée |
| I7 : un championnat attendu (match coté dans la fenêtre) n'est pas vide alors qu'il avait des matchs à la version précédente | dérivée | blocage = perte de couverture |

- **Aucun seuil en pourcentage.** I6 et I7 comparent des **ensembles** (identifiants présents avant, absents maintenant), pas des taux.
- **Anomalie nouvelle de source** (I1, I3) : mise en quarantaine immédiate et **signalée à Patrick au premier passage**. Elle n'arrête pas le pipeline en continu : son statut `quarantaine` est une propriété de l'enregistrement dans l'historique (avec son identifiant, sa source, sa date de première observation, la raison), pas une exception codée. Au run suivant elle n'est plus « nouvelle ». Les seuls cas connus aujourd'hui : América Cali (26/04) et Cerro (29/05). L'identifiant de match prouve même le vrai adversaire du match América Cali (Cali) : une correction par la source serait possible, à décider.
- **Compétition réellement incomplète** : classée par I7/I6, rapportée à part dans le rapport de contrôle, distincte des anomalies de chargeur (I1 bis, I2, I4, I5).
- **Compromis assumé** : bloquer sur I6/I7 tant que le cache source n'est pas remplacé par l'historique permanent bloquerait souvent le pipeline (le cache tourne : 22 matchs disparus entre deux versions, 11 championnats vides). Le blocage ne devient tenable qu'**après** l'étage 4. Avant, I6/I7 doivent rester en mode rapport.

## 5. Conséquences sur les moteurs existants

- **Gamma** : lit aujourd'hui l'assemblage via `moteur_dc/donnees.py`. Avec l'historique, le chargeur n'aurait plus à reconstruire d'identités pour les enregistrements Matchendirect (identifiants fournis). Les effectifs (n) et les buts attendus **changeraient** (plus de matchs, vrais adversaires) : toutes les fiches futures seraient différentes de celles d'aujourd'hui. Rejeu avant/après obligatoire.
- **Omega / Alpha série** : ils ont leurs propres chargeurs. **Non audités ici.** Ils lisent peut-être la même source dégradée ; à vérifier avant de dire qu'ils ne sont pas touchés. Aucun n'est modifié.
- **Journal gelé et bilans** : inchangés. Les bilans ne portent que sur les paris gelés avant le coup d'envoi. Ajouter l'identifiant de version d'historique à la fiche permettrait ensuite de dire sur quelle donnée repose chaque pari.
- **Pipeline** : `calculs.py`, `run_pipeline.py`, `scraper_details.py` ne seraient pas touchés. Seuls `precalcul.py` (point de purge) et `assemblage_equipes.py` changeraient.

## 6. Ordre proposé (avis de Patrick repris, avec l'état actuel)

1. Éliminer les fausses identités : **fait** sur `moteur-dc-chargeur` (non fusionné), prouvé par identifiant (`audit_identites.py`).
2. Audit d'impact des pronostics gelés : **fait** (`docs/AUDIT_PRONOSTICS_GELES.md`).
3. Étage 4 (historique permanent) : **à valider** d'après ce document.
4. Contrôles bloquants (I1 bis, I2, I4, I5 immédiatement ; I6, I7 après l'étage 4).
5. Rejeu des moteurs sur les données corrigées, comparaison avant/après.
6. Fusion après validation explicite.

## 7. Décisions à prendre par Patrick

1. Valider l'enregistrement de match (section 2) et les clés de compétition/saison.
2. Autoriser l'historique à s'alimenter uniquement des pages d'équipes déjà scrapées, ou étudier les résultats quotidiens de Matchendirect.
3. Autoriser ou non une règle de rattachement fondée sur l'identifiant de match (récupère 2 alias de plus, supprime toute dépendance aux scores).
4. Faire corriger ou non l'enregistrement América Cali par l'identifiant du match (traiter comme anomalie de source sinon).
5. Statuer sur les 6 paris réglés qui ne respectent pas la règle actuelle (Shakhtar, Slaven), indépendamment des identités.
