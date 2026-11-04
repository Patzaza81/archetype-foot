# Classement descriptif des 38 profils

Regles inventaire `1.0.1`. Trois dimensions SEPAREES; aucun score global; aucun statut n'est une recommandation de marche.

**Ce classement decrit la disponibilite et la coherence des donnees. Ce n'est PAS un classement de performance predictive.**

## Avertissement completude

La completude reelle d'une saison (nombre d'equipes et de matchs attendus) n'est verifiee que si une verification externe est enregistree dans `verifications_completude.json`. Sinon: `COMPLETUDE_NON_VERIFIEE`. Une structure aller-retour complete dans l'archive est coherente mais ne prouve pas qu'aucune equipe n'a ete oubliee.

- Saisons verifiees: 181 sur 190 (E0:2122, E0:2223, E0:2324, E0:2425, E0:2526, E1:2122, E1:2223, E1:2324, E1:2425, E1:2526, E2:2122, E2:2223, E2:2324, E2:2425, E2:2526, E3:2122, E3:2223, E3:2324, E3:2425, E3:2526, EC:2122, EC:2223, EC:2324, EC:2425, EC:2526, SC0:2122, SC0:2223, SC0:2324, SC0:2425, SC0:2526, SC1:2122, SC1:2223, SC1:2324, SC1:2425, SC1:2526, SC2:2122, SC2:2223, SC2:2324, SC2:2425, SC2:2526, SC3:2122, SC3:2223, SC3:2324, SC3:2425, SC3:2526, D1:2122, D1:2223, D1:2324, D1:2425, D1:2526, D2:2122, D2:2223, D2:2324, D2:2425, D2:2526, I1:2122, I1:2223, I1:2324, I1:2425, I1:2526, I2:2122, I2:2223, I2:2324, I2:2425, I2:2526, SP1:2122, SP1:2223, SP1:2324, SP1:2425, SP1:2526, SP2:2122, SP2:2223, SP2:2324, SP2:2425, SP2:2526, F1:2122, F1:2223, F1:2324, F1:2425, F1:2526, F2:2122, F2:2223, F2:2324, F2:2425, F2:2526, N1:2122, N1:2223, N1:2324, N1:2425, N1:2526, B1:2122, B1:2223, B1:2324, P1:2122, P1:2223, P1:2324, P1:2425, P1:2526, T1:2122, T1:2223, T1:2324, T1:2425, T1:2526, G1:2122, G1:2223, G1:2324, G1:2526, ARG:2122, ARG:2324, ARG:2425, ARG:2526, AUT:2122, AUT:2223, AUT:2324, AUT:2425, AUT:2526, BRA:2122, BRA:2223, BRA:2324, BRA:2425, BRA:2526, CHN:2122, CHN:2223, CHN:2324, CHN:2425, CHN:2526, DNK:2122, DNK:2223, DNK:2324, DNK:2425, DNK:2526, FIN:2122, FIN:2223, FIN:2324, FIN:2425, FIN:2526, IRL:2122, IRL:2223, IRL:2324, IRL:2425, IRL:2526, JPN:2122, JPN:2223, JPN:2324, JPN:2425, JPN:2526, MEX:2122, MEX:2223, MEX:2324, MEX:2425, NOR:2122, NOR:2223, NOR:2425, NOR:2526, POL:2122, POL:2324, POL:2425, POL:2526, ROU:2122, ROU:2223, ROU:2324, ROU:2425, RUS:2122, RUS:2223, RUS:2324, RUS:2425, RUS:2526, SWE:2122, SWE:2223, SWE:2324, SWE:2425, SWE:2526, SWZ:2223, SWZ:2324, SWZ:2425, SWZ:2526, USA:2122, USA:2223, USA:2324, USA:2425, USA:2526)
- **Competitions comparables sans reserve: 30 sur 38**

## Completude de l'archive (dimension distincte de la completude de la competition)

