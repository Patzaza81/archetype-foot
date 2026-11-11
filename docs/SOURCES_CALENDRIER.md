# Sources de calendrier (11/11/2026)

Code `sources_calendrier/` · réglages `config/sources_calendrier.json` et `config/sources_noms.json` · résultats `data/sources_calendrier/` · étape du pipeline `python -m sources_calendrier.mesure`.

## Pourquoi

Tout le système dépendait d'une seule source pour savoir quels matchs se jouent : Matchendirect. Du 08/11 au 11/11/2026, la collecte de J+2 et J+3 est restée vide sans que rien ne le signale.
Ce module prépare des sources de secours **gratuites**, mesurées avant d'être branchées.

## Hiérarchie (une seule liste, dans `config/sources_calendrier.json`)

| Rang | Source | Rôle | Nature |
|---|---|---|---|
| 1 | matchendirect | principale | `scraper.py` + `scraper_semaine.py`, inchangés |
| 2 | espn | secours | flux public d'ESPN, sans clé, non officiel, environ 250 championnats |
| 3 | openfootball | secours | fichiers libres sur GitHub (9 championnats suivis), impossible à bloquer |

Constat du 11/11/2026 sur openfootball : les 9 fichiers contiennent le calendrier de toute la saison, mais leurs scores s'arrêtent au 20/09/2026. Calendrier de dernier recours seulement, jamais une source de résultats.

## Organisation du code (un rôle par fichier)

| Fichier | Rôle |
|---|---|
| `modele.py` | le format commun `Match` ; suppression des doublons par (source, identifiant) |
| `sources/<nom>.py` | un fichier par source : `lire(jours, conf, telecharger) -> (matchs, erreurs)` et rien d'autre |
| `reseau.py` | le seul endroit qui télécharge (délai, essais, en-tête) |
| `noms.py` | comparaison des noms d'équipes, réglée par `config/sources_noms.json` |
| `rapprochement.py` | « est-ce le même match ? » : un pour un, le doute donne « ambigu » |
| `mesure.py` | compare les sources de secours à la principale et écrit le résultat |

## Règles

- Une source ne plante jamais les autres : elle rend ses matchs et la liste de ses erreurs.
- Même match = les deux équipes concordent, dans le même sens (domicile / extérieur), à un jour près au plus.
- Un match de référence n'est rapproché qu'à un seul match d'une source, et inversement. Deux candidats = « ambigu », jamais un choix.
- Féminines, jeunes (U17, U19…) et réserves ne sont jamais confondues avec l'équipe première. Matchendirect ne l'écrit pas toujours dans le nom de l'équipe : on le reprend du nom de la compétition.
- ESPN range les matchs par jour américain : la veille du premier jour est demandée aussi, puis chaque match n'est gardé qu'une fois.
- Si ESPN rend autant de matchs que la limite demandée, c'est noté comme erreur (liste peut-être coupée).

## Corriger

| Problème | Où corriger |
|---|---|
| Une équipe n'est pas reconnue entre deux sources (ex. « Allemagne » / « Germany ») | `config/sources_noms.json`, rubrique `equivalents` |
| Un mot parasite empêche la reconnaissance (« FC », « Club »…) | `config/sources_noms.json`, rubrique `mots_ignores` |
| Couper une source | `config/sources_calendrier.json`, `"actif": false` |
| Ajouter un championnat openfootball | `config/sources_calendrier.json`, liste `fichiers` |
| Une source change de format | son seul fichier `sources/<nom>.py` |
| Ajouter une source | un nouveau fichier `sources/<nom>.py` + une ligne dans la liste |

La mesure liste elle-même les matchs avec cotes qu'une source n'a pas retrouvés (`exemples_avec_cotes_non_retrouves`) : c'est la liste de travail pour compléter les équivalents.

## Mode actuel : mesure

Chaque nuit, `data/sources_calendrier/mesure.json` (dernier passage) et `historique.json` (un résumé par passage) disent, pour chaque source de secours :
joignable ou non, nombre de matchs lus, part des matchs Matchendirect retrouvés, et surtout part retrouvée **parmi les matchs qui ont des cotes Betpawa**.
Rien n'alimente le système. On ne branchera une source de secours qu'au vu de ces chiffres.

## Tests

`tests/test_sources_calendrier.py` : sans réseau, données fabriquées.
