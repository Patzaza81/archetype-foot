# Moteur « selections » — qualifications Coupe du monde des sélections nationales (13/11/2026)

Demande de Patrick : un moteur adapté **uniquement** aux matchs de qualification à la Coupe du monde (Europe, Amérique, Afrique…), qui **fonctionne comme Analyse Verdict** (`verif_pronostic.py`).
État : cœur du moteur, branche `moteur-selections`, non fusionné. Rien n'est branché sur le pipeline, la collecte commune ou le site.

## Méthode (celle d'Analyse Verdict)

1. Cote ≥ 1,26 (règle de Patrick) et au moins 4 matchs au même lieu pour chaque équipe (domicile pour l'une, extérieur pour l'autre), sinon NON ÉVALUABLE.
2. Pour chaque pari : combien de fois il serait passé dans chaque échantillon. Plus souvent passé que raté des deux côtés = TIENT ; d'un seul côté = TIENT AVEC RÉSERVE ; sinon NE TIENT PAS.
3. Buts attendus = moyenne de ce que l'attaque marque et de ce que la défense adverse encaisse ; avantage du terrain des qualifications remis. Si l'attaque contre la défense confirme alors que les fréquences disent non, le verdict remonte d'un cran.
4. Mêmes primitives que Verdict, lues sans modification (`verif_pronostic` : catalogue des marchés, lecture des lignes, ajustement). Catalogue complet, combos double chance + total compris.

Différences imposées par les sélections nationales :
- **Terrain neutre** : NON ÉVALUABLE (ni domicile ni extérieur). Les matchs neutres n'entrent dans aucun échantillon.
- **Pas de xG** : la lecture xG reste indisponible (sans effet). Pas de règles par marché non plus (`verif_regles.py` : elles se calibrent sur les résultats gelés d'un moteur, pas encore disponibles ici).
- **Pas de « saison »** : échantillon = les matchs au même lieu dans une fenêtre de jours, avant le match (jamais le jour même).

## Réglages tirés des données (`etude_parametres.py`, résultats dans `data/selections/etude_parametres.json`)

Seuls deux réglages ne viennent pas des règles de Patrick : la fenêtre et le périmètre (tous les matchs ou officiels seulement, sans amicaux). Choisis sur les qualifications 2010-2017, contrôlés sur 2019-2026 (jamais utilisés pour choisir) :
- Mesure : erreur quadratique de la « force » du verdict sur 10 marchés courants, sur les mêmes matchs pour toutes les combinaisons.
- Une fenêtre de 1 an ne couvre que 32 % (tous) et 7 % (officiels) des matchs de qualification : écartée.
- Gain décroissant quand la fenêtre s'allonge ; au-delà de 5 ans, plus de différence mesurable. Retenu par parcimonie (la plus courte fenêtre indiscernable de la meilleure, à 1 erreur type) : **1 825 jours, matchs officiels seulement** (couverture 92 % en réglage, 96 % en contrôle ; c'est aussi la meilleure en contrôle).
- Les écarts entre les meilleures combinaisons sont petits (de l'ordre de 0,001 d'erreur quadratique) : la fenêtre n'est pas un levier majeur.

## Données

Historique : résultats internationaux publics et gratuits (GitHub `martj42/international_results`, `results.csv`), téléchargés par `donnees.telecharger()` ; le fichier n'est pas versionné. La collecte commune d'ARCHETYPE Foot exclut volontairement les sélections nationales (`precalcul.py`, `scraper_details.py`) : ce moteur a sa propre lecture et ne touche pas à cette exclusion.

## Limites connues

- Le calcul d'Analyse Verdict ne tient pas compte de la force des adversaires. En qualification les écarts de niveau sont grands : test préalable sur 1 767 matchs de qualification (2018-2026), la méthode « même lieu » seule était moins précise qu'un modèle de force des équipes (ex. victoire à domicile : erreur 0,600 contre 0,502). Piste d'amélioration à décider, non faite.
- Calendrier : le dernier match de qualification de la base est du 31/03/2026 (barrages 2026). Les qualifications 2030 sont annoncées pour septembre 2027 (CONCACAF, Wikipédia) ; un article évoque un tour préliminaire CAF dès mars 2026, non retrouvé dans les données.
- Aucune cote : la sélection jouable exige la cote Betpawa ≥ 1,26. Sans cotes, `paris()` liste les paris qui tiennent avec `cote = None` (aucune sélection jouable).

## Reste à faire (rien n'est fait)

Calendrier des matchs de qualification, cotes Betpawa de ces matchs, noms d'équipes (Matchendirect / Betpawa ↔ données publiques), journal gelé avant le coup d'envoi, page, étape du pipeline. Aucun bilan de performance avant d'avoir des matchs réellement gelés.

Tests : `tests/test_moteur_selections.py` (16 tests).
