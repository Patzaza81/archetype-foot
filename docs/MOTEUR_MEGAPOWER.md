# Moteur MEGAPOWER v2 (18/11/2026) — refonte sans aucune cote

Page `pronostics_megapower.html` · code `megapower/` · données `data/megapower/` · config `config/megapower.json` · étape du pipeline nocturne `python -m megapower.suivi pipeline`.

## But (décision de Patrick, 18/11/2026)

Trouver le **maximum de pronostics vrais et constants**. Le but n'est pas de battre la cote du bookmaker : **aucune cote n'entre dans le moteur, n'est lue, ni affichée** (test `test_aucune_cote_dans_le_code_du_moteur`). La version 1 (fondée sur les cotes, 10/11/2026) n'est plus alimentée ; son journal `data/megapower/journal.jsonl` reste en place pour comparer.

## Architecture (audit du 18/11/2026)

| Couche | Fichier | Ce qu'elle fait |
|---|---|---|
| Données | `donnees.py` | matchs du flux commun (`data/archive_test`), historique saison des deux équipes (avant le match seulement), scores connus. xG manquant = jamais inventé (buts seuls). |
| Référentiel + force + adversaires + tendance + classement | `modele.py` | μ domicile/extérieur de la ligue ; attaque et vulnérabilité défensive de chaque équipe AU MÊME LIEU ; chaque observation divisée par ce que l'adversaire laisse normalement (notes de ligue calculées avec les matchs d'avant) ; tendance arithmétique (u+r) ou géométrique (q·u) ; écarts de points / buts / xG par match. |
| Croisement | `modele.lambdas` | λA = μdom × ATT(A, dom) × DEF(B, ext) ; λB = μext × ATT(B, ext) × DEF(A, dom). Les quatre branches sont lues ensemble (une seule estimation, jamais quatre projections additionnées). |
| Probabilités | `modele.probas` | grille Poisson + Dixon-Coles (ρ d'Omega) → probabilité des 112 marchés du catalogue d'Analyse Verdict. |
| Scénarios | `modele.scenarios` | favorable / normal / catastrophe : les forces bougent d'un écart-type de leur incertitude, on garde le pire et le meilleur **pour chaque marché**. |
| Calibrage | `calibration.py` | par famille de marchés, régression logistique `logit(réussite réelle) = a + b·logit(P normale) + c·logit(P catastrophe)` : la constance entre dans la prévision seulement si elle aide. |
| Sélection | `calibration.choisir`, `suivi.retenus` | un marché est retenu si sa fiabilité calibrée (borne basse à 95 %) ≥ `fiabilite_demandee`, dans une famille autorisée. Jamais deux fois le même événement : si un marché plus précis (qui implique l'autre) est retenu, le plus large est retiré. Classé du plus fiable au moins fiable. « Aucun pronostic » est valide. |
| Suivi | `suivi.py` | gel avant le coup d'envoi (`journal_v2.jsonl`, ajout seul), règlement, bilan réel, page, test marche avant. |

## Règles

- Minimum 4 matchs au même lieu (domicile pour l'un, extérieur pour l'autre), sinon pas d'analyse (règle de Patrick du 07/11).
- **Aucun paramètre du modèle n'est posé à la main** : poids du xG, force du rapprochement vers 1, rapprochement de la ligue vers la moyenne générale, poids de la tendance (0 = aucune), coefficient du classement (0 = ignoré) sont choisis sur la 1re moitié des matchs joués et vérifiés sur la 2e (`modele.ajuster`). Un ingrédient qui n'améliore pas la prévision est mis à 0 (tendance : mise à 0 le 18/11).
- Seule valeur posée à la main : `fiabilite_demandee` = 0,72 (seuil de réussite fixé par Patrick pour alpha le 24/10/2026), modifiable dans `config/megapower.json`.
- Une famille de marchés dont la réussite mesurée en marche avant est sous ce niveau est écartée automatiquement (recalculé chaque nuit).
- Bilan réel = gel valide avant le coup d'envoi, match terminé, rien d'autre (règle `CLAUDE.md`). Les chiffres « marche avant » ne sont pas des résultats réels.

## Mesures du 18/11/2026 (base : 3 558 matchs joués du flux commun, 28/09 → 17/11 ; 2 379 analysables avec 4 matchs au même lieu pour chaque équipe)

Paramètres retenus : xG pleinement utilisé, rapprochement d'équipe 16 matchs neutres, ligue très rapprochée de la moyenne générale, **tendance rejetée (0)**, **écart de buts au classement retenu** (coefficient 0,33).

Erreur du modèle de buts sur la 2e moitié (plus bas = meilleur) : complet 3,0074 ; sans xG 3,0121 ; sans classement 3,0255 ; sans correction des adversaires 3,0076 ; sans tendance 3,0074 (identique, tendance à 0). Le classement est l'ingrédient le plus utile après le xG ; la correction des adversaires et la tendance n'apportent presque rien sur cette base (la base ne contient que les matchs des équipes déjà vues).

Test marche avant (chaque jour du 23/10 au 17/11 : calibrage appris sur les jours d'avant, pronostics du jour jamais vus) à fiabilité demandée 0,72 : **1 591 matchs, 9 071 pronostics (≈ 5,7 par match), 79,6 % réussis** ; 80,1 % sur la 1re moitié, 78,7 % sur la 2e. Probabilités calibrées : par tranche, la fréquence réelle suit la probabilité annoncée (ex. 74,8 % annoncé → 74,4 % observé). Familles : buts de l'extérieur 82 %, buts du domicile 81 %, total de buts 80 %, cage inviolée 79 %, double chance 78 % ; écartées : victoire ou nul (69 %, 36 pronostics), double chance + total de buts (69 %, 182 pronostics). Le contrôle hors échantillon du choix des familles n'en a écarté aucune sur la 1re moitié : il ne prouve donc rien sur ce filtre.

Compromis niveau/volume à d'autres fiabilités demandées (marche avant, borne basse) : 0,75 → 7 612 pronostics, 82,1 % ; 0,80 → 5 871, 86,8 % ; 0,85 → 4 581, 90,5 % ; 0,90 → 3 190, 93,4 %.

Limites : période de 8 semaines, une seule saison ; plusieurs pronostics d'un même match sont corrélés (le nombre de pronostics n'est pas le nombre de matchs indépendants) ; aucun résultat réel enregistré avant le déploiement.

## Tests

`tests/test_megapower.py` : aucune cote dans le code, règle des 4 matchs (3 cas qui passent, 3 qui échouent), xG jamais inventé, anti-fuite des notes de ligue, cohérence des probabilités et des scénarios, sélection sans doublon d'événement, barre de fiabilité et familles, calibrage, gel avant le coup d'envoi, règlement et bilan. Données fabriquées.

## Nature du championnat (19/11/2026)
Le calibrage de chaque famille reçoit un 4e terme : logit de la fréquence réelle récente du marché dans le championnat (matchs joués avant le match, lissée vers le modèle par 100 matchs). Poids appris, aucune cote. Essai marche avant sur l'archive (2 379 matchs joués) : réussite 79,6 % -> 80,4 % (9 071 -> 9 196 pronostics) ; seconde moitié 78,7 % -> 79,3 %. Étude : `docs/ETUDE_COMPLETE_MEGAPOWER.md` (branche megapower-audit). Non retenu car sans gain démontré : classement/écart de points, goal-average, réciproque au même lieu.

## Cote et jour (19/11/2026)
Pronostic proposé seulement si le marché a une cote Betpawa ≥ 1,26 (filtre d'affichage ; aucune cote dans le modèle ni dans le calibrage des probabilités). Le calibrage s'apprend sur les seuls marchés proposables (cote ≥ 1,26) : la fiabilité annoncée est celle de la population réellement proposée. Marche avant sur l'archive à 0,72 : 758 pronostics, 608 matchs, réussite 69,9 % (2e moitié 72,6 % sur 281). La page affiche la cote et le jour de la semaine (heure du Cameroun).

## Seuil propre à chaque famille (19/11/2026)
Un +1,5 but ne se calibre pas comme une victoire sèche : chaque famille de marchés a son seuil de fiabilité, appris sur le test marche avant (cote ≥ 1,26). Famille qui atteint la réussite demandée (0,72) : plus petit seuil qui l'atteint (≥ 100 pronostics). Familles prioritaires (victoire, double chance) qui ne l'atteignent pas : seuil à la meilleure réussite garantie (borne basse 95 %), marquées « objectif non atteint » ; leur fiabilité affichée est leur réussite réelle (victoire ≈ 63 %). Autres familles : proposées seulement si elles atteignent l'objectif.
