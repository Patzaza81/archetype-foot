# Bilan consolide - completude des archives Football-Data (190 saisons, 38 competitions)

Etat gele du 04/11/2026, branche `classement-descriptif-fd`. Aucune archive source modifiee, rien fusionne dans `main`. Document descriptif: mesure ce qui est reellement verifie, ne predit rien.

## 1. Comptes

- 190 saisons inventoriees; 181 verifiees sur la completude de la competition (9 `COMPLETUDE_NON_VERIFIEE`); 181 examinees sur la dimension archive.
- **Examinee n'est pas integralement verifiee**: seules les saisons `ARCHIVE_COMPLETE_PERIMETRE_ETENDU` ont un perimetre large; les partielles, les phases non detaillees et les signalements restent distincts.

| Statut d'archive | Saisons |
|---|---|
| `ARCHIVE_COMPLETE_PERIMETRE_ETENDU` | 33 |
| `ARCHIVE_COMPLETE_PERIMETRE_PARTIEL` | 99 |
| `MATCH_ARCHIVE_MANQUANT` | 23 |
| `PHASE_EXCLUE_NON_DETAILLEE` | 17 |
| `MATCH_ATTRIBUE_NON_JOUE` | 7 |
| `SCORE_ATTRIBUE_DIVERGENT` | 2 |
| `ARCHIVE_NON_EXAMINEE` | 9 |
| **Total** | **190** |

- Competitions comparables sans reserve sur l'archive (5 saisons verifiees ET perimetre etendu): **['BRA', 'E0', 'SP1']** (3 sur 38).
- Competitions comparables sans reserve sur la completude de la competition: 30 sur 38 (inchange).

Legende des cartes ci-dessous (saisons 2122, 2223, 2324, 2425, 2526): E etendu, P partiel, M matchs manquants, X phase exclue non detaillee, A attribue non joue, D score attribue divergent, - non examinee.

## 2. Carte par competition

| Competition | Archive (5 saisons) | Comparable archive |
|---|---|---|
| ARG | P - P P P | non |
| AUT | P P P M M | non |
| B1 | M M M - - | non |
| BRA | E E E E E | oui |
| CHN | P A E E E | non |
| D1 | A P P A P | non |
| D2 | P P P P P | non |
| DNK | P P P M M | non |
| E0 | E E E E E | oui |
| E1 | P P P P P | non |
| E2 | P P P P P | non |
| E3 | P P P P P | non |
| EC | P P P P P | non |
| F1 | P P P P A | non |
| F2 | P P P P A | non |
| FIN | P M M P M | non |
| G1 | M P P - P | non |
| I1 | E M E E E | non |
| I2 | P P P M P | non |
| IRL | A X M M X | non |
| JPN | D P E E E | non |
| MEX | A P P P - | non |
| N1 | P P P P P | non |
| NOR | P P - P M | non |
| P1 | P P P P P | non |
| POL | E - E E E | non |
| ROU | P P P M - | non |
| RUS | P D P M M | non |
| SC0 | P P P P P | non |
| SC1 | X X X X X | non |
| SC2 | X X X X X | non |
| SC3 | X X X X X | non |
| SP1 | E E E E E | oui |
| SP2 | P P P P P | non |
| SWE | P P M P M | non |
| SWZ | - P P M M | non |
| T1 | E P E E E | non |
| USA | P P P P P | non |

## 3. `ARCHIVE_COMPLETE_PERIMETRE_ETENDU` - 33 saisons

Saisons: BRA 2122-2526 (5), E0 (5), SP1 (5), I1 2122/2324/2425/2526 (4), T1 2122/2324/2425/2526 (4), POL 2122/2324/2425/2526 (4), CHN 2324/2425/2526 (3), JPN 2324/2425/2526 (3).

**Ce que le statut prouve, et ce qu'il ne prouve pas.** Il repose sur trois critiques de force differente, a ne pas confondre:

