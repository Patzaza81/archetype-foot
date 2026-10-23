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
