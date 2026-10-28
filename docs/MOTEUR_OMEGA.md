# Moteur omega (`moteur_omega/`)

Dernier moteur décidé par Patrick (27/10/2026, « mon dernier moteur avant deux mois »). Cahier des charges : quatre croisements,
scénario contradictoire par marché, Poisson/Dixon-Coles, sélection, traçabilité. Calibré sur les expériences des moteurs précédents.
Autonome : n'utilise ni V2, ni V3, ni le Journal, ni l'alpha, ni Europe, ni v2r, ni v. Hors générateur de tickets.

## Quatre rôles séparés
1. **Croisements** (`coeur.croisements`) : attaque dom × attaque ext, défense dom × défense ext (descriptifs), attaque dom × défense ext,
   attaque ext × défense dom (servent aux buts attendus). Valeurs, moyennes, extrêmes, dispersion, convergence.
2. **Scénario contradictoire** (`coeur.scenario_contradictoire`) — règle de Patrick :
   - valeurs prises dans les échantillons réels des deux équipes (rien d'inventé) ;
   - buts candidats d'une équipe = (ses buts marqués + buts encaissés par l'adversaire) / 2, avec les extrêmes défavorables au marché
     (Plus de 1,5 : attaque la plus faible × défense adverse la plus solide pour chaque équipe ; Moins de 2,5 : attaque la plus forte ×
     défense adverse la plus faible ; victoire : défavorable à l'équipe soutenue, favorable à l'adversaire ; nul et « pas de nul » : les 4 combinaisons) ;
   - **buts entiers** : « Plus de 1,5 » est l'affichage, la valeur réelle est « au moins 2 buts ». Une valeur non entière (1,5) peut valoir 1 ou 2 :
     le marché ne résiste que si tous les scores entiers possibles le font gagner (`marches.tient_en_buts_entiers`) ;
   - statut RESISTE / FRAGILE (INDETERMINE impossible : un match sans 4 matchs au même lieu est exclu avant). C'est un test, pas une probabilité.
3. **Poisson / Dixon-Coles** (`modele.py`) : buts attendus selon la méthode de Patrick (croisements 3 et 4), rapprochés de la moyenne du championnat
   selon la taille d'échantillon ; correction ρ ; distribution 0..10 renormalisée ; marchés par agrégation exacte ; calibrage isotone par marché.
4. **Sélection** (`coeur.retenu`, `coeur.selectionner`) : cote BetPawa connue **≥ 1,39, jamais moins** (ordre de Patrick du 27/10/2026) ;
   probabilité du modèle ≥ seuil ; **accord avec la cote** : la probabilité annoncée par BetPawa (marge retirée en normalisant les issues du
   marché) atteint aussi le seuil. Seuil APPRIS sur le développement de l'archive : **62 %** (72 % est impossible à 1,39 et plus : une cote de
   1,39 annonce au plus ~66 % une fois la marge retirée). Probabilité affichée
   (« réussite attendue ») = la plus prudente des deux. Principal = le plus probable ; « autres » = le reste ; jamais deux fois le même événement
   (même ensemble de scores gagnants, ex. handicap +0,5 = ne perd pas). Aucun marché ne passe : aucun pari (on ne force jamais).

## Données
- Séries au même lieu, saison en cours, même compétition, strictement avant le jour du match ; minimum 4 matchs (règle de Patrick).
- Réglage : bloc Football-Data (`data/bloc_saisons/`), historiques reconstitués par saison ET division (aucune donnée de la saison passée).
- Validation finale et production : archive ARCHETYPE (`data/archive_test/`), cotes prises avant le coup d'envoi (sinon match écarté).

## Marchés
1X2, double chance, plus/moins 1,5 à 4,5, les deux marquent, buts d'une équipe 0,5 à 2,5, cages inviolées, handicaps ±0,5 et ±1,5,
combinés BetPawa (double chance ou 1X2 + total 1,5 à 4,5, + les deux marquent). Exclus (décisions déjà prises) : score exact, nombre exact
de buts, 5,5 et plus, handicaps de 2,5 et plus, pair/impair, mi-temps, corners, cartons.

## Calibrage (`python -m moteur_omega.calibrage`) — protocole fixé avant calcul
Leçon des moteurs précédents : des réglages appris sur 3 semaines d'archive ne tenaient pas hors échantillon. Donc :
1. **Réglage sur Football-Data 2025-26** (9 510 matchs analysables) : fenêtre et forme choisies sur les 30 % les plus récents après
   ajustement sur les 70 % plus anciens ; rapprochement et ρ au maximum de vraisemblance ; calibrage isotone par marché.
