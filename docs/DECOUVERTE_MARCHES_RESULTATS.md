# Découverte des indices par marché — résultats (26/10/2026)

Statut : ÉTUDE EN LECTURE SEULE. Aucun gel, aucune modification de production. Rien n'est « validé » : « confirmée sur C » veut dire qu'une configuration choisie sur A et B tient sur la période indépendante C ; seul un gel avant match peut valider.

## Résumé
- 41 événements (marchés distincts) étudiés ; 177 configurations jugées une fois sur C : **119 confirmées**, 5 prometteuses (effectif insuffisant), 53 rejetées.
- **Contrôle de biais de sélection** : la même procédure sur résultats mélangés dans chaque période (3 essais) confirme 1, 0, 2 configuration(s) sur 94, 98, 99 jugées. Une procédure sans biais devrait confirmer presque rien : ce chiffre est la part de fausses confirmations à attendre.
- Jeux : A 4753 matchs, B 3305, C 4475, D (archive BetPawa) 1233. Football-Data s'arrête au 27/09 (452 lignes écartées : même match que l'archive). Doublons d'identifiant 0, même match en double 0, résultats manquants 0.

## Vue d'ensemble : meilleure configuration confirmée par marché (niveau visé le plus haut)
| Marché | Taux de base A+B | Niveau visé | Configuration | A | B | C | Matchs sans la configuration (C) | D (BetPawa) | Statut |
|---|---|---|---|---|---|---|---|---|---|
| Plus de 1,5 buts | 75.1% | 85% | h_tot >= 2.8571 ET m_p12 >= 0.7658 | 470/549 (85.6%, W 82.4%) | 314/369 (85.1%, W 81.1%) | 605/713 (84.9%, W 82.0%) | 76.6% | 154/184 (83.7%, W 77.7%) | confirmee sur C |
| Moins de 1,5 buts | 24.9% | 45% | a_btts >= 0.3333 ET a_v2 <= 0.25 ET m_p12 <= 0.6781 | 59/131 (45.0%, W 36.8%) | 36/80 (45.0%, W 34.6%) | 29/69 (42.0%, W 31.1%) | 21.7% | 1/5 (20.0%, W 3.6%) | prometteuse a confirmer |
| Plus de 2,5 buts | 51.8% | 75% | h_o25 >= 0.6 ET h_sd >= 1.1249 ET m_p12 >= 0.7935 | 133/172 (77.3%, W 70.5%) | 80/106 (75.5%, W 66.5%) | 140/199 (70.3%, W 63.7%) | 54.3% | 37/61 (60.7%, W 48.1%) | confirmee sur C |
| Moins de 2,5 buts | 48.2% | 70% | h_sd >= 0.8165 ET m_p12 <= 0.7069 ET x_mn <= 0.714 | 120/171 (70.2%, W 62.9%) | 61/85 (71.8%, W 61.4%) | 55/87 (63.2%, W 52.7%) | 44.6% | 12/21 (57.1%, W 36.5%) | prometteuse a confirmer |
| Plus de 3,5 buts | 28.7% | 55% | h_gf >= 1.7143 ET m_p12 >= 0.8176 ET x_ext >= 0.875 | 61/109 (56.0%, W 46.6%) | 37/67 (55.2%, W 43.4%) | 63/125 (50.4%, W 41.8%) | 31.7% | 17/36 (47.2%, W 32.0%) | confirmee sur C |
| Moins de 3,5 buts | 71.3% | 90% | a_o35 >= 0.1429 ET h_nul <= 0.5 ET m_p12 <= 0.691 | 142/156 (91.0%, W 85.5%) | 82/91 (90.1%, W 82.3%) | 50/56 (89.3%, W 78.5%) | 67.5% | 8/12 (66.7%, W 39.1%) | prometteuse a confirmer |
| Plus de 4,5 buts | 13.6% | 30% | h_ga >= 1 ET m_p12 >= 0.7935 ET s_tot >= 2.95 | 52/169 (30.8%, W 24.3%) | 30/98 (30.6%, W 22.4%) | 68/227 (30.0%, W 24.4%) | 15.5% | 15/65 (23.1%, W 14.5%) | confirmee sur C |
| Moins de 4,5 buts | 86.4% | 95% | m_p12 <= 0.691 ET x_absd >= 0.025 | 421/439 (95.9%, W 93.6%) | 251/263 (95.4%, W 92.2%) | 212/221 (95.9%, W 92.4%) | 83.2% | 34/37 (91.9%, W 78.7%) | confirmee sur C |
| Les deux marquent : oui | 53.7% | 65% | h_o15 >= 0.8571 ET x_mn >= 1.5 | 254/390 (65.1%, W 60.3%) | 176/267 (65.9%, W 60.0%) | 269/427 (63.0%, W 58.3%) | 56.7% | 73/125 (58.4%, W 49.6%) | confirmee sur C |
| Les deux marquent : non | 46.3% | - | aucune configuration ne tient sur C | - | - | - | - | - | rejetée |
| Victoire domicile | 44.3% | 90% | h_sd <= 1.479 ET m_ph >= 0.6933 ET x_mn <= 0.929 | 57/63 (90.5%, W 80.7%) | 64/71 (90.1%, W 81.0%) | 63/72 (87.5%, W 77.9%) | 42.6% | 21/24 (87.5%, W 69.0%) | prometteuse a confirmer |
| Match nul | 25.9% | 35% | m_p12 <= 0.7173 ET s_cs >= 0.375 | 148/422 (35.1%, W 30.7%) | 69/196 (35.2%, W 28.9%) | 70/196 (35.7%, W 29.3%) | 25.9% | 20/59 (33.9%, W 23.1%) | confirmee sur C |
| Victoire extérieur | 29.8% | 75% | a_ga >= 1 ET m_ph <= 0.2048 ET s_fts >= 0.2 | 82/108 (75.9%, W 67.1%) | 59/78 (75.6%, W 65.1%) | 79/111 (71.2%, W 62.2%) | 29.3% | 28/36 (77.8%, W 61.9%) | confirmee sur C |
| Domicile ne perd pas (1N) | 70.2% | 95% | a_tot >= 1.5714 ET m_p1n >= 0.8822 | 215/226 (95.1%, W 91.5%) | 173/182 (95.0%, W 90.9%) | 204/220 (92.7%, W 88.5%) | 68.5% | 56/57 (98.2%, W 90.7%) | confirmee sur C |
| Extérieur ne perd pas (N2) | 55.7% | 90% | a_gd <= 0.7143 ET m_ph <= 0.2048 ET x_absd <= 1 | 127/141 (90.1%, W 84.0%) | 105/116 (90.5%, W 83.8%) | 164/183 (89.6%, W 84.4%) | 55.2% | 46/50 (92.0%, W 81.2%) | confirmee sur C |
| Pas de nul (12) | 74.1% | 80% | a_tot >= 2 ET m_p12 >= 0.7512 | 1049/1307 (80.3%, W 78.0%) | 668/835 (80.0%, W 77.1%) | 1279/1619 (79.0%, W 77.0%) | 70.7% | 340/451 (75.4%, W 71.2%) | confirmee sur C |
| Handicap -1,5 domicile | 21.5% | 55% | h_btts >= 0.2857 ET m_ph >= 0.6933 | 116/210 (55.2%, W 48.5%) | 90/161 (55.9%, W 48.2%) | 123/227 (54.2%, W 47.7%) | 19.9% | 21/52 (40.4%, W 28.2%) | confirmee sur C |
| Handicap +1,5 extérieur | 78.5% | 95% | m_p1n <= 0.5258 ET s_fts >= 0.1429 | 309/323 (95.7%, W 92.9%) | 248/260 (95.4%, W 92.1%) | 320/343 (93.3%, W 90.1%) | 77.1% | 104/107 (97.2%, W 92.1%) | confirmee sur C |
| Handicap +1,5 domicile | 87.0% | 95% | m_ph >= 0.4609 ET s_gd >= 0.5 | 1387/1460 (95.0%, W 93.8%) | 1000/1049 (95.3%, W 93.9%) | 1396/1476 (94.6%, W 93.3%) | 83.4% | 400/411 (97.3%, W 95.3%) | confirmee sur C |
| Handicap -1,5 extérieur | 13.0% | 30% | m_p12 >= 0.7512 ET m_p1n <= 0.7102 | 124/377 (32.9%, W 28.3%) | 72/237 (30.4%, W 24.9%) | 157/517 (30.4%, W 26.6%) | 10.7% | 44/175 (25.1%, W 19.3%) | confirmee sur C |
| Plus de 0,5 buts du domicile | 77.5% | 95% | m_p12 >= 0.7935 ET x_dom >= 1.833 | 259/270 (95.9%, W 92.8%) | 171/180 (95.0%, W 90.8%) | 285/300 (95.0%, W 91.9%) | 78.1% | 81/88 (92.0%, W 84.5%) | confirmee sur C |
| Moins de 0,5 buts du domicile | 22.5% | 45% | a_gf <= 2.1667 ET m_ph <= 0.2547 ET s_fts >= 0.25 | 104/230 (45.2%, W 38.9%) | 85/188 (45.2%, W 38.3%) | 81/203 (39.9%, W 33.4%) | 19.9% | 27/60 (45.0%, W 33.1%) | confirmee sur C |
| Plus de 1,5 buts du domicile | 43.6% | 80% | m_p12 >= 0.7935 ET s_gf >= 0.8571 ET s_nul <= 0.2 | 84/105 (80.0%, W 71.4%) | 65/81 (80.2%, W 70.3%) | 100/126 (79.4%, W 71.5%) | 45.2% | 25/39 (64.1%, W 48.4%) | confirmee sur C |
| Moins de 1,5 buts du domicile | 56.4% | 80% | a_o35 <= 0.4286 ET h_fts >= 0.2 ET m_ph <= 0.2048 | 116/144 (80.6%, W 73.3%) | 108/133 (81.2%, W 73.7%) | 107/137 (78.1%, W 70.5%) | 53.1% | 44/47 (93.6%, W 82.8%) | confirmee sur C |
| Plus de 2,5 buts du domicile | 19.5% | 50% | a_cs >= 0 ET m_ph >= 0.6933 | 119/237 (50.2%, W 43.9%) | 87/170 (51.2%, W 43.7%) | 116/238 (48.7%, W 42.5%) | 19.7% | 25/64 (39.1%, W 28.1%) | confirmee sur C |
| Moins de 2,5 buts du domicile | 80.5% | 95% | h_pts <= 2.1429 ET m_ph <= 0.2048 | 213/223 (95.5%, W 91.9%) | 195/205 (95.1%, W 91.2%) | 246/261 (94.2%, W 90.7%) | 77.8% | 84/87 (96.5%, W 90.3%) | confirmee sur C |
| Plus de 0,5 buts de l'extérieur | 68.8% | 95% | a_ga <= 1.2857 ET m_p12 >= 0.7658 ET m_p1n <= 0.5258 | 107/112 (95.5%, W 90.0%) | 93/97 (95.9%, W 89.9%) | 111/117 (94.9%, W 89.3%) | 71.1% | 43/48 (89.6%, W 77.8%) | confirmee sur C |
| Moins de 0,5 buts de l'extérieur | 31.2% | 55% | m_p1n >= 0.8822 ET s_btts >= 0.2857 ET x_mn <= 0.929 | 69/124 (55.6%, W 46.9%) | 69/124 (55.6%, W 46.9%) | 59/116 (50.9%, W 41.9%) | 27.6% | 19/34 (55.9%, W 39.5%) | confirmee sur C |
| Plus de 1,5 buts de l'extérieur | 33.7% | 70% | a_v2 >= 0.1429 ET m_p12 >= 0.7658 ET m_ph <= 0.5031 | 101/144 (70.1%, W 62.2%) | 68/96 (70.8%, W 61.1%) | 100/148 (67.6%, W 59.7%) | 35.3% | 39/59 (66.1%, W 53.4%) | confirmee sur C |
| Moins de 1,5 buts de l'extérieur | 66.3% | - | aucune configuration ne tient sur C | - | - | - | - | - | rejetée |
| Plus de 2,5 buts de l'extérieur | 12.5% | 35% | h_pts <= 1.5714 ET m_ph <= 0.2048 ET x_dom >= 0.857 | 52/146 (35.6%, W 28.3%) | 41/117 (35.0%, W 27.0%) | 45/155 (29.0%, W 22.5%) | 13.6% | 11/51 (21.6%, W 12.5%) | confirmee sur C |
| Moins de 2,5 buts de l'extérieur | 87.5% | - | aucune configuration ne tient sur C | - | - | - | - | - | rejetée |
| Multigoals 1-2 | 40.8% | 60% | a_cs >= 0.1429 ET m_p12 <= 0.7173 ET m_ph >= 0.4609 | 61/101 (60.4%, W 50.6%) | 38/61 (62.3%, W 49.8%) | 33/62 (53.2%, W 41.0%) | 38.4% | 5/11 (45.5%, W 21.3%) | prometteuse a confirmer |
| Multigoals 1-3 | 64.0% | - | aucune configuration ne tient sur C | - | - | - | - | - | rejetée |
| Multigoals 1-4 | 79.1% | 85% | p_o25 <= 0.25 ET x_mn >= 0.929 | 300/352 (85.2%, W 81.1%) | 131/154 (85.1%, W 78.6%) | 155/183 (84.7%, W 78.8%) | 77.1% | 60/77 (77.9%, W 67.5%) | confirmee sur C |
| Multigoals 2-3 | 46.5% | - | aucune configuration ne tient sur C | - | - | - | - | - | rejetée |
| Multigoals 2-4 | 61.6% | 75% | h_d2 >= 0.1667 ET m_ph <= 0.3526 ET m_pover25 >= 0.519 | 81/104 (77.9%, W 69.0%) | 86/114 (75.4%, W 66.8%) | 87/121 (71.9%, W 63.3%) | 61.4% | 70/116 (60.3%, W 51.2%) | confirmee sur C |
| Multigoals 2-5 | 69.5% | 85% | a_vic >= 0.1429 ET m_pover25 >= 0.5686 ET x_mn <= 1.071 | 82/95 (86.3%, W 78.0%) | 88/102 (86.3%, W 78.3%) | 123/151 (81.5%, W 74.5%) | 70.5% | 45/66 (68.2%, W 56.2%) | confirmee sur C |
| Multigoals 3-4 | 38.2% | 50% | a_ga <= 2.25 ET m_p12 >= 0.8176 ET s_cs >= 0.0714 | 85/170 (50.0%, W 42.6%) | 63/126 (50.0%, W 41.4%) | 96/206 (46.6%, W 39.9%) | 38.4% | 26/66 (39.4%, W 28.5%) | confirmee sur C |
| Multigoals 3-5 | 46.2% | 55% | a_cs >= 0 ET m_p12 >= 0.7658 | 524/949 (55.2%, W 52.0%) | 353/635 (55.6%, W 51.7%) | 625/1173 (53.3%, W 50.4%) | 46.1% | 160/327 (48.9%, W 43.6%) | confirmee sur C |
| Multigoals 3-6 | 49.8% | 60% | m_p12 >= 0.7413 ET s_tot >= 2.7857 | 694/1150 (60.4%, W 57.5%) | 441/726 (60.7%, W 57.1%) | 861/1433 (60.1%, W 57.5%) | 49.0% | 245/430 (57.0%, W 52.3%) | confirmee sur C |

