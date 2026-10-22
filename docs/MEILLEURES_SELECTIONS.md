# Onglet « Meilleures sélections » (V2 et V3) — 22/10/2026

Onglet ajouté aux pages Moteur V2 et Moteur V3 : les sélections du jour qui appartiennent à un type de pari ayant battu les cotes dans l'historique.
**Recalibrage 100 % automatique, chaque semaine, sans intervention** (étape du pipeline nocturne, `python -m meilleures_selections.suivi pipeline`).

## Règle (meilleures_selections/regles.py)
- **Unité testée** : (moteur, famille de marché, palier d'indice). Un ensemble = les paris de la famille dont l'indice (indice / sur) est au moins égal au palier.
- **Base d'un pari** = 1 / cote. **Test** = probabilité exacte (loi binomiale) d'obtenir au moins autant de paris gagnés par pur hasard.
- Un ensemble est admis s'il : gagne plus que sa base, rapporte à mise égale, et dépasse sa base dans **chacune des deux moitiés chronologiques**.
- **Confirmé** : p <= 1/m. **En observation** : p <= 1/racine(m). m = paliers réellement atteignables sur les deux moteurs (88 : 7 familles à deux équipes × 5 paliers + 3 familles d'une équipe × 3 paliers, par moteur ; le nul n'a pas d'indice), fixé par la structure, jamais par la quantité de données.
- **Échantillon V2** : seulement la version du moteur en production (celle du pari le plus récent, aujourd'hui 2.6.10) ; une nouvelle version repart de ses propres paris.
- **Un pari par match et par famille** dans le calibrage (celui de plus forte probabilité affichée) : les paris d'un même match ne sont pas indépendants.
- Par (moteur, famille) : l'ensemble admis **le plus large** (aucun choix sur le gain).
- Classement : confirmés d'abord, puis p le plus bas, puis indice, probabilité, cote.
- Recalibrage : tous les 7 jours (sur les paris strictement antérieurs au jour). Un type qui cesse de gagner sort ; un autre peut entrer.

## Mesures honnêtes affichées sur la page
- **Sur l'historique** : flatteur (ces paris ont servi à choisir).
- **Depuis le recalibrage** : paris joués après le choix (`historique_calibrations.json`, ajout seul) = la vraie mesure.
- **Rejeu** : même méthode appliquée au passé semaine par semaine, sans regarder l'avenir.

## Limites constatées (evaluation/verifie_meilleures_selections.py)
- Avec des résultats tirés au hasard (probabilité 1 / cote), le filtre « en observation » laisse passer environ 2 groupes par recalibrage ; « confirmé » environ 0,2. Les groupes « en observation » ne sont donc pas des preuves.
- Au 22/10/2026 aucun groupe n'est « confirmé » : archive de 24 jours.

## Fichiers
`meilleures_selections/{regles,donnees,suivi}.py`, `data/meilleures_selections/{classement,historique_calibrations}.json`, `meilleures_selections.js`, `af-meilleures.css`, tests `tests/test_meilleures_selections.py`.
