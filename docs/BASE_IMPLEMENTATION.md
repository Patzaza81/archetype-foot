# Implémentation BASE — vérifications et écarts avec le protocole v4

- **Module** : `base_protocole.py` (lecture seule), tests `tests/test_base_protocole.py` (53 tests).
- **Branche** : `base-implementation`, issue de `protocole-base`. Aucune fusion, aucun workflow, aucune page du site.
- **Lecture** : les archives sont lues à un état Git (`--ref`, par défaut `origin/main`) avec `git show`, jamais dans l'arbre de travail. La branche n'a donc pas besoin d'être à jour avec `main`.
- **Écriture** : uniquement `data/base/` (`etat.json`, `empreintes.jsonl`, `points_de_controle.json`, `simulation.json`). Un test le vérifie.

## 1. Reproduction des chiffres du § 10 (archive au commit `7c532a7`, calcul au 13/10/2026 6 h UTC)

| Élément | Protocole § 10 | Module | Écart et cause |
|---|---|---|---|
| B0 : matchs / jours | 253 / 13 | 253 / 13 | aucun |
| B0 : réussite | 74,3 % | 74,31 % | aucun |
| B0 : probabilité implicite brute | 75,5 % | 75,55 % | aucun |
| B0 : ROI | −1,5 % | −1,47 % | aucun |
| B0 : ROI, intervalle 95 % bootstrap | −5,6 ; +2,3 % | −5,4 ; +2,2 % | 100 000 tirages au lieu de 10 000 (bruit du tirage) |
| B0 : ROI, intervalle 95 % Student | non calculé | −5,4 ; +2,5 % | nouveau |
| H1-a / H1-b | 149 / 104 | 149 / 104 | aucun |
| `RELEVE_APRES_COUP_D_ENVOI` / `HORODATAGE_ABSENT` | 11 / 7 | 11 / 7 | aucun |
| `RESULTAT_MANQUANT` | 2 | 2 | aucun |
| `NON_REGLE` | 38 | 37 | le § 10 comptait par relevé ; le module compte par match après retrait des doublons |
| Doublons | 3 | 4 | même cause : un doublon de plus parmi les matchs non réglés |
| B1 | 15 | 15 | aucun |
| B2 | 13 | 13 | aucun |
| B3 | 14 | **3** | le module applique la définition du § 6.2 (choix de **V2.6.10**) ; la reproduction du 13/10 comptait aussi V2.6.9, en production avant la migration |
| B4 / complément | 175 / 78 | 175 / 78 | aucun |

Le test `test_reproduction_des_chiffres_du_paragraphe_10` vérifie ces valeurs (ignoré si le commit `7c532a7` est absent du clone).

## 2. Reproduction de la simulation du § 9.5 (200 000 tirages par ligne)

| Jours | Niveau | Protocole | Module | Intervalle du module |
|---|---|---|---|---|
| 20 / 40 | 99,5 % | 0,688 % | 0,670 % | 0,634 – 0,706 % |
| 25 / 50 | 99,5 % | 0,661 % | 0,655 % | 0,620 – 0,691 % |
| 30 / 60 | 99,5 % | 0,665 % | 0,636 % | 0,601 – 0,671 % |
| 20 / 40 | 99,6 % | 0,544 % | 0,555 % | 0,523 – 0,589 % |
| **20 / 40** | **99,7 %** | **0,455 %** | **0,453 %** | **0,424 – 0,483 %** |

Les écarts restent dans l'erreur de simulation. Différences de méthode :
- cotes tirées parmi les matchs admis par les règles du § 4 (le 13/10 : tous les matchs de H1, sans exclusion) ;
- graines différentes.

La conclusion est inchangée : 99,7 % tient la cible de 0,5 %, borne haute comprise.

## 3. Précisions d'implémentation — décisions finales du 13/10/2026

**Décision : les deux adaptations ci-dessous sont acceptées pour l'implémentation v4.** Elles clarifient la représentation des données et la population effectivement suivie ; elles ne modifient ni H1, ni les cotes, ni les seuils statistiques, ni les points de contrôle. Le protocole source reste conservé tel quel pour la traçabilité.

Deux points du texte du protocole ne pouvaient pas être appliqués à la lettre. **Ils doivent être validés ou refusés.**

| § | Texte du protocole | Règle d'implémentation retenue | Raison (preuve) |
|---|---|---|---|
| 5.1 | empreinte score = « le champ `score` seul » | empreinte du **résultat** (`buts_dom`, `buts_ext`) | le pipeline réécrit l'horodatage `score.ecrit_le` sans changer le score : 120 fausses alertes sur l'archive actuelle avec la définition littérale, 0 avec celle-ci |
| 6.2 | A(B2) : « les **deux** équipes ont au moins 5 matchs » | **au moins une** des deux équipes, ou pari effectivement proposé par le Journal | le Journal suit une seule équipe. Avec « les deux », 4 des 13 paris réellement proposés auraient été jugés « non admissibles », ce qui est contradictoire |

