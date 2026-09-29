# Graphe de dépendances réel — préparation de l'épuration

Date : 2026-09-29
Branche : refactor/epuration-systeme-legacy

## 1. Règle de sécurité

Ce document est un état de référence avant suppression. Aucune suppression de module critique ne doit être faite sur la seule base d'un nom de fichier ou d'un commentaire historique.

## 2. Flux de production actuel

### Moteur V2 actuellement en production

`precalcul.py`
→ `run_pipeline.py` (collecte/orchestration historique encore utilisée)
→ `pont_moteur.py`
→ `moteur_v2_6_9.py`
→ `branchement_moteur.py`
→ sorties `precalcul.json` / `precalcul_leger.json`

Dépendances de données importantes :
- `stats_saison_en_cours.py`
- `cache_equipes.py`
- `cache_classement.py`
- `cache_h2h.py`
- `resolution_betpawa_precalcul.py`
- `scraper_details.py`
- `parse_betpawa*.py`
- `justification.py`

### Moteur V3 expérimental

`enregistre_scores_historique.py`
→ `moteur_v3_pipeline.py`
→ `moteur_v3/{core,model,markets,decision,value,risk,calibration}.py`

La V3 ne dépend pas directement de `archetype_model` dans son cœur mathématique.

Elle dépend toutefois encore indirectement de composants historiques via :
- données/snapshots ;
- règlement ;
- H2H ;
- infrastructure d'archive.

## 3. Shrink — branche encore réellement active

Le shrink n'est PAS mort actuellement.

Chemin constaté :

`precalcul.py`
→ import dynamique `moteur_shrink_pipeline.py`
→ réutilisation de `STATS_EQUIPES_VUES`
→ `branchement_moteur.py`
→ `moteur_v2_6_9.py`
→ archive `archive_shrink/`

Puis :

`.github/workflows/pipeline.yml`
→ `bilan_shrink_v1.py`
→ `archetype_model.learning.{observations,matrice,resultats}`
→ `bilan_shrink_v1.json`

Et :

`.github/workflows/journal.yml`
→ `journal_rentabilite.py`
→ lecture de `archive_shrink/`

Et l'interface possède encore :
- `archetype_shrink.js`
- `bilan_shrink_v1` dans `etat_systeme.json`
- comparaison V2 / shrink dans `systeme.js`.

Conclusion : supprimer uniquement `moteur_shrink_pipeline.py` casserait plusieurs flux. Le retrait doit être transversal.

## 4. Ancien package archetype_model — état réel

Le package n'est plus le moteur de décision de production, mais il n'est pas encore inactif.

### Dépendances encore actives

`precalcul.py`
→ `archetype_model.learning.archive`
→ archivage des observations V2.

`precalcul.py`
→ `archetype_model.h2h.h2h_stats`
→ normalisation/classification H2H.

`stats_saison_en_cours.py`
→ `archetype_model.data.loader`
→ extraction de l'historique de saison.

`stats_saison_en_cours.py`
→ `archetype_model.data.validation.N_MAX_FENETRE`.

`branchement_moteur.py`
→ `archetype_model.learning.archive`.

`evaluation_scores.py`
→ `archetype_model.learning.resultats`.

`verifie_resultats_archetype_model.py`
→ `archetype_model.learning.resultats`.

`notifie_constat_majeur.py`
→ `archetype_model.learning.constat_majeur`.

`audit_permanent.py`
→ plusieurs modules `archetype_model`, notamment archive/règlement/H2H/Poisson.

Tests actifs :
- `tests/test_branchement_moteur.py`
- `tests/test_reglement_1x2.py`
- `tests/test_evaluation_moteur.py`
- `tests/test_audit_telemetry.py`
- `tests/test_integrite_du_depot.py`
- tests V2/H2H associés.

## 5. Modules historiques à ne pas supprimer directement

Les fichiers suivants ont encore des consommateurs identifiés :

- `run_pipeline.py`
- `calculs.py`
- `archetype_model/learning/archive.py`
- `archetype_model/learning/resultats.py`
- `archetype_model/learning/reglement.py`
- `archetype_model/h2h/h2h_stats.py`
- `archetype_model/data/loader.py`
- `archetype_model/data/validation.py`

Ils doivent d'abord être remplacés ou déplacés vers des modules appartenant à l'architecture actuelle.

## 6. Shrink : cible de suppression

Le périmètre shrink identifié est :

- `moteur_shrink_pipeline.py`
- `bilan_shrink_v1.py`
- `evaluation/cv_shrink.py`
- `evaluation/modeles/shrink_v1.py`
- `archetype_shrink.js`
- données `archive_shrink/`
- `bilan_shrink_v1.json`
- références shrink dans `precalcul.py`
- étapes shrink dans `.github/workflows/pipeline.yml`
- lecture shrink dans `.github/workflows/journal.yml` / `journal_rentabilite.py`
- comparaison shrink dans `construit_etat_systeme.py` / `systeme.js`
- assertions/tests spécifiques au shrink
- références documentaires obsolètes.

Les paramètres historiques `K_SHRINKAGE` / `calibrage_k_shrinkage` devront être retirés séparément après vérification de leurs consommateurs réels. Ils ne doivent pas être supprimés au motif qu'ils contiennent le mot « shrink ».

## 7. Stratégie d'épuration

Ordre obligatoire :

1. Supprimer le chemin d'exécution shrink du pipeline.
2. Supprimer ses sorties et son affichage.
3. Retirer les tests et références shrink.
4. Extraire les composants encore nécessaires de `archetype_model` vers des modules neutres appartenant à l'architecture actuelle.
5. Remplacer tous les imports consommateurs.
6. Vérifier qu'aucun import/runtime path ne pointe encore vers `archetype_model`.
7. Retirer l'ancien package et ses scripts devenus orphelins.
8. Rechercher les références textuelles résiduelles.
9. Exécuter la suite de tests complète.
10. Vérifier `git diff` et `git status`.
11. Ne fusionner qu'après validation.

## 8. Invariants

À préserver impérativement :
- moteur V2 actuel tant que V3 n'est pas promu ;
- contrat moteur ;
- données Football-Data/Matchendirect ;
- résolution BetPawa ;
- H2H informatif ;
- archive des résultats du moteur actuel ;
- pipeline quotidien ;
- publication Netlify ;
- format attendu par le site ;
- tests de parsing handicap 3 choix ;
- séparation V3 expérimentale / production.

## 9. Conclusion

Le graphe montre que « supprimer l'ancien système » ne signifie pas supprimer immédiatement tout le dossier `archetype_model`.

Le package contient encore des services transversaux utilisés par le moteur actuel.

La bonne épuration consiste donc à :
- supprimer le shrink maintenant ;
- extraire les briques historiques encore nécessaires ;
- faire pointer les consommateurs vers ces briques neutres ;
- puis supprimer le reste de `archetype_model`.

Aucune suppression aveugle n'est justifiée.
