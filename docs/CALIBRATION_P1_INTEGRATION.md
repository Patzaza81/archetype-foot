# Branchement de la calibration P1 (mode parallèle)

## Constat à lire d'abord
- Le « P1 » calibré est le modèle de recherche `pouvoir_predictif.py` (Poisson attaque/défense, k et demi-vie par compétition).
- **Aucun moteur de production ne calcule ce P1** (v2.6.10, DC, omega, Gamma, Europe-Gamma, alpha_serie ont chacun leur modèle). Les calibrations ne valent que pour ce P1 : ne jamais les appliquer aux probabilités d'un moteur.
- Les 266 couples sont « P1 CONSERVÉ » : calibré = original, exactement.

## Point d'accroche (flux réel)
- `data/archive_test/<jour>.json.gz`, écrit chaque nuit par `archive_donnees_test.py` (déjà lu par alpha_serie et DC) : division Football-Data et noms FD des deux équipes déjà résolus.
- `integration_calibration.py` lit les matchs à venir (score absent, coup d'envoi futur), calcule P1 via `pouvoir_predictif.predire` (aucun calcul dupliqué), applique `calibration_p1.appliquer`/`appliquer_1x2`.
- Historique : archives 2122-2526 + `data/football_data/normalized/2627/<CODE>.jsonl`, strictement avant la date du match.

## Sorties (seules écritures)
- `data/calibration_p1/parallele/journal.jsonl` : une ligne gelée par match (p1_original, p1_calibre, méthode par marché, sommes 1X2, publie).
- `dernier_rapport.json`, `verification_38.json`.
- Mode dans `data/calibration_p1/integration.json` (`parallele` par défaut).

## Résultats du 04/11/2026
- 157 matchs à venir dans le flux ; 36 avec P1 (BRA 7, F2 5, E1 4, JPN 3, MEX 3, etc.) ; 121 hors périmètre (compétitions/équipes non couvertes par Football-Data : coupes, Europe, etc.).
- Écart max calibré − original = 0 ; somme 1X2 = 1 ; fichiers publiés (`data/*/pronostics.json`, `precalcul.json`, journaux) : empreinte SHA-256 identique avant/après.
- `python integration_calibration.py --verifier` : 38/38 compétitions avec 7 marchés, P1 calculable, 1X2 = 1, O1,5 ≥ O2,5 ≥ O3,5, identité.
- Échantillon : un seul jour de flux ; ce n'est pas une performance de moteur.

## Activation ultérieure
1. Une correction doit d'abord être « CORRECTION VALIDEE » par `calibration_finale.py` (protocole 2324/2425 sélection, 2526 confirmation).
2. Laisser tourner le mode parallèle ; comparer sur matchs terminés du journal gelé (règle CLAUDE.md : matchs réellement tournés).
3. Si gain confirmé : mettre `"mode": "actif"` dans `integration.json` (le champ `publie` prend alors la valeur calibrée). Le branchement à une page ou un moteur reste une décision séparée.
4. Retour arrière : remettre `"parallele"`.

## Tests
`pytest tests/test_integration_calibration.py tests/test_calibration_p1.py`

## Correction du 04/11/2026 (journal)
Le premier journal avait été gelé avec une heure de test fixée à 12:00Z : certains matchs déjà commencés y figuraient comme gelés avant le coup d'envoi. Il a été régénéré avec l'heure réelle (matchs non commencés seulement). Désormais : `ecrire` refuse tout match dont le coup d'envoi est passé, chaque ligne porte une empreinte SHA-256 chaînée à la précédente, et `verifier_journal()` détecte toute modification ou tout gel postérieur au coup d'envoi (`tests/test_page_p1.py`).

## Page « P1 – Analyse statistique » (`pronostics_p1.html`)
- Fichiers : `pronostics_p1.html`, `archetype_p1.js`, `af-p1.css`, données `data/calibration_p1/page_p1.json` (produit par `p1_page_donnees.py`).
- Lien dans la navigation de toutes les pages qui ont la barre des moteurs, et dans l'accueil. Aucun moteur, aucune API, aucun JSON d'un autre moteur modifiés.
- Contenu : à venir (filtres date et compétition), 1/N/2 + plus de 1,5 / 2,5 / 3,5 + les deux marquent, détail statistique (buts attendus, matchs antérieurs, k, demi-vie, empreinte), P1 original vs calibré (identiques tant qu'aucune correction n'est validée ; l'écart s'affiche seulement s'il existe), terminés avec résultat, performances (perte logarithmique, Brier, favori correct ± erreur-type, par marché) sur matchs gelés avant le coup d'envoi, historique gelé avec contrôle d'intégrité.
- Donnée absente : « — » ou message explicite ; aucune valeur inventée. Les résultats viennent des scores déjà écrits par le flux (`data/archive_test`).
- Le workflow `calibration_parallele.yml` met à jour journal et `page_p1.json` après le pipeline.

## Preuve d'exactitude
`python verifier_page_p1.py` → `data/calibration_p1/preuve_page_p1.json` : recalcul de P1 depuis zéro pour chaque match (écart max avec journal et page), lecture du DOM dans Chromium (écart max en %), intégrité du journal. Captures : `data/calibration_p1/captures/`.

## Pari retenu par P1 (ajout du 05/11/2026)
- Règle (`p1_paris.py`, aucune constante) : marchés dont P1 donne la probabilité (1, N, 2, 1N, N2, 12, plus/moins de 1,5 / 2,5 / 3,5, les deux marquent oui/non, par somme ou complément exact) ET dont la cote réelle est présente dans `cotes_betpawa` du flux. Valeur = proba P1 × cote − 1. Pari retenu = marché à valeur > 0 de plus forte proba P1 ; sinon « aucun marché retenu ». Sans cote : marché non évalué.
- Pari et cotes sont gelés dans le journal avec la prédiction. Mesure : taux et rendement moyen par mise unitaire (± erreur-type), sur matchs terminés seulement.
- Limite : la valeur est jugée par P1 lui-même ; P1 n'a pas démontré de gain face aux cotes. Le journal a été régénéré le 05/11 (aucun match terminé à ce moment) pour inclure les paris.

## Apprentissage quotidien (ajout du 07/11/2026, demande de Patrick : « le système doit apprendre chaque jour »)
- Code : `apprentissage_p1.py` (couche AU-DESSUS de P1 ; P1, `config_calibration.json`, `config_med.json` et le journal gelé ne sont pas modifiés). Sortie : `data/calibration_p1/apprentissage/etat.json`, recalculée de zéro chaque nuit par `calibration_parallele.yml` (étape avant `p1_page_donnees.py`).
- Données : uniquement les matchs du journal gelé AVANT le coup d'envoi et terminés (scores du flux `data/archive_test`) ; le calcul refuse de tourner si `verifier_journal()` signale une anomalie.
- Méthode : par marché (plus de 1,5 / 2,5 / 3,5, les deux marquent), tous championnats ensemble, décalage logit `b` (maximum de vraisemblance) : `p' = sigmoïde(logit(p) + b)`. 1X2 non touché.
- Validation (aucune constante inventée ; seuil du protocole du dépôt) : correction « VALIDÉE » seulement si |b|/erreur-type > 1,645 ET gain de perte logarithmique prospectif moyen > 0 avec z > 1,645 (chaque jour évalué avec un `b` appris sur les jours précédents seulement). Sinon « EN OBSERVATION » : probabilité inchangée.
- Effet : `page_p1.json` porte la clé `apprentissage` ; un match à venir reçoit `p1_appris` seulement si une correction est validée. Aucun affichage ajouté sur la page.
- Limites : avec ~40 matchs/jour, la première correction possible demande plusieurs semaines ; un apprentissage par championnat n'est pas fait (trop peu de matchs par division). Le 07/11/2026 : 1 match terminé au journal, tous marchés « EN OBSERVATION ».
- Tests : `pytest tests/test_apprentissage_p1.py` (3 biais nets validés, 3+ cas calibrés/bruit/un jour/un match/résultats identiques non validés, absence de fuite recalculée à la main, journal altéré refusé).

## Derniers matchs à trois onglets pour tous les moteurs (07/11/2026, demande de Patrick)
- Chaque carte affiche, pour chaque équipe, les onglets « À domicile / À l'extérieur / H2H » comme la page P1 (matchs réels de la saison en cours, strictement avant le match ; H2H : 10 dernières confrontations au plus).
- Données communes : `derniers_onglets.py` -> `data/derniers_onglets.json` (clé = `match_id` du flux commun, format compact, 3 derniers jours + à venir), recalculées chaque nuit par `calibration_parallele.yml`. Même calcul que P1 (`p1_page_donnees.derniers_matchs`). `integration_calibration.lire_flux(..., tous=True)` lit aussi les matchs terminés (défaut inchangé).
- Affichage : `af-derniers-onglets.js` / `.css` (classes `afd-*`), chargés avant le script de chaque moteur : Omega, Gamma, DC, Mixte, V, V2R, V3, V2 (`archetype.html`), alpha (`pronostics_comportement.html`). Les pages attendent le chargement via `afAttend` ; sans donnée pour un match, la page garde son affichage actuel (rien n'est inventé).
- Non couverts : matchs dont les deux équipes ne sont pas reliées à un championnat suivi (coupes, Europe, petits championnats sans historique) ; page Europe inchangée (aucun de ses matchs n'est couvert). La page alpha remplit ses détails au dépliage.
- Tests : `pytest tests/test_derniers_onglets.py`.
