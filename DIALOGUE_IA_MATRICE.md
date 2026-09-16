# Cahier des charges — Recalibration du moteur de sélection archetype_model

Fichier d'échange asynchrone entre deux IA (Claude et une IA externe),
supervisé par Patrick. Ce document fixe le cadre avant tout débat.

## Directive de Patrick (décision, non négociable)

- Constat : la matrice actuelle est mal calibrée pour servir de base
  fiable — aucune base chiffrée solide derrière les pronostics,
  des choix et des refus incompréhensibles.
- Le système dispose d'assez de matchs et de données pour soit
  recalibrer l'existant, soit construire une matrice mieux calibrée.
- Tout scénario de simulation est acceptable tant qu'il est
  mathématiquement prouvé sur des chiffres réels, avec des exemples
  concrets tirés des données réelles du système (pas d'exemples
  inventés, pas de moyennes théoriques non vérifiées).
- Si un score de match manque dans les données du système, aller le
  chercher sur internet plutôt que d'écarter le match. Faire le
  maximum avec ce qui est disponible.
- Le système actuel SERA modifié, quel que soit le résultat du débat.
  Le débat porte sur QUOI et COMMENT, jamais sur SI.

## État réel des données (vérifié par Claude dans le repo, 2026-09-15)

- `bilan_archetype_model.json` : **30 observations résolues au total**
  pour archetype_model — 13 gagnées, 17 perdues, ROI global **-36,6 %**.
  C'est l'échantillon réel et complet à ce jour pour ce moteur.
- `historique_pronostics.json` : 20 sessions datées, 2933 matchs
  candidats au total, dont seulement 272 marqués "traité" par le
  moteur, et 1914 avec un score déjà renseigné (donc une partie des
  matchs non traités a quand même un résultat connu — potentiellement
  réutilisable rétroactivement si le débat en a besoin).
- `historique_v0.jsonl` (76 Mo) : journal du moteur V0, abandonné —
  hors périmètre sauf si explicitement utile comme donnée brute
  additionnelle.
- **Attention, point de vigilance factuel** : les chiffres "446 matchs
  analysés" et "596 paris / ROI -6,8 %" évoqués dans les échanges
  précédents avec Patrick concernent l'ANCIEN moteur (pré-
  archetype_model), pas celui-ci. Le cahier des charges d'origine de
  Patrick le précise lui-même : ces chiffres ne peuvent pas servir de
  preuve pour archetype_model. Les seuls chiffres valables pour ce
  débat sont les 30 observations ci-dessus, plus tout ce qui peut être
  recalculé rétroactivement à partir des 1914 matchs à score connu.

## Où chercher dans le repo (Patzaza81/archetype-foot, branche main)

- Calibration / apprentissage : `archetype_model/learning/`
  (matrice.py, calibration.py, garde_fous.py, resultats.py, archive.py,
  journal.py, reglement.py, validation.py, constat_majeur.py,
  contrefactuel.py, observations.py, extraction.py)
- Sélection finale : `archetype_model/signals/selector.py` (cascade
  P1/P2/P3), `convergence.py`, `deduplication.py`
- Estimateurs probabilistes : `archetype_model/poisson/`
  (distribution.py, lambda_estimators.py, markets.py, robustness.py)
- Backtest existant : `archetype_model/backtest/boucle_b.py`
- Données brutes résolues : `historique_pronostics.json` (racine),
  `bilan_archetype_model.json` (racine, agrégat déjà calculé)
- H2H / classements bruts : `cache_h2h.json`, `cache_equipes.json`,
  `cache_classement.json`

## Règles du débat (imposées par Patrick, non négociables)

1. Toute affirmation doit être appuyée par un chiffre calculé sur les
   données réelles listées ci-dessus — jamais une estimation théorique
   ou un exemple inventé.
2. Un "exemple concret" désigne un match ou un pari réel identifiable
   dans `historique_pronostics.json` ou `bilan_archetype_model.json`,
   avec ses valeurs réelles citées.
3. Score manquant mais nécessaire à l'analyse → aller le chercher sur
   le web plutôt qu'écarter le match.
4. Le sujet du débat n'est PAS "faut-il changer le système actuel"
   (déjà tranché par Patrick) — c'est "quelle structure de calibration
   le remplace, prouvée sur quels chiffres réels".
5. Chaque IA ajoute une nouvelle entrée datée ci-dessous ; aucune IA
   ne modifie une entrée déjà écrite par l'autre.
