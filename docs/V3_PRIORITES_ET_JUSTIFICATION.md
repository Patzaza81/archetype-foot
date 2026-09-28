# Moteur V3 — priorités de recalibrage et standard de justification (28/09/2026)

Document de référence pour l'autre IA (conception V3) et pour Patrick (décideur). Rien ici ne modifie les
paramètres V3 : ce sont des constats et une proposition, à trancher avant le futur recalibrage.

## 1. Priorités pour le futur recalibrage (constats du 28/09 sur les 4 premiers aperçus)

Constats chiffrés sur Rudar Velenje–Dravinja, Fylde–Carlisle, Hornchurch–Aldershot, Yeovil–Worthing
(archive du 28/09, commit 95d13ab) :

| Priorité | Constat | Chiffres | Piste (à décider) |
|---|---|---|---|
| P1 | Les aperçus tombent tous sur les plus petits échantillons (3 ou 4 matchs au même lieu) | 4 sur 4 ; buts attendus 2,74 / 0,63 (Rudar) ; total 4,52 (Yeovil) ; total 1,69 (Hornchurch) | Lissage plus fort quand n est petit (K plus grand), ou n minimum plus haut pour sélectionner |
| P2 | Écart modèle / marché très grand, donc surconfiance probable | +15,7 pts (Rudar), +9,4 (Fylde), +18,9 (Hornchurch), +13,4 (Yeovil) | Plafond d'écart ou alerte « écart suspect » tant que la calibration n'est pas prête |
| P3 | Référence 1,35 but identique pour tous les championnats | Même attraction vers 1,35 pour la Slovénie D2 et la National League | Référence par championnat, estimée hors des 501 matchs de contrôle |
| P4 | La dispersion mélange les buts des deux équipes, tous lieux confondus | 1,34 (Rudar), 1,38 (Hornchurch) calculées sur 14 et 20 matchs mélangés | Dispersion par équipe et par lieu |
| P5 | Poisson indépendant : extrêmes trop probables | Yeovil : 30 % pour 6 buts ou plus contre 15 % pour le marché | Correction de dépendance ou de sur-dispersion, validée sur l'archive |
| P6 | Calibration : 300 observations = seulement 12 à 15 matchs | ~25 paris par match, tous liés au même score | FAIT le 28/09 : minimum 50 matchs joués en plus des 300 observations |

## 2. Couverture des marchés (mise en place le 28/09)

Avant : la V3 ne calculait que 37 marchés (ceux du registre du banc). Les handicaps, le score exact, le pair/impair,
les totaux 6,5 / 7,5, les buts d'une équipe 2,5 / 3,5 et « encaisse au moins un but » étaient cotés par BetPawa
mais ignorés.

