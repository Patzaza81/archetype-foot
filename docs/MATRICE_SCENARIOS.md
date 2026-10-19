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
- Lancement : voir « Lancement automatique » ci-dessous (étape du pipeline nocturne depuis le 19/10/2026).

### Lancement automatique (19/10)
- `python -m matrice_scenarios.suivi_comportement quotidien` : récupère l'archive la plus récente de `origin/main` (copie temporaire, rien n'est fusionné ni modifié sur main), gèle les nouveaux pronostics, enregistre les résultats connus, met à jour `bilan_suivi.json` et les données de la page. Idempotent. Ne fait ni commit ni push.
- **Intégration au pipeline (19/10/2026, sur ordre de Patrick)** : `python -m matrice_scenarios.suivi_comportement pipeline` est une étape du pipeline nocturne (`.github/workflows/pipeline.yml`, après la comparaison V2/V3), avec `continue-on-error: true` : une panne d'alpha ne peut pas arrêter le pipeline. Elle lit l'archive du dossier de travail (sans git), gèle les nouveaux pronostics, enregistre les résultats, met à jour `bilan_suivi.json` et la page. Le commit « Mise à jour pipeline » publie `data/comportement/` avec le reste. Ne tourne jamais sur un run de panier.
- **Statut : production parallèle**, comme V3 : page, données et journal publiés, **hors tickets** (`generateur_tickets.SOURCES` = V3 et Journal seulement), hors fichier de comparaison V2/V3, aucune cote en entrée du moteur. Une entrée dans les tickets exige une décision séparée de Patrick et une preuve de rentabilité (seuil ≈ 72 % pour une cote moyenne de 1,39 ; observé : 69,5 % sur l'archive, IC95 65,5–74,2 %).
- L'ancienne tâche programmée « Suivi Comportement » (branche `matrice-decouverte-scenarios`) est désactivée : deux écrivains sur le journal en ajout seul le feraient diverger. La commande `quotidien` (archive de `origin/main` dans une copie temporaire) reste disponible pour un lancement manuel.

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

## Réglage du moteur alpha — tous les marchés (conseil du 19/10/2026)

Méthode : la grille de scores donne tous les marchés, donc la log-vraisemblance du score exact et le calibrage par famille se jugent sur les SCORES, sans cote.
Découpe chronologique du bloc Football-Data : 4 060 matchs anciens pour régler, 10 000 suivants pour tester (`evaluer_bloc_grand_test`). Cotes : jugement seulement.

- **Calibrage par famille (10 000 matchs)** : bien calibrés = 1X2, double chance, totaux par équipe, handicaps demi-lignes, handicap 3 issues (biais ≤ ~1 point).
  À corriger : « plus de 2,5 » sous-estimé de 2,7 points, BTTS « oui » de 1,4 point. Sans signal : pair/impair, nombre exact de buts, score exact (gain ≤ 0,2 % sur la fréquence de base).
- **Découpage par championnat** : refusé. Dispersion réelle entre championnats (0,009) inférieure à l'erreur-type par championnat (0,010 à 0,030).
- **Structure** (log-vraisemblance du score exact, test 10 000) : fenêtre complète +0,0165 ± 0,0023 par rapport à 5 matchs (confirmé sur l'archive : +0,008 ± 0,003 pour 8 à 12 matchs) ;
  force d'équipe type Dixon-Coles +0,033 ± 0,003. Sans effet : moyenne ou avantage du terrain par championnat, re-réglage de shrink/rho, binomiale négative.
- **Contre le marché (cote moyenne de clôture, 10 000 matchs)** : l'écart reste défavorable partout. 1X2 : −0,052 (fenêtre 5), −0,042 (fenêtre complète), −0,029 (Dixon-Coles).
  Dixon-Coles n'apporte aucune information que le marché n'a pas (poids de mélange négatif ou instable).
- **Sélection** : la fenêtre complète ne change pas la réussite de la règle (substitut p ≤ 1/1,26 sur 10 000 matchs : 76,56 % contre 76,78 %, IC95 −1,3 à +1,0 point ;
  archive BetPawa : 67,95 % contre 69,6 %, écart apparié −1,6 point, IC95 −2,6 à 0,0). Calibrage par famille ou pénalité d'incertitude : aucun effet distinguable sur l'archive.
- **Décision** : le réglage de production reste à 5 matchs (empreinte des paramètres inchangée, journal gelé intact). La variante « historique complet » est prête :
  `docs/parametres_comportement_fenetre_complete.json` (clé `fenetre: null`). Pour l'activer : copier ce fichier sur `parametres_comportement.json`, relancer `python -m matrice_scenarios.page_comportement --seuils`.
  Le code lit la fenêtre dans `comportement.FENETRE` (`None` = tout l'historique disponible, aucun plafond).
- **Procédure d'acceptation d'un futur calibrage** : gain de Brier > 0,001, p corrigé Benjamini-Hochberg < 5 %, même signe sur au moins 3 blocs chronologiques sur 4, calibrage glissant appris avant la période jugée.
- **Limites** : 2 saisons seulement ; marchés autres que 1X2, plus/moins 2,5 et handicap demi-ligne non jugeables contre une cote ; archive = 20 jours.

## Crédibilité du moteur alpha — conseil du 19/10/2026 (après usage réel)

Constat : picks répétitifs, contradictions avec le profil affiché, probabilités par pick non crédibles (98 % pour « Trinidense +4 »).

Mesures (archive de 1 256 matchs ; réglage 60 % anciens, test 40 % récents) :
- **Contradictions** (« Plus de » en match fermé, « Moins de » en match ouvert) : 13,6 % des picks. Les écarter ne coûte rien (réussite 74,8 % → 75,0 %). **Appliqué** : `contredit_le_profil` (totaux de buts du match).
- **Cotes non fiables** : coup d'envoi absent (n = 39) = 48,7 % de réussite ; cotes prises après le coup d'envoi (n = 33) = 66,7 %. Le « Trinidense +4 » (98 %) vient de cotes en direct. **Appliqué** : `cotes_fiables`, statut `NON_EVALUE : COTES_NON_FIABLES`.
- **Convention des handicaps confirmée** : h = K pour `handicap_3issues_K` (χ² faibles ; h = K±1 : 41 à 148) et signe h = K pour les handicaps à 2 issues. L'hypothèse d'un décalage était fausse ; le code n'a pas changé.
- **Probabilités par pick** : AUC 0,52 (réglage) et 0,50 (test) — elles ne distinguent pas les picks qui réussissent de ceux qui échouent ; surestimation de 15 points dans la tranche haute. Aucune recalibration par famille ne passe le critère (gain de Brier > 0,001, BH). **Appliqué** : l'affichage ne montre plus de % par pick mais la réussite observée du moteur.
- **Diversification forcée** : coûte de la réussite (−2,4 points pour la meilleure variante) pour un gain faible ; non appliquée. Le lift brut sur la fréquence de base perd 17 points.
- **Rendement** : −4,2 % (flat, cotes réelles), 0,0 % sur le test récent : pas d'avantage prouvé contre les cotes. Le moteur est présenté comme une aide à la lecture du match.
- Non appliqués (à décider) : filtres de cohérence entre marchés (écartent surtout des picks gagnants, 85,7 %), exclusion des handicaps (réussite 68,6 % contre 70,1 %, pas de preuve).

### Pari risqué (conseil du 19/10/2026, sur demande du propriétaire)

Affiché en plus du pick principal : parmi les marchés qui **suivent la tendance** du match (côté du favori, total conforme ouvert/fermé, les deux marquent), cotés ≥ 1,26, plus chers que le principal et d'un autre événement, on prend celui qui maximise probabilité × cote, sous un seuil de probabilité mesuré (`seuil_risque` dans `docs/parametres_comportement.json`, commande `python -m matrice_scenarios.page_comportement --seuil-risque` : plus petite probabilité à partir de laquelle ces marchés réussissent au moins une fois sur deux, 1re moitié de l'archive ; 2e moitié : 53,5 % sur 1 745 cas).
- Mesure : 48 % de réussite pour une cote moyenne ≈ 2,0, rendement −11 %. Aucune règle testée ne bat les cotes (E) ; aucune zone famille × cote n'a de rendement positif (G : 0 cellule sur 52 après correction ; −22 % à partir de la cote 3, favori/outsider net).
- Le modèle surestime les outsiders (1X2 cote ≥ 3,97 : 13 % réels, 27 % annoncés par le modèle, 18 % par le marché) : le pari n'est donc jamais présenté comme le meilleur pari du match, et la carte affiche sa réussite observée et un rendement négatif.
- Hors tickets, comme tout le moteur alpha. Le fichier de paramètres change (nouvelle empreinte dans le journal gelé). Le journal gelé enregistre toutes les sélections : le pari risqué y figure (`role` = risque) à partir de maintenant, ce qui permet de le juger hors échantillon sur des matchs jamais vus.