Un match documente absent des fichiers n'est jamais ajoute a l'archive ni compte. `MATCH_ARCHIVE_MANQUANT` = rencontre disputee documentee et absente; `PHASE_EXCLUE_NON_DETAILLEE` = phase exclue sans rencontres individualisees; `SCORE_ATTRIBUE_DIVERGENT` = rencontre presente dans l'archive avec le score joue, le resultat officiel etant un score attribue different (pas une rencontre absente); `MATCH_ATTRIBUE_NON_JOUE` = match attribue sans rencontre disputee. `ARCHIVE_COMPLETE_PERIMETRE_PARTIEL` = aucun match documente manquant dans le perimetre examine, mais ce perimetre n'inclut pas tout (voir `perimetre_examen`); `ARCHIVE_COMPLETE_PERIMETRE_ETENDU` = saison reguliere (paires verifiees) + phases finales examinees individuellement + matchs additionnels. `ARCHIVE_NON_EXAMINEE` = rien n'est affirme.

- ARCHIVE_COMPLETE_PERIMETRE_ETENDU: 33 saisons (dont verifiees: 33)
- ARCHIVE_COMPLETE_PERIMETRE_PARTIEL: 99 saisons (dont verifiees: 99)
- MATCH_ARCHIVE_MANQUANT: 23 saisons (dont verifiees: 23)
- PHASE_EXCLUE_NON_DETAILLEE: 17 saisons (dont verifiees: 17)
- SCORE_ATTRIBUE_DIVERGENT: 2 saisons (dont verifiees: 2)
- MATCH_ATTRIBUE_NON_JOUE: 7 saisons (dont verifiees: 7)
- ARCHIVE_NON_EXAMINEE: 9 saisons (dont verifiees: 0)
- **Competitions comparables sans reserve sur l'archive (5 saisons verifiees ET perimetre etendu): 3 sur 38**

