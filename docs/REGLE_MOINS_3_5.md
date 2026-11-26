# Règle « moins de 3,5 buts » d'Analyse Verdict (Patrick, 26/11/2026)

**Règle** : dans l'**onglet Catégories seulement**, le marché « moins de 3,5 buts » (et tout combo « & moins de 3,5 ») est **écarté** si
buts marqués par match de l'équipe à domicile **à domicile** + buts marqués par match de l'équipe à l'extérieur **à l'extérieur** > **3,1**
(même échantillon que le verdict : saison en cours, avant le match, 4 matchs minimum au même lieu). 3,1 exactement passe.

La règle vient **en plus** de la méthode de l'onglet : le match doit d'abord tomber dans l'intervalle figé du marché (`categories_zones.json`, xG attendu du domicile < 1,38 et de l'extérieur < 1,57), puis avoir sa cote, puis passer cette règle. Elle ne remplace rien.
Les autres onglets d'Analyse Verdict (Tous, Buts, Combos, Top 20, Règles, Étude, +1,5, +2,5) ne changent pas.
Code : `verif_pronostic.moins35_refuse` (constante `MOINS35_MAX`), appelée dans le bloc Catégories de `fiche_match`. Tests : classe `Moins35` de `tests/test_verif_pronostic.py` et fin de `tests/test_verif_categories.py`.

Effet sur la page du 26/11/2026 (814 matchs, 7 jours passés + 4 à venir) : moins de 3,5 dans Catégories 192 → 168 ; aucun autre onglet modifié.

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
