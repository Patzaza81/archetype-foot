# Matrice évolutive de découverte de scénarios — version expérimentale

## Statut et limites

La matrice est un laboratoire indépendant et en lecture seule. Elle ne modifie ni les moteurs V2/V3/V2R/Europe, ni le Journal, ni le pipeline, ni les pronostics publiés. Aucune règle n'est automatiquement promue. Le but est de découvrir des relations candidates et de les soumettre à une validation chronologique indépendante.

## Lancement

Le format normalisé est disponible pour les jeux de recherche. Un adaptateur direct lit aussi `data/archive_test/*.json.gz` (SCHEMA_VERSION 2), uniquement les matchs résolus avec score, et récupère l'historique d'équipe conservé avant-match. Il mappe les cotes 1X2, double chance, BTTS, totaux et buts par équipe uniquement via les clés exactes de `parse_betpawa.py` / `moteur_europe/cotes_archive.py` ; tout marché non mappé reste sans cote.

**Preuve pré-match (archive).** Un match n'est utilisé que si sa capture (`run.pris_le`, qui porte cotes, classement et historique) est strictement antérieure à son coup d'envoi (`coup_d_envoi_utc`). Sont exclus et comptés dans `rejected` : `CAPTURE_APRES_COUP_D_ENVOI`, `COUP_D_ENVOI_ABSENT` (antériorité non démontrable) et `CAPTURE_SANS_HORODATAGE`. Un classement n'est gardé que si `classement_horodatage` précède le coup d'envoi ; sinon le rang est ignoré. Les jeux normalisés fournis sans `snapshot_at` suivent le contrat ci-dessous : leur provenance pré-match est déclarée par l'appelant, la matrice ne peut pas la prouver.

```bash
python -m matrice_scenarios.cli data/archive_test --output rapport_matrice_scenarios.json --walk-forward
python -m matrice_scenarios.cli chemin/vers/matchs_normalises.json --output rapport_matrice_scenarios.json --max-candidates 20000
pytest -q tests/test_matrice_scenarios.py
```

Le fichier d'entrée peut être :
- un tableau JSON de matchs ;
- un objet JSON `{"matches": [...]}` ;
- un fichier JSONL, un match JSON par ligne.

## Contrat d'un match normalisé

Champs obligatoires : `match_id`, `date` (AAAA-MM-JJ), `home_team`, `away_team`, `home_goals`, `away_goals`. Le score final sert uniquement à évaluer la cible, jamais à construire les variables pré-match.

Champs facultatifs :
- `league`, `home_rank`, `away_rank`, `home_odds`, `draw_odds`, `away_odds` ;
- `home_history` et `away_history`, listes chronologiques ou non de matchs antérieurs. Chaque élément contient `date`, `goals_for`, `goals_against`, et éventuellement `venue` (`home` ou `away`) et `opponent_rank` ;
- `snapshot_at` et `kickoff_at` (ISO 8601, facultatifs) : si `snapshot_at` est présent, la capture doit précéder `kickoff_at`, sinon le match est refusé ;
- `target_odds`, dictionnaire des cotes réellement observées avant le coup d'envoi, indexé par l'identifiant exact de la cible ;
- `prematch_features`, signaux numériques pré-match dont le nom commence par `pre_`. Chaque variable ajoutée doit avoir une provenance documentée et être connue avant le coup d'envoi.

Exemple de structure (valeurs illustratives pour décrire le format, pas une preuve ni un résultat historique) :

```json
{
  "match_id": "source-id-unique",
  "date": "2026-10-01",
  "league": "Nom exact de la compétition",
  "home_team": "Équipe domicile",
  "away_team": "Équipe extérieur",
  "home_goals": 1,
  "away_goals": 0,
  "home_rank": 5,
  "away_rank": 12,
  "home_odds": 1.8,
  "draw_odds": 3.2,
  "away_odds": 4.2,
  "home_history": [
    {"date": "2026-09-24", "goals_for": 0, "goals_against": 2, "venue": "away"},
    {"date": "2026-09-18", "goals_for": 2, "goals_against": 1, "venue": "home"}
  ],
  "away_history": [],
  "target_odds": {"home_not_lose": 1.25},
  "prematch_features": {"pre_rest_days_home": 6}
}
```

