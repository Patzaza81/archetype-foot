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
