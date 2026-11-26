# Règle « moins de 3,5 buts » d'Analyse Verdict (Patrick, 26/11/2026)

**Règle** : tout marché « moins de 3,5 buts », combos compris (1, N, 2, 1N, N2, 12 & moins de 3,5), est **refusé** si
buts marqués par match de l'équipe à domicile **à domicile** + buts marqués par match de l'équipe à l'extérieur **à l'extérieur** > **3,1**
(même échantillon que le verdict : saison en cours, avant le match, 4 matchs minimum au même lieu). 3,1 exactement passe.

S'applique partout dans Analyse Verdict : onglets Tous / Buts / Combos / Top 20 / Règles / Étude, et onglet **Catégories**.
Le reste ne change pas. Code : `verif_pronostic.constat` (constante `MOINS35_MAX`, verdict « REFUSÉ »). Tests : classe `Moins35` de `tests/test_verif_pronostic.py`.

## Test sur échantillons (26/11/2026)

Matchs avec 4 matchs minimum au même lieu, réussite du marché selon le total des buts marqués (SM) :

| Échantillon | Moins de 3,5 : tous | SM ≤ 3,1 | SM > 3,1 |
|---|---|---|---|
| Grand échantillon 2000-2021 | 72,6 % (78 279) | 74,1 % (61 060) | 67,0 % (17 219) |
| Football-Data 2025-26 | 70,4 % (11 127) | 72,5 % (8 196) | 64,5 % (2 931) |
| Matchs Betpawa du système | 68,1 % (2 953) | 71,0 % (1 976) | 62,1 % (977) |
| Intervalle Catégories, 2000-2021 | 76,2 % (41 218) | 76,4 % (37 809) | 73,5 % (3 409) |
| Intervalle Catégories, 2025-26 | 75,7 % (5 093) | 76,4 % (4 658) | 67,8 % (435) |

Les 5 combos « & moins de 3,5 » baissent aussi au-delà de 3,1 sur les trois échantillons (ex. 1N & -3,5 : 53,4 % contre 48,4 % en 2000-2021).

Paris réellement gelés par Analyse Verdict (journal, verdicts TIENT / TIENT AVEC RÉSERVE, 07/11 → 25/11/2026) :
moins de 3,5 seul : 64,4 % (160 paris) si SM ≤ 3,1, **72,4 % (29 paris)** si SM > 3,1 ; combos : 57,1 % (35) contre 0 % (3).
Le marché seul va dans l'autre sens sur ce petit échantillon réel (29 paris) : à suivre dans le journal.

Scripts : `etudes/moins35_2026_11/test_echantillons.py` (tables de `etudes/categories_2026_11/build.py`), `etudes/moins35_2026_11/test_journal_reel.py`.
