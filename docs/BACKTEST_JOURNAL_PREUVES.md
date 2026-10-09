# Backtest du classement du Journal — 09/10/2026

Méthode : chronologique, sans fuite. Candidats de chaque jour reconstruits avec les seuls matchs de date strictement antérieure ; calibrage de chaque jour appris sur les jours passés. 325 candidats, 14 jours (20/09 → 08/10/2026), dont 248 avec cote BetPawa. Reproductible : `python evaluation/backtest_journal_preuves.py`.

| Variante | Paris | Réussite | Annoncée | Implicite | ROI (± erreur std) |
|---|---|---|---|---|---|
| Ancien, Wilson | 10 | 20,0 % | 52,0 % | 45,4 % | −60,3 % (± 25,2) |
| Ancien, lissé | 67 | 46,3 % | 63,7 % | 56,6 % | −21,3 % (± 10,5) |
| Probabilité calibrée seule (sans condition d'écart) | 45 | 64,4 % | 61,8 % | 70,8 % | −11,2 % (± 9,9) |
| **Nouveau, mode preuves** | **0** | — | — | — | — |
| Référence : tous les candidats avec cote | 206 | 54,9 % | 61,9 % | 62,7 % | −12,7 % (± 5,7) |

Qualité des probabilités (Brier, plus bas = mieux, 213 paris) : Wilson 0,2662 ; lissée 0,2374 ; **calibrée 0,2264** ; moyenne passée 0,2431 ; **probabilité implicite de la cote seule 0,2221**.

Lecture honnête :
- Le calibrage améliore la probabilité annoncée (Brier −15 % contre Wilson, −5 % contre la lissée) et rapproche l'annoncé du réel, mais la cote du bookmaker prédit encore mieux que tout ce que le Journal ajoute.
- Sur cet échantillon, la fréquence de l'équipe n'apporte aucune information mesurable en plus du marché (pente écartée par le calibrage). Aucun pari du Journal n'a de borne basse au-dessus de la probabilité implicite : le mode `preuves` publie 0 pari.
- Aucune variante n'a un ROI positif démontré. Les petits échantillons (10 à 67 paris) ne permettent pas de distinguer les variantes entre elles : l'erreur type du ROI est de 10 à 25 points.
- Wilson, comme filtre `p ≥ 1/cote`, ne laisse passer que 10 candidats sur 248 et leur cote médiane est de 2,15 (contre 1,52 pour l'ensemble) : il choisit mécaniquement des cotes hautes.
- Non évalué faute de données : stabilité par compétition et par contexte domicile/extérieur (trop peu d'observations par cellule). Seule la stabilité entre moitiés de l'historique de l'équipe est utilisée.
- À refaire quand l'échantillon aura grandi : le calibrage se réajuste seul à chaque exécution.
