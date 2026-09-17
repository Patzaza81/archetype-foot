"""
archetype_model/audit/ — Module d'audit et de contrôle PASSIF du moteur
(chantier Patrick, 17/09/2026).

RÈGLE D'OR DE TOUT CE PACKAGE, NE JAMAIS ENFREINDRE : aucun fichier ici
ne modifie, ne lit pour décider, ni n'influence de quelque façon que ce
soit un seuil de production (SEUIL_PEAGE1 dans main.py, COTE_MIN/MAX,
EDV_MIN_*, ROBUSTNESS_STD_THRESHOLD dans config_loader.py/convergence.py,
ni aucune valeur de config/adaptive_parameters.json gérée par
archetype_model/learning/calibration.py). Ce package OBSERVE le pipeline
existant et PRODUIT de la télémétrie -- il ne participe jamais à la
sélection P1/P2/P3, jamais à la robustesse, jamais à l'éligibilité d'un
marché.

- circuit_breaker.py : verdict d'intégrité des données brutes d'un
  match, calculé AVANT le Péage 1 -- additif, jamais un rejet.
- telemetry.py : agrégats de rétention par étage réel du pipeline
  (Péage 1 -> filtre de convergence -> H2H informatif -> sélection
  finale) + Brier score / log-loss calculés a posteriori sur les
  pronostics déjà résolus dans archetype_model/learning/archive/.
- report.py : synthèse dashboard (data/audit_status.json).
"""
