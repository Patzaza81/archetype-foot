# Instructions — archive de test

`archive_donnees_test.py → data/archive_test/AAAA-MM-JJ.json.gz`

- **But** : pouvoir rejouer n'importe quel moteur (actuel ou futur) sur les matchs passés, uniquement avec ce qui était connu avant le coup d'envoi. `historique_pronostics.json` ne suffit pas : il ne garde pas les statistiques d'équipe.
- **Contenu obligatoire par match avec cotes** : liste complète des matchs de chaque équipe (saison en cours, même compétition, domicile et extérieur : date, adversaire, buts), cotes BetPawa complètes + cotes observées, choix du moteur en production, puis le score.
- **Anti-fuite** : aucun match d'équipe daté du jour du match ou après. **Figé au coup d'envoi** : le dernier état avant le coup d'envoi est gardé ; ensuite seul le score peut être écrit, et un score existant n'est jamais modifié.
- **Ne jamais retirer ni alléger** ces champs pour gagner de la place : sans eux, les matchs deviennent inutilisables pour tester un moteur. Toute donnée nouvelle utilisée par un moteur (mi-temps, corners, cartons, Football-Data…) doit aussi être ajoutée à cette archive, avec un nouveau `SCHEMA_VERSION`.
- **Tout nouveau moteur est jugé sur cette archive** (et sur Football-Data) avant tout branchement au pipeline : il doit au minimum prédire aussi bien que le marché.
- **Football-Data (SCHEMA_VERSION 2)** : l'assemblage `data/assemblage/equipes.json` est lu par `contrat_moteur.py` (seul lecteur autorisé) et chaque match y est gardé EN ENTIER (mi-temps, tirs, corners, cartons, xG), même règle anti-fuite. Constat du 27/09 : cet assemblage est publié chaque nuit mais **aucun moteur ne le lit encore** (chantier B). Assemblage absent ou contrat rompu : le bloc `assemblage` porte la raison, le reste est écrit.
- **Exécution** : chaque nuit, à la fin de `enregistre_scores_historique.py` (`execution_nocturne()`), donc après `precalcul.py` et sa garde ; `data/` est déjà commité par le workflow. Chaque équipe est retrouvée par l'adresse exacte du match dans `cache_equipes_saison.json`, jamais par ressemblance de nom.
- Tests : `tests/test_archive_donnees_test.py` (3 cas qui passent et 3 qui échouent par règle).
