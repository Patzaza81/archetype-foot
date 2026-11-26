# Règle « moins de 3,5 buts » d'Analyse Verdict (Patrick, 26/11/2026)

**Règle** (étendue le 26/11/2026 au soir à tout Analyse Verdict, sans exception) : tout marché « moins de 3,5 buts », combos compris (1, N, 2, 1N, N2, 12 & moins de 3,5), est **refusé** si
buts marqués par match de l'équipe à domicile **à domicile** + buts marqués par match de l'équipe à l'extérieur **à l'extérieur** > **3,1**
(même échantillon que le verdict : saison en cours, avant le match, 4 matchs minimum au même lieu). 3,1 exactement passe.

S'applique dans tous les onglets : Tous, Buts, Combos, Top 20, Règles, Étude, Catégories (dans Catégories, en plus de l'intervalle du marché).
Code : `verif_pronostic.moins35_refuse` (constante `MOINS35_MAX`), appelée dans `constat()` (verdict « REFUSÉ »). Tests : classe `Moins35` de `tests/test_verif_pronostic.py` et fin de `tests/test_verif_categories.py`.

Historique : le matin du 26/11 la règle ne valait que pour l'onglet Catégories (PR 203).

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

## Comparaison ancienne / nouvelle méthode de l'onglet Catégories (26/11/2026)

Intervalle seul (ancienne) contre intervalle + règle 3,1 (nouvelle), moins de 3,5 buts :

| Échantillon | Ancienne | Nouvelle | Écart | Écartés par la règle |
|---|---|---|---|---|
| 2000-2016 (recherche de l'intervalle) | 76,1 % (34 654) | 76,4 % (31 771) | +0,3 pt | 2 883, 73,2 % gagnants |
| 2017-2020 (jamais vus) | 76,5 % (6 564) | 76,6 % (6 038) | +0,1 pt | 526, 75,3 % gagnants |
| 2025-26 (jamais vus) | 75,7 % (5 093) | 76,4 % (4 658) | +0,7 pt | 435, 67,8 % gagnants |
| Matchs Betpawa du système | 72,4 % (1 107) | 72,8 % (980) | +0,4 pt | 127, 69,3 % gagnants |
| Total | 76,0 % (47 418) | 76,3 % (43 447) | +0,3 pt | 3 971, 72,7 % gagnants |

Seuil 3,1 retenu par Patrick (« Fusionne avec 3.1 »). Script : `etudes/moins35_2026_11/compare_ancienne_nouvelle.py`.

## Comparaison ancienne / nouvelle méthode, tous les onglets (26/11/2026 au soir)

Verdict de base d'Analyse Verdict reproduit sur les grands échantillons (pari passé plus souvent que raté, des deux côtés = TIENT, d'un seul = RÉSERVE ; même lieu, saison en cours, 4 matchs minimum ; sans les ajustements xG ni les règles, pas de cote sur ces données). Moins de 3,5 seul :

| Échantillon | Ancienne | Nouvelle | Écart | Écartés par la règle |
|---|---|---|---|---|
| 2000-2010 | 72,8 % (40 078) | 73,8 % (31 861) | +1,1 pt | 8 217, 68,7 % gagnants |
| 2011-2020 | 72,7 % (35 593) | 74,6 % (27 907) | +1,9 pt | 7 686, 65,8 % gagnants |
| 2025-26 (Football-Data) | 70,7 % (10 806) | 72,6 % (8 132) | +1,8 pt | 2 674, 65,1 % gagnants |

Combos : 1N, N2, 12 & -3,5 gagnent +0,3 à +0,9 pt partout ; 1 & -3,5 et 2 & -3,5 restent à peu près égaux (−0,8 à +0,1 pt).
Paris réellement gelés (journal, 07/11 → 25/11) : moins de 3,5 seul 64,4 % (160) si ≤ 3,1 contre 72,4 % (29) au-dessus ; combos 57,1 % (35) contre 0 % (3).
Page du 26/11 au soir (814 matchs) : matchs avec un moins de 3,5 dans Tous / Buts / Combos 715 → 494 (à venir 254 → 177).
Script : `etudes/moins35_2026_11/compare_verdict_tous_onglets.py`.
