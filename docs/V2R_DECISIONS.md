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

## Limites connues de la méthode (constatées dans le code, pas des opinions)

- Les cellules sont retenues sur leur ROI **sur l'échantillon qui les a produites** : un ROI élevé sur peu de paris (surtout à grosse cote) peut venir du hasard. Un ROI sur échantillon n'est pas une preuve prédictive.
- Le choix du « meilleur ROI de cellule » parmi plusieurs marchés d'un match favorise les cellules chanceuses.
- Aucun test de sensibilité des paramètres ci-dessus n'est archivé.

## A compléter par Patrick

Pour chaque ligne marquée « Non documentée » : pourquoi cette valeur, quelles autres valeurs ont été essayées, sur quel échantillon (dates, nombre de matchs). Tant que ce n'est pas rempli, ces valeurs sont des **paramètres hérités, non justifiés**.

## Preuves disponibles

- Test à l'aveugle, règles apprises avant chaque jour : `python -m moteur_v2r.backtest AAAA-MM-JJ ...` (résultats dans `docs/V2R.md`).
- Seul le carnet (`data/v2r/carnet.json`) mesure la rentabilité réelle.
