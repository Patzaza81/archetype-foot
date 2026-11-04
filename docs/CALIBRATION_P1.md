# Calibration de P1 — livraison finale (étape 7)

**Décision : P1 CONSERVÉ pour les 266 couples compétition × marché (38 compétitions × 7 marchés). Aucune correction ne passe la validation chronologique.** Statistiques d'archive, pas une performance de moteur. Chaque compétition est apprise seule.

## Protocole (fixé avant les résultats)
- Candidats sur logit(P1) : LEVEL (décalage), SLOPE (pente + décalage), ELO (pente + décalage + écart Elo), ELO_PALIER et P_PALIER (correction additive par paliers de l'écart Elo ou de P1, seuil par arbre à une coupure, groupes ≥ 30 matchs).
- Pour chaque saison t ∈ {2324, 2425, 2526} : ajustement sur les matchs strictement antérieurs à t, mesure sur t.
- Sélection sur 2324 + 2425 : meilleure méthode ; retenue si gain de perte log > 0 dans les deux saisons, z > 2,58 (Bonferroni sur 5 méthodes) et pente positive (ordre de P1 conservé).
- Confirmation sur 2526 (jamais vue par la sélection) : gain de perte log > 0, gain de Brier > 0 et z > 1,645.
- Les paramètres livrés sont ceux ajustés sur 2122–2526 de la méthode retenue ; si le statut est P1 CONSERVÉ, la meilleure candidate est conservée dans `parametres_meilleure_candidate` pour information.

## Résultat

- Couples validés : **0 sur 266**. Couples passant la sélection : 3 (F2 plus de 2,5 buts, I1 extérieur, I2 BTTS) ; aucun ne se confirme sur 2526 (z de confirmation −0,57 / +0,49 / +0,96).
- Gain moyen de la meilleure candidate sur 2526, par marché (nombre de compétitions à gain > 0 sur 38) : dom +0.0010 (23), nul -0.0004 (16), ext -0.0002 (24), o15 -0.0014 (15), o25 -0.0021 (13), o35 -0.0012 (18), btts +0.0002 (20) : en moyenne nul, donc aucun gain reproductible.
- Biais de P1 (pente de calibration sur tout l'historique, 1 = parfait) : moyenne 0.75, médiane 0.72 ; 158 couples < 0,85 (P1 trop extrême), 53 couples > 1,15 (P1 trop resserré). Le biais existe mais l'ajustement de pente ne se reproduit pas hors échantillon.

## T1 victoire extérieure (candidat prioritaire) : P1 CONSERVÉ
- Biais de P1 : pente de calibration 1.661 (P1 trop resserré) ; tiers bas : annoncé 19.7%, observé 14.2% (z -3.36) ; tiers haut : annoncé 41.6%, observé 46.7% (z 2.51).
- Meilleure candidate : ELO_PALIER, seuil d'écart Elo -1.090 (même seuil que la règle trouvée à l'étape 5), correction +0.226 sous le seuil, -0.039 au-dessus.
- Gains de perte log : 2324 −0,0001 (le seuil est appris sur 2 saisons seulement), 2425 +0,0224 (z 1,86), 2526 +0,0082 (z 0,72). Cumul 2425 + 2526 : +0,0157, z 1,89 (a posteriori, non utilisable comme validation).
- Motif du rejet : gain de perte log non positif dans chacune des saisons 2324 et 2425; z de selection 1.13 <= 2.58; confirmation 2526 insuffisante (gain +0.0082, gain Brier +0.0025, z 0.72, exige gain>0, Brier>0, z>1.645).

| Saison | perte log | Brier | pente de calibration | écart moyen | réussite |
|---|---|---|---|---|---|
| 2324 | 0.5446 → 0.5447 | 0.1811 → 0.1794 | 1.45 → 0.80 | 0.032 → 0.071 | 75.8% → 77.4% |
| 2425 | 0.5356 → 0.5132 | 0.1778 → 0.1672 | 1.62 → 1.00 | 0.030 → 0.049 | 76.3% → 78.6% |
| 2526 | 0.5223 → 0.5142 | 0.1729 → 0.1704 | 2.18 → 1.06 | 0.024 → 0.020 | 74.8% → 75.5% |

- Candidat à réévaluer avec une saison de plus : la direction est la même en 2425 et 2526, avec une pente de calibration ramenée à ≈ 1.

## USA BTTS : P1 CONSERVÉ
- Biais de P1 : pente 0.712, sous-estimation dans le tiers bas (annoncé 51.3%, observé 57.4%, z 3.56).
- Meilleure candidate : P_PALIER ; gains de perte log −0,0032 (2324), +0,0070 (2425), −0,0008 (2526) : signe instable, la pente de calibration de P1 oscille d'une saison à l'autre (1,34 / 0,81 / 0,93).
- Motif : gain de perte log non positif dans chacune des saisons 2324 et 2425; z de selection 0.70 <= 2.58; confirmation 2526 insuffisante (gain -0.0008, gain Brier -0.0004, z -0.26, exige gain>0, Brier>0, z>1.645).

## Incohérence perte log / calibration signalée au rapport précédent
- USA BTTS en 2526 (famille de règles) : perte log −0,0057 **et** écart moyen 0,016 → 0,049 : les deux se dégradent, pas d'incohérence sur ce cas ; la correction de 0,06 était appliquée à 93 % des matchs alors que l'écart restant était 0,016.
- L'écart apparent venait des lignes agrégées (perte log −0,0038 avec écart moyen 0,0243 → 0,0208). L'**écart moyen** (moyenne de P1 contre fréquence) ne mesure que le niveau global ; la perte log et le Brier mesurent aussi la pente et la résolution. Une correction peut améliorer l'un et dégrader l'autre.
- Cas inverse vérifié sur T1 extérieur : la perte log s'améliore (2425 : 0,5356 → 0,5132) alors que l'écart moyen augmente (0,030 → 0,049), parce que la correction corrige la **pente** (1,62 → 1,00) et non le niveau. Sur les 266 couples en 2526 : 25 ont une perte log dégradée avec un écart moyen amélioré, 42 l'inverse. **La pente de calibration et le Brier sont les mesures retenues pour décider ; l'écart moyen ne suffit pas.**

## Fichiers et interfaces
- `data/calibration_p1/config_calibration.json` : par compétition (paramètres de P1 : `k`, `demi_vie_jours`, `K_elo`) et par marché (`dom`, `nul`, `ext`, `o15`, `o25`, `o35`, `btts`) : `statut`, `methode`, `parametres`, `conditions_application`, `couverture`, `selection_2324_2425`, `confirmation_2526`, `performances_par_saison` (avant/après), `diagnostic_biais_P1`, `observation`, `parametres_meilleure_candidate`.
- `calibration_p1.py` (numpy seulement, indépendant des moteurs) : `charger()`, `appliquer(config, competition, marche, p, elo_diff=None)` → `(p_corrigée, info)` (P1 renvoyée telle quelle si P1 CONSERVÉ), `appliquer_1x2(...)` (renormalisation), `elo_diff_depuis_historique(matchs, K, dom, ext)` (vérifié identique à la recherche).
- `calibration_finale.py` : régénère la configuration (≈ 30 s) ; à relancer quand une saison est ajoutée : le statut sera réévalué avec le même protocole.
- Aucun moteur existant n'est modifié ni appelé ; tant qu'aucun couple n'est validé, `appliquer` ne change aucune probabilité.
