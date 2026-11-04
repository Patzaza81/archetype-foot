# Branchement de la calibration P1 (mode parallèle)

## Constat à lire d'abord
- Le « P1 » calibré est le modèle de recherche `pouvoir_predictif.py` (Poisson attaque/défense, k et demi-vie par compétition).
- **Aucun moteur de production ne calcule ce P1** (v2.6.10, DC, omega, Gamma, Europe-Gamma, alpha_serie ont chacun leur modèle). Les calibrations ne valent que pour ce P1 : ne jamais les appliquer aux probabilités d'un moteur.
- Les 266 couples sont « P1 CONSERVÉ » : calibré = original, exactement.

## Point d'accroche (flux réel)
- `data/archive_test/<jour>.json.gz`, écrit chaque nuit par `archive_donnees_test.py` (déjà lu par alpha_serie et DC) : division Football-Data et noms FD des deux équipes déjà résolus.
- `integration_calibration.py` lit les matchs à venir (score absent, coup d'envoi futur), calcule P1 via `pouvoir_predictif.predire` (aucun calcul dupliqué), applique `calibration_p1.appliquer`/`appliquer_1x2`.
- Historique : archives 2122-2526 + `data/football_data/normalized/2627/<CODE>.jsonl`, strictement avant la date du match.

## Sorties (seules écritures)
- `data/calibration_p1/parallele/journal.jsonl` : une ligne gelée par match (p1_original, p1_calibre, méthode par marché, sommes 1X2, publie).
- `dernier_rapport.json`, `verification_38.json`.
- Mode dans `data/calibration_p1/integration.json` (`parallele` par défaut).

## Résultats du 04/11/2026
- 157 matchs à venir dans le flux ; 36 avec P1 (BRA 7, F2 5, E1 4, JPN 3, MEX 3, etc.) ; 121 hors périmètre (compétitions/équipes non couvertes par Football-Data : coupes, Europe, etc.).
- Écart max calibré − original = 0 ; somme 1X2 = 1 ; fichiers publiés (`data/*/pronostics.json`, `precalcul.json`, journaux) : empreinte SHA-256 identique avant/après.
- `python integration_calibration.py --verifier` : 38/38 compétitions avec 7 marchés, P1 calculable, 1X2 = 1, O1,5 ≥ O2,5 ≥ O3,5, identité.
- Échantillon : un seul jour de flux ; ce n'est pas une performance de moteur.

## Activation ultérieure
1. Une correction doit d'abord être « CORRECTION VALIDEE » par `calibration_finale.py` (protocole 2324/2425 sélection, 2526 confirmation).
2. Laisser tourner le mode parallèle ; comparer sur matchs terminés du journal gelé (règle CLAUDE.md : matchs réellement tournés).
3. Si gain confirmé : mettre `"mode": "actif"` dans `integration.json` (le champ `publie` prend alors la valeur calibrée). Le branchement à une page ou un moteur reste une décision séparée.
4. Retour arrière : remettre `"parallele"`.

## Tests
`pytest tests/test_integration_calibration.py tests/test_calibration_p1.py`
