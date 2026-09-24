# Contrat de données Football-Data

## Principe

Ce dossier est une couche de **collecte et normalisation**, pas une couche
d'analyse.

Le collecteur:

1. découvre les fichiers réellement publiés par Football-Data.co.uk ;
2. conserve le CSV source sans modification dans `raw/` ;
3. produit une ligne normalisée par match dans `normalized/*.jsonl` ;
4. conserve la provenance et le SHA-256 dans `manifest.json`.

Le collecteur ne calcule **aucune** moyenne, probabilité, xG dérivé, EV,
valeur, signal ou choix de marché.

## Politique des saisons

- `2627` = saison courante au 24/09/2026 : elle peut être mise à jour si
  Football-Data publie un contenu différent.
- `2526` = saison passée : une fois téléchargée avec succès, elle devient
  immuable et n'est plus retéléchargée par le collecteur.
- Les fichiers bruts sont la référence de traçabilité ; le JSONL normalisé
  est le contrat consommable par le futur moteur.

## Champs normalisés

Les champs disponibles sont conservés seulement s'ils sont présents dans la
source: date, heure, code compétition, équipes, scores finaux, scores
mi-temps, tirs, tirs cadrés, corners, cartons et xG lorsqu'un champ xG existe
réellement.

Un champ absent reste `null` ou absent selon le type de donnée. Il n'est
jamais remplacé par zéro.

Les colonnes de cotes Football-Data restent dans le CSV brut. Elles ne sont
pas interprétées comme cotes d'ouverture/clôture par cette couche. Le chantier
des cotes du run prendra ses propres relevés horodatés.

## Consommation

Le moteur d'analyse pourra lire `data/football_data/normalized/` sans
déclencher de téléchargement et sans dépendre de Matchendirect ou BetPawa.
Le rapprochement inter-sources et les décisions de marché sont des chantiers
séparés.

## Archive historique annuelle — A1

À partir de la décision d'architecture A1, les saisons terminées sont archivées
comme snapshots complets dans `data/football_data/snapshots/<saison>/`.
Le snapshot contient tous les CSV Football-Data découvrables pour la saison,
classés par division/compétition, avec manifeste SHA-256 et verrou
`_SNAPSHOT_COMPLETE.json`.

Un snapshot marqué COMPLETE est **immuable** : aucun téléchargement quotidien,
aucun remplacement silencieux et aucune fusion avec une autre saison. En cas
d'archive incomplète, seuls les fichiers manquants peuvent être ajoutés ; les
fichiers déjà présents ne sont jamais écrasés.

Le premier snapshot réel doit être exécuté et contrôlé dans GitHub Actions avant
que l'archive soit considérée comme validée en conditions réelles.

Le moteur doit lire ces snapshots localement. La collecte historique et la
collecte opérationnelle de la saison courante sont deux flux distincts.


## Catalogue des compétitions

Chaque snapshot contient aussi `catalogue.json`. Il recense les CSV réellement découverts pour la saison et conserve, pour chaque code, l'URL directe officielle utilisée. Les compétitions actuellement identifiables sont enrichies avec leur pays et leur nom. Un code nouveau ou non identifiable n'est jamais supprimé ni attribué arbitrairement : ses champs descriptifs restent `null` jusqu'à identification fiable. La découverte des fichiers reste dynamique afin de ne pas figer la couverture Football-Data.


## Correctif du 24/09/2026 — découverte par l'archive de saison

Vérifié sur la vraie page `downloadm.php` (capture `diagnostic/sources/`) : pour une saison, Football-Data ne publie
pas de liens CSV individuels mais une archive `mmz4281/<saison>/data.zip` contenant les CSV de toutes les divisions.
Si aucun lien CSV n'est trouvé, le collecteur prend cette archive (URL découverte sur la page, jamais construite),
en extrait les CSV dans `raw/` et enregistre la provenance dans le manifeste (`source_archive` : URL, SHA-256, taille,
nombre de CSV ; `source_url` de chaque fichier = `<archive>#<CODE>.csv`). Une seule requête par saison.

Déclenchement depuis l'iPhone : écrire la saison (ex. `2526`) dans `data/football_data/demande_snapshot.txt`.

## Championnats supplémentaires (24/09/2026) — toutes les divisions publiées

En plus des divisions de l'archive `data.zip`, le snapshot contient `<saison>/nouvelles_ligues/` : chaque championnat
publié en `new/<CODE>.csv` sur les pages pays liées depuis `all_new_data.php` (liens lus, jamais construits). Ces fichiers
contiennent toutes les saisons : seules les lignes de la saison sont conservées dans `raw/<CODE>.csv`, avec l'empreinte
du fichier téléchargé (`source_sha256`). Pays et nom viennent des colonnes `Country` et `League` du fichier lui-même.
Saison « 2526 » : lignes « 2025/2026 » pour un championnat à cheval sur deux années, « 2025 » pour un championnat sur
l'année civile. Un championnat sans ligne pour la saison est noté dans `empty` (jamais inventé). Manifeste, catalogue et
verrou propres : le snapshot principal déjà verrouillé n'est jamais modifié.

