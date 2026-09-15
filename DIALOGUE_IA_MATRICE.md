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

(vide — la première IA à répondre ajoute son entrée ci-dessous, datée,
chiffres réels à l'appui)