2. **Validation sur Football-Data 2026-27** (1 617 matchs, jamais utilisés pour régler) : qualité des probabilités ; décision sur les filtres
   de résistance et de stabilité (gardés seulement si la réussite dépasse la probabilité, test de Welch, p < 0,05).
3. **Archive ARCHETYPE coupée au 14/10/2026** : développement (avant) pour apprendre le seuil (meilleure borne basse de Wilson à 95 % de la
   réussite des paris principaux, seuils candidats 50 à 75 %, au moins 30 paris) et décider l'accord avec la cote ; réserve (à partir du 14/10) = test final.
Sorties : `moteur_omega/parametres.json`, `docs/omega_validation.json`.

## Version 1.1.0 (27/10/2026) : cotes de 1,39 et plus seulement (ordre de Patrick)
- Seuil appris : 62 % (développement : 250 paris, 65,6 %, borne de Wilson 59,5 % ; les autres seuils font moins bien).
- Accord avec la cote à 1,39 et plus : indispensable (développement : +13,9 points sur la probabilité du modèle ; réserve : +8,2 points).
  Sans accord, réserve : 63,5 % et rendement −7,5 %.
- Recherche faite pour trouver mieux à 1,39 et plus (écart modèle − cote, « valeur » du modèle, résistance, convergence, familles, tranches
  de cotes) : aucun levier ne bat la cote ; la réussite suit la probabilité annoncée par BetPawa (1,39–1,50 : ~64–65 % ; 1,50–1,70 : ~58 %).
- **Test final (réserve, 851 matchs du 14 au 27/10)** : 557 paris principaux, **67,7 % réussis pour 64,8 % annoncés**, cote moyenne 1,42,
  rendement −3,7 %. Tous les paris retenus : 832, 66,6 %, rendement −4,7 %. Cotes proposées en pratique : 1,39 à ~1,55.
- Résistance et stabilité : toujours sans apport (2026-27 : −2,3 points, p = 0,015 ; +1,6 point, p = 0,077), affichées pour information.