Autres précisions, sans effet sur les règles :
- **Clé du registre d'empreintes** = fichier + match. Un même match peut figurer dans deux fichiers journaliers ; avec le match seul, 59 fausses alertes (sur 182 au total avant ces deux précisions ; 3 après).
- **Points de contrôle** : calculés sur les **premiers jours complets** qui atteignent les minimums (300 matchs et 20 jours ; 600 et 40). Le résultat ne dépend donc pas du jour où le calcul est lancé.
- **Simulation au point de contrôle** : à C1, le second contrôle est simulé avec max(40, 2 × jours de C1) jours ; à C2, avec les jours réels de C1 et C2.
- **Lois de Student et bêta** : calculées sans scipy, que le runner du pipeline n'installe pas. Écart avec scipy inférieur à 10⁻⁹ (testé). Les tests passent dans un environnement limité aux paquets du workflow.

## 4. Constat sur l'archive de test (défaut du pipeline, non corrigé ici)

Le registre d'empreintes, reconstruit depuis l'historique Git de `main`, montre **3 matchs dont les données d'avant-match ont été réécrites après le coup d'envoi**. La règle « figé au coup d'envoi » de `docs/CLAUDE_ARCHIVE.md` n'a donc pas été respectée pour eux :

| Fichier | Match | Champs modifiés |
|---|---|---|
| `2026-10-08.json.gz` | `5ssxx2cubaxn0dzoqx8vhg45w` | `run` (nouveau relevé) |
| `2026-10-10.json.gz` | `6tfz6x71jlsl00mq9tjblv0no` | données d'avant-match |
| `2026-10-12.json.gz` | `14tmt9vbsc9ngvwf484emf21g` | cotes, coup d'envoi, choix V2, `run` |

- Ces trois matchs sont antérieurs à la période de test. Ils seraient exclus (`MODIFICATION_DETECTEE`) s'ils entraient dans un calcul de décision.
- La correction relève de `archive_donnees_test.py` sur `main`, hors du périmètre autorisé.

## 5. État au 13/10/2026 (lecture de `origin/main`)

- **Statut B0 : NON ÉVALUÉ.** La période de test a commencé le 13/10 ; aucun match n'a encore 7 jours.
- 54 matchs de H1 dans la période de test, tous `NON_REGLE`.
- Aucun point de contrôle atteint.


## 6. Décision de livraison

- Les deux précisions de la section 3 sont validées pour cette branche isolée.
- Les résultats de test et de simulation sont documentés ; B0 reste **NON ÉVALUÉ** tant que les points de contrôle ne sont pas atteints.
- Le défaut d'archive concernant trois matchs reste hors périmètre et n'est pas corrigé ici.
- Cette validation ne vaut **ni fusion dans `main`, ni ouverture de PR, ni exécution de workflow, ni publication du site**. Toute mise en production exige une décision distincte après les futurs points de contrôle et une revue du diff.

## 6. Déclenchement automatique de C1 et C2 (13/10/2026)

**Mécanismes examinés** :

| Mécanisme | Possible sans toucher `main` ? | Raison |
|---|---|---|
| Workflow GitHub programmé (`schedule`) | non | GitHub ne lit ce déclencheur que dans les workflows de la branche principale |
| Workflow lancé après le pipeline (`workflow_run`) | non | même limite (branche principale seulement) |
| Fonction programmée Netlify | non | Netlify déploie `main` : ce serait une mise en production |
| **Tâche planifiée Claude** (session quotidienne qui lance `--auto` sur la branche) | **oui** | ne dépend que de la branche dédiée ; lit `origin/main` sans la modifier |

**Ce qui détecte les seuils** : le code (`execute` → `prefixe`), pas la tâche planifiée. La tâche ne fait que lancer le passage chaque jour. C1 et C2 sont évalués sur les premiers jours complets qui remplissent les conditions : le résultat ne dépend pas du jour où le passage tourne.

**Protections, toutes testées** :
- aucun point de contrôle avant son seuil (299 matchs, ou 19 jours, ou matchs de moins de 7 jours : rien) ;
- jamais deux C1 : ajout seul, relance sans effet, reprise depuis la version distante si un autre passage a publié entre-temps ;
- verrou local contre deux passages simultanés ;
- refus de `main` et d'un arbre de travail modifié ;
- commit limité à `data/base/`.

**Limites** :
- La tâche planifiée dépend du service de tâches de Claude. Si un passage échoue, le suivant rattrape (le calcul est complet à chaque fois).
- Le registre d'empreintes suppose des passages réguliers. Un long arrêt rapprocherait la « première observation » de la date de reprise ; l'historique Git de `main` limite ce risque (§ 5.2).
