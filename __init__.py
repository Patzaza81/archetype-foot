"""
archetype_model — package neuf, isolé, remplaçant définitif de V0
(TRANSITION.md 27.1, ARCHETYPE_FOOT_modele_corrige_v3.md).

Aucune ligne de V0 (moteur_v0.py, brancher_moteur_v0.py) n'est réutilisée
ici. Ce package ne dépend, en LECTURE SEULE, que de primitives déjà
existantes et déjà testées du dépôt (ex. scraper_details.fetch_html) --
jamais de calculs.py, run_pipeline.py, precalcul.py, moteur_v0.py, ni
d'aucun cache partagé avec l'ancien moteur (cache_equipes.json inclus).

Chantiers livrés à ce jour :
- data/ (loader.py, validation.py) -- 08/09/2026
"""
