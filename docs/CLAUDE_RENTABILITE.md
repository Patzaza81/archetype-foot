# Instructions — journal de rentabilité

`journal_rentabilite.py → journal.json → journal.html`

- Ce n'est pas un moteur. Le journal règle les cotes BetPawa réellement relevées sur les scores finaux. Il ne doit jamais importer ni recalculer `moteur_v2_6_9` ou `shrink_v1` ; il lit seulement leurs choix.
- Affichage : statistiques gagnantes uniquement. Tout ROI négatif est calculé (statuts `A_EVITER`, `NEUTRE`) mais n'est jamais affiché. La colonne « Niveau » (Prouvé / À surveiller / Non confirmé) est obligatoire.
- Conseil sur un match à venir = même championnat ET même marché. Le segment championnat × marché doit être `A_JOUER` ou `A_SURVEILLER`, et la cote du jour doit être entre `cote_min` et `cote_max` du segment (`verdict_marche`). Interdit : moyenne tous championnats ou famille de marchés.
- Équipes à suivre : fréquence ≥ 70 %, ≥ 5 matchs de l'équipe, marchés dont la fréquence générale est < 70 %. La cote retenue est toujours celle du côté de l'équipe (domicile/extérieur).
- Handicaps de `historique_pronostics.json` : ligne vue du domicile (`ligne_propre`). Toute cote incohérente avec le 1X2 est retirée (`controle_coherence`), jamais corrigée.
- Pages : `journal.html` et pages de pronostics suivent `archetype.css`, classes `ax-`, mode nuit `archetype_theme_nuit`. Après modification d'un `.js`/`.css`, changer le paramètre `?v=`.
- Tests : toute fonction de comparaison ou de règlement du journal est testée sur au moins 3 cas qui passent et 3 qui échouent (`tests/test_journal_rentabilite.py`).
