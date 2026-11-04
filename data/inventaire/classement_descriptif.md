# Classement descriptif des 38 profils

Regles inventaire `1.0.1`. Trois dimensions SEPAREES; aucun score global; aucun statut n'est une recommandation de marche.

**Ce classement decrit la disponibilite et la coherence des donnees. Ce n'est PAS un classement de performance predictive.**

## Avertissement completude

La completude reelle d'une saison (nombre d'equipes et de matchs attendus) n'est verifiee que si une verification externe est enregistree dans `verifications_completude.json`. Sinon: `COMPLETUDE_NON_VERIFIEE`. Une structure aller-retour complete dans l'archive est coherente mais ne prouve pas qu'aucune equipe n'a ete oubliee.

- Saisons verifiees: 31 sur 190 (E0:2122, E0:2223, E0:2324, E0:2425, E0:2526, E1:2122, E1:2223, E1:2324, E1:2425, E1:2526, E2:2122, E2:2223, E2:2324, E2:2425, E2:2526, E3:2122, E3:2223, E3:2324, E3:2425, E3:2526, I1:2122, I1:2223, I1:2324, I1:2425, I1:2526, I2:2122, I2:2223, I2:2324, I2:2425, I2:2526, T1:2223)
- **Competitions comparables sans reserve: 6 sur 38**

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
