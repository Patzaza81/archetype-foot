# Moteur DC (`moteur_dc/`)

Créé le 30/10/2026 à partir des 5 modules « Extraction → Dixon-Coles & Bayes → Marchés → Sélecteur statistique → Cotes et staking » fournis par Patrick,
après audit de leur cohérence. Branche `moteur-dc`. Autonome : n'utilise ni V2, ni V3, ni le Journal, ni alpha, ni omega, ni Europe, ni v2r, ni v
(le catalogue de marchés d'omega est COPIÉ dans `moteur_dc/marches.py`, pas importé). Hors générateur de tickets. Statut : observation.

## Ce qui a été gardé, corrigé, retiré (audit des 5 modules)
| Module reçu | Décision | Pourquoi |
|---|---|---|
| 2 — Dixon-Coles | **Gardé et corrigé** | Le contrat d'entrée ne contenait que l'historique des deux équipes (adversaire = style, sans identité) : les forces d'un championnat ne s'estiment que sur TOUS ses matchs. `donnees.py` reconstitue le championnat entier. Ajout d'un terme de niveau de buts `mu` (absent). Pénalité vers 0 (= moyenne du championnat), pas vers CBD/CBE. |
| 2 — choix de xi | **Corrigé** | La vraisemblance pondérée de l'échantillon diverge quand xi grandit : σ, xi et ρ sont choisis sur la vraisemblance PRÉDICTIVE hors échantillon. |
| 2 — ρ | **Corrigé** | Un ρ libre par championnat se perd dans le bruit et a rendu des scores impossibles (τ ≤ 0, constaté pendant la construction) : ρ commun, appris hors échantillon. |
| 2 — facteur d'efficacité BP/xG | **Retiré** | Double emploi (les forces sont déjà ajustées sur les buts réels) ; aucun xG dans le contrat ; circulaire s'il vient du Poisson. |
| 2 — ajustement Bayes par style/profil | **Retiré** | Estimé sur 4 matchs contre 5 profils : bruit ; aucune preuve hors échantillon. À reproposer avec preuve. |
| 1 — 44 paramètres | **Non repris** | La majorité n'entrait dans aucune formule du Module 2 (moy_bp, taux_nul, score_modal, variance, ie, forme_ppm, CBD/CBE…). Forme_PPM divisait par J−5 (nul ou négatif pour une équipe à 4 matchs) ; 5 profils sans règle de classement. Le moteur lit directement les matchs. |
| 3 — extraction des marchés | **Gardé** | Somme exacte des cases de la grille, combinés compris (catalogue d'omega : 100 marchés). |
| 4 — EMAC, Z-test, Bonferroni | **Corrigé** | EMAC = moyenne de |P − Y| avec Y∈{0,1} vaut ≈ 0,4–0,5 (jamais 0,032) : l'étape 3 rejetait tout, l'étape 0 laissait tout passer. Remplacé par l'erreur de calibration PAR TRANCHE (`calibrage.tranches`). Le pool k/n mélangeait des matchs où « 1 » ne veut pas dire la même chose : p̂ est lu par perspective (A à domicile, B à l'extérieur, score orienté), n = essais, k = réussites. Le Z (p̂ contre la base du championnat) est AFFICHÉ, jamais un filtre (aucune preuve hors échantillon, cf. omega). |
| 5 — cotes, EV, Kelly | **Non repris** | Contraire aux règles de Patrick : ne pas chercher à battre la cote, réussite d'abord, pas de ROI. Cote minimale **1,39**, ordre du 27/10/2026 (seule valeur posée à la main). |

Les exemples chiffrés des modules étaient incohérents (k(1X)=50 alors que k(1)+k(N)=54 ; probabilités du Module 3 sans rapport avec les λ du Module 2).
Contrôlés et exacts : la formule τ de Dixon-Coles, les Z des exemples, le seuil Bonferroni 2,66 pour 13 marchés, l'arithmétique Kelly.

## Modèle (`modele.py`)
`λ_dom = exp(mu + gamma + att_dom + def_ext)`, `λ_ext = exp(mu + att_ext + def_dom)` (`def` = faiblesse défensive). Vraisemblance de Dixon-Coles (τ sur 0-0, 1-0, 0-1, 1-1),
poids `exp(−xi × âge en jours)`, pénalité `(1/2σ²) Σ(att² + def²)` (rend la solution unique), gradient analytique (vérifié contre le gradient numérique : écart 5·10⁻⁸).
Grille des scores 0 à 10 renormalisée ; chaque marché = somme des cases. Un match n'entre jamais dans l'ajustement d'une prédiction s'il n'est pas STRICTEMENT antérieur au jour du match.

## Données (`donnees.py`)
- Production : `data/assemblage/equipes.json` (assemblage du contrat des données). Chaque équipe y liste ses matchs ; le championnat entier est reconstitué en dédoublonnant les
  matchs vus des deux côtés. Un adversaire écrit autrement est rattaché par les faits (même jour, score inverse, équipe connue en face ; l'alias va à l'équipe qui y gagne le plus
  de dates, égalité = rien n'est deviné) — aucun seuil de ressemblance de noms. Une équipe sans aucun bloc dans l'assemblage garde sa propre identité d'adversaire.
- Règle de Patrick conservée : au moins 4 matchs au même lieu pour chaque équipe, sinon match exclu. Saison en cours seulement.
- Calibrage : bloc Football-Data 2025-26 / 2026-27 (`data/bloc_saisons/`), identités propres, saison ET division séparées.

## Calibrage (`python -m moteur_dc.calibrage [tout|reprise]`) — protocole fixé avant calcul
1. **Hyperparamètres** sur Football-Data 2025-26, marche avant (ajustement avec les matchs d'AVANT chaque semaine, notation des matchs de la semaine ; 9 488 matchs) :
   **σ = 0,25 ; xi = 0,004 ; ρ = −0,04** ; vraisemblance prédictive −2,9178 par match (σ=0,15 : −2,927 ; σ=0,4 : −2,928 ; σ=2 : −2,972 ; xi=0 : −2,919 ; xi=0,016 : −2,930).
2. **Calibration par marché** (isotone) apprise sur 2025-26 et **taux de base** par marché ; calibration gardée pour une famille SEULEMENT si elle améliore, sur 2026-27, la perte logarithmique ET le Brier.
3. **Validation sur Football-Data 2026-27** (1 598 matchs, jamais utilisés pour régler) : le modèle brut bat le taux de base dans les 4 familles (perte logarithmique :
   résultat 0,5665 contre 0,5802 ; buts du match 0,5875 / 0,5972 ; buts d'une équipe 0,5476 / 0,5604 ; combinés 0,4964 / 0,5037). **La calibration isotone NE LES AMÉLIORE PAS**
   (légèrement pire dans les 4 familles) : elle est donc retirée, les probabilités utilisées sont les probabilités brutes. Écart annoncé − observé par tranche : de −1,1 à +1,9 point
   (le plus élevé : 90-100 %, annoncé 92,8 % pour 90,9 % observé). Vraisemblance exacte 2026-27 : −2,996 par match (début de saison : plus d'équipes à petit échantillon).
4. **Sélection** (archive ARCHETYPE, coupée au 14/10/2026 comme omega) : seuil appris par la meilleure borne basse de Wilson à 95 % sur le développement (261 matchs, 95 paris principaux),
   candidats 50 à 75 %, accord avec la cote testé : **seuil 71 %, sans accord avec la cote** (développement : 71,6 % réussis). Contrôle sur la réserve (616 matchs, 245 paris, cote
   moyenne 1,48) : **66,5 %** réussis pour au moins 71 % annoncés : le modèle surestime un peu sur la réserve. Ce n'est PAS un bilan de performance (archive, période courte) :
   le bilan réel vient du journal gelé.

Limites : l'archive ne contient que 36 jours ; l'accord avec la cote n'a pas montré d'apport ici (il en montrait chez omega) — à retester quand le journal réel sera plus long.
Pas de preuve que le moteur bat la cote ; la rentabilité n'est ni testée ni visée.

## Production (`python -m moteur_dc.suivi pipeline`)
- Étape « Moteur DC » de `pipeline.yml`, après omega, `continue-on-error`. Dépendance ajoutée à l'étape d'installation : `scipy`.
- `data/dc/journal.jsonl` (ajout seul) : une ligne « pronostic » par match à venir, nouvelle ligne seulement si la sélection change ; la dernière ligne écrite AVANT le coup
  d'envoi compte ; une ligne « resultat » par match, jamais modifiée. `data/dc/pronostics.json` pour une page (pas encore créée).
- Sélection : cote BetPawa connue ≥ 1,39 ; probabilité ≥ seuil appris ; principal = le plus probable ; « autres » = les autres marchés retenus ; jamais deux fois le même événement ;
  aucun marché qui passe = aucun pari. Chaque pari porte sa preuve (k, n, p̂, Z) et sa base de championnat.
- Bilan réel : `python bilan_reel.py` (lignes « DC tous paris » et « DC pari principal ») : seulement les paris gelés avant le coup d'envoi, matchs terminés.
  Au 30/10/2026 : 0 match réglé (premier gel le 30/10/2026).

## Points ouverts
- Page `pronostics_dc.html` (affichage des paris, preuves, derniers matchs au même lieu) : non faite.
- Recalibrer (`python -m moteur_dc.calibrage reprise`) quand la saison 2026-27 sera plus avancée.
- Reproposer l'ajustement par style adverse ou l'efficacité de finition seulement avec une preuve hors échantillon.
- Tests : `tests/test_moteur_dc.py` (17 tests : modèle, anti-fuite, minimum 4 matchs, preuve orientée, championnat reconstitué, sélection, gel et résultat).
