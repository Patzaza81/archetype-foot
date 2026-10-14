# Moteur v2r (V2 reconstruit)

- **Code** : `moteur_v2r/` (stdlib seulement). **Page** : `pronostics_v2r.html` + `archetype_v2r.js` (menu « V2R »). **Données** : `data/v2r/`.
- **Entrée** : uniquement `data/archive_test/` (cotes BetPawa, historiques, scores) -- aucun scraper propre. **Sortie** : uniquement `data/v2r/`.
- **Exécution** : chaque nuit, à la fin de `enregistre_scores_historique.py` (`moteur_v2r.execution.passage_nocturne`, dans un try : jamais bloquant).
- **Méthode** : une cellule = (libellé de marché, tranche de cote de 0,25, classe de buts du championnat, classe de buts attendus du match). On garde les cellules à ROI >= 30 % avec >= 10 paris sur l'échantillon d'entraînement ; un pari au maximum par match (meilleure cellule).
- **Règles figées** : `data/v2r/regles/regles_AAAA-MM-JJ.json`, jamais réécrites. Réentraînement le lundi, APRÈS le règlement du carnet. Changer la méthode = incrémenter `VERSION_METHODE` (`regles.py`) et mettre à jour ce document et les tests.
- **Carnet** (`data/v2r/carnet.json`) : un pari par match, écrit avant le coup d'envoi, figé ensuite, score ajouté une seule fois.
- **Statut** : `observation` (< 300 paris réglés, ne pas miser), `actif` (>= 300 réglés ET borne basse de l'IC95 du ROI > 0), `non_rentable` sinon. Le ROI sur échantillon (+56 %) n'est PAS une preuve prédictive ; seul le carnet compte.
- **Évaluation** : `python -m moteur_v2r.evaluation` (walk-forward) et `python -m moteur_v2r.integration` (ROI sur échantillon, non prédictif).
- Tests : `tests/test_moteur_v2r.py`, `test_echantillon_v2r.py`, `test_integration_v2r.py`, `test_v2r_autonome.py`, `test_v2r_integration_systeme.py`, `test_v2r_modere.py`.

## Variantes « marché modéré » (14/10/2026, `moteur_v2r/modere.py`)

- **Principe** : v2r choisit toujours le match et le marché (règles figées, carnet officiel : inchangés). Deux variantes remplacent ce marché par un marché de la même famille, **1 cran** ou **2 crans** plus prudent (ex. « Plus de 5.5 buts » -> « Plus de 3.5 buts » à 2 crans).
- **Plancher de cote 1,40 (décision de Patrick)** : si la cote finale est inférieure à 1,40, **on ne propose rien** (jamais de repli sur le pari d'origine). Un pari déjà écrit et devenu inférieur au plancher avant le coup d'envoi est retiré de la variante.
- **Familles** : total de buts et buts d'une équipe (Plus de L -> L-k, ligne minimale 0,5 ; Moins de L -> L+k), handicap (ligne + k), 1X2 victoire -> double chance, **nul -> double chance** (domicile ou extérieur : celle dont la cote est la plus proche du plancher en restant au-dessus ; aucune au-dessus -> rien), **les deux marquent « oui » -> Plus de 1,5 buts**, **cage inviolée -> Moins de (0,5+k) buts de l'adversaire**. Sans version modérée (aucun marché plus sûr n'est logiquement équivalent ; pari gardé tel quel, sous le même plancher) : les deux marquent « non », pair/impair, « encaisse au moins 1 but ». Marché modéré non coté : le pari d'origine est gardé.
- **Carnets séparés** : `data/v2r/modere1/carnet.json` et `data/v2r/modere2/carnet.json`, mêmes règles que le carnet officiel (écrit avant le coup d'envoi, figé ensuite, score ajouté une seule fois). Publiés dans `pronostics_v2r.json` sous la clé `modere` (`plancher`, `1_cran`, `2_crans` : `bilan`, `a_venir`, `reglees`). Une erreur est publiée dans `modere.erreur`, sans bloquer v2r.
- **Preuve** : test hors échantillon du 14/10 avec plancher 1,40 et les équivalents du nul / des deux marquent « oui » / de la cage inviolée (170 paris v2r, 09 au 12/10, règles apprises sur les jours précédents) : v2r +8 % (165 gardés), 1 cran +15 % (141 gardés), 2 crans +12 % (97 gardés), avec IC95 qui incluent 0, donc **non prouvé** ; seuls les carnets comptent, bilan à comparer sur les mêmes matchs.

## Statut SUPER FAVORI (14/10/2026, `moteur_v2r/super_favori.py`)

- **Indice en %** d'un pari modéré = moyenne de deux parts, **sur les buts seulement** : part des matchs de l'équipe à domicile, joués à domicile, où le pari aurait été gagné ; part des matchs de l'équipe à l'extérieur, joués à l'extérieur, où il aurait été gagné. **Indice >= 75 % -> SUPER FAVORI.** Pas de pire scénario, pas de Poisson.
- **Minimum** 3 matchs au lieu par équipe, sinon pas d'indice. **Sans indice** : nul, pair/impair, « encaisse au moins 1 but », handicap à ligne entière.
- **Autonome** : seules les données de v2r (historiques de l'archive). Information seulement : le choix du pari, la cote et les règles ne changent pas.
- **Carnets** : `indice_pct` et `super_favori` sont écrits dans la ligne du carnet modéré avant le coup d'envoi (figés ensuite). `pronostics_v2r.json` publie, par variante, `super_favori` : `seuil`, `bilan` (paris SUPER FAVORI réglés seuls), `a_venir` (nombre). Page : badge « SUPER FAVORI · 80 % », sinon « indice 62 % ».
- **Preuve** (test hors échantillon 09 au 13/10, règles apprises sur les jours précédents) : indice >= 75 % -> 1 cran 10 paris, 90 % de réussite, ROI +67 % ; 2 crans 10 paris, 80 %, ROI +77 %. **Échantillon trop petit pour conclure** : seul le carnet compte (statut observation tant que < 300 réglés). Le BTTS non n'a presque aucun historique de test : à surveiller.
- Tests : `tests/test_v2r_super_favori.py`.
