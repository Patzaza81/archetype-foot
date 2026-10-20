# Moteur alpha « séries » (`alpha_serie/`)

Nouvelle logique de Patrick, codée à côté de l'ancien alpha (`matrice_scenarios/`), qu'elle ne modifie pas. **Non branchée au pipeline** : aucune sortie de production, aucun ticket. Mise en service seulement sur ordre de Patrick.

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
- Tests : `tests/test_alpha_serie.py`.

## Résultat du backtest au 20/10/2026 (marche avant, 707 matchs rejoués, coupe au 09/10)
Chiffres rapportés tels quels, **aucune rentabilité démontrée** (archive de 21 jours) :
- Buts (avec cote ≥ 1,25) : 167 propositions, réussite 59,9 %, rendement à mise égale −12,7 %.
- Équipes (avec cote ≥ 1,25) : 902 propositions, réussite 66 %, rendement −8,1 %.
- Marché par marché, la réussite des marchés admis est proche de leur réussite de base (par exemple Pas de nul 71 % contre 74 %, Victoire domicile 50 % contre 43 %).
- Multigoals et multiscores : jugés en réussite seule, sans cote dans l'archive. Le groupe « Match nul » est admis très souvent (355 fois) à 26 %, comme sa base.

## Points ouverts
- Les enjeux (légende de zones Matchendirect) ne sont pas collectés.
- Aucune norme de niveau mesurée pour les multigoals (marge d'un but par borne par défaut).
- 21 jours d'archive seulement : tout seuil reste provisoire et à recalculer à chaque ajout de jours.
