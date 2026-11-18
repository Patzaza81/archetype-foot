# Audit Mega Power — rapport (18/11/2026)

Statut : audit et expériences seulement. Aucun moteur modifié, PR 171 non fusionnée. Aucune cote lue dans aucun calcul. Code des expériences : `experiences_megapower/`, sorties brutes : `experiences_megapower/sorties/`.

## 0. Limites (à lire d'abord)
- Archive : 28/09 → 21/11/2026, soit 8 semaines, une saison. Les découpages A (50 % premiers jours), B (25 %), C (25 % derniers) donnent ~1 181 / 602 / 596 matchs.
- Ce sont des expériences sur archive, pas des résultats de journal gelé. Seul le journal gelé fera foi.
- Par championnat, l'échantillon est mince : médiane 14 matchs joués par championnat, 24 championnats sur 126 ont au moins 30 matchs.
- Par semaine : 3 tranches seulement. La « récurrence » est donc faible, pas démontrée.

## 1. Audit du code actuel (PR 171, v2)
Points faibles trouvés, non corrigés :
- Seuil universel 0,72 : il n'est pas appris par marché.
- Scénario catastrophe générique (boîte ±1σ sur λ), pas construit par marché.
- Le filtre des familles exclues est calculé sur les mêmes données que l'évaluation.
- Les pronostics corrélés (ex. 1N / N2&+1,5 ; −3,5 / multibuts 1-3, phi 0,89) sont comptés comme indépendants.
- m_équipe = 16 : 32 est meilleur sur l'archive (voir §3).
- Le taux de 79,58 % vient surtout du taux de base : mêmes marchés joués sans analyse = 75,91 %. Apport réel de l'analyse : +3,68 points (9 071 pronostics, walk-forward 23/10→17/11, 1 591 matchs).
- Marchés où l'analyse n'apporte rien : +1,5 buts (78,5 % vs 78,5 %), −4,5 buts (+0,3), −2,5 équipe extérieure (−0,1), +0,5 buts (−2,1), −5,5 buts (−8,1).
- Marchés où l'analyse apporte : N2 +21,5 ; dom −1,5 +21,1 ; 1N +10,6 ; ext −1,5 +9,9 ; cage dom non +5,0 ; −3,5 buts +4,4.

