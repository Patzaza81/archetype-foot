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
- Moteur Gamma (depuis le 02/11/2026 ; page `pronostics_gamma.html`, code `moteur_omega_v3/`) : exploration ouverte de la spécification « Omega V1 » (4 séquences au même lieu : minimum 5 matchs, 19 derniers au plus, depuis le 03/11/2026 ; n_A²·n_B² scénarios, paliers de compatibilité défensive, marchés générés depuis les scores, stabilité par retrait d'une observation) ; sélection = fréquence robuste ≥ seuil par marché appris sur l'archive (cible 70 %), cote ≥ 1,26 obligatoire, jamais deux fois le même événement, « AUCUN MARCHÉ RETENU » est valide ; fréquence ≠ probabilité ; autonome, hors tickets ; journal gelé `data/gamma/journal.jsonl.gz` (compressé depuis le 27/11/2026 : le .jsonl dépassait 100 Mo, limite GitHub) : `docs/MOTEUR_OMEGA_V3.md`. Ancien moteur DC conservé sans modification (historique) : `docs/MOTEUR_DC.md`
- Moteur Europe = Europe-Gamma (depuis le 03/11/2026 ; page `pronostics_europe.html`, code `moteur_europe_gamma/`) : méthode Gamma sur trois échantillons au même lieu (20 % saison européenne passée = 5 derniers, 30 % championnat en cours, 50 % Europe en cours), poids renormalisés si un échantillon manque (aucun minimum pour la saison en cours, 3 matchs pour la saison passée, 2 échantillons minimum), observations pesées par la force réelle de l'adversaire, enjeu réel calculé sur le classement de la phase de ligue (enjeu nul = affiché seulement, match non exclu) ; sans calibrage = aperçu non calibré compté à part ; autonome, hors tickets ; journal gelé `data/europe_gamma/journal.jsonl` : `docs/MOTEUR_EUROPE_GAMMA.md`. Ancienne page conservée : `pronostics_europe_ancien.html`
- Moteur Megapower v2 (refonte du 18/11/2026, SANS AUCUNE COTE ; page `pronostics_megapower.html`, code `megapower/`) : but = le maximum de pronostics vrais et constants, jamais battre la cote ; buts attendus (xG, adversaires, tendance, écart au classement, 4 matchs minimum au même lieu) → grille Poisson/Dixon-Coles → 3 scénarios (favorable, normal, catastrophe) → calibrage par famille sur les résultats réels → pronostics retenus si fiabilité calibrée (borne basse 95 %) ≥ `config/megapower.json` ; tous les paramètres du modèle sont appris sur les données (aucun posé à la main, sauf ce seuil) ; jamais deux fois le même événement ; « aucun pronostic » est valide ; autonome, hors tickets ; journal gelé `data/megapower/journal_v2.jsonl` (l'ancien `journal.jsonl` de la v1 fondée sur les cotes n'est plus alimenté) ; moteurs désactivés dans `config/moteurs_desactives.json` : `docs/MOTEUR_MEGAPOWER.md`
- Sources de calendrier de secours (depuis le 11/11/2026 ; code `sources_calendrier/`) : hiérarchie matchendirect (principale) > espn > openfootball dans `config/sources_calendrier.json`, format commun `Match`, un fichier par source, rapprochement un pour un (le doute = « ambigu »), noms d'équipes réglés dans `config/sources_noms.json` ; mode « mesure » seulement (rien n'alimente le système) : `docs/SOURCES_CALENDRIER.md`
- Moteur Selections (depuis le 13/11/2026 ; code `moteur_selections/`, branche `moteur-selections`, non fusionné) : qualifications Coupe du monde des sélections nationales, méthode d'Analyse Verdict (même lieu, 4 matchs minimum par équipe, cote ≥ 1,26, terrain neutre non évaluable, pas de xG) ; fenêtre et périmètre choisis sur les données (`etude_parametres.py`) ; données publiques gratuites, la collecte commune exclut les sélections ; cœur seulement (ni cotes, ni journal, ni page, ni pipeline) : `docs/MOTEUR_SELECTIONS.md`

- Onglet « Étude » d'Analyse Verdict (depuis le 21/11/2026 ; `verif_etude.py`, `data/verif_pronostics/etude_regles.json`, branche `onglet-etude`) : condition « le double des buts marqués + une meilleure défense » (écart mince / moyen / grand), marchés retenus seulement s'ils dépassent 70 % dans l'étude sur matchs joués, sélection gelée « etude » : `docs/ETUDE_DOUBLE_DEFENSE.md`

- Onglet « +1,5 buts » d'Analyse Verdict (depuis le 21/11/2026, fusionné ; `verif_regle_buts.py`, `data/verif_pronostics/regle_buts.json`) : ne montre QUE les matchs qui remplissent la règle d'admission (buts marqués cumulés ≥ 3,5 et encaissés cumulés ≥ 2,8, 4 matchs au même lieu, filtre du championnat) avec le marché plus de 1,5 buts coté ≥ 1,24 (seuil propre à cet onglet ; autres onglets : 1,26), sans verdict affiché ; les mêmes matchs sont dans l'onglet Étude ; sélections gelées « plus15 » et « regle_buts » : `docs/REGLE_BUTS_PLUS_1_5.md`

- Onglet « +2,5 buts » d'Analyse Verdict (depuis le 23/11/2026 ; `verif_regle_plus25.py`, `data/verif_pronostics/regle_plus25.json`) : règle de l'étude sur les paramètres de Patrick (championnat ≥ 2,88 buts par match, différence de buts domicile − extérieur ≥ 1,09, l'équipe à domicile marque dans ≥ 60 % de ses matchs chez elle, l'extérieur marque ≤ 1,33 dehors, 4 matchs au même lieu) ; la cote n'entre pas dans la règle, seulement à la fin (≥ 1,26) ; aucun autre onglet modifié ; sélection gelée « plus25 » : `docs/REGLE_BUTS_PLUS_2_5.md`

- Onglet « Catégories » d'Analyse Verdict (depuis le 24/11/2026 ; `verif_categories.py`, `data/verif_pronostics/categories_zones.json`, branche `onglet-categorisation`) : à partir de la fiche (4 piliers au lieu du match + xG sur tous les lieux relatif au championnat), le match est classé dans les intervalles favorables de 11 marchés, un seuil et un ensemble d'intervalles par marché (victoire domicile 70 %, victoire extérieur 60 %, +1,5 77 % (règle des 2 buts de Patrick du 25/11 : chaque équipe a marqué 2+ buts dans ≥ 40 % de ses matchs à son lieu, 5 matchs minimum), X1 90 %, X2 75 %, domicile marque 90 %, extérieur marque 80 %, combinés), cote ≥ 1,26 seulement à la fin (1,24 pour le plus de 1,5 seulement ; pour les autres marchés, s'ajoutent les 3 meilleurs sur 4 jours cotés 1,24 ou 1,25 : décisions de Patrick du 24/11), intervalles figés le 24/11 sur 2000-2016 et mesurés sur 2017-2020 et 2025-26 ; sélection gelée « categories » : `docs/CATEGORIES_INTERVALLES.md`

- Règle « moins de 3,5 buts » de l'onglet Catégories (Patrick, 26/11/2026) : EN PLUS de l'intervalle de la catégorie, le moins de 3,5 buts (combos compris) est écarté si buts marqués par match du domicile à domicile + de l'extérieur à l'extérieur > 3,1 ; autres onglets inchangés (`verif_pronostic.moins35_refuse`) : `docs/REGLE_MOINS_3_5.md`

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
