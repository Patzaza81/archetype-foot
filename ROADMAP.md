# ROADMAP — Archetype Foot

> Les renvois « TRANSITION.md §N » de ce document désignent l'ancien journal de sessions, supprimé le 21/09/2026.
> Il reste lisible dans l'historique Git : `git show c1ce4c9:TRANSITION.md`.

Suivi des chantiers majeurs. Les statuts ci-dessous reposent sur des vérifications réelles du dépôt, des exécutions GitHub Actions et des fichiers produits. Aucune conclusion ne doit être tirée d'un simple statut vert sans inspection des sorties.

Dernière mise à jour : 20/09/2026 — après la session justification/casse critique/Handicap (voir TRANSITION.md §52).

---

## 1. État immédiat

### Run #128 — SUCCÈS technique
- Commit exécuté : `4f772866`.
- Pipeline complet exécuté.
- Les étapes scraping, pré-calcul, Betpawa, vérifications, observation, tickets, bilan comportemental et calibration sont passées.
- La bibliothèque de justification est présente dans les sorties.
- Défauts constatés : justifications spécifiques encore absentes pour plusieurs candidats, `odds_scraped`/`market_prob_pct` parfois nuls dans le chemin courant, marchés Under non couverts par le dictionnaire de preuves, `over_2.5` non reconnu par le règlement.

### Run #129 — ÉCHEC APRÈS ~2 h 29
- Type : `schedule`.
- Commit de départ : `4f772866`.
- Étapes 1 à 14 : **succès**.
- Étape 15 — « Commit et push du résultat » : **échec**.
- Cause exacte vérifiée dans les logs : le job a produit un commit local `db65c61`, puis le `git pull --rebase` a rencontré des conflits de contenu sur les gros fichiers de données générés simultanément sur `main` (archive, caches, diagnostics, `precalcul.json`, tickets, etc.).
- Le rebase n'a pas pu appliquer `db65c61`, sortie 1.
- L'échec n'est donc **pas un échec du moteur de prédiction ni du scraping** : c'est un conflit de synchronisation Git sur la phase de publication.
- Le problème est aggravé par le volume massif des fichiers générés et par des écritures concurrentes sur `main`.

**Action prioritaire : sécuriser la publication des résultats avant de relancer des runs longs.**

### Incident du 19/09 — `main` cassé entre les runs #129 et le run suivant (voir TRANSITION.md §52)
Le nettoyage "retirer parité et combos" (décision assumée, pas remise en cause) a accidentellement supprimé du code actif sans rapport avec parité/combo : une erreur de syntaxe a rendu tout le moteur non-importable, 3 constantes de marchés actifs (buts par équipe, total, handicap) et 2 fonctions de lecture des cotes utilisées par tout le pipeline avaient disparu. Corrigé et vérifié (54/54 tests, import complet OK) avant que le run suivant ne parte. **Leçon retenue : après toute suppression volontaire de code, vérifier l'import complet du moteur et la suite de tests avant de committer — pas seulement que les occurrences ciblées ont disparu.**

---

## 2. Feuille de route priorisée

### P0 — Bloquant avant nouveau gros run

#### P0.1 Publication GitHub atomique et sans conflit
**Problème confirmé par le run #129.**

Objectif :
- empêcher qu'un run long termine correctement puis perde ses résultats au dernier `git pull --rebase`;
- gérer explicitement la concurrence entre run planifié et run manuel;
- ne jamais écraser silencieusement le travail arrivé sur `main` pendant le calcul.

Critères de sortie :
- un run complet peut publier ses résultats même si `main` a avancé pendant son exécution;
- aucune donnée produite n'est perdue;
- aucun conflit manuel ne doit être requis depuis l'iPhone.

#### P0.2 Réduire le temps du pré-calcul / Betpawa
**Problème confirmé : ~80,5 min de Betpawa dans le run #128.**

Constats :
- 976 tentatives ;
- 440 cache hits ;
- 121 trouvailles fraîches ;
- 48 ambiguës ;
- 367 non trouvées ;
- 193 titres mismatch ;
- 0 erreur technique ;
- durée Betpawa ~4829 s.