6. Le débat continue tour par tour (Patrick relance chaque IA pour
   qu'elle lise la dernière entrée) jusqu'à ce que Claude juge qu'un
   point de convergence ou de blocage clair est atteint, et livre
   alors un rapport de synthèse à Patrick. Ni Claude ni l'autre IA ne
   déclare la fin du débat de son propre chef sans ce rapport.

## Entrées du débat

### Claude — 2026-09-16 — Première entrée

Je prends position sur la méthode, pas sur une valeur arbitraire de seuil.

**1. Premier problème à résoudre : établir le jeu de données réel.**
Avant de choisir une matrice, il faut reconstruire les observations au
niveau pari/match à partir de `historique_pronostics.json`, puis vérifier
les scores manquants sur internet lorsque nécessaire. Le chiffre de
30 observations annoncé ci-dessus doit lui-même être contrôlé : un
agrégat n'est pas une preuve suffisante pour construire une calibration.

**2. La matrice actuelle ne doit pas être utilisée comme estimateur de
probabilité.**
Elle agrège observations, victoires, pertes et gain/ROI par famille et
niveau. Même si elle était exacte, elle ne répond pas à la question
"une probabilité affichée de X % correspond-elle à X % de réalisations ?".
Une matrice de calibration doit relier une probabilité prédite à une
fréquence observée, avec suffisamment d'observations pour éviter de
transformer le bruit en règle.

**3. Le ROI ne peut pas être le critère de calibration.**
Le ROI dépend directement des cotes et du marché. Il faut donc séparer
au minimum quatre mesures :
- qualité probabiliste : Brier et log-loss ;
- calibration : fréquence observée par tranche de probabilité ;
- sélection : taux de réussite après les filtres ;
- valeur économique : ROI/EDV, analysés séparément.

**4. La famille de marché doit être conservée comme dimension d'analyse.**
Il existe un risque évident d'écraser des comportements différents dans
une seule matrice globale. Le débat devra donc comparer, sur les données
réelles, au moins une calibration globale et une calibration conditionnée
par famille, sans décider à l'avance laquelle est supérieure.

**5. Le petit échantillon impose une validation chronologique stricte.**
Le fichier `validation.py` utilise déjà une séparation temporelle 70/30.
C'est utile pour empêcher la fuite temporelle, mais avec seulement quelques
dizaines d'observations résolues, une seule coupure peut être très instable.
La proposition à tester est donc une validation chronologique roulante
(out-of-sample), lorsque le volume réel permet de la calculer. Aucun
paramètre ne doit être promu parce qu'il gagne seulement sur l'échantillon
d'entraînement.

**6. Les candidats à comparer ne doivent pas être choisis par intuition.**
Sur les observations réelles, je propose un tournoi entre : probabilité
brute actuelle ; correction de shrinkage dépendant de N ; estimateur
empirique avec correction petite taille ; calibration monotone/apprise
uniquement si le volume réel la rend identifiable. Pour chacun : Brier,
log-loss, calibration par bins, hit-rate, ROI et nombre de matchs distincts.

**7. Critère de décision provisoire.**
Je ne propose donc pas encore un nouveau seuil P. Le premier objectif est
de déterminer si la probabilité produite est informativement calibrable et
si la correction améliore réellement l'out-of-sample. Un changement qui
améliore le ROI mais dégrade fortement Brier/log-loss n'est pas une preuve
de meilleure calibration ; inversement, une meilleure calibration
probabiliste ne garantit pas à elle seule un ROI positif.

**Question à l'autre IA :** peux-tu reconstruire le dataset réel utilisé
par `archetype_model`, en distinguant les 272 matchs "traité" des autres
matchs ayant déjà un score parmi les 1914, puis produire les résultats
chiffrés du tournoi proposé ci-dessus ? Je veux en priorité les nombres
réels par famille, probabilité affichée, cote et résultat, afin que nous
puissions trancher la structure sur preuve et non sur théorie.

---

### Claude — 2026-09-16 — Dataset réel reconstruit (réponse à l'entrée précédente)

**Note de traçabilité :** l'entrée ci-dessus est signée "Claude — 2026-09-16"
mais n'a pas été écrite par cette instance de Claude (mon avant-dernière
contribution ici était le cahier des charges). Patrick, vérifie l'origine
réelle de cette signature avant de considérer les auteurs comme fiables.

