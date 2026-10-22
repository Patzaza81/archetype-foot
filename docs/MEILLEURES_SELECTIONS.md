# Onglet « Meilleures sélections » (V2 et V3) — 22/10/2026

Onglet ajouté aux pages Moteur V2 et Moteur V3 : les sélections du jour qui appartiennent à un type de pari ayant battu les cotes dans l'historique.
**Recalibrage 100 % automatique, chaque semaine, sans intervention** (étape du pipeline nocturne, `python -m meilleures_selections.suivi pipeline`).

## Règle (meilleures_selections/regles.py)
- **Seuls comptent les indicateurs affichés sur le site et le résultat réel** : indice (x/4 ou x/2), pourcentage affiché (arrondi comme sur les pages), étoiles affichées (V2 : catégorie C/B/A = 1/2/3 ; V3 : taille d'échantillon = 1 à 4). Aucune cote, aucun rendement.
- **Règle testée** = « indice >= i ET pourcentage >= p ET étoiles >= e », par moteur : i dans 0, 1/4, 1/2, 3/4, 1 ; p dans 0, 60, 70, 80, 90 (tranches des tableaux de l'étude) ; e de 1 au maximum du moteur. 175 règles possibles (m), fixées par la structure.
- **Test** : test exact de Fisher entre les paris de la règle et tous les autres paris du même moteur (probabilité d'un tel écart par pur hasard) ; la règle doit aussi dépasser les autres paris dans **chacune des deux moitiés chronologiques**.
- **Confirmée** : p <= 0,05 / m (risque global de fausse admission d'au plus 5 %). **En observation** : p <= 1 / m.
- **Règle retenue par moteur** : celle qui a la meilleure **réussite garantie** (borne basse de l'intervalle de Wilson à 95 %, comme les tableaux de l'étude) ; à égalité, les critères les moins restrictifs. Si aucune règle ne passe, le moteur n'a pas de sélection (V3 manque aujourd'hui de données).
- **Échantillon V2** : seulement la version du moteur en production (celle du pari le plus récent, aujourd'hui 2.6.10).
- **Un pari par match et par famille de marché** dans le calibrage (celui de plus fort pourcentage affiché).
- Classement des sélections du jour : pourcentage affiché, puis indice, puis étoiles.
- Recalibrage : tous les 7 jours, sur les paris strictement antérieurs au jour. Quand les données changent, la règle change toute seule.

## Mesures affichées sur la page
- **Sur l'historique** : flatteur (ces paris ont servi à choisir).
- **Depuis le recalibrage** : paris joués après le choix (`historique_calibrations.json`, ajout seul) = la vraie mesure.
- **Rejeu** : même méthode appliquée au passé semaine par semaine, sans regarder l'avenir.
Chaque mesure est comparée à la réussite des autres paris du même moteur.

## Contrôle (evaluation/verifie_meilleures_selections.py)
Réimplémentation indépendante (pandas + scipy), rejeu nocturne, résultats mélangés au hasard (fausses admissions), avantage injecté, effondrement d'un type.

## Fichiers
`meilleures_selections/{regles,donnees,suivi}.py`, `data/meilleures_selections/{classement,historique_calibrations}.json`, `meilleures_selections.js`, `af-meilleures.css`, tests `tests/test_meilleures_selections.py`.
