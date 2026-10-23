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