## Rentabilité, séparée du taux de réussite (configurations confirmées ou prometteuses)
| Marché | Niveau | Cotes BetPawa (D) : paris jouables ≥ 1,25 | Taux | Gains / pertes | Rendement net (IC 95 %) | Cotes moyennes de clôture Football-Data (C) |
|---|---|---|---|---|---|---|
| Plus de 1,5 buts | 80% | 144 sur 803 (part jouable 17.9%) | 75.7% | 31.93 / 35.0 | -2.1% [-11.2% ; +7.0%] | sans objet |
| Plus de 1,5 buts | 85% | 6 sur 176 (part jouable 3.4%) | 83.3% | 1.34 / 1.0 | +5.7% [-35.8% ; +47.1%] | sans objet |
| Moins de 1,5 buts | 40% | 27 sur 27 (part jouable 100.0%) | 37.0% | 14.96 / 17.0 | -7.6% [-54.2% ; +39.1%] | sans objet |
| Moins de 1,5 buts | 45% | 5 sur 5 (part jouable 100.0%) | 20.0% | 1.29 / 4.0 | -54.2% [-144.0% ; +35.6%] | sans objet |
| Plus de 2,5 buts | 70% | 106 sur 112 (part jouable 94.6%) | 55.7% | 25.59 / 47.0 | -20.2% [-33.9% ; -6.5%] | -6.7% sur 222 paris |
| Plus de 2,5 buts | 75% | 56 sur 60 (part jouable 93.3%) | 60.7% | 14.46 / 22.0 | -13.5% [-32.0% ; +5.1%] | -6.1% sur 104 paris |
| Moins de 2,5 buts | 65% | 30 sur 30 (part jouable 100.0%) | 53.3% | 7.52 / 14.0 | -21.6% [-48.4% ; +5.2%] | +5.2% sur 38 paris |
| Moins de 2,5 buts | 70% | 20 sur 20 (part jouable 100.0%) | 55.0% | 5.45 / 9.0 | -17.8% [-51.4% ; +15.9%] | +13.3% sur 15 paris |
| Plus de 3,5 buts | 50% | 61 sur 61 (part jouable 100.0%) | 37.7% | 24.18 / 38.0 | -22.7% [-48.5% ; +3.2%] | sans objet |
| Plus de 3,5 buts | 55% | 34 sur 34 (part jouable 100.0%) | 47.1% | 14.48 / 18.0 | -10.3% [-43.2% ; +22.5%] | sans objet |
| Moins de 3,5 buts | 85% | 2 sur 32 (part jouable 6.2%) | 100.0% | 0.5 / 0 | +25.0% [+25.0% ; +25.0%] | sans objet |
| Moins de 3,5 buts | 90% | 3 sur 11 (part jouable 27.3%) | 66.7% | 0.5 / 1.0 | -16.7% [-98.3% ; +65.0%] | sans objet |
| Plus de 4,5 buts | 30% | 64 sur 64 (part jouable 100.0%) | 23.4% | 39.9 / 49.0 | -14.2% [-54.1% ; +25.7%] | sans objet |
| Moins de 4,5 buts | 95% | 0 sur 31 (part jouable 0.0%) | - | - / - | - | sans objet |
| Les deux marquent : oui | 60% | 311 sur 313 (part jouable 99.4%) | 58.8% | 109.17 / 128.0 | -6.0% [-15.0% ; +2.9%] | sans objet |
| Les deux marquent : oui | 65% | 123 sur 125 (part jouable 98.4%) | 57.7% | 36.04 / 52.0 | -13.0% [-26.4% ; +0.4%] | sans objet |
| Victoire domicile | 80% | 29 sur 59 (part jouable 49.2%) | 72.4% | 6.24 / 8.0 | -6.1% [-27.6% ; +15.4%] | -0.9% sur 217 paris |
| Victoire domicile | 90% | 13 sur 24 (part jouable 54.2%) | 84.6% | 3.34 / 2.0 | +10.3% [-16.4% ; +37.0%] | +6.7% sur 72 paris |
| Match nul | 30% | 259 sur 259 (part jouable 100.0%) | 30.9% | 175.38 / 179.0 | -1.4% [-19.4% ; +16.6%] | -4.2% sur 1133 paris |
| Match nul | 35% | 59 sur 59 (part jouable 100.0%) | 33.9% | 41.88 / 39.0 | +4.9% [-32.9% ; +42.6%] | +9.0% sur 196 paris |
| Victoire extérieur | 70% | 55 sur 57 (part jouable 96.5%) | 80.0% | 22.92 / 11.0 | +21.7% [+5.2% ; +38.1%] | -2.3% sur 170 paris |
| Victoire extérieur | 75% | 35 sur 36 (part jouable 97.2%) | 77.1% | 13.89 / 8.0 | +16.8% [-4.9% ; +38.5%] | +5.2% sur 111 paris |
| Domicile ne perd pas (1N) | 90% | 0 sur 111 (part jouable 0.0%) | - | - / - | - | sans objet |
| Domicile ne perd pas (1N) | 95% | 0 sur 52 (part jouable 0.0%) | - | - / - | - | sans objet |
| Extérieur ne perd pas (N2) | 85% | 19 sur 111 (part jouable 17.1%) | 78.9% | 4.39 / 4.0 | +2.1% [-22.3% ; +26.4%] | sans objet |
| Extérieur ne perd pas (N2) | 90% | 0 sur 49 (part jouable 0.0%) | - | - / - | - | sans objet |
| Pas de nul (12) | 80% | 157 sur 444 (part jouable 35.4%) | 68.2% | 28.59 / 50.0 | -13.6% [-22.9% ; -4.4%] | sans objet |
| Handicap -1,5 domicile | 50% | 107 sur 109 (part jouable 98.2%) | 53.3% | 52.3 / 50.0 | +2.1% [-16.5% ; +20.8%] | sans objet |
| Handicap -1,5 domicile | 55% | 43 sur 45 (part jouable 95.6%) | 41.9% | 12.06 / 25.0 | -30.1% [-55.3% ; -4.9%] | sans objet |
| Handicap +1,5 extérieur | 90% | 1 sur 174 (part jouable 0.6%) | 100.0% | 0.27 / 0 | +27.0% [+27.0% ; +27.0%] | sans objet |
| Handicap +1,5 extérieur | 95% | 0 sur 14 (part jouable 0.0%) | - | - / - | - | sans objet |
| Handicap +1,5 domicile | 90% | 8 sur 403 (part jouable 2.0%) | 100.0% | 6.68 / 0 | +83.5% [+50.7% ; +116.3%] | sans objet |
| Handicap +1,5 domicile | 95% | 7 sur 24 (part jouable 29.2%) | 100.0% | 6.31 / 0 | +90.1% [+55.4% ; +124.9%] | sans objet |
| Handicap -1,5 extérieur | 30% | 161 sur 161 (part jouable 100.0%) | 27.3% | 90.12 / 117.0 | -16.7% [-40.0% ; +6.6%] | sans objet |
| Plus de 0,5 buts du domicile | 90% | 0 sur 195 (part jouable 0.0%) | - | - / - | - | sans objet |
| Plus de 0,5 buts du domicile | 95% | 1 sur 60 (part jouable 1.7%) | 0.0% | 0 / 1.0 | -100.0% [-100.0% ; -100.0%] | sans objet |
| Moins de 0,5 buts du domicile | 40% | 99 sur 99 (part jouable 100.0%) | 42.4% | 55.23 / 57.0 | -1.8% [-25.0% ; +21.4%] | sans objet |
| Moins de 0,5 buts du domicile | 45% | 50 sur 50 (part jouable 100.0%) | 46.0% | 29.41 / 27.0 | +4.8% [-27.4% ; +37.1%] | sans objet |
| Plus de 1,5 buts du domicile | 75% | 32 sur 39 (part jouable 82.1%) | 56.2% | 6.41 / 14.0 | -23.7% [-47.4% ; +0.0%] | sans objet |
| Plus de 1,5 buts du domicile | 80% | 20 sur 25 (part jouable 80.0%) | 60.0% | 4.28 / 8.0 | -18.6% [-48.6% ; +11.4%] | sans objet |
| Moins de 1,5 buts du domicile | 75% | 25 sur 39 (part jouable 64.1%) | 80.0% | 6.99 / 5.0 | +8.0% [-13.9% ; +29.8%] | sans objet |
| Moins de 1,5 buts du domicile | 80% | 10 sur 32 (part jouable 31.2%) | 100.0% | 2.89 / 0 | +28.9% [+26.7% ; +31.1%] | sans objet |
| Plus de 2,5 buts du domicile | 45% | 80 sur 80 (part jouable 100.0%) | 36.2% | 30.86 / 51.0 | -25.2% [-47.4% ; -2.9%] | sans objet |
| Plus de 2,5 buts du domicile | 50% | 41 sur 41 (part jouable 100.0%) | 36.6% | 13.37 / 26.0 | -30.8% [-59.5% ; -2.1%] | sans objet |
| Moins de 2,5 buts du domicile | 90% | 2 sur 213 (part jouable 0.9%) | 100.0% | 0.56 / 0 | +28.0% [+24.1% ; +31.9%] | sans objet |
| Moins de 2,5 buts du domicile | 95% | 0 sur 34 (part jouable 0.0%) | - | - / - | - | sans objet |
| Plus de 0,5 buts de l'extérieur | 90% | 0 sur 72 (part jouable 0.0%) | - | - / - | - | sans objet |
| Plus de 0,5 buts de l'extérieur | 95% | 0 sur 39 (part jouable 0.0%) | - | - / - | - | sans objet |
| Moins de 0,5 buts de l'extérieur | 50% | 46 sur 46 (part jouable 100.0%) | 56.5% | 22.81 / 20.0 | +6.1% [-21.6% ; +33.9%] | sans objet |
| Moins de 0,5 buts de l'extérieur | 55% | 28 sur 28 (part jouable 100.0%) | 53.6% | 13.16 / 13.0 | +0.6% [-35.5% ; +36.7%] | sans objet |
| Plus de 1,5 buts de l'extérieur | 65% | 53 sur 56 (part jouable 94.6%) | 64.2% | 17.91 / 19.0 | -2.1% [-22.4% ; +18.3%] | sans objet |
| Plus de 1,5 buts de l'extérieur | 70% | 34 sur 37 (part jouable 91.9%) | 61.8% | 9.54 / 13.0 | -10.2% [-34.5% ; +14.1%] | sans objet |
| Plus de 2,5 buts de l'extérieur | 30% | 50 sur 50 (part jouable 100.0%) | 22.0% | 18.91 / 39.0 | -40.2% [-73.7% ; -6.7%] | sans objet |
| Plus de 2,5 buts de l'extérieur | 35% | 33 sur 33 (part jouable 100.0%) | 27.3% | 13.64 / 24.0 | -31.4% [-71.4% ; +8.6%] | sans objet |
| Multigoals 1-2 | 55% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 1-2 | 60% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 1-4 | 85% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 2-4 | 65% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 2-4 | 75% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 2-5 | 75% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 2-5 | 85% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 3-4 | 45% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 3-4 | 50% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 3-5 | 50% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 3-5 | 55% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 3-6 | 55% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |
| Multigoals 3-6 | 60% | 0 sur 0 (part jouable -) | - | - / - | - | sans objet |

