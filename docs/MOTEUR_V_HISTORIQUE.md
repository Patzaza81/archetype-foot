# Moteur v : conception, tests subis, résultats, suivi

Document de référence pour suivre v plus tard. Il dit **comment v a été conçu, ce qu'il a subi, ce qui a été mesuré, ce qui s'est révélé faux** et **comment le suivre**.
Description technique du moteur : `docs/MOTEUR_V.md`. Période de conception : 15-16/10/2026. Données de conception : `data/archive_test`, 440 matchs joués du 28/09 au
14/10/2026 avec cotes, score et >= 4 matchs au même lieu pour les deux équipes (liste figée : `evaluation/moteur_v/jeu_reglage_ids.json`), soit 10 771 lignes match x marché.
**Toutes les mesures ci-dessous sont EN ÉCHANTILLON (17 jours)** : seul le carnet `data/v/carnet.json` fait foi.

## 1. Cahier des charges (décisions de Patrick)
- Moteur « froid » et cartésien : seulement des chiffres, scores historiques des deux équipes **au même lieu** (domicile pour l'une, extérieur pour l'autre). Le classement ne pèse que faiblement (tendance).
- **Verrou d'échantillon inchangeable** : >= 4 matchs au même lieu pour les DEUX équipes, sinon match exclu ; coefficient k = 0,8 (4 matchs), 0,9 (5), 1,0 (6 et +) ; fenêtre des 12 derniers matchs au lieu.
- Règles d'origine sur le pourcentage brut : seuil 75 % (4-5 matchs) / 72 % (6+) ; cote 1,26-1,37 : >= 77 % ; cote > 1,37 : >= 72 % ; le pari doit passer les deux (le plus strict). **Cote minimale 1,26.**
- « Musique » (répétition des buts marqués/encaissés : stable, instable, pic, rupture) : conservée comme **alertes**, jamais comme filtre.
- Demandes ultérieures : régler le moteur sur les résultats connus ; diagnostic méticuleux des erreurs ; intégrer écart de points, classement et force des adversaires ; seuil 72 % puis recherche du meilleur seuil ; faire sortir des cotes 1,49-1,81 sans que la cote impose le choix ; deux étages (pronostic puis version filtrée par un calcul simple) ; pronostic principal + rubrique « autres ».

## 2. Écart entre les règles d'origine et la production (À SAVOIR)
- En production, v **n'applique pas** les seuils bruts 75/72/77 % : le choix se fait par le score du modèle et la fiabilité affichée est la fiabilité **mesurée par zone de cote**. Le verrou >= 4 matchs et la cote minimale 1,26 sont conservés.
- Les seuils bruts d'origine ne servent que dans la règle « Sûr » du test à l'aveugle (`evaluation/moteur_v/test_aveugle.py`, verrou 75/72).
- Raison : les mesures ci-dessous (section 3) montrent que le pourcentage brut est trop optimiste et n'apporte rien en plus de la cote.

## 3. Tests subis et résultats
Chiffres exacts ; scripts d'origine dans `evaluation/moteur_v/analyses_conception/` (archive, voir son LISEZMOI).

