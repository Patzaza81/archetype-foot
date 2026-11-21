# Étude de la variable V (total de buts) — 20/11/2026

Idée de Patrick : V = (buts marqués + buts encaissés à domicile) + (buts marqués + buts encaissés à l'extérieur), moyennes sur les matchs au même lieu seulement (domicile pour l'équipe qui reçoit, extérieur pour le visiteur), comparée au total de buts du match. **Étude seulement : aucun moteur, aucune page, aucun test existant n'est modifié ; megapower n'utilise pas V.** Ce n'est pas un bilan de moteur (règle du 29/10 non concernée) : base d'archive Football-Data.

Code : `etudes/v_total_buts/` (`build_v.py` construit le tableau, `exp_v.py` et `exp2_v.py` font l'expérience ; le CSV est regénéré, non versionné).

## Base
`data/bloc_saisons/bloc_2526_2627.json.gz` : 11 127 matchs analysables (au moins 4 matchs au même lieu pour chaque équipe), 38 divisions. Chaque moyenne n'utilise que des matchs strictement antérieurs, de la même division et saison. Découpage chronologique de l'étude Mega Power : A 4 328 (01/09/2025 → 31/01/2026), B 2 690 (→ 12/04/2026), C test 2 788 (après le 12/04/2026). Modèles appris sur A+B, mesurés sur C.

## Résultats sur C
- V/2 est l'échelle du total moyen attendu : erreur moyenne 1,34 buts (V brut : 2,78). Corrélation V / total : 0,18.
- Réussite des 20 % de matchs où V est le plus fort (base de C entre parenthèses) : plus de 1,5 but 84,2 % (78,4 %) ; plus de 2,5 buts 64,1 % (54,9 %) ; moins de 3,5 buts 76,5 % (68,0 %) ; moins de 4,5 buts 89,0 % (83,5 %).
- Composantes séparées, deux intensités (domicile/extérieur), interactions : aucune ne bat V de façon nette (écarts dans l'erreur-type). Ajouter la nature du championnat améliore davantage (plus de 1,5 but : gain de log-loss 83,7 contre 46,9, ×10⁻⁴, contre le taux de base).
- Plus de 2,5 buts ne dépasse pas 72 % de façon stable.

## Limites
- Gains mesurés contre un taux de base constant, pas en plus du modèle d'équipes de megapower : **non testé si V ajoute quelque chose à megapower.**
- Cotes de totaux absentes du bloc (sauf plus/moins 2,5) : filtre cote ≥ 1,26 non testé ; les marchés les plus sûrs ont souvent une cote sous 1,26.
- Une seule période test ; gains modestes.
- Sur la base du flux megapower (8 semaines, médiane de 5 matchs par équipe) la corrélation n'était que de 0,11 : trop peu de matchs par équipe pour conclure.

Conclusion : V porte un signal réel mais modeste ; intégration à megapower non justifiée tant que son apport au-delà du modèle n'est pas démontré.
