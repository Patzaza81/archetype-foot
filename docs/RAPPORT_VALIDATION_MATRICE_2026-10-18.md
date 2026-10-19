# Validation statistique de la matrice de scénarios — 2026-10-18

Statut : **DONNÉES INSUFFISANTES**. Aucun scénario n'est déclaré rentable. `promotion_allowed=false`, rien n'est branché.
Preuves brutes : `docs/validation_matrice_2026-10-18.json` (sortie de `python -m matrice_scenarios.validate`).

## 1. Données utilisées
- **Archive de test** (`data/archive_test`, cotes BetPawa archivées au run, avant coup d'envoi) :
  - 1 493 lignes → 1 359 matchs uniques, du 2026-09-28 au 2026-10-17 (**20 jours**).
  - Exclus : 65 sans coup d'envoi, 48 captés après le coup d'envoi, 1 équipes identiques, 20 doublons fusionnés. 697 sans score définitif.
  - Seule source avec cotes du run : seule base valable pour le ROI et la comparaison au marché.
- **Football-Data** (`data/football_data`) : 16 558 matchs, 38 ligues, 2025-01-23 → 2026-10-16. Lu en **résultats seulement** : ses colonnes de cotes ne sont pas des cotes du run (CONTRAT.md), donc aucun ROI ni comparaison au marché sur cette source. 1 ligne sans score écartée, 0 doublon contradictoire.

## 2. Tests exécutés
- **E1 – Walk-forward archive** (3 plis, 60 %/80 %/100 % de l'historique) : découverte, validation, test chronologiques, sans jour partagé. 1 000 permutations du pipeline entier (rejouent la sélection).
- **E2 – Walk-forward Football-Data** : 12 mois testés (2025-09 → 2026-10), fenêtre croissante, 200 permutations par pli. Contre le taux de base seulement.
- **E3 – Transfert** : 4 509 règles gelées sur Football-Data jusqu'au 2026-09-27 (empreinte SHA-256 `24a6e37d…`), évaluées sur l'archive jamais vue. Correction max-T (famille 4 191 règles pour la lift, 4 114 pour le ROI, définie par l'effectif ≥ 30, jamais par les résultats). 2 000 permutations.
- Deux nuls : **marché** (scores permutés à probabilité 1X2 du marché égale ; sert aux conclusions de rentabilité) et **libre** (permutés par ligue ; dit seulement « mieux que le hasard »).
- Un seul pari par match (priorité fixée par la lift de validation). Intervalle bootstrap par jour (les marchés d'un même match ne comptent pas comme preuves indépendantes).

## 3. Résultats chiffrés
**E3 – transfert gelé sur l'archive (1 359 paris, 1 par match)**
- Taux de réussite 54,1 %, cote moyenne 1,99.
- Excès sur le taux de base : **+7,7 points** [+4,3 ; +11,0].
- **ROI net : −6,6 %** [−13,5 % ; −0,1 %].
- ROI par bloc de dates : −18,7 % / −7,9 % / −2,6 %. Aucun bloc positif. Par ligue : 10 positives sur 23 (petits effectifs).
- Lift moyenne des règles : p = 0,0005 contre le nul « libre » (mieux que le hasard), mais **p = 0,0495 contre le nul « marché »**. Excès du portefeuille contre le marché : p = 0,225. ROI du portefeuille contre le marché : p = 0,20.
- Max-T : 0 règle avec p ajusté ≤ 0,05 en ROI ; 0 en lift contre le marché (max z = 6,43 contre un seuil 95 % de 6,83). Seul le nul « libre » en garde 73 en lift.
- Meilleur ROI observé : 17–37 % sur 19–30 paris réglés, p ajusté = 1,0. C'est du bruit de sélection.

**E1 – walk-forward archive (tests d'un seul jour ou presque)**
- Plis 60/80/100 % : 119 / 420 / 778 règles sélectionnées, tests sur 230 / 238 / 258 matchs.
- ROI du portefeuille test : −3,2 % / −0,2 % / −3,0 %. Excès sur la base : +13,7 / +14,4 / +8,3 points.
- Permutations « marché » : p du ROI de 0,43 / 0,25 / 0,28 ; p de l'excès de 0,52 / 0,22 / 0,89. Rien de distinguable du marché.
- Deux plis sur trois ne couvrent qu'un jour : pas d'IC par jour possible (affiché `null`, jamais inventé).

**E2 – Football-Data, 12 mois, sans cotes**
- Lift moyenne de test : +3,9 points, mais le nul la donne à +4,2 : **p = 0,60**. Les règles sélectionnées ne battent pas le hasard une fois la sélection rejouée.
- Excès du portefeuille : +8,3 points contre +2,9 sous le nul, p = 0,005. Un seul pli sur 12 passe p ≤ 0,05. Plis à fenêtres qui se recoupent : indicatif seulement.

## 4. Lecture
- Les règles trouvent une vraie structure (équipes fortes à l'extérieur, buts à domicile) : le taux de base est battu.
- Le marché la connaît déjà. Un excès sur la base n'est **pas** un avantage sur le marché : ROI négatif malgré +7,7 points d'excès.
- Aucune preuve indépendante de rentabilité. Le ROI mesuré est plutôt négatif, de l'ordre de la marge du bookmaker.

## 5. Limites
- 20 jours d'archive : critère de preuve fixé d'avance = ≥ 56 jours et ≥ 300 paris réglés avec ROI > 0, IC95 bootstrap par jour excluant 0, p marché ≤ 0,05, au moins 2/3 des blocs positifs. Critères remplis : échantillon gelé, nombre de paris. Non remplis : durée, ROI, IC, p marché, stabilité.
- Une seule saison de cotes. Les autres marchés que ceux archivés (BetPawa) ne sont pas testables.
- Football-Data : aucun horodatage de capture, preuve pré-match par dates strictement antérieures seulement.
- Valeur de p du binomial par approximation normale, sert au tri ; les conclusions reposent sur les permutations.

## 6. Prochaine étape faisable
- Continuer l'archivage nocturne jusqu'à ≥ 56 jours cumulés au-delà du 2026-10-17 (soit environ le 2026-12-12) et ≥ 300 paris réglés indépendants.
- Règles préenregistrées pour ce test futur : `docs/regles_gelees_matrice_2026-10-16.json` (4 726 règles, gelées au 2026-10-16, empreinte `4e0a242a…`, non modifiables : le chargeur refuse tout fichier modifié).
- Commande : `python -m matrice_scenarios.validate --evaluate-frozen docs/regles_gelees_matrice_2026-10-16.json --from-date 2026-10-18 --output rapport.json`
- La matrice continue de découvrir des combinaisons nouvelles (20 000 candidats échantillonnés, 1 250 règles distinctes) ; les règles gelées ne sont qu'un jeu de test, pas une liste fermée.

## 7. Réglage orienté rentabilité (demande du 18/10)
- Données : 7 622 matchs Football-Data avec cotes d'ouverture Bet365 (substitut, pas des cotes du run), 2025-07 → 2026-05. Marchés : 1X2 et Over/Under 2,5.
- Procédure fixée avant le test (`matrice_scenarios/tuning.py`) : règles découvertes sur l'apprentissage (4 587 matchs) ; gardées si ROI > 0 en apprentissage ET en validation (1 522 matchs), effectifs ≥ 60/40, classées par ROI de validation moins 1,28 erreur-type ; 34 règles retenues ; test unique sur 1 513 matchs (22/03 → 31/05).
- **Test (substitut)** : 1 499 paris, ROI **−3,5 %** [−8,7 % ; +2,3 %]. Nul « marché » (procédure rejouée sur scores permutés, 100 tirages) : ROI moyen −2,7 %, p = 0,56. Rien ne bat le hasard.
- **Test réel sur l'archive BetPawa (cotes du run, jamais vue)** : 1 199 paris, ROI **−8,0 %** [−14,3 % ; −0,3 %]. Paris : 884 over 2,5, 251 nuls, 48 under 2,5, 16 victoires extérieur.
- Conclusion : le réglage n'a pas produit de règle rentable. Le ROI se dégrade du test (−3,5 %) à l'archive (−8,0 %), signe que la sélection n'a appris que du bruit. Aucune règle activée.
- Fichiers : `docs/reglage_rentabilite_2026-10-18.json` (règles et chiffres), `docs/run_reglage_rentabilite.py.txt` (script exact).

## 8. Croisements « marqué contre encaissé adverse » (approche de Patrick), 8 marchés
- Code : `matrice_scenarios/croisements.py` ; chiffres : `docs/croisements_2026-10-18.json`. Famille fixée d'avance (une formule par marché, 5 derniers matchs au même lieu, ≥ 4 requis). Seuil = top 20 % du score sur les 60 % de dates les plus anciennes ; mesure sur la suite.
- Contre le taux de base (Football-Data, 5 390 matchs de test, 22/03 → 16/10) : victoire domicile 56,9 % contre 43,4 % de base, victoire extérieur 40,0 % contre 30,4 %, Over 2,5 60,9 % contre 54,9 %, Under 2,5 51,5 % contre 45,1 %, domicile marque 81,9 % contre 79,2 %. Les deux marquent (57,5 % contre 57,1 %) et nul (27,7 % contre 26,2 %) : quasi rien.
- Contre la cote (ROI) : Football-Data avec cotes Bet365 de substitut, ~300 paris par marché, ROI entre −9,9 % et +4,7 %, tous intervalles incluant 0. Archive BetPawa : 40 à 82 paris par marché, ROI entre −16,4 % et +5,1 %, intervalles très larges (historique réduit : 634 matchs avec ≥ 4 matchs au même lieu).
- Conclusion : le croisement bat nettement le taux de base mais pas démontrablement le prix. Pas de preuve de rentabilité.

## 9. Outil d'analyse d'un match (`python -m matrice_scenarios.analyse_match`)
- Entrée : 3 à 5 scores récents par équipe (buts de l'équipe d'abord, au même lieu que le match) et, en option, les cotes. Sortie : probabilité calibrée par marché, cote d'équilibre, écart au taux de base, lecture de la cote donnée.
- Calibration : `docs/calibration_croisements.json` (14 048 matchs Football-Data, résultats seulement ; tranches fixées sur les 60 % les plus anciens). Qualité hors échantillon (Brier contre taux de base, 5 635 matchs) : victoire domicile +2,9 %, victoire extérieur +2,3 %, Over/Under 2,5 +1,0 %, domicile marque +0,7 %, extérieur marque +0,4 %, nul +0,1 %, les deux marquent +0,04 %.
- Limite connue : la tranche la plus haute plafonne (victoire extérieur 45 %), elle sous-estime les cas extrêmes comme Zwolle - Go Ahead Eagles.

## 10. Pronostic « le plus sûr » (`matrice_scenarios/pronostic_sur.py`)
- Règle (corrigée à la demande de Patrick) : cotes 1,10 à 1,25 EXCLUES (pas de marge de gain) ; parmi les marchés BetPawa à partir de 1,26, retenir le plus probable selon le modèle de croisements (marchés ajoutés : double chance, Over 1,5, Under 3,5 / 4,5 / 5,5).
- Archive jouée (calibration Football-Data seule, donc indépendante), réussite selon le plafond de cote : 1,26 à 1,30 : 73,7 % (414) ; 1,26 à 1,35 : 73,7 % (636, annoncé 73,6 %) ; 1,26 à 1,40 : 71,5 % ; 1,26 à 1,50 : 69,7 % ; sans plafond : 66,0 % (958, annoncé 75,0 %).
- Plafond par défaut : 1,35, retenu parce que la réussite (priorité) y est la meilleure et calibrée. Au-delà, le modèle est trop confiant. ROI à 1,26-1,35 : −3,9 %.
