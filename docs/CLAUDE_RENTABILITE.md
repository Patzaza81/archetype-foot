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

## Journal — mode « regularites » (sans ROI)

Réglage : `config/journal_calibrage.json` → `{"mode": "regularites"}`. Retour arrière : `{"mode": "wilson"}` (défaut si le fichier est absent, illisible ou le mode inconnu). Code : `journal_regularites.py` (indépendant de V2/V3). Le ROI et le gain espéré ne sont PAS des critères du Journal (V3 les intègre déjà).

Règles :
1. Entrée (inchangée, `journal_rentabilite.py`) : au moins 5 matchs, réussite >= 70 %, marché non banal (< 70 % en général), prochain match avec cote.
2. Cote : 1,26 à 1,56. Plus de plafond 1,80. Le filtre général 1,26–3,01 du générateur reste, redondant.
3. Constance : dès 6 matchs, la moyenne « réussite globale » et « réussite sur les 6 derniers matchs » (champs `gagnes_6` / `joues_6`, ajoutés par `journal_rentabilite.py`, ordre chronologique) doit atteindre 70 %. À 6 matchs elle vaut la réussite globale. Avec 5 matchs, la réussite globale seule suffit. Donnée des 6 derniers absente (ancien `journal.json`) : pari rejeté (`DONNEE_6_DERNIERS_ABSENTE`), jamais présenté comme fiable.
4. Classement (`rank_journal_regularite`) : borne de Wilson, puis fréquence, puis nombre de matchs, puis cote la plus basse. Aucun ROI.
5. Liste : un seul pari par match, 15 au maximum, jamais complétée.
6. Probabilité utilisée pour les tickets : réussite OBSERVÉE pour la tranche de cote (pas de 0,10), calculée sur TOUS les résultats passés (tous marchés, pas seulement le Journal), recalculée à chaque exécution ; moins de 200 paris dans la tranche : valeur de l'intervalle entier. Wilson ne sert qu'au classement.
7. Aucun gain espéré ni ROI : `ev_estime` et `journal_roi` valent `null` pour ces paris (sélection, tickets). Les paris par segment championnat×marché (basés sur un ROI de segment) sont ignorés dans ce mode. Le Journal n'entre jamais dans les tickets « prudents ».
8. Affichage : « x sur y » + réussite observée à cette cote ; ni fréquence brute ni Wilson en pourcentage.
9. Suivi : `data/suivi_journal_regularites.json` (liste du jour + résultat réel des jours passés), mis à jour par `generateur_tickets.py`. `journal.yml` ne l'ajoute pas à son commit explicite ; `pipeline.yml` (`git add -A`) le fait.

Ce qui n'est pas prouvé : sur ces cotes, le Journal réussit comme n'importe quel pari de la même cote. La règle est seulement « moins mauvaise » que « wilson » (test du 09/10 : 9 paris, 22 % de réussite avec « wilson » contre 64 % sur 52 paris avec cote <= 1,8). Le suivi dit si la constance apporte quelque chose.

Tests : `tests/test_journal_regularites.py`.