## Résultats du calibrage de la version 1.0.0 (27/10/2026, cotes ≥ 1,25, seuil 72 % — remplacée par la 1.1.0)
- Fenêtre retenue : **toute la saison au même lieu** (meilleure que 5, 6, 7, 8 et 10 matchs). Forme retenue : **la moyenne de Patrick**
  (meilleure que la forme multiplicative). Rapprochement : 3,9 pseudo-matchs ; moyenne du championnat ≈ moyenne générale (les moyennes
  par championnat en cours de saison n'apportent rien) ; ρ = −0,043. Pondération des matchs récents testée : gain négligeable, non gardée.
- Le modèle bat le taux de base et la constante (vraisemblance −2,934 contre −2,982), il est bien calibré sur l'ensemble des marchés
  (2026-27 et archive), **mais il est moins précis que la cote** (Brier 1X2 domicile : 0,237 contre 0,216 pour BetPawa) et, une fois la cote
  connue, il n'apporte aucune information de plus (vérifié par famille sur la réserve).
- Conséquence mesurée : quand le modèle annonce ≥ 72 % mais que BetPawa annonce moins, la réussite tombe à 64–69 % (le modèle se trompe) ;
  d'où l'**accord avec la cote** (développement : +7,8 points sur la probabilité, p = 0,009 ; confirmé sur la réserve : +5,4 points, p = 0,004).
- Scénario contradictoire : **ne filtre pas** (les marchés qui résistent font moins bien que leur probabilité, p = 0,047) ; stabilité : apport non
  significatif (p = 0,10). Les deux restent affichés, pour information.
- **Test final (réserve, 851 matchs du 14 au 27/10)** : 531 paris principaux, **74,8 % réussis pour 73,4 % annoncés**, cote moyenne 1,27,
  rendement −4,8 %. Tous les paris retenus : 793, 73,9 %, rendement −5,7 %. **Aucune rentabilité démontrée** : la cote paie un peu moins que la réussite.
- Combinés : aucun ne passe les règles sur la réserve (cotes trop hautes pour 72 %).

## Production (`python -m moteur_omega.suivi pipeline`)
- Étape « Moteur omega » de `pipeline.yml`, après l'alpha, `continue-on-error`.
- `data/omega/journal.jsonl` (ajout seul) : une ligne « pronostic » par match à venir, nouvelle ligne seulement si la sélection change ; la
  dernière ligne écrite AVANT le coup d'envoi est celle qui compte ; une ligne « resultat » par match, jamais modifiée.
- `data/omega/pronostics.json` → `pronostics_omega.html` (`archetype_omega.js`, lecture seule). Bilan calculé sur les seuls paris gelés avant le match.
- Présentation (27/10/2026, ordre de Patrick) : en-tête court dans une carte épurée ; le bloc « EN OBSERVATION… test sur 557 paris… » et les notes
  du pire scénario (« buts d'une équipe = … ÷ 2 », « information… », « sans un des matchs… ») ne sont plus affichés (le calcul, le statut et
  `p_min` restent dans le JSON). À la place : « Derniers matchs » des deux équipes = EXACTEMENT les matchs du même lieu utilisés par le modèle
  (`donnees.derniers_matchs` : date, adversaire, score, V/N/D, moyennes marquées/encaissées ; 10 au plus par équipe, du plus récent au plus ancien).
  Gelé dans la fiche des nouveaux pronostics ; pour les anciens gels, complété à la lecture par `page(matchs=…)` sans modifier le journal.
- **Barre « réussite attendue » supprimée** (27/10/2026) : parmi les paris retenus (807, du 28/09 au 26/10), le pourcentage annoncé (62–70 %) ne
  distingue pas les paris (corrélation avec la réussite 0,004 ; tranches 67,5 / 65,2 / 69,8 / 69,0 %). Ce qui distingue, de façon stable sur les deux
  moitiés de la période : le TYPE de pari (buts du match 72 % sur 306 ; résultat 62 % sur 292 ; buts d'une équipe 69 % sur 197 ; combinés trop peu, non publiés).
  La carte affiche donc la réussite constatée du type de pari (`historique.py` → `docs/omega_historique.json`, relancé à chaque passage du pipeline,
  minimum 30 paris par famille). Le pourcentage du pari reste dans le détail (modèle et cote). Aucun niveau de « confiance » inventé.
- **Carte « pourquoi ce pari »** (27/10/2026, ordre de Patrick) : le pourcentage du cercle = probabilité BRUTE du modèle (`p_modele`, 62 à 88 % selon les paris, sans la cote ; ce n'est pas la probabilité affichée avant, qui était min(modèle, cote) et ne variait que de 62 à 69 %). Mesuré : au-dessus de la cote, le modèle ne gagne rien en réussite réelle; il est dans un cercle ; à côté, UNE phrase vraie **propre au type de pari** (`archetype_omega.js`, `omPhrase`), simple décompte sur les « Derniers matchs »
  affichés, sans estimation : total de buts (« terminés avec 3 buts ou moins : X sur N pour A à domicile, Y sur N pour B à l'extérieur ») ; buts d'une équipe
  (ses buts marqués + les buts encaissés par l'adversaire) ; les deux marquent ; cage inviolée / encaisse ; 1X2 ; double chance ; handicap (marge exigée) ;
  combinés = décompte du pari complet (`pari_sur_derniers`, calculé en Python par `marches.test_du_marche`, score de l'extérieur inversé).
  Aucune phrase si une équipe n'a pas de matchs. Les décomptes JS sont recoupés avec ceux de Python (60 paris, 0 écart). L'encart « réussite par type de pari » (`historique.py`) n'est plus affiché sur les cartes (refusé par Patrick le 27/10/2026) ; le fichier
  `docs/omega_historique.json` reste produit.
- **Buts attendus près du pari** (28/10/2026) : la ligne « Buts attendus : A x – y B » est affichée sous le pari principal (zone du cercle), plus dans les détails
  (`archetype_omega.js`, `omPourquoiCourt`). Raison : un pari « Forest Green encaisse au moins 1 but » se décide sur les buts attendus d'Eastleigh (1,3), pas sur sa seule moyenne
  à l'extérieur (0,7), et ce chiffre était trop loin du pari. Affichage seulement, aucun calcul ni sélection modifiés.
- **Seuil lié à la taille d'échantillon : testé, NON retenu** (28/10/2026, 830 paris principaux de l'archive, sélection actuelle) : réussite par minimum de matchs au même lieu
  4-5 : 67,5 % (526), 6-7 : 76,6 % (47), 8-10 : 33,3 % (9), 11-14 : 65,2 % (227), 15+ : 85,7 % (21) ; par stabilité (p_min) et par écart modèle − cote : aucune pente nette. Aucun seuil ajouté (cohérent avec « stabilité sans apport »).
- **Solidité** (28/10/2026, ordre de Patrick ; `solidite.py`, `indice.py`, `suivi._ajouter_solidite`) : pourcentage affiché sous chaque pari (principal et « autres paris »), pour repérer d'un coup d'œil les marchés
  les plus pertinents et robustes. Pour le MÊME TYPE DE MARCHÉ, croise deux lectures des derniers matchs au même lieu des deux équipes (séries gelées du match, poids égal aux deux équipes) :
  la FRÉQUENCE (part des matchs où le pari passait) et les ÉCARTS DE BUTS (distance moyenne au basculement du score = nombre minimal de buts à changer pour que le pari change d'issue, signée,
  normalisée par l'écart-type propre au type de marché ; `marches.test_du_marche` donc valable pour tous les marchés, combinés compris). Régression logistique de la réussite réelle sur :
  niveau de départ par type de marché + logit(fréquence) + écart normalisé ; poids APPRIS sur l'archive (tous les marchés des matchs joués, avec ou sans cote), réécrits à chaque pipeline dans
  `docs/omega_solidite.json`. N'utilise NI la cote NI la probabilité du modèle. Marché non appris (moins de 100 observations) ou sans poids : aucune solidité. Calcul à la lecture, jamais écrit dans le journal,
  ne change ni la sélection ni les pronostics. **Vérifié hors échantillon** (poids appris sur les premiers 60 % des jours, test sur les 40 % suivants, 84 600 marchés) : perte 0,5255 contre 0,5581 (type de
  marché seul) et 0,5650 (fréquence brute) ; écart moyen de calibrage par marché 1,7 point (max 4,2) ; tranches de 9 / 19 / 29 / 45 / 72 % de solidité = 9 / 19 / 29 / 45 / 72 % de réussite.
  Le poids de la fréquence seule est quasi nul une fois les écarts pris en compte (le signe de l'écart contient déjà « passe / ne passe pas »).
  **Historique du jour (abandonné)** : (1) indice de réserve = moyenne de (pari passe) et (pari passe avec un but de réserve), non comparable entre types de marché (sous-estime de 5 à 21 points,
  plafonne à 50 % pour match nul / cage inviolée / moins de 0,5 but) ; (2) fréquence seule, comparable mais sans les écarts de buts demandés. La Solidité ne départage pas les paris déjà retenus par Omega
  (rejeu de l'archive, 1 229 paris : corrélation −0,03) : c'est une aide de lecture. Journal réel d'Omega au 28/10 : 36 matchs réglés, 39 paris (les 1 229 viennent du rejeu de l'archive).
- **Marché pondéré** (27/10/2026, ordre de Patrick ; `ponderation.py`, `docs/omega_ponderation.json`) : sur chaque carte, sous le pari principal, le marché
  le plus probable parmi ceux de cote **supérieure à 1,22**, avec un repère « Même pari / Dans le même sens / Pari différent » (comparaison des scores qui font gagner).
  Probabilité pondérée = régression logistique sur modèle, cote et fréquence dans les derniers matchs ; poids APPRIS sur l'archive (40 984 marchés), réécrits à chaque
  pipeline. Poids mesurés : cote 1,09, modèle 0,03, derniers matchs ≈ 0 : le résultat est presque la cote seule (Brier 0,1973 contre 0,1975). Test réserve (après le 14/10) :
  ≈ 75 % de réussite, cote moyenne 1,27, rendement ≈ −5 % : INFORMATION, pas un pari rentable. Affichage seulement : calculé à la lecture, jamais écrit dans le journal,
  ne change ni la sélection ni les pronostics gelés. Le jour du lancement : 1 pari identique, 6 dans le même sens, 92 différents sur 99 (le pondéré tombe presque toujours
  sur un favori à cote ≈ 1,24).
- **Bloc « Les 4 croisements »** : ancien affichage (2×2, « (moy. x) » après les buts) ; la moyenne est en couleur, en gras, police 12 px (+2 px), identique partout (27/10/2026, ordre de Patrick).
- **Replier une carte** (27/10/2026, ordre de Patrick) : `af-repli-carte.js`, commun à tous les moteurs (alpha, V, V2R, V3, Europe, Comportement, Omega, Journal) : quand on replie une carte dont le haut
  est sorti de l'écran, la page remet son haut sous la barre fixe, donc la carte suivante apparaît tout de suite ; si le haut est visible, rien ne bouge. Aucune donnée touchée.
- **Barre d'onglets** (28/10/2026, ordre de Patrick) : onglets en cartes avec icône, TOUS de la même taille (78×62 px), une couleur par page (`--c`), libellé « MOTEUR » en petit au-dessus du nom
  (alpha, Omega, V3, Europe, V2R, V, V2), onglet actif plein et centré (`af-repli-carte.js`). Tickets, Journal, Corners & cartons, Système sans « Moteur ». Liens et ordre inchangés (12 pages).
- Statut (dans le JSON) : observation.
- Une seule exception à « tout seuil appris » : la cote minimale 1,39, imposée par Patrick.

## Points ouverts / améliorations possibles
- Recalibrer quand la saison 2026-27 sera plus avancée (relancer `python -m moteur_omega.calibrage`).
- Les combinés n'ont presque pas d'historique de cotes (archivés depuis peu) : à réévaluer avec plus de données.
- Tests : `tests/test_moteur_omega.py`.
