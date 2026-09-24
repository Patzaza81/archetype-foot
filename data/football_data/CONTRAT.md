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

## Archive historique annuelle — A1

À partir de la décision d'architecture A1, les saisons terminées sont archivées
comme snapshots complets dans `data/football_data/snapshots/<saison>/`.
Le snapshot contient tous les CSV Football-Data découvrables pour la saison,
classés par division/compétition, avec manifeste SHA-256 et verrou
`_SNAPSHOT_COMPLETE.json`.

Un snapshot marqué COMPLETE est **immuable** : aucun téléchargement quotidien,
aucun remplacement silencieux et aucune fusion avec une autre saison. En cas
d'archive incomplète, seuls les fichiers manquants peuvent être ajoutés ; les
fichiers déjà présents ne sont jamais écrasés.

Le premier snapshot réel doit être exécuté et contrôlé dans GitHub Actions avant
que l'archive soit considérée comme validée en conditions réelles.

Le moteur doit lire ces snapshots localement. La collecte historique et la
collecte opérationnelle de la saison courante sont deux flux distincts.
