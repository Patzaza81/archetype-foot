# Piste B′ : prior hiérarchique à moyenne Elo dans le Dixon-Coles pénalisé

Branche `moteur-dc-elo` (depuis main). Ordre de Patrick du 31/10/2026. Fiche écrite AVANT tout calcul. Aucune fusion avant validation du rapport. Pas de test sur les 827 matchs
d'archive, pas de critère sur le taux de réussite, pas de marge ΔLL, aucune constante posée à la main. `style_tag` écarté (piste A : échoue à Holm, dans la zone des placebos).

## État au 01/11/2026 : données trouvées, test fait avec écarts déclarés
- L'API ClubElo est en panne (HTTP 502 depuis le 31/10/2026) et clubelo.com bloque les robots (Cloudflare) : voir `data/clubelo/diagnostic.txt`, `data/clubelo/sonde_page.txt`. Aucun contournement n'a été tenté.
- Les données viennent d'une copie publique CC BY 4.0 (`data/clubelo/SOURCE.md`) : 105 clubs des cinq grands championnats, séries complètes. Contrôle d'intégrité : accord à 0,000 point avec une 2e copie indépendante (01/03/2026, 105 clubs).
- Couverture MESURÉE (`docs/DC_ELO_COUVERTURE.md`) : 13,0 % des matchs de 2025-26 du bloc, 6,9 % de ceux de 2026-27, 3,5 % de l'archive ARCHETYPE. L'affirmation « ClubElo couvre l'archive » est fausse.
- Écart au protocole : aucun match de 2026-27 des cinq grandes divisions ne passe le contrat 1.5 (saison trop jeune). Le test est donc un découpage chronologique de 2025-26 (date médiane 2026-02-08, fixée avant le résultat), plus l'inverse.
- Résultat et lecture : `docs/DC_ELO_RESULTATS.md`.

## Lecture (01/11/2026) : résultat nul, non concluant
- Gain de log-vraisemblance par match : +0,0006 (IC 95 % [−0,0074 ; +0,0088], MDE 0,0079, n = 679) ; inverse +0,0055 (IC [−0,0040 ; +0,0150], MDE 0,0097, n = 673). Borne basse < 0 : NON retenu, ni brut ni centré.
- γ est positif et stable (+0,15 sur les deux moitiés) ; δ change de signe (−0,10 / +0,05) : pas de lecture fiable pour la défense.
- EMAC : 0,0050 sans Elo, 0,0058 avec Elo (pas d'amélioration). Gains par division de signes mixtes (SP1 −0,0103, I1 +0,0111).
- Puissance : le test ne voit que des gains supérieurs à 0,008 par match ; un gain plus petit mais réel resterait invisible. Périmètre : 5 championnats seulement.
- Conclusion : l'Elo n'apporte pas de gain mesurable au Dixon-Coles sur ce périmètre. Module 4 et moteur inchangés. Pas de fusion.

## Modèle (déjà codé, testé sur ligues simulées : `moteur_dc/modele.py`, `tests/test_modele_elo.py`)
- Pénalité : (1/2σ²)·Σᵢ[(attᵢ − γ·Eᵢ)² + (dfnᵢ − δ·Eᵢ)²], remplace (1/2σ²)·Σᵢ(attᵢ² + dfnᵢ²). σ = valeur apprise du moteur (0,25), inchangée.
- Eᵢ = Elo de l'équipe i centré et réduit sur les équipes du championnat qui en ont un, au jour de la prédiction (garde-fou 3). Équipe sans Elo : Eᵢ = 0 ; championnat sans Elo (moins de 2 équipes couvertes) : pénalité habituelle (garde-fou 2). Aucune branche spéciale.
- Elo strictement antérieur : valeur dont l'intervalle [From, To] contient la veille du match (garde-fou 1) ; jamais celle du jour ni d'après.
- γ et δ : UN couple global, figé, appris sur le calibrage seulement. L'estimer à chaque ajustement de championnat (une vingtaine d'équipes) est trop bruité (vérifié sur ligues simulées) ; ce mode libre existe dans le code mais ne sert pas à la décision.
  Apprentissage : vraisemblance prédictive de la marche avant 2025-26, recherche par coordonnées comme au calibrage (départ (0, 0) = ridge actuel, la grille s'étend tant que ça s'améliore, aucune borne).
  Pas de recherche : mêmes conventions que `calibrage.PAS` (il fixe la résolution, pas le résultat).

## Rapprochement des noms (avant tout test)
Les noms Football-Data et ClubElo diffèrent (« Man United » / « ManUnited », accents, suffixes). La fonction de rapprochement sera testée sur au moins 3 cas qui passent et 3 qui échouent ; la liste des équipes sans correspondance est publiée, jamais corrigée en silence.

## Protocole (identique à la piste A)
- Apprentissage 2025-26 (9 488 matchs, marche avant hebdomadaire), test 2026-27 (1 598 matchs) figé.
- Écart apparié de log-vraisemblance du score par match entre Dixon-Coles avec prior Elo et Dixon-Coles pur (mêmes données, mêmes hyperparamètres).
- Intervalle à 95 % de la moyenne : bootstrap par rééchantillonnage des matchs (4 000 tirages). Retenu seulement si la borne basse est > 0.
- MDE recalculé pour cette expérience : 1,96·sd(écart)/√n avec la sd mesurée ici.
- Variante centrée (leçon de la piste A) publiée à côté : le Dixon-Coles pur sous-estime le niveau de buts de 2026-27 ; un prior Elo qui rattrape ce niveau, et non les équipes, ne doit pas passer pour un signal. Placebo : Elo permuté entre équipes d'un même championnat, même pipeline ; le nombre de « retenus » doit être compatible avec le hasard.

## Livrables
1. Tableau du gain de log-vraisemblance avec/sans prior Elo, intervalle à 95 %, MDE recalculé, couverture réelle (équipes, compétitions, matchs).
2. EMAC avec/sans Elo (erreur de calibration par dixième de probabilité, 103 marchés, 2026-27) ; si Elo dégrade la calibration, retrait.
3. Matrices DC pur et DC-Elo sur un match exemple.
4. Stabilité du signe de γ (et de δ) sur les deux moitiés de 2025-26 : bootstrap par blocs de championnats (les championnats sont rééchantillonnés, le couple optimal recalculé sur la courbe de vraisemblance de chacun).

## Limites annoncées d'avance
- Un seul échantillon de test (≈ 1 600 matchs) : un gain inférieur au MDE ne sera pas vu ; « retiré » ne veut pas dire « inutile ».
- Le gain éventuel viendra surtout des équipes à 4-8 matchs ; l'échantillon de test n'en contient qu'une partie.
- L'Elo est construit sur les résultats : il n'est pas indépendant des buts au sens strict, seulement de la fenêtre de 4 à 20 matchs de la saison courante.
