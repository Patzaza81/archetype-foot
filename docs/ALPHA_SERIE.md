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
- Marges des marchés de buts (total, par équipe, donc « les deux marquent ») : **règle des buts entiers de Patrick, demi-but de marge partout** (24/10/2026) — « plus de 1,5 » = au moins 2 buts, accepté si le total attendu atteint 2,5 ; « moins de 2,5 » = en réalité moins de 3 buts, accepté si le total attendu est au plus 2,5 (`parametres.MARGE_PLUS` = 1,0 au-dessus de la ligne, `MARGE_MOINS` = 0 sous la ligne), jamais recalculée. La marge n'est qu'un garde-fou : la fréquence de répétition (branches) décide d'abord.
- Seuils d'écart attendu (victoire, ne perd pas) : aucun plancher fixé à la main ; seulement la valeur apprise sur l'archive, 0 sinon. Multigoals : aucune distance aux bornes imposée.
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
- **Remplaçant (24/10/2026, Patrick)** : si le marché principal de Buts, Équipes ou Calibrés n'a pas de cote BetPawa, le **meilleur marché inférieur coté de la même catégorie** est retenu à sa place, et la carte le signale (« le marché principal de cette catégorie n'a pas de cote BetPawa : le marché suivant est retenu »). « Pourcentage acceptable » = marché déjà retenu par le moteur dans cette catégorie (normes de l'alpha ; Calibrés : règle exploitable validée) : aucun seuil ajouté. Toujours aucun pronostic sans cote hors multigoals / multiscores. Données du 24/10 (302 matchs) : Équipes affichée 254 fois (168 remplaçants), Calibrés 299 (227 remplaçants), Buts 55, Multigoals 288, Multiscores 256 ; 0 pronostic sans cote.

### Explications et matchs affichés (24/10/2026, Patrick)
- **Marchés exclus** : plus affichés (retirés de `pronostics.json` et de la page) ; le moteur les calcule toujours, rien n'est changé à `coeur.py`.
- **Pourquoi ce marché** : une phrase courte et factuelle sous chaque marché affiché : « Aurait gagné dans X des N matchs à domicile de [équipe] et dans Y des M matchs à l'extérieur de [adversaire] ». Compté par `suivi.explication` sur les matchs affichés (aucune généralisation ; pas de phrase si le marché n'est pas lisible).
- **Détails** : tous les matchs à domicile de l'équipe qui reçoit et tous les matchs à l'extérieur de son adversaire, avec date, adversaire et score (`suivi.historique_lieu`, mêmes équipes figées que le moteur, avant le jour du match), puis buts marqués et encaissés au total et par match sur cet échantillon (`suivi.bilan_historique`).
- Tests : `tests/test_alpha_calibrees.py`.
- **Raison de chaque pronostic (24/10/2026, Patrick)** : chaque marché affiché porte la vraie raison de sa sélection, en une phrase (`suivi.pourquoi`), tirée des seuls critères appliqués par le moteur : buts / équipes / multigoals = part des comparaisons (buts marqués, buts encaissés) au-dessus du seuil des deux côtés, plus la marge de sécurité si le marché en a une ; multiscores = nombre d'apparitions (minimum 3) ; calibrés = règle remplie, avec sa réussite sur matchs jamais vus et sans elle. Sur la carte, s'ajoute sa place : « Premier de sa catégorie » ou « Le premier de la catégorie n'a pas de cote BetPawa : celui-ci est le suivant ». Aucune phrase si une donnée manque. Vérifié : 0 pronostic affichable sans raison.
- **Langage simple (24/10/2026, Patrick : « jargon basique compréhensible par tous »)** : raisons réécrites en mots de tous les jours avec les vrais nombres (« On a comparé les 6 derniers matchs de León à domicile avec ceux de Toluca à l'extérieur : ce pari passe 6 fois sur 6 avec leurs buts marqués et 5 fois sur 6 avec leurs buts encaissés. La moyenne de buts des deux équipes le confirme. » ; multiscores : « ce type de score est sorti 4 fois sur 12 » ; calibrés : « Dans 577 matchs passés qui ressemblaient à celui-ci, ce pari a gagné 61 % du temps (contre 57 % en général) »). Retirés de l'écran : « valeur », « branches », « comparaisons », « filtre », « gelés », « rentabilité démontrée » ; remplacés par « de chances », « de réussite », « Nos vrais résultats », « aucun gain n'est garanti ». Cote absente (multigoals / multiscores) : « à vérifier ». Bandeau de la page réécrit.

### Suppression des marges fixées à la main (24/10/2026, ordre de Patrick)
- Les anciennes valeurs (ex. « plus de 1,5 buts » exigeait 3,5 buts attendus, « l'équipe marque au moins 1 but » exigeait 2,0, « moins de 4,5 » au plus 2,0) étaient des planchers proposés le 20/10 et que la calibration ne pouvait qu'élargir. Ils sont supprimés : `parametres.DEFAUT` à 0, `calibration.py` garde seulement les marges apprises.
- Recalibrage sur 940 matchs (28/09–24/10) : marges apprises — plus de 1,5 buts 1,75 ; moins de 3,5 : 0,25 ; moins de 4,5 : 2,5 ; plus de 4,5 : 0,5 (2 matchs seulement) ; équipe marque au moins 1 but : 0,5 ; équipe moins de 2,5 : 0,25 ; toutes les autres : 0. Le nul reste sans seuil appris.
- Effet sur les 338 matchs analysés à venir : catégorie Buts disponible avec cote dans 293 matchs (61 avant) ; buts par équipe avec cote dans 274 matchs (39 avant).
- Mesure sur l'archive (même période que la calibration, donc flatteuse) : beaucoup plus de paris, réussite de l'ordre de 46 à 73 % selon le marché, rendement toujours négatif pour la plupart : aucun gain démontré.
- Tests : `tests/test_alpha_serie.py` (aucun plancher imposé ; marges de production = marges apprises ; mécanisme testé avec des marges d'exemple).
- **Règle des buts entiers (24/10/2026, Patrick)** : les marges apprises des marchés de buts (ex. 1,75 pour « plus de 1,5 », 2,5 pour « moins de 4,5 ») sont abandonnées au profit d'une règle unique : 1 but d'écart avec la ligne (attendu ≥ buts nécessaires + 0,5). La calibration ne fait plus que les afficher pour information. Effet sur les 338 matchs à venir : Buts avec cote dans 200 matchs (61 avec les anciens planchers), buts par équipe avec cote dans 77 (39 avant).
- **Correction « moins de » (24/10/2026, Patrick)** : « moins de 2,5 » équivaut à « moins de 3 buts » ; avec le demi-but de marge, il est accepté jusqu'à 2,5 buts attendus (et non 1,5 comme la version précédente). Effet sur les 338 matchs à venir : Buts avec cote dans 286 matchs, buts par équipe avec cote dans 234.
- **Libellés « moins de » (24/10/2026, Patrick)** : sur la page, « Moins de 2,5 buts » s'affiche « Pas plus de 2,5 buts dans le match » ; par équipe : « [équipe] ne marque pas plus de 2,5 buts ». Moins de 0,5 : « Aucun but dans le match » / « [équipe] ne marque pas ».
- **Plaque compacte (24/10/2026, Patrick)** : carte repliée = en-tête du match + le meilleur marché **Buts** et le meilleur marché **Équipes** (une ligne courte chacun : catégorie, pari, cote) ; s'il n'y en a aucun, le **Multigoal** ; à défaut, la première catégorie disponible. Raisons, onglets et matchs des deux équipes seulement carte dépliée (la place « premier choix / suivant » passe en tête de l'onglet). **Repli et dépli au toucher n'importe où sur la plaque** ; seuls les onglets (changer de catégorie) et les liens gardent leur action. Plus de boutons « Replier » / « Détails ». Vérifié sur une simulation de la page (338 cartes) : 57 cartes repliées à 1 ligne, 280 à 2 lignes, aucune vide.

## 24/10/2026 — Cotes des combinés (double chance + plus/moins de buts, double chance + les deux marquent)

- Constat : 0 cote de combiné lue depuis le début (précalcul et archive). Le lecteur `parse_combines_betpawa.py` attendait des titres anglais alors que la page Betpawa.cm est en français.
- Correction du lecteur : titres français acceptés (« Double Chance & Plus de/Moins de | Fin de Match », « … et Les Deux Équipes Marquent … »), libellés « Plus de / Moins de », « Oui / Non », virgule décimale. Mi-temps ignorée. Cote illisible : rien n'est lu (aucune cote inventée).
- Relevé brut : `scraper_betpawa.py` écrit `diagnostic/betpawa_combines.json` (20 derniers matchs : titres et blocs bruts, groupes lus). Il sert à confirmer le titre exact utilisé par Betpawa après la prochaine collecte de nuit.
- Branchement : `calibrees.cote_combo` relie la règle (« combo », « 1N+moins_3.5 ») au groupe `dc_total_3.5` / « 1N|moins », et (« combo », « N2+btts_oui ») à `dc_btts` / « N2|Oui ». Même règle que les autres marchés : cote < 1,25 → non proposable ; sans cote → non affiché.
- Limite : tant que le relevé ne confirme pas le titre réel, l'affichage des combinés n'est pas garanti.

## 25/10/2026 — Traitement séquentiel des tickets (onglet de la page alpha, demande de Patrick)

- **Page** : `tickets_alpha.html`, reliée à la page alpha par deux onglets (« Pronostics » / « Traitement séquentiel des tickets »). Calcul dans le navigateur (`af-alpha-tickets.js`), affichage `af-alpha-tickets-vue.js`, style `af-alpha-tickets.css` (couleurs et cartes de la page alpha, mode nuit compris).
- **Source** : uniquement `data/alpha_serie/pronostics.json` déjà publié. Le meilleur marché de chaque catégorie est celui du site (`af-alpha-selection.js`). Le moteur (`alpha_serie/`), le pipeline et les données ne sont ni appelés ni modifiés ; aucun résultat passé n'entre dans la sélection.
- **Règles** (procédure de l'audit validé le 25/10/2026 ; règles de cette procédure, pas des paramètres du moteur ; constantes `REGLES`) :
  1. Buts, Équipes, Calibrés seulement (Multigoals et Multiscores exclus), meilleur marché affiché de chaque catégorie, cote ≥ 1,25.
  2. Admissible : pas un remplaçant ; valeur alpha ≥ 80 % ; confirmation sur les matchs propres des deux équipes ≥ 75 % (la plus faible) ; au moins 5 matchs comparés par équipe. Chaque marché écarté affiche sa raison.
  3. Tranches de 2 heures à partir de 10 h (heure de Douala) ; ticket de tranche = les 2 meilleurs (valeur, confirmation, matchs comparés, puis cote la plus basse par convention), un seul marché par match.
  4. Méthode A : un seul ticket validé d'avance, le premier de chaque tranche ajouté tranche après tranche.
  5. Méthode B : enchaînements où chaque ticket commence après la fin estimée du précédent (dernier coup d'envoi + 115 min) et 15 min de règlement ; seuls les matchs de la tranche qui respectent ce délai sont gardés ; marge < 30 min signalée « marge courte ». Montants « tout réinvestir » et « prudent » (mise de départ mise de côté après le premier gain), avec, à chaque étape, ce qui reste si l'étape perd.
- **Mise** : simulée, réglable (100, 500, 1 000 ou libre), mémorisée sur le téléphone. Rien n'est joué depuis le site ; aucun taux de réussite n'est présenté comme une probabilité ; « aucun gain n'est garanti ».
- **Vérifié** sur les données du 25/10 : mêmes tickets et mêmes montants que l'audit validé (méthode A 5,3979 ; B1 4,3613, 2 180,64 / prudent 1 003,22).
- Tests : `tests/test_alpha_tickets_sequentiels.py` (admis et écartés, ex æquo, un pari par match, cotes, faisabilité des horaires, montants).
- **Vue simple (25/10/2026, Patrick : « un utilisateur qui n'a jamais entendu parler de ça doit comprendre »)** : la page s'ouvre sur « Le ticket du jour » (le ticket progressif de la méthode A) : les matchs dans l'ordre avec l'heure, le pari en mots simples et son nom sur Betpawa ; choix du nombre de matchs (de 1 au maximum, avec le multiplicateur de chacun) ; « Tu mises → Si tout passe, tu reçois » ; « Si un seul de ces matchs rate, tu perds ta mise ». Les tranches, enchaînements et règles sont repliés sous « Pour les connaisseurs ». Aucun calcul modifié.
- **Paramètres visibles et ticket plus long (25/10/2026, Patrick)** : sous chaque match du ticket du jour : chances selon le moteur, nombre de matchs comparés, nombre de matchs des deux équipes où le pari serait passé, points par match au classement. Le choix du nombre de matchs va au-delà du premier de chaque créneau : les deuxièmes meilleurs de chaque créneau s'ajoutent ensuite (`ticketLong`), avec le multiplicateur affiché (25/10 : ×5,40 avec 6 matchs, ×14,60 avec 10). Rappel écrit : plus de matchs = gain plus grand mais beaucoup plus de risques.

## 25/10/2026 — Cotes des combinés : disposition réelle de la page

- Le relevé de la collecte de nuit (`diagnostic/betpawa_combines.json`, 20 matchs) montre que la page lue est en anglais (« Double Chance and Over/Under | Full Time », « Double Chance and Both Teams To Score | Full Time », « 1X2 and … ») et que chaque cote est précédée de son étiquette répétée, une fois par colonne. Aucune des lectures précédentes ne comprenait cette disposition : 0 combiné lu.
- `parse_combines_betpawa.py` la lit maintenant : 17 relevés sur 17 qui contiennent des combinés (les 3 autres matchs n'en proposent pas). Colonne incomplète ou cote illisible : la ligne est ignorée.
- Effet : à partir de la prochaine collecte, les groupes `dc_total_X`, `dc_btts`, `1x2_total_X`, `1x2_btts` sont remplis et les combinés calibrés reçoivent leur cote (`calibrees.cote_combo`).

## 25/10/2026 — Moteur de tickets finalisé : palier 2, gel et suivi chaque nuit

- **Palier 2** (`alpha_serie/palier2.py`) : « l'équipe à domicile ne marque pas plus de 2 buts » (total de buts du domicile, moins de 2,5) quand la probabilité estimée × cote BetPawa − 1 > 0,10. Probabilité : loi de Poisson sur λ = (buts marqués à domicile de l'équipe qui reçoit + buts encaissés à l'extérieur de l'adversaire) / 2, sur leurs 10 derniers matchs au même lieu (au moins 5 chacun). Origine : étude du 25/10/2026 sur 802 matchs ARCHETYPE avec cotes BetPawa (53 paris, 77 % gagnés, +20 % ; +17 % sur la période récente). « Les deux équipes ne marquent pas » n'est pas retenu (retombé à 0 % sur la période récente). Ajouté à chaque match analysé de `pronostics.json` (`palier2`) ; affiché sous le ticket du jour comme « Palier 2 — en test » (renommé « Palier 3 — en test » le même jour, voir plus bas), avec les chiffres qui le justifient.
- **Gel et suivi** (`alpha_serie/tickets.py`) : les mêmes règles que la page, en Python (un test vérifie que la page et le pipeline choisissent exactement les mêmes paris). Chaque nuit, `suivi.pipeline` gèle les tickets du jour (Douala) avant le premier match — ticket du jour, ticket long, palier 2 — dans `data/alpha_serie/tickets_journal.jsonl` (ajout seul, jamais regelé, jamais a posteriori), les règle quand tous leurs matchs ont un score, et publie le bilan (`bilan_tickets`) en tête de l'onglet : tickets gagnés, matchs gagnés, rendement par ticket.
- Le moteur alpha (`coeur.py`), ses onglets et son journal ne changent pas.
- Tests : `tests/test_alpha_tickets_suivi.py`.

## 25/10/2026 — Palier 2 = les 10 meilleurs pronostics restants (demande de Patrick)

- **Palier 1** (inchangé) : le premier pari de chaque tranche de 2 heures, de 10 h à minuit.
- **Palier 2** : les `PALIER2_MAX` = 10 meilleurs pronostics admissibles RESTANTS de la journée (10 h – minuit), hors matchs du palier 1, un seul pari par match, mêmes règles d'admissibilité et même classement que le palier 1 (valeur, confirmation, matchs comparés, cote la plus basse, heure, identifiant). S'il reste moins de 10 admissibles, le palier en compte moins : aucune règle n'est assouplie pour le remplir.
- **Palier 3 — en test** : l'ancien « palier 2 » (`alpha_serie/palier2.py`, domicile ≤ 2 buts). Le champ `palier2` de chaque match de `pronostics.json` garde son nom (compatibilité) ; il alimente le palier 3.
- Généré chaque nuit sans intervention : `af-alpha-tickets.js` (`palier2(cands, palier1)`) pour la page, `tickets.palier_2` pour le gel ; un test vérifie que les deux choisissent les mêmes paris aux paliers 1 et 2.
- Journal : clés `palier1`, `palier2`, `palier3` (l'ancien `palier1_long` disparaît, le ticket long reste visible dans les détails de la page). Le gel du 25/10/2026, fait à 01:59 UTC dans l'ancienne structure, a été effacé et refait à 02:07 UTC (03:07 à Douala, avant le premier match de 13:00) : aucun match n'avait commencé, le palier 1 est identique.
- Le 25/10/2026 : palier 1 = 6 matchs, palier 2 = 9 (seulement 9 restants admissibles), palier 3 = 4.
- Tests : `tests/test_alpha_tickets_suivi.py` (`test_palier2_dix_meilleurs_restants`, `test_meme_ticket_que_la_page`).
- Gel du soir (25/10/2026) : le pipeline démarre à 21:00 UTC (22 h à Douala). Après 22 h (début du dernier créneau, `FIN − PAS`), `tickets.geler` gèle le lendemain ; avant, le jour courant. Sans cela, un passage terminé avant minuit ne gelait rien (tous les matchs du jour avaient commencé). Test : `test_gel_du_lendemain_si_le_pipeline_finit_avant_minuit`.

## 25/10/2026 — Page d'accueil : 3 tickets du moteur alpha (demande de Patrick)

- Les tickets de l'ancien générateur (`data/tickets.json`) ne sont plus affichés sur l'accueil. Le générateur, `tickets.html` et la validation Netlify ne changent pas.
- L'accueil affiche 3 tickets de 10 matchs au plus, un par famille de pari (`tickets.famille`, d'après la clé du pari) :
  - **Résultat** : double chance, handicap, 1N2, combinés résultat + buts.
  - **Peu de buts** : moins de…, les deux ne marquent pas, cages inviolées.
  - **Buts** : plus de…, les deux marquent, une équipe encaisse.
  Une clé inconnue n'est rangée nulle part.
- Mêmes règles que le palier 1, de 10 h à minuit. Les paris sont pris dans l'ordre du classement ; un match n'apparaît qu'une fois sur les trois tickets, dans la famille de son meilleur pari, ou de son pari admissible suivant si cette famille a déjà 10 matchs. Moins de 10 admissibles → le ticket en a moins : rien n'est assoupli.
- Gel et suivi : clés `accueil_resultat`, `accueil_peu_de_buts`, `accueil_buts` du journal des tickets, avec le même gel et le même bilan que les paliers.
- Fichier de l'accueil : `data/alpha_serie/tickets_accueil.json`, écrit par `suivi.pipeline` (`tickets.ecrire_accueil`). Il affiche le ticket GELÉ du jour cible quand il existe, sinon le calcul du moment, marqué `gele: false`.
- Le gel du 25/10/2026 a été refait une seconde fois à 02:29 UTC (03:29 à Douala, avant le premier match de 13:00) pour y ajouter les 3 tickets ; les paliers 1, 2 et 3 sont identiques.
- Le 25/10/2026 : Résultat 7 matchs, Peu de buts 6, Buts 2. Avec les données complètes du 24/10, on aurait eu 3, 10 et 10.
- Tests : `test_famille_des_paris`, `test_trois_tickets_accueil`, `test_accueil_affiche_le_gel`.

## 25/10/2026 — Accueil : tickets rangés par classement au lieu du type de pari (remarque de Patrick)

- Ce qui remplace le découpage par famille : ranger des matchs de championnats et de contextes différents par type de pari n'a pas de sens (remarque de Patrick). Le découpage par famille (Résultat / Peu de buts / Buts) est abandonné le jour même.
- Les paris admissibles de la journée (mêmes règles que le palier 1, de 10 h à minuit, un pari par match) sont rangés dans l'ordre du classement du moteur, puis coupés en tickets :
  - ticket 1 = rangs 1 à 10 ;
  - ticket 2 = rangs 11 à 20 ;
  - ticket 3 = rangs 21 à 30.
- Les clés du journal sont `accueil_1`, `accueil_2`, `accueil_3`. Moins de 30 admissibles → les derniers tickets en comptent moins ; rien n'est assoupli.
- Le gel du 25/10/2026 a été refait une troisième fois, à 02:35 UTC (03:35 à Douala, avant le premier match de 13:00) ; les paliers 1, 2 et 3 sont identiques. Résultat du 25/10 : 10, 5 et 0 matchs.
- Tests : `test_trois_tickets_accueil_par_classement`, `test_accueil_jamais_force`, `test_accueil_affiche_le_gel`.

## 25/10/2026 — Accueil : ticket recommandé, cote 5 maximum (règle de Patrick)

- Les paris du classement de l'accueil sont pris dans l'ordre tant que la cote totale reste ≤ `COTE_RECOMMANDEE_MAX` = 5. On s'arrête au premier pari qui la ferait dépasser : on ne saute jamais un pari mieux classé pour en prendre un moins bien classé à plus petite cote.
- Le ticket est affiché en tête de l'accueil, encadré, et sélectionné par défaut dans « Détails du ticket ».
- Il est gelé et suivi sous la clé `accueil_recommande` du journal des tickets.
- Le gel du 25/10/2026 a été refait une quatrième fois, à 02:43 UTC (03:43 à Douala, avant le premier match de 13:00) ; tout ce qui était déjà gelé est identique.
- Le 25/10/2026 : 6 matchs, cote 4,67.
- Tests : `test_ticket_recommande_cote_5_maximum`, `test_ticket_recommande_ne_depasse_jamais_ni_ne_saute`.

## 26/10/2026 — « Plus de 1,5 buts » à chances maximales : entre tout seul dans le ticket du jour et se reconnaît (demande de Patrick)

- **Règle** (`data/alpha_serie/plus15_chances_max.json`, gelée) : le « Plus de 1,5 buts » proposé par alpha dont le **total attendu** (`niveaux.total`, déjà publié) atteint **3,4**, avec une cote BetPawa connue ≥ 1,25 (voir « Essai à 1,22 retiré » ci-dessous). Pas de cote : rien n'est proposé. Le calcul d'alpha (`coeur.py`) n'est ni appelé ni modifié ; seule la lecture des tickets change.
- **Palier fixé par les données, pas à la main** : plus petit palier du total attendu dont la borne basse de Wilson 95 % est ≥ 1/1,25 = 0,80 à la fois sur la période de réglage (avant le 01/04/2026 : 83,3 %, 836 matchs, borne 80,6 %) et sur la période de contrôle (après : 84,2 %, 872 matchs, borne 81,6 %). Rejeu du code alpha sur 14 161 matchs analysés (Football-Data 2025-2026 + archive ARCHETYPE). Tous matchs : 83,7 % (1 708 matchs) contre 76,4 % pour l'ensemble des matchs analysés.
- **Comportement** : ce pari devient candidat PRIORITAIRE (`chances_max`, catégorie `plus15`) : il passe devant tous les autres dans le palier 1 (le ticket du jour), le palier 2, les tickets de l'accueil et le ticket recommandé, toujours un pari par match (il prime sur le meilleur autre pari du même match). Aucun autre seuil (valeur, confirmation) ne lui est imposé : c'est le total attendu qui décide. Les autres règles (10 h – minuit, un match une fois) restent.
- **Reconnaissable** : repère jaune souligné « ★ Chances maximales » sur la page des tickets (ticket du jour, paliers, détail) avec une phrase en mots simples, et sur l'accueil (`index.html`) ; le repère suit le pari dans le journal gelé (`chances_max`, `total_attendu`).
- **Suivi réel** : `bilan_tickets.plus15_max` = paris gelés avant leur match, gagnés / joués, un match compté une fois ; à comparer aux 84 % du rejeu.
- **Page et pipeline** : mêmes choix (`af-alpha-tickets.js` et `alpha_serie/tickets.py`) ; un test vérifie l'égalité du palier entre le fichier, le Python et le JavaScript, et que la page et le pipeline retiennent les mêmes paris, y compris avec ces paris prioritaires. Vérifié sur les données du 25 au 29/10 : parité vraie chaque jour.
- **Constat** : sur les données du 25 au 29/10, 52 matchs ont un total attendu ≥ 3,4 mais alpha ne propose le « Plus de 1,5 » que pour 11, dont 5 avec une cote connue. La règle n'agit que sur ce qu'alpha propose.
- Tests : `test_palier_gele_identique_partout`, `test_plus15_max_entre_dans_tous_les_tickets_et_est_marque`, `test_plus15_max_prioritaire_sur_le_meilleur_pari_du_meme_match`, `test_plus15_max_ecarte_si_sous_le_palier_sans_cote_ou_hors_horaire`, `test_plus15_max_gele_regle_et_suivi`, `test_plus15_max_meme_ticket_que_la_page`. Suite complète : 2 615 tests réussis.

### Essai à 1,22 retiré : le « Plus de 1,5 » reste à 1,25 (décision de Patrick, 26/10/2026)
- L'essai (minimum 1,22 pour ce seul marché) est retiré : `COTE_MIN_PLUS15` et `cote_min_du` n'existent plus ; tous les marchés sont à `COTE_MIN = 1.25` (`coeur.choisir`, `tickets.py`, `af-alpha-tickets.js`, `plus15_chances_max.json`). Les multiscores restent sans limite.
- Pourquoi : sur 190 « Plus de 1,5 » ★ avec cote connue (29/09 → 25/10), les cotes 1,22–1,249 ne réussissent que 4 sur 11 (36 %), les cotes 1,25–1,30 réussissent 11 sur 11 ; jouables à partir de 1,25 : 13 sur 16 (81 %), à partir de 1,22 : 17 sur 27 (63 %). Échantillons très petits.
- Tests : `test_cote_minimale_1_25_aussi_pour_plus_de_1_5`, `test_plus15_cote_minimale_1_25_comme_les_autres`.

## 26/10/2026 — Validation des bandes de cotes 1X2 (victoire domicile / extérieur), règles candidates NON intégrées

- **Origine** : étude comparative du 26/10/2026 (rejeu sur 14 161 matchs, découpage chronologique, période réservée depuis le 01/04/2026). Seule la fenêtre BetPawa du 28/09 au 25/10/2026 (1 229 matchs) a des cotes BetPawa ; avant, seul Pinnacle (substitut, jamais mélangé). Constats : un minimum de cote seul (1,33 / 1,38) fait **baisser** la réussite ; ce sont des **bandes** qui ressortent ; dans ces bandes le filtre de probabilité n'apporte rien de démontré.
- **Règles figées** (`data/alpha_serie/bandes_1x2.json`, bornes incluses, aucun filtre de probabilité) : victoire domicile avec cote BetPawa de 1,33 à 1,50 ; victoire extérieur avec cote BetPawa de 1,38 à 1,70.
- **Suivi** (`alpha_serie/suivi.py`, journal existant `journal.jsonl`, aucun nouveau module) : chaque nuit, `geler_bandes` gèle TOUS les matchs admissibles (pertes comprises) avant leur coup d'envoi, avec la cote figée ; jamais regelé, jamais a posteriori, un enregistrement par (match, règle). `resultats_bandes` ajoute le résultat réel. `bilan_bandes` écrit `data/alpha_serie/validation_bandes_1x2.json` : par règle, matchs, gagnés, perdus, taux, borne basse de Wilson à 95 %, résultats par semaine ISO, part des matchs analysés par Alpha, et contrôles (doublons, gels non antérieurs au coup d'envoi, résultats sans gel, cotes hors bande : tous doivent valoir 0).
- **Aucun effet** sur les pronostics, les tickets, le moteur (`coeur.py`) ni l'affichage du site. Les lignes `bande` / `resultat_bande` sont ignorées par `geler`, `resultats` et `bilan` (types différents). Le gel démarre à la première nuit après la fusion : la fenêtre de l'étude n'est pas rattrapée (elle est déjà connue, ce n'est pas une validation) ; ses chiffres, bornes incluses, sont dans `bandes_1x2.json` (`reference_etude` : domicile 171 matchs dont 125 gagnés, extérieur 161 dont 107 gagnés, tous matchs de la bande).
- **Décision** : attendre plusieurs semaines gelées indépendantes, puis examiner le taux cumulé, sa borne basse de Wilson et la stabilité hebdomadaire. 7 réussites sur 10 = cible à confirmer, pas une garantie. Aucune intégration à Alpha avant.
- Tests : `tests/test_alpha_bandes_1x2.py` (bornes incluses 3 cas dans la bande et 3 hors bande par règle, pas de doublon, pas de gel après le coup d'envoi, pertes comprises, Wilson, semaines, journal alpha inchangé, appel réel dans `pipeline`).

## 26/10/2026 — Onglet « Indice Alpha » (demande de Patrick) : consultation et gestion des indices de réussite

- **Où** : sous-onglet de « Moteur alpha » (Pronostics, Traitement séquentiel des tickets, **Indice Alpha**), page `indice_alpha.html` (+ `af-indice-alpha.js`, `af-indice-alpha.css`), lien sur l'accueil et dans le pied de page. La page ne calcule rien : elle affiche `data/alpha_serie/indice_alpha.json`.
- **Données** (`alpha_serie/indice_alpha.py`, appelé en fin de `suivi.pipeline`, après le gel des tickets et des bandes ; une erreur est écrite dans le résultat du pipeline et ne bloque rien d'autre) : lit seulement les journaux gelés (`journal.jsonl` pour les bandes 1X2 de la PR #115, `tickets_journal.jsonl` pour le « Plus de 1,5 » à chances maximales). Aucun moteur, pronostic ni ticket n'est modifié.
- **Trois vues** : *Indice total* (paris DISTINCTS réglés : un couple match + indice compté une fois, pourcentages jamais additionnés, matchs à plusieurs indices signalés, indices classés par borne basse de Wilson 95 %, indices en baisse repérés), *Par marché* (conditions, seuils réels, évalués / gagnés / perdus, taux, borne basse, fréquence par jour, résultats par semaine et cumulés, étude historique présentée À PART du suivi réel, contrôles doublons / gel), *Gestion* (règles actives, seuils, statut, empreinte, historique des modifications).
- **Registre** (`data/alpha_serie/indices_registre.json`) : un indice = une entrée indépendante (id, marché, statut `en_etude` / `en_validation` / `valide`, source, conditions, objectif de réussite, historique). Les SEUILS ne sont pas recopiés : ils sont lus dans les fichiers que le suivi utilise vraiment (`bandes_1x2.json`, `plus15_chances_max.json`). Chaque entrée porte l'empreinte de ce qui la définit ; si une règle, un seuil ou un statut change sans nouvelle ligne d'historique (avec `python -m alpha_serie.indice_alpha --empreinte <id>`), la page affiche une alerte. Changer un indice ne change jamais le rapport des autres (test).
- **Fiabilité** : « fiable » seulement si le statut est « validé » ET que la borne basse réelle atteint l'objectif de l'indice (70 % pour les deux bandes 1X2, 80 % pour le « Plus de 1,5 ») ; sinon « pas encore fiable » ou « à confirmer ». Les trois indices démarrent « en validation ». Tendance : « en baisse » seulement si la dernière semaine passe sous la borne basse du cumul précédent (aucun seuil posé à la main).
- **Limite connue** : le suivi réel du « Plus de 1,5 » ne compte que les paris entrés dans un ticket gelé (cote connue, créneau 10 h – minuit). Au 26/10/2026 : 0 pari réglé, la page l'affiche tel quel. L'indice normal / maximal de la PR #114, s'il est fusionné, s'ajoute par une nouvelle entrée du registre.
- Tests : `tests/test_indice_alpha.py` (calculs, regroupement par marché, doublons, traçabilité et indépendance, suivi nocturne, navigation, CSS mobile, rendu de la page sous node avec échappement du texte). Rendu vérifié à 414 px : aucun débordement horizontal.

## 26/10/2026 — Sélection provisoire : 8 marchés sur la page « Sélection » (demande de Patrick)

- **Origine** : sélection provisoire du 26/10/2026 (commit 576577e, branche `etude-marches-rigueur`, `docs/SELECTION_PROVISOIRE.md`). Rien n'est validé : les taux passés ne garantissent ni la réussite ni la rentabilité.
- **Règles gelées** (`data/alpha_serie/selection_provisoire.json`) : Multigoals 1-4, Double chance 12, Plus de 1,5, Handicap +1,5 domicile, Moins de 4,5, Domicile plus de 0,5 (équivalent : cage inviolée extérieur « non »), Extérieur moins de 2,5 — niveau **normal** ; Domicile moins de 2,5 — niveau **maximal** (au plus 1 match passé où l'événement a échoué dans les paires publiées : match de l'équipe qui reçoit = (offensif[0], défensif[1]), match de l'équipe qui se déplace = (défensif[0], offensif[1])).
- **Application** (`alpha_serie/selection_provisoire.py`) : lit les marchés ADMIS par `coeur.analyser_match` (aucun calcul d'alpha modifié) ; cote BetPawa figée au run nocturne (archive), première trouvée dans l'ordre des clés équivalentes, ≥ 1,25 exigée ; Multigoals sans cote. Pas de cote : rien n'est affiché. Les autres marchés n'entrent jamais dans cette sélection.
- **Suivi** : chaque nuit (`suivi.pipeline`, bloc isolé : une erreur ne bloque rien), gel AVANT le coup d'envoi dans `data/alpha_serie/selection_provisoire_journal.jsonl` (jamais regelé, défaites comprises), résultat réel, réussite et rendement SÉPARÉS par marché (rendement seulement avec une cote figée). Page : `data/alpha_serie/selection_provisoire_page.json`.
- **Site** : page `selection_alpha.html` (+ `af-selection-alpha.js`, `af-selection-alpha.css`), sous-onglet « Sélection » ajouté aux pages du moteur alpha (barre de sous-onglets en 2 × 2 sur téléphone). Vues « Pronostics » (par jour : heure, compétition, match, marché, cote ou « sans cote BetPawa », niveau, résultat) et « Suivi réel » (par marché, étude historique présentée à part).
- **Vérifié** : rejeu du module sur la fenêtre BetPawa 28/09–25/10 = mêmes pronostics que l'étude pour les 8 marchés (849/1 099, 565/773, 146/191, 113/156, 96/134, 72/97, 65/84, 34/46).
- Tests : `tests/test_alpha_selection_provisoire.py`.

## 28/10/2026 — Solidité des marchés (affichage, ordre de Patrick)
- **Principe** (même méthode que la Solidité d'omega, voir `docs/MOTEUR_OMEGA.md`) : sous chaque marché affiché (buts, équipes, multigoals, multiscores, calibrés, combos), un pourcentage « Solidité » qui croise, pour le MÊME TYPE DE MARCHÉ,
  la fréquence de passage du pari et les écarts de buts (distance au basculement du score) sur les matchs au même lieu affichés sur la carte (tous les matchs à domicile de l'équipe qui reçoit et tous ceux de son adversaire à l'extérieur, avant le jour du match ; moyenne des deux équipes).
- **Code** : `alpha_serie/solidite.py` (poids appris sur l'archive, 81 types de marché lus par `suivi._gagne`, écrits dans `docs/alpha_solidite.json` à chaque passage de `suivi.pipeline`), `suivi._solidite` (champ `solidite` ajouté à chaque marché des onglets de `pronostics.json`, seulement si calculable),
  `archetype_comportement.js` (`solidite()`, carte repliée et dépliée), `af-comportement.css`. Les fonctions mathématiques communes (distance au basculement, régression) viennent de `moteur_omega/indice.py` et `moteur_omega/solidite.py`.
- **Aucun effet sur le moteur** : `coeur.py`, les sélections, le classement des marchés, les tickets, le journal gelé et les règles sacrées de la méthodologie sont inchangés. N'utilise ni la cote ni la valeur de l'alpha. Marché non appris, moins de 4 matchs d'une équipe ou pas de poids : aucun pourcentage.
- **Vérifié hors échantillon** (poids appris sur les premiers 60 % des jours, test sur les 74 844 marchés suivants) : perte 0,5819 contre 0,6071 (type de marché seul) et 0,6223 (fréquence brute) ; écart moyen de calibrage par marché 1,7 point (max 4,8) ; tranches de solidité 18 / 31 / 44 / 59 / 80 % = réussite 17 / 31 / 45 / 59 / 80 %. Les 49 types de marché publiés ont un pourcentage.
- Tests : `tests/test_alpha_solidite.py`.
- **Onglet « Sélection »** (28/10/2026, Patrick) : chaque pronostic de la sélection affiche aussi sa Solidité (`selection_provisoire._solidite_pronostic`, appelée par `page(matchs=…, solidite=…)`). Calcul à la lecture sur les matchs affichés des deux équipes avec le marché de la règle (`regle` = « groupe|sélection »),
  mêmes poids que la page Pronostics. Affichage seulement : jamais écrite dans `selection_provisoire_journal.jsonl`, aucun pronostic ni règle modifié, rien si le match, les poids ou les matchs des équipes manquent. Sur les données du 28/10 : 350 pronostics sur 351 ont un pourcentage. Le pipeline en cours n'est pas relancé : l'affichage s'applique au passage suivant.

- **Affichage de la Solidité (28/10/2026, Patrick)** : pastille jaune du logo (#C49A3A), bien visible (libellé 14 px, pourcentage 20 px), remplie à hauteur du pourcentage (`--s`), identique sur Omega, alpha (ligne dépliée et plaque repliée) et l'onglet Sélection ; placée sous le nom du marché, cote à droite comme sur Omega. Correctif : dans la ligne dépliée d'alpha, l'ajout de la Solidité décalait la grille (nom écrasé en colonne) ; `.ax-mk-sol` est maintenant placé en colonne 1, ligne 2, et `.ax-resume-texte` occupe toute la largeur. Aucune couleur par seuil : le remplissage suit le pourcentage.
  Omega : l'anneau du pourcentage du modèle n'apparaît que carte dépliée (une seule valeur au premier coup d'œil : la Solidité, en jaune du logo) ; sur alpha, le « % de chances » n'est déjà visible que carte dépliée.
