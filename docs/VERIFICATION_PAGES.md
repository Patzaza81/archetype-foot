# Vérification des pages — branche `accueil-prototype` (13/10/2026)

Rien n'est fusionné ni déployé. `main`, les moteurs, leurs calculs, les données et les scripts des pages sont inchangés.

## 1. Pages adaptées : barre de navigation commune

Pages : `archetype.html` (V2), `pronostics_v3.html` (V3), `journal.html`, `panier.html`.

**Changement par page** : l'ancienne barre (« ← Accueil » + bouton nuit) est remplacée par la barre commune, et `af-barre.css` est ajouté. Le bouton nuit garde son id `ax-bouton-theme`, lu par le script de chaque page.

**Non modifiés** : les scripts, les blocs de pronostics, les styles des cartes.

| Contrôle (390 et 1 280 px, clair et nuit) | V2 | V3 | Journal | Panier |
|---|---|---|---|---|
| Contenu hors barre identique avant / après (empreinte du DOM) | oui | oui | oui | oui |
| Erreurs JavaScript | 0 | 0 | 0 | 0 |
| Défilement horizontal | 0 | 0 | 0 | 0 |
| Mode nuit mémorisé appliqué au chargement | oui | oui | oui | oui |
| Bouton nuit : bascule et mémorisation | oui | oui | oui | oui |
| Onglets du Journal (5) : s'affichent au clic | — | — | oui | — |

- Captures avant / après : `docs/apercus/pages/`.
- Tests ajoutés : `tests/test_barre_commune.py`. Il vérifie la présence de la barre, l'id du bouton conservé, les liens vers des pages existantes et que les scripts de chaque page sont exactement les mêmes. Suite complète : 1 918 tests réussis.

## 2. Vérification des 15 pages HTML

| Page | Erreurs JS | Débordement à 390 px | Mode nuit | Barre commune |
|---|---|---|---|---|
| accueil-prototype | 0 | 0 | oui | oui |
| archetype (V2) | 0 | 0 | oui | oui |
| pronostics_v3 | 0 | 0 | oui | oui |
| journal | 0 | 0 | oui | oui |
| panier | 0 | 0 | oui | oui (hors menu) |
| index | 0 | 0 | oui | non |
| tickets | 0 | 0 | oui | non |
| corners_cartons | 0 | 0 | oui | non |
| systeme | 0 | **10 px** | oui | non |
| compte | 0 | 0 | oui | non |
| abonnement | 0 | 0 | oui | non |
| inscription | 0 | 0 | oui | non |
| admin | 0 | 0 | oui (bouton masqué par l'écran de connexion) | non |
| betpawa-validation | 0 | 0 | **non** | non |
| presentation-site | 0 | 0 | **non** | non |

- Aucun lien vers une page `.html` inexistante.
- **Drapeaux** : seulement sur le prototype d'accueil (26 sélections sur 27 ; la 27e, Irlande du Nord, n'a pas de drapeau officiel). Les pages V2 et V3 affichent le pays en texte : y ajouter un drapeau demanderait de toucher leur script d'affichage. Ce n'est pas fait.

## 3. Restant, non fait (décision du propriétaire)

- Barre commune sur les pages qui chargent `theme.css` / `theme.js` (index, tickets, corners, système, compte, abonnement, inscription, admin). Leur bouton nuit est installé par `theme.js` dans leur en-tête ; il faut l'adapter page par page, avec la même méthode de vérification.
- `systeme.html` : 10 px de défilement horizontal à 390 px. Défaut déjà présent sur `main`, la page n'a pas été modifiée.
- `betpawa-validation.html` et `presentation-site.html` : pas de mode nuit.
