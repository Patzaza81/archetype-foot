# Instructions — données, saison et sources

## Données de saison

- Une saison d'équipe n'est lue que dans la section dont le TITRE de compétition correspond (`scraper_details._section_competition`). Interdit : ancrer sur un texte quelconque de la page (JavaScript compris) ou lire un tableau après le titre d'une autre compétition. En cas de doute : NO DATA → NO GO.
- Toute saison lue est confrontée aux scores connus par les pages de match (`stats_saison_en_cours.controle_coherence`) ; une contradiction fait refuser l'équipe. Le contrôle nocturne `controle_saisons.py` publie le taux d'erreur.
- Toute modification de lecture des pages se vérifie d'abord sur de vraies pages capturées (`diagnostic/`, `tests/fixtures/pages_equipes/`), jamais sur des pages imaginées.

## Sources de données — décisions du 24/09/2026

- Football-Data.co.uk est la source principale pour les 38 divisions qu'il publie (`archive_football_data.py` pour les saisons terminées immuables ; `collecte_football_data.py` pour la saison en cours).
- Pour une compétition couverte par Football-Data : Football-Data est la base. Matchendirect ajoute uniquement les jours manquants (retard de 1 à 4 jours) ou les matchs absents.
- Vérification exacte, match par match : un match Matchendirect n'est ajouté que si l'équipe n'a aucun match Football-Data contre le même adversaire à ±1 jour. Jamais deux fois le même match.
- Chaque match transmis au moteur porte sa source et sa date.
- Pour une compétition non couverte par Football-Data : Matchendirect seul, sous contrôle nocturne de `controle_saisons.py`.
- Un marché dont une donnée nécessaire manque est écarté.
- Un match ajouté depuis Matchendirect est PROVISOIRE. Dès que Football-Data publie le même match (même adversaire à ±1 jour), la version Football-Data remplace Matchendirect. L'assemblage est entièrement reconstruit à chaque run ; chaque match Matchendirect porte « provisoire : true ».
- Prérequis : correspondance des noms d'équipes et conservation de la date et de l'adversaire de chaque match Matchendirect.
- Aucune comparaison de cotes entre bookmakers, aucune API externe. Aucune cote n'est collectée depuis Football-Data.
- La collecte ne calcule rien : elle récupère, normalise, vérifie et transmet.
- Le moteur ne lit les données d'équipes que par `contrat_moteur.py` (`charge_assemblage`, `equipe`) ; tout changement de format passe par une nouvelle `VERSION_CONTRAT` + `docs/CONTRAT_MOTEUR.md` + `tests/test_contrat_moteur.py`.
