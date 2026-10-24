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
- **Décision de Patrick (19/10/2026), qui LÈVE la règle du 24/09 pour l'évaluation et le calibrage** : les colonnes de cotes des CSV bruts Football-Data (Bet365, Pinnacle, Betfair, moyenne, maximum ; ouverture et clôture ; 1X2, plus/moins 2,5, handicap asiatique) peuvent être lues par des modules d'évaluation séparés (bancs de test, blocs de saisons : `matrice_scenarios/bloc_saisons.py`) pour juger et calibrer les moteurs. Inchangé : la couche de collecte ne normalise ni ne transmet aucune cote, et `contrat_moteur.py` n'en donne aucune à un moteur ; un pronostic n'est jamais calculé à partir d'une cote Football-Data.
- La collecte ne calcule rien : elle récupère, normalise, vérifie et transmet.
- Le moteur ne lit les données d'équipes que par `contrat_moteur.py` (`charge_assemblage`, `equipe`) ; tout changement de format passe par une nouvelle `VERSION_CONTRAT` + `docs/CONTRAT_MOTEUR.md` + `tests/test_contrat_moteur.py`.

## Dates des matchs de la nuit (correctif du 24/10/2026)

- Matchendirect liste les matchs de la nuit suivante (environ 00:00-07:00 heure française) à la fin de la page du jour D et en tête de la page D+1, avec le même match_id. Leur vraie date est D+1.
- Avant le correctif, la page D les datait du jour D : coup d'envoi 24 h trop tôt, match vu comme « déjà commencé » (Amériques, Japon, Corée, Australie, Nouvelle-Zélande, Océanie). Mesure du 24/10 : 124 matchs communs aux pages du 24 et du 25.
- Règle : `scraper.corrige_dates_minuit` — un match présent sur deux pages consécutives prend la date de la page la plus tardive ; date et heure du Cameroun recalculées ; date d'origine gardée dans `date_page`. Appliquée dans `scraper.py` (aujourd'hui/demain), `scraper_semaine.py` (J+2/J+3) et `precalcul.py` (fusion des trois fichiers).
- Limite : un match de la nuit qui suit la DERNIÈRE page lue n'a pas de seconde page comme preuve ; il est corrigé au passage suivant du pipeline.
- Tests : `tests/test_scraper_date_timezone.py`.
