# Moteur v

> Conception, tests subis, résultats et suivi : voir `docs/MOTEUR_V_HISTORIQUE.md` (à lire avant toute modification).

- **Code** : `moteur_v/` (stdlib seulement). **Page** : `pronostics_v.html` + `archetype_v.js` (menu « V »). **Données** : `data/v/`.
- **Autonome** : lit seulement `data/archive_test/` (cotes BetPawa, historiques, scores) ; écrit seulement `data/v/`. Ne dépend d'aucun autre moteur (test `test_independance_v_ne_depend_d_aucun_autre_moteur`).
- **Exécution** : chaque nuit, à la fin de `enregistre_scores_historique.py` (`moteur_v.execution.passage_nocturne`, dans un `try` : jamais bloquant, après v2r). À la main : `python -m moteur_v.execution`.

## Sortie : pronostic principal + « autres »
- **Principal** : le marché au plus fort score du modèle. **La cote ne choisit pas** (cote minimale 1,26, règle de Patrick).
- **Autres** : jusqu'à 5 pronostics aussi acceptables (score modèle >= 70 %, cote >= 1,26, marché différent). Deux marchés qui gagnent sur exactement les mêmes scores sont fusionnés (ex. Handicap +0,5 domicile = Double chance 1X).
- **Score du modèle** = moyenne de deux probabilités de marché : (1) Poisson avec la **force des adversaires affrontés** (forces d'attaque/défense ajustées sur tous les matchs archivés strictement avant la date, rétrécies vers 1 par 3 matchs fictifs) ; (2) **calcul simple** : buts attendus = (marqués d'une équipe + encaissés de l'autre) / 2 au même lieu.
- **Fiabilité AFFICHÉE = fiabilité mesurée par zone de cote**, jamais le score brut (trop optimiste de 20 points à cote 1,49–1,81) :

| Zone de cote | Niveau | Fiabilité mesurée (440 matchs, 28/09 au 14/10) |
|---|---|---|
| 1,26–1,37 | SÛR | 74,8 % |
| 1,37–1,49 | MOYEN | 65,5 % |
| 1,49–1,81 | RISQUÉ | 54,3 % (IC95 bas 38 %) |
| > 1,81 | NON CALIBRÉ | 37,5 % (8 paris) : à éviter |

- **Verrou d'échantillon (inchangeable, Patrick)** : >= 4 matchs au même lieu pour les DEUX équipes, sinon match exclu ; k = 0,8 (4), 0,9 (5), 1,0 (6+) ; fenêtre des 12 derniers matchs au lieu.
- **Alertes (information, jamais un filtre)** : musique instable / pic / rupture ; côté parié (1X2, double chance) très défavorisé aux points (écart de points par match / 3 <= −0,30) ou au classement (écart de rang normalisé <= −0,40).
- **Classement** : reconstruit sans fuite depuis les historiques archivés (partiel : médiane 11 équipes connues par championnat). À remplacer par le vrai classement dès qu'il est archivé à chaque match. L'écart de points et l'écart de rang sont corrélés à 0,94 : ils portent la même information.

## Présentation pour un parieur (16/10/2026)
La page n'affiche plus le vocabulaire du moteur. Par pari : un **verdict** en un mot (SOLIDE / MOYEN / RISQUÉ / NON ÉVALUÉ = niveaux SÛR / MOYEN / RISQUÉ / NON CALIBRÉ), « sur 100 paris comme celui-ci, environ N passent », le **seuil pour ne pas perdre** (100 / cote) avec une jauge, le gain ou la perte moyenne estimée pour 1 000 F misés (réussite mesurée × cote − 1), les buts attendus, la fréquence du pari chez chaque équipe au lieu, des alertes en clair, puis « Autres paris possibles ». Le « score du modèle » (trop optimiste) n'est plus qu'en « Détails techniques ». Filtres Solides / Moyens / Risqués. Forme : G/N/P avec le score toujours du point de vue de l'équipe. Les alertes de forme « pic » et « instable » (présentes sur presque chaque match) sont reléguées aux détails ; seule la « rupture » reste visible. Rien ne change dans le calcul : présentation uniquement.

## Plancher du pronostic principal (version 2026-10-16b)
- `PLANCHER_PRINCIPAL = 0,50` (`modele.py`). Si même le meilleur pari du modèle a un score sous 50 %, **aucun pronostic principal** : le match n'entre pas au carnet, il est listé sur la page sous « Sans pronostic fiable » (`sans_pronostic` dans `pronostics_v.json`).
- Origine : le 16/10/2026, Alashkert – Syunik affichait « Match nul ou Syunik » (cote 3,45) avec un score de 17 % : le moteur n'avait que 3 paris lisibles, tous très bas, et prenait le moins mauvais. Défaut de conception (aucun minimum), corrigé. Sur 261 pronostics du jour, 1 seul était concerné.
- Un pronostic déjà écrit mais non figé qui passe sous le plancher est **retiré** du carnet ; l'ancienne version et le retrait restent dans `historique/versions/` (ligne `retire: true`).
- Le plancher ne touche ni le test à l'aveugle (règles S et V), ni les zones de fiabilité.

## Carnet et statut
- `data/v/carnet.json` : un pronostic par match, écrit **avant le coup d'envoi**, figé ensuite, score ajouté une seule fois. Principal et autres sont réglés séparément. **Sans coup d'envoi connu : jamais écrit** (garde contre les cotes prises en cours de jeu : 38 matchs de l'archive de test en avaient).
- Sortie publiée : `data/v/pronostics_v.json`. Bilan par rôle (principal / autres) et par niveau : réglés, réussite, fiabilité annoncée, écart, IC95 Wilson, ROI.
- **Statuts** : `observation` (< 100 paris principaux réglés : ne pas miser) ; `controle_ok` (>= 100 réglés, fiabilités tenues) ; `gel` (un niveau SÛR/MOYEN/RISQUÉ a une réussite réelle inférieure de plus de 10 points à sa fiabilité annoncée, sur >= 50 paris). **Aucun statut ne dit « rentable »** : le ROI au carnet est affiché, pas jugé.

## Historique durable (pour analyse)
Le carnet est l'état du jour ; l'historique en est la mémoire. Règle : **on ajoute, on ne réécrit jamais** (`moteur_v/historique.py`, fichiers `.jsonl`, une ligne = un fait). Il est écrit par `moteur_v/execution.py` à chaque passage et committé par les workflows avec `data/`. Le moteur ne le relit jamais pour décider un pronostic.
- `data/v/historique/versions/AAAA-MM.jsonl` : chaque version d'un pronostic avant le coup d'envoi (principal, autres, niveau, cote, `vu_le`). Écrite seulement si le pronostic change (signature = principal, autres, version des paramètres).
- `data/v/historique/reglements/AAAA-MM.jsonl` : chaque match réglé, **une seule fois** : pronostic figé, score, résultat et profit de chaque pari, **tous les marchés lus** avec probabilités (`pf` force, `ps` calcul simple, `pm` mixte), cote, scores de lieu `sh`/`sa`, coefficient `k`, lambdas des deux modèles, contexte (écarts de points et de rang), alertes, version des paramètres. C'est la base pour refaire toute analyse (calibration, seuils, rôle de chaque modèle) sans rejouer le passé.
- `data/v/historique/bilans.jsonl` : un instantané du bilan (par rôle et par niveau) à chaque changement ; sert à voir la dérive de la calibration dans le temps.
- Contrôle d'intégrité : `historique.verifie(dossier)` (fichier illisible, match réglé deux fois, réglé sans score). Ne jamais éditer ces fichiers à la main ; une correction se fait par une nouvelle ligne.
- Limite : les matchs réglés avant le 16/10/2026 n'ont pas le détail « tous les marchés » (le carnet ne le contenait pas) ; le détail commence avec le premier passage de cette version.

## Ce que les mesures disent (à ne pas oublier)
- Le pourcentage des fréquences brutes n'apporte rien en plus de la cote (coefficient ≈ 0). Le modèle (forces + calcul simple) a une erreur de prédiction meilleure que les fréquences brutes (0,603 contre 0,669) mais pas meilleure que la cote seule (0,586).
- La cote surestime les chances d'environ 4 à 6 points (marge du bookmaker) : à cotes 1,26–1,37, le seuil de rentabilité est ~77 % pour 75 % de réussite mesurée.
- Les fiabilités par zone sont mesurées **en échantillon** (440 matchs, 17 jours) : seul le carnet fait foi.
- Test à l'aveugle figé le 16/10/2026 : règle « Valeur » (cote 1,45–1,85, calcul simple >= 75 %) et mode « Sûr » (seuil 0,76 calibré) ; ADOPTÉE seulement si >= 100 paris, ROI >= +5 % et réussite > moyenne de 1/cote. Date de décision estimée : autour du 20/11/2026.

## Changer le moteur
Changer une règle = incrémenter `PARAMETRES_VERSION` (`modele.py`), mettre à jour ce document et `tests/test_moteur_v.py`. Les fiabilités par zone ne se modifient qu'avec une nouvelle mesure datée.

Tests : `tests/test_moteur_v.py`.
