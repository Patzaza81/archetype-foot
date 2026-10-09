# Instructions — journal de rentabilité

`journal_rentabilite.py → journal.json → journal.html`

- **Affichage : statistiques gagnantes uniquement.** Tout ROI négatif est calculé (statuts `A_EVITER`, `NEUTRE`) mais n'est jamais affiché sur la page. La colonne « Niveau » (Prouvé / À surveiller / Non confirmé) est obligatoire : elle est le seul garde-fou contre les gains dus au hasard.
- **Conseil sur un match à venir = même championnat ET même marché.** Le segment championnat × marché doit être `A_JOUER` ou `A_SURVEILLER`, et la cote du jour doit être comprise entre `cote_min` et `cote_max` du segment (`verdict_marche`). Interdit : conseiller un match à partir d'une moyenne tous championnats ou d'une famille de marchés (erreur corrigée le 24/09 : BTTS oui à 2,24 dans Trefelin – The New Saints, « justifié » par la moyenne BTTS oui tous championnats à 1,73).
- **Équipes à suivre** : fréquence ≥ 70 %, ≥ 5 matchs de l'équipe, marchés dont la fréquence générale est < 70 %. La cote retenue est toujours celle du côté de l'équipe (domicile/extérieur).
- **Handicaps de `historique_pronostics.json`** : ligne vue du domicile (`ligne_propre`). Toute cote de handicap incohérente avec le 1X2 est retirée (`controle_coherence`), jamais corrigée.
- **Pages** : `journal.html` et les pages de pronostics suivent le gabarit Archetype (`archetype.css`, classes `ax-`, mode nuit `archetype_theme_nuit`). Après modification d'un `.js`/`.css`, changer le paramètre `?v=`.
- **Tests** : toute fonction de comparaison ou de règlement du journal est testée sur au moins 3 cas qui doivent passer et 3 qui doivent échouer (`tests/test_journal_rentabilite.py`).

## Classement du Journal fondé sur des preuves — mode `preuves` (09/10/2026)

`config/journal_calibrage.json` accepte maintenant trois modes : `wilson` (état initial, défaut si fichier absent ou illisible), `lisse` et `preuves`. Le passage de l'un à l'autre ne demande aucun changement de code (exigence non négociable du 08/10 conservée).

Mode `preuves` (`journal_classement.py`, indépendant des moteurs V2 et V3) :
- **Calibrage walk-forward** : probabilité réelle = a + b × fréquence lissée + c × probabilité implicite de la cote, ajustée sur les jours PASSÉS (candidats reconstruits avec les seuls matchs antérieurs au jour). Pentes ≥ 0 ; si la fréquence du Journal n'apporte rien de mesurable en plus du marché, elle est écartée. Moins de 30 observations : rien n'est publiable.
- **Admissibilité** : la borne basse 95 % de la probabilité calibrée doit couvrir la probabilité implicite de la cote (espérance positive démontrée). Cote entre 1,26 et 3,01.
- **Classement** (ordre de priorité) : borne basse calibrée, probabilité calibrée, espérance calibrée, stabilité (min des deux moitiés de l'historique de l'équipe), nombre de matchs.
- **Un seul pari par match, 15 au maximum, jamais complété** : si 6 passent, on publie 6 ; si aucun ne passe, on publie 0.
- **Générateur de tickets** : un pari non admissible n'entre jamais dans le pool (`eligible`), donc ni dans le classement ni dans le tirage au sort des tickets.
- **Diagnostic** : `data/selection_intelligence.json` → `journal_classement` (modèle retenu, nombre d'admissibles, motifs de rejet, cinq rejetés les plus proches du seuil). Une erreur de calibrage est écrite dans ce diagnostic et dans les journaux du workflow, jamais masquée : le Journal devient alors non publiable.
- **Backtest** : `python evaluation/backtest_journal_preuves.py` ; résultats et limites dans `docs/BACKTEST_JOURNAL_PREUVES.md`. Tests : `tests/test_journal_classement.py`.
