# Omega V3 — audit et mise en cohérence (mission du 02/11/2026)

Branche `moteur-gamma-omega-v3` (PR #143). Rien n'est fusionné, rien n'est déployé, `main` n'est pas touché.
Mesures : `python -m moteur_omega_v3.evaluation` → `docs/omega_v3_evaluation.json` (tout le détail) et `docs/omega_v3_marches_A_B_C.csv` (383 marchés, une ligne chacun).
Échantillon : 525 matchs joués analysables (28/09 → 01/11/2026). Chronologie : 354 matchs de développement (avant le 28/10), 171 de réserve. Les règles sont apprises sur le développement, jamais sur la réserve.

## Verdict en cinq lignes

- **Cote minimale 1,35 + réussite de 70 % : incompatibles sur ces données.** Aucun marché ne dépasse 65,6 % de réussite lissée quand on ne regarde que les cotes ≥ 1,35. Avec une cible de 70 %, la route principale est **vide** (0 marché, 0 pari).
- **L'estimation g surestime partout, et d'autant plus qu'elle est haute** : sur les cotes ≥ 1,35, g annonce 64,5 % en moyenne, la réalité est 53,3 % (+11,2 points). À g ≥ 90 % : annoncé 96,6 %, réel 65,1 %.
- **Le filtre à 81 % pour les cotes basses** donne 85 % réel (996 observations, réserve) quand on lit l'estimation seule, et 89,6 % quand on exige aussi l'historique du marché. Le même taux de 85 % est celui du taux de base de ces marchés : l'estimation n'apporte presque rien seule.
- **Combinaisons** : seuls 66 des 156 combinés générés ont une cote BetPawa réelle. Sur la réserve, l'événement joint à g ≥ 70 % réussit 44–59 %. Aucune combinaison n'est validable aujourd'hui.
- **Rien n'est basculé en production.** Les niveaux de cible ne sont pas tranchés : c'est ton arbitrage (section « Décisions à prendre »).

## A. Audit de l'existant

- **Estimation du moteur** : f = fréquence des 25 couples de buts (attaque domicile × attaque extérieur) ; g = la plus basse f quand on retire une observation. Les défenses ne changent ni f ni g (prouvé : variation 0,0 sur les 10 retraits défensifs testés). C'est la pondération marginale de l'ancien moteur, à l'identique (écart max 0).
- **Seuil actuel** : tranches de g de 5 points, lissage monotone, première tranche à 70 % de réussite avec ≥ 30 paris. Calibré sur les cotes ≥ 1,26. Il n'y avait que 11 marchés sur 383 avec un seuil.
- **EV / écart à la cote** : ne servaient pas à décider mais étaient calculés, journalisés et affichés. **Supprimés** (`coeur.py`, `suivi.py`, page). Les anciennes lignes du journal gelé ne sont pas modifiées ; la page ignore le champ.
- **Cote** : le chargeur ne garde un match joué que si ses cotes ont été prises avant le coup d'envoi. Dans l'archive (relevés, plusieurs par match) : 2 988 relevés de matchs joués avec cote avant le coup d'envoi, 87 avec cote après (écartés), 199 sans heure de coup d'envoi (écartés).
- **Cotes manquantes** : 201 075 couples match × marché ; 53 301 ont une cote (26,5 %). Seuls les marchés que BetPawa propose ont une cote : tout le reste n'est jamais publiable.

## B. Analyse statistique

### B1. Cotes (population de décision)

| | observations |
|---|---|
| avec cote | 53 301 |
| cote ≥ 1,35 (route principale) | 46 051 |
| cote < 1,35 (route combinaisons) | 7 250 |
| dont entre 1,26 et 1,35 (perdues en passant de 1,26 à 1,35) | 1 793 |

### B2. Surestimation de g (cote ≥ 1,35, g ≥ 50 %, toute l'archive) — constat, aucune correction

| tranche de g | observations | g moyen | réussite réelle | écart |
|---|---|---|---|---|
| 50–60 % | 2 113 | 51,3 % | 48,2 % | +3,0 |
| 60–70 % | 1 085 | 62,0 % | 54,4 % | +7,6 |
| 70–80 % | 1 176 | 73,5 % | 53,7 % | +19,9 |
| 80–90 % | 412 | 81,8 % | 63,6 % | +18,3 |
| 90–100 % | 401 | 96,6 % | 65,1 % | +31,5 |

- **Par famille** : buts d'une équipe +10,4 ; buts du match +12,3 ; combinés +11,7 ; résultat +10,6 (les scores exacts, 6 observations, ne comptent pas). Aucune famille n'est épargnée.
- **Par période** (trois tiers d'effectif égal) : +13,2 ; +7,8 ; +12,5. Pas de tendance.
- **Par effectif du marché** : < 30 observations (335 marchés) +21,1 ; 30–99 (28 marchés) +11,4 ; ≥ 100 (20 marchés) +9,2. Moins il y a de données, plus l'écart est grand.
- **Explication des 7,3 points du premier audit** : c'est un biais de sélection. Parier seulement quand la cote est ≥ seuil retient justement les cas que le bookmaker juge moins sûrs ; à g égal ces cas réussissent moins. Plus la cote minimale monte, plus l'écart monte : +6,9 points sur la sélection à 1,26 (réserve), +11,2 sur l'ensemble des cotes ≥ 1,35.
- **Limite de cette lecture** : un écart à g ≥ 90 % de 31 points montre que g est une fréquence de 5 matchs, pas une probabilité. Je n'ai posé aucune constante de correction.

### B3. Route principale (cote ≥ 1,35) : seuil propre à chaque marché, appris sur le développement, jugé sur la réserve

| cible de réussite lissée | marchés avec seuil | paris | matchs | réussite réelle (C) | g moyen annoncé |
|---|---|---|---|---|---|
| 55 % | 16 | 582 | — | 56,7 % | 70,0 % |
| 60 % | 5 | 250 | — | 56,0 % | 70,0 % |
| 65 % | 1 | 51 | 51 | 51,0 % | 66,2 % |
| 70 % | 0 | 0 | 0 | — | — |
| 75 % | 0 | 0 | 0 | — | — |
| *référence : cible 70 %, cote ≥ 1,26* | 11 | 344 | 136 | 70,6 % | 77,6 % |

- Plus aucune cible ≥ 65 % n'est tenue. Le niveau maximal qu'un marché ait tenu sur le développement (cote ≥ 1,35, ≥ 30 observations) est 65,6 % ; 28 marchés sur 383 ont un niveau mesurable ; **0 atteint 70 %**.
- Le niveau tenu par chaque marché est dans le CSV (`niveau_atteignable`) : c'est le seuil propre à chaque marché, sans cible commune.
- Méthodes testées pour fixer le seuil par marché (réserve, cote ≥ 1,35 ; essais exploratoires non versionnés, ordres de grandeur) : cible = taux de base du marché (+ borne de Wilson) → 54 % réel, annoncé 72 % ; cible = base + 5 points → 49 % réel ; courbe commune à tous les marchés → 52,7–58,2 % réel pour 60–68,6 % annoncé ; courbe par famille, avec ou sans ajustement par marché → 52–55 % réel pour 70–75 % annoncé. **Aucune ne corrige l'écart.** Je ne grave aucune de ces méthodes.
- Stabilité du seuil (apprentissage sur deux moitiés du développement) : aucun marché n'a de seuil dans les deux moitiés. Les seuils par marché ne sont pas reproductibles avec 354 matchs.
- Stabilité de la fréquence historique B par période : les 383 marchés restent dans le bruit binomial sur les trois périodes (≈ 175 matchs chacune). Ce test a peu de puissance : il ne montre pas que les marchés sont stables, seulement qu'on n'y voit pas d'instabilité.

### B4. Route « combinaisons » : trois lectures du seuil de 81 % (cote < 1,35, réserve)

| lecture | observations | marchés | réussite réelle | Wilson 95 % | annoncé (g) |
|---|---|---|---|---|---|
| estimation du match g ≥ 81 % | 996 | 50 | 85,3 % | 83,0–87,4 | 95,4 % |
| fréquence historique du marché B ≥ 81 % (≥ 30 matchs) | 1 152 | 24 | 85,1 % | 82,9–87,0 | 82,2 % |
| les deux | 633 | 24 | 89,6 % | 87,0–91,7 | 96,3 % |

- Lire le seuil sur l'**estimation seule** admet 50 marchés, dont « plus de 1,5 but » : 79,8 % réel au développement pour un taux de base de 75,1 %. Sur la réserve, son taux (85,3 %) est celui de la lecture historique (85,1 %) : l'estimation seule n'apporte pas d'information mesurable en plus du marché.
- Lire le seuil sur l'**historique seul** est calibré (annoncé 82,2 % / réel 85,1 %) mais ne tient pas compte du match.
- **Les deux** donne le meilleur taux. Elle exige au moins 30 matchs valides : un marché à petit échantillon ne passe jamais.
- Le choix reste à toi (voir plus bas). Je n'ai rien gravé.

### B5. Combinaisons (événement joint)

- **Ce que BetPawa propose** : groupes `1x2_btts`, `dc_btts`, `1x2_total_1.5…5.5`, `dc_total_1.5…4.5` = 66 combinés. Aucune cote pour `btts_total_*`, `1x2_total_6.5+`, `dc_total_5.5+` : 90 des 156 combinés générés n'ont aucune cote et ne sont **jamais publiés**.
- Un exemple du type « l'équipe A marque au moins un but et plus de 1,5 but » n'existe pas dans le relevé de BetPawa. Il serait calculable, mais sans cote réelle il n'est pas publiable.
- Seuls 118 des 11 034 couples match × combiné cotés ont une cote < 1,35 (1,1 %) : les combinés sont presque tous des marchés à cote ≥ 1,35.
- **Méthodes comparées sur la réserve** (8 928 observations) : l'événement joint (f) annonce 25,1 %, réel 25,1 % (Brier 0,1842). Le produit des pourcentages annonce 17,1 % (−8,0 points), le minimum 24,6 %. L'événement joint est la seule méthode sans biais ; produit et minimum sont écartés par principe.
- **Cote d'une combinaison** : la cote réelle vaut en médiane 1,02 fois le produit des cotes des composantes (5–95 % : 0,74–1,59). Elle doit donc être lue, jamais calculée.
- **Réussite réelle par tranche de g de l'événement joint** (développement | réserve) : 40–50 % : 51,2 % | 37,6 % ; 50–60 % : 51,7 % | 42,4 % ; 60–70 % : 63,2 % | 54,8 % ; 70–80 % : 60,7 % | 44,3 % ; 80–90 % et 90–100 % : moins de 60 % en réserve (51 et 18 observations). **Aucune combinaison ne tient un niveau élevé.**

### B6. Couverture : les 666 matchs exclus (1 191 matchs joués, 525 analysables)

| cause | matchs |
|---|---|
| les deux équipes < 5 matchs au même lieu | 528 |
| domicile < 5 matchs à domicile | 64 |
| extérieur < 5 matchs à l'extérieur | 67 |
| championnat sans aucun match connu | 7 |

- Les défenses viennent des mêmes matchs que les attaques : il n'y a pas de manque défensif séparé. Les 659 « données insuffisantes » sont toutes des manques d'historique au lieu.
- Manque d'historique (équipe × match exclu) : 1 match manquant dans 523 cas, 2 dans 371, 3 dans 168, 4 dans 92, 5 dans 33.
- Couverture si le minimum était de : 4 matchs au lieu → 797 matchs, 3 → 1 004, 5 → 525 (actuel), 6 → 333.
- Je **ne baisse pas** le minimum de 5. Statuts proposés (non branchés) : *analysable* (≥ 5 au lieu des deux côtés), *analysable avec réserve* (4 au lieu : 272 matchs de plus, à valider avant tout usage), *non analysable* (< 4 ou doublon / incohérence / donnée manquante).

### B7. Les 625 scénarios

- 625 = 5⁴ exact. Chaque couple (attaque domicile, attaque extérieur) est répété 25 fois, une fois par couple de défenses. Défenses « filtre » = pondération marginale de l'ancien moteur : **équivalents** (écart max f = 0, prouvé par énumération indépendante). Les 625 scénarios ne sont pas 625 observations indépendantes : il n'y en a que 20.
- Trois lectures comparées (réserve, mêmes seuils par protocole) : A (attaques seules, production) Brier calibré 0,1112 ; B (mélange attaque / défense) 0,1018 ; C (Poisson sur la moyenne attaque / défense) 0,1006. Sur la sélection : A 71,8 % réel (269 paris), B 66,9 % (384), C 71,9 % (270).
- C améliore le Brier du pool (0,1006 contre 0,1112) mais pas la sélection. **Je ne change pas la formule** : la différence est mesurée sur tous les marchés confondus (dominés par des marchés presque certains), elle ne prouve pas un gain sur les marchés décisifs.
- Lecture « fermé / habituel / ouvert » : c'est le vocabulaire du moteur alpha (paires de matchs). Omega V3 ne l'utilise pas ; son équivalent est le palier de compatibilité (strict / intermédiaire / élargi). Le CSV ne donne donc pas de colonne par scénario fermé / habituel / ouvert.

## C. Architecture (ce qui est fait et ce qui reste à trancher)

**Fait et testé** (`moteur_omega_v3/evaluation.py`) :
- trois notions séparées partout : A (`f_moyen`, `g_moyen`), B (`B_historique` : n valides, succès, échecs, remboursés, fréquence, Wilson, trois périodes), C (`C_validation_reserve`) ;
- tableau de 383 marchés (dont les 174 initiaux marqués) : identifiant, famille, définition et formule indépendantes, écart A − B, stabilité, part de matchs cotés, cotes ≥ 1,35 et < 1,35, cote médiane, date de dernière collecte, niveau atteignable, seuil pour une cible donnée ;
- route principale : cote ≥ 1,35, seuil propre à chaque marché, appris sur le développement ;
- route combinaisons : trois lectures du filtre à 81 %, historique appris sur le développement seulement, 30 matchs valides minimum ;
- combinaisons : événement joint calculé par somme sur la loi des scores ; produit, minimum et somme comparés en preuve seulement ; aucune combinaison sans cote réelle ;
- ni Edge, ni EV, ni EDV : supprimés du moteur, du journal (nouvelles lignes) et de la page. La cote ne sert qu'à aiguiller et reste affichée comme condition d'accès.

**Non basculé en production** (la page et le journal gelé gardent la sélection actuelle, cote ≥ 1,26) : c'est volontaire, les niveaux ne sont pas tranchés. Changer la cote minimale de la production à 1,35 avec une cible de 70 % vide la page.

## D. Avant / après

| | avant (production actuelle) | après, cote ≥ 1,35, cible 70 % | après, cote ≥ 1,35, cible 55 % |
|---|---|---|---|
| marchés principaux avec un seuil | 11 | 0 | 16 |
| paris en réserve | 344 | 0 | 582 |
| réussite réelle en réserve | 70,6 % | — | 56,7 % |
| g annoncé | 77,6 % | — | 70,0 % |
| écart | +6,9 | — | +13,3 |

Marchés candidats aux combinaisons : 24 marchés (lecture « les deux », 633 observations en réserve, 89,6 %). Marchés non retenus : tous les autres, avec raison dans le tableau.

## Décisions à prendre (je ne tranche pas à ta place)

1. **Cible de réussite d'un marché principal.** À 1,35, 70 % n'existe pas sur ces données. Options : (a) garder 70 % et accepter une page presque vide ; (b) descendre à 55–60 %, réussite réelle 56–57 % mais annoncée à 70 % (surestimation de 13 points, donc un pourcentage affiché qui trompe) ; (c) ne rien afficher en principal tant que les données ne permettent pas de tenir le niveau. Je recommande (c) pour l'affichage, et (a) comme règle : un pari principal à 56 % réel ne correspond pas à ce que tu veux publier.
2. **Lecture du seuil de 81 %** : « les deux » est la seule qui dépasse 89 % avec peu de marchés (24). À confirmer.
3. **Pourcentage affiché** : g est une fréquence de 5 matchs, pas une probabilité (écart de 31 points à g ≥ 90 %). Tant qu'il n'est pas calibré sur la population réellement cotée, afficher la réussite observée (B ou C) et pas g.
4. **Marchés du périmètre** : tu parles de 174 marchés ; le moteur en génère 383 (les 174 en sont un sous-ensemble). Je les ai tous évalués ; les 174 sont marqués.
5. **Formule des 625 scénarios** : C est meilleure au Brier sur le pool mais pas en sélection. Pas de changement sans ton accord.

## Limites

- 525 matchs sur 35 jours : un seul mois, un seul régime de marché. La réserve (171 matchs) a des intervalles larges (± 5 à 8 points).
- Les seuils par marché ne sont pas reproductibles entre deux moitiés du développement.
- Les cotes sont celles de la dernière collecte avant le coup d'envoi : elles ne sont pas des cotes d'ouverture.
- Aucun bilan de paris réellement gelés n'est utilisé ici : ces mesures sont des validations chronologiques sur archive, pas le bilan du moteur (`bilan_reel.py` reste la seule source pour ça).

## Preuves techniques

- Modules ajoutés : `moteur_omega_v3/evaluation.py` ; tests : `tests/test_evaluation_omega_v3.py` (17).
- Modifiés : `coeur.py` (EV et écart à la cote retirés), `suivi.py` (champs retirés du journal pour les nouvelles lignes), `archetype_gamma.js` + `pronostics_gamma.html` (cote affichée comme simple condition, plus d'EV), `tests/test_gamma_js.py` (test EV remplacé par un test d'absence).
- Non touchés : `calculs.py`, `run_pipeline.py`, `scraper_details.py`, `contrat_moteur.py`, moteur DC, journal gelé, `bilan_reel.py`.
