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

## Journal — mode « regularites » (formule simple, sans cote ni ROI)

Réglage : `config/journal_calibrage.json` → `{"mode": "regularites"}`. Retour arrière : `{"mode": "wilson"}` (défaut si le fichier est absent, illisible ou le mode inconnu). Code : `journal_regularites.py` (indépendant de V2/V3). Ni la cote ni le ROI ni le gain espéré ne sont des critères du Journal (V3 intègre déjà le ROI).

Formule : `chiffre = taux de l'équipe x réalisme du marché x (1 - marge d'erreur relative)`, puis on classe par ce chiffre.
- **Taux de l'équipe** : gagnés / joués sur le marché (8 sur 10 = 0,80).
- **Réalisme du marché** : réussite RÉELLE de ce marché au match suivant ÷ taux affiché, mesuré sur toutes les régularités passées du marché (même règle d'entrée que le Journal, tous les matchs terminés, sans cote, sans fuite du futur : `candidats_passes`). Marché avec moins de 15 cas : réalisme moyen de tous les marchés. Moins de 30 cas au total : aucun pari admissible (`REALISME_ABSENT`). Recalculé à chaque exécution, jamais écrit en dur.
- **Marge d'erreur** : taux moins sa borne basse à 95 % (Wilson). Elle ne tombe pas à zéro à 100 % : 5 sur 5 reste moins sûr que 18 sur 20. (Équivaut à `réalisme x borne basse`.)
- **Probabilité utilisée pour les tickets** : `taux x réalisme` (sans la marge, qui sert au classement).

Autres règles :
1. Entrée (inchangée, `journal_rentabilite.py`) : au moins 5 matchs, réussite >= 70 %, marché non banal (< 70 % en général), prochain match avec cote.
2. Constance : dès 6 matchs, la moyenne « réussite globale » et « réussite sur les 6 derniers matchs » (`gagnes_6` / `joues_6`, ajoutés par `journal_rentabilite.py`, ordre chronologique) doit atteindre 70 %. À 6 matchs elle vaut la réussite globale. Avec 5 matchs, la réussite globale seule suffit. Donnée absente : pari rejeté (`DONNEE_6_DERNIERS_ABSENTE`).
3. Classement (`rank_journal_regularite`) : chiffre, puis taux, puis nombre de matchs. Aucune cote.
4. Liste : un seul pari par match, 15 au maximum, jamais complétée.
5. La fenêtre de cote 1,26–3,01 du générateur (`eligible`) reste une contrainte de tickets, pas un critère de sélection.
6. `ev_estime` et `journal_roi` valent `null` pour ces paris ; les paris par segment (basés sur un ROI de segment) sont ignorés ; le Journal n'entre jamais dans les tickets « prudents ».
7. Affichage : « x sur y » + estimation de réussite pour ce match (`taux x réalisme`). Ni fréquence brute ni borne de Wilson en pourcentage.
8. Suivi : `data/suivi_journal_regularites.json` (liste du jour + résultat réel des jours passés), mis à jour par `generateur_tickets.py`. `journal.yml` ne l'ajoute pas à son commit explicite ; `pipeline.yml` (`git add -A`) le fait.
9. Diagnostic : `data/selection_intelligence.json` → `journal_classement` (réalisme par marché, nombre de cas passés).

Mesures du 09/10 (14 jours, 351 régularités passées) : un taux affiché de 85 % se réalise à 58 % en moyenne (réalisme 0,68). Par marché : « moins de 3,5 buts » 0,75, « ne perd pas » 0,75, « plus de 2,5 buts » 0,72, « les deux équipes marquent » 0,68 ; faibles : « moins de 2,5 buts » 0,35 (17 cas), « marque 2 buts ou plus » 0,48, « au moins une équipe ne marque pas » 0,47. Classement des 15 par jour (59 paris) : formule 64 %, borne de Wilson seule 71 %, hasard 63 % (± 12 points : aucune différence démontrée entre les trois). Le suivi dira si le classement apporte quelque chose.

Tests : `tests/test_journal_regularites.py`.

### Affichage du pourcentage (mode « regularites », 09/10/2026) — affichage seulement
- Chaque pari du Journal montre le pourcentage réel de l'équipe (7 sur 7 = 100 %) ET un pourcentage lissé :
  `lissé = (gagnés + k × base) / (joués + k)`, `k = 10` (`K_LISSAGE`), `base` = réussite RÉELLE du marché au match suivant
  (marché avec moins de 15 cas : moyenne de tous les marchés).
- Champs : `journal_taux_brut`, `journal_taux_lisse`, `journal_base_marche`, `journal_k_lissage`. Front : « lissé xx % » dans `tickets.js`.
- Le lissage n'entre ni dans le chiffre, ni dans le classement, ni dans la probabilité de ticket (inchangés). Mêmes 30 paris et mêmes
  probabilités avant/après (vérifié).
- k = 10 a été choisi pour que le lissé reste proche de « taux × réalisme » (7 sur 7 : 76 % contre 75 %). Sur 294 cas passés, le
  meilleur k mesuré est plus grand (≥ 20) : le taux de l'équipe apporte peu au-delà de la réussite réelle du marché.