- AUT:2425 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_et_dates; perimetre: implique_un_club_de_la_ligue): Barrage Conference League (demi-finale 29/05/2025, finale 01/06/2025) absent de l'archive.
- AUT:2526 MATCH_ARCHIVE_MANQUANT (3 match(s) disputes; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Barrage Conference League: Ried 2-1 Wolfsberger (19/05/2026), Ried 2-1 Rapid (22/05), Rapid 3-0 Ried (25/05) (RSSSF), absents de l'archive.
- B1:2122 MATCH_ARCHIVE_MANQUANT (14 match(s) disputes; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue): Play-offs de la saison (14 matchs) non presents dans l'archive.
- B1:2223 MATCH_ARCHIVE_MANQUANT (24 match(s) disputes; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue): Play-offs de la saison (24 matchs) non presents dans l'archive.
- B1:2324 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Standard-Westerlo attribue 0-5 (non joue: Standard n'a pas pris le coup d'envoi), absent de l'archive; ce n'est pas un match joue. (qualification corrigee: match attribue, aucune rencontre disputee absente)
- B1:2324 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_et_equipes; perimetre: hors_clubs_de_la_ligue): Deux matchs de barrage de promotion/relegation contre Lommel, absents de l'archive.
- CHN:2223 MATCH_ATTRIBUE_NON_JOUE (8 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Wikipedia (2022 CSL) marque des matchs 'attribues' 3-0. Huit sont presents dans l'archive avec le score 3-0 attribue: Beijing Guoan 0-3 Shanghai Port (27/12), Cangzhou 3-0 Hebei (27/12), Guangzhou City 0-3 Dalian Pro (28/06), Henan 3-0 Shenzhen (23/12), Shandong 3-0 Beijing Guoan (31/12), Shandong 3-0 Meizhou Hakka (27/12), Tianjin 0-3 Dalian Pro (27/12), Wuhan Three Towns 3-0 Tianjin (31/12). Le neuvieme cite par la page, Dalian Pro 0-3 Guangzhou City, ne correspond pas a l'archive (Dalian Pro 2-0 Guangzhou City le 08/06/2022): ecart non resolu (lecture de la page a verifier). Les dates ne sont pas donnees par la page; la raison de chaque attribution n'est pas precisee.
- D1:2122 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Bochum-M'gladbach (18/03/2022): match interrompu, victoire 2-0 attribuee a M'gladbach par le tribunal sportif de la DFB (reference citee par Wikipedia, 24/03/2022). Present dans l'archive avec le score 0-2 (score attribue, pas le score au moment de l'interruption, que la source ne donne pas).
- D1:2425 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Union Berlin-Bochum (14/12/2024): match interrompu, donne a Bochum par la DFB (titre de la reference DFB.de du 09/01/2025 cite par Wikipedia; le score attribue n'est pas ecrit dans la page). Present dans l'archive avec le score 0-2, identique au tableau de resultats de Wikipedia.
- DNK:2425 MATCH_ARCHIVE_MANQUANT (1 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrage europeen Randers-Silkeborg (selon la page Wikipedia), absent de l'archive.
- DNK:2526 MATCH_ARCHIVE_MANQUANT (1 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrage europeen Brondby-Copenhague du 21/05/2026, absent de l'archive.
- F1:2526 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Nantes-Toulouse (17/05/2026): match interrompu apres invasion de terrain, score 0-0 enterine par la ligue (Le Parisien et BBC cites par Wikipedia). Present dans l'archive avec 0-0; resultat enterine, pas un match termine.
- F2:2526 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Bastia-Red Star (05/12/2025): interrompu a la 57e minute a 0-0 (fumigene), perdu par forfait par Bastia (Wikipedia). Ligne presente dans l'archive SANS score (ni FTHG ni FTAG); le tableau Wikipedia affiche 0-3 sans l'identifier comme score de forfait; buts non comptes au classement par la source. Un second match interrompu (0-2, fumigenes de supporters de Bastia) dont le score a ete confirme par la LFP n'est pas identifie dans la page (adversaire et date non indiques).
- FIN:2223 MATCH_ARCHIVE_MANQUANT (1 match(s) disputes; preuve: match_par_match; perimetre: hors_clubs_de_la_ligue): Jaro-EIF 2-1 le 12/10/2022 (premier tour du parcours de barrage de Ykkonen, RSSSF), absent de l'archive.
- FIN:2324 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Barrage de relegation Mariehamn-Gnistan: 0-0 le 25/10/2023 et 3-0 le 29/10/2023 (RSSSF), absents de l'archive.
- FIN:2526 MATCH_ARCHIVE_MANQUANT (nombre non documente; preuve: equipes_sans_nombre; perimetre: implique_un_club_de_la_ligue): Barrage de relegation KTP-TPS absent de l'archive; nombre de matchs non documente dans la verification.
- G1:2122 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrage de relegation Lamia-Veria (2 manches), absent de l'archive.
- I1:2223 MATCH_ARCHIVE_MANQUANT (1 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Match de depart Spezia-Hellas Verona (egalite a 31 points, 17e/18e): Verona 3-1, terrain neutre, date non indiquee par la source; absent de l'archive (aucune des deux equipes n'a plus de 38 matchs). Source: Wikipedia 2022-23 Serie A.
- I2:2425 MATCH_ARCHIVE_MANQUANT (1 match(s) disputes; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Play-out Sampdoria-Salernitana, match aller du 15/06/2025: 2-0 (Wikipedia 2024-25 Serie B), joue, absent de l'archive (table de saison reguliere seulement).
- I2:2425 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Play-out, match retour du 22/06/2025 a Salerne suspendu a la 74e minute (Sampdoria menait 2-0 sur le terrain), victoire 3-0 attribuee a la Sampdoria par la Lega B (Wikipedia); absent de l'archive; ce n'est pas un match joue en entier.
- IRL:2122 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Sligo Rovers-Waterford (15/05/2021): Waterford a declare forfait (cas de COVID-19), victoire 3-0 attribuee a Sligo (Wikipedia, '3-0*'). Present dans l'archive avec 3-0.
- IRL:2223 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: hors_clubs_de_la_ligue): Matchs de First Division du parcours de barrage absents de l'archive; seule la finale UC Dublin-Waterford y figure.
- IRL:2324 MATCH_ARCHIVE_MANQUANT (nombre non documente; preuve: equipes_sans_nombre; perimetre: hors_clubs_de_la_ligue): Matchs de First Division du parcours de barrage (Waterford-Athlone, Cobh-Wexford, Waterford-Cobh le 04/11/2023...) absents de l'archive; seule la finale y figure.
- IRL:2425 MATCH_ARCHIVE_MANQUANT (nombre non documente; preuve: equipes_sans_nombre; perimetre: hors_clubs_de_la_ligue): Matchs de First Division du parcours de barrage (demi-finales, finale Bray-Athlone) absents de l'archive; seule la finale Bray-Drogheda y figure.
- IRL:2526 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: hors_clubs_de_la_ligue): Barrages (hors ligue) exclus: matchs non documentes individuellement, absents de l'archive.
- JPN:2122 SCORE_ATTRIBUE_DIVERGENT (1 score divergent; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Urawa-Shonan (20/06/2021): rencontre PRESENTE dans l'archive avec le score joue Urawa 2-3 Shonan; la JPFL a attribue 3-0 a Shonan (joueur non qualifie, Wikipedia 2021 J1 League). Score officiel different du score archive; rien n'est absent, rien n'est modifie.
- MEX:2122 MATCH_ATTRIBUE_NON_JOUE (1 attribue(s); preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Queretaro-Atlas (05/03/2022, Clausura): arrete a la 60e minute (Queretaro 0-1, bagarre), victoire 0-3 attribuee a Atlas (Wikipedia). Present dans l'archive avec 0-3 (score attribue, pas le score au moment de l'arret).
- NOR:2526 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrage de relegation Bryne (14e)-Aalesund, 4-1 cumule pour Aalesund: 2 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)
- ROU:2425 MATCH_ARCHIVE_MANQUANT (4 match(s) disputes; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue): Quatre matchs de barrage Liga I/Liga II absents de l'archive.
- RUS:2223 SCORE_ATTRIBUE_DIVERGENT (1 score divergent; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue): Pari NN-Torpedo Moscou (19/03/2023): rencontre PRESENTE dans l'archive avec le score joue 1-1; l'Union russe a attribue 3-0 a Torpedo (joueur non eligible, decision du 22/03/2023; Wikipedia 2022-23 RPL). Score officiel different du score archive; rien n'est absent, rien n'est modifie.
- RUS:2425 MATCH_ARCHIVE_MANQUANT (4 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrages de relegation (deux matchs aller-retour chacun): Akhmat-Ural (3-2 cumule) et Pari NN-Sochi (3-4 cumule): 4 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)
- RUS:2526 MATCH_ARCHIVE_MANQUANT (4 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrages de relegation: Dynamo Makhachkala-Ural (3-0 cumule) et Akron-Rotor (2-1 cumule), 23/05/2026: 4 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)
- SC1:2122 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC1:2223 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC1:2324 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC1:2425 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC1:2526 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC2:2122 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC2:2223 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC2:2324 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC2:2425 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC2:2526 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC3:2122 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC3:2223 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC3:2324 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC3:2425 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SC3:2526 PHASE_EXCLUE_NON_DETAILLEE (nombre non documente; preuve: existence_seulement; perimetre: non_documente): Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).
- SWE:2324 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrage de relegation Brommapojkarna-Utsiktens, 7-0 cumule (Allsvenskan 14e contre 3e de Superettan 2023): 2 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)
- SWE:2526 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue): Barrage de relegation, 14e d'Allsvenskan (IFK Norrkoping d'apres le classement de la page) contre Orgryte IS, 3-0 cumule pour Orgryte: 2 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)
- SWZ:2425 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue): Barrage de relegation (2 manches) absent de l'archive.
- SWZ:2526 MATCH_ARCHIVE_MANQUANT (2 match(s) disputes; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue): Barrage de relegation (2 manches) absent de l'archive.


