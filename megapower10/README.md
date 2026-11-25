# MEGAPOWER 10+ — moteur indépendant

Cette brique est indépendante d'ARCHETYPE Foot. Elle ne modifie aucun moteur existant et ne lit aucun flux de production. Elle reçoit des relevés de cotes horodatés et des résultats réglés, quel que soit le fournisseur.

## Contrat JSONL (une ligne = un prix réellement observé)

Champs obligatoires :

- `event_id`, `kickoff_utc` (ISO-8601 avec fuseau), `competition`, `market`, `selection` ;
- `bookmaker`, `captured_at_utc` (ISO-8601 avec fuseau), `odds` (cote décimale > 1) ;
- `result` (`true`, `false` ou `null` si non réglé), `source`.

Champs facultatifs : `phase` (prematch par défaut, inplay exclu), `model_probability`, `closing_odds`, `season`, `quote_id`.

Une ligne représente un prix effectivement observé chez un bookmaker. Il est interdit de fabriquer une cote « meilleure » en assemblant des prix non simultanés. Les marchés in-play sont séparés du pré-match. Toute cote enregistrée au coup d'envoi ou après est exclue.

## Premières commandes

```python
from megapower10 import load_jsonl, validate_quotes, evaluate
quotes = load_jsonl("quotes.jsonl")
check = validate_quotes(quotes)
print(check["input"], len(check["usable"]), check["errors"][:10])
print(evaluate(check["usable"], min_odds=10, max_odds=15))
```

## Règles statistiques

- Les bandes sont calculées séparément : <5, 5–8, 8–10, 10–15, 15–20, 20–30, 30–50, 50+.
- Le ROI est calculé à mise constante de 1 unité, sans prétendre intégrer les limites, commissions ou coûts non fournis.
- L'intervalle de Wilson accompagne chaque taux de réussite.
- Le découpage chronologique se fait sur le coup d'envoi. Les paramètres sont appris sur train, contrôlés sur validation, puis gelés avant test.
- Les compétitions et marchés sont conservés séparément ; aucune moyenne mondiale ne doit masquer les écarts.
- Les prix d'ouverture, prix à l'instant de décision et clôture sont des observations distinctes. Le champ `closing_odds` ne remplace jamais le prix exécutable à la prise.

## Limite actuelle

Le socle réalise l'ingestion, les contrôles temporels, les bandes de cotes et l'évaluation descriptive. Il ne contient pas encore de modèle prédictif ni de résultat de performance : ceux-ci ne seront ajoutés qu'après alimentation par des historiques réels et une validation chronologique.
