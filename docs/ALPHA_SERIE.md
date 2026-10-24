# Moteur alpha « séries » (`alpha_serie/`)

**C'est LE moteur alpha** (20/10/2026, ordre de Patrick). L'ancien alpha de `matrice_scenarios/` est supprimé ; ses données historiques restent en archive dans `data/comportement/` et `docs/parametres_comportement*.json`. Branché au pipeline nocturne (`python -m alpha_serie.suivi pipeline`, `continue-on-error`, hors tickets) : gèle les pronostics avant le coup d'envoi (`data/alpha_serie/journal.jsonl`, ajout seul), enregistre les résultats (`bilan.json`), publie la page (`pronostics.json`).

## Méthodologie (sacrée — ne pas modifier sans Patrick)
1. **Séries** au même lieu (domicile pour l'équipe à domicile, extérieur pour l'autre), strictement avant le jour du match, 4 à 7 matchs. Moins de 4 pour l'une des deux équipes : match exclu.
2. **Scénarios appariés** sur la même période (les n derniers matchs de chaque équipe, un contre un, n = plus petit échantillon) :
   - offensive : (marqués domicile, marqués extérieur) ;
   - défensive : (encaissés extérieur, encaissés domicile) = ce que marque chaque équipe.
3. **Marchés lus en buts entiers** (Plus de 1,5 = au moins 2 buts). **Marge de niveau obligatoire** (moyennes des séries : attendu d'une équipe = (ce qu'elle marque + ce que l'adversaire encaisse) / 2). Marché hors norme : **exclu**, consigné au registre avec la raison.
4. **Admission** : part de scénarios validants ≥ seuil (50 %) dans **chacune** des deux branches ET norme de niveau respectée. **Valeur** = moyenne des deux parts × k (4 matchs : 0,8 ; 5 : 0,9 ; 6 et + : 1,0).
5. **Aucune cote à l'analyse.** Étape 2 (`choisir`) : buts et équipes, cote ≥ 1,25, aucun maximum ; multiscores, aucune limite. Cote introuvable : le marché reste, marqué « cote à lire ».
6. **Trois onglets** (buts incl. multigoals, équipes incl. victoire / nul / double chance / handicaps ±0,5 et ±1,5 / buts par équipe / cages inviolées, multiscores) ; seuls les marchés retenus y figurent. Jamais deux événements identiques (le mieux classé est gardé).
7. **Multiscores** : lecture PAR GROUPE de scores Betpawa ; un groupe est retenu s'il revient au moins 3 fois (« constante de 3 ») sur l'ensemble des scénarios des deux branches.
8. **Graduation** (points ÷ matchs, goal-average ÷ matchs, nom d'équipe exact) : **alerte seulement**, jamais un filtre.

## Paramètres (`parametres.py`, `parametres.json`)
- Règles de Patrick en constantes (échantillon, k, constante de 3, cote minimale).
- Marges et seuils d'écart attendu : valeurs de départ = **planchers** validés par Patrick ; `calibration.py` les recalcule sur l'archive (résultats seuls) et **ne peut que les élargir**. Une marge calibrée est le plus petit cran de 0,25 but dont la réussite dépasse la base de plus d'une erreur-type et ne passe sous la base dans aucune moitié chronologique.
- Match nul : aucun seuil de niveau appris sur l'archive (la réussite du nul ne dépasse pas sa base) → il passe par la même porte que les autres marchés mais est rejeté au registre avec la raison tant qu'aucun seuil n'est appris. Se recalcule avec l'archive.
- Plages de multigoals : liste de départ dans `parametres.py` (à aligner sur celles que Betpawa propose ; les cotes de multigoals et de multiscores ne sont pas dans l'archive).

## Commandes
- `python -m alpha_serie.calibration` : recalcule `alpha_serie/parametres.json`.
- `python -m alpha_serie.backtest` : calibre sur la 1re moitié des jours, rejoue la 2e, écrit `docs/alpha_serie_backtest.json`.
- `python -m alpha_serie.suivi [pipeline|geler|resultats|bilan|page]` : suivi nocturne.
- Tests : `tests/test_alpha_serie.py`.

## Résultat du backtest au 20/10/2026 (marche avant, 707 matchs rejoués, coupe au 09/10)
Chiffres rapportés tels quels, **aucune rentabilité démontrée** (archive de 21 jours) :
- Buts (avec cote ≥ 1,25) : 167 propositions, réussite 59,9 %, rendement à mise égale −12,7 %.
- Équipes (avec cote ≥ 1,25) : 902 propositions, réussite 66 %, rendement −8,1 %.
- Marché par marché, la réussite des marchés admis est proche de leur réussite de base (par exemple Pas de nul 71 % contre 74 %, Victoire domicile 50 % contre 43 %).
- Multigoals et multiscores : jugés en réussite seule, sans cote dans l'archive. Le groupe « Match nul » est admis très souvent (355 fois) à 26 %, comme sa base.

## Affichage de la page (22/10/2026)
- Carte repliée : le meilleur marché de chaque onglet (valeur, cote ou « cote à lire », alerte) est visible sans clic. Un clic sur un onglet déplie la carte.
- Carte dépliée : une ligne par marché (nom, cote, barre de valeur, branches offensive/défensive, alerte écrite). Plus de tableau : il débordait sur téléphone.
- En tête : nombre de matchs, puis bilan réel en trois pastilles (« Aucune rentabilité démontrée »). Aucun seuil dans l'affichage : la barre est proportionnelle à la valeur.
- Tests : `tests/test_alpha_affichage.py`.

## Points ouverts
- Les enjeux (légende de zones Matchendirect) ne sont pas collectés.
- Aucune norme de niveau mesurée pour les multigoals (marge d'un but par borne par défaut).
- 21 jours d'archive seulement : tout seuil reste provisoire et à recalculer à chaque ajout de jours.

## Couche de robustesse par scénarios (`alpha_serie/robustesse.py`, branche `alpha-robustesse`, 23/10/2026)
Cahier des charges figé par Patrick. Couche séparée : `coeur.py`, la page et le pipeline ne sont pas modifiés.
- Paire i : A = marqués domicile, C = encaissés extérieur, B = marqués extérieur, D = encaissés domicile. Fermé = (min(A,C), min(B,D)), habituel = (A,B), ouvert = (max(A,C), max(B,D)).
- Défavorable = pire des 4 coins ; une validation « juste au seuil » (un seul but de plus ou de moins la fait perdre) compte comme échec. Exemptés : BTTS non, cage inviolée oui, buts d'une équipe moins de 0,5.
- Tous les marchés de l'alpha + multigoals + groupes de multiscores + combos double chance × (plus 1,5/2,5/3,5, moins 2,5/3,5/4,5, BTTS oui/non). Exclus inchangés.
- Table (marché, n, v_def, v_hab) gelée dans `data/alpha_serie/robustesse_table.json` (date, empreinte des matchs) ; retenu si borne basse de Wilson 95 % >= 80 % (= 1/1,25). k supprimé.
- Stabilité : retrait de chaque paire, lecture de la table gelée (cellule n-1 ; n = 3 existe pour ce seul test).
- Réglage : Football-Data saison 2526 (10 194 matchs analysables). Validation unique : saison 2627 (3 418 matchs) et archive ARCHETYPE (862 matchs). Rapport : `docs/alpha_robustesse_validation.json`.
- Commande : `python -m alpha_serie.robustesse`. Tests : `tests/test_alpha_robustesse.py`.

### Résultat de la première validation (23/10/2026, chiffres bruts)
- 110 cellules retenues sur 5 240. Marchés qui passent : handicap +1,5 domicile, moins de 2,5 buts de l'extérieur, moins de 4,5 buts (les autres tombent au test de stabilité).
- 2627 : 950 propositions, réussite 90 % (base des mêmes marchés 85–87 %), 75 % des matchs sans aucun marché.
- Archive ARCHETYPE : 381 propositions, réussite 87,1 %, cote Betpawa moyenne 1,08–1,13, rendement −8,7 % sur 183 cotes ; seulement 8 propositions avec une cote >= 1,25 (5 gagnées).
- Constat : la barre de 80 % ne laisse passer que des marchés que Betpawa paie sous 1,25. Rien n'est branché au pipeline.

### Version 2 (23/10/2026, ordre de Patrick) : calibrage par marché et par intervalle de cote sur les matchs ARCHETYPE
- Seuil : borne basse de Wilson 95 % >= **72 %** (80 % jugé trop strict par Patrick). Priorité à la fréquence de réussite ; le rendement est publié pour information.
- Données : **tous** les matchs de l'archive de test avec historique des deux équipes, cotes BetPawa et score, **sans doublon** (match_id puis date + équipes, l'état le plus récent est gardé) : 1 766 matchs, 889 analysables (4 matchs au même lieu minimum), du 28/09 au 22/10/2026. Historique : assemblage figé, sinon le bloc équipe de l'archive.
- Lecture de la stratégie inchangée (paires, défavorable sans « juste au seuil », habituel). Stabilité : chaque part est lue après retrait de chaque paire, on garde la plus petite.
- Combos : « juste au seuil » = juste sur l'une des deux jambes, chacune avec sa propre règle (la jambe BTTS non garde son exemption).
- Règle apprise par marché (`calibrer_marche`) : part défavorable minimale, part habituelle minimale (valeurs réellement observées) et intervalle de cote (bornes = cotes observées, >= 1,25) qui gardent le plus de paris avec Wilson >= 72 % et au moins 72 % dans chaque moitié chronologique. Marchés sans cote dans l'archive (combos, multigoals, multiscores) : réussite seule.
- Quatre coins : test prouvant que, pour les marchés monotones, exiger les 4 coins = exiger le coin défavorable propre au marché (`test_quatre_coins_egal_coin_du_marche_pour_les_marches_monotones`).
- Sorties : `data/alpha_serie/robustesse_intervalles.json` (règles gelées, date, empreinte), `data/alpha_serie/robustesse_matchs.json.gz` (liste explicite des matchs), `docs/alpha_robustesse_validation.json`.
- Réglage du 23/10 (chiffres bruts) : 23 marchés reçoivent une règle. Sur tous les matchs : 1 614 paris, 81,4 % de réussite, rendement +18,8 % sur 725 cotes.
- **Contrôle chronologique** (règles apprises avant le 14/10, jugées du 14 au 22/10) : 969 paris, **70,6 %** de réussite, rendement −9 % sur 516 cotes. Les règles ne tiennent pas hors de leurs données : la plupart des intervalles reposent sur 10 à 30 paris en 25 jours. Tiennent au-dessus de 72 % hors échantillon : plus de 1,5 buts (73 %), handicap +1,5 extérieur (77 %), handicap +0,5 extérieur (72 %), moins de 2,5 buts du domicile (76 %), multigoals 1-4 (74 %, égal à sa fréquence de base). Rien n'est branché au pipeline.
- La version 1 (table Football-Data, 80 %) reste dans le code (`construire_table`, `verdict`) et dans `robustesse_table.json`, à titre de référence ; elle n'est plus utilisée par `main`.

### Version finale (24/10/2026) : protocole figé et verdict hors échantillon
- Protocole : validation chronologique répétée **jour par jour** sur les matchs ARCHETYPE (1 766 sans doublon, 889 analysables, 28/09–22/10) : pour chaque jour, les règles sont apprises sur les jours strictement antérieurs, gelées, puis appliquées à ce seul jour. Aucun seuil, intervalle ni marché n'est ajusté sur le jour évalué.
- Le juge est le résultat hors échantillon. Wilson ne sert plus qu'à l'apprentissage et figure à titre indicatif. k est conservé (champ `k`), il ne décide rien.
- Multigoals et multiscores hors de cette couche (ils gardent leur méthode propre). Combos inclus.
- Verdict par marché (`juger`) : **validé** = au moins 50 paris hors échantillon, réussite >= 72 %, >= 72 % dans chaque moitié chronologique de ses paris, au-dessus du taux de base du marché sur les mêmes jours ; **exploratoire** = moins de 50 paris ; **rejeté** = sinon. Le 50 est un minimum pratique, pas une preuve statistique.
- Résultat brut : 891 paris hors échantillon, 70,0 % de réussite. **Un seul marché validé : handicap +1,5 extérieur**, 105 paris, 80,0 % (84 gagnés, 21 perdus), 85 % puis 75 %, base 78,5 % (gain +1,5 point), cote moyenne 1,30, rendement indicatif +3,8 %, Wilson indicatif 71,4 %.
- Limite à ne pas cacher : la règle gelée de ce marché a des seuils de part défavorable et habituelle à 0. **La lecture par scénarios ne filtre rien** : la sélection vient de l'intervalle de cote 1,25–1,36. Le gain sur la base est faible et non démontré statistiquement.
- Rejetés : plus de 1,5 buts (71,9 %), pas de nul (incohérent 76 % puis 72 %), extérieur ne perd pas (70,6 %), moins de 3,5 buts (69,2 %). Tous les autres : exploratoires (moins de 50 paris).
- Fichiers : `data/alpha_serie/robustesse_intervalles.json` (règles gelées des seuls marchés validés), `docs/alpha_robustesse_validation.json` (verdicts, résultats par semaine, journal des jours), `data/alpha_serie/robustesse_matchs.json.gz` (liste des matchs). Commande : `python -m alpha_serie.robustesse`. Rien n'est branché au pipeline ni à la page.

### Correction méthodologique (24/10/2026, branche `alpha-robustesse-correction`)
Remplace le verdict de la « version finale » ci-dessus, qui reposait sur des bandes de cote apprises avec Wilson >= 72 % comme filtre obligatoire.
- **Plus de bande de cote apprise ni de Wilson obligatoire.** Deux voies fixes, séparées, chacune avec son objectif et son verdict :
  - **A — sélections robustes** : cote de 1,25 à moins de 1,39. Objectif : fréquence de réussite >= 72 %.
  - **B — occasions à cote élevée** : cote de 1,39 et plus, **sans limite haute**. Objectif : gain net à mise égale.
  - La frontière 1,39 = 1 / 0,72 : au-dessus, la cote annonce moins de 72 % de chances, l'objectif fréquence n'a plus de sens. Elle découle du seul seuil de Patrick.
  - **Sans cote** : combos seulement (aucune cote dans l'archive), jugés sur la réussite seule. Un marché simple dont la cote manque pour un match est écarté (7 343 lectures), comme les cotes sous 1,25 (4 815 lectures).
- Règle par marché et par voie, apprise sur les seuls jours antérieurs : part défavorable minimale et part habituelle minimale ; « sans filtre » est candidate. Une règle filtrée n'est retenue que si elle fait mieux que « tout prendre » dans la même voie, et que si elle remplit l'objectif de sa voie dans chaque moitié chronologique. Choix selon l'objectif (A : borne de Wilson comme mesure de fréquence fiable, B : gain net total), jamais selon le volume.
- Verdicts hors échantillon (validation jour par jour) : A validé = >= 50 paris, >= 72 %, >= 72 % dans chaque moitié, au-dessus de la sélection sans filtre de la même voie ; B « opportunité démontrée » = >= 50 paris, gain net > 0 au total et dans chaque moitié, réussite au-dessus de la probabilité implicite des cotes ; moins de 50 paris = exploratoire. Références publiées : taux de base du marché, taux sans filtre de la même voie, apport du filtre, part des paris où le filtre est actif, résultats par semaine.
- Contrôle des cotes : un match n'est gardé que si ses cotes ont été prises avant le coup d'envoi (`run.pris_le` < `coup_d_envoi_utc`) : 146 enregistrements écartés. `appliquer` ne lit jamais l'issue du match (test).
- k conservé dans chaque lecture (champ `k`), sans rôle de preuve.
- **Résultat brut** (1 670 matchs sans doublon, 851 analysés, 28/09–22/10) :
  - Voie A : 1 295 paris, 73,0 %, gain −63,8 unités. **Un seul marché validé : moins de 3,5 buts**, 74 paris, 77,0 % (57/17), contre 67,5 % sans filtre (+9,5 points), 73 % puis 81 %, filtre actif sur 93 % des paris, cotes 1,25–1,38, gain +0,49 unité, Wilson indicatif 66 %. Rejetés faute d'apport du filtre : pas de nul, plus de 1,5 buts, handicap +1,5 extérieur ; extérieur ne perd pas : incohérent (78 % puis 67 %).
  - Voie B : 1 059 paris, 48,1 %, gain −144,9 unités. **Aucune opportunité démontrée** ; 6 marchés rejetés (dont moins de 3,5 buts : gain instable), les autres exploratoires.
  - Combos : 146 paris, 57,5 %, tous exploratoires.
- Limites : un seul marché validé, sur 74 paris en 25 jours, première moitié juste au-dessus de 72 %. Ce n'est pas une preuve durable. Rien n'est branché au pipeline, aucune exécution automatique programmée.
- Tests : `tests/test_alpha_robustesse.py` (35 tests alpha) ; suite complète : 2 500 tests réussis.

### Calibrage par famille de marchés (24/10/2026, branche `alpha-robustesse-correction`)
Remplace le verdict de la correction précédente (seuil commun de 72 % en voie A, 50 paris fixes).
- **Audit** : les combos restaient exploratoires parce que (1) leurs cotes ne sont pas archivées (`parse_combines_betpawa.py` existe mais ses groupes n'atteignent pas l'archive) et (2) la règle commune « >= 72 % dans chaque moitié » de la voie sans cote les éliminait presque tous (taux naturels de 20 à 60 %). Le même seuil commun bloquait 1N2, handicaps, buts par équipe et grosses cotes.
- **Aucun taux commun** : chaque marché (ligne précise) et chaque voie apprennent leur propre marge (part défavorable, part habituelle) sur les jours antérieurs. Candidats = toutes les marges observées ; admissible si le filtre fait mieux que « tout prendre » dans chaque moitié chronologique ; retenu = meilleure borne basse à 95 % de l'apport (réussite : borne de Wilson de la sélection moins le taux sans filtre ; voie B : rendement moyen moins 1,96 erreur-type). Ni volume, ni seuil fixe.
- **Combos** : calibrage autonome sur leur **jambe la plus fragile** (parts de chaque jambe avec sa propre règle). Résultats publiés par type (côté double chance × jambe), 2 jambes.
- **Familles** séparées : totaux, buts par équipe, BTTS, 1N2, double chance, handicaps, combos, multigoals, multiscores (ces deux derniers réintégrés à l'étude ; leur règle de production n'est pas modifiée).
- **Voies** : A (1,25 à moins de 1,39), B (1,39 et plus, sans limite haute, objectif rendement), sans cote (combos, multigoals, multiscores, marchés simples sans cote pour le match) : valeur financière **non évaluable**, aucune cote inventée.
- **Statuts** (hors échantillon, jour par jour, contre la référence sans filtre du même marché et de la même voie) : rejeté (apport <= 0, ou en A / sans cote réussite pas au-dessus du taux de base) ; exploratoire (apport positif mais pas dans les deux moitiés) ; prometteur (positif dans les deux moitiés, intervalle à 95 % incluant zéro) ; validé hors échantillon (positif dans les deux moitiés et borne basse > 0). Plus de minimum fixe de 50 : l'intervalle d'incertitude décide.
- **Résultat brut** (1 670 matchs, 851 analysés, 121 couples marché × voie jugés) : 4 « validés hors échantillon », tous **sans cote** donc non évaluables financièrement : plus de 1,5 buts du domicile (78 paris, 57,7 % contre 46,2 %), plus de 2,5 buts de l'extérieur (35, 28,6 % contre 11,3 %), handicap −0,5 domicile (11, 72,7 % contre 38,6 %), combo domicile ne perd pas + moins de 3,5 buts (85, 57,6 % contre 45,6 %). Prometteurs : 21. Moins de 3,5 buts en voie A passe de « validé » à « prometteur » (58 paris, 77,6 % contre 67,5 %, intervalle incluant zéro).
- **Par famille**, réussite des paris filtrés contre réussite attendue sans filtre avec le même mélange de marchés : apport de +0,4 point (double chance) à +4,6 points (1N2). Toutes les familles avec cotes restent en gain net négatif (BTTS −8,4, 1N2 −72,5, double chance −106,2 unités).
- **Limite majeure** : 121 couples testés. Avec une borne à 95 %, quelques « validés » peuvent sortir par hasard ; 4 validés n'excluent pas ce cas. Aucune amélioration robuste et rentable n'est démontrée. Rien n'est branché.
- Commande : `python -m alpha_serie.robustesse`. Tests : `tests/test_alpha_robustesse.py` ; 36 tests alpha, suite complète 2 501 tests réussis (24/10/2026).

### Révision statistique (24/10/2026, branche `alpha-robustesse-correction`)
Corrige les défauts relevés sur `2e5f090`. Remplace ses statuts.
- **Cote manquante séparée** : un marché simple sans cote pour un match va dans la voie `cote_manquante`, jamais dans `sans_cote` (réservée aux combos, multigoals, multiscores). Les 3 marchés simples « validés » de `2e5f090` venaient de ce mélange.
- **Comparaison correcte** : la sélection étant incluse dans la référence, elle est comparée aux paris **non retenus** (groupes disjoints), par test exact (Fisher pour la réussite, permutation à graine fixe pour le rendement), valable pour les petits effectifs.
- **Période réservée** : dernier tiers des jours (14/10–22/10, 9 jours), fixé avant tout calcul, jamais utilisé pour choisir. Les règles apprises sur le développement (28/09–13/10) sont gelées puis appliquées une seule fois.
- **Faux positifs** : seuls les candidats du développement sont testés sur la réserve ; Benjamini-Hochberg à 5 % sur ces seuls tests.
- **Statuts** : rejeté, exploratoire, non confirmé (bon en développement, pas sur la réserve), prometteur (positif sur la réserve, non significatif), validé hors échantillon (significatif après correction).
- **Surajustement mesuré** (`surajustement` dans le rapport) : apport des règles sur leurs propres données contre validation jour par jour et réserve, par famille ; ex. totaux +6,9 points en apprentissage, −11,5 en validation jour par jour, +2,1 sur la réserve.
- **Cotes des combos** : aucune dans l'archive ni dans `precalcul.json` (625 matchs avec cotes BetPawa, 0 groupe combiné). `parse_combines_betpawa.py` est appelé par le scraper mais ne produit rien. Archivage impossible sans toucher la production : non fait.
- **Résultat brut** (104 couples marché × voie) : **0 validé hors échantillon**, 15 prometteurs, 2 non confirmés, 38 exploratoires, 49 rejetés. Les 4 « validés » de `2e5f090` : 2 non confirmés (plus de 1,5 buts du domicile), 2 ramenés à prometteur, dont le combo domicile ne perd pas + moins de 3,5 buts (réserve : 20 paris, 65 % contre 47 % sans filtre, p = 0,089).
- Toutes les familles avec cotes restent en gain net négatif sur la réserve, sauf BTTS (+0,7 et +0,3 unité sur 10 et 46 paris : non significatif).
- Tests : 38 tests alpha ; suite complète 2 503 tests réussis (24/10/2026).

### Campagne d'optimisation systématique (24/10/2026, `alpha_serie/campagne.py`, branche `alpha-robustesse-correction`)
Construite au-dessus de `robustesse.py` (ffb25b0), sans le modifier. Aucun autre moteur touché, rien de branché.
- **Données** : apprentissage = Football-Data saison 2526 (9 510 matchs analysables) ; validation = Football-Data 2627 avant le 28/09/2026 (3 023) ; test final = archive ARCHETYPE 28/09–22/10 (851, cotes BetPawa prises avant le coup d'envoi). Aucun recouvrement de matchs entre étapes.
- **Recherche** : pour chaque marché précis et chaque catégorie (toutes / A / B), toutes les configurations (taille minimale 4 à 7, marge défavorable, marge habituelle, valeurs observées) : **27 494 configurations évaluées**. Admissible = mieux que les paris non retenus dans chaque moitié de l'apprentissage ; retenue = la plus nette.
- **Validation** : configuration gelée appliquée telle quelle ; candidate = apport positif dans chaque moitié et significatif (tests exacts, Benjamini-Hochberg 5 %) : 64 candidates.
- **Test final** (jamais utilisé pour choisir) : Benjamini-Hochberg 5 % sur les 60 candidates ayant un apport positif.
- **Résultat** (122 couples marché × catégorie) : **22 exploitables** (18 événements distincts : 1N = handicap +0,5 domicile, victoire = handicap −0,5, etc. sont signalés `meme_evenement_que`), 38 prometteurs, 4 non confirmés, 27 écartés en validation, 59 insuffisamment documentés.
- **Tous les exploitables sont en catégorie « toutes » (objectif réussite)** : le filtre augmente la réussite de 3 à 14 points sur des matchs jamais vus (ex. extérieur ne perd pas + plus de 2,5 buts : 37,5 % contre 26,6 % ; victoire extérieur : 41,8 % contre 31,7 %).
- **Rentabilité** : aucune configuration des catégories A et B (sélection par la cote) ne passe la validation. Sur les paris exploitables qui ont une cote BetPawa, le filtre réduit souvent les pertes, mais le rendement reste négatif sauf pour 2 marchés sur peu de paris avec cote (moins de 2,5 buts de l'extérieur, handicap +1,5 domicile) : **aucune rentabilité démontrée**.
- Combos : 6 exploitables en réussite (ex. domicile ne perd pas + moins de 4,5 buts : 60,7 % contre 56,5 %, 577 paris), valeur financière non évaluable (cotes non archivées).
- Sorties : `docs/alpha_campagne.json` (une fiche par marché et catégorie : configuration, apprentissage, validation, test final, semaines, finances), `data/alpha_serie/campagne_regles.json` (configurations des exploitables et prometteurs). Commande : `python -m alpha_serie.campagne` (environ 35 s, résultat identique à chaque exécution). Tests : `tests/test_alpha_campagne.py` (numpy et scipy requis, sinon ignorés).

### Validation de la campagne (24/10/2026) : deux défauts corrigés
- **Découpage** : l'apprentissage (étiquette 2526, jusqu'au 01/06/2026) et la validation (étiquette 2627) se chevauchaient dans le temps : 1 093 matchs « 2627 » des championnats sur l'année civile (Argentine, États-Unis, Brésil, Chine, Irlande, Norvège, Suède, Finlande) étaient datés de janvier à juin 2026. Aucun identifiant commun, mais pas de séparation chronologique. Corrigé par une coupe **par date** : apprentissage avant le 01/07/2026 (début de la saison européenne 2026-27), validation du 01/07 au 27/09, test final à partir du 28/09. Preuve (`preuve_decoupage` du rapport) : apprentissage 10 524 matchs du 28/02/2025 au 28/06/2026, validation 2 009 du 03/07 au 27/09/2026, final 851 du 28/09 au 22/10/2026, 0 identifiant commun, strictement chronologique. Configurations réapprises sur la nouvelle période ; les anciennes sont gardées dans chaque fiche (`avant_2dc8e31`).
- **Faux positifs** : Benjamini-Hochberg était appliqué après une présélection sur les résultats de l'étape (apport positif). Il porte maintenant sur **toutes** les hypothèses de l'étape : 92 configurations en validation, 63 candidates au test final (p = 1 sans pari). q-valeurs publiées (`q_validation`, `q_final`).
- **Résultat** : 18 exploitables (15 événements distincts), 41 prometteurs, 4 non confirmés, 27 écartés en validation, 60 insuffisamment documentés. Sur les 22 exploitables de `2dc8e31` : 18 confirmés individuellement (q final de 0,0002 à 0,045), 4 ramenés à prometteur (plus de 2,5 buts, moins de 2,5 buts de l'extérieur, domicile ne perd pas, pas de nul + plus de 2,5 buts ; q final de 0,051 à 0,172). Aucun nouvel exploitable.
- **Rentabilité** : sur les 13 exploitables qui ont des cotes BetPawa, le rendement reste négatif dans tous les cas (de −3,2 % à −20,3 %) ; le filtre réduit les pertes pour 9 d'entre eux, les aggrave pour 3 (victoire domicile, handicap −0,5 domicile, handicap +1,5 domicile) et ne change rien pour 1 (plus de 0,5 buts du domicile). Les 5 combos exploitables restent non évaluables (cotes non archivées). **Aucune rentabilité démontrée.**
- Tests de non-régression : `tests/test_alpha_campagne.py` (14 tests ; les 4 tests des deux défauts échouent sur le code de `2dc8e31`, vérifié). Suite complète : 2 519 tests réussis. Deux exécutions successives donnent un résultat identique.

### Branchement des sélections calibrées (24/10/2026, ordre de Patrick « Branche le nouveau moteur et adapte-le au système »)
- `alpha_serie/calibrees.py` : applique en production les **seules règles exploitables** de la campagne (18 règles, `data/alpha_serie/campagne_regles.json`, gelées, jamais réapprises en production). Lecture identique à la campagne (`robustesse.parts_marche`, testée), sur les équipes figées avant le coup d'envoi. Cote minimale 1,25 (cote connue en dessous : non proposé) ; cote absente : « cote à lire » ; un même événement n'est proposé qu'une fois. Bibliothèque standard seulement (le pipeline n'a ni numpy ni scipy ; vérifié).
- `suivi.py` : quatrième onglet `calibrees` à côté de buts / équipes / multiscores, **gelé avant le coup d'envoi, réglé et compté dans le bilan** comme les trois autres. Les trois onglets existants et la méthode de `coeur.py` sont inchangés. Même étape du pipeline nocturne (`python -m alpha_serie.suivi pipeline`), toujours hors générateur de tickets.
- Page `pronostics_comportement.html` : onglet « Calibrés » ; pour chaque marché, réussite observée au test sur matchs jamais vus et réussite sans le filtre, cote BetPawa ou « à lire », mention « aucune rentabilité n'est démontrée ».
- Tests : `tests/test_alpha_calibrees.py` (10 tests : 3 cas qui passent, 4 qui échouent, même événement, échantillon et fuite, combo, gel / résultat / bilan, lecture commune, page). Suite complète : 2 531 tests réussis.

### Règle définitive d'affichage (24/10/2026, décision de Patrick) — présentation seulement
- Cinq catégories indépendantes sur la carte : **Buts, Multigoals, Équipes, Multiscores, Calibrés** (les multigoals, rangés dans l'onglet « buts » du fichier, forment leur propre catégorie). Aucun classement entre catégories : chaque catégorie garde son meilleur marché, classé par elle-même (valeur décroissante).
- Buts, Équipes, Calibrés : le meilleur marché n'est affiché que si sa **cote BetPawa est connue** ; sinon la catégorie est masquée. **Jamais de marché inférieur en remplacement.**
- Multigoals et Multiscores : affichés même sans cote (« Cote facultative »).
- Doublons retirés à l'intérieur d'une catégorie seulement. Un match n'apparaît que si au moins une catégorie est affichable. Les onglets dépliés gardent la liste complète de chaque catégorie (analyse).
- Code : `af-alpha-selection.js` (règle, testable avec node), utilisé par `archetype_comportement.js`. Aucun calcul de moteur modifié. Tests : `tests/test_alpha_affichage_categories.py`.
- Constat sur les données du 24/10 (302 matchs analysés à venir) : catégorie affichée pour Multigoals 288 fois, Multiscores 256, Équipes 86, Calibrés 72, Buts 55. Le meilleur marché de Buts, Équipes et Calibrés est souvent sans cote BetPawa (multigoal-type, handicaps, combos), d'où ces catégories souvent masquées.

- **Complément (24/10/2026, Patrick)** : aucun pronostic de Buts, Équipes ou Calibrés n'apparaît sans sa cote BetPawa, **y compris dans les onglets dépliés** (`marchesAffiches`). Si le meilleur marché d'une catégorie est sans cote, la catégorie est vide partout (aucun remplaçant). Multigoals et Multiscores : cote facultative. Vérifié sur les données du 24/10 : 1 909 marchés affichables, 0 sans cote hors multigoals / multiscores.
