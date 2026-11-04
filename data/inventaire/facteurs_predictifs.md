# Étape 6c — carte des facteurs prédictifs isolés

Code : `facteurs_predictifs.py`. Pour chaque compétition, marché et variable (32), modèle à 2 paramètres [logit P1, variable] ajusté sur les matchs strictement antérieurs à la saison test (2324, 2425, 2526), comparé à P1 et à P1 recalibré seul. Statistiques d'archive.

- Tests : 8512 ; seuil de Bonferroni z > 4.38 : **0 facteur robuste**.
- Facteurs avec z > 1,96 contre P1 recalibré : 113 sur 8512 (à peu près 213 attendus par hasard, unilatéral) : **aucun signal d'un facteur linéaire isolé au-delà de P1**.
- Recalibrage de P1 seul : gain moyen -0.0010 de perte log, significatif (z > 1,96) dans 12 couples sur 266.
- Critère plus souple (z > 1,96, ≥ 2 saisons gagnantes, signe du coefficient stable) : 66 couples-facteurs ; par marché {'ext': 18, 'o15': 10, 'nul': 8, 'o35': 2, 'dom': 15, 'btts': 2, 'o25': 11} ; variables les plus fréquentes [('mu_dom_moins_ext', 8), ('mu_total', 6), ('elo_diff', 6), ('dom_bc_domicile', 4), ('h2h_buts', 3), ('forme_bc_dom', 3)] ; compétitions [('MEX', 5), ('P1', 5), ('SC1', 5), ('USA', 5), ('SP2', 4)]. À lire comme des pistes, pas des preuves.
- Conclusion : les écarts à P1 trouvés par les règles sont non linéaires (seuils, queues de distribution), pas des effets linéaires de variables isolées.

Détail : `facteurs_predictifs.json`.
