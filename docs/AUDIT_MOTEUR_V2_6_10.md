# Audit sévère du moteur v2.6.10 — 01/10/2026

Audit du code que j'avais écrit la veille, mené comme une relecture hostile : chaque soupçon a été **mesuré** avant d'être
corrigé (simulations **synthétiques**, aucune donnée du dépôt n'a servi à régler quoi que ce soit). État final : 51 tests
locaux contre un harnais reprenant les fonctions réelles de `moteur_v2_6_9.py`.

## Défauts trouvés et corrigés

| # | Gravité | Défaut | Mesure | Correction |
|---|---|---|---|---|
| 1 | **Haute** | Lissage à référence **unique** (1,35) : il tire l'équipe qui reçoit vers un niveau trop bas et la visiteuse vers un niveau trop haut. | Deux équipes parfaitement moyennes (1,50 / 1,20) : P(domicile) 44,1 % → 41,0 % à n = 5, P(extérieur) 30,4 % → 33,3 %. Biais systématique, plus fort sur petits échantillons. | Références par rôle (1,50 domicile, 1,20 extérieur ; total 2,70 inchangé). Test : deux équipes moyennes ne bougent plus. |
| 2 | **Haute** | Calibration marché par marché : les probabilités de marchés complémentaires ne somment plus à 1. Les deux côtés d'un même marché pouvaient être « value » ensemble. | 1X2 = 1,090 ; BTTS = 1,028 ; over/under 2,5 = 1,038 ; dc_1X ≠ victoire + nul. | `coherence.harmonise` : groupes complets renormalisés, double chance dérivée du 1X2, marchés équivalents alignés. Test : jamais « value » des deux côtés. |
| 3 | **Haute** | Un calibrateur appris sur le mauvais modèle (probabilités v2.6.9 non lissées) ou sur des matchs postérieurs au match analysé était appliqué sans aucun contrôle. | Constat de code (aucune garde). | Signature du modèle (incluant les paramètres de lissage) + date du plus récent match d'apprentissage. Le moteur **ignore et signale** (`IGNORE_MODELE_DIFFERENT`, `IGNORE_ANACHRONIQUE`). Dates obligatoires à l'apprentissage. |
| 4 | **Haute** | Biais de sélection : l'archive du pipeline ne contient que les value bets / choix. Un calibrateur appris dessus mesure la malchance du modèle sur ce qu'il juge meilleur que le marché, pas sa fiabilité. | Constat de code et de conception. | Apprentissage refusé en dessous de 8 marchés par match (`ECHANTILLON_BIAISE_PAR_SELECTION`). Exigence documentée : archiver l'**inventaire complet** (≈ 20 marchés/match). |
| 5 | Moyenne | Calibration trop bruitée sur peu de matchs. | Modèle parfaitement calibré : à 50 matchs la courbe isotone s'écarte de l'identité de 3,5 points en moyenne, 9 au pire (234 matchs : 1,7 / 5). | Minimum de 100 matchs (V3 : 50), blocs ≥ 30 observations, et correction **pondérée** n / (n + 100). Simulation d'un modèle surconfiant : plus proche de la vraie correction que la correction pleine à 50, 100, 234 et 500 matchs. |
| 6 | Moyenne | L'avertissement R5 (profil attaque/défense asymétrique) était évalué sur des moyennes déjà lissées : il disparaissait. | Test : profil 2,0 / 0,9 flagué par v2.6.9, plus par le lissage naïf. | R5 recalculé sur les valeurs **brutes**, remis à sa place dans la liste. |
| 7 | Moyenne | Handicap à ligne entière avec push remboursé : le calibrateur apprend « pari gagné », l'événement n'est plus le même. | Constat de code. | Ces lignes ne sont pas calibrées quand `HANDICAP_ENTIER_REMBOURSE = True`. |
| 8 | Faible | Comparaison : un match du même jour pouvait se retrouver des deux côtés de la coupure chronologique. Pas de compte des choix. | Test de la coupure. | Coupure toujours entre deux jours ; le script affiche le nombre de choix simulés. |
| 9 | Faible | Couplage silencieux aux fonctions internes de `moteur_v2_6_9`. | — | Test de contrat qui nomme la fonction manquante si elle est renommée. |
| 10 | Faible | Recherche linéaire dans le calibrateur. | — | Recherche dichotomique. |

## Ce qui n'est PAS corrigible ici (limites structurelles, à décider)

1. **Le marché bat le modèle.** Brier mesuré le 21/09 : 0,2004 (modèle) contre 0,1860 (marché). Lissage et calibration corrigent le
   *niveau* des probabilités, pas leur *pouvoir de discrimination* : une transformation monotone ne rend pas le modèle plus
   informatif que le marché. Si, après la comparaison, la différence de Brier avec le marché reste positive, les « value bets »
   du moteur n'ont pas de fondement statistique, et aucune correction de ce fichier n'y changera rien. Décision du
   propriétaire : ancrer le modèle sur le marché, ou ne plus présenter ces choix comme des value bets.
2. **Les références 1,50 / 1,20 et K = 4 sont a priori, pas validées.** `--sensibilite` montre si la conclusion en dépend.
3. **Les seuils d'EV (6 à 9 %), les catégories A-D (p ≥ 0,45) et « écrasant » (p ≥ 0,65) ont été posés sur des probabilités non
   corrigées.** Avec des probabilités moins extrêmes, il y aura moins de value bets et moins de choix. Un effet attendu (sur un
   favori de 5 matchs : 4 value bets → 0 dans le harnais), mais à mesurer : `compare_moteurs_v2.py` affiche le nombre de choix.
4. **Poisson à buts indépendants** (sous-estime les nuls) : inchangé.
5. **Aucune exécution contre le vrai `moteur_v2_6_9.py` ni contre le snapshot** : mon environnement n'a pas accès au dépôt. Les tests
   passent contre un harnais qui reprend les fonctions réelles ; la comparaison reste à lancer chez toi.
6. **L'étape nocturne qui apprend le calibrateur n'existe pas.** Elle exige l'archivage de l'inventaire complet avec les
   probabilités brutes du modèle courant (défaut 4).

## Verdict de l'audit
La v2.6.10 corrigée est plus sûre que celle d'hier (trois défauts à effet systématique supprimés), mais elle reste un **candidat non
validé**. Le point 1 ci-dessus est la vraie question ; la comparaison la tranchera.
