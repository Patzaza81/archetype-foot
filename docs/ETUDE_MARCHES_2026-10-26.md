# Étude des marchés — audit et résultats reproductibles (2026-10-26)

**REMPLACÉE** par `docs/DECOUVERTE_MARCHES.md` (26/10/2026) : cette étude testait les pronostics existants avec une seule condition et mêlait la rentabilité au verdict ; elle ne reproduisait pas la méthode des victoires. Conservée pour mémoire.

Statut : ÉTUDE EN LECTURE SEULE. Aucun gel, aucune modification du moteur ni de la production. Rien n'est « validé ».

## Résultat en une ligne
- 29 marchés étudiés ; **0 sous observation, 29 non validés**. Sans aucun effet réel, on attendrait environ 0.73 faux positif.
- Les deux candidats (Moins de 3,5 « total ≤ 2,8 » et Double chance 12 « écart ≥ 0,6 ») sont **rejetés**.

## 1. Audit de l'étude précédente
- **Recouvrement de sources** : 205 des 452 matchs Football-Data postérieurs au 28/09 sont aussi dans l'archive BetPawa (205 avec le même score) : mes tableaux précédents les comptaient deux fois. Ici, Football-Data s'arrête au 27/09 (452 lignes écartées).
- **Choix après observation** : les deux candidats ont été retenus en lisant les taux de toute la période, contrôle compris. Ils ne sont pas des règles choisies sur le réglage : aucune preuve indépendante.
- **Comparaison de populations différentes** : « tous les paris » (Football-Data + archive) était comparé aux « jouables » (archive seule). Ici la comparaison est faite dans la même archive (section 4).
- **Fréquence par jour** fausse (division par une constante de 208) : remplacée par les jours calendaires de chaque jeu.
- **Recherche en masse de la PR #117** (~40 000 règles par marché, 7 gels) : sélection optimiste, mauvaise méthode ; la PR ne doit pas être fusionnée.
- **« Écart de niveau ≥ 0,6 » pour Double chance 12** : le moteur n'a aucune norme de niveau pour le « 12 » (`ecart_niveau` vide). J'ai utilisé l'écart attendu absolu |d| ; à confirmer.
- **Paramètres du moteur appris sur l'archive BetPawa** (`parametres.json`, 940 matchs du 28/09 au 24/10) : le jeu B est « en échantillon » pour le moteur. La preuve principale est donc V (Football-Data), pas B.
- **Second mode de choix de règle** ajouté après lecture d'un premier jeu de résultats sur V (le premier mode plaçait la règle au bord de la barre). Les deux modes sont reportés et les deux doivent passer.
- Contrôles passés : identifiants en double 0, même match en double dans une source 0, résultats manquants 0, cotes BetPawa prises après le coup d'envoi 0, cotes sans horodatage 0. Anti-fuite du moteur et choix de règle limité à R : testés (`tests/test_etude_marches.py`).