## Candidats imposés (traités par la même fonction de jugement, sans privilège)
### Moins de 3,5 buts — x_tot <= 2.8 (niveau promis par son réglage : 70%) → **rejetee**
- A : 2185/2908 (75.1%, W 73.5%) ; B : 1499/2025 (74.0%, W 72.1%) ; C : 1767/2465 (71.7%, W 69.9%) ; D : 458/646 (70.9%, W 67.3%)
- Matchs sans la configuration : A 64.3%, B 68.5%, C 63.0%, D 65.6%
- Raison : baisse significative de A+B à C. règle imposée, non découverte par la procédure ; choisie après lecture de résultats d'une étude précédente : la période C n'est pas indépendante pour elle.
- Cotes BetPawa (D), jouables ≥ 1,25 : 439 sur 627 ; rendement -5.8% [-12.0% ; +0.3%]

### Pas de nul (12) — x_absd >= 0.6 (niveau promis par son réglage : 70%) → **confirmee sur C**
- A : 1211/1589 (76.2%, W 74.1%) ; B : 810/1088 (74.5%, W 71.8%) ; C : 1179/1530 (77.1%, W 74.9%) ; D : 367/497 (73.8%, W 69.8%)
- Matchs sans la configuration : A 73.3%, B 73.7%, C 71.9%, D 75.4%
- Raison : bat les matchs sans la configuration, tient son niveau, pas de baisse significative. règle imposée, non découverte par la procédure ; choisie après lecture de résultats d'une étude précédente : la période C n'est pas indépendante pour elle.
- Cotes BetPawa (D), jouables ≥ 1,25 : 280 sur 482 ; rendement -8.1% [-15.0% ; -1.2%]

