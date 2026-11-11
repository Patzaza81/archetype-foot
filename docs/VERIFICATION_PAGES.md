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


## Analyse Verdict (`pronostics_verif.html`) — 11/11/2026

- **Page sur 7 jours** : `python verif_pronostic.py page` garde les matchs des 7 derniers jours (`JOURS_PASSES_PAGE`). Avant, seuls les matchs du jour et à venir étaient écrits : dès le lendemain les matchs disparaissaient et la recherche par date ne trouvait plus rien.
- **Sélections gelées** : la même commande gèle, avant le coup d'envoi, le pari du Top 20 de chaque match à venir et ses paris de l'onglet Règles (`data/verif_pronostics/journal_selections.jsonl`, ajout seul, empreintes chaînées). Une ligne n'est écrite que si la sélection change ; une liste vide note qu'un match est sorti d'une sélection. Le dernier état avant le coup d'envoi fait foi.
- **Bilan réel** : `bilan_selections()` (matchs terminés seulement), affiché dans le tableau de résultats de la page (lignes « Top 20 (recommandé) » et « Onglet Règles »), dès qu'un match gelé est terminé.
- `top20_page()` recalcule le Top 20 exactement comme `archetype_verif.js` (contrôlé le 11/11 sur 493 matchs : 107 sélections identiques). Le classement de la page n'est pas modifié.
- Le premier journal (`journal.jsonl` : 2 paris qui tiennent le mieux et 2 qui tiennent le moins bien par match) est inchangé.
