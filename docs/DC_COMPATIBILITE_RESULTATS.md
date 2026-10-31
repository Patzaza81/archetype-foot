# Règle n°1 (compatibilité) — rapport d'évaluation

> **Exploration sur archive/rejeu (Football-Data), PAS un bilan réel.** Aucun de ces paris n'a été gelé par le moteur avant le coup d'envoi. Le seul juge reste `bilan_reel.py`.
> Cotes absentes du rejeu : le filtre « cote ≥ 1,26 » n'est PAS appliqué. Test de la compatibilité brute.

- Calibrage : **9488 matchs** de la saison 2025-26 (2025-02-28 → 2026-05-31).
- Test : **1598 matchs** de la saison 2026-27 (2026-03-03 → 2026-10-16), séparation stricte. Période courte, échantillon modeste.

## Sélection par P seul (référence, seuil appris sur 2025-26)

`{"seuil": 0.7, "paris": 14631, "matchs_avec_pari": 1598, "reussite": 0.803020982844645}`

## Écart apparié compatibilité − P, à nombre de paris égal (IC 95 % par bootstrap sur les matchs)

| Variante | Seuil appris | Volume | Réussite compat. | Réussite P | Écart | IC 95 % | MDE | Retenu | Holm | Paris communs |
|---|---|---|---|---|---|---|---|---|---|---|
| min (volume_compat) | 0.50 | 4152 | 85.0% | 88.5% | -3.5% | [-4.7% ; -2.2%] | 1.2% | non | False | 2408 |
| min (volume_P_seuil) | 0.50 | 14631 | 76.4% | 80.3% | -3.9% | [-4.7% ; -3.2%] | 0.8% | non | — | 10271 |
| min (demi_pari_par_match) | 0.50 | 799 | 88.6% | 92.9% | -4.3% | [-7.2% ; -1.4%] | 2.9% | non | — | 224 |
| moyenne (volume_compat) | 0.50 | 7137 | 83.3% | 86.1% | -2.8% | [-3.7% ; -1.9%] | 0.9% | non | False | 4765 |
| moyenne (volume_P_seuil) | 0.50 | 14631 | 77.4% | 80.3% | -2.9% | [-3.5% ; -2.2%] | 0.7% | non | — | 10985 |
| moyenne (demi_pari_par_match) | 0.50 | 799 | 89.6% | 92.9% | -3.3% | [-6.3% ; -0.4%] | 2.9% | non | — | 216 |
| produit (volume_compat) | 0.50 | 356 | 89.3% | 91.9% | -2.5% | [-7.2% ; +2.0%] | 4.5% | non | False | 66 |
| produit (volume_P_seuil) | 0.50 | 14631 | 77.5% | 80.3% | -2.8% | [-3.5% ; -2.1%] | 0.7% | non | — | 10962 |
| produit (demi_pari_par_match) | 0.50 | 799 | 90.1% | 92.9% | -2.8% | [-5.6% ; +0.1%] | 2.8% | non | — | 217 |

## La compatibilité ajoute-t-elle de l'information à P ? (logistique ajustée sur 2025-26, lue sur 2026-27, pool P ≥ 50 %, observations : 41546)

### Régression brute (sans placebo : biaisée, voir ci-dessous)

| Variante | Coef. P | Coef. compat. (std) | Gain LL / observation | IC 95 % | MDE | Retenu |
|---|---|---|---|---|---|---|
| min | 1.00 | +0.006 | +0.00004 | [+0.00000 ; +0.00008] | 0.00004 | oui |
| moyenne | 0.98 | +0.021 | +0.00017 | [+0.00005 ; +0.00029] | 0.00012 | oui |
| produit | 0.99 | +0.017 | +0.00011 | [+0.00002 ; +0.00020] | 0.00009 | oui |

### Régression CENTRÉE par marché (lecture décisive, amendement post-hoc)

| Variante | Coef. P | Coef. compat. (std) | Gain LL / observation | IC 95 % | MDE | Retenu |
|---|---|---|---|---|---|---|
| min | 1.01 | -0.011 | +0.00001 | [-0.00008 ; +0.00011] | 0.00010 | non |
| moyenne | 1.01 | -0.007 | +0.00000 | [-0.00006 ; +0.00007] | 0.00006 | non |
| produit | 1.01 | -0.009 | +0.00000 | [-0.00007 ; +0.00007] | 0.00007 | non |