Journal des corrections : le 24/09/2026, le premier verrou `2526/nouvelles_ligues` (posé à 13:05 UTC) notait à tort
l'Argentine et le Japon « sans ligne » (changement de format de saison mal géré). Il a été supprimé avant toute
utilisation par le moteur, le filtre a été corrigé et testé, puis le snapshot refait une seule fois. Le snapshot
principal `2526/` (22 divisions) n'a pas été touché.


## Saison en cours — A2 (24/09/2026)

`collecte_football_data.py` (pipeline quotidien, et workflow `football_data_collecte.yml` pour un essai isolé) :

| Sortie | Contenu |
|---|---|
| `raw/<saison>/<DIV>.csv` | CSV des 22 divisions, extraits de `mmz4281/<saison>/data.zip` |
| `raw/<saison>/nouvelles_ligues/<CODE>.csv` | lignes de la saison en cours des championnats supplémentaires |
| `normalized/<saison>/<CODE>.jsonl` | une ligne par match (contrat ci-dessus ; `country`/`competition` pour les supplémentaires) |
| `manifest.json` | provenance, empreintes, ETag / Last-Modified, bilan du dernier run (`last_run`) |

Téléchargement seulement si la source a changé (requête conditionnelle, puis empreinte SHA-256 par division).
Chaque division porte `last_match_date` et `source_last_modified` : Football-Data publie les résultats avec 1 à 4 jours
de retard (constat du 24/09). Une source en panne est notée dans `last_run.errors` et ne bloque pas le pipeline.

**Décision de Patrick (24/09/2026) : aucune cote n'est collectée ici** (pas de comparaison de cotes entre bookmakers,
aucune API). Les colonnes de cotes des CSV restent dans les fichiers bruts et ne sont jamais utilisées.
Règle d'assemblage (précisée par Patrick le 24/09/2026) :
1. Championnat couvert par Football-Data : les matchs de Football-Data sont la base (données plus complètes : mi-temps,
   tirs, corners, cartons, xG). Matchendirect ne sert qu'à ajouter les JOURS manquants, c'est-à-dire les matchs joués
   après la dernière mise à jour de Football-Data (retard de 1 à 4 jours) ou absents de Football-Data.
2. Vérification des dates exactes, match par match : un match Matchendirect n'est ajouté que si l'équipe n'a AUCUN match
   Football-Data contre le même adversaire à ± 1 jour. Le ± 1 jour est obligatoire : un match joué tard le soir en heure
   locale (MLS, Brésil, Argentine…) peut porter la date du lendemain dans l'autre source. Jamais deux fois le même match.
3. Chaque match transmis au moteur porte sa source (football-data ou matchendirect) et sa date.
4. Championnat non couvert par Football-Data (Cymru Premier, Serie C, Eerste Divisie…) : Matchendirect seul, sous le
   contrôle nocturne `controle_saisons.py`.
5. Un marché dont une donnée nécessaire manque (ex. corners d'un match venu de Matchendirect) est écarté.
6. Remplacement automatique (précisé par Patrick le 24/09/2026) : un match ajouté depuis Matchendirect n'est que
   PROVISOIRE. Dès que Football-Data publie ce même match (même adversaire à ± 1 jour), c'est la version Football-Data qui
   est utilisée et la version Matchendirect disparaît. Pour que ce soit toujours vrai, l'assemblage n'est jamais stocké
   ni cumulé d'un run à l'autre : il est entièrement reconstruit à chaque run à partir des deux sources. Chaque match
   Matchendirect porte « provisoire : true ».
Prérequis : correspondance des noms d'équipes (A3) et conservation de la date et de l'adversaire de chaque match
Matchendirect (aujourd'hui seuls les buts sont gardés).


## A3 et A4 bis (24/09/2026) — sorties transmises au moteur

`assemblage_equipes.py` (workflow `journal.yml`, après le pipeline), reconstruit à chaque run :

- `data/correspondances/equipes.json` : pour chaque division Football-Data, son nom de compétition Matchendirect et,
  pour chaque équipe, son nom Matchendirect avec le nombre de preuves ; listes `ambigues` et `non_resolues`.
  Matchendirect est le pivot (les noms BetPawa y sont déjà reliés par le pipeline).
- `data/assemblage/equipes.json` : une entrée par équipe des matchs à venir (`cache_equipes_saison.json`), avec ses
  matchs de la saison en cours ; chaque match porte `source` (`football-data` ou `matchendirect`) et `provisoire`.
  Matchs Football-Data : mi-temps, tirs, tirs cadrés, corners, cartons, xG (quand publiés). Matchs Matchendirect :
  date, lieu, adversaire, buts, lien. Champ `raison` pour les équipes sans Football-Data (championnat non couvert,
  ou équipe pas encore reliée).


## A4 (24/09/2026) — contrôles qualité

`controle_football_data.py` → `data/controles/football_data.json` (page Système) : concordance des scores avec
Matchendirect sur les matchs communs (appariés par équipes reliées et date à ± 1 jour, sans regarder le score), doublons,
dates invalides ou futures, écarts de date. Critère : ≥ 98 % d'accord. Les désaccords sont listés, jamais corrigés.
Limite : les noms étant reliés à partir de scores identiques, le taux est optimiste par construction.
