# Scripts d'analyse tels qu'exécutés pendant la conception de v (15-16/10/2026)

**Archive, non maintenue.** Ces scripts ont tourné dans un répertoire de travail temporaire, avec des chemins en dur et le prototype
`moteur_v_test.py` / `moteur_v_calibre.py` (copiés ici), PAS le package `moteur_v/` du dépôt. Ils servent à retrouver comment chaque chiffre
de `docs/MOTEUR_V_HISTORIQUE.md` a été obtenu. Le moteur en production est `moteur_v/` ; sa vérification est
`evaluation/moteur_v/rejoue_niveaux.py` et le suivi à l'aveugle `evaluation/moteur_v/test_aveugle.py`.
`rows2.pkl` (10 771 lignes match x marché du prototype) n'est pas conservé : il se reconstruit en rejouant le prototype sur `jeu_reglage_ids.json`.

| Script | Rôle |
|---|---|
| `moteur_v_test.py` | prototype v1 (fréquences, verrou, k, musique) + rejeu sur l'archive |
| `test_300.py` | test à l'aveugle des règles A, B, C figées (version 1) |
| `tune.py`, `search.py` | réglage « en trichant » : calibrage logistique, grille de 525 règles |
| `diag.py` | diagnostic de calibration (pourcentage annoncé / cote / famille / championnat), IC par match |
| `valid.py` | validation chronologique (première moitié / seconde moitié) des restrictions |
| `calib.py` | calibrage par validation croisée (cote, pourcentage v, fréquences rétrécies, familles) |
| `pts.py`, `rang.py` | écart de points, classement reconstruit, corrélation |
| `robust.py` | robustesse du pourcentage calibré dans les deux sens |
| `force.py` | force des adversaires (Poisson) contre la cote |
| `moteur_v_calibre.py`, `seuil.py` | moteur calibré (seuil, verrou, vetos) et balayage des seuils 0,66 à 0,78 |
| `etage2.py`, `modele_seul.py` | étage 2 (calcul simple), choix par le modèle seul, zones de cote |
| `replay_modele.py`, `replay_autres.py` | rejeu du mode « modèle seul » et de la rubrique « autres » |
| `audit.py` | audit des chiffres annoncés (plages de cotes, apport de l'étage 2, test de hasard) |
| `test_aveugle_v2.py` | version prototype du test à l'aveugle (remplacée par `evaluation/moteur_v/test_aveugle.py`) |