## Variables générées

- Classement : écart signé (positif = domicile mieux classé), écart absolu et rangs si disponibles.
- Historique par fenêtres 2, 3, 5, 8 et 10 : buts pour/contre, différence de buts, taux de marquer, concéder, gagner, ne pas perdre et Over 2,5.
- Séquences : séries de défaites, de non-défaites, de buts marqués, de matchs sans but ; dernier résultat, défaite précédente à domicile/extérieur, défaite lourde, match précédent sans but, match précédent à 2+ buts, 3+ buts encaissés, mauvaise série sur 3 matchs et candidat de reprise.
- Splits domicile/extérieur quand la source les renseigne ; confrontations directes historiques uniquement sur les noms normalisés exacts et les dates antérieures au match.
- Cotes et probabilités implicites 1X2 normalisées sans marge, utilisées comme variables explicatives, pas comme certitude.
- Championnat exact et variables numériques documentées `pre_*`.

Les variables d'historique sont recalculées en ignorant systématiquement toute rencontre datée le jour du match cible ou après. Les variables de classement et de cote présentes au niveau du match doivent, elles aussi, correspondre à l'état pré-match ; la matrice ne peut pas vérifier seule la provenance externe de ces champs.

## Recherche et cibles

La recherche génère des conditions numériques `>=` / `<=`, des conditions exactes de championnat, et des combinaisons de deux ou trois conditions portant sur des variables distinctes. Le budget (`--max-candidates`, 20 000 par défaut, compté en scénarios = règle × cible) est réparti 40 % règles simples, 40 % paires, 20 % triplets. Les règles simples sont prises en tourniquet sur toutes les variables ; les paires et triplets sont échantillonnés de façon déterministe (graine fixe `DISCOVERY_SEED`) parmi toutes les conditions admissibles, jamais en tronquant un produit cartésien trié (cette troncature faisait partir 100 % des paires d'une même condition). Deux règles qui sélectionnent exactement les mêmes matchs de découverte ne comptent qu'une fois. Les seuils sont tirés d'une grille interprétable et de quantiles du seul segment de découverte. Le rapport publie `exploration` (règles distinctes, variables utilisées et jamais utilisées, part de la condition la plus répétée, règles dynamiques) : le budget n'est pas la couverture, et le système ne prétend pas épuiser toutes les combinaisons possibles.

Cibles : 1X2, double chance sans défaite, buts d'équipe (1+, 2+, 3+), les deux équipes marquent et totaux de buts 1,5 / 2,5 / 3,5. D'autres cibles ne sont ajoutées que lorsque les scores et les cotes correspondantes peuvent être réglés sans ambiguïté.

## Validation et statut

- Dédoublonnage par `match_id`. Des copies dont les équipes ou le score se contredisent sont exclues et comptées. Pour l'archive, un même match listé deux jours (date décalée) n'est pas une contradiction : la copie conservée est la capture la plus tardive encore antérieure au coup d'envoi (`date_shifted_duplicates`).
- Séparation chronologique : 60 % découverte, 20 % validation, 20 % test final, avec des coupures alignées sur un changement de date (aucun jour partagé entre deux segments ; `days_shared_between_splits` doit valoir 0). Aucun mélange aléatoire.
- Support minimum de découverte : 30 matchs déclenchés. Support minimum sur chacun des segments validation et test : 30 matchs ; en dessous, le scénario reste `ECHANTILLON_INSUFFISANT`.
- Intervalle de Wilson à 95 % pour le taux de réussite.
- Par scénario et par segment : effectif, taux de réussite, Wilson, nombre de paris réglés (`settled_bets`, cote réelle de la cible exacte), cote moyenne réelle (`mean_odds`), ROI net à mise plate (`roi`) et son intervalle approximatif à 95 % (`roi_ci95`), taux implicite du marché (`market_implied_rate`) et écart (`edge_vs_market`). Le taux implicite est sans marge pour le 1X2 (trois cotes du match) et brut, marge incluse, pour les autres marchés. Le taux de base du segment est comparé via `*_lift`.
- Sélection gelée (`selected_on_validation`) : q Benjamini-Hochberg de découverte ≤ 0,10, au moins 30 matchs en validation et écart positif au taux de base en validation. Le test n'entre dans aucun critère ni dans le tri (tri par écart au taux de base en validation). Le rapport compare le test des scénarios retenus à un groupe témoin (candidats non retenus), avec et sans variables de marché (`selection`).
- Validation glissante (`--walk-forward`) : trois origines croissantes (60 %, 80 %, 100 % de la chronologie), chaque pli rejouant découverte, sélection et test sur son préfixe ; les segments test des plis sont disjoints. Avec peu de jours distincts ce ne sont pas des saisons indépendantes.
- Les listes de matchs ne sont conservées que pour les 200 meilleurs candidats (le rapport pesait 108 Mo pour 5 000 scénarios).
- Correction Benjamini-Hochberg sur les valeurs p approximatives pour limiter les faux positifs. Ces p-values sont un outil de tri seulement : elles ne constituent pas une preuve de significativité finale.
- ROI calculé uniquement quand une cote `target_odds` explicite et valide existe pour la cible exacte. Aucune cote n'est inventée ou substituée.
- `A_VALIDER` signifie uniquement que les deux segments ont un support minimal, pas que le scénario est rentable, significatif ou promu.
- `promotion_allowed` reste toujours faux dans cette version. La validation finale exige revue humaine, volume suffisant, comparaison au taux de base et au marché, et test hors échantillon gelé.

## Limites connues à traiter avant la production

1. Adapter et tester un convertisseur à chaque source réelle (archives de pronostics, résultats, cotes) ; ne pas joindre les données sur des noms approximatifs. Seul l'adaptateur `data/archive_test` est implémenté et vérifié.
2. Mesurer les observations manquantes, la qualité des identifiants et les scores contradictoires sur chaque nouvelle source. Pour l'archive, la date de capture est prouvée par `run.pris_le` et `classement_horodatage` ; une source sans horodatage ne permet pas de prouver l'antériorité.
3. Étendre la validation glissante à des périodes réellement indépendantes (saisons, ligues) et ajouter une estimation par match pour tenir compte des marchés corrélés (les 16 cibles d'une même règle ne sont pas indépendantes).
4. Ajouter les tests de permutation, la stabilité par saison/ligue et la comparaison au marché avec intervalles par match.
5. Étendre prudemment au-delà des paires de conditions, avec recherche beam/association ou arbres peu profonds et budget déterministe ; ne pas faire une recherche exhaustive exponentielle.
6. Ne jamais connecter la sortie au générateur de tickets ou au pipeline avant un banc historique indépendant, un jeu final jamais utilisé et une décision explicite.

## Principe immuable

Les scénarios sont des hypothèses qui peuvent être inventées, combinées, transformées, testées puis abandonnées. Un exemple humain n'est jamais une règle standard imposée au système. L'absence de données donne « inconnu », jamais une supposition.


## Validation statistique (module isolé, lecture seule)

- `matrice_scenarios/football_data.py` : adaptateur Football-Data, résultats seulement, aucune cote lue.
- `matrice_scenarios/validation.py` : moteur vectorisé (numpy), permutations imbriquées (nuls « marché » et « libre »), max-T, un pari par match, bootstrap par jour, verdict à critères fixés d'avance.
- `matrice_scenarios/validate.py` : CLI `python -m matrice_scenarios.validate` (walk-forward archive, walk-forward Football-Data, transfert de règles gelées, `--freeze-forward`, `--evaluate-frozen`).
- Preuve exigée : ≥ 56 jours, ≥ 300 paris réglés, ROI > 0, IC95 par jour excluant 0, p marché ≤ 0,05, ≥ 2/3 des blocs de dates positifs. Sinon DONNEES_INSUFFISANTES, NON_CONCLUANT ou NON_RENTABLE.
- Résultats : `docs/RAPPORT_VALIDATION_MATRICE_2026-10-18.md`. Tests : `tests/test_matrice_validation.py`.
- Toujours `promotion_allowed=false`, aucune liaison aux moteurs, au Journal ni au pipeline.

## Page « Moteur alpha (ex-Comportement) » (19/10/2026)
- Page : `pronostics_comportement.html` + `archetype_comportement.js` + `af-comportement.css` (même habillage que les autres moteurs). Elle lit `data/comportement/pronostics_comportement.json`.
- Données : `python -m matrice_scenarios.page_comportement` (lecture de `data/archive_test/`, comme la V3). `--seuils` recalcule les seuils mesurés (`docs/parametres_comportement.json`).
- Contenu par match : tendances (résultat, buts, deux marquent, scores extrêmes), pronostic principal, puis le meilleur pronostic de chaque autre tendance présente, si cote ≥ 1,26 et probabilité ≥ quartile bas des pronostics principaux (mesuré). 3 onglets au plus.
- Bandeau : réussite mesurée (69,5 %, intervalle 66–74 %) ; la probabilité du modèle est surestimée d'environ 10 points.
- Rien n'est branché à V2/V3/V2R/Europe/Journal/pipeline ; `promotion_allowed=false`. Les menus des autres pages ne sont pas modifiés (pas de lien vers cette page depuis elles).

### Mise à jour 19/10 (avis du conseil sur les variantes)
- Tendances ajoutées : buts du domicile et buts de l'extérieur (probabilité de 0, 1, 2, 3+ buts, tirée de la grille). « Les deux marquent » ne contient plus que le BTTS ; les cages inviolées sont rangées avec les buts de l'équipe concernée (cage de l'extérieur inviolée = le domicile ne marque pas).
- Pas de doublon : deux sélections qui gagnent sur exactement les mêmes scores sont le même événement (`evenement()`), on garde un seul.
- Jusqu'à 5 onglets (principal + une sélection par autre tendance qui passe les filtres).
- Mesure sur l'archive jouée : pronostics des autres tendances 66 à 71 % de réussite selon la tendance, comparable au principal (69,5 %).
- Menu : lien « Comportement » ajouté aux pages qui ont le menu des moteurs (index, V2, V3, V2R, V, Europe, Journal, Panier).

### Clôture du chantier « Comportement » (19/10, suivi des propositions du conseil)
- Seuil par tendance, mesuré (plus de seuil global) : plus petite probabilité à partir de laquelle les pronostics de la tendance ont réussi au moins autant que les pronostics principaux (66,7 % sur la 1re moitié de l'archive, 40 cas minimum). Sans tel seuil, la tendance ne propose pas de pronostic secondaire.
- Résultat sur la 2e moitié (jamais vue) : Résultat 63,7 % (342 cas), Buts du match 66,8 % (307 cas). Buts du domicile, buts de l'extérieur, les deux marquent : aucun seuil ne tient la cible → pas de pronostic secondaire pour ces tendances (elles restent affichées comme explication).
- Existence d'une tendance d'équipe (classe la plus probable ≥ tertile haut, 0,361) : validée sur les 40 % de Football-Data non utilisés, effet très faible (35,8 % au-dessus du seuil contre 34,2 % en dessous). À ne pas surinterpréter.
- Limites : volumes faibles (quelques centaines de cas), probabilités du modèle surestimées d'environ 10 points, réussite du principal 69,5 % (IC 66–74 %) pour une cote moyenne de 1,39, sous le seuil de rentabilité (~72 %).
- Prochaine étape unique : suivi en conditions réelles sur de nouveaux matchs, moteur figé.

### Suivi et archivage (19/10)
- Journal en ajout seul : `data/comportement/journal_comportement.jsonl` (une ligne « pronostic » figée avant le coup d'envoi, puis une ligne « resultat » ; aucune ligne n'est jamais modifiée). Chaque pronostic porte l'heure de gel, le commit du code et l'empreinte des paramètres.
- Commandes : `python -m matrice_scenarios.suivi_comportement geler | resultats | bilan | tout`. Un match dont le coup d'envoi est passé n'est jamais gelé.
- `bilan_suivi.json` : réussite calculée uniquement sur les pronostics gelés (le vrai test hors échantillon).
- Pas automatisé : à lancer chaque jour (geler avant les matchs, résultats ensuite). Aucun lien avec le pipeline.

### Lancement automatique (19/10)
- `python -m matrice_scenarios.suivi_comportement quotidien` : récupère l'archive la plus récente de `origin/main` (copie temporaire, rien n'est fusionné ni modifié sur main), gèle les nouveaux pronostics, enregistre les résultats connus, met à jour `bilan_suivi.json` et les données de la page. Idempotent. Ne fait ni commit ni push.
- Planification : tâche programmée deux fois par jour (≈ 01:27 et 07:27 heure de Douala), après la chaîne de collecte (21:00 UTC) et le journal (05:07 UTC). Elle committe et pousse uniquement sur la branche `matrice-decouverte-scenarios`.
- Les workflows GitHub planifiés ne tournent que depuis la branche par défaut (main) : on ne les utilise pas, main reste intouché.

### Banc contre le marché sur Football-Data (19/10)
- Les fichiers bruts de Football-Data contiennent des cotes (Bet365, Pinnacle, Betfair, moyenne/max ; ouverture et clôture ; 1X2, plus/moins 2,5, handicap asiatique). Dans nos données locales : 7 622 matchs avec cotes 1X2 et plus/moins 2,5 (Bet365 ouverture).
- Elles sont lues uniquement pour JUGER le moteur (`python -m matrice_scenarios.banc_cotes_football_data`), jamais pour calculer un pronostic. La décision du 24/09 (aucune cote collectée par la couche de données) reste valable pour la collecte et les moteurs.
- Résultat (1 624 matchs de test, jamais utilisés pour le réglage) : 1X2, log-vraisemblance modèle −1,046 contre marché −0,996 ; plus/moins 2,5, Brier modèle 0,2493 contre marché 0,2416 : le moteur est moins bon que le marché. Règle « plus probable, cote ≥ 1,26 » sur ces 5 marchés : 53,2 % de réussite (annoncé 56,2 %), cote moyenne 1,83, ROI à plat −5,2 %.
- Lecture : avec 5 marchés en concurrence, la surestimation est de 3 points ; avec la vingtaine de groupes BetPawa elle est de 10 points → le biais vient du nombre de marchés mis en concurrence.

### Bloc de saisons pour tester les moteurs (19/10)
- Règle du 24/09 levée pour l'évaluation et le calibrage (voir `docs/CLAUDE_DATA.md` et `data/football_data/CONTRAT.md`) : les cotes des CSV bruts Football-Data peuvent juger les moteurs, jamais calculer un pronostic.
- Bloc : `data/bloc_saisons/bloc_2526_2627.json.gz` (16 558 matchs du 23/01/2025 au 16/10/2026 : saison 2526 complète + 2627 en cours + nouvelles ligues), construit par `python -m matrice_scenarios.bloc_saisons construire`. Contenu : score, statistiques de match, cotes Bet365 / Pinnacle / moyenne / maximum, ouverture et clôture (1X2 clôture 16 558 matchs ; ouverture, plus/moins 2,5 et handicap asiatique ≈ 9 200).
- `bloc_saisons.entree(bloc, match, n)` : historique strictement antérieur au match, sans fuite (testé).
- Saison 2425 : absente du dépôt et non téléchargeable depuis cet environnement (le réseau n'autorise pas football-data.co.uk). Il faut lancer `archive_football_data.py` là où le réseau est ouvert (workflow GitHub) ou fournir les CSV ; le bloc se reconstruit ensuite avec `SOURCES["2425"]`.
- Jugement du moteur Comportement contre le marché moyen (5 624 matchs de test, 40 % les plus récents) : 1X2 clôture −1,055 contre −1,003 ; plus/moins 2,5 Brier 0,2478 contre 0,2385 ; handicap asiatique (demi-lignes) 0,2693 contre 0,2492. Le moteur est moins bon que le marché sur les trois.
