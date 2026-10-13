# Moteur v2r (V2 reconstruit)

- **Code** : `moteur_v2r/` (stdlib seulement). **Page** : `pronostics_v2r.html` + `archetype_v2r.js` (menu « V2R »). **Données** : `data/v2r/`.
- **Entrée** : uniquement `data/archive_test/` (cotes BetPawa, historiques, scores) -- aucun scraper propre. **Sortie** : uniquement `data/v2r/`.
- **Exécution** : chaque nuit, à la fin de `enregistre_scores_historique.py` (`moteur_v2r.execution.passage_nocturne`, dans un try : jamais bloquant).
- **Méthode** : une cellule = (libellé de marché, tranche de cote de 0,25, classe de buts du championnat, classe de buts attendus du match). On garde les cellules à ROI >= 30 % avec >= 10 paris sur l'échantillon d'entraînement ; un pari au maximum par match (meilleure cellule).
- **Règles figées** : `data/v2r/regles/regles_AAAA-MM-JJ.json`, jamais réécrites. Réentraînement le lundi, APRÈS le règlement du carnet. Changer la méthode = incrémenter `VERSION_METHODE` (`regles.py`) et mettre à jour ce document et les tests.
- **Carnet** (`data/v2r/carnet.json`) : un pari par match, écrit avant le coup d'envoi, figé ensuite, score ajouté une seule fois.
- **Statut** : `observation` (< 300 paris réglés, ne pas miser), `actif` (>= 300 réglés ET borne basse de l'IC95 du ROI > 0), `non_rentable` sinon. Le ROI sur échantillon (+56 %) n'est PAS une preuve prédictive ; seul le carnet compte.
- **Évaluation** : `python -m moteur_v2r.evaluation` (walk-forward) et `python -m moteur_v2r.integration` (ROI sur échantillon, non prédictif).
- Tests : `tests/test_moteur_v2r.py`, `test_echantillon_v2r.py`, `test_integration_v2r.py`, `test_v2r_autonome.py`, `test_v2r_integration_systeme.py`.
