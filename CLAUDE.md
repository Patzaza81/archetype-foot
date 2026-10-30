# Config
- Stack: Python 3.12, Git, GitHub, Netlify
- Test: `pytest`
- Git: `git status && git diff`

# Agents
- Sous-agent uniquement si tâche parallèle/isolable
- Contexte minimal par sous-tâche
- Revue du résultat avant intégration

# Guardrails
- Vérifier avant toute modification critique
- Préserver compatibilité + tests existants
- Pas de suppression/modification clé sans validation

# Instructions spécialisées — à lire selon la tâche

Avant toute modification concernée, lire le document spécialisé correspondant :
- Sélection, double contrôle, justification des marchés : `docs/CLAUDE_SELECTION.md`
- Journal de rentabilité : `docs/CLAUDE_RENTABILITE.md`
- Données, saisons, sources et contrat moteur : `docs/CLAUDE_DATA.md`
- Archive de test, anti-fuite et évaluation : `docs/CLAUDE_ARCHIVE.md`
- Corners et cartons (modèle, preuves, limites) : `docs/CORNERS_CARTONS.md`
- Moteur v (conception, tests subis, résultats, suivi) : `docs/MOTEUR_V.md` et `docs/MOTEUR_V_HISTORIQUE.md`
- Moteur alpha = séries appariées (`alpha_serie/`, remplace l'ancien alpha le 20/10/2026 ; pronostics et journal gelé chaque nuit, hors tickets, aucune cote à l'analyse) : `docs/ALPHA_SERIE.md`
- Laboratoire de matrice de scénarios (indépendant de l'alpha) : `docs/MATRICE_SCENARIOS.md`
- Moteur omega (croisements, scénario contradictoire, Poisson/Dixon-Coles calibré, accord avec la cote, cotes de 1,39 et plus seulement ; autonome, hors tickets) : `docs/MOTEUR_OMEGA.md`
- Moteur DC (Dixon-Coles sur le championnat entier, vraisemblance pénalisée, calibré hors échantillon, preuves empiriques par perspective, cotes de 1,39 et plus ; autonome, hors tickets, sans mise ni EV) : `docs/MOTEUR_DC.md`

## Règles de sécurité

- Les documents spécialisés font partie des instructions du projet : ne pas les ignorer lorsqu'une tâche relève de leur domaine.
- En cas de modification d'une règle métier, mettre à jour simultanément le document spécialisé et les tests concernés.
- Ne pas déplacer, supprimer ou modifier une règle spécialisée uniquement pour réduire la taille de ce fichier.
- Les fichiers critiques du système restent inchangés par cette réorganisation documentaire.
- Cette organisation ne modifie ni le code Python, ni les données, ni le pipeline, ni les tests : elle ne fait que répartir les instructions Claude.

## Documentation complémentaire

Les contrats et règles détaillées référencés par les documents spécialisés restent les sources de référence lorsqu'ils existent, notamment :
- `docs/CONTRAT_MOTEUR.md`
- `docs/REGLE_DOUBLE_CONTROLE.md`
- `tests/`

## Tests, bilans et rapports de performance (règle de Patrick, 29/10/2026)

- Tout test, bilan ou rapport sur un moteur (alpha, omega, dc, …) utilise UNIQUEMENT les matchs que le moteur a réellement tournés : paris des journaux gelés AVANT le coup d'envoi, sur des matchs terminés. Jamais d'archive, de rejeu, de backtest ni de matchs à venir, sans que Patrick ait à le préciser.
- Pour alpha, seulement les marchés que la page affiche vraiment (règle `af-alpha-selection.js`). Utiliser `python bilan_reel.py [--solidite-min 0.78]` ; ne pas recompter à la main.
- Tout rapport annonce le nombre de matchs, de paris et la période ; ne pas citer le nombre de lignes de journal comme un nombre de matchs.
- Si la période est courte ou l'échantillon petit, le dire. Les poids de la Solidité sont appris sur l'archive : le préciser quand elle sert de filtre.
