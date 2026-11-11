"""Sources de calendrier d'ARCHETYPE Foot (11/11/2026) : une seule porte d'entrée pour savoir « quels matchs se jouent tel jour », quelle que soit la source.

HIÉRARCHIE (config/sources_calendrier.json, une seule liste, lue dans l'ordre) :
  1. matchendirect : source principale (scraper.py et scraper_semaine.py, inchangés) ;
  2. espn          : flux public d'ESPN, sans clé, environ 250 championnats, non officiel ;
  3. openfootball  : fichiers libres sur GitHub, quelques grands championnats, impossible à bloquer mais peu mis à jour.

RÈGLES (les mêmes pour toutes les sources, pour éviter doublons et confusions) :
  - chaque source rend des `Match` au MÊME format (modele.py) : aucun autre module ne lit le format brut d'une source ;
  - une source ne plante jamais le reste : elle rend ses matchs ET la liste de ses erreurs (jamais un silence) ;
  - deux matchs sont « le même » seulement si les DEUX équipes concordent et que les jours sont voisins (rapprochement.py) ;
    un match de référence n'est rapproché qu'à UN match d'une source et inversement ; en cas de doute (deux candidats) : « ambigu », jamais un choix au hasard ;
  - équipes féminines, de jeunes et réserves ne sont jamais confondues avec l'équipe première (noms.py) ;
  - les différences de nom entre sources se corrigent dans UN fichier : config/sources_noms.json.

MODE ACTUEL : « mesure ». `python -m sources_calendrier.mesure` compare chaque nuit les sources 2 et 3 à Matchendirect et écrit data/sources_calendrier/.
Rien n'alimente encore le système : on branche une source de secours seulement quand sa mesure est bonne.
"""
