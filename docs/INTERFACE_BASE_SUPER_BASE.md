# Cahier des charges — interface BASE / SUPER BASE

- **Statut :** spécification de design uniquement ; aucun écran ni code UI n'est créé par ce document.
- **Branche cible :** `protocole-base`.
- **Règle de sécurité :** ne pas modifier `main`, les moteurs V2/V3, le Journal, les indices, la navigation actuelle ou les workflows.
- **Protection pendant l'implémentation du module (décision du 13/10/2026) :** aucun changement de navigation, de styles globaux ou de pages existantes.
- **Publication :** aucune page BASE/SUPER BASE sur le site avant le point de contrôle C1 prévu dans `PROTOCOLE_BASE.md` et sans validation explicite.

## 1. Objectif UX

Rendre les résultats compréhensibles sur iPhone sans obliger l'utilisateur à interpréter des statistiques complexes. Séparer visuellement :
- **BASE** : mesure de la configuration de référence B0 ;
- **SUPER BASE** : espace futur réservé aux indices dont la valeur ajoutée aura été démontrée selon le protocole. Tant qu'aucun indice n'est validé, afficher « Aucun indice validé » plutôt que suggérer une performance.

## 2. Structure de l'écran (mobile-first)

1. **En-tête** : « BASE / SUPER BASE » et une phrase expliquant que l'écran évalue l'historique, sans garantir les résultats futurs.
2. **Carte BASE — hypothèse H1** : « Moins de 3,5 buts », cote 1,27–1,39, période évaluée et date du dernier point de contrôle.
3. **Indicateurs principaux**, dans cet ordre :
   - ROI réel, mesure principale, avec intervalle d'incertitude ;
   - matchs réglés et nombre de jours de matchs distincts ;
   - taux de réussite avec son intervalle ;
   - cote moyenne / probabilité implicite brute, clairement identifiée comme repère et non comme preuve d'avantage.
4. **Statut statistique** : NON ÉVALUÉ, EN COURS, NON CONCLUANT, NEUTRE, DÉFAVORABLE ou VALIDÉ. Le statut est accompagné d'une explication courte et de la date du point de contrôle. Aucun statut ne doit être déduit visuellement d'un simple taux de réussite.
5. **Données exclues et limites** : lien ou panneau repliable montrant les volumes exclus par motif, les résultats manquants et les limites des cotes relevées avant match.
6. **Section exploratoire B1 à B4 (décision du 13/10/2026)** : section séparée de la carte BASE, titrée comme exploratoire. Chaque configuration affiche son statut en toutes lettres : « Non évalué », « En cours », « Signal exploratoire » ou « Sans signal », avec ses deux comparaisons (générale et à population égale). Jamais présentée comme un pronostic validé, jamais de badge « VALIDÉ ».
7. **SUPER BASE** : liste d'indices avec version, volume, période et statut. Par défaut, tous les indices restent « NON ÉVALUÉ » ; aucun indice ne devient validé sans satisfaire aux critères du protocole.

## 3. Présentation visuelle

- Concevoir d'abord pour une largeur de **414 px**, puis vérifier les largeurs plus petites et plus grandes.
- **Référence (décision du 13/10/2026)** : le design actuel d'ARCHETYPE Foot et ses composants `theme.css` (variables `--af-*`, turquoise principal). Ne pas créer une identité concurrente.
- **Thème (décision du 13/10/2026)** : mode clair par défaut, compatible avec le mode nuit existant. Pas de thème sombre distinct imposé.
- Le rose reste réservé aux éléments où le site l'utilise déjà. Les couleurs ne doivent jamais être le seul moyen d'identifier un statut.
- Cartes compactes, titres courts, chiffres lisibles, marges suffisantes et navigation simple ; éviter les tableaux larges, les paragraphes longs et les informations répétées.
- Les statuts doivent aussi être écrits en toutes lettres et accompagnés d'une explication accessible.
- Prévoir chargement, absence de données, erreur de collecte et données insuffisantes sans afficher de faux zéro ni de pourcentage trompeur.

## 4. Règles de contenu et de confiance

- Afficher « NON ÉVALUÉ » lorsque les données ne suffisent pas.
- Toujours présenter le ROI avec la période, le nombre de matchs, le nombre de jours et l'intervalle.
- Ne pas présenter le taux de réussite seul comme preuve de rentabilité.
- Ne jamais masquer les paris perdants, les exclusions, les données manquantes ou les limites méthodologiques.
- Ne pas utiliser de formulations telles que « pari sûr », « garanti » ou « bénéfice assuré ».
- Les configurations B1 à B4 restent exploratoires et ne doivent pas recevoir un badge « VALIDÉ ».
- Ne pas afficher de projection de gains futurs comme s'il s'agissait d'un résultat observé.

## 5. Accessibilité et vérification

Avant toute intégration :
- vérifier la lisibilité à 414 px et sur un écran plus étroit ;
- vérifier les contrastes, la taille des textes, les libellés et la navigation au toucher ;
- tester les états NON ÉVALUÉ, EN COURS, NON CONCLUANT, NEUTRE, DÉFAVORABLE et VALIDÉ avec des données de test ;
- vérifier que les chiffres affichés correspondent exactement aux sorties du module BASE ;
- vérifier qu'aucun composant, style global, route ou navigation existante n'a été modifié ;
- fournir une capture avant/après et le diff exact pour revue avant publication.

## 6. Hors périmètre

Ce cahier des charges n'autorise pas à modifier le site, ses pages existantes, le design global, les moteurs, le Journal, les indices ou les workflows. Il décrit uniquement la future présentation de BASE/SUPER BASE. La maquette et l'intégration restent soumises à une validation séparée.