## Détail par marché
### Plus de 1,5 buts  (`over_under_1.5|plus`)
- Gagnants / perdants : A 3555/1198  B 2499/806  C 3488/987  D 958/275 ; 741 532 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5974, log-loss 0.5207 contre 0.5303 (taux de base) ; boosting AUC 0.5925, meilleurs 5 % → 83.9% (taux de base 77.9%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_pover25 +0.35 (oui); m_p12 +0.33 (oui); m_pn -0.33 (oui); s_tot +0.25 (oui); x_tot +0.25 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 80% | m_p12 >= 0.7251 ET p_o15 >= 0.6 | 2043/2536 (80.6%, W 79.0%) | 1330/1661 (80.1%, W 78.1%) | 2294/2829 (81.1%, W 79.6%) | 72.5% | 651/825 (78.9%, W 76.0%) | confirmee sur C |
| 85% | h_tot >= 2.8571 ET m_p12 >= 0.7658 | 470/549 (85.6%, W 82.4%) | 314/369 (85.1%, W 81.1%) | 605/713 (84.9%, W 82.0%) | 76.6% | 154/184 (83.7%, W 77.7%) | confirmee sur C |
| 90% | a_gd >= -1.5714 ET h_gd >= -1.1429 ET p_o25 >= 0.8571 | 198/220 (90.0%, W 85.3%) | 134/148 (90.5%, W 84.8%) | 216/269 (80.3%, W 75.1%) | 77.8% | 66/79 (83.5%, W 73.9%) | rejetee |

### Moins de 1,5 buts  (`over_under_1.5|moins`)
- Gagnants / perdants : A 1198/3555  B 806/2499  C 987/3488  D 275/958 ; 742 949 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5974, log-loss 0.5207 contre 0.5303 (taux de base) ; boosting AUC 0.5925, meilleurs 5 % → 36.3% (taux de base 22.1%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_pover25 -0.35 (oui); m_p12 -0.33 (oui); m_pn +0.33 (oui); s_tot -0.25 (oui); x_tot -0.25 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | a_o15 <= 0.8571 ET m_p12 <= 0.7333 | 544/1732 (31.4%, W 29.3%) | 321/1056 (30.4%, W 27.7%) | 323/1086 (29.7%, W 27.1%) | 19.6% | 82/331 (24.8%, W 20.4%) | confirmee sur C |
| 35% | m_p12 <= 0.7069 ET s_tot <= 2.2 | 178/473 (37.6%, W 33.4%) | 91/255 (35.7%, W 30.1%) | 85/229 (37.1%, W 31.1%) | 21.2% | 18/50 (36.0%, W 24.1%) | confirmee sur C |
| 40% | m_p12 <= 0.691 ET m_ph >= 0.2547 ET p_e <= 0.4 | 125/312 (40.1%, W 34.8%) | 62/154 (40.3%, W 32.8%) | 64/144 (44.4%, W 36.6%) | 21.3% | 10/27 (37.0%, W 21.5%) | confirmee sur C |
| 45% | a_btts >= 0.3333 ET a_v2 <= 0.25 ET m_p12 <= 0.6781 | 59/131 (45.0%, W 36.8%) | 36/80 (45.0%, W 34.6%) | 29/69 (42.0%, W 31.1%) | 21.7% | 1/5 (20.0%, W 3.6%) | prometteuse a confirmer |

### Plus de 2,5 buts  (`over_under_2.5|plus`)
- Gagnants / perdants : A 2443/2310  B 1732/1573  C 2463/2012  D 658/575 ; 741 982 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5966, log-loss 0.6759 contre 0.6907 (taux de base) ; boosting AUC 0.5933, meilleurs 5 % → 68.2% (taux de base 55.0%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 +0.34 (oui); m_pn -0.34 (oui); m_pover25 +0.30 (oui); s_tot +0.23 (oui); x_tot +0.23 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 55% | a_cs >= 0 ET m_p12 >= 0.7173 | 1868/3312 (56.4%, W 54.7%) | 1229/2228 (55.2%, W 53.1%) | 2086/3555 (58.7%, W 57.0%) | 41.0% | 570/1037 (55.0%, W 51.9%) | confirmee sur C |
| 60% | a_o25 >= 0.1429 ET m_p12 >= 0.7413 | 1110/1834 (60.5%, W 58.3%) | 682/1134 (60.1%, W 57.3%) | 1345/2159 (62.3%, W 60.2%) | 48.3% | 365/625 (58.4%, W 54.5%) | confirmee sur C |
| 65% | m_p12 >= 0.7658 ET p_o25 >= 0.4 | 499/751 (66.4%, W 63.0%) | 334/513 (65.1%, W 60.9%) | 643/967 (66.5%, W 63.5%) | 51.9% | 166/271 (61.3%, W 55.3%) | confirmee sur C |
| 70% | m_p12 >= 0.7935 ET x_ext >= 0.875 | 234/334 (70.1%, W 64.9%) | 144/201 (71.6%, W 65.0%) | 280/411 (68.1%, W 63.5%) | 53.7% | 65/115 (56.5%, W 47.4%) | confirmee sur C |
| 75% | h_o25 >= 0.6 ET h_sd >= 1.1249 ET m_p12 >= 0.7935 | 133/172 (77.3%, W 70.5%) | 80/106 (75.5%, W 66.5%) | 140/199 (70.3%, W 63.7%) | 54.3% | 37/61 (60.7%, W 48.1%) | confirmee sur C |
| 80% | h_ga >= 1.2857 ET m_p12 >= 0.7935 ET p_o35 >= 0.2857 | 79/97 (81.4%, W 72.6%) | 52/65 (80.0%, W 68.7%) | 105/142 (73.9%, W 66.2%) | 54.4% | 26/40 (65.0%, W 49.5%) | rejetee |

### Moins de 2,5 buts  (`over_under_2.5|moins`)
- Gagnants / perdants : A 2310/2443  B 1573/1732  C 2012/2463  D 575/658 ; 743 861 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5966, log-loss 0.6759 contre 0.6907 (taux de base) ; boosting AUC 0.5933, meilleurs 5 % → 57.9% (taux de base 45.0%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 -0.34 (oui); m_pn +0.34 (oui); m_pover25 -0.30 (oui); s_tot -0.23 (oui); x_tot -0.23 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 55% | h_o35 <= 0.2857 ET m_p12 <= 0.7413 | 867/1570 (55.2%, W 52.8%) | 513/931 (55.1%, W 51.9%) | 556/1034 (53.8%, W 50.7%) | 42.3% | 179/330 (54.2%, W 48.9%) | confirmee sur C |
| 60% | a_o15 <= 0.6667 ET m_p12 <= 0.7069 | 302/476 (63.4%, W 59.0%) | 164/272 (60.3%, W 54.4%) | 131/212 (61.8%, W 55.1%) | 44.1% | 28/51 (54.9%, W 41.4%) | confirmee sur C |
| 65% | a_o15 <= 0.8571 ET m_p12 <= 0.691 ET s_nul >= 0.0714 | 271/409 (66.3%, W 61.5%) | 141/216 (65.3%, W 58.7%) | 123/185 (66.5%, W 59.4%) | 44.0% | 17/31 (54.8%, W 37.8%) | confirmee sur C |
| 70% | h_sd >= 0.8165 ET m_p12 <= 0.7069 ET x_mn <= 0.714 | 120/171 (70.2%, W 62.9%) | 61/85 (71.8%, W 61.4%) | 55/87 (63.2%, W 52.7%) | 44.6% | 12/21 (57.1%, W 36.5%) | prometteuse a confirmer |

### Plus de 3,5 buts  (`over_under_3.5|plus`)
- Gagnants / perdants : A 1381/3372  B 929/2376  C 1441/3034  D 390/843 ; 743 531 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5933, log-loss 0.6189 contre 0.6307 (taux de base) ; boosting AUC 0.5874, meilleurs 5 % → 42.1% (taux de base 32.2%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 +0.36 (oui); m_pn -0.36 (oui); m_pover25 +0.33 (oui); s_tot +0.27 (oui); x_tot +0.27 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 35% | h_fts <= 0.2857 ET m_p12 >= 0.7333 | 596/1572 (37.9%, W 35.5%) | 342/964 (35.5%, W 32.5%) | 683/1733 (39.4%, W 37.1%) | 27.6% | 207/562 (36.8%, W 33.0%) | confirmee sur C |
| 40% | m_ph >= 0.5534 ET p_btts >= 0.4286 | 229/565 (40.5%, W 36.6%) | 148/364 (40.7%, W 35.7%) | 257/620 (41.4%, W 37.6%) | 30.7% | 78/189 (41.3%, W 34.5%) | confirmee sur C |
| 45% | m_p12 >= 0.7935 ET s_fts <= 0.5 ET x_ext >= 0.875 | 152/332 (45.8%, W 40.5%) | 90/200 (45.0%, W 38.3%) | 190/410 (46.3%, W 41.6%) | 30.8% | 41/114 (36.0%, W 27.8%) | confirmee sur C |
| 50% | h_tot >= 3 ET m_p12 >= 0.7935 ET p_btts >= 0.5714 | 96/192 (50.0%, W 43.0%) | 63/120 (52.5%, W 43.6%) | 126/246 (51.2%, W 45.0%) | 31.1% | 23/62 (37.1%, W 26.2%) | confirmee sur C |
| 55% | h_gf >= 1.7143 ET m_p12 >= 0.8176 ET x_ext >= 0.875 | 61/109 (56.0%, W 46.6%) | 37/67 (55.2%, W 43.4%) | 63/125 (50.4%, W 41.8%) | 31.7% | 17/36 (47.2%, W 32.0%) | confirmee sur C |
| 60% | h_o35 >= 0.5714 ET m_p12 >= 0.7935 ET x_ext >= 0.875 | 57/90 (63.3%, W 53.0%) | 36/60 (60.0%, W 47.4%) | 68/133 (51.1%, W 42.7%) | 31.6% | 14/38 (36.8%, W 23.4%) | rejetee |

### Moins de 3,5 buts  (`over_under_3.5|moins`)
- Gagnants / perdants : A 3372/1381  B 2376/929  C 3034/1441  D 843/390 ; 741 923 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5933, log-loss 0.6189 contre 0.6307 (taux de base) ; boosting AUC 0.5874, meilleurs 5 % → 85.2% (taux de base 67.8%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 -0.36 (oui); m_pn +0.36 (oui); m_pover25 -0.33 (oui); s_tot -0.27 (oui); x_tot -0.27 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 75% | h_gf <= 2.5714 ET m_p12 <= 0.7413 | 2138/2793 (76.5%, W 74.9%) | 1573/2094 (75.1%, W 73.2%) | 1640/2201 (74.5%, W 72.7%) | 61.3% | 415/564 (73.6%, W 69.8%) | confirmee sur C |
| 80% | m_p12 <= 0.7173 ET s_o15 <= 0.7143 | 766/923 (83.0%, W 80.4%) | 548/685 (80.0%, W 76.8%) | 468/592 (79.0%, W 75.6%) | 66.1% | 87/119 (73.1%, W 64.5%) | confirmee sur C |
| 85% | a_v2 <= 0.25 ET m_p12 <= 0.691 | 359/411 (87.4%, W 83.8%) | 199/233 (85.4%, W 80.3%) | 178/209 (85.2%, W 79.7%) | 67.0% | 27/35 (77.1%, W 61.0%) | confirmee sur C |
| 90% | a_o35 >= 0.1429 ET h_nul <= 0.5 ET m_p12 <= 0.691 | 142/156 (91.0%, W 85.5%) | 82/91 (90.1%, W 82.3%) | 50/56 (89.3%, W 78.5%) | 67.5% | 8/12 (66.7%, W 39.1%) | prometteuse a confirmer |

### Plus de 4,5 buts  (`over_under_4.5|plus`)
- Gagnants / perdants : A 642/4111  B 451/2854  C 726/3749  D 214/1019 ; 742 656 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6154, log-loss 0.4329 contre 0.4464 (taux de base) ; boosting AUC 0.6143, meilleurs 5 % → 27.8% (taux de base 16.2%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 +0.40 (oui); m_pn -0.40 (oui); m_pover25 +0.37 (oui); s_tot +0.30 (oui); x_tot +0.30 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | h_ga >= 1 ET m_p12 >= 0.7935 ET s_tot >= 2.95 | 52/169 (30.8%, W 24.3%) | 30/98 (30.6%, W 22.4%) | 68/227 (30.0%, W 24.4%) | 15.5% | 15/65 (23.1%, W 14.5%) | confirmee sur C |

### Moins de 4,5 buts  (`over_under_4.5|moins`)
- Gagnants / perdants : A 4111/642  B 2854/451  C 3749/726  D 1019/214 ; 741 931 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6154, log-loss 0.4329 contre 0.4464 (taux de base) ; boosting AUC 0.6143, meilleurs 5 % → 94.6% (taux de base 83.8%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 -0.40 (oui); m_pn +0.40 (oui); m_pover25 -0.37 (oui); s_tot -0.30 (oui); x_tot -0.30 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 90% | m_p12 <= 0.7333 ET s_o15 <= 0.8571 | 1781/1948 (91.4%, W 90.1%) | 1233/1370 (90.0%, W 88.3%) | 1240/1394 (88.9%, W 87.2%) | 81.4% | 308/352 (87.5%, W 83.6%) | rejetee |
| 95% | m_p12 <= 0.691 ET x_absd >= 0.025 | 421/439 (95.9%, W 93.6%) | 251/263 (95.4%, W 92.2%) | 212/221 (95.9%, W 92.4%) | 83.2% | 34/37 (91.9%, W 78.7%) | confirmee sur C |

### Les deux marquent : oui  (`btts|Oui`)
- Gagnants / perdants : A 2519/2234  B 1807/1498  C 2564/1911  D 684/549 ; 740 589 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5324, log-loss 0.6857 contre 0.6862 (taux de base) ; boosting AUC 0.5463, meilleurs 5 % → 57.9% (taux de base 57.3%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : s_tot +0.18 (oui); x_tot +0.18 (oui); x_mn +0.17 (oui); a_tot +0.15 (oui); a_gf +0.15 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 60% | m_p1n <= 0.7102 ET s_fts <= 0.2143 | 638/1063 (60.0%, W 57.0%) | 465/772 (60.2%, W 56.7%) | 736/1230 (59.8%, W 57.1%) | 56.3% | 185/313 (59.1%, W 53.6%) | confirmee sur C |
| 65% | h_o15 >= 0.8571 ET x_mn >= 1.5 | 254/390 (65.1%, W 60.3%) | 176/267 (65.9%, W 60.0%) | 269/427 (63.0%, W 58.3%) | 56.7% | 73/125 (58.4%, W 49.6%) | confirmee sur C |
| 70% | a_btts >= 0.2 ET x_tot >= 3.714 | 170/242 (70.2%, W 64.2%) | 75/106 (70.8%, W 61.5%) | 144/245 (58.8%, W 52.5%) | 57.2% | 66/104 (63.5%, W 53.9%) | rejetee |

### Les deux marquent : non  (`btts|Non`)
- Gagnants / perdants : A 2234/2519  B 1498/1807  C 1911/2564  D 549/684 ; 741 390 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5324, log-loss 0.6857 contre 0.6862 (taux de base) ; boosting AUC 0.5463, meilleurs 5 % → 51.6% (taux de base 42.7%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : s_tot -0.18 (oui); x_tot -0.18 (oui); x_mn -0.17 (oui); a_tot -0.15 (oui); a_gf -0.15 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 50% | a_o15 <= 0.8571 ET x_mx <= 1.571 | 999/1989 (50.2%, W 48.0%) | 601/1202 (50.0%, W 47.2%) | 655/1447 (45.3%, W 42.7%) | 41.5% | 186/421 (44.2%, W 39.5%) | rejetee |
| 55% | s_btts <= 0.4 ET s_tot <= 2.2 | 297/537 (55.3%, W 51.1%) | 157/285 (55.1%, W 49.3%) | 137/276 (49.6%, W 43.8%) | 42.2% | 59/114 (51.7%, W 42.7%) | rejetee |
| 60% | h_def >= 0.2857 ET s_gd <= 1.1429 ET s_o15 <= 0.5 | 115/191 (60.2%, W 53.1%) | 71/117 (60.7%, W 51.6%) | 60/122 (49.2%, W 40.5%) | 42.5% | 18/35 (51.4%, W 35.6%) | rejetee |
| 65% | h_fts <= 0.1429 ET m_ph >= 0.5534 ET x_tot <= 2.357 | 61/90 (67.8%, W 57.6%) | 51/76 (67.1%, W 55.9%) | 42/78 (53.8%, W 42.9%) | 42.5% | 9/19 (47.4%, W 27.3%) | rejetee |

### Victoire domicile  (`1x2|1`)
- Gagnants / perdants : A 2098/2655  B 1474/1831  C 1940/2535  D 536/697 ; 744 051 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6915, log-loss 0.6252 contre 0.6844 (taux de base) ; boosting AUC 0.6848, meilleurs 5 % → 81.2% (taux de base 43.4%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph +0.70 (oui); m_pn2 -0.70 (oui); m_p1n +0.68 (oui); m_pa -0.68 (oui); s_gd +0.45 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 50% | m_ph >= 0.3092 ET p_e <= 0.6 | 1813/3625 (50.0%, W 48.4%) | 1300/2522 (51.5%, W 49.6%) | 1726/3494 (49.4%, W 47.7%) | 21.8% | 468/933 (50.2%, W 47.0%) | confirmee sur C |
| 55% | m_p12 >= 0.6781 ET m_p1n >= 0.6787 | 1485/2693 (55.1%, W 53.3%) | 1076/1925 (55.9%, W 53.7%) | 1421/2581 (55.1%, W 53.1%) | 27.4% | 386/704 (54.8%, W 51.1%) | confirmee sur C |
| 60% | m_p1n >= 0.7387 ET p_h >= 0.2857 | 1095/1823 (60.1%, W 57.8%) | 807/1336 (60.4%, W 57.8%) | 1057/1770 (59.7%, W 57.4%) | 32.6% | 269/439 (61.3%, W 56.6%) | confirmee sur C |
| 65% | m_p12 >= 0.7413 ET m_p1n >= 0.7387 | 789/1213 (65.0%, W 62.3%) | 532/811 (65.6%, W 62.3%) | 832/1328 (62.6%, W 60.0%) | 35.2% | 221/340 (65.0%, W 59.8%) | rejetee |
| 70% | m_p12 >= 0.7512 ET m_p1n >= 0.8048 | 529/753 (70.2%, W 66.9%) | 379/539 (70.3%, W 66.3%) | 571/836 (68.3%, W 65.1%) | 37.6% | 165/221 (74.7%, W 68.5%) | confirmee sur C |
| 75% | h_gd >= -0.75 ET m_ph >= 0.6264 | 357/473 (75.5%, W 71.4%) | 255/340 (75.0%, W 70.1%) | 363/510 (71.2%, W 67.1%) | 39.8% | 106/136 (77.9%, W 70.3%) | rejetee |
| 80% | m_p12 >= 0.7512 ET m_p1n >= 0.8822 | 189/236 (80.1%, W 74.5%) | 148/185 (80.0%, W 73.7%) | 174/217 (80.2%, W 74.4%) | 41.5% | 48/59 (81.4%, W 69.6%) | confirmee sur C |
| 85% | m_ph >= 0.6933 ET s_o15 >= 0.6429 ET s_tot <= 3.7143 | 149/173 (86.1%, W 80.2%) | 114/133 (85.7%, W 78.8%) | 137/172 (79.7%, W 73.0%) | 41.9% | 36/45 (80.0%, W 66.2%) | rejetee |
| 90% | h_sd <= 1.479 ET m_ph >= 0.6933 ET x_mn <= 0.929 | 57/63 (90.5%, W 80.7%) | 64/71 (90.1%, W 81.0%) | 63/72 (87.5%, W 77.9%) | 42.6% | 21/24 (87.5%, W 69.0%) | prometteuse a confirmer |

### Match nul  (`1x2|N`)
- Gagnants / perdants : A 1223/3530  B 861/2444  C 1178/3297  D 311/922 ; 744 547 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.546, log-loss 0.5758 contre 0.5765 (taux de base) ; boosting AUC 0.5435, meilleurs 5 % → 33.2% (taux de base 26.3%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 -0.25 (oui); m_pn +0.25 (oui); m_pover25 -0.16 (oui); m_ph -0.16 (oui); m_pn2 +0.16 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | h_ga <= 1.6 ET m_p12 <= 0.7251 | 491/1632 (30.1%, W 27.9%) | 371/1209 (30.7%, W 28.1%) | 346/1133 (30.5%, W 27.9%) | 24.9% | 80/259 (30.9%, W 25.6%) | confirmee sur C |
| 35% | m_p12 <= 0.7173 ET s_cs >= 0.375 | 148/422 (35.1%, W 30.7%) | 69/196 (35.2%, W 28.9%) | 70/196 (35.7%, W 29.3%) | 25.9% | 20/59 (33.9%, W 23.1%) | confirmee sur C |
| 40% | m_p12 <= 0.7069 ET s_cs >= 0.375 ET x_absd <= 0.417 | 85/208 (40.9%, W 34.4%) | 42/97 (43.3%, W 33.9%) | 27/91 (29.7%, W 21.3%) | 26.2% | 8/19 (42.1%, W 23.1%) | rejetee |

### Victoire extérieur  (`1x2|2`)
- Gagnants / perdants : A 1432/3321  B 970/2335  C 1357/3118  D 386/847 ; 741 753 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6722, log-loss 0.5717 contre 0.6136 (taux de base) ; boosting AUC 0.6698, meilleurs 5 % → 65.9% (taux de base 30.3%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph -0.69 (oui); m_pn2 +0.69 (oui); m_p1n -0.68 (oui); m_pa +0.68 (oui); s_gd -0.46 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 35% | m_p1n <= 0.8048 ET s_pts <= 1.1429 | 1201/3419 (35.1%, W 33.5%) | 844/2410 (35.0%, W 33.1%) | 1114/3158 (35.3%, W 33.6%) | 18.4% | 318/831 (38.3%, W 35.0%) | confirmee sur C |
| 40% | m_p12 >= 0.691 ET m_ph <= 0.4609 | 956/2389 (40.0%, W 38.1%) | 685/1712 (40.0%, W 37.7%) | 935/2354 (39.7%, W 37.8%) | 19.9% | 292/683 (42.8%, W 39.1%) | confirmee sur C |
| 45% | m_p12 >= 0.691 ET m_ph <= 0.3908 | 716/1587 (45.1%, W 42.7%) | 510/1132 (45.1%, W 42.2%) | 720/1598 (45.1%, W 42.6%) | 22.1% | 218/441 (49.4%, W 44.8%) | confirmee sur C |
| 50% | m_p1n <= 0.5957 ET s_gf <= 1.5714 | 471/942 (50.0%, W 46.8%) | 357/691 (51.7%, W 47.9%) | 501/955 (52.5%, W 49.3%) | 24.3% | 152/278 (54.7%, W 48.8%) | confirmee sur C |
| 55% | m_p12 >= 0.7251 ET m_ph <= 0.3092 | 314/566 (55.5%, W 51.4%) | 248/442 (56.1%, W 51.4%) | 360/663 (54.3%, W 50.5%) | 26.2% | 127/215 (59.1%, W 52.4%) | confirmee sur C |
| 60% | m_p1n <= 0.5258 ET s_fts >= 0.2 | 188/307 (61.2%, W 55.7%) | 157/260 (60.4%, W 54.3%) | 197/341 (57.8%, W 52.5%) | 28.1% | 64/102 (62.7%, W 53.1%) | confirmee sur C |
| 65% | m_ph <= 0.2048 ET s_gf <= 1.25 | 162/236 (68.6%, W 62.5%) | 136/209 (65.1%, W 58.4%) | 178/272 (65.4%, W 59.6%) | 28.1% | 67/89 (75.3%, W 65.4%) | confirmee sur C |
| 70% | h_btts <= 0.6 ET m_ph <= 0.2048 ET p_btts >= 0.25 | 114/162 (70.4%, W 62.9%) | 102/145 (70.3%, W 62.5%) | 113/170 (66.5%, W 59.1%) | 28.9% | 46/57 (80.7%, W 68.7%) | confirmee sur C |
| 75% | a_ga >= 1 ET m_ph <= 0.2048 ET s_fts >= 0.2 | 82/108 (75.9%, W 67.1%) | 59/78 (75.6%, W 65.1%) | 79/111 (71.2%, W 62.2%) | 29.3% | 28/36 (77.8%, W 61.9%) | confirmee sur C |

### Domicile ne perd pas (1N)  (`double_chance|1N`)
- Gagnants / perdants : A 3321/1432  B 2335/970  C 3118/1357  D 847/386 ; 744 119 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6722, log-loss 0.5717 contre 0.6136 (taux de base) ; boosting AUC 0.6698, meilleurs 5 % → 92.4% (taux de base 69.7%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph +0.69 (oui); m_pn2 -0.69 (oui); m_p1n +0.68 (oui); m_pa -0.68 (oui); s_gd +0.46 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 75% | m_p1n >= 0.5957 ET m_ph >= 0.3092 | 2775/3700 (75.0%, W 73.6%) | 1965/2552 (77.0%, W 75.3%) | 2633/3469 (75.9%, W 74.5%) | 48.2% | 710/939 (75.6%, W 72.8%) | confirmee sur C |
| 80% | a_cs >= 0 ET m_ph >= 0.4233 | 1905/2365 (80.5%, W 78.9%) | 1356/1664 (81.5%, W 79.5%) | 1878/2343 (80.2%, W 78.5%) | 58.2% | 523/640 (81.7%, W 78.5%) | confirmee sur C |
| 85% | h_gd >= 0.2857 ET m_ph >= 0.4609 | 1103/1297 (85.0%, W 83.0%) | 808/946 (85.4%, W 83.0%) | 1124/1363 (82.5%, W 80.4%) | 64.1% | 293/335 (87.5%, W 83.5%) | rejetee |
| 90% | a_cs >= 0 ET m_p1n >= 0.8496 | 428/473 (90.5%, W 87.5%) | 317/343 (92.4%, W 89.1%) | 422/471 (89.6%, W 86.5%) | 67.3% | 118/122 (96.7%, W 91.9%) | confirmee sur C |
| 95% | a_tot >= 1.5714 ET m_p1n >= 0.8822 | 215/226 (95.1%, W 91.5%) | 173/182 (95.0%, W 90.9%) | 204/220 (92.7%, W 88.5%) | 68.5% | 56/57 (98.2%, W 90.7%) | confirmee sur C |

### Extérieur ne perd pas (N2)  (`double_chance|N2`)
- Gagnants / perdants : A 2655/2098  B 1831/1474  C 2535/1940  D 697/536 ; 744 245 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6915, log-loss 0.6252 contre 0.6844 (taux de base) ; boosting AUC 0.6848, meilleurs 5 % → 86.6% (taux de base 56.6%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph -0.70 (oui); m_pn2 +0.70 (oui); m_p1n -0.68 (oui); m_pa +0.68 (oui); s_gd -0.45 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 60% | a_cs >= 0 ET m_ph <= 0.5534 | 2338/3787 (61.7%, W 60.2%) | 1629/2646 (61.6%, W 59.7%) | 2180/3455 (63.1%, W 61.5%) | 34.8% | 606/951 (63.7%, W 60.6%) | confirmee sur C |
| 65% | a_cs >= 0 ET m_ph <= 0.4609 | 1879/2840 (66.2%, W 64.4%) | 1319/1985 (66.5%, W 64.3%) | 1756/2570 (68.3%, W 66.5%) | 40.9% | 488/718 (68.0%, W 64.5%) | confirmee sur C |
| 70% | a_cs >= 0 ET m_ph <= 0.3908 | 1350/1893 (71.3%, W 69.2%) | 949/1325 (71.6%, W 69.1%) | 1273/1744 (73.0%, W 70.9%) | 46.2% | 336/465 (72.3%, W 68.0%) | confirmee sur C |
| 75% | m_ph <= 0.3526 ET s_pts <= 0.8571 | 978/1303 (75.1%, W 72.6%) | 708/941 (75.2%, W 72.4%) | 891/1171 (76.1%, W 73.6%) | 49.8% | 243/330 (73.6%, W 68.6%) | confirmee sur C |
| 80% | m_p12 >= 0.7251 ET m_ph <= 0.3092 | 453/566 (80.0%, W 76.5%) | 370/442 (83.7%, W 80.0%) | 532/663 (80.2%, W 77.0%) | 52.5% | 177/215 (82.3%, W 76.7%) | confirmee sur C |
| 85% | m_p12 >= 0.7512 ET m_p1n <= 0.5258 | 242/282 (85.8%, W 81.3%) | 193/224 (86.2%, W 81.0%) | 324/381 (85.0%, W 81.1%) | 54.0% | 100/112 (89.3%, W 82.2%) | confirmee sur C |
| 90% | a_gd <= 0.7143 ET m_ph <= 0.2048 ET x_absd <= 1 | 127/141 (90.1%, W 84.0%) | 105/116 (90.5%, W 83.8%) | 164/183 (89.6%, W 84.4%) | 55.2% | 46/50 (92.0%, W 81.2%) | confirmee sur C |

### Pas de nul (12)  (`double_chance|12`)
- Gagnants / perdants : A 3530/1223  B 2444/861  C 3297/1178  D 922/311 ; 743 035 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.546, log-loss 0.5758 contre 0.5765 (taux de base) ; boosting AUC 0.5435, meilleurs 5 % → 78.5% (taux de base 73.7%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 +0.25 (oui); m_pn -0.25 (oui); m_pover25 +0.16 (oui); m_ph +0.16 (oui); m_pn2 -0.16 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 80% | a_tot >= 2 ET m_p12 >= 0.7512 | 1049/1307 (80.3%, W 78.0%) | 668/835 (80.0%, W 77.1%) | 1279/1619 (79.0%, W 77.0%) | 70.7% | 340/451 (75.4%, W 71.2%) | confirmee sur C |
| 85% | m_p12 >= 0.7935 ET x_ext <= 1.875 | 380/445 (85.4%, W 81.8%) | 252/296 (85.1%, W 80.6%) | 419/511 (82.0%, W 78.4%) | 72.6% | 115/138 (83.3%, W 76.2%) | rejetee |
| 90% | a_btts <= 0.8571 ET a_v2 <= 0.1429 ET m_ph >= 0.6933 | 153/170 (90.0%, W 84.6%) | 131/145 (90.3%, W 84.5%) | 165/194 (85.0%, W 79.4%) | 73.2% | 42/50 (84.0%, W 71.5%) | rejetee |

### Handicap -1,5 domicile  (`handicap_-1.5|domicile`)
- Gagnants / perdants : A 1040/3713  B 690/2615  C 967/3508  D 271/962 ; 743 941 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6976, log-loss 0.4793 contre 0.5219 (taux de base) ; boosting AUC 0.6894, meilleurs 5 % → 47.1% (taux de base 21.6%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph +0.72 (oui); m_pn2 -0.72 (oui); m_p1n +0.69 (oui); m_pa -0.69 (oui); m_p12 +0.46 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | m_p12 >= 0.7173 ET m_ph >= 0.3526 | 737/2441 (30.2%, W 28.4%) | 483/1608 (30.0%, W 27.9%) | 762/2574 (29.6%, W 27.9%) | 10.8% | 215/737 (29.2%, W 26.0%) | confirmee sur C |
| 35% | m_p12 >= 0.7333 ET m_p1n >= 0.6787 | 570/1621 (35.2%, W 32.9%) | 370/1053 (35.1%, W 32.3%) | 584/1758 (33.2%, W 31.1%) | 14.1% | 170/482 (35.3%, W 31.1%) | confirmee sur C |
| 40% | a_cs >= 0 ET m_p1n >= 0.8048 | 380/947 (40.1%, W 37.0%) | 267/664 (40.2%, W 36.5%) | 376/954 (39.4%, W 36.4%) | 16.8% | 109/250 (43.6%, W 37.6%) | confirmee sur C |
| 45% | m_p12 >= 0.7658 ET m_ph >= 0.5534 | 318/705 (45.1%, W 41.5%) | 212/471 (45.0%, W 40.6%) | 343/823 (41.7%, W 38.4%) | 17.1% | 100/222 (45.1%, W 38.6%) | rejetee |
| 50% | h_fts <= 0.2857 ET m_ph >= 0.6264 | 196/392 (50.0%, W 45.1%) | 146/283 (51.6%, W 45.8%) | 190/399 (47.6%, W 42.8%) | 19.1% | 60/115 (52.2%, W 43.1%) | confirmee sur C |
| 55% | h_btts >= 0.2857 ET m_ph >= 0.6933 | 116/210 (55.2%, W 48.5%) | 90/161 (55.9%, W 48.2%) | 123/227 (54.2%, W 47.7%) | 19.9% | 21/52 (40.4%, W 28.2%) | confirmee sur C |
| 60% | a_tot <= 3.7143 ET m_p12 >= 0.8176 ET p_h >= 0.5714 | 103/170 (60.6%, W 53.1%) | 74/123 (60.2%, W 51.3%) | 92/177 (52.0%, W 44.6%) | 20.4% | 28/55 (50.9%, W 38.1%) | rejetee |

### Handicap +1,5 extérieur  (`handicap_-1.5|exterieur`)
- Gagnants / perdants : A 3713/1040  B 2615/690  C 3508/967  D 962/271 ; 742 619 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6976, log-loss 0.4793 contre 0.5219 (taux de base) ; boosting AUC 0.6894, meilleurs 5 % → 97.3% (taux de base 78.4%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph -0.72 (oui); m_pn2 +0.72 (oui); m_p1n -0.69 (oui); m_pa +0.69 (oui); m_p12 -0.46 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 85% | m_ph <= 0.5031 ET s_gd <= 1.4286 | 2577/3031 (85.0%, W 83.7%) | 1820/2132 (85.4%, W 83.8%) | 2311/2697 (85.7%, W 84.3%) | 67.3% | 639/745 (85.8%, W 83.1%) | confirmee sur C |
| 90% | m_ph <= 0.3526 ET s_gf <= 1.5714 | 1270/1410 (90.1%, W 88.4%) | 945/1032 (91.6%, W 89.7%) | 1192/1311 (90.9%, W 89.2%) | 73.2% | 335/367 (91.3%, W 87.9%) | confirmee sur C |
| 95% | m_p1n <= 0.5258 ET s_fts >= 0.1429 | 309/323 (95.7%, W 92.9%) | 248/260 (95.4%, W 92.1%) | 320/343 (93.3%, W 90.1%) | 77.1% | 104/107 (97.2%, W 92.1%) | confirmee sur C |

### Handicap +1,5 domicile  (`handicap_1.5|domicile`)
- Gagnants / perdants : A 4127/626  B 2886/419  C 3896/579  D 1077/156 ; 743 865 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.7029, log-loss 0.3565 contre 0.3852 (taux de base) ; boosting AUC 0.6966, meilleurs 5 % → 97.8% (taux de base 87.1%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n +0.75 (oui); m_pa -0.75 (oui); m_ph +0.74 (oui); m_pn2 -0.74 (oui); s_gd +0.52 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 90% | a_cs >= 0 ET m_p1n >= 0.5957 | 3426/3787 (90.5%, W 89.5%) | 2371/2612 (90.8%, W 89.6%) | 3204/3516 (91.1%, W 90.1%) | 72.2% | 867/951 (91.2%, W 89.2%) | confirmee sur C |
| 95% | m_ph >= 0.4609 ET s_gd >= 0.5 | 1387/1460 (95.0%, W 93.8%) | 1000/1049 (95.3%, W 93.9%) | 1396/1476 (94.6%, W 93.3%) | 83.4% | 400/411 (97.3%, W 95.3%) | confirmee sur C |

### Handicap -1,5 extérieur  (`handicap_1.5|exterieur`)
- Gagnants / perdants : A 626/4127  B 419/2886  C 579/3896  D 156/1077 ; 744 377 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.7029, log-loss 0.3565 contre 0.3852 (taux de base) ; boosting AUC 0.6966, meilleurs 5 % → 34.1% (taux de base 12.9%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n -0.75 (oui); m_pa +0.75 (oui); m_ph -0.74 (oui); m_pn2 +0.74 (oui); s_gd -0.52 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | m_p12 >= 0.7512 ET m_p1n <= 0.7102 | 124/377 (32.9%, W 28.3%) | 72/237 (30.4%, W 24.9%) | 157/517 (30.4%, W 26.6%) | 10.7% | 44/175 (25.1%, W 19.3%) | confirmee sur C |
| 35% | m_p12 >= 0.7658 ET m_ph <= 0.5534 | 87/244 (35.7%, W 29.9%) | 58/164 (35.4%, W 28.5%) | 103/350 (29.4%, W 24.9%) | 11.5% | 25/105 (23.8%, W 16.7%) | rejetee |
| 40% | m_p12 >= 0.7658 ET m_p1n <= 0.7387 ET s_o15 >= 0.6429 | 69/171 (40.4%, W 33.3%) | 49/122 (40.2%, W 31.9%) | 88/261 (33.7%, W 28.2%) | 11.7% | 21/81 (25.9%, W 17.6%) | rejetee |

### Plus de 0,5 buts du domicile  (`over_under_domicile_0.5|plus`)
- Gagnants / perdants : A 3675/1078  B 2573/732  C 3545/930  D 979/254 ; 744 107 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6474, log-loss 0.488 contre 0.5121 (taux de base) ; boosting AUC 0.6393, meilleurs 5 % → 95.5% (taux de base 79.2%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph +0.54 (oui); m_pn2 -0.54 (oui); m_p1n +0.47 (oui); m_pa -0.47 (oui); x_dom +0.39 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 80% | m_p12 >= 0.691 ET m_ph >= 0.2547 | 3060/3799 (80.5%, W 79.3%) | 2144/2631 (81.5%, W 80.0%) | 3075/3732 (82.4%, W 81.1%) | 63.3% | 861/1047 (82.2%, W 79.8%) | confirmee sur C |
| 85% | m_p12 >= 0.7173 ET m_ph >= 0.3908 | 1895/2228 (85.0%, W 83.5%) | 1294/1509 (85.8%, W 83.9%) | 1983/2313 (85.7%, W 84.2%) | 72.2% | 577/673 (85.7%, W 82.9%) | confirmee sur C |
| 90% | m_p12 >= 0.7333 ET m_ph >= 0.5534 | 837/928 (90.2%, W 88.1%) | 585/649 (90.1%, W 87.6%) | 906/1005 (90.1%, W 88.1%) | 76.0% | 257/277 (92.8%, W 89.1%) | confirmee sur C |
| 95% | m_p12 >= 0.7935 ET x_dom >= 1.833 | 259/270 (95.9%, W 92.8%) | 171/180 (95.0%, W 90.8%) | 285/300 (95.0%, W 91.9%) | 78.1% | 81/88 (92.0%, W 84.5%) | confirmee sur C |

### Moins de 0,5 buts du domicile  (`over_under_domicile_0.5|moins`)
- Gagnants / perdants : A 1078/3675  B 732/2573  C 930/3545  D 254/979 ; 743 325 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6474, log-loss 0.488 contre 0.5121 (taux de base) ; boosting AUC 0.6393, meilleurs 5 % → 39.0% (taux de base 20.8%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph -0.54 (oui); m_pn2 +0.54 (oui); m_p1n -0.47 (oui); m_pa +0.47 (oui); x_dom -0.39 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | m_ph <= 0.4233 ET s_fts >= 0.0833 | 646/2153 (30.0%, W 28.1%) | 434/1442 (30.1%, W 27.8%) | 529/1850 (28.6%, W 26.6%) | 15.3% | 150/535 (28.0%, W 24.4%) | confirmee sur C |
| 35% | h_pts <= 2.1429 ET m_ph <= 0.3092 | 312/890 (35.1%, W 32.0%) | 252/678 (37.2%, W 33.6%) | 290/844 (34.4%, W 31.2%) | 17.6% | 85/244 (34.8%, W 29.1%) | confirmee sur C |
| 40% | h_gd <= 0.4286 ET m_ph <= 0.2547 | 161/402 (40.1%, W 35.4%) | 137/332 (41.3%, W 36.1%) | 157/410 (38.3%, W 33.7%) | 19.0% | 48/119 (40.3%, W 32.0%) | confirmee sur C |
| 45% | a_gf <= 2.1667 ET m_ph <= 0.2547 ET s_fts >= 0.25 | 104/230 (45.2%, W 38.9%) | 85/188 (45.2%, W 38.3%) | 81/203 (39.9%, W 33.4%) | 19.9% | 27/60 (45.0%, W 33.1%) | confirmee sur C |
| 50% | h_fts >= 0.2 ET h_o35 <= 0.1429 ET m_ph <= 0.2547 | 68/136 (50.0%, W 41.7%) | 60/111 (54.0%, W 44.8%) | 62/149 (41.6%, W 34.0%) | 20.1% | 13/26 (50.0%, W 32.1%) | rejetee |

### Plus de 1,5 buts du domicile  (`over_under_domicile_1.5|plus`)
- Gagnants / perdants : A 2067/2686  B 1449/1856  C 2064/2411  D 557/676 ; 742 633 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6567, log-loss 0.6524 contre 0.6915 (taux de base) ; boosting AUC 0.6553, meilleurs 5 % → 68.2% (taux de base 46.1%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph +0.49 (oui); m_pn2 -0.49 (oui); m_p1n +0.43 (oui); m_pa -0.43 (oui); m_p12 +0.39 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 50% | m_p12 >= 0.691 ET m_ph >= 0.3526 | 1530/3028 (50.5%, W 48.8%) | 1072/2112 (50.8%, W 48.6%) | 1611/3020 (53.3%, W 51.6%) | 31.1% | 433/843 (51.4%, W 48.0%) | confirmee sur C |
| 55% | m_p12 >= 0.7251 ET m_p1n >= 0.5957 | 1213/2202 (55.1%, W 53.0%) | 780/1411 (55.3%, W 52.7%) | 1345/2401 (56.0%, W 54.0%) | 34.7% | 368/681 (54.0%, W 50.3%) | confirmee sur C |
| 60% | m_p12 >= 0.7413 ET m_ph >= 0.3908 | 845/1406 (60.1%, W 57.5%) | 532/877 (60.7%, W 57.4%) | 990/1613 (61.4%, W 59.0%) | 37.5% | 261/451 (57.9%, W 53.3%) | confirmee sur C |
| 65% | m_p12 >= 0.7658 ET m_ph >= 0.2547 | 519/770 (67.4%, W 64.0%) | 320/487 (65.7%, W 61.4%) | 623/937 (66.5%, W 63.4%) | 40.7% | 162/254 (63.8%, W 57.7%) | confirmee sur C |
| 70% | m_ph >= 0.6264 ET p_o15 >= 0.6 | 302/431 (70.1%, W 65.6%) | 213/303 (70.3%, W 64.9%) | 330/465 (71.0%, W 66.7%) | 43.2% | 84/127 (66.1%, W 57.6%) | confirmee sur C |
| 75% | h_vic >= 0.1429 ET m_p12 >= 0.7935 ET s_gf >= 0.8571 | 177/236 (75.0%, W 69.1%) | 138/184 (75.0%, W 68.3%) | 217/286 (75.9%, W 70.6%) | 44.1% | 46/73 (63.0%, W 51.5%) | confirmee sur C |
| 80% | m_p12 >= 0.7935 ET s_gf >= 0.8571 ET s_nul <= 0.2 | 84/105 (80.0%, W 71.4%) | 65/81 (80.2%, W 70.3%) | 100/126 (79.4%, W 71.5%) | 45.2% | 25/39 (64.1%, W 48.4%) | confirmee sur C |

### Moins de 1,5 buts du domicile  (`over_under_domicile_1.5|moins`)
- Gagnants / perdants : A 2686/2067  B 1856/1449  C 2411/2064  D 676/557 ; 743 017 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6567, log-loss 0.6524 contre 0.6915 (taux de base) ; boosting AUC 0.6553, meilleurs 5 % → 78.0% (taux de base 53.9%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph -0.49 (oui); m_pn2 +0.49 (oui); m_p1n -0.43 (oui); m_pa +0.43 (oui); m_p12 -0.39 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 60% | a_cs >= 0 ET m_ph <= 0.5534 | 2325/3787 (61.4%, W 59.8%) | 1611/2646 (60.9%, W 59.0%) | 2047/3455 (59.2%, W 57.6%) | 35.7% | 574/951 (60.4%, W 57.2%) | rejetee |
| 65% | a_cs >= 0 ET m_ph <= 0.4233 | 1551/2369 (65.5%, W 63.5%) | 1069/1641 (65.1%, W 62.8%) | 1397/2132 (65.5%, W 63.5%) | 43.3% | 387/589 (65.7%, W 61.8%) | confirmee sur C |
| 70% | h_gf <= 1.5714 ET m_ph <= 0.3526 | 723/1028 (70.3%, W 67.5%) | 544/773 (70.4%, W 67.1%) | 627/889 (70.5%, W 67.5%) | 49.8% | 184/265 (69.4%, W 63.6%) | confirmee sur C |
| 75% | a_o35 <= 0.1429 ET m_ph <= 0.3092 | 242/322 (75.2%, W 70.2%) | 203/268 (75.8%, W 70.3%) | 234/318 (73.6%, W 68.5%) | 52.4% | 55/67 (82.1%, W 71.2%) | confirmee sur C |
| 80% | a_o35 <= 0.4286 ET h_fts >= 0.2 ET m_ph <= 0.2048 | 116/144 (80.6%, W 73.3%) | 108/133 (81.2%, W 73.7%) | 107/137 (78.1%, W 70.5%) | 53.1% | 44/47 (93.6%, W 82.8%) | confirmee sur C |

### Plus de 2,5 buts du domicile  (`over_under_domicile_2.5|plus`)
- Gagnants / perdants : A 935/3818  B 636/2669  C 952/3523  D 261/972 ; 742 795 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6875, log-loss 0.4813 contre 0.5184 (taux de base) ; boosting AUC 0.6826, meilleurs 5 % → 50.7% (taux de base 21.3%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph +0.66 (oui); m_pn2 -0.66 (oui); m_p1n +0.59 (oui); m_pa -0.59 (oui); m_p12 +0.52 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | m_p12 >= 0.7333 ET m_p1n >= 0.5957 | 559/1837 (30.4%, W 28.4%) | 342/1128 (30.3%, W 27.7%) | 642/2026 (31.7%, W 29.7%) | 12.7% | 175/576 (30.4%, W 26.8%) | confirmee sur C |
| 35% | m_p12 >= 0.7512 ET m_ph >= 0.2547 | 418/1161 (36.0%, W 33.3%) | 245/688 (35.6%, W 32.1%) | 498/1395 (35.7%, W 33.2%) | 14.7% | 141/400 (35.2%, W 30.7%) | confirmee sur C |
| 40% | m_p12 >= 0.7658 ET m_ph >= 0.2547 | 317/770 (41.2%, W 37.7%) | 195/487 (40.0%, W 35.8%) | 378/937 (40.3%, W 37.2%) | 16.2% | 103/254 (40.6%, W 34.7%) | confirmee sur C |
| 45% | m_p12 >= 0.7935 ET s_pts >= -0.3238 | 190/420 (45.2%, W 40.5%) | 123/269 (45.7%, W 39.9%) | 203/472 (43.0%, W 38.6%) | 18.7% | 52/132 (39.4%, W 31.5%) | confirmee sur C |
| 50% | a_cs >= 0 ET m_ph >= 0.6933 | 119/237 (50.2%, W 43.9%) | 87/170 (51.2%, W 43.7%) | 116/238 (48.7%, W 42.5%) | 19.7% | 25/64 (39.1%, W 28.1%) | confirmee sur C |
| 55% | a_gf >= 0.4286 ET a_o25 <= 0.7143 ET m_ph >= 0.6933 | 88/160 (55.0%, W 47.3%) | 72/130 (55.4%, W 46.8%) | 90/189 (47.6%, W 40.6%) | 20.1% | 16/38 (42.1%, W 27.9%) | rejetee |
| 60% | a_d2 <= 0.3333 ET m_p12 >= 0.8176 ET s_gf >= 0.6333 | 51/85 (60.0%, W 49.4%) | 42/70 (60.0%, W 48.3%) | 51/105 (48.6%, W 39.2%) | 20.6% | 12/32 (37.5%, W 22.9%) | rejetee |

### Moins de 2,5 buts du domicile  (`over_under_domicile_2.5|moins`)
- Gagnants / perdants : A 3818/935  B 2669/636  C 3523/952  D 972/261 ; 742 519 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6875, log-loss 0.4813 contre 0.5184 (taux de base) ; boosting AUC 0.6826, meilleurs 5 % → 94.2% (taux de base 78.7%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_ph -0.66 (oui); m_pn2 +0.66 (oui); m_p1n -0.59 (oui); m_pa +0.59 (oui); m_p12 -0.52 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 85% | m_ph <= 0.5534 ET x_dom <= 2.214 | 3162/3713 (85.2%, W 84.0%) | 2227/2617 (85.1%, W 83.7%) | 2811/3364 (83.6%, W 82.3%) | 64.1% | 766/904 (84.7%, W 82.2%) | rejetee |
| 90% | m_ph <= 0.3526 ET s_pts <= 1.4286 | 1277/1406 (90.8%, W 89.2%) | 920/1022 (90.0%, W 88.0%) | 1169/1301 (89.8%, W 88.1%) | 74.2% | 322/362 (88.9%, W 85.3%) | confirmee sur C |
| 95% | h_pts <= 2.1429 ET m_ph <= 0.2048 | 213/223 (95.5%, W 91.9%) | 195/205 (95.1%, W 91.2%) | 246/261 (94.2%, W 90.7%) | 77.8% | 84/87 (96.5%, W 90.3%) | confirmee sur C |

### Plus de 0,5 buts de l'extérieur  (`over_under_exterieur_0.5|plus`)
- Gagnants / perdants : A 3253/1500  B 2291/1014  C 3211/1264  D 872/361 ; 744 921 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6258, log-loss 0.5742 contre 0.5979 (taux de base) ; boosting AUC 0.6287, meilleurs 5 % → 91.0% (taux de base 71.8%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n -0.46 (oui); m_pa +0.46 (oui); m_ph -0.41 (oui); m_pn2 +0.41 (oui); x_ext +0.29 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 75% | a_def <= 0.6 ET m_p1n <= 0.7387 | 1856/2474 (75.0%, W 73.3%) | 1314/1729 (76.0%, W 73.9%) | 1858/2362 (78.7%, W 77.0%) | 64.0% | 511/649 (78.7%, W 75.4%) | confirmee sur C |
| 80% | m_p12 >= 0.7069 ET m_p1n <= 0.6787 | 1194/1481 (80.6%, W 78.5%) | 802/987 (81.3%, W 78.7%) | 1297/1582 (82.0%, W 80.0%) | 66.2% | 381/473 (80.5%, W 76.7%) | confirmee sur C |
| 85% | m_p12 >= 0.7333 ET m_ph <= 0.4233 | 647/761 (85.0%, W 82.3%) | 406/465 (87.3%, W 84.0%) | 808/934 (86.5%, W 84.2%) | 67.9% | 245/295 (83.0%, W 78.3%) | confirmee sur C |
| 90% | m_ph <= 0.2048 ET x_ext >= 0.625 | 212/235 (90.2%, W 85.7%) | 192/211 (91.0%, W 86.4%) | 255/272 (93.8%, W 90.2%) | 70.3% | 81/89 (91.0%, W 83.2%) | confirmee sur C |
| 95% | a_ga <= 1.2857 ET m_p12 >= 0.7658 ET m_p1n <= 0.5258 | 107/112 (95.5%, W 90.0%) | 93/97 (95.9%, W 89.9%) | 111/117 (94.9%, W 89.3%) | 71.1% | 43/48 (89.6%, W 77.8%) | confirmee sur C |

### Moins de 0,5 buts de l'extérieur  (`over_under_exterieur_0.5|moins`)
- Gagnants / perdants : A 1500/3253  B 1014/2291  C 1264/3211  D 361/872 ; 741 439 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6258, log-loss 0.5742 contre 0.5979 (taux de base) ; boosting AUC 0.6287, meilleurs 5 % → 40.4% (taux de base 28.2%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n +0.46 (oui); m_pa -0.46 (oui); m_ph +0.41 (oui); m_pn2 -0.41 (oui); x_ext -0.29 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 35% | a_gf <= 1.8571 ET m_ph >= 0.3092 | 1224/3445 (35.5%, W 34.0%) | 837/2389 (35.0%, W 33.1%) | 1034/3248 (31.8%, W 30.3%) | 18.7% | 294/870 (33.8%, W 30.7%) | rejetee |
| 40% | m_p1n >= 0.7387 ET m_ph >= 0.3908 | 757/1890 (40.1%, W 37.9%) | 542/1355 (40.0%, W 37.4%) | 665/1811 (36.7%, W 34.5%) | 22.5% | 190/472 (40.2%, W 35.9%) | rejetee |
| 45% | h_ga <= 1.2857 ET m_p1n >= 0.8048 | 337/740 (45.5%, W 42.0%) | 236/505 (46.7%, W 42.4%) | 275/666 (41.3%, W 37.6%) | 26.0% | 86/177 (48.6%, W 41.3%) | rejetee |
| 50% | m_p1n >= 0.8822 ET x_ext <= 1.714 | 117/234 (50.0%, W 43.6%) | 93/185 (50.3%, W 43.1%) | 106/221 (48.0%, W 41.5%) | 27.2% | 34/58 (58.6%, W 45.8%) | confirmee sur C |
| 55% | m_p1n >= 0.8822 ET s_btts >= 0.2857 ET x_mn <= 0.929 | 69/124 (55.6%, W 46.9%) | 69/124 (55.6%, W 46.9%) | 59/116 (50.9%, W 41.9%) | 27.6% | 19/34 (55.9%, W 39.5%) | confirmee sur C |

### Plus de 1,5 buts de l'extérieur  (`over_under_exterieur_1.5|plus`)
- Gagnants / perdants : A 1599/3154  B 1116/2189  C 1629/2846  D 451/782 ; 745 765 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6286, log-loss 0.6334 contre 0.6574 (taux de base) ; boosting AUC 0.6303, meilleurs 5 % → 61.9% (taux de base 36.4%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n -0.52 (oui); m_pa +0.52 (oui); m_ph -0.47 (oui); m_pn2 +0.47 (oui); x_ext +0.35 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 40% | m_p12 >= 0.691 ET m_p1n <= 0.7699 | 1157/2873 (40.3%, W 38.5%) | 812/2015 (40.3%, W 38.2%) | 1196/2846 (42.0%, W 40.2%) | 26.6% | 347/827 (42.0%, W 38.6%) | confirmee sur C |
| 45% | m_p12 >= 0.6781 ET m_p1n <= 0.6787 | 820/1804 (45.5%, W 43.2%) | 572/1243 (46.0%, W 43.3%) | 835/1782 (46.9%, W 44.5%) | 29.5% | 243/516 (47.1%, W 42.8%) | confirmee sur C |
| 50% | m_p12 >= 0.7173 ET m_p1n <= 0.6787 | 618/1226 (50.4%, W 47.6%) | 403/785 (51.3%, W 47.8%) | 688/1393 (49.4%, W 46.8%) | 30.5% | 213/429 (49.6%, W 44.9%) | confirmee sur C |
| 55% | m_p12 >= 0.7251 ET m_ph <= 0.3526 | 394/705 (55.9%, W 52.2%) | 284/509 (55.8%, W 51.4%) | 451/850 (53.1%, W 49.7%) | 32.5% | 144/267 (53.9%, W 47.9%) | confirmee sur C |
| 60% | m_p12 >= 0.7658 ET m_ph <= 0.5534 | 153/244 (62.7%, W 56.5%) | 100/164 (61.0%, W 53.3%) | 198/350 (56.6%, W 51.3%) | 34.7% | 61/105 (58.1%, W 48.5%) | confirmee sur C |
| 65% | m_p12 >= 0.7658 ET m_p1n <= 0.7387 ET s_gf <= 0.8571 | 135/195 (69.2%, W 62.4%) | 95/145 (65.5%, W 57.5%) | 175/275 (63.6%, W 57.8%) | 34.6% | 54/84 (64.3%, W 53.6%) | confirmee sur C |
| 70% | a_v2 >= 0.1429 ET m_p12 >= 0.7658 ET m_ph <= 0.5031 | 101/144 (70.1%, W 62.2%) | 68/96 (70.8%, W 61.1%) | 100/148 (67.6%, W 59.7%) | 35.3% | 39/59 (66.1%, W 53.4%) | confirmee sur C |

### Moins de 1,5 buts de l'extérieur  (`over_under_exterieur_1.5|moins`)
- Gagnants / perdants : A 3154/1599  B 2189/1116  C 2846/1629  D 782/451 ; 742 191 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6286, log-loss 0.6334 contre 0.6574 (taux de base) ; boosting AUC 0.6303, meilleurs 5 % → 82.1% (taux de base 63.6%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n +0.52 (oui); m_pa -0.52 (oui); m_ph +0.47 (oui); m_pn2 -0.47 (oui); x_ext -0.35 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 70% | a_cs >= 0 ET m_p1n >= 0.5957 | 2680/3787 (70.8%, W 69.3%) | 1853/2612 (70.9%, W 69.2%) | 2388/3516 (67.9%, W 66.4%) | 47.8% | 650/951 (68.3%, W 65.3%) | rejetee |
| 75% | h_fts <= 0.4286 ET m_p1n >= 0.7102 | 1651/2201 (75.0%, W 73.2%) | 1189/1584 (75.1%, W 72.9%) | 1518/2111 (71.9%, W 70.0%) | 56.2% | 378/523 (72.3%, W 68.3%) | rejetee |
| 80% | a_pts <= 1.7143 ET m_p1n >= 0.8048 | 723/903 (80.1%, W 77.3%) | 521/642 (81.2%, W 78.0%) | 685/898 (76.3%, W 73.4%) | 60.4% | 181/224 (80.8%, W 75.1%) | rejetee |
| 85% | h_o35 <= 0.5714 ET m_p1n >= 0.8496 | 336/394 (85.3%, W 81.4%) | 234/271 (86.4%, W 81.8%) | 284/352 (80.7%, W 76.2%) | 62.1% | 88/99 (88.9%, W 81.2%) | rejetee |
| 90% | h_o25 <= 0.5 ET h_vic >= 0.4 ET m_p1n >= 0.8496 | 167/185 (90.3%, W 85.2%) | 96/104 (92.3%, W 85.5%) | 90/111 (81.1%, W 72.8%) | 63.1% | 38/45 (84.4%, W 71.2%) | rejetee |

### Plus de 2,5 buts de l'extérieur  (`over_under_exterieur_2.5|plus`)
- Gagnants / perdants : A 613/4140  B 397/2908  C 631/3844  D 162/1071 ; 743 725 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6483, log-loss 0.3909 contre 0.4074 (taux de base) ; boosting AUC 0.6568, meilleurs 5 % → 33.6% (taux de base 14.1%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n -0.61 (oui); m_pa +0.61 (oui); m_ph -0.57 (oui); m_pn2 +0.57 (oui); x_ext +0.41 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 30% | h_tot >= 3.2857 ET m_p1n <= 0.5957 | 62/204 (30.4%, W 24.5%) | 45/148 (30.4%, W 23.6%) | 58/212 (27.4%, W 21.8%) | 13.4% | 18/70 (25.7%, W 16.9%) | confirmee sur C |
| 35% | h_pts <= 1.5714 ET m_ph <= 0.2048 ET x_dom >= 0.857 | 52/146 (35.6%, W 28.3%) | 41/117 (35.0%, W 27.0%) | 45/155 (29.0%, W 22.5%) | 13.6% | 11/51 (21.6%, W 12.5%) | confirmee sur C |
| 40% | m_ph <= 0.2048 ET s_fts >= 0.2 ET x_mn >= 1 | 38/92 (41.3%, W 31.8%) | 29/72 (40.3%, W 29.7%) | 30/117 (25.6%, W 18.6%) | 13.8% | 6/34 (17.6%, W 8.3%) | rejetee |

### Moins de 2,5 buts de l'extérieur  (`over_under_exterieur_2.5|moins`)
- Gagnants / perdants : A 4140/613  B 2908/397  C 3844/631  D 1071/162 ; 742 547 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.6483, log-loss 0.3909 contre 0.4074 (taux de base) ; boosting AUC 0.6568, meilleurs 5 % → 95.5% (taux de base 85.9%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p1n +0.61 (oui); m_pa -0.61 (oui); m_ph +0.57 (oui); m_pn2 -0.57 (oui); x_ext -0.41 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 90% | m_p1n >= 0.5957 ET s_pts >= -1 | 3348/3718 (90.0%, W 89.0%) | 2345/2587 (90.6%, W 89.5%) | 3092/3485 (88.7%, W 87.6%) | 76.0% | 839/932 (90.0%, W 87.9%) | rejetee |
| 95% | m_p1n >= 0.8048 ET p_e <= 0.4286 | 857/902 (95.0%, W 93.4%) | 623/649 (96.0%, W 94.2%) | 857/923 (92.8%, W 91.0%) | 84.1% | 226/232 (97.4%, W 94.5%) | rejetee |

### Multigoals 1-2  (`multigoals|1-2`)
- Gagnants / perdants : A 1966/2787  B 1325/1980  C 1729/2746  D 509/724 ; 743 672 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5663, log-loss 0.662 contre 0.6686 (taux de base) ; boosting AUC 0.5618, meilleurs 5 % → 48.4% (taux de base 38.6%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 -0.23 (oui); m_pn +0.23 (oui); m_pover25 -0.20 (oui); x_mx -0.16 (oui); s_tot -0.16 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 45% | m_p12 <= 0.7413 ET m_p1n >= 0.6395 | 873/1909 (45.7%, W 43.5%) | 653/1445 (45.2%, W 42.6%) | 634/1445 (43.9%, W 41.3%) | 36.1% | 183/390 (46.9%, W 42.0%) | confirmee sur C |
| 50% | h_ga <= 1.6 ET s_fts >= 0.5 | 162/319 (50.8%, W 45.3%) | 103/204 (50.5%, W 43.7%) | 100/227 (44.0%, W 37.8%) | 38.4% | 39/90 (43.3%, W 33.6%) | rejetee |
| 55% | h_def <= 0.5 ET h_gf <= 1.2857 ET s_fts >= 0.5 | 106/191 (55.5%, W 48.4%) | 66/117 (56.4%, W 47.4%) | 60/122 (49.2%, W 40.5%) | 38.3% | 31/65 (47.7%, W 36.0%) | confirmee sur C |
| 60% | a_cs >= 0.1429 ET m_p12 <= 0.7173 ET m_ph >= 0.4609 | 61/101 (60.4%, W 50.6%) | 38/61 (62.3%, W 49.8%) | 33/62 (53.2%, W 41.0%) | 38.4% | 5/11 (45.5%, W 21.3%) | prometteuse a confirmer |

### Multigoals 1-3  (`multigoals|1-3`)
- Gagnants / perdants : A 3028/1725  B 2128/1177  C 2751/1724  D 777/456 ; 743 099 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5503, log-loss 0.6646 contre 0.6676 (taux de base) ; boosting AUC 0.5444, meilleurs 5 % → 68.2% (taux de base 61.5%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 -0.20 (oui); m_pn +0.20 (oui); m_pover25 -0.18 (oui); s_tot -0.16 (oui); x_tot -0.16 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 70% | m_p12 <= 0.7173 ET p_o15 <= 0.8571 | 773/1092 (70.8%, W 68.0%) | 466/659 (70.7%, W 67.1%) | 396/590 (67.1%, W 63.2%) | 60.6% | 101/147 (68.7%, W 60.8%) | rejetee |
| 75% | h_o25 <= 0.8571 ET m_p12 <= 0.7173 ET s_pts >= 0.8571 | 246/323 (76.2%, W 71.2%) | 173/227 (76.2%, W 70.3%) | 149/235 (63.4%, W 57.1%) | 61.4% | 33/51 (64.7%, W 51.0%) | rejetee |
| 80% | a_def >= 0.6 ET h_cs >= 0.2857 ET m_p12 <= 0.7069 | 85/104 (81.7%, W 73.2%) | 64/79 (81.0%, W 71.0%) | 43/66 (65.1%, W 53.1%) | 61.4% | 8/13 (61.5%, W 35.5%) | rejetee |

### Multigoals 1-4  (`multigoals|1-4`)
- Gagnants / perdants : A 3767/986  B 2606/699  C 3466/1009  D 953/280 ; 743 392 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5461, log-loss 0.5325 contre 0.5347 (taux de base) ; boosting AUC 0.5281, meilleurs 5 % → 78.5% (taux de base 77.5%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 -0.12 (oui); m_pn +0.12 (oui); p_o25 -0.11 (oui); h_gf -0.10 (oui); s_tot -0.10 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 85% | p_o25 <= 0.25 ET x_mn >= 0.929 | 300/352 (85.2%, W 81.1%) | 131/154 (85.1%, W 78.6%) | 155/183 (84.7%, W 78.8%) | 77.1% | 60/77 (77.9%, W 67.5%) | confirmee sur C |
| 90% | m_p12 <= 0.7069 ET s_gf <= 0.8571 ET s_pts >= 0.8571 | 143/156 (91.7%, W 86.3%) | 98/108 (90.7%, W 83.8%) | 69/89 (77.5%, W 67.8%) | 77.5% | 13/20 (65.0%, W 43.3%) | rejetee |

### Multigoals 2-3  (`multigoals|2-3`)
- Gagnants / perdants : A 2174/2579  B 1570/1735  C 2047/2428  D 568/665 ; 742 117 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5179, log-loss 0.691 contre 0.6895 (taux de base) ; boosting AUC 0.5162, meilleurs 5 % → 42.1% (taux de base 45.7%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : h_gf -0.06 (oui); h_o25 -0.05 (oui); m_p12 -0.05 (oui); m_pn +0.05 (oui); m_ph -0.05 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 50% | s_gf <= 0.6333 ET s_nul >= 0.3571 | 504/995 (50.6%, W 47.5%) | 378/756 (50.0%, W 46.4%) | 481/1019 (47.2%, W 44.1%) | 45.3% | 134/276 (48.5%, W 42.7%) | rejetee |
| 55% | h_o25 <= 0.25 ET h_pts >= 0.5 ET p_o15 <= 0.6 | 164/293 (56.0%, W 50.2%) | 62/111 (55.9%, W 46.6%) | 74/150 (49.3%, W 41.4%) | 45.6% | 50/97 (51.5%, W 41.7%) | rejetee |
| 60% | p_btts <= 0.25 ET s_o15 <= 0.5 | 104/168 (61.9%, W 54.4%) | 39/65 (60.0%, W 47.9%) | 25/68 (36.8%, W 26.3%) | 45.9% | 18/42 (42.9%, W 29.1%) | rejetee |

### Multigoals 2-4  (`multigoals|2-4`)
- Gagnants / perdants : A 2913/1840  B 2048/1257  C 2762/1713  D 744/489 ; 744 438 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5239, log-loss 0.6668 contre 0.6655 (taux de base) ; boosting AUC 0.514, meilleurs 5 % → 65.0% (taux de base 61.7%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_pover25 +0.09 (oui); x_ext +0.06 (non); m_p12 +0.06 (oui); m_pn -0.06 (oui); a_nul +0.05 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 65% | m_pover25 >= 0.5027 ET x_ext >= 0.625 | 663/1009 (65.7%, W 62.7%) | 782/1202 (65.1%, W 62.3%) | 911/1426 (63.9%, W 61.4%) | 60.7% | 447/746 (59.9%, W 56.4%) | confirmee sur C |
| 70% | h_d2 >= 0.1667 ET m_pover25 >= 0.519 ET p_h <= 0.8571 | 161/230 (70.0%, W 63.8%) | 160/228 (70.2%, W 63.9%) | 178/270 (65.9%, W 60.1%) | 61.5% | 166/266 (62.4%, W 56.5%) | rejetee |
| 75% | h_d2 >= 0.1667 ET m_ph <= 0.3526 ET m_pover25 >= 0.519 | 81/104 (77.9%, W 69.0%) | 86/114 (75.4%, W 66.8%) | 87/121 (71.9%, W 63.3%) | 61.4% | 70/116 (60.3%, W 51.2%) | confirmee sur C |

### Multigoals 2-5  (`multigoals|2-5`)
- Gagnants / perdants : A 3278/1475  B 2325/980  C 3171/1304  D 874/359 ; 742 666 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5421, log-loss 0.6042 contre 0.6042 (taux de base) ; boosting AUC 0.5354, meilleurs 5 % → 76.7% (taux de base 70.9%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_pover25 +0.19 (oui); m_p12 +0.18 (oui); m_pn -0.18 (oui); s_tot +0.12 (non); x_tot +0.12 (non)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 75% | m_pover25 >= 0.5027 ET s_o15 >= 0.675 | 639/850 (75.2%, W 72.2%) | 790/1049 (75.3%, W 72.6%) | 905/1224 (73.9%, W 71.4%) | 69.7% | 461/661 (69.7%, W 66.1%) | confirmee sur C |
| 80% | h_pts <= 1.4286 ET m_p12 >= 0.7658 | 204/255 (80.0%, W 74.7%) | 137/165 (83.0%, W 76.6%) | 234/338 (69.2%, W 64.1%) | 71.0% | 83/119 (69.8%, W 61.0%) | rejetee |
| 85% | a_vic >= 0.1429 ET m_pover25 >= 0.5686 ET x_mn <= 1.071 | 82/95 (86.3%, W 78.0%) | 88/102 (86.3%, W 78.3%) | 123/151 (81.5%, W 74.5%) | 70.5% | 45/66 (68.2%, W 56.2%) | confirmee sur C |

### Multigoals 3-4  (`multigoals|3-4`)
- Gagnants / perdants : A 1801/2952  B 1281/2024  C 1737/2738  D 444/789 ; 740 551 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5354, log-loss 0.6683 contre 0.6681 (taux de base) ; boosting AUC 0.5206, meilleurs 5 % → 37.7% (taux de base 38.8%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 +0.15 (oui); m_pn -0.15 (oui); m_pover25 +0.14 (oui); x_mx +0.09 (oui); s_tot +0.09 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 45% | h_nul <= 0.2857 ET m_p12 >= 0.7658 | 242/532 (45.5%, W 41.3%) | 143/308 (46.4%, W 40.9%) | 242/564 (42.9%, W 38.9%) | 38.2% | 80/208 (38.5%, W 32.1%) | confirmee sur C |
| 50% | a_ga <= 2.25 ET m_p12 >= 0.8176 ET s_cs >= 0.0714 | 85/170 (50.0%, W 42.6%) | 63/126 (50.0%, W 41.4%) | 96/206 (46.6%, W 39.9%) | 38.4% | 26/66 (39.4%, W 28.5%) | confirmee sur C |
| 55% | m_pover25 >= 0.6393 ET p_o15 >= 0.6 ET s_btts <= 0.6429 | 41/74 (55.4%, W 44.1%) | 54/98 (55.1%, W 45.2%) | 86/180 (47.8%, W 40.6%) | 38.4% | 34/84 (40.5%, W 30.6%) | rejetee |

### Multigoals 3-5  (`multigoals|3-5`)
- Gagnants / perdants : A 2166/2587  B 1558/1747  C 2146/2329  D 574/659 ; 743 458 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5496, log-loss 0.6921 contre 0.6935 (taux de base) ; boosting AUC 0.5458, meilleurs 5 % → 53.4% (taux de base 48.0%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 +0.24 (oui); m_pn -0.24 (oui); m_pover25 +0.20 (oui); x_mx +0.15 (oui); s_tot +0.14 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 50% | a_cs >= 0 ET m_p12 >= 0.7251 | 1425/2840 (50.2%, W 48.3%) | 953/1890 (50.4%, W 48.2%) | 1611/3172 (50.8%, W 49.0%) | 41.1% | 444/923 (48.1%, W 44.9%) | confirmee sur C |
| 55% | a_cs >= 0 ET m_p12 >= 0.7658 | 524/949 (55.2%, W 52.0%) | 353/635 (55.6%, W 51.7%) | 625/1173 (53.3%, W 50.4%) | 46.1% | 160/327 (48.9%, W 43.6%) | confirmee sur C |
| 60% | h_sd >= 1.2454 ET m_p12 >= 0.7935 | 194/312 (62.2%, W 56.7%) | 128/212 (60.4%, W 53.7%) | 194/358 (54.2%, W 49.0%) | 47.4% | 48/102 (47.1%, W 37.7%) | rejetee |
| 65% | a_d2 <= 0.1667 ET m_p12 >= 0.7935 ET x_ext >= 0.714 | 107/164 (65.2%, W 57.7%) | 82/126 (65.1%, W 56.4%) | 119/217 (54.8%, W 48.2%) | 47.6% | 23/55 (41.8%, W 29.7%) | rejetee |
| 70% | a_gd >= -0.4286 ET a_sd >= 0.9897 ET m_p12 >= 0.8176 | 46/64 (71.9%, W 59.9%) | 42/60 (70.0%, W 57.5%) | 55/97 (56.7%, W 46.8%) | 47.8% | 12/22 (54.5%, W 34.7%) | rejetee |

### Multigoals 3-6  (`multigoals|3-6`)
- Gagnants / perdants : A 2346/2407  B 1670/1635  C 2351/2124  D 628/605 ; 743 979 configurations comparées.
- Signal global sur C (modèles appris sur A) : logistique AUC 0.5732, log-loss 0.6866 contre 0.6939 (taux de base) ; boosting AUC 0.5737, meilleurs 5 % → 60.1% (taux de base 52.5%).
- Caractéristiques qui distinguent gagnants et perdants (A+B, écart standardisé ; même signe sur C ?) : m_p12 +0.30 (oui); m_pn -0.30 (oui); m_pover25 +0.26 (oui); s_tot +0.19 (oui); x_mx +0.19 (oui)

| Niveau visé | Configuration | A | B | C | Sans la configuration (C) | D | Statut |
|---|---|---|---|---|---|---|---|
| 55% | m_p12 >= 0.7251 ET p_o25 >= 0.1429 | 1491/2669 (55.9%, W 54.0%) | 972/1767 (55.0%, W 52.7%) | 1673/2966 (56.4%, W 54.6%) | 44.9% | 465/864 (53.8%, W 50.5%) | confirmee sur C |
| 60% | m_p12 >= 0.7413 ET s_tot >= 2.7857 | 694/1150 (60.4%, W 57.5%) | 441/726 (60.7%, W 57.1%) | 861/1433 (60.1%, W 57.5%) | 49.0% | 245/430 (57.0%, W 52.3%) | confirmee sur C |
| 65% | h_ga >= 0.4286 ET m_p12 >= 0.7935 | 282/432 (65.3%, W 60.7%) | 181/276 (65.6%, W 59.8%) | 309/503 (61.4%, W 57.1%) | 51.4% | 75/140 (53.6%, W 45.3%) | rejetee |
| 70% | h_o25 >= 0.6 ET m_p12 >= 0.7935 ET s_cs <= 0.5 | 156/221 (70.6%, W 64.3%) | 90/128 (70.3%, W 61.9%) | 162/257 (63.0%, W 57.0%) | 51.9% | 47/83 (56.6%, W 45.9%) | rejetee |
| 75% | a_d2 <= 0.1667 ET m_p12 >= 0.7935 ET s_cs <= 0.3571 | 81/108 (75.0%, W 66.1%) | 55/73 (75.3%, W 64.4%) | 86/134 (64.2%, W 55.8%) | 52.2% | 20/42 (47.6%, W 33.4%) | rejetee |

## Limites
- Statuts rétrospectifs ; la seule validation est un gel prospectif avant match (non fait ici).
- La mention « prometteuse » = signal sans effectif suffisant sur C : à reprendre quand il y aura plus de données.
- Les probabilités implicites (1X2, plus/moins 2,5) viennent des cotes moyennes de clôture Football-Data sur A, B, C et des cotes BetPawa d'avant match sur D : même idée, deux marges différentes ; D est présenté à part.
- Archive BetPawa : 28 jours ; effectifs de jouables souvent < 100, intervalles de rendement larges.
- Plusieurs marchés ont des cotes sous 1,25 : un taux élevé n'y est pas jouable (jugé à part de la réussite).

## Reproduction
- `python -m alpha_serie.decouverte_marches --ecrire` (rejeu des données ≈ 15 s ; recherche + contrôle par permutation : plusieurs minutes).
- `python -m pytest tests/test_decouverte_marches.py -q`.
