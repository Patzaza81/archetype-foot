# Harmonisation visuelle des pronostics V2 et V3 — rapport

Branche : `accueil-prototype` · `main` non modifié · aucune fusion, aucun déploiement.

## Principe

Couche de présentation séparée, chargée **après** `archetype.css` :

- elle ne s'applique qu'aux pages marquées `af-v2` (archetype.html) ou `af-v3` (pronostics_v3.html) ;
- le panier et les autres pages qui chargent `archetype.css` ne sont pas concernés ;
- elle ne change que les couleurs, les bordures, les rayons, les ombres et la typographie ;
- elle ne contient aucune règle qui masque, ajoute ou déplace un contenu (vérifié par test).

`archetype.js`, `archetype_v3.js`, les données, les calculs, les cotes, les onglets et les détails sont inchangés.

## Fichiers

| Fichier | Nature |
|---|---|
| `af-pronostics.css` | nouveau : couche visuelle (jetons de l'accueil, clair et nuit) |
| `af-drapeaux-cartes.js` | nouveau : ajoute le drapeau du **pays du championnat** devant le libellé de compétition (span `aria-hidden`), via `drapeaux.js` |
| `archetype.html`, `pronostics_v3.html` | 1 lien CSS, classe `af-v2` / `af-v3` sur `body`, 2 scripts de présentation après les scripts métier |
| `tests/test_harmonisation_pronostics.py` | nouveau : périmètre de la couche, aucun masquage, panier exclu, script des drapeaux limité au libellé |
| `tests/test_barre_commune.py` | adapté : scripts métier identiques et dans le même ordre ; seuls `drapeaux.js` et `af-drapeaux-cartes.js` sont autorisés en plus, après eux |

## Présentation façon accueil (13/10, demande de Patrick)

Les cartes reprennent la présentation des lignes de ticket de l'accueil, en CSS seul (grille et `display:contents`), sans modifier le HTML produit par les scripts :

- **En-tête** :
  - heure et date dans une colonne à gauche ;
  - à droite : drapeau et compétition en gris, puis les deux équipes en gras.
- **Onglets** : P1/P2/P3 en pastilles.
  - Onglet actif : sarcelle.
  - Onglet disponible : fond clair.
  - Onglet vide : contour pointillé, texte lisible.
- **Sélection, carte repliée et dépliée** :
  - ligne sur fond gris-vert clair ;
  - marché en sarcelle, cote en gros à droite ;
  - justification et indice en dessous.
- **Bandeau** : couleur exacte du bandeau de l'accueil (`#0F2A28`).

Vérifié de nouveau à 390, 414 et 1 280 px, en clair et en nuit :

- **Données** : texte, HTML et cotes identiques ;
- **Fonctionnement** : 0 erreur, 0 débordement ; onglets, dépliage, détails et mode nuit fonctionnent ;
- **Noms d'équipe** : 0 nom coupé de 320 à 1 280 px.

## Ce qui change à l'écran (première version)

- Rose (#D94F91) remplacé par le sarcelle de l'accueil (#087F78 / #06645F), fond crème, cartes blanches.
- Rayons ramenés de 22 px à 14 px (cartes) et de 12–14 px à 10 px (blocs, boutons), ombres plus légères.
- Pastille de cote dorée claire (même valeur, chiffres alignés).
- Les onglets 2 et 3 ont désormais deux teintes distinctes ; avant, ils avaient exactement la même couleur rose.
- Drapeau du championnat devant la compétition :
  - V2 : 68 cartes sur 69 ; pas de drapeau pour « Irlande du Nord », qui n'a pas de drapeau officiel ;
  - V3 : 20 cartes sur 20 ;
  - les compétitions continentales affichent un globe.

## Vérifications effectuées

Navigateur Chromium (Playwright), serveur local. Pour chaque page : 390, 414 et 1 280 px, en clair et en nuit, soit 6 cas par page.

| Contrôle | V2 (69 cartes) | V3 (20 cartes) |
|---|---|---|
| Texte des cartes identique à avant (empreinte) | ✅ 6/6 | ✅ 6/6 |
| HTML des cartes identique à avant (hors drapeau) | ✅ 6/6 | ✅ 6/6 |
| Cotes affichées identiques | ✅ 250 cotes, 6/6 | ✅ 42 cotes, 6/6 |
| Erreurs JavaScript | 0 | 0 |
| Débordement horizontal | 0 px | 0 px |
| Dépliage de la carte au toucher | ✅ | ✅ |
| Changement d'onglet et panneau visible, puis retour | ✅ | ✅ |
| « Détails de l'analyse » s'ouvre | ✅ | ✅ |
| Bouton mode nuit (classe et mémorisation) | ✅ | ✅ |
| Drapeau = pays écrit dans la compétition | ✅ 68/68 | ✅ 20/20 |

Tests : `pytest`, suite complète, **1 925 réussis, 0 échec**.

## Captures

Elles se trouvent dans `docs/apercus/harmonisation/` :

- `v2_iphone_avant_apres.jpg` et `v3_iphone_avant_apres.jpg` : 390 px, clair et nuit ;
- `v2_ordinateur_avant_apres.jpg` et `v3_ordinateur_avant_apres.jpg` : 1 280 px ;
- `v2_carte_detaillee_avant_apres.jpg` et `v3_carte_detaillee_avant_apres.jpg` : carte dépliée avec détails ouverts.

## Défauts restants (non corrigés, préexistants)

- ~~Noms d'équipe coupés au milieu d'un mot~~ : **corrigé**. La cause était commune aux deux couches : colonne horaire fixe de 84 px et nom à 17 px.
  - Mesure avant correction : à 360 px, jusqu'à 13 noms coupés sur 138 en V2 (14 avec la couche `ax-accueil-theme.css`) et 3 sur 40 en V3. À 390 px : 5 en V2, 1 en V3.
  - Correction, téléphone uniquement : horaire à 58 px, marges réduites, taille du nom proportionnelle à l'écran (14 à 17 px), `overflow-wrap:break-word`.
  - Résultat mesuré : 0 nom coupé à 360, 390, 414 et 1 280 px, cartes repliées et dépliées. L'heure reste sur une ligne et aucun texte n'est masqué.
- `systeme.html` déborde de 10 px à 390 px. `betpawa-validation.html` et `presentation-site.html` n'ont pas de mode nuit.
- Huit pages basées sur `theme.js` n'ont pas encore la barre commune.
- Le drapeau anglais, écossais ou gallois (séquence d'étiquettes) peut s'afficher comme un drapeau noir sur certains anciens Android ou Windows 10.