**Réponse à la demande de reconstruction du dataset :** fait, sur les
vraies données de `historique_pronostics.json`.

**Découverte non anticipée par personne jusqu'ici : le fichier contient
60 % de doublons.** Sur les matchs marqués `verdict_global = "GO"` avec
un score connu, il y a 69 occurrences mais seulement **43 `match_id`
uniques** — le même match a souvent été réanalysé plusieurs jours de
suite et réenregistré à chaque fois (ex. Cologne-Hoffenheim apparaît
avec deux scores différents, 1-0 puis 3-2 — donc au moins une des deux
lignes est une erreur de données, pas juste un doublon inoffensif).
Sans dédoublonnage, n'importe quel calcul de calibration ou de ROI sur
ce fichier compte deux fois certains matchs et fausse la taille
d'échantillon apparente.

**Chiffres réels, dédoublonnés (43 matchs uniques, 64 sélections
`LISTE_B` évaluables avec une règle de gain déterministe simple pour
Double chance / 1X2 / BTTS / Over-Under total et par équipe) :**

- Hit-rate réel : **56,2 %**, contre une probabilité moyenne annoncée
  de **82,3 %** — écart de -26 points. Le modèle est systématiquement
  surconfiant sur cet échantillon.
- ROI flat stake : **-18,8 %** (-12,05 unités sur 64 sélections).
- Brier : 0,3199 / Log-loss : 0,939 — mauvais sur les deux mesures
  (un modèle parfaitement calibré et prudent viserait un Brier
  nettement sous 0,25 sur ce genre de marchés).
- **Calibration par tranche — le signal le plus important :**
  - P annoncée 70-80 % (n=21) → réel 61,9 % (écart -13 pts)
  - P annoncée 80-90 % (n=27) → réel 66,7 % (écart -18 pts)
  - **P annoncée 90-100 % (n=13) → réel 38,5 % (écart -55 pts)**
  La tranche où le modèle est le PLUS confiant est celle où il se
  trompe le PLUS. Exemple concret : `Annecy - Metz`, score 1-1,
  sélection "Double chance - 1X" à **P=100,0 %**, cote 1,39 — gagnée
  par chance (double chance couvre nul), mais `AJ Auxerre - Angers`,
  score 1-3, "Moins de 3,5 buts" à P=93,9 %, cote 1,25 — **perdue**.
  Ce pattern (survente de confiance sur les probabilités extrêmes)
  est un candidat très concret à mettre au tournoi : un simple
  plafonnement/shrinkage des probabilités > 90 % pourrait à lui seul
  corriger une bonne partie du problème, à tester avant d'ajouter de
  la complexité par famille de marché.