## Volume (tri: matchs avec score decroissant)

| Code | Matchs avec score | Saisons | Matchs/saison (min-max) |
|---|---|---|---|
| E1 | 2760 | 5 | 552-552 |
| E2 | 2760 | 5 | 552-552 |
| E3 | 2760 | 5 | 552-552 |
| ARG | 2755 | 5 | 501-582 |
| EC | 2714 | 5 | 506-552 |
| USA | 2544 | 5 | 472-540 |
| SP2 | 2310 | 5 | 462-462 |
| E0 | 1900 | 5 | 380-380 |
| I1 | 1900 | 5 | 380-380 |
| I2 | 1900 | 5 | 380-380 |
| SP1 | 1900 | 5 | 380-380 |
| BRA | 1900 | 5 | 380-380 |
| JPN | 1756 | 5 | 306-380 |
| F2 | 1751 | 5 | 305-380 |
| T1 | 1750 | 5 | 306-380 |
| MEX | 1700 | 5 | 336-342 |
| F1 | 1678 | 5 | 306-380 |
| ROU | 1598 | 5 | 315-321 |
| B1 | 1547 | 5 | 306-312 |
| D1 | 1530 | 5 | 306-306 |
| D2 | 1530 | 5 | 306-306 |
| N1 | 1530 | 5 | 306-306 |
| P1 | 1530 | 5 | 306-306 |
| POL | 1530 | 5 | 306-306 |
| RUS | 1212 | 5 | 240-244 |
| NOR | 1207 | 5 | 240-242 |
| CHN | 1206 | 5 | 180-306 |
| SWE | 1206 | 5 | 240-242 |
| G1 | 1189 | 5 | 233-240 |
| SC0 | 1140 | 5 | 228-228 |
| SWZ | 1049 | 5 | 181-230 |
| AUT | 969 | 5 | 192-195 |
| DNK | 963 | 5 | 192-193 |
| IRL | 909 | 5 | 180-186 |
| SC1 | 900 | 5 | 180-180 |
| SC2 | 900 | 5 | 180-180 |
| SC3 | 900 | 5 | 180-180 |
| FIN | 847 | 5 | 164-177 |