1. **Rencontres de saison reguliere - PREUVE calculee, independante de Wikipedia.** Pour les 33 saisons, chaque paire (domicile, exterieur) apparait exactement une fois dans le CSV (N x (N-1) lignes, 0 doublon, 0 manquante), recalcule le 04/11/2026 sur les fichiers actuels (33/33). Les 33 ont aussi une completude de competition VERIFIEE (equipes et matchs attendus confirmes par une source externe).
2. **Phases finales - `aucune_phase_documentee` pour les 33** (aucune n'est `individuelle`). Cela signifie qu'aucune phase finale ou barrage n'est documente pour ces competitions/saisons; ce n'est PAS une demonstration qu'il n'en existe pas. Appui: le format connu de ces championnats (pas de play-off de relegation/titre dans la table) et les pages Wikipedia consultees, qui ne mentionnent aucun play-off de ligue; certaines le disent explicitement (ex.: J1 2024, 'sans barrage J1/J2'; Super Lig 2021-22, 'les quatre derniers descendent directement'), la plupart n'en font simplement pas mention. Dans I1 2022-23, un match de depart (Spezia-Verona) existait: cette saison est donc classee en matchs manquants, pas ici.
3. **Matchs additionnels (interrompus, attribues, annules, rejoues) - ABSENCE DE MENTION, pas preuve d'absence.** Une seule source (Wikipedia) a ete lue par saison; l'absence de mention n'est jamais une preuve negative. Les cas trouves ont ete consignes (signalements); les 33 saisons n'en ont aucun, ce qui signifie 'aucun cas trouve dans cette source', pas 'aucun cas n'existe'.

Lecture correcte: `ETENDU` = identite des rencontres de saison reguliere PROUVEE, plus aucune anomalie ni phase finale trouvee dans le perimetre examine. Ce n'est pas une certification d'exhaustivite absolue; le qualificatif 'etendu' decrit le perimetre examine (le plus large atteint), pas la force de la preuve de chaque composante. Si cette formulation est jugee trop forte, le statut peut etre renomme sans toucher aux donnees.

## 4. `ARCHIVE_COMPLETE_PERIMETRE_PARTIEL` - 99 saisons

Aucun match documente manquant dans le perimetre examine, mais ce perimetre est incomplet. Raison du caractere partiel, par saison:
- 52 saisons: phases finales: non_examinee
- 14 saisons: saison reguliere par comptes seulement + phases finales: total_seulement
- 10 saisons: saison reguliere par comptes seulement + matchs additionnels: non_examines
- 8 saisons: phases finales: total_seulement
- 5 saisons: saison reguliere par comptes seulement + phases finales: non_examinee
- 3 saisons: saison reguliere par comptes seulement + phases finales: total_seulement + matchs additionnels: examines_non_resolus
- 3 saisons: phases finales: non_examinee + matchs additionnels: examines_non_resolus
- 2 saisons: saison reguliere par comptes seulement + phases finales: total_seulement + matchs additionnels: non_examines
- 1 saisons: saison reguliere par comptes seulement
- 1 saisons: matchs additionnels: examines_non_resolus

Saisons par competition: ARG 2122, 2324, 2425, 2526; AUT 2122, 2223, 2324; CHN 2122; D1 2223, 2324, 2526; D2 2122, 2223, 2324, 2425, 2526; DNK 2122, 2223, 2324; E1 2122, 2223, 2324, 2425, 2526; E2 2122, 2223, 2324, 2425, 2526; E3 2122, 2223, 2324, 2425, 2526; EC 2122, 2223, 2324, 2425, 2526; F1 2122, 2223, 2324, 2425; F2 2122, 2223, 2324, 2425; FIN 2122, 2425; G1 2223, 2324, 2526; I2 2122, 2223, 2324, 2526; JPN 2223; MEX 2223, 2324, 2425; N1 2122, 2223, 2324, 2425, 2526; NOR 2122, 2223, 2425; P1 2122, 2223, 2324, 2425, 2526; ROU 2122, 2223, 2324; RUS 2122, 2324; SC0 2122, 2223, 2324, 2425, 2526; SP2 2122, 2223, 2324, 2425, 2526; SWE 2122, 2223, 2425; SWZ 2223, 2324; T1 2223; USA 2122, 2223, 2324, 2425, 2526

## 5. `MATCH_ARCHIVE_MANQUANT` - 23 saisons

- **AUT:2425** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_et_dates; perimetre: implique_un_club_de_la_ligue) - Barrage Conference League (demi-finale 29/05/2025, finale 01/06/2025) absent de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **AUT:2526** `MATCH_ARCHIVE_MANQUANT` (absents: 3; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Barrage Conference League: Ried 2-1 Wolfsberger (19/05/2026), Ried 2-1 Rapid (22/05), Rapid 3-0 Ried (25/05) (RSSSF), absents de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **B1:2122** `MATCH_ARCHIVE_MANQUANT` (absents: 14; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue) - Play-offs de la saison (14 matchs) non presents dans l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **B1:2223** `MATCH_ARCHIVE_MANQUANT` (absents: 24; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue) - Play-offs de la saison (24 matchs) non presents dans l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **B1:2324** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Standard-Westerlo attribue 0-5 (non joue: Standard n'a pas pris le coup d'envoi), absent de l'archive; ce n'est pas un match joue. (qualification corrigee: match attribue, aucune rencontre disputee absente)  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **B1:2324** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_et_equipes; perimetre: hors_clubs_de_la_ligue) - Deux matchs de barrage de promotion/relegation contre Lommel, absents de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **DNK:2425** `MATCH_ARCHIVE_MANQUANT` (absents: 1; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrage europeen Randers-Silkeborg (selon la page Wikipedia), absent de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **DNK:2526** `MATCH_ARCHIVE_MANQUANT` (absents: 1; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrage europeen Brondby-Copenhague du 21/05/2026, absent de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **FIN:2223** `MATCH_ARCHIVE_MANQUANT` (absents: 1; preuve: match_par_match; perimetre: hors_clubs_de_la_ligue) - Jaro-EIF 2-1 le 12/10/2022 (premier tour du parcours de barrage de Ykkonen, RSSSF), absent de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **FIN:2324** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation Mariehamn-Gnistan: 0-0 le 25/10/2023 et 3-0 le 29/10/2023 (RSSSF), absents de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **FIN:2526** `MATCH_ARCHIVE_MANQUANT` (absents: non documente; preuve: equipes_sans_nombre; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation KTP-TPS absent de l'archive; nombre de matchs non documente dans la verification.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **G1:2122** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation Lamia-Veria (2 manches), absent de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **I1:2223** `MATCH_ARCHIVE_MANQUANT` (absents: 1; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Match de depart Spezia-Hellas Verona (egalite a 31 points, 17e/18e): Verona 3-1, terrain neutre, date non indiquee par la source; absent de l'archive (aucune des deux equipes n'a plus de 38 matchs). Source: Wikipedia 2022-23 Serie A.  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: individuelle; matchs additionnels: examines
- **I2:2425** `MATCH_ARCHIVE_MANQUANT` (absents: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Play-out Sampdoria-Salernitana, match aller du 15/06/2025: 2-0 (Wikipedia 2024-25 Serie B), joue, absent de l'archive (table de saison reguliere seulement).  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: non_examinee; matchs additionnels: examines
- **I2:2425** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Play-out, match retour du 22/06/2025 a Salerne suspendu a la 74e minute (Sampdoria menait 2-0 sur le terrain), victoire 3-0 attribuee a la Sampdoria par la Lega B (Wikipedia); absent de l'archive; ce n'est pas un match joue en entier.  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: non_examinee; matchs additionnels: examines
- **IRL:2324** `MATCH_ARCHIVE_MANQUANT` (absents: non documente; preuve: equipes_sans_nombre; perimetre: hors_clubs_de_la_ligue) - Matchs de First Division du parcours de barrage (Waterford-Athlone, Cobh-Wexford, Waterford-Cobh le 04/11/2023...) absents de l'archive; seule la finale y figure.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **IRL:2425** `MATCH_ARCHIVE_MANQUANT` (absents: non documente; preuve: equipes_sans_nombre; perimetre: hors_clubs_de_la_ligue) - Matchs de First Division du parcours de barrage (demi-finales, finale Bray-Athlone) absents de l'archive; seule la finale Bray-Drogheda y figure.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **NOR:2526** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation Bryne (14e)-Aalesund, 4-1 cumule pour Aalesund: 2 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: total_seulement; matchs additionnels: examines_non_resolus
- **ROU:2425** `MATCH_ARCHIVE_MANQUANT` (absents: 4; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue) - Quatre matchs de barrage Liga I/Liga II absents de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **RUS:2425** `MATCH_ARCHIVE_MANQUANT` (absents: 4; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrages de relegation (deux matchs aller-retour chacun): Akhmat-Ural (3-2 cumule) et Pari NN-Sochi (3-4 cumule): 4 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: total_seulement; matchs additionnels: examines
- **RUS:2526** `MATCH_ARCHIVE_MANQUANT` (absents: 4; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrages de relegation: Dynamo Makhachkala-Ural (3-0 cumule) et Akron-Rotor (2-1 cumule), 23/05/2026: 4 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: total_seulement; matchs additionnels: examines
- **SWE:2324** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation Brommapojkarna-Utsiktens, 7-0 cumule (Allsvenskan 14e contre 3e de Superettan 2023): 2 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: total_seulement; matchs additionnels: examines
- **SWE:2526** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation, 14e d'Allsvenskan (IFK Norrkoping d'apres le classement de la page) contre Orgryte IS, 3-0 cumule pour Orgryte: 2 matchs, scores individuels non obtenus. Absents de l'archive (table de saison reguliere)  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: total_seulement; matchs additionnels: examines
- **SWZ:2425** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation (2 manches) absent de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SWZ:2526** `MATCH_ARCHIVE_MANQUANT` (absents: 2; preuve: nombre_seulement; perimetre: implique_un_club_de_la_ligue) - Barrage de relegation (2 manches) absent de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -

## 6. `PHASE_EXCLUE_NON_DETAILLEE` - 17 saisons

- **IRL:2223** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: hors_clubs_de_la_ligue) - Matchs de First Division du parcours de barrage absents de l'archive; seule la finale UC Dublin-Waterford y figure.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **IRL:2526** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: hors_clubs_de_la_ligue) - Barrages (hors ligue) exclus: matchs non documentes individuellement, absents de l'archive.  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC1:2122** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC1:2223** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC1:2324** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC1:2425** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC1:2526** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC2:2122** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC2:2223** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC2:2324** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC2:2425** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC2:2526** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC3:2122** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC3:2223** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC3:2324** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC3:2425** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -
- **SC3:2526** `PHASE_EXCLUE_NON_DETAILLEE` (absents: non documente; preuve: existence_seulement; perimetre: non_documente) - Barrages exclus (verification: 'barrages exclus'); matchs non documentes individuellement, absents de l'archive (180 lignes de championnat).  
  Perimetre examine: saison reguliere: -; phases finales: -; matchs additionnels: -

## 7. `MATCH_ATTRIBUE_NON_JOUE` - 7 saisons

- **CHN:2223** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 8; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Wikipedia (2022 CSL) marque des matchs 'attribues' 3-0. Huit sont presents dans l'archive avec le score 3-0 attribue: Beijing Guoan 0-3 Shanghai Port (27/12), Cangzhou 3-0 Hebei (27/12), Guangzhou City 0-3 Dalian Pro (28/06), Henan 3-0 Shenzhen (23/12), Shandong 3-0 Beijing Guoan (31/12), Shandong 3-0 Meizhou Hakka (27/12), Tianjin 0-3 Dalian Pro (27/12), Wuhan Three Towns 3-0 Tianjin (31/12). Le neuvieme cite par la page, Dalian Pro 0-3 Guangzhou City, ne correspond pas a l'archive (Dalian Pro 2-0 Guangzhou City le 08/06/2022): ecart non resolu (lecture de la page a verifier). Les dates ne sont pas donnees par la page; la raison de chaque attribution n'est pas precisee.  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: aucune_phase_documentee; matchs additionnels: examines_non_resolus
- **D1:2122** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Bochum-M'gladbach (18/03/2022): match interrompu, victoire 2-0 attribuee a M'gladbach par le tribunal sportif de la DFB (reference citee par Wikipedia, 24/03/2022). Present dans l'archive avec le score 0-2 (score attribue, pas le score au moment de l'interruption, que la source ne donne pas).  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: non_examinee; matchs additionnels: examines
- **D1:2425** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: nombre_et_equipes; perimetre: implique_un_club_de_la_ligue) - Union Berlin-Bochum (14/12/2024): match interrompu, donne a Bochum par la DFB (titre de la reference DFB.de du 09/01/2025 cite par Wikipedia; le score attribue n'est pas ecrit dans la page). Present dans l'archive avec le score 0-2, identique au tableau de resultats de Wikipedia.  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: non_examinee; matchs additionnels: examines
- **F1:2526** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Nantes-Toulouse (17/05/2026): match interrompu apres invasion de terrain, score 0-0 enterine par la ligue (Le Parisien et BBC cites par Wikipedia). Present dans l'archive avec 0-0; resultat enterine, pas un match termine.  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: non_examinee; matchs additionnels: examines
- **F2:2526** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Bastia-Red Star (05/12/2025): interrompu a la 57e minute a 0-0 (fumigene), perdu par forfait par Bastia (Wikipedia). Ligne presente dans l'archive SANS score (ni FTHG ni FTAG); le tableau Wikipedia affiche 0-3 sans l'identifier comme score de forfait; buts non comptes au classement par la source. Un second match interrompu (0-2, fumigenes de supporters de Bastia) dont le score a ete confirme par la LFP n'est pas identifie dans la page (adversaire et date non indiques).  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: non_examinee; matchs additionnels: examines
- **IRL:2122** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Sligo Rovers-Waterford (15/05/2021): Waterford a declare forfait (cas de COVID-19), victoire 3-0 attribuee a Sligo (Wikipedia, '3-0*'). Present dans l'archive avec 3-0.  
  Perimetre examine: saison reguliere: comptes_par_equipe_et_total; phases finales: individuelle; matchs additionnels: examines
- **MEX:2122** `MATCH_ATTRIBUE_NON_JOUE` (absents: 0; attribues non joues: 1; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Queretaro-Atlas (05/03/2022, Clausura): arrete a la 60e minute (Queretaro 0-1, bagarre), victoire 0-3 attribuee a Atlas (Wikipedia). Present dans l'archive avec 0-3 (score attribue, pas le score au moment de l'arret).  
  Perimetre examine: saison reguliere: comptes_par_equipe_et_total; phases finales: total_seulement; matchs additionnels: examines

## 8. `SCORE_ATTRIBUE_DIVERGENT` - 2 saisons

- **JPN:2122** `SCORE_ATTRIBUE_DIVERGENT` (absents: 0; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Urawa-Shonan (20/06/2021): rencontre PRESENTE dans l'archive avec le score joue Urawa 2-3 Shonan; la JPFL a attribue 3-0 a Shonan (joueur non qualifie, Wikipedia 2021 J1 League). Score officiel different du score archive; rien n'est absent, rien n'est modifie.  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: aucune_phase_documentee; matchs additionnels: examines
- **RUS:2223** `SCORE_ATTRIBUE_DIVERGENT` (absents: 0; preuve: match_par_match; perimetre: implique_un_club_de_la_ligue) - Pari NN-Torpedo Moscou (19/03/2023): rencontre PRESENTE dans l'archive avec le score joue 1-1; l'Union russe a attribue 3-0 a Torpedo (joueur non eligible, decision du 22/03/2023; Wikipedia 2022-23 RPL). Score officiel different du score archive; rien n'est absent, rien n'est modifie.  
  Perimetre examine: saison reguliere: paires_completes_verifiees; phases finales: total_seulement; matchs additionnels: examines

## 9. `ARCHIVE_NON_EXAMINEE` - 9 saisons

Saisons non verifiees (`COMPLETUDE_NON_VERIFIEE`), aucun examen d'archive: ARG:2223, B1:2425, B1:2526, G1:2425, MEX:2526, NOR:2324, POL:2223, ROU:2526, SWZ:2122.

## 10. Cas non resolus (jamais comptes comme complets)

- **ARG:2122** - Un match de Copa de la Liga Profesional 2021 (3e journee) est dit 'suspendu' (18 minutes restantes jouees plus tard) par la page Liga Profesional; l'issue n'est pas precisee: non resolu.
- **CHN:2223** - Matchs attribues: 8 confirmes dans l'archive sur 9 cites par la page (la preuve precedente en comptait 7); un ecart non resolu (voir signalements_archive). CAS NON RESOLU MAINTENU: Dalian Pro-Guangzhou City (cite 0-3 attribue par la page; archive 2-0 le 08/06/2022). Les 8 autres cas confirmes ne valident pas ce neuvieme.
- **EC:2526** - Reference de presse citee par Wikipedia (BBC, 17/10/2025): 'Iron awarded Wealdstone win, will replay Eastleigh'; details et score de rejouer non donnes par la page: non resolu, non compare a l'archive.
- **F1:2324** - Montpellier-Clermont: match interrompu pour troubles du public (Montpellier: 1 point retire, Wikipedia); date et score officiel non indiques par la source (les deux rencontres de l'archive affichent 1-1: 29/11/2023 Montpellier-Clermont et 14/04/2024 Clermont-Montpellier); statut officiel non tranche.
- **F2:2223** - Bordeaux-Rodez: match interrompu (invasion de terrain, references presse des 03 et 05/06/2023 citees par Wikipedia); score officiel non indique par la source (l'archive affiche Bordeaux 0-1 Rodez au 02/06/2023); statut officiel non tranche.
- **G1:2324** - Reference citee: decision juridique sur la defaite 0-3 d'Olympiacos contre Panathinaikos (22/10/2023), retrait d'un point et deux matchs a huis clos annules par le TAS; effet sur le resultat du match non precise par la page: non resolu, non compare a l'archive.
- **NOR:2526** - Une defaite 0-3 par forfait de Kristiansund apres reclamation acceptee est mentionnee par la page sans nommer le match ni le score ajuste; match non identifie, resultat dans l'archive non compare.
- **SWZ:2223** - Reference de presse citee par Wikipedia: 'Forfait-defaite pour le Servette FC' (21/03/2023), sans explication ni match nomme: non resolu.
- **T1:2223** - Gaziantep et Hatayspor se sont retires le 12/02/2023: la page ne dit pas si leurs resultats ont ete annules ou conserves (elle liste 36 matchs pour chacun et l'archive les contient: 19 equipes, 342 lignes).

- Autres cas hors perimetre de cette liste: 9 saisons `COMPLETUDE_NON_VERIFIEE` (B1 2425, B1 2526, SWZ 2122, G1 2425, MEX 2526, ARG 2223, NOR 2324, POL 2223, ROU 2526); les 4 dernieres a variantes de noms: voir `docs/VARIANTES_NOMS_EQUIPES.md` (aucune fusion).

## 11. Limite documentee: play-offs et barrages non examines individuellement

- 65 saisons verifiees ont `phases_finales: non_examinee` (play-offs/barrages hors table, absents de l'archive, non individualises): D1 (5); D2 (5); E1 (5); E2 (5); E3 (5); EC (5); F1 (5); F2 (5); I2 (5); N1 (5); P1 (5); SC0 (5); SP2 (5).
- Ces saisons restent au mieux `ARCHIVE_COMPLETE_PERIMETRE_PARTIEL` tant que cette limite n'est pas levee. Aucune decision de les examiner n'est prise. Verification: le compte de 65 correspond exactement aux entrees `phases_finales: non_examinee` du JSON (13 competitions x 5 saisons: D1, D2, E1, E2, E3, EC, F1, F2, I2, N1, P1, SC0, SP2), reparties par statut d'archive en 60 partielles, 4 `MATCH_ATTRIBUE_NON_JOUE` (D1 2122, D1 2425, F1 2526, F2 2526) et 1 `MATCH_ARCHIVE_MANQUANT` (I2 2425). Le chiffre de 62 annonce plus tot etait une erreur de ma part: c'etait le nombre de saisons alors en statut partiel (a cet instant), pas un decompte des phases non examinees; il ne s'appuyait pas sur le JSON.
- Information pour une phase ulterieure (factuelle): competitions dont les 5 saisons sont verifiees, a saison reguliere prouvee par paires et matchs additionnels examines, bloquees SEULEMENT par cette limite:
  D2, E1, E2, E3, N1, P1, SP2.

## 12. Controles executes apres le dernier changement de donnees

Dernier run reel: Actions 41872638609, commit `eba2dd8` (04/11/2026 16:57 UTC), conclusion `success`, suivi du commit bot `19f8e5e` (resultats, uniquement `data/inventaire`). Les controles du run precedent (`2d31772`) ne sont plus la reference.

- Etapes du run toutes `success`: tests (23 OK), inventaire, recomptage independant, classement, 'archives sources inchangees' (`git diff --exit-code -- data/football_data`), publication; etape d'echec 'skipped' (rien a signaler).
- Inventaire: publication `true`, 0 echec, 256 anomalies (nombre identique au run precedent). `dernier_run.json` (commit `eba2dd8`): 197 controles, 0 en echec.
- Recomptage independant (CSV sources vs inventaire): 58 000 comparaisons, 0 ecart. Classement: 38 competitions, `completude_incoherente: []`.
- Empreintes: manifeste `archives_avant` = `archives_apres` (220 fichiers, SHA-256 global `4abd0a25...bd94`). Les 190 fichiers sources (2122-2526) ont ete re-hashes en SHA-256 a partir des blobs git du commit `19f8e5e`: 0 ecart avec le manifeste, 0 difference avec `main` actuel (`8c2a4a1`).
- Le commit `19f8e5e` ne modifie que `data/inventaire` (3 fichiers de resultats).
- Reperage des comptes: les 190 saisons sont reparties sans chevauchement ni omission (190 cellules uniques); recompte independant a partir de `verifications_completude.json` = `classement_descriptif.json`, cellule par cellule, et = les chiffres de ce rapport.

## 13. Test `test_ancien_moteur_dc_intact_par_rapport_a_main` (comparaison actualisee avec `main` = `8c2a4a1`)

- Il execute `git diff --quiet origin/main -- moteur_dc data/dc tests/test_moteur_dc.py`; il echoue car `data/dc/journal.jsonl` (+55 lignes, prefixe identique a la branche) et `data/dc/pronostics.json` (1 ligne) different de `main`.
- Cause: commit nocturne du bot de `main`, `2dbae51` (04/11/2026 03:40 UTC, "Mise a jour pipeline"), absent de la branche. `moteur_dc/` et `tests/test_moteur_dc.py` sont identiques a `main`; la branche n'a modifie aucun fichier de `data/dc/`.
- Reproduction: copie temporaire de la branche avec ces 2 fichiers pris sur `main` -> le test passe. Le delta reel est donc exactement ces 2 fichiers de donnees du bot, pas du code. `main` a avance (`8cd4ee1` -> `8c2a4a1`, 2 commits: journal de rentabilite, moteur Europe) sans modifier `moteur_dc/`, `data/dc/`, `tests/` ni `data/football_data`: le delta est inchange. Il disparaitra apres integration de `main`; a re-controler a ce moment-la.

## 14. Methode et limites generales

- Sources: Wikipedia (principale), RSSSF, ESPN, presse citee. Le resume automatique des pages est lossy: les scores ou equipes peuvent manquer, d'ou les niveaux de preuve (`match_par_match`, `nombre_et_equipes`, `nombre_et_dates`, `equipes_sans_nombre`, `nombre_seulement`, `existence_seulement`).
- Preuve structurelle de l'identite des matchs: completude des paires domicile/exterieur (ligues a aller-retour simple). Les formats multi-phases ne l'ont pas: comptes par equipe et total seulement.
- Aucun match documente absent n'a ete ajoute; aucun score modifie; aucune equipe fusionnee.

## 15. Position par rapport au `main` actuel (actualisee, sans rebase ni fusion)

- `main` = `8c2a4a1`; branche = `19f8e5e`; ancetre commun `9692027`. Branche en avance de 47 commits, en retard de 4 (`2dbae51`, `8cd4ee1`, `269a14e`, `8c2a4a1`), branches divergentes. La reference `8cd4ee1` citee plus haut est depassee.
- Archives des 190 saisons (2122-2526): identiques a `main`. Les 47 fichiers `data/football_data` differents sont la saison 2627 (raw/normalized) et `manifest.json`, modifies par le bot de `main`; hors perimetre.
- Fichiers de `main` hors `data/football_data` modifies depuis l'ancetre commun: pipeline, journaux, tickets, exports (98 fichiers), sans lien avec le classement descriptif. Avant toute integration, la comparaison devra etre refaite sur la tete de `main` a ce moment-la.
