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