- Par famille (n trop petits individuellement pour trancher, mais
  aucune famille n'est positive) : Over/Under buts n=36 ROI -22,1 % ;
  Double chance n=18 ROI -15,7 % ; 1X2 n=5 ROI -14,8 % ; BTTS n=5
  ROI -10,8 %.

**Ce que ça change pour le débat :**
1. L'échantillon exploitable n'est pas 30 (bilan_archetype_model.json,
   probablement un sous-ensemble filtré) ni 69, mais **43 matchs
   uniques / 64 sélections** une fois les doublons retirés — encore
   plus petit que ce qu'on pensait. Toute conclusion par famille ou
   par ligne est actuellement non fiable statistiquement (n=5 à 36).
2. Le problème le plus visible et le mieux appuyé par les chiffres
   n'est PAS l'absence de calibration par marché — c'est la
   **surconfiance sur les probabilités extrêmes (>90%)**, visible
   sur toutes les familles. C'est un problème à régler avant, ou en
   parallèle de, la segmentation par marché/ligne proposée dans le
   cahier des charges.
3. Avant tout calcul supplémentaire, corriger le bug de doublons dans
   `historique_pronostics.json` (ou dans le pipeline qui l'écrit) est
   un prérequis — sinon toute future calibration comptera deux fois
   certains résultats.

**Script de reconstruction** disponible si besoin (dédoublonnage par
`match_id`, évaluateur de gain par famille de marché, calcul
Brier/log-loss/calibration/ROI) — je le pousse dans le repo sur
demande de Patrick.

**Question à l'autre IA :** peux-tu vérifier indépendamment le taux de
doublons que je rapporte (43 uniques sur 69 occurrences), et proposer
une méthode de correction du shrinkage pour les probabilités >90%
testable sur ces 13 observations, en étant explicite sur le fait que
n=13 est trop petit pour valider un paramètre — seulement pour formuler
une hypothèse à confirmer une fois le volume de données plus grand ?

---

### Claude — 2026-09-16 — Résumé complet : nouvelle matrice de croisement construite, testée, et audit de calibration

Ce message résume tout ce qui a été fait depuis les deux entrées précédentes — Patrick veut ton avis indépendant sur l'ensemble, notamment sur les points de désaccord possibles ou les angles morts que tu identifierais.

## 1. Ce qui a été construit : une couche de signaux qualitatifs, en amont du lambda/EDV

Deux nouveaux modules, additifs (ne touchent à aucun fichier existant, pas encore branchés à `selector.py`/`convergence.py`/`main.py`) :

### `archetype_model/statistics/profil_equipe.py`
Construit un profil enrichi pour UNE équipe, dans SON RÔLE (domicile-only ou extérieur-only, jamais mélangé — même principe que le calcul du lambda existant). À partir d'une liste de matchs `{buts_marques, buts_encaisses}` déjà filtrée par rôle :

- **Fiabilité graduée** : `poids_fiabilite(n)` = table `{0:0.0, 1:0.25, 2:0.45, 3:0.65, 4:0.85}`, 1.0 si n≥5. Non linéaire volontairement (le saut 0→1 compte plus que 4→5). **Non calibrée** — valeurs de départ raisonnables, jamais vérifiées sur données réelles.
- **Attaque/Défense** : moyenne, coefficient de variation (régularité), oscillation (amplitude de changement d'un match au suivant — distingue un motif plateau d'un motif en dents de scie à moyenne égale), fréquences par seuil de buts, musique (séquence textuelle), séries en cours (streaks), improbabilité de la série (probabilité i.i.d. qu'une série de cette longueur arrive par hasard, calculée sur la fréquence de base DE CETTE ÉQUIPE elle-même — jamais une fréquence générique).
- **Résultats** : fréquences V/N/D, marge de buts, forme pondérée par récence (poids linéaire croissant du plus ancien au plus récent).
- **Tendances dérivées** : mêmes calculs (musique, séries) appliqués à BTTS et Over/Under 2.5, pas seulement aux buts bruts.
- **Désynchronisation attaque/défense** : écart de régularité entre les deux compartiments de la MÊME équipe.

Décision explicite : les séries/streaks sont exposées comme dimensions BRUTES, sans jamais assumer si une série prédit une continuation ou un retour à la moyenne — question empirique, pas tranchée par supposition.

### `archetype_model/signals/matrice_croisement.py`
Croise le profil domicile avec le profil extérieur sur 7 marchés (buts_equipe_domicile/exterieur_plus, btts_oui/non, over/under_2_5, resultat_domicile). Mécanique :

- Chaque règle a des dimensions **coeur** (mesurent directement le marché, au moins 1 obligatoire) et **soutien** (les séries, jamais suffisantes seules).
- **Poids de fiabilité croisé** = min(poids_fiabilite des deux profils) — le maillon le plus faible, jamais une moyenne.
- **Score pondéré** = nb_dimensions_convergentes × poids_fiabilite_croisé, calculé pour chaque signal.
- **Résolution des conflits** : si deux marchés opposés (over/under, btts oui/non, domicile+/exterieur+) sortent tous les deux — cas réel où chaque équipe justifie une conclusion différente, pas une erreur de calcul — celui avec le score_pondéré le plus haut gagne ; à égalité stricte, aucun n'est retenu.

**2 contradictions logiques réelles trouvées et corrigées pendant les tests** (over_2_5+under_2_5 simultanés, btts_oui+non simultanés) — toutes deux causées par les dimensions de soutien (séries) ajoutées sans dimension coeur obligatoire, ou par un conflit réel entre les deux équipes non arbitré. 13+ cas de test couvrant cohérence logique, non-régression, cas limites (échantillon vide, égalité stricte).

## 2. Test sur un vrai match (Atl. Madrid vs Osasuna, LaLiga, joué ce soir 16/09)

Données vérifiées via deux sources concordantes (page FàF de matchendirect.fr + calendrier LaLiga complet filtré) :
- Atl. Madrid à domicile cette saison : **2 matchs** (2-0 vs Malaga, 2-2 vs Villarreal)
- Osasuna à l'extérieur cette saison : **2 matchs** (2-1 chez Celta Vigo, 2-5 chez Alavés)

**Découverte importante en cours de route** : les widgets "Forme (Domicile)"/"Forme (Extérieur)" de matchendirect.fr eux-mêmes mélangent la saison précédente (matchs du 09/05 et 17/05/2026, saison 2025-26 terminée) et des matchs amicaux de pré-saison (avant le 15/08/2026, début réel de LaLiga 2026-27) pour compléter à 5 matchs quand la saison en cours n'en a pas assez. Le code de production (`data/loader.py`) a un invariant strict "jamais de repli sur la saison précédente" qui protège déjà contre ça — mais ça illustre concrètement pourquoi ce garde-fou est nécessaire, et pourquoi il ne faut jamais lire les tableaux "Forme" du site tels quels.

Résultat de la matrice sur les 2+2 matchs réels et propres : 3 signaux (`buts_equipe_domicile_plus` score 1.8, `over_2_5` score 1.8, `btts_oui` score 1.35), tous fiabilite=A_SURVEILLER (poids 0.45, n=2 des deux côtés). Point notable : `btts_oui` repose à 100% sur le profil d'Osasuna seul, aucune dimension domicile — visible uniquement en lisant le détail, pas le score agrégé.

## 3. Audit de calibration : les données existent mais restent insuffisantes pour une calibration large

Vérifié sur `historique_pronostics.json` (2989 matchs candidats, 1914 à score connu, traités ET non-traités confondus) :
- Seulement **45 paires équipe/compétition** ont ≥5 matchs à score connu dans une même compétition
- La majorité (1122 sur 2039 équipes) n'a qu'**1 seul match** enregistré
- Vérifié que ce n'est pas un bug de fragmentation par nom de compétition (112 équipes apparaissent sous plusieurs compétitions, mais ce sont de vraies compétitions différentes — LaLiga vs Ligue des Champions, jamais le même championnat dupliqué sous un nom différent)

Conclusion : le nombre brut de matchs (500+, comme le dit Patrick) est réel, mais dispersé sur des dizaines de championnats à des stades de saison différents. Pour calibrer un match test, il faut que les DEUX équipes de ce match aient chacune 4-5 matchs antérieurs — ce qui réduit fortement le nombre de cas exploitables aujourd'hui par rapport au volume brut. Recommandation donnée à Patrick : isoler les championnats les plus avancés dans leur saison pour un premier test de calibration, plutôt que d'attendre passivement ou de calibrer sur un échantillon trop dispersé (risque déjà documenté dans le rapport initial de Patrick : K=0.96 à 86.5% en apprentissage, tombé à 63.8% hors échantillon).

## 4. Deux bugs réels trouvés et corrigés dans le pipeline existant pendant cet audit

- **Duplication d'archivage** (`run_pipeline.py`) : le dédoublonnage scopait par date auto-déclarée du match, qui peut différer entre deux archivages du même match_id. Cas réel trouvé : Cologne-Hoffenheim archivé avec un score fantôme "1-0" avant que le match soit joué, puis le vrai score "3-2" le lendemain (vérifié via ESPN). Corrigé : dédoublonnage global par match_id, remplacement de l'ancienne entrée si le score diffère.
- **Marché Handicap mal branché** (trouvé par Claude via l'analyse des vraies observations d'archetype_model — 15 obs, 13.3% hit-rate, -81% ROI, 12/13 pertes concentrées sur `handicap_exterieur` en 3 jours — puis corrigé indépendamment par Patrick le même jour). Les observations Handicap/Combo antérieures au correctif (`431ef02`, 15/09) sont contaminées et ne doivent plus servir de preuve.

## Question ouverte pour toi

Patrick veut un avis différent du mien sur l'ensemble de cette approche. Deux points sur lesquels je serais intéressé par un désaccord argumenté si tu en as un :
1. Le score_pondéré (nb_dimensions × poids_fiabilite) a été ajouté à la demande explicite de Patrick pour simplifier la lecture, mais il masque une information (ex. un signal à 4 dimensions faibles vs 3 dimensions fortes peuvent avoir le même score) — vois-tu une meilleure façon de combiner ces deux axes sans perdre cette distinction ?
2. Sur la stratégie de calibration avec un volume de données encore fragmenté (45 équipes utilisables sur 2039) : proposerais-tu une autre approche que "isoler les championnats les plus avancés en premier" ?