## Couverture (signature par capacite; tri: nb de capacites confirmees decroissant, puis signature)

Ordre des lettres: resultat_final, mi_temps, tirs, tirs_cadres, corners, fautes, cartons_jaunes, cartons_rouges, cotes_calibration. C = confirmee, L = limitee, X = inexploitable.

| Code | Signature | Capacites C | Taux minimum observe (hors X) |
|---|---|---|---|
| D2 | CCCCCCCCC | 9 | 1.0000 |
| E3 | CCCCCCCCC | 9 | 1.0000 |
| F1 | CCCCCCCCC | 9 | 1.0000 |
| I1 | CCCCCCCCC | 9 | 1.0000 |
| I2 | CCCCCCCCC | 9 | 1.0000 |
| N1 | CCCCCCCCC | 9 | 1.0000 |
| P1 | CCCCCCCCC | 9 | 1.0000 |
| SC0 | CCCCCCCCC | 9 | 1.0000 |
| SP1 | CCCCCCCCC | 9 | 1.0000 |
| E0 | CCCCCCCCL | 8 | 1.0000 |
| E1 | CCCCCCCCL | 8 | 1.0000 |
| E2 | CCCCCCCCL | 8 | 1.0000 |
| SC1 | CCCCCCCCL | 8 | 1.0000 |
| SP2 | CCCCCCCCL | 8 | 1.0000 |
| SC3 | CCCCLCCCC | 8 | 0.9944 |
| SC2 | CCLCLCCLL | 5 | 0.9944 |
| EC | CCXCXCCXX | 5 | 1.0000 |
| B1 | LLLCLLCLL | 2 | 0.9902 |
| D1 | LLLCLLCLL | 2 | 0.9967 |
| F2 | LLLCLLCLL | 2 | 0.9974 |
| G1 | LLLCLLCLL | 2 | 0.9958 |
| ARG | XXXCXXCXX | 2 | 1.0000 |
| AUT | XXXCXXCXX | 2 | 1.0000 |
| BRA | XXXCXXCXX | 2 | 1.0000 |
| DNK | XXXCXXCXX | 2 | 1.0000 |
| FIN | XXXCXXCXX | 2 | 1.0000 |
| IRL | XXXCXXCXX | 2 | 1.0000 |
| JPN | XXXCXXCXX | 2 | 1.0000 |
| MEX | XXXCXXCXX | 2 | 1.0000 |
| NOR | XXXCXXCXX | 2 | 1.0000 |
| POL | XXXCXXCXX | 2 | 1.0000 |
| ROU | XXXCXXCXX | 2 | 1.0000 |
| SWE | XXXCXXCXX | 2 | 1.0000 |
| SWZ | XXXCXXCXX | 2 | 1.0000 |
| USA | XXXCXXCXX | 2 | 1.0000 |
| T1 | LLLLLLCLL | 1 | 0.9035 |
| CHN | XXXLXXCXX | 1 | 0.0000 |
| RUS | XXXLXXCXX | 1 | 0.4333 |

