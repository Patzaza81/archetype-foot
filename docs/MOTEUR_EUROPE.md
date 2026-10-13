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
1. Collecte de l'historique européen par club (rien dans le dépôt aujourd'hui).
2. Archive de test avant-match européenne, puis entraînement du calibrateur.
3. Validation sur ≥ 100 matchs nouveaux avant tout verdict (règle du 27/09).
