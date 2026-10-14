# V2R : registre des décisions de conception (créé le 14/10/2026)

**Constat (Patrick, 14/10/2026) : les raisons des choix de conception de V2R ne sont écrites nulle part.**
Ce document sépare ce qui est vérifiable dans le code de ce qui reste à documenter. Il n'invente aucune justification.

## Paramètres actuels (vérifiés dans le code)

| Décision | Valeur | Où | Justification documentée |
|---|---|---|---|
| Ligne minimale d'une cellule | 10 paris | `regles.CONFIG["min_paris"]` | **Non documentée** |
| ROI minimal d'une cellule (sur échantillon) | 30 % | `regles.CONFIG["roi_min"]` | **Non documentée** |
| Paris par match | 1 (meilleur ROI de cellule) | `regles.CONFIG["max_par_match"]`, `pronostics.proposer` | **Non documentée** |
| Largeur d'une tranche de cote | 0,25 | `echantillon.PAS_COTE` | **Non documentée** |
| Coupures de la classe de championnat (buts/match) | 2,5 et 2,9 | `integration.COUPURES_LIGUE` | **Non documentée** |
| Coupures de la classe de match (buts attendus) | 2,4 et 3,0 | `integration.COUPURES_MATCH` | **Non documentée** |
| Modèle de buts | Poisson, `k0=1.0, wsame=0.3, s=0.7, d=0.0` | `modele.PARAMS` | **Non documentée** |
| Seuil de statut « actif » | 300 paris réglés et borne basse IC95 > 0 | `carnet.SEUIL_PARIS`, `carnet.statut` | Règle de prudence écrite dans `docs/V2R.md` |
| Réentraînement | le lundi, après règlement du carnet | `regles.doit_reentrainer` | Écrit dans `docs/V2R.md` |
| Plancher de cote des variantes modérées | 1,40 | `modere.PLANCHER_COTE` | Décision de Patrick (14/10/2026) |
| Seuil SUPER FAVORI | 75 % | `super_favori.SEUIL` | Décision de Patrick (14/10/2026) |

Changer un paramètre de `CONFIG` exige d'incrémenter `VERSION_METHODE` (`regles.py`), de mettre à jour ce document, `docs/V2R.md` et les tests.

## Échantillon de conception (décrit par Patrick, 14/10/2026 ; chiffres vérifiés dans le dépôt)

- **Définition (Patrick)** : tous les matchs du système ARCHETYPE avec les cotes des différents marchés, les historiques des deux équipes pour chaque match et les résultats ; **les matchs d'hier (13/10) exclus**.
- **Dans le code** (`donnees.charge`) : matchs de `data/archive_test/` avec score, cotes observées et historiques des deux équipes, un historique étant limité aux matchs antérieurs au match.
- **Taille réelle** : 889 matchs, du 28/09/2026 au 13/10/2026 (16 jours, très inégaux : 16 matchs le 08/10, 258 le 10/10, 50 le 12/10, 35 le 13/10). Avant le 13/10 : 854 matchs.
- **ECART A TRANCHER** : `data/v2r/regles/regles_2026-10-14.json` indique `entraine_sur = 889` et `jusqu_au = 2026-10-13` : les règles en production **incluent déjà les matchs du 13/10**. Si l'intention était de les exclure, ces règles ne respectent pas la définition ci-dessus. Cela ne fausse pas le carnet (ses paris sont des matchs du 14/10 et après, figés avant le coup d'envoi) mais le 13/10 ne peut plus servir de test avec ces règles : `backtest.py` réentraîne avant le jour testé pour cette raison. Règles figées : on ne les réécrit pas sans décision de Patrick.
- **Taille** : 889 matchs, c'est peu pour des cellules à 4 dimensions (41 cellules retenues, chacune sur 10 paris ou un peu plus).

## Données de l'échantillon (mesurées le 14/10/2026 par `python -m moteur_v2r.sensibilite`)