## Familles (memes statuts de capacite; regroupement exact, sans seuil)

- `XXXCXXCXX` : ARG, AUT, BRA, DNK, FIN, IRL, JPN, MEX, NOR, POL, ROU, SWE, SWZ, USA
- `CCCCCCCCC` : D2, E3, F1, I1, I2, N1, P1, SC0, SP1
- `CCCCCCCCL` : E0, E1, E2, SC1, SP2
- `LLLCLLCLL` : B1, D1, F2, G1
- `XXXLXXCXX` : CHN, RUS
- `CCCCLCCCC` : SC3
- `CCLCLCCLL` : SC2
- `CCXCXCCXX` : EC
- `LLLLLLCLL` : T1

## Fiabilite (cas d'erreurs de donnees + codes de remplissage pour 1000 matchs, croissant)

| Code | Erreurs de donnees | Codes de remplissage | Doublons | Pour 1000 matchs | Noms a verifier |
|---|---|---|---|---|---|
| ARG | 0 | 0 | 0 | 0.0 | 0 |
| AUT | 0 | 0 | 0 | 0.0 | 0 |
| B1 | 0 | 0 | 0 | 0.0 | 0 |
| BRA | 0 | 0 | 0 | 0.0 | 0 |
| D2 | 0 | 0 | 0 | 0.0 | 0 |
| DNK | 0 | 0 | 0 | 0.0 | 0 |
| E3 | 0 | 0 | 0 | 0.0 | 0 |
| F2 | 0 | 0 | 0 | 0.0 | 0 |
| FIN | 0 | 0 | 0 | 0.0 | 0 |
| I1 | 0 | 0 | 0 | 0.0 | 0 |
| I2 | 0 | 0 | 0 | 0.0 | 1 |
| IRL | 0 | 0 | 0 | 0.0 | 0 |
| JPN | 0 | 0 | 0 | 0.0 | 0 |
| MEX | 0 | 0 | 0 | 0.0 | 0 |
| NOR | 0 | 0 | 0 | 0.0 | 0 |
| P1 | 0 | 0 | 0 | 0.0 | 0 |
| POL | 0 | 0 | 0 | 0.0 | 0 |
| ROU | 0 | 0 | 0 | 0.0 | 0 |
| RUS | 0 | 0 | 0 | 0.0 | 0 |
| SC0 | 0 | 0 | 0 | 0.0 | 1 |
| SC2 | 0 | 0 | 0 | 0.0 | 1 |
| SC3 | 0 | 0 | 0 | 0.0 | 1 |
| SWE | 0 | 0 | 0 | 0.0 | 1 |
| SWZ | 0 | 0 | 0 | 0.0 | 1 |
| E2 | 1 | 0 | 0 | 0.362 | 0 |
| EC | 0 | 1 | 0 | 0.368 | 0 |
| USA | 0 | 1 | 0 | 0.393 | 0 |
| SP2 | 1 | 0 | 0 | 0.433 | 0 |
| SP1 | 0 | 2 | 0 | 1.053 | 0 |
| E1 | 1 | 2 | 0 | 1.087 | 1 |
| E0 | 1 | 2 | 0 | 1.579 | 0 |
| N1 | 0 | 3 | 0 | 1.961 | 0 |
| D1 | 0 | 4 | 0 | 2.614 | 0 |
| T1 | 0 | 6 | 0 | 3.429 | 0 |
| F1 | 0 | 7 | 0 | 4.172 | 0 |
| SC1 | 2 | 3 | 0 | 5.556 | 2 |
| G1 | 0 | 7 | 0 | 5.887 | 0 |
| CHN | 16 | 0 | 0 | 13.267 | 1 |

## Indices de segmentation historique (a examiner; aucune fusion d'editions ni d'identites)

