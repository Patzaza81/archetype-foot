# Matrice évolutive de découverte de scénarios — version expérimentale

## Statut et limites

La matrice est un laboratoire indépendant et en lecture seule. Elle ne modifie ni les moteurs V2/V3/V2R/Europe, ni le Journal, ni le pipeline, ni les pronostics publiés. Aucune règle n'est automatiquement promue. Le but est de découvrir des relations candidates et de les soumettre à une validation chronologique indépendante.

## Lancement

Le format normalisé est disponible pour les jeux de recherche. Un adaptateur direct lit aussi `data/archive_test/*.json.gz` (SCHEMA_VERSION 2), uniquement les matchs résolus avec score, et récupère l'historique d'équipe conservé avant-match. Il mappe les cotes 1X2, double chance, BTTS, totaux et buts par équipe uniquement via les clés exactes de `parse_betpawa.py` / `moteur_europe/cotes_archive.py` ; tout marché non mappé reste sans cote.

\`\`\`bash
python -m matrice_scenarios.cli data/archive_test --output rapport_matrice_scenarios.json --max-candidates 5000
python -m matrice_scenarios.cli chemin/vers/matchs_normalises.json --output rapport_matrice_scenarios.json --max-candidates 5000
pytest -q tests/test_matrice_scenarios.py
\`\`\`

Le fichier d'entrée peut être :
- un tableau JSON de matchs ;
- un objet JSON \`{"matches": [...]}\` ;
- un fichier JSONL, un match JSON par ligne.

## Contrat d'un match normalisé

Champs obligatoires : \`match_id\`, \`date\` (AAAA-MM-JJ), \`home_team\`, \`away_team\`, \`home_goals\`, \`away_goals\`. Le score final sert uniquement à évaluer la cible, jamais à construire les variables pré-match.

Champs facultatifs :
- \`league\`, \`home_rank\`, \`away_rank\`, \`home_odds\`, \`draw_odds\`, \`away_odds\` ;
- \`home_history\` et \`away_history\`, listes chronologiques ou non de matchs antérieurs. Chaque élément contient \`date\`, \`goals_for\`, \`goals_against\`, et éventuellement \`venue\` (\`home\` ou \`away\`) et \`opponent_rank\` ;
- \`target_odds\`, dictionnaire des cotes réellement observées avant le coup d'envoi, indexé par l'identifiant exact de la cible ;
- \`prematch_features\`, signaux numériques pré-match dont le nom commence par \`pre_\`. Chaque variable ajoutée doit avoir une provenance documentée et être connue avant le coup d'envoi.

Exemple de structure (valeurs illustratives pour décrire le format, pas une preuve ni un résultat historique) :

\`\`\`json
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
\`\`\`

## Variables générées

- Classement : écart signé (positif = domicile mieux classé), écart absolu et rangs si disponibles.
- Historique par fenêtres 2, 3, 5, 8 et 10 : buts pour/contre, différence de buts, taux de marquer, concéder, gagner, ne pas perdre et Over 2,5.
- Séquences : séries de défaites, de non-défaites, de buts marqués, de matchs sans but ; dernier résultat, défaite précédente à domicile/extérieur, défaite lourde, match précédent sans but, match précédent à 2+ buts, 3+ buts encaissés, mauvaise série sur 3 matchs et candidat de reprise.
- Splits domicile/extérieur quand la source les renseigne ; confrontations directes historiques uniquement sur les noms normalisés exacts et les dates antérieures au match.
- Cotes et probabilités implicites 1X2 normalisées sans marge, utilisées comme variables explicatives, pas comme certitude.
- Championnat exact et variables numériques documentées \`pre_*\`.

Les variables d'historique sont recalculées en ignorant systématiquement toute rencontre datée le jour du match cible ou après. Les variables de classement et de cote présentes au niveau du match doivent, elles aussi, correspondre à l'état pré-match ; la matrice ne peut pas vérifier seule la provenance externe de ces champs.

## Recherche et cibles

La première version génère des conditions numériques \`>=\` / \`<=\`, des conditions exactes de championnat et des combinaisons à deux conditions portant sur des variables distinctes. Le budget de calcul réserve environ la moitié des candidats aux interactions. Les seuils sont tirés d'une grille interprétable et de quantiles du seul segment d'entraînement. Le nombre de scénarios explorés est limité explicitement : le système ne prétend pas épuiser toutes les combinaisons possibles.

Cibles : 1X2, double chance sans défaite, buts d'équipe (1+, 2+, 3+), les deux équipes marquent et totaux de buts 1,5 / 2,5 / 3,5. D'autres cibles ne sont ajoutées que lorsque les scores et les cotes correspondantes peuvent être réglés sans ambiguïté.

## Validation et statut

- Dédoublonnage par \`match_id\`. Des doublons dont les scores ou l'identité de match se contredisent sont exclus et comptés.
- Séparation chronologique : 60 % découverte, 20 % validation, 20 % test final. Aucun mélange aléatoire.
- Support minimum de découverte : 30 matchs déclenchés. Support minimum sur chacun des segments validation et test : 15 matchs ; en dessous, le scénario reste \`ECHANTILLON_INSUFFISANT\`.
- Intervalle de Wilson à 95 % pour le taux de réussite.
- Correction Benjamini-Hochberg sur les valeurs p approximatives pour limiter les faux positifs. Ces p-values sont un outil de tri seulement : elles ne constituent pas une preuve de significativité finale.
- ROI calculé uniquement quand une cote \`target_odds\` explicite et valide existe pour la cible exacte. Aucune cote n'est inventée ou substituée.
- \`A_VALIDER\` signifie uniquement que les deux segments ont un support minimal, pas que le scénario est rentable, significatif ou promu.
- \`promotion_allowed\` reste toujours faux dans cette version. La validation finale exige revue humaine, volume suffisant, comparaison au taux de base et au marché, et test hors échantillon gelé.

## Limites connues à traiter avant la production

1. Adapter et tester un convertisseur à chaque source réelle (archive de test, archives de pronostics, résultats, cotes) ; ne pas joindre les données sur des noms approximatifs.
2. Mesurer les observations manquantes, la qualité des identifiants, les scores contradictoires et la date exacte des instantanés de cotes/classement.
3. Passer à une validation walk-forward à plusieurs origines et à une estimation par match pour tenir compte des marchés corrélés.
4. Ajouter les tests de permutation, la stabilité par saison/ligue et la comparaison au marché avec intervalles par match.
5. Étendre prudemment au-delà des paires de conditions, avec recherche beam/association ou arbres peu profonds et budget déterministe ; ne pas faire une recherche exhaustive exponentielle.
6. Ne jamais connecter la sortie au générateur de tickets ou au pipeline avant un banc historique indépendant, un jeu final jamais utilisé et une décision explicite.

## Principe immuable

Les scénarios sont des hypothèses qui peuvent être inventées, combinées, transformées, testées puis abandonnées. Un exemple humain n'est jamais une règle standard imposée au système. L'absence de données donne « inconnu », jamais une supposition.
