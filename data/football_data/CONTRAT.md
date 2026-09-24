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