- ARG: nombre de matchs different selon les saisons: {"2122": 501, "2223": 581, "2324": 582, "2425": 581, "2526": 510}
- ARG: plusieurs editions dans un meme fichier: {"2122": ["Copa De La Liga Profesional", "Liga Profesional"], "2223": ["Copa De La Liga Profesional", "Liga Profesional"], "2324": ["Copa De La Liga Profesional", "Liga Profesional"], "2425": ["Copa De La Liga Profesional", "Liga Profesional"]}
- ARG: libelle de competition different selon les saisons: {"2122": "Copa De La Liga Profesional", "2223": "Copa De La Liga Profesional", "2324": "Liga Profesional", "2425": "Copa De La Liga Profesional", "2526": "Liga Profesional"}
- ARG: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- AUT: nombre de matchs different selon les saisons: {"2122": 195, "2223": 195, "2324": 195, "2425": 192, "2526": 192}
- AUT: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- B1: nombre de matchs different selon les saisons: {"2122": 306, "2223": 306, "2324": 312, "2425": 312, "2526": 311}
- B1: structure aller-retour simple non respectee: 2324,2425,2526
- CHN: nombre de matchs different selon les saisons: {"2122": 180, "2223": 306, "2324": 240, "2425": 240, "2526": 240}
- CHN: structure aller-retour simple non respectee: 2122
- DNK: nombre de matchs different selon les saisons: {"2122": 193, "2223": 193, "2324": 193, "2425": 192, "2526": 192}
- DNK: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- EC: nombre de matchs different selon les saisons: {"2122": 506, "2223": 552, "2324": 552, "2425": 552, "2526": 552}
- F1: nombre de matchs different selon les saisons: {"2122": 380, "2223": 380, "2324": 306, "2425": 306, "2526": 306}
- F2: nombre de matchs different selon les saisons: {"2122": 380, "2223": 380, "2324": 380, "2425": 306, "2526": 305}
- FIN: nombre de matchs different selon les saisons: {"2122": 164, "2223": 170, "2324": 167, "2425": 169, "2526": 177}
- FIN: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- G1: nombre de matchs different selon les saisons: {"2122": 240, "2223": 240, "2324": 240, "2425": 233, "2526": 236}
- G1: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- IRL: nombre de matchs different selon les saisons: {"2122": 186, "2223": 181, "2324": 181, "2425": 181, "2526": 180}
- IRL: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- JPN: nombre de matchs different selon les saisons: {"2122": 380, "2223": 310, "2324": 306, "2425": 380, "2526": 380}
- JPN: structure aller-retour simple non respectee: 2223
- MEX: nombre de matchs different selon les saisons: {"2122": 342, "2223": 342, "2324": 340, "2425": 340, "2526": 336}
- MEX: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- NOR: nombre de matchs different selon les saisons: {"2122": 241, "2223": 242, "2324": 242, "2425": 242, "2526": 240}
- NOR: structure aller-retour simple non respectee: 2122,2223,2324,2425
- POL: structure aller-retour simple non respectee: 2223
- ROU: nombre de matchs different selon les saisons: {"2122": 320, "2223": 321, "2324": 321, "2425": 315, "2526": 321}
- ROU: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- RUS: nombre de matchs different selon les saisons: {"2122": 244, "2223": 244, "2324": 244, "2425": 240, "2526": 240}
- RUS: structure aller-retour simple non respectee: 2122,2223,2324
- SC0: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- SC1: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- SC2: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- SC3: libelle de competition different selon les saisons: {"2122": "League Two", "2223": "League Two", "2324": "League Two", "2425": "League Two", "2526": null}
- SC3: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- SWE: nombre de matchs different selon les saisons: {"2122": 242, "2223": 242, "2324": 240, "2425": 242, "2526": 240}
- SWE: structure aller-retour simple non respectee: 2122,2223,2425
- SWZ: nombre de matchs different selon les saisons: {"2122": 181, "2223": 182, "2324": 230, "2425": 228, "2526": 228}
- SWZ: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
- T1: nombre de matchs different selon les saisons: {"2122": 380, "2223": 342, "2324": 380, "2425": 342, "2526": 306}
- USA: nombre de matchs different selon les saisons: {"2122": 472, "2223": 489, "2324": 521, "2425": 522, "2526": 540}
- USA: structure aller-retour simple non respectee: 2122,2223,2324,2425,2526