Objectif : réduire fortement le temps sans relâcher la règle de sécurité « mieux vaut aucun match qu'un mauvais match ».

Critères de sortie :
- durée mesurée avant/après ;
- taux de correspondances correctes conservé ;
- aucune acceptation d'un match ambigu.

---

### P1 — Justifications : terminer l'intégration proprement

#### P1.1 Brancher réellement `rattrapage_justification.py`
Le script corrigé existe mais n'est pas appelé par `pipeline.yml`.

Objectif :
- faire tourner le rattrapage sur les fenêtres réellement produites ;
- transmettre H2H quand disponible ;
- distinguer recalcul, preuve spécifique, EV seul et absence de preuve.

#### P1.2 Supprimer le pont implicite cote/probabilité
**FAIT (session du 19-20/09, voir TRANSITION.md §52).** Le pont `inspect.currentframe()` a été retiré de `justification.py` ; `odds_scraped`/`market_prob_pct` sont désormais transmis explicitement aux deux points d'appel de `main.py`.

#### P1.5 (nouveau) Règle maîtresse : justification spécifique obligatoire par marché retenu
**FAIT, à valider sur le prochain run réel.** Un marché retenu sans preuve spécifique (pas seulement l'EV générique) est désormais rejeté avant sélection (`JUSTIFICATION_INSUFFISANTE`). Impact quantifié sur le run du 19/09 : 22 des 32 sélections auraient été rejetées sous cette règle — à surveiller au prochain run, le volume de sélections réelles va mécaniquement baisser.

#### P1.6 (nouveau) Handicap : marché mort depuis le 15/09, pas seulement biaisé
**Découvert en session du 19-20/09.** La regex de parsing (`_RE_HANDICAP_3`) ne correspond à aucun libellé Betpawa réel depuis le commit `cc1f860` du 15/09 — le marché Handicap ne peut plus être sélectionné du tout. Une regex antérieure correcte existe dans l'historique (`_RE_HANDICAP`, format réel `"Handicap X - Domicile/Extérieur"`, 2 issues, ligne signée). Un bug de signe distinct a aussi été prouvé numériquement sur les lignes positives (inversion), mais n'explique pas l'échec des lignes négatives observé dans l'archive — **cause encore non isolée pour ce second point**. Voir TRANSITION.md §52 pour le détail du calcul.

#### P1.3 Compléter uniquement les marchés réellement présents
Le run démontre des marchés `over_under_total_3.5_under` et `over_under_total_2.5_under` avec des preuves statistiques disponibles.

Objectif :
- définir les preuves Under à partir de données réellement disponibles ;
- ne pas inventer de métriques ;
- conserver la règle : donnée exacte → utilisée, dérivable → calculée, définition différente → refusée, absente → à ajouter.

#### P1.4 Corriger le règlement de `over_2.5`
Le run a rencontré la nomenclature réelle `over_2.5`.

Objectif :
- accepter cette nomenclature exacte dans le règlement ;
- vérifier toutes les variantes réellement émises avant modification ;
- ne pas ajouter d'alias hypothétique sans preuve dans les données.

---

### P1 — Handicap : audit séparé

**Mis à jour 19-20/09 (voir TRANSITION.md §52 et P1.6 ci-dessus) :**
- 21 observations `SELECTED` réelles réanalysées (archive continue de se résoudre) : domicile 3W/1L, extérieur 1W/13L.
- Règlement vérifié manuellement ligne à ligne par Patrick : **correct, pas la cause**.
- **Cause structurelle trouvée** : la regex de parsing ne correspond plus à aucun libellé Betpawa réel depuis le 15/09 (`cc1f860`) — le marché est mort, pas juste biaisé.
- Bug de signe prouvé numériquement sur les lignes positives (formule actuelle inverse le signe), mais insuffisant pour expliquer l'échec sur les lignes négatives observé dans l'archive.
- **Reste à faire** : isoler la cause de l'échec sur les lignes négatives ; corriger le parsing avec la regex retrouvée dans l'historique (`_RE_HANDICAP`) ; revalider avec les 21 observations réelles avant toute nouvelle confiance dans ce marché.

**Critère de sortie :** convention mathématique et sens du marché démontrés par des cas réels — pas encore atteint.

---

### P2 — Calibration et validation prédictive

#### P2.1 Ne pas promouvoir de nouveau paramètre avec N insuffisant
Le run #128 n'a produit aucune promotion de calibration.

Le protocole reste :
1. observations admissibles ;
2. dédoublonnage par `match_id` ;
3. exclusion des observations contaminées ;
4. N global ;
5. Brier/log-loss ;
6. calibration par bins ;
7. transformation éventuelle apprise chronologiquement puis évaluée hors échantillon.

Jalon cible de travail : accumuler environ 150–200 observations propres avant de prétendre identifier une calibration globale exploitable.

#### P2.2 Rejouer le fixture 68/48 verrouillé
La suite permanente et le fixture historique doivent rester protégés.

Objectif :
- vérifier toute modification contre le rejeu attendu ;
- ne jamais utiliser une modification de production pour masquer une divergence du fixture.

#### P2.3 Rollback automatique
`garde_fous.verifier_rollback()` existe mais n'est pas appelé par `calibre_archetype_model.py`.

Objectif : intégrer un rollback vérifiable après promotion, sans contourner les garde-fous.

---

### P2 — Qualité des données / audit

#### P2.4 Télémétrie de résultats
Le module d'audit passif est branché mais `telemetry.enregistre_scores_probabilistes()` n'est pas encore alimenté automatiquement par la résolution réelle.

Objectif : fermer la boucle score → résultat → Brier/log-loss.

#### P2.5 Divergence du rejeu 10/09
Le rejeu réel connu a produit 35 candidats / 29 matchs au lieu des 68 / 48 attendus.

Objectif : expliquer cette divergence avant de considérer la suite permanente comme représentative du comportement actuel.

---

### P3 — Interface / présentation

À traiter après stabilisation des données et du moteur :
- afficher uniquement les justifications effectivement produites ;
- supprimer les anciens textes historiques uniquement lorsque leur source active a été vérifiée ;
- conserver la carte prototype : pronostic principal visible en état replié, détails complets après dépliage, autres pronostics accessibles ensuite ;
- vérifier les boutons « Analyse » du panier ;
- maintenir la lisibilité iPhone 414 px et les couleurs validées.

---

## 3. Ordre strict d'exécution

1. **Corriger la publication GitHub du workflow (#129).**
2. **Réduire le temps Betpawa sans diminuer la sécurité du matching.**
3. **Brancher le rattrapage des justifications.**
4. **Corriger le passage explicite cote/probabilité.**
5. **Compléter les preuves Under réellement présentes.**
6. **Corriger le règlement `over_2.5`.**
7. **Auditer Handicap indépendamment.**
8. **Accumuler les observations propres et reprendre le protocole de calibration.**
9. **Résoudre la divergence du rejeu 68/48.**
10. **Seulement ensuite reprendre les finitions UI dépendantes des données.**

---

## 4. Règles de sécurité de la feuille de route

- Ne pas modifier `calculs.py`, `run_pipeline.py` ou `scraper_details.py` sans preuve et test ciblé.
- Ne pas relâcher le matching Betpawa pour améliorer artificiellement le taux de trouvés.
- Ne pas transformer une absence de preuve en justification marketing.
- Ne pas promouvoir une calibration sur un échantillon insuffisant.
- Ne pas confondre validation logique et validation prédictive.
- Ne pas considérer un run GitHub vert comme preuve suffisante : inspecter les fichiers produits.
- Le nouveau dictionnaire de justification prévaut sur les anciens textes lorsqu'il y a conflit.
- Les anciennes données historiques ne doivent pas être réécrites à l'aveugle.

---

## 5. Point de reprise

**Après le run #129 :** le prochain chantier n'est pas de relancer le pipeline.

Il faut d'abord rendre sa phase de publication robuste. Le run #129 a démontré que le calcul peut aller jusqu'au bout pendant plus de deux heures, puis échouer uniquement au moment de publier les résultats.

Une fois ce verrou levé, un run court de validation ciblée doit précéder tout nouveau run complet.
