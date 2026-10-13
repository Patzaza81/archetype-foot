# Moteur Europe (LdC, Europa League, Conférence) — 13/10/2026

Branche isolée `moteur-europe`. Aucun fichier V2/V3, pipeline, workflow ou donnée modifié. Code : `moteur_europe/`. Tests : `tests/test_moteur_europe.py`.

## Principe (décision de Patrick)
- Historique européen du club 70 % + championnat 30 %, 3 matchs minimum, 6 maximum, par source, au MÊME LIEU (domicile pour l'hôte, extérieur pour le visiteur).
- Calcul V3 : chaque source est lissée vers 1,35 (K = 4) selon sa taille, puis mélangée 70/30 ; buts attendus = attaque × défense adverse / 1,35 ; Poisson ; mêmes marchés pleins temps (`derive_markets`).
- Mêmes filtres que V3 : cote 1,26–1,74, probabilité ≥ 60 %, seuils de marge, dispersion, calibration obligatoire, une sélection par exposition, 3 au maximum.
- Moins de 3 matchs européens ou de championnat au lieu voulu : match non évalué (NO DATA → NO GO), jamais de repli sur une seule source.
- Mi-temps non calculée (données absentes côté européen).

## Double contrôle
Appliqué à l'historique européen (bloquant). Le même contrôle sur le championnat est calculé à titre d'information (`CONTROLE_CHAMPIONNAT_BLOQUANT = False`). Écart assumé avec la règle 1.1.0 « même compétition seulement ».

## Indice de performance (version 4)
Profil moyen = moyenne pondérée 70/30 ; pire match = cherché dans tous les matchs utilisés. Information seulement.

## Calibration
Calibrateur Europe séparé, appris seulement sur des matchs européens joués avant la date, ≥ 300 observations et ≥ 50 matchs. Pas de calibration : pas de sélection.

## Reste à faire avant tout usage
1. Collecte de l'historique européen par club : écrite (`collecte_europe.py`, voir plus bas), à tester en réel hors de cet environnement.
2. Archive de test avant-match européenne, puis entraînement du calibrateur.
3. Validation sur ≥ 100 matchs nouveaux avant tout verdict (règle du 27/09).

## Collecte des données européennes (`collecte_europe.py`)

Module isolé : il n'est branché sur aucun workflow et ne modifie aucun scraper existant.

- **Matchs à venir** : lus dans `data/archive_test/*.json.gz`. Compétition reconnue seulement si le titre commence par « Europe : » et
  vaut Ligue des Champions, Ligue Europa ou Ligue Conférence. Refusés : jeunes, féminin, qualifications, préliminaires, amicaux.
- **Cotes BetPawa** : déjà résolues par le pipeline Playwright existant (liste blanche européenne dans `precalcul.py`). Pas de second scraping.
- **Historique Matchendirect** : page de chaque club, via `scraper_details`. Sections « Europe : … » (toutes les coupes d'Europe) +
  championnat national (rubrique nationale avec le plus de matchs ; égalité ou absence → `CHAMPIONNAT_AMBIGU` / `CHAMPIONNAT_INTROUVABLE`, donc NO GO).
- **Saison précédente** : demandée via `?season=`. Si le site renvoie la même page, elle est ignorée (`ignoree_par_le_site`). Chaque ligne porte sa `saison`.
- **Anti-fuite** : seuls les matchs strictement antérieurs au jour du match sont gardés. Une ligne sans date est écartée et comptée, jamais devinée.
- **Sortie** : `data/europe/entrees_europe.json` (entrée du moteur + couverture + `evaluable`) et cache `data/europe/cache_clubs.json` (1 chargement/club/jour).
- **Lancer** : `python collecte_europe.py [--archive ... --sortie ... --cache ...]`.

Limites connues :
- Couverture : sur l'archive de test, 1 match sur 50 avait ≥ 3 matchs européens au bon lieu pour les deux clubs (saison courante seule).
- Les tours de qualification portent le même titre que la phase de ligue sur la page club : impossible de les séparer.
- Utiliser la saison précédente contredit la règle V3 « pas de saison précédente » : décision à confirmer.
- Le scraping réel n'a pas pu être testé ici (Matchendirect bloqué depuis cet environnement) : validé sur pages enregistrées et faux fetch.