## 2. Méthode (identique pour chaque marché ; barres et variables propres à chaque marché)
- Jeux disjoints : R = Football-Data avant le 2026-04-01 (8058 matchs) ; V = Football-Data du 2026-04-01 au 27/09 (4475) ; B = archive BetPawa 28/09–25/10 (1233). Jamais mélangés.
- Population : les paris que le moteur propose réellement (même filtre que la production). Réglage uniquement sur R.
- Configurations annoncées à l'avance : la variable de niveau que le moteur lit pour ce marché (total attendu, buts attendus de l'équipe, écart attendu, plus petit attendu pour « les deux marquent ») et la valeur du moteur ; pas fixes de 0,2 (0,05 pour la valeur).
- Barre propre au marché = max(taux du marché sur R, taux d'équilibre du marché). Taux d'équilibre = 1 / cote BetPawa moyenne des paris proposés jouables (cote ≥ 1.25) de l'archive ; il n'utilise que des prix, jamais un résultat.
- Une règle doit avoir ≥ 200 matchs sur R, ≥ 150 sur V, borne basse de Wilson sur V ≥ barre, pas de baisse significative R→V ni V→B (test à 5 % unilatéral), ≥ 30 paris jouables dans l'archive et rendement net ≥ 0 sur ces paris.
- « Sous observation » est le maximum possible : seul un gel prospectif peut valider. Les deux modes de choix (couverture, Wilson maximal) doivent passer.

## 3. Résultats par marché (V = validation chronologique ; B jouables = archive, cote ≥ 1,25)
| Marché | Taux marché V | Barre | Mode | Règle choisie sur R | V : gagnés/matchs | Wilson bas V | B jouables | Rend. net B | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1x2 : 1 | 57.1% | 57.3% | couverture | d >= 0.8 | 316/501 (63.1%) | 58.8% | 156 | -13.9% | non validé |
| 1x2 : 1 | 57.1% | 57.3% | wilson_max | d >= 1.2 | 148/215 (68.8%) | 62.4% | 66 | -14.0% | non validé |
| 1x2 : 2 | 44.0% | 42.6% | couverture | aucune ne passe | - | - | - | - | non validé |
| 1x2 : 2 | 44.0% | 42.6% | wilson_max | aucune ne passe | - | - | - | - | non validé |
| btts : Non | 46.9% | 52.2% | couverture | aucune ne passe | - | - | - | - | non validé |
| btts : Non | 46.9% | 52.2% | wilson_max | aucune ne passe | - | - | - | - | non validé |
| btts : Oui | 63.4% | 66.0% | couverture | aucune ne passe | - | - | - | - | non validé |
| btts : Oui | 63.4% | 66.0% | wilson_max | aucune ne passe | - | - | - | - | non validé |
| double_chance : 12 | 73.7% | 76.8% | couverture | absd >= 1.4 | 104/127 (81.9%) | 74.3% | 13 | -21.3% | non validé |
| double_chance : 12 | 73.7% | 76.8% | wilson_max | absd >= 1.4 | 104/127 (81.9%) | 74.3% | 13 | -21.3% | non validé |
| double_chance : 1N | 73.9% | 75.2% | couverture | d >= 0.2 | 1851/2469 (75.0%) | 73.2% | 321 | -13.7% | non validé |
| double_chance : 1N | 73.9% | 75.2% | wilson_max | d >= 1.2 | 227/265 (85.7%) | 80.9% | 24 | -10.8% | non validé |
| double_chance : N2 | 67.8% | 67.8% | couverture | d <= -0.2 | 473/676 (70.0%) | 66.4% | 167 | -13.0% | non validé |
| double_chance : N2 | 67.8% | 67.8% | wilson_max | d <= -0.8 | 55/68 (80.9%) | 70.0% | 25 | -38.6% | non validé |
| handicap_-1.5 : exterieur | 80.3% | 80.0% | couverture | d <= 0.8 | 2847/3456 (82.4%) | 81.1% | 259 | -5.2% | non validé |
| handicap_-1.5 : exterieur | 80.3% | 80.0% | wilson_max | d <= -0.8 | 63/70 (90.0%) | 80.8% | 1 | -100.0% | non validé |
| handicap_1.5 : domicile | 87.3% | 87.3% | couverture | d >= -0.4 | 3556/4022 (88.4%) | 87.4% | 87 | +8.8% | sous observation |
| handicap_1.5 : domicile | 87.3% | 87.3% | wilson_max | d >= 1.2 | 255/265 (96.2%) | 93.2% | 0 | - | non validé |
| multigoals : 1-2 | 44.5% | - | couverture | aucune ne passe | - | - | - | - | non validé |
| multigoals : 1-2 | 44.5% | - | wilson_max | aucune ne passe | - | - | - | - | non validé |
| multigoals : 1-3 | 62.8% | 65.7% | couverture | total <= 2.4 | 587/893 (65.7%) | 62.6% | 0 | - | non validé |
| multigoals : 1-3 | 62.8% | 65.7% | wilson_max | total <= 1.8 | 79/121 (65.3%) | 56.5% | 0 | - | non validé |
| multigoals : 1-4 | 78.0% | 79.4% | couverture | total <= 2.4 | 827/1035 (79.9%) | 77.3% | 0 | - | non validé |
| multigoals : 1-4 | 78.0% | 79.4% | wilson_max | total <= 2.4 | 827/1035 (79.9%) | 77.3% | 0 | - | non validé |
| multigoals : 2-3 | 44.0% | - | couverture | aucune ne passe | - | - | - | - | non validé |
| multigoals : 2-3 | 44.0% | - | wilson_max | aucune ne passe | - | - | - | - | non validé |
| multigoals : 2-4 | 61.1% | - | couverture | aucune ne passe | - | - | - | - | non validé |
| multigoals : 2-4 | 61.1% | - | wilson_max | aucune ne passe | - | - | - | - | non validé |
| multigoals : 2-5 | 70.4% | 70.2% | couverture | total >= 2.8 | 1160/1670 (69.5%) | 67.2% | 0 | - | non validé |
| multigoals : 2-5 | 70.4% | 70.2% | wilson_max | total >= 2.8 | 1160/1670 (69.5%) | 67.2% | 0 | - | non validé |
| multigoals : 3-4 | 38.7% | - | couverture | aucune ne passe | - | - | - | - | non validé |
| multigoals : 3-4 | 38.7% | - | wilson_max | aucune ne passe | - | - | - | - | non validé |
| multigoals : 3-5 | 46.8% | 49.0% | couverture | total >= 3.2 | 174/369 (47.1%) | 42.1% | 0 | - | non validé |
| multigoals : 3-5 | 46.8% | 49.0% | wilson_max | total >= 3.2 | 174/369 (47.1%) | 42.1% | 0 | - | non validé |
| multigoals : 3-6 | 56.2% | 53.7% | couverture | total >= 3.2 | 322/541 (59.5%) | 55.3% | 0 | - | non validé |
| multigoals : 3-6 | 56.2% | 53.7% | wilson_max | total >= 3.6 | 120/192 (62.5%) | 55.5% | 0 | - | non validé |
| over_under_1.5 : plus | 79.2% | 78.0% | couverture | total >= 2.8 | 1560/1936 (80.6%) | 78.8% | 105 | +0.1% | non validé |
| over_under_1.5 : plus | 79.2% | 78.0% | wilson_max | total >= 3.8 | 126/154 (81.8%) | 75.0% | 3 | -15.0% | non validé |
| over_under_2.5 : moins | 52.2% | 55.7% | couverture | aucune ne passe | - | - | - | - | non validé |
| over_under_2.5 : moins | 52.2% | 55.7% | wilson_max | aucune ne passe | - | - | - | - | non validé |
| over_under_2.5 : plus | 64.8% | 66.4% | couverture | aucune ne passe | - | - | - | - | non validé |
| over_under_2.5 : plus | 64.8% | 66.4% | wilson_max | aucune ne passe | - | - | - | - | non validé |
| over_under_3.5 : moins | 70.0% | 73.2% | couverture | valeur >= 0.65 | 1722/2440 (70.6%) | 68.7% | 317 | -6.6% | non validé |
| over_under_3.5 : moins | 70.0% | 73.2% | wilson_max | total <= 1.8 | 115/151 (76.2%) | 68.8% | 22 | -17.0% | non validé |
| over_under_4.5 : moins | 84.5% | 86.8% | couverture | total <= 3.2 | 2968/3447 (86.1%) | 84.9% | 60 | -7.6% | non validé |
| over_under_4.5 : moins | 84.5% | 86.8% | wilson_max | total <= 1.8 | 132/151 (87.4%) | 81.2% | 0 | - | non validé |
| over_under_domicile_0.5 : plus | 82.8% | 82.9% | couverture | dom >= 1.8 | 941/1071 (87.9%) | 85.8% | 18 | -13.8% | non validé |
| over_under_domicile_0.5 : plus | 82.8% | 82.9% | wilson_max | dom >= 2.2 | 317/350 (90.6%) | 87.1% | 0 | - | non validé |
| over_under_domicile_1.5 : moins | 61.4% | 64.0% | couverture | dom <= 1.2 | 488/739 (66.0%) | 62.5% | 131 | -11.4% | non validé |
| over_under_domicile_1.5 : moins | 61.4% | 64.0% | wilson_max | dom <= 1.0 | 290/416 (69.7%) | 65.1% | 75 | -13.5% | non validé |
| over_under_domicile_2.5 : moins | 80.9% | 82.0% | couverture | dom <= 1.8 | 2733/3302 (82.8%) | 81.4% | 110 | -6.2% | non validé |
| over_under_domicile_2.5 : moins | 80.9% | 82.0% | wilson_max | dom <= 1.0 | 393/440 (89.3%) | 86.1% | 3 | -56.0% | non validé |
| over_under_exterieur_0.5 : plus | 78.6% | 77.1% | couverture | ext >= 1.6 | 473/604 (78.3%) | 74.9% | 30 | -24.6% | non validé |
| over_under_exterieur_0.5 : plus | 78.6% | 77.1% | wilson_max | ext >= 2.0 | 102/124 (82.3%) | 74.6% | 5 | -21.4% | non validé |
| over_under_exterieur_1.5 : moins | 66.9% | 71.2% | couverture | ext <= 1.2 | 1329/1944 (68.4%) | 66.3% | 240 | -10.5% | non validé |
| over_under_exterieur_1.5 : moins | 66.9% | 71.2% | wilson_max | ext <= 0.6 | 87/119 (73.1%) | 64.5% | 16 | -6.4% | non validé |
| over_under_exterieur_2.5 : moins | 86.2% | 87.7% | couverture | ext <= 1.6 | 3357/3849 (87.2%) | 86.1% | 35 | +7.4% | non validé |
| over_under_exterieur_2.5 : moins | 86.2% | 87.7% | wilson_max | ext <= 0.6 | 106/119 (89.1%) | 82.2% | 0 | - | non validé |

Marchés non étudiés (moins de 200 paris proposés sur R) : handicap_-1.5 : domicile, handicap_1.5 : exterieur, over_under_1.5 : moins, over_under_3.5 : plus, over_under_domicile_0.5 : moins, over_under_domicile_1.5 : plus, over_under_domicile_2.5 : plus, over_under_exterieur_0.5 : moins, over_under_exterieur_1.5 : plus.

## 4. Le filtre « cote ≥ 1,25 » fait-il baisser la réussite ? (même archive, mêmes matchs)
| Marché | Tous les paris proposés | Paris jouables | Part jouable |
|---|---|---|---|
| 1x2 : 1 | 50.0% (296) | 46.5% (273) | 92.9% |
| 1x2 : 2 | 49.6% (115) | 47.8% (111) | 97.4% |
| btts : Non | 49.1% (318) | 48.9% (317) | 100.0% |
| btts : Oui | 57.6% (144) | 57.5% (141) | 97.9% |
| double_chance : 12 | 74.5% (1077) | 73.1% (773) | 72.9% |
| double_chance : 1N | 74.0% (764) | 61.0% (423) | 56.6% |
| double_chance : N2 | 67.7% (359) | 60.5% (263) | 73.7% |
| handicap_-1.5 : exterieur | 79.5% (1075) | 65.9% (349) | 40.9% |
| handicap_1.5 : domicile | 87.7% (1188) | 72.4% (156) | 24.8% |
| over_under_1.5 : plus | 78.2% (800) | 76.4% (191) | 24.6% |
| over_under_2.5 : moins | 53.9% (291) | 54.0% (289) | 100.0% |
| over_under_2.5 : plus | 65.2% (141) | 63.6% (132) | 95.7% |
| over_under_3.5 : moins | 68.2% (859) | 65.1% (645) | 77.1% |
| over_under_4.5 : moins | 83.1% (1147) | 71.6% (134) | 12.2% |
| over_under_domicile_0.5 : plus | 83.6% (639) | 76.5% (81) | 20.7% |
| over_under_domicile_1.5 : moins | 58.7% (445) | 54.3% (256) | 89.2% |
| over_under_domicile_2.5 : moins | 79.9% (1075) | 69.8% (182) | 27.0% |
| over_under_exterieur_0.5 : plus | 77.5% (360) | 56.5% (62) | 29.2% |
| over_under_exterieur_1.5 : moins | 67.1% (726) | 61.0% (356) | 73.6% |
| over_under_exterieur_2.5 : moins | 87.3% (1169) | 77.4% (84) | 12.6% |

## 5. Les deux candidats, traités par les mêmes fonctions que les autres règles
### double_chance : 12 — absd >= 0.6 → **non valide**
- R : 1828/2411 (75.8%), Wilson bas 74.1%, 6.07/jour
- V : 1061/1376 (77.1%), Wilson [74.8% ; 79.2%], 7.64/jour ; tous les paris du marché sur V : 73.7%
- B : 333/454 (73.4%) ; jouables 254 (70.5%), gains 52.5, pertes 75.0, net -22.5, rendement -8.9%, IC95 [-0.1613, -0.0158]
- Raisons : borne basse de Wilson sur V (74.8%) sous la barre du marché (76.8%) ; taux des paris jouables (70.5%) sous leur propre taux d'équilibre (77.2%) : rendement net -8.9%, IC95 [-16.1% ; -1.6%] ; règle imposée après observation des résultats (non choisie sur R) : aucune preuve indépendante
- Hausse de réussite démontrée sur V (borne basse de Wilson 74.8% contre 73.7% pour tous les paris du marché) : oui. Rejet principal : rendement net négatif aux cotes jouables.

### over_under_3.5 : moins — total <= 2.8 → **non valide**
- R : 3404/4556 (74.7%), Wilson bas 73.4%, 11.48/jour
- V : 1631/2270 (71.9%), Wilson [70.0% ; 73.7%], 12.61/jour ; tous les paris du marché sur V : 70.0%
- B : 418/593 (70.5%) ; jouables 398 (67.3%), gains 103.7, pertes 130.0, net -26.3, rendement -6.6%, IC95 [-0.1308, -0.0014]
- Raisons : borne basse de Wilson sur V (70.0%) sous la barre du marché (70.3%) ; baisse significative de R à V ; taux des paris jouables (67.3%) sous leur propre taux d'équilibre (72.0%) : rendement net -6.6%, IC95 [-13.1% ; -0.1%] ; règle imposée après observation des résultats (non choisie sur R) : aucune preuve indépendante
- Hausse de réussite démontrée sur V (borne basse de Wilson 70.0% contre 70.0% pour tous les paris du marché) : non. Rejet principal : rendement net négatif aux cotes jouables.

## 6. Bandes de cotes (exploratoire, comme dans l'étude des victoires)
- 76 cellules marché × bande × jeu avec ≥ 30 paris ; 16 ont un rendement positif ; **0 ont une borne basse d'intervalle de confiance au-dessus de 0**. Aucune règle n'en est tirée.
- Détail par bande et par période dans le fichier de résultats (`bandes_de_cotes`). Cotes de B = BetPawa d'avant match ; cotes de R et V = moyennes de clôture Football-Data (1X2 et plus/moins 2,5 seulement), jamais mélangées.

## 7. Limites
- Rétrospectif : aucune de ces règles n'est validée. Le seul test indépendant est le gel avant match, sur plusieurs semaines.
- Archive BetPawa : 28 jours, effectifs de jouables souvent < 100 ; intervalles de rendement larges.
- Multigoals : pas de cote BetPawa dans l'archive, donc jouabilité et rendement non évaluables.
- Football-Data et archive couvrent des championnats différents : les taux de V et de B ne sont pas directement comparables ; ils sont présentés séparément.

## 8. Reproduction
- `python -m alpha_serie.etude_marches --ecrire` régénère `data/etudes/marches_2026-10-26.json` et ce rapport (≈ 30 s).
- `python -m pytest tests/test_etude_marches.py -q` vérifie les calculs, la séparation des jeux, l'absence de fuite et la non-intégration à la production.