1. **Rejeu du prototype v1** (fréquences x k, verrou, musique) sur les 440 matchs : 488 lignes passent les seuils (239 matchs). Le pourcentage annoncé n'apporte aucune information au-delà de la cote (coefficient logistique ≈ 0, celui de la cote ≈ 1,0). Effet « malédiction du gagnant » : choisir le meilleur de ~60 marchés par match sélectionne le bruit favorable.
2. **Réglage « en trichant »** (sur résultats connus) : grille de 525 règles, découpes chronologiques. Les règles trouvées en échantillon **ne tiennent pas hors échantillon**. Règles A (buts d'une équipe, cote 1,50-2,00) et B (total de buts, cote 1,26-1,74, >= 80 %) figées dans `test_300.py` : il faut ~600 matchs neufs (A) et >1 000 (B) pour atteindre 100 paris.
3. **Diagnostic de calibration** (IC95 par rééchantillonnage des matchs). Pourcentage annoncé / réel : 60-70 % -> 62,9 / 58,4 ; 70-80 % -> 73,0 / 64,6 ; 80-90 % -> 82,7 / 66,8 ; 90 % et + -> 92,0 / 74,3. Par cote (final >= 60 %) : 1,26-1,37 -> 72,1 / 71,8 ; 1,37-1,5 -> 69,2 / 64,0 ; 1,5-1,7 -> 67,6 / 54,6 ; 1,7-2,0 -> 66,4 / 48,1 ; 2,0-3,0 -> 65,6 / 40,0. ROI négatif dans toutes les tranches de pourcentage sauf 90 % et + (35 lignes, +2,5 %, non significatif). Plus la cote monte, plus v surestime.
4. **Restrictions testées dans le temps** (réglage sur la 1re moitié, test sur la 2e, et l'inverse) : moteur actuel ROI -4,2 % puis -6,8 % ; « cote 1,26-1,37 » +2,5 % puis -15,2 % ; « cote <= 1,50 » -2,9 % puis -13,1 % ; hors handicaps/double chance/1X2 -7,8 % et -7,5 % ; >= 6 matchs -4,6 % et -4,1 %. **Aucune ne tient.**
5. **Calibrage par validation croisée** (erreur logarithmique, plus bas = mieux) : cote brute 0,5863 ; cote recalibrée 0,5818 ; + pourcentage v 0,5821 (coefficient -0,03, IC95 -0,10 à +0,04) ; + fréquences rétrécies 0,5821-0,5822. La cote surestime la probabilité de 4 à 6 points (marge du bookmaker) dans toutes les familles, sauf 1X2 (-0,2).
6. **Robustesse du pourcentage calibré** (dans les deux sens) : écart annoncé/réel 6,9 % et 7,9 % pour v brut, **1,5 % et 0,6 % calibré**. À >= 75 % calibré : 69 paris, 78,3 % (borne basse 67 %) puis 103 paris, 77,7 % (69 %). **Plafond ≈ 77-78 %** : aucune probabilité calibrée n'atteint 80 %.
7. **Écart de points** (1X2 et double chance, 1 526 lignes, 437 matchs) : erreur 0,6153 (cote) contre 0,6159 (+ points) ; coefficient 0,71 (IC95 -0,17 à +1,58), non prouvé. Le côté parié très défavorisé (écart <= -0,3) réussit 27,0 % pour 34,9 % implicites (-7,9 pts) : la cote surpaie les équipes faibles.
8. **Classement reconstruit** (sans fuite, depuis les historiques ; 138 championnats, médiane 11 équipes connues, donc partiel) : corrélation écart de points / écart de rang = **0,94** (même information). Erreur : cote 0,6156 ; + points 0,6176 ; + rang 0,6162 ; + les deux 0,6176. Côté parié très mal classé (<= -0,40) : -11 pts.
9. **Force des adversaires** (Poisson, 9 956 matchs distincts, 1 991 équipes) : erreur v brut 0,669 ; force seule **0,603** (nettement mieux que les fréquences brutes) ; cote 0,586 ; cote recalibrée 0,5818 ; + force 0,5815 (coefficient 0,13, IC95 -0,11 à +0,33). Ne bat pas la cote seule.
10. **Balayage du seuil calibré** (avec verrou) : 0,72 -> 178 paris, 73,0 % (borne basse 66 %, -8,2 pts en 2e moitié) ; 0,74 -> 118 paris, 74,6 % ; **0,76 -> 47 paris, 85,1 % (IC95 72-93 %), écart +11,3 / +4,0 selon la moitié, ROI +8,0 %** ; 0,78 -> 5 paris. Seuil retenu 0,76 pour la règle « Sûr », mais choisi parmi 7 seuils et calibré sur les mêmes matchs : **provisoire** (le seuil de rentabilité à cote 1,26 est 79,4 %, dans l'intervalle).
11. **Étage 2** (cote 1,45-1,85, probabilité du calcul simple >= 75 %) : 89 paris, 67,4 % pour 64,4 % de seuil de rentabilité, ROI +4,7 % (+6,1 % / +1,5 % par moitié) contre -8,5 % pour des paris au hasard dans la bande ; **p = 0,061 sans correction, 12 combinaisons essayées : non significatif**. Le calcul simple n'ajoute rien à la cote en régression (coefficient -0,13, IC95 -0,34 à +0,08 ; dans la bande -0,02, IC95 -0,24 à +0,21). C'est une hypothèse, pas un acquis.
12. **Mode « modèle seul »** (la cote ne choisit pas ; score = moyenne force des adversaires + calcul simple ; 1 pari par match) : cote 1,26-1,37 -> 310 paris, 74,8 % réel pour 78,6 % annoncés ; 1,37-1,49 -> 87 paris, 65,5 % pour 77,3 % ; **1,49-1,81 -> 35 paris, 54,3 % (borne basse 38 %) pour 73,7 % annoncés, ROI -15,3 %** ; > 1,81 -> 6-8 paris perdants. Exiger un score plus haut (70/75/80 %) ne remonte pas la zone 1,49-1,81. D'où les fiabilités affichées par zone (SÛR 74,8 / MOYEN 65,5 / RISQUÉ 54,3). Rubrique « autres » : 1,4 par match en moyenne, 111 matchs sans autre ; réussite SÛR 73,1 %, MOYEN 66,4 %, RISQUÉ 64,7 %, NON CALIBRÉ 38,5 %.
13. **Qualité des données** : 38 matchs de l'archive de test ont des cotes prises après le coup d'envoi (ou des cotes manifestement en cours de jeu, ex. Plus de 2,5 buts à 1,04). Rejeu sans eux (`evaluation/moteur_v/ids_cotes_apres_ko.json`) : variation < 2 points (SÛR 74,8 %, RISQUÉ 52,9 %, règle « Sûr » 47 paris 85,1 %) : conclusions inchangées. Le carnet de v n'écrit jamais un match sans coup d'envoi connu ni après son coup d'envoi.
14. **Vérification du code livré** : `python evaluation/moteur_v/rejoue_niveaux.py` rejoue le vrai package sur les 440 matchs et retrouve exactement les nombres de la ligne 12. 24 tests dans `tests/test_moteur_v.py` (suite complète : 2 240 tests passés au 16/10/2026).

## 4. Erreurs découvertes et corrigées (pour ne pas les refaire)
- **Verrou mal lu** (traité comme remplacé par les seuils de cote) : corrigé sur correction de Patrick (le verrou d'échantillon est inchangeable, le pari doit passer les deux seuils).
- **Musique BTTS** : lue comme série de valeurs, elle refusait à tort ; lue comme majorité binaire.
- **Plages de cotes annoncées fausses** : « cote max 1,277 à 75 % et 1,322 à 72 % » venaient de la formule à cote seule ; avec la force des adversaires les paris réels montent jusqu'à 1,32 (seuil 0,76) et 1,39 (seuil 0,72).
- **Étage 2 présenté comme un signal** : surestimé (p = 0,061, 12 essais). Corrigé : hypothèse à prouver.
- **Bogue du 16/10/2026 dans le package** : `lambdas_simples` recevait les scores de l'équipe extérieure orientés « du match » au lieu de « de son point de vue » (marqués et encaissés inversés). Détecté en reproduisant le test à l'aveugle (règle V : 57 paris au lieu de 27), corrigé, couvert par 2 tests de régression. Le premier `data/v` (261 pronostics) avait été produit avec cette version : supprimé et régénéré.
- **Comptes de tests annoncés incohérents** (23, 30, 37 selon les messages) : seul fait foi le résultat de pytest.
- **Leçon générale** : toute règle trouvée en échantillon doit passer un test à l'aveugle figé avant usage ; un chiffre « présenté » sans test dans le temps n'est pas une preuve.

## 5. Valeurs de référence à comparer au carnet
| Niveau (cote) | Fiabilité mesurée en échantillon | Score du modèle annoncé | Paris (échantillon) |
|---|---|---|---|
| SÛR (1,26-1,37) | 74,8 % | 78,6 % | 310 |
| MOYEN (1,37-1,49) | 65,5 % | 77,3 % | 87 |
| RISQUÉ (1,49-1,81) | 54,3 % | 73,7 % | 35 |
| NON CALIBRÉ (> 1,81) | 37,5 % | n/d | 8 |

Règles du test à l'aveugle (gelées le 16/10/2026) : **S** (calibré >= 0,76 + verrou 75/72) ; **V** (cote 1,45-1,85, calcul simple >= 75 %). Au rejeu de contrôle (jeu `essai_ids_10_10.json`, **non à l'aveugle**) : S 21 paris, 81,0 % ; V 27 paris, 66,7 %.

## 6. Comment suivre v
1. **Chaque semaine** : ouvrir `pronostics_v.html` (ou `data/v/pronostics_v.json`) : `bilan.par_niveau` donne, par niveau et par rôle (principal / autres), réglés, réussite, fiabilité annoncée, écart, IC95. Comparer à la section 5.
2. **Statuts** : `observation` (< 100 paris principaux réglés, ne pas miser) ; `controle_ok` (>= 100 réglés, fiabilités tenues, **ne veut pas dire rentable**) ; `gel` (un niveau SÛR/MOYEN/RISQUÉ à plus de 10 points sous son annonce sur >= 50 paris : arrêter de s'y fier). Le ROI du carnet est affiché, jamais jugé automatiquement.
3. **Test à l'aveugle** : `python evaluation/moteur_v/test_aveugle.py` (option `--max N`). Décision pour S et V séparément : **ADOPTÉE** si >= 100 paris, ROI >= +5 % et réussite > moyenne de 1/cote ; sinon REJETÉE ; < 100 paris = attendre, ne rien modifier. Une règle adoptée doit être confirmée sur un second lot avant tout usage réel. Estimation : ~26 matchs réglés par jour -> 100 paris V vers le 11/11/2026, 100 paris S vers le 20/11/2026.
4. **Ne pas modifier** pendant le test : seuils, zones, règles. Toute modification = nouvelle `PARAMETRES_VERSION` (`moteur_v/modele.py`) + mise à jour de ce document et des tests + nouveau test à l'aveugle.
5. **Remesurer les zones de fiabilité** seulement quand >= 1 000 matchs réglés sont disponibles, avec la même méthode (rejeu, validation chronologique), en datant la mesure.
6. **Ne pas mélanger** mesures en échantillon (section 3) et carnet : seul le carnet est prédictif.

## 7. Décisions ouvertes
- Seuil de la règle « Sûr » : 0,76 (provisoire, 47 paris) ou 0,74 (118 paris, plus de volume).
- Masquer ou non les niveaux RISQUÉ et NON CALIBRÉ sur la page (aujourd'hui affichés et signalés ; NON CALIBRÉ perdait presque toujours).
- Intégrer la règle « Sûr » au moteur de production (elle n'existe que dans le script d'évaluation).
- Seuils bruts 75/72/77 % d'origine : non appliqués en production (section 2).
- **Données à corriger** : archiver le vrai classement à chaque match (le classement de v est reconstruit, partiel) ; horodater la prise de chaque cote et rejeter celles prises après le coup d'envoi.

## 8. Historique durable (ajouté le 16/10/2026)
Le carnet est écrasé chaque nuit ; l'historique `data/v/historique/` (versions, règlements complets, instantanés du bilan) n'est jamais réécrit. Détail dans `docs/MOTEUR_V.md`, section « Historique durable ». Les matchs réglés avant cette date n'ont pas le détail des marchés.