## 2. Données réellement disponibles
- Archive : 4 234 matchs, 3 558 joués, 2 379 joués et analysables (≥ 4 matchs au même lieu pour chaque équipe), 131 championnats analysables.
- xG présent sur 14,4 % des observations d'équipe (10 950 / 75 779).
- Pas de classement daté complet : le rang n'est pas exploitable. Remplacé par écart de différence de buts (gd) ou de points par match (ppm) calculés avant le match.
- Bloc Football-Data (`data/bloc_saisons`) : 16 558 matchs, 38 divisions, saisons 2526 et 2627 (du 23/01/2025 au 16/10/2026), buts seulement (pas de xG, `stats` vide sur l'échantillon lu). Les cotes du bloc n'ont pas été lues.
- Saison 2425 absente du dépôt.

## 3. Comparaison des variantes (perte logarithmique des scores, plus bas = mieux)
Archive, période de test C :
- A (sans suite) : 2,9806
- B (arithmétique) : 2,9996 ; C (géométrique) : 2,9941 ; D (les deux) : 2,9972
- E (suites normalisées par championnat, corrigées de l'adversaire) : arith 2,9938 ; géo 2,9897 ; les deux 2,9912
- Régression : 2,9907 ; moyenne pondérée récente : 2,9803 (égale à A)
Conclusion : aucune suite ne bat A sur C. Aucune des 23 marchés n'a de gain significatif (écarts B/C tous dans ±1 à 2 erreurs-types, ou dans le bruit).
Réglages (archive, C, comparés à la référence) :
- xG vs buts : écart de 0,002 au plus ; poids 0 ou 1 équivalents.
- Référentiel de la ligue (pseudo-matchs) : ramener la ligue vers la moyenne générale est meilleur ou égal ; la moyenne propre à la ligue est pire (+0,010).
- m_équipe : 32 meilleur que 16 (−0,0097 sur C) ; 64 un peu moins bon.
- Écart de classement : gd β=0,27 (C 2,9759 contre 2,9901 sans) ; ppm β=0,38 (2,9776) ; xgd, xpts, surperformance : inutiles.
- Tendance θ : meilleur à 0 ou 0,02 ; 0,1 dégrade.
Confirmation sur le bloc (16 558 matchs, 5 520 / 2 819 / 2 788) :
- m_équipe : 16 et 32 équivalents (C 2,9990 vs 3,0019) ; 8, 64, 128 pires.
- m_ligue : sans effet (C entre 3,0003 et 3,0029).
- Écart de classement : gd β 0,2–0,3 (C 2,9864 contre 2,9990 sans) ; ppm β 0,3–0,4 (2,9876–2,9879). Gain réel mais petit (~0,4 %).

## 4. Suites par marché
Voir §3 et `sorties/e1_suites.txt` : verdict « inutile » pour les 23 marchés. Le meilleur écart (dom_plus_0.5, +18,5 sur C) est à ±14,6 : bruit.

## 5. Seuils et intervalles optimaux par marché
Seuil choisi sur B (borne basse de Wilson maximale, ≥ 30 pronostics), confirmé sur C (`sorties/e3_seuils.txt`, `e4_validation.txt`). « Validé » = taux sur C supérieur au taux de base de plus de 2 erreurs-types.

| Marché | Seuil | n sur C | Taux C | Taux de base | Verdict |
|---|---|---|---|---|---|
| 1 | 0,68 | 27 | 70,4 % | 44,5 % | validé (n faible) |
| 2 | 0,50 | 72 | 56,9 % | 30,5 % | validé |
| 1N | 0,84 | 79 | 88,6 % | 69,5 % | validé |
| N2 | 0,66 | 142 | 71,1 % | 55,5 % | validé |
| +1,5 buts | 0,80 | 189 | 82,0 % | 74,8 % | validé |
| équipe dom marque | 0,84 | 188 | 85,1 % | 78,2 % | validé |
| 1N & +1,5 | 0,66 | 100 | 67,0 % | 51,7 % | validé |
| N2 & +1,5 | 0,50 | 163 | 58,9 % | 42,3 % | validé |
| 1N & −3,5 | 0,52 | 198 | 58,1 % | 48,2 % | validé |
| N2 & −3,5 | 0,50 | 47 | 59,6 % | 37,8 % | validé (n faible) |
| 12 | 0,76 | 214 | 77,6 % | 75,0 % | non validé |
| +0,5 / +2,5 / −2,5 / −3,5 / −4,5 buts | — | — | — | — | non validés (écart ≤ +4,1) |
| BTTS oui | 0,56 | 277 | 50,9 % | 53,0 % | non validé (sous la base) |
| BTTS non, N | — | — | — | — | aucun seuil avec 30 pronostics |
| équipe ext marque | 0,84 | 34 | 82,4 % | 69,0 % | non validé (n faible) |
| multibuts 1-3 / 2-4 / 1-4 | — | — | — | — | non validés |

10 marchés validés sur 23. Les intervalles de probabilité par tranche sont dans `e4_validation.txt` ; ils montrent que la probabilité annoncée est sur-estimée pour 12 et +1,5 dans la tranche 0,75–0,80 (C : 75,9 % et 69,9 %).

## 6. Résultats par championnat
Au seuil retenu, marchés validés, B∪C : seulement 14 championnats ont ≥ 44 pronostics. Meilleurs : Slovaquie 88,2 % (annoncé 75,3 %), Turquie Super Ligue 86,0 %, Espagne LaLiga 83,7 %, MLS 81,7 %. Pires : Espagne RFEF groupe 1 47,7 % (annoncé 65,8 %), Turquie TFF 1. Ligue 52,3 % (annoncé 69,3 %). Intervalles larges (±10 points) : ces écarts ne sont pas encore prouvés. Un marché peut être bon dans un championnat et faible dans un autre : non démontré statistiquement avec 8 semaines.

## 7. Récurrence dans le temps
3 tranches hebdomadaires seulement. Exemples (taux min–max) : 12 : 69,4–81,6 % ; +1,5 : 81,3–86,5 % ; N2 : 67,7–75,8 % ; 1N : 86,1–87,7 %. Marchés les plus stables : 1N, +1,5. Pas de conclusion plus forte possible avant d'avoir plus de semaines de journal gelé.

## 8. Architecture mathématique proposée
1. λ = μ · attaque · défense, ajusté à l'adversaire, buts (xG en complément quand il existe), rapprochement d'équipe m = 32 (à confirmer sur journal gelé).
2. Référentiel de ligue : moyenne générale (pas de μ propre à la ligue).
3. Écart de classement : terme gd, β ≈ 0,3 (appris).
4. Aucune suite arithmétique ni géométrique : retirées.
5. Grille Poisson / Dixon-Coles (ρ appris) → probabilités des marchés.
6. Quatre branches de croisement et trois scénarios conservés ; catastrophe à construire par marché (à tester).
7. Calibrage par marché (pas par famille) ; seuil par marché appris sur B et confirmé sur C ; borne basse de Wilson.
8. Un marché n'est publié que s'il est validé (lift sur le taux de base) ; sinon « aucun pronostic ».
9. Corrélations : un seul marché retenu par groupe corrélé (|phi| ≥ 0,7).

## 9. Cahier des charges (si validé)
- Apprendre le seuil, le calibrage et la validité par marché.
- Retirer les suites, m_équipe = 32, μ de ligue commun, garder gd.
- Journal : ajouter taux de base du marché, lift, validité.
- Page : n'afficher que les marchés validés.
- Tests : mêmes tests existants + test « aucune cote » + test anti-fuite (apprentissage sur jours < jour du match).
- Ne pas toucher aux autres moteurs.

## 10. Plan de test et critères d'acceptation
- Walk-forward quotidien sur archive puis journal gelé réel seul.
- Critère par marché : lift ≥ 2 erreurs-types sur C, n ≥ 30 pronostics, borne basse Wilson ≥ taux de base.
- Critère global : apport mesuré sur le taux de base ≥ +3,68 points (v2) sur la même période.
- Brier et log-loss ≤ taux de base et ≤ moyenne simple sur C.
- Rapport : annoncer matchs, pronostics, période.
- Revalider après 4 semaines de journal gelé réel.

## 11. Ce qui reste à faire (non fait)
- Catastrophe par marché.
- Test multi-saisons du référentiel de ligue avec saison 2425 (absente).
- Récurrence sur plus de 3 semaines.