- **Contenu** : 889 matchs réglés, du 28/09/2026 au 13/10/2026, 119 championnats, en moyenne 33,8 marchés cotés par match. Les 889 ont les historiques des deux équipes.
- **Matchs par jour** : 28/09: 6 · 29/09: 14 · 30/09: 7 · 01/10: 2 · 02/10: 5 · 03/10: 93 · 04/10: 63 · 05/10: 16 · 06/10: 2 · 07/10: 13 · 08/10: 16 · 09/10: 96 · 10/10: 258 · 11/10: 213 · 12/10: 50 · 13/10: 35. Quatre jours (03/10, 09/10, 10/10, 11/10) pèsent 74 % de l'échantillon (3 jours de week-end plus un vendredi) : les cellules reflètent surtout les championnats de ces jours-là.
- **Règles du 13/10** : 851 matchs, jusqu'au 12/10, 43 cellules. **Règles du 14/10** : 889 matchs, jusqu'au 13/10, 41 cellules.
- **Cellules du 14/10** : 41 cellules, 628 paris au total ; 10 à 52 paris par cellule (médiane 12) ; 22 cellules sur 12 paris ou moins ; ROI de cellule de +31 % à +129 % (médiane +44 %). Marchés les plus fréquents : 1X2 nul (6), BTTS non (5), Plus de 4.5 buts (5), Moins de 0.5 buts (3).

## Test de sensibilité (test à l'aveugle, un paramètre à la fois)

Méthode : moteur officiel rejoué du 06/10 au 13/10 (8 jours), règles réapprises avant chaque jour avec les seuls matchs précédents ; ROI sur le pari officiel, IC95 par match. **Limites** : réentraînement quotidien (production : le lundi), premiers jours testés avec très peu de matchs d'entraînement, tests non indépendants (mêmes matchs).

| Paramètre testé | Paris | ROI | IC95 |
|---|---|---|---|
| Base (10 paris, ROI 30 %, tranche 0,25) | 196 | +6,5 % | −14 % à +28 % |
| min_paris = 5 | 425 | −8,5 % | −23 % à +7 % |
| min_paris = 20 | 60 | −15,5 % | −47 % à +23 % |
| roi_min = 0 % | 609 | −8,1 % | −18 % à +1 % |
| roi_min = 15 % | 424 | −4,0 % | −15 % à +9 % |
| roi_min = 45 % | 89 | +8,5 % | −27 % à +44 % |
| tranche 0,20 | 179 | −2,3 % | −20 % à +16 % |
| tranche 0,50 | 255 | −5,2 % | −23 % à +14 % |

Lecture (faits, pas opinions) : tous les IC95 contiennent 0 ; le ROI est positif seulement pour la base et roi_min = 45 %, et il change de signe dès qu'on bouge un paramètre ; aucune valeur ne se distingue du hasard sur 8 jours. Les coupures de buts (2,5/2,9 et 2,4/3,0) et le modèle de Poisson n'ont pas été testés : `sensibilite.rejoue_avec` accepte `coupures_ligue` et `coupures_match` pour le faire.

Pour refaire ces mesures ou ajouter un essai : `python -m moteur_v2r.sensibilite` (outil d'étude, ne modifie ni le moteur ni les fichiers de `data/v2r/`).

## Limites connues de la méthode (constatées dans le code, pas des opinions)

- Les cellules sont retenues sur leur ROI **sur l'échantillon qui les a produites** : un ROI élevé sur peu de paris (surtout à grosse cote) peut venir du hasard. Un ROI sur échantillon n'est pas une preuve prédictive.
- Le choix du « meilleur ROI de cellule » parmi plusieurs marchés d'un match favorise les cellules chanceuses.
- Le test de sensibilité du 14/10/2026 (ci-dessus) ne couvre que min_paris, roi_min et la largeur de tranche, sur 8 jours.

## A compléter par Patrick

Pour chaque ligne marquée « Non documentée » : pourquoi cette valeur, quelles autres valeurs ont été essayées, sur quel échantillon (dates, nombre de matchs). Tant que ce n'est pas rempli, ces valeurs sont des **paramètres hérités, non justifiés**.

## Preuves disponibles

- Test à l'aveugle, règles apprises avant chaque jour : `python -m moteur_v2r.backtest AAAA-MM-JJ ...` (résultats dans `docs/V2R.md`).
- Seul le carnet (`data/v2r/carnet.json`) mesure la rentabilité réelle.
