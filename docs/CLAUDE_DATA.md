# Instructions — données, saison et sources

## Données de saison

- Une saison d'équipe n'est lue que dans la section dont le **TITRE de compétition** correspond (`scraper_details._section_competition`). Interdit : ancrer sur un texte quelconque de la page (JavaScript compris) ou lire un tableau situé après le titre d'une autre compétition. En cas de doute : aucune donnée (NO DATA → NO GO), jamais une autre compétition.
- Toute saison lue est confrontée aux scores connus par les pages de match (`stats_saison_en_cours.controle_coherence`) ; une contradiction fait refuser l'équipe. Le contrôle nocturne `controle_saisons.py` publie le taux d'erreur (page Système).
- Toute modification de la lecture des pages se vérifie d'abord sur de vraies pages capturées (`diagnostic/`, `tests/fixtures/pages_equipes/`), jamais sur des pages imaginées.

## Sources de données — décisions du 24/09/2026

- Football-Data.co.uk est la source principale des données d'équipes pour les **38 divisions** qu'il publie (saisons terminées : `archive_football_data.py`, immuables ; saison en cours : `collecte_football_data.py`).
- Règle d'assemblage : pour un championnat couvert par Football-Data, les matchs Football-Data sont la base, avec leurs données plus complètes (mi-temps, tirs, corners, cartons, xG). Matchendirect ne sert qu'à ajouter les jours manquants, c'est-à-dire les matchs joués après la dernière mise à jour de Football-Data (retard de 1 à 4 jours) ou les matchs absents de Football-Data.
- Vérification exacte, match par match : un match Matchendirect n'est ajouté que si l'équipe n'a AUCUN match Football-Data contre le même adversaire à ± 1 jour. Le ± 1 jour est obligatoire car un match joué tard le soir en heure locale (MLS, Brésil, Argentine…) peut porter la date du lendemain dans l'autre source. Jamais deux fois le même match.
- Chaque match transmis au moteur porte sa source (football-data ou matchendirect) et sa date.
- Pour une compétition non couverte par Football-Data (Cymru Premier, Serie C, Eerste Divisie…), Matchendirect seul, sous contrôle nocturne de `controle_saisons.py`.
- Un marché dont une donnée nécessaire manque (ex. corners d'un match venu de Matchendirect) est écarté.
- Un match ajouté depuis Matchendirect est **PROVISOIRE**. Dès que Football-Data publie le même match (même adversaire à ± 1 jour), la version Football-Data remplace Matchendirect et la version Matchendirect disparaît. L'assemblage est entièrement reconstruit à chaque run à partir des deux sources ; chaque match Matchendirect porte « provisoire : true ».
- Prérequis : correspondance des noms d'équipes (A3) et conservation de la date et de l'adversaire de chaque match Matchendirect (aujourd'hui seuls les buts sont gardés).
- Aucune comparaison de cotes entre bookmakers, aucune API externe. Aucune cote n'est collectée depuis Football-Data.
- La collecte ne calcule rien : elle récupère, normalise, vérifie et transmet.
- Le moteur ne lit les données d'équipes que par `contrat_moteur.py` (`charge_assemblage`, `equipe`) ; tout changement de format passe par une nouvelle `VERSION_CONTRAT` + `docs/CONTRAT_MOTEUR.md` + `tests/test_contrat_moteur.py`.