Après : tous les marchés plein temps cotés par BetPawa sont calculés (jusqu'à ~110 par match). Chaque run note
dans `bilan.couverture` les groupes BetPawa que la V3 ne sait pas lire (aucun sur l'archive du 28/09). Le journal
`data/v3/journal/` garde le diagnostic COMPLET de chaque marché : cote, probabilité, marge, raisons de rejet.

Ajout du 28/09 (décision de Patrick) : **handicap à 3 choix** BetPawa, lignes Domicile −2, −1, +1, +2, issues 1 / X / 2
(12 marchés). Le scraper de nuit ne lisait pas ce bloc : lecture ajoutée dans `parse_betpawa_playwright.py` et
`parse_betpawa_url.py`, sous la clé `handicap_3issues_L` (L = handicap du domicile). Clé volontairement différente de
`handicap_3choix_N` (copier-coller) que le pont V2 lit : la V2 ne voit aucun changement (test d'isolation). Les autres
lignes éventuellement cotées (±3…) sont ignorées par choix et notées dans `bilan.couverture.groupes_ignores_par_choix`.
Les handicaps à 2 choix (±0,5 à ±3,5) restent calculés. Premières cotes à 3 choix : à partir du prochain run de nuit.

Limites qui restent :
- **Mi-temps** (1X2 MT, MT/fin, buts par mi-temps) : le moteur sait les calculer, mais l'archive n'a ni buts à la
  mi-temps ni cotes mi-temps. Aucun de ces marchés n'est calculable aujourd'hui.
- **Corners, cartons** : pas de cotes, pas de données dans l'archive.
- **Sélection** : un marché n'est sélectionnable que si la règle du double contrôle le couvre. Depuis la version 1.2.0
  (28/09, décision de Patrick), 27 règles couvrent 41 marchés V3, dont 6 issues du handicap à 3 choix (docs/REGLE_DOUBLE_CONTROLE.md). Restent hors règle :
  score exact, nombre exact de buts, pair / impair, match nul, handicaps ±2,5 / ±3,5, 6 issues du handicap à 3 choix
  (les 4 « X » et les deux « gagne par 3 buts ou plus ») et les autres lignes.

## 3. Standard de justification V3 (validé par Patrick le 28/09, appliqué : `moteur_v3_pipeline.explication`)

Même structure pour chaque sélection, quel que soit le marché. Tout est calculé par le pipeline et écrit dans
`pronostics_v3.json` ; le site ne fait qu'afficher.

**Résumé (carte repliée, 1 ligne)**
« Probabilité 82 % (non calibrée) contre 66 % selon la cote 1,52 · marge +23,9 % · 3 matchs au même lieu »

**Détails de l'analyse (6 blocs, toujours dans cet ordre)**

1. **Données** : matchs utilisés, scores inclus.
   « Rudar à domicile (3) : 3-0, 4-1, 2-0 → marque 3,00, encaisse 0,33. Dravinja à l'extérieur (4) : 0-1, 0-2, 1-1, 1-5 → marque 0,50, encaisse 2,25. »
2. **Buts attendus** : moyenne brute → moyenne lissée → buts attendus.
   « Attaque Rudar 3,00 → 2,06 ; défense Dravinja 2,25 → 1,80 ; buts attendus Rudar = 2,06 × 1,80 / 1,35 = 2,74. »
3. **Probabilité du marché** : phrase de calcul propre à la famille (tableau ci-dessous) + les 2 scores les plus probables.
4. **Face à la cote** : cote → probabilité du marché, écart, marge, seuil appliqué.
   « 1,52 → 65,8 % ; écart +15,7 pts ; marge 1,52 × 0,157 = +23,9 % (seuil 5 % au-dessus de 71 %). »
5. **Contrôles passés** : fenêtre de cote, dispersion (valeur), double contrôle (raisons), règle d'échantillon, état de la calibration.
6. **Pourquoi ce marché** : les 3 meilleurs marchés des autres familles et la raison exacte de leur rejet (ou « dominé par … »).

**Alertes automatiques (affichées en tête si déclenchées)**
- 3 ou 4 matchs au même lieu → « petit échantillon »
- écart avec la cote > 12 points → « écart inhabituel avec le marché »
- total de buts attendus < 1,8 ou > 4,0 → « buts attendus extrêmes »
- dispersion entre 1,20 et 1,50 → « résultats irréguliers »
- calibration non prête → « aperçu non calibré »

**Phrase de calcul par famille de marchés (bloc 3)**

| Famille | Marchés V3 | Phrase de calcul |
|---|---|---|
| Résultat | 1X2, double chance | « Somme des scores où domicile > extérieur (ou ≥, ≠…) » |
| Handicap à 2 choix | handicap ±0,5 à ±3,5 | « Somme des scores où buts domicile + L > buts extérieur » |
| Handicap à 3 choix | Domicile −2, −1, +1, +2 (1 / X / 2) | « Somme des scores où buts domicile + L >, = ou < buts extérieur » |
| Total de buts | plus / moins de 0,5 à 7,5 | « Somme des scores avec au moins N buts (ou au plus N-1) » |
| Nombre exact / parité | 0 à 6+, pair / impair | « Somme des scores dont le total vaut N (ou est pair) » |
| Buts d'une équipe | plus / moins de 0,5 à 3,5 | « Probabilité que l'équipe marque au moins N buts avec ses buts attendus seuls » |
| Les deux marquent | oui / non | « Probabilité que chaque équipe marque au moins un but » |
| Cage inviolée / encaisse | oui / non | « Probabilité que l'adversaire ne marque pas (ou marque) » |
| Score exact | 0-0 à 4-4 | « Probabilité du score h-a : P(domicile marque h) × P(extérieur marque a) » |

Chaque famille garde les blocs 1, 2, 4, 5, 6 à l'identique ; seul le bloc 3 change.
