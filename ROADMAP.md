# ROADMAP — Archetype Foot

> Les renvois « TRANSITION.md §N » de ce document désignent l'ancien journal de sessions, supprimé le 21/09/2026.
> Il reste lisible dans l'historique Git : `git show c1ce4c9:TRANSITION.md`.

Suivi des chantiers majeurs. Les statuts ci-dessous reposent sur des vérifications réelles du dépôt, des exécutions GitHub Actions et des fichiers produits. Aucune conclusion ne doit être tirée d'un simple statut vert sans inspection des sorties.

Dernière mise à jour : 21/09/2026 — après les sessions du 20-21/09 (refonte de l'interface, bibliothèque de justification étendue, README) et le **branchement du moteur v2.6.9**. Vérifications faites le 21/09 sur le dépôt (commit `a3d2b77`), sur l'API GitHub Actions et sur les fichiers produits.

Statuts : **FAIT** · **EN COURS** · **À FAIRE** · **NON VÉRIFIÉ** (non re-contrôlé le 21/09).

---

## 1. État immédiat

### Exécutions du workflow `pipeline.yml` (API GitHub, 21/09)

| Run | Type | Résultat | Durée | Commit |
|---|---|---|---|---|
| #128 | manuel | succès | 2 h 51 | `4f77286` |
| #129 | planifié | **échec** (publication, voir ci-dessous) | 4 h 28 | `4f77286` |
| #130 | planifié | succès | 3 h 25 | `92a5725` |
| #131 | manuel | succès | 2 h 23 | `fbee644` |
| #132 | planifié | succès (dernier à avoir publié, 20/09 00:19 UTC) | 1 h 29 | `62111ce` |
| #133 | planifié | **annulé** après 28 min (20/09, 23:06 UTC ; cause non déterminée) | 0 h 28 | `97db2d9` |
| #134 | manuel (`jours` = 2) | **échec en 52 s** à l'étape d'autotests (21/09, 12:50 UTC) : un de mes tests importait PyYAML, absent du runner, et lisait un chemin absolu de la machine de développement. Rien n'a été scrapé ni publié | 0 h 01 | `565ce32` |

- **Aucune donnée fraîche depuis le run #132.** Le site affiche donc encore les matchs du 20/09. Prochain run planifié : 21/09 à 21:00 UTC.
- Le run #132 est le dernier exécuté avant les corrections de la bibliothèque (21/09). **Le prochain run sera le premier à exécuter** : les nouveaux textes par marché, l'export de `bibliotheque` dans `precalcul_leger.json` et les corrections X2 / 1X2 extérieur. À inspecter (voir §5).
- Le 21/09, `precalcul_leger.json` a été enrichi à la main de `bibliotheque` : ajout uniquement, identique à la sortie de `precalcul._leger_pour_site` sur `precalcul.json` (vérifié ; aucune valeur retirée ni modifiée).

### Réalisé depuis la mise à jour du 20/09
- **Interface Archetype entièrement refaite** (20/09) d'après la maquette : nouveaux `archetype.html` / `archetype.css` / `archetype.js`, classes `ax-`, sans `!important`, ancien `archetype-prototype.css` supprimé. Le panier utilise les mêmes cartes.
- **Trois onglets** Favori du Modèle / Value Bet / Coup de Poker (réattribution des choix P1/P2/P3 côté site), aperçu replié qui suit l'onglet actif, phrase de justification sous chaque marché.
- **Tableaux de « Détails de l'analyse »** (21/09) : synthèse, preuves avec icônes (contrat visuel `ui_mappings.js`), forme domicile / extérieur, H2H, métriques combinées, badge Value Bet.
- **Bibliothèque de justification** (21/09) : deux plantages corrigés dans la branche X2 / 1X2 extérieur (`NameError`, `KeyError`, introduits le 20/09 par `6f60b3b`, jamais exécutés en production), texte X2 corrigé (il affirmait « sans défaite » pour une série « sans victoire »), textes ajoutés pour le nul, la double chance 12, « les deux équipes marquent : non », les lignes de buts quelconques et les buts d'une équipe.
- **Fichier allégé du site** : `precalcul.py` exporte maintenant `bibliotheque` (`rattrapage_justification.py`, qui en avait une copie, est supprimé).
- **Tests** : 109 tests Python passent (dont 52 sur la couverture des marchés).
- **Documentation** : `README.md` créé ; `TRANSITION.md` et `TRANSITION 4.md` supprimés.
- **Nouveau moteur branché (21/09)** : `moteur_v2_6_9.py` remplace l'ancien modèle `archetype_model` dans le pipeline (via `pont_moteur.py` et `branchement_moteur.py`). L'ancien modèle est débranché (code conservé). Aucun repli sur l'ancien moteur. Le site lit le bloc `moteur_v2_6_9`. Rejeu du 20/09 (mêmes entrées, aucun nouveau scraping) : 139 matchs analysés sur 495 (305 sans cotes BetPawa, 37 sans historique), **71 matchs avec au moins un choix, 107 choix retenus** (contre 3 pour l'ancien modèle), 735 observations archivées (107 `SELECTED`, 628 `COUNTERFACTUAL`). Chaque marché produit est reconnu par le règlement.
- **Règlement corrigé (21/09)** : `1x2_domicile` / `1x2_exterieur` étaient réglés comme une double chance (un nul comptait gagné) et `1x2_nul` n'existait pas. Ne touche que 5 nuls contrefactuels déjà résolus (aucun des 87 choix `SELECTED` de l'ancien modèle) ; l'archive résolue reste immuable.
- **Filet de sécurité (21/09)** : le workflow lance les autotests du moteur et du pont puis `pytest` avant tout scraping.
- **Nettoyage de l'ancien moteur (21/09)** : `archetype_model/main.py`, `rattrapage_justification.py` et le test de bout en bout de l'ancien moteur sont supprimés ; `applique_archetype_model()` et le repli disparaissent de `precalcul.py` ; `precalcul.py` ne produit plus aucune clé `archetype_model`. Vérifié : le chemin de production redonne exactement les mêmes blocs que les données publiées (0 différence sur 495 signaux). Ce nettoyage avait laissé deux casses silencieuses, réparées : `archetype_model/backtest/boucle_b.py` non importable (`from ..main import SCENARIOS`, remplacé par `signals.convergence.SCENARIOS`, même tuple) et `audit_permanent.py` qui ne compilait plus (blocs coupés en plein milieu, plus des sections orphelines).
- **Données du moteur corrigées (21/09)** : voir P1.7 (52 % des équipes avaient un historique mélangeant les saisons ; nouvelle source `stats_saison_en_cours.py`). **Bibliothèque** : les statistiques « des deux équipes » exigent maintenant des matchs des deux équipes (cas réel Dallas : phrase calculée sur une seule). **Run limité** : option `jours = 2` (aujourd'hui + demain) au lancement manuel.
- **Tests** : plus de 320 tests Python (dont cohérence moteur ↔ règlement, contrat avec le site, et `tests/test_integrite_du_depot.py` : tout fichier compile, tout module d'`archetype_model` et tout script du workflow s'importent).

### Incidents passés (conservés pour mémoire)
**Run #129** — le job a produit un commit local, puis le `git pull --rebase` a rencontré des conflits sur les gros fichiers de données générés simultanément sur `main` (archive, caches, diagnostics, `precalcul.json`, tickets…). Le rebase n'a pas pu appliquer le commit : les résultats de plus de quatre heures de calcul n'ont pas été publiés. Ce n'était **pas un échec du moteur ni du scraping**, mais un conflit de synchronisation Git à la publication.

**Incident du 19/09 — `main` cassé** (voir TRANSITION.md §52) — le nettoyage « retirer parité et combos » (décision assumée) a accidentellement supprimé du code actif sans rapport : une erreur de syntaxe a rendu tout le moteur non-importable, 3 constantes de marchés actifs et 2 fonctions de lecture des cotes avaient disparu. Corrigé et vérifié avant le run suivant. **Leçon retenue : après toute suppression volontaire de code, vérifier l'import complet du moteur et la suite de tests avant de committer — pas seulement que les occurrences ciblées ont disparu.**

---

## 2. Feuille de route priorisée

### P0 — Bloquant avant nouveau gros run

#### P0.1 Publication GitHub atomique et sans conflit — **À FAIRE**
`pipeline.yml` n'a **pas été modifié depuis le 17/09** : l'étape de publication reste `git pull --rebase origin main` puis `git push`, sans gestion de conflit. Les runs #130, #131 et #132 ont publié sans incident, mais rien ne protège d'un nouveau conflit dès qu'un push arrive sur `main` pendant un run.

Objectif :
- empêcher qu'un run long termine correctement puis perde ses résultats au dernier `git pull --rebase` ;
- gérer explicitement la concurrence entre run planifié et run manuel ;
- ne jamais écraser silencieusement le travail arrivé sur `main` pendant le calcul.

Critères de sortie :
- un run complet peut publier ses résultats même si `main` a avancé pendant son exécution ;
- aucune donnée produite n'est perdue ;
- aucun conflit manuel ne doit être requis depuis l'iPhone.

En attendant : ne pas pousser de fichiers de données pendant qu'un run tourne (vérifier l'API avant).

#### P0.2 Réduire le temps du pré-calcul / BetPawa — **À FAIRE**
Mesures : run #128 = 976 tentatives en ~4 829 s (4,9 s par tentative) ; run #132 = 495 tentatives en 2 794 s (5,6 s par tentative). La baisse vient du nombre de matchs, **pas d'un gain par tentative**.

Détail du run #132 : 216 cache hits, 75 trouvailles fraîches, 32 ambiguës, 172 non trouvées, 112 titres en désaccord, 178 cotes extraites (36 % des 495), 0 erreur technique.

Objectif : réduire fortement le temps sans relâcher la règle de sécurité « mieux vaut aucun match qu'un mauvais match ». Critères de sortie : durée mesurée avant/après ; taux de correspondances correctes conservé ; aucune acceptation d'un match ambigu.

#### P0.3 (nouveau) Filet de sécurité avant publication — **EN COURS**
Fait le 21/09 : `pipeline.yml` lance, avant tout scraping et sans `continue-on-error`, `python moteur_v2_6_9.py --autotest`, `python pont_moteur.py --autotest` et `python -m pytest tests -q`. Un moteur cassé arrête le job en quelques secondes.
**Le filet a fonctionné le 21/09** : le run n°134 s'est arrêté en 52 s à cette étape au lieu de perdre un run entier. Cause : un test (PyYAML absent du runner + chemin absolu). Gardes ajoutées dans `tests/test_integrite_du_depot.py` : les tests n'importent que la bibliothèque standard, le dépôt et les paquets installés par le workflow, et aucun test ne lit un chemin absolu ; plus un test de fumée de `precalcul.main()` de bout en bout (réseau simulé). Vérification à faire avant tout run : `pytest` dans un environnement vierge avec les seuls paquets du workflow.
Reste à faire : aucun contrôle de syntaxe JavaScript (`node --check`) et aucun test de l'interface dans le workflow ; les tests d'affichage (Chrome) ne sont pas versionnés. Casses passées inaperçues jusqu'ici : 19/09 (moteur non-importable), 19/09 (`traduction_marches.js`), 20/09 (`NameError` de la bibliothèque).

---

### P1 — Justifications et marchés

#### P1.1 Brancher `rattrapage_justification.py` — **SANS OBJET**
Il recalculait les textes à partir des fenêtres de l'ancien modèle : sans objet avec le nouveau moteur, dont les justifications sont calculées dans le pipeline même (`branchement_moteur.py`). Fichier supprimé le 21/09.

#### P1.2 Supprimer le pont implicite cote/probabilité — **FAIT** (session du 19-20/09)
Le pont `inspect.currentframe()` a été retiré de `justification.py` (0 occurrence, vérifié le 21/09) ; `odds_scraped` et `market_prob_pct` sont transmis explicitement.

#### P1.3 Compléter les marchés réellement présents — **FAIT** (21/09), à valider sur le prochain run réel
La bibliothèque produit désormais un texte spécifique, calculé sur les historiques réels, pour : 1X2 (domicile, nul, extérieur), double chance (1X, 12, X2), les deux équipes marquent (oui, non), plus/moins de buts (toutes les lignes, y compris « moins de X »), buts d'une équipe. Le H2H « historique fermé » des marchés « under », qui ne pouvait jamais être produit, fonctionne.
- Non couverts : handicap à 3 issues (aucune cote ne lui parvient, voir P1.6) et cage inviolée (ancien moteur).
- Rejouée sur les 8 marchés éligibles rejetés au run #132 : **6 obtiennent un texte**, 2 restent rejetés faute de données (règle NO DATA → NO GO respectée). Sur 216 matchs réels, plus aucune exception.
- Les seuils des nouveaux textes reprennent ceux de la bibliothèque (70/30 %, 75/25 %, minimum 5 matchs au total et 3 par lieu) ; 20 % de nuls pour la double chance 12 et 35 % pour le nul ont été choisis lors de l'ajout.
- Effet attendu : davantage de choix retenus (P2/P3, donc onglets Value Bet et Coup de Poker) **à partir du prochain run complet**. À mesurer, pas à présumer.

#### P1.4 Corriger le règlement de `over_2.5` — **SANS OBJET pour l'avenir**
Le nouveau moteur n'émet plus `over_2.5` : il produit `over_under_total_2.5_over`, reconnu par le règlement. Restent 19 anciens enregistrements d'archive (matchs joués avant le 20/09) `PENDING` pour toujours, au nom de l'ancien modèle ; ils n'affectent pas les mesures du nouveau moteur (`model_version` distincte).

#### P1.5 Règle maîtresse : justification spécifique obligatoire par marché retenu — **FAIT et VALIDÉ**
Un marché retenu sans preuve spécifique (pas seulement l'EV générique) est rejeté avant sélection (`JUSTIFICATION_INSUFFISANTE`). La règle (commit `a3112cd`, 19/09 09:01) faisait partie du run #132 : on y observe **8 marchés éligibles rejetés pour ce motif, contre 3 retenus**. Ce rejet massif venait du manque de textes par marché : voir P1.3.

#### P1.6 Handicap — **PARTIELLEMENT RÉSOLU**
- Avec le nouveau moteur, le handicap est **évalué** : 772 lignes sur 3 517 au rejeu du 20/09 (BetPawa « 2-way handicap » et « handicap à 3 choix »). Le nom canonique porte la ligne de l'équipe nommée (`handicap_exterieur_1.5` = extérieur à +1,5), ce que lit le règlement : la piste du signe de la ligne « extérieur » de l'ancien modèle ne se reproduit pas. Un test vérifie que la probabilité du moteur est exactement celle du règlement pour toutes les lignes.
- **Aucun handicap n'est retenu** : la bibliothèque de justification n'a pas de texte pour ce marché, donc « NO DATA → NO GO » les écarte tous. À traiter si le handicap doit être proposé.
- Le moteur traite l'égalité sur une ligne entière comme **perdante** (marché à 3 issues), comme le règlement. Le handicap à 2 issues (remboursement) ne serait pas réglé correctement : à ne pas activer sans adapter le règlement.
- Reste l'archive de l'ancien modèle (21 observations, 4 gagnées, sens de la ligne « extérieur » probablement inversé) : historique non réécrit.

#### P1.7 Historiques de buts du scraping — **CORRIGÉ pour le moteur** (21/09), reste à confirmer sur un run réel
**Constat (cache du 20/09, comparé au classement officiel, 1 589 équipes)** : 52 % des équipes avaient plus de matchs que la saison en cours ne le permet (historique complété par la saison précédente), 5,5 % seulement correspondaient exactement au classement. 105 des 139 matchs analysés par le moteur, et **88 de ses 107 choix (82 %)**, reposaient sur au moins une telle équipe. Cause : `recupere_gf_ga_avec_repli` complète avec la saison précédente **et** prend les N plus anciens matchs (la page les liste du plus ancien au plus récent), ce que `loader.py` interdit explicitement (décision de Patrick du 08/09 : « invariant non négociable, à ne pas rouvrir sans lui en parler »). Conséquence pour les textes : les « séries » de la bibliothèque, comptées depuis la fin de la liste, décrivaient des matchs de la saison précédente.
**Correction** : `stats_saison_en_cours.py` (chargeur conforme, 12 plus récents par lieu, saison en cours seule, cache `cache_equipes_saison.json`) alimente désormais le moteur ; le collecteur à repli ne sert plus qu'à l'ancien calcul. Rejeu sur données correctes (fenêtres de l'ancien chargeur) : **seuls 31 % des choix de la version à repli sont retrouvés**. Les 174 phrases de justification du rejeu ont été recalculées de façon indépendante depuis les matchs bruts : 174 confirmées, 0 écart.
**Effet à connaître** : en début de saison les échantillons par lieu sont petits (médiane 4 matchs à domicile, 3 à l'extérieur) ; 51 des 74 choix du rejeu portent l'avertissement « Fenêtre d'analyse trop courte ». **Décision du propriétaire (21/09)** : un match n'est analysé que si l'équipe qui reçoit a ≥ 2 matchs à domicile et la visiteuse ≥ 2 à l'extérieur (règle D6 de `branchement_moteur.py`, `MIN_MATCHS_PAR_LIEU`) ; sinon refus `echantillon_insuffisant`, seules les conditions irréfutables (pas de cotes, match commencé/reporté, cotes inexploitables, validations V1-V12) refusent en plus. Articulation avec la bibliothèque : ses statistiques de forme exigent 3 matchs par lieu ; à 2 matchs seule la justification par le H2H ou par l'autre équipe est possible, le match est analysé mais souvent sans choix (rejeu du 20/09 : 8 matchs sur 21 avec un échantillon minimal de 2 produisent un choix, contre 27 sur 36 à 3-4 et 16 sur 25 à 5 et plus). Aucune value bet ne se perd en silence (contrôlé par un test aléatoire de 600 matchs). Non observée sur le rejeu (les équipes sans match au lieu y étaient déjà écartées) : à vérifier au premier run réel, ligne `raisons des refus`.
Reste : 161 équipes sur 1 750 (Suède, Norvège, Estonie, Biélorussie, Japon, Corée du Sud…) sans aucun historique, cause non établie (hypothèse : format du sélecteur de saison des championnats à saison calendaire) ; scores du cache contredisant le classement pour quelques équipes (12 cas, ex. Manchester City) ; le pipeline ne détecte pas ces écarts. Piste : contrôle automatique « historique = classement officiel ».

#### P1.8 Brancher le nouveau moteur d'analyse — **FAIT** (21/09), à valider sur le prochain run réel
`moteur_v2_6_9.py` est le moteur du pipeline. Contrat avec le site, à respecter pour tout futur moteur :
- filtre d'affichage (page principale et panier) : `moteur_utilise === CLE_MOTEUR` et au moins un choix parmi P1, P2, P3 ; **le site ne vérifie pas `statut`** ;
- par choix : `marche` (nom canonique), `cote`, `probabilite`, `edge`, `edv`, `niveau` (`CAT_A/B/C`), `robustesse` (`null` : pas d'analyse de robustesse), `points_de_vigilance`, `justification { resume, preuves[{type, texte, valeur}], donnees_suffisantes, bibliotheque }` ;
- `_leger_pour_site` (`precalcul.py`) décide ce qui parvient au site ;
- réattribution en onglets côté site (`remappeEnOngletsApp`), mêmes règles que le backend : un test de contrat les compare sur 300 tirages ;
- tout type de preuve inconnu s'affiche avec son nom brut (voir `ui_mappings.js`).
À valider au premier run réel (un run `jours = 2` a été prévu avant le run complet) : statuts (`OK` / `NON_EXPORTABLE` / `SKIP` / `ERREUR_TECHNIQUE` dans le log `moteur_v2_6_9 -- statuts`), aucune `ERREUR_TECHNIQUE`, `export_moteur/` produit, archive `model_version = moteur_v2_6_9`. Limites connues : `heure` d'un signal (heure d'export) ; données d'équipe = les 10 premiers matchs de la liste (voir P1.7).

---

### P2 — Calibration et validation prédictive

#### P2.1 Calibration adaptative — **DÉBRANCHÉE** (21/09)
Elle réglait les paramètres de l'ancien modèle ; le nouveau moteur a des constantes fixes. L'étape est commentée dans `pipeline.yml`. La promotion du 20/09 (`EDV_MIN_P_71_75`, N = 55) est désormais sans effet. Si une calibration du nouveau moteur est décidée, elle repartira du protocole ci-dessous (observations admissibles ; dédoublonnage par `match_id` ; exclusion des observations contaminées ; N global ; Brier/log-loss ; calibration par bins ; transformation apprise chronologiquement puis évaluée hors échantillon) et d'un seuil d'échantillon à décider (le garde-fou de l'ancien code : 50).

#### P2.2 Rejouer le fixture 68/48 verrouillé — **NON VÉRIFIÉ** ; suite permanente réparée
La suite permanente et le fixture historique doivent rester protégés ; ne jamais utiliser une modification de production pour masquer une divergence du fixture.

`audit_permanent.py` (lancé à la main, hors workflow), audit **complet** :
- avant le nettoyage (`5907eb5`) : 464 OK / 24 échecs ;
- après le nettoyage et les réparations du 21/09 : **434 OK / 13 échecs**, aucun échec nouveau, aucun contrôle passé de OK à échec. 41 contrôles ont quitté la suite avec les sections de l'ancien moteur (dont 11 qui échouaient).
- Les 13 échecs restants **préexistent** : 2 sur `odds_provider` (traduction des libellés de handicap) et 11 sur l'ancienne API de justification (`construit_justification`, `construit_raison_selection`, `enrichit_justification_selection`, `confirmation_historique`), dont les attentes datent d'avant la bibliothèque du 17/09. À réécrire contre la bibliothèque actuelle ou à retirer.
- Correction d'une erreur de ce document : la référence « 256 OK / 9 échecs » publiée le matin du 21/09 venait de journaux d'audit **incomplets** (lus avant la fin de l'exécution).

#### P2.3 Rollback automatique — **À FAIRE**
`garde_fous.verifier_rollback()` existe (seuil de dégradation de ROI de 10 %) mais n'est toujours pas appelé par `calibre_archetype_model.py` (confirmé le 21/09).

#### P2.4 Télémétrie de résultats — **À FAIRE**
`telemetry.enregistre_scores_probabilistes()` n'est toujours appelée par aucun script (confirmé le 21/09) : la boucle score → résultat → Brier/log-loss reste ouverte.

#### P2.5 Divergence du rejeu 10/09 — **NON VÉRIFIÉ**
Le rejeu réel connu a produit 35 candidats / 29 matchs au lieu des 68 / 48 attendus. À expliquer avant de considérer la suite permanente comme représentative.

#### P2.6 (nouveau) Calibration des probabilités — **À FAIRE, priorité du nouveau moteur**
**Nouveau moteur : aucune mesure.** Poisson indépendant, constantes non calibrées, un couple de λ par match ; rejeu du 20/09 : 107 choix pour 71 matchs (66 catégorie A, 6 B, 35 C), environ 20 % des lignes évaluées signalées value bets. L'archive (`model_version = moteur_v2_6_9`) enregistre chaque choix (`SELECTED`) et chaque value bet non retenu (`COUNTERFACTUAL`, catégorie D comprise) : c'est la base de mesure. Critère : mesurer sur 150-200 choix propres **avant** de juger le moteur, par famille de marché ; ne pas confondre volume de choix et valeur.

**Ancien modèle (référence, 13-20/09, 8 jours, observations corrélées : un signal, pas une preuve)** :
- 87 choix `SELECTED` résolus : 55,2 % gagnés pour 82,5 % annoncés ; ROI à plat −19,5 % ; Brier 0,315 (modèle) contre 0,252 (probabilité implicite de la cote).
- 294 marchés contrefactuels : Brier **0,210 pour le modèle contre 0,203 pour la cote** après correction du règlement du 21/09 (0,203 contre 0,201 avant : 5 nuls comptés à tort gagnants). Le modèle est donc légèrement **moins bon que le marché** sur ce qu'il n'a pas retenu, et beaucoup moins sur ce qu'il a retenu : la sélection (filtre EDV) retient les erreurs du modèle.
- Pistes qui valent aussi pour le nouveau moteur : Poisson indépendant sans correction de type Dixon-Coles ; λ estimé sur peu de matchs ; marge du bookmaker non retirée sur les marchés isolés (le moteur le reconnaît dans ses limites).

---

### P3 — Interface / présentation

Fait le 20-21/09 : refonte de la page Archetype, panier identique, onglets, aperçu replié compact, phrase de justification sous chaque marché, tableaux de détails, points de vigilance du moteur, mode nuit, cibles tactiles de 44 px. Testé sur les 71 cartes du rejeu (Chrome, 320 à 1024 px, jour et nuit) : pas d'erreur, pas de débordement ; panier identique à la page principale (hauteurs identiques à 414 px ; à 375 px, 4 cartes sur 71 diffèrent d'une ligne quand le nom de la compétition est très long).

Reste à traiter :
- **Page Système** : le tableau `tableau-systeme` (391 px) déborde sur les écrans de 390 px ou moins (+15 px à 390 px, +29 px à 375 px, +84 px à 320 px) ; correct à 414 px.
- **Onglets** : sur le rejeu, 34 cartes sur 71 ont au moins 2 onglets, 2 ont les 3 ; le Coup de Poker n'apparaît que sur 2 matchs (cote maximale 3,41).
- **Volume** : 71 cartes dans une journée, sans regroupement ni filtre ; à revoir si le volume reste tel quel.
- **Accueil, Système, Admin** utilisent encore l'ancienne charte (`style.css` + `theme.css`, avec de nombreux `!important`). La page Admin lit `data/audit_*.json`, figés depuis le débranchement de l'audit passif.
- **Admin** : mot de passe en clair dans `admin.js` et site publiant toute la racine du dépôt (dépôt privé, site public). Envisager une protection côté hébergeur.
- Conserver la lisibilité iPhone 375-414 px et les couleurs validées.

---

## 3. Ordre strict d'exécution

1. **Corriger la publication GitHub du workflow (P0.1)** — à faire.
2. **Compléter le filet de sécurité avant publication (P0.3)** — en cours (autotests et `pytest` faits ; reste le contrôle JavaScript).
3. **Réduire le temps BetPawa sans diminuer la sécurité du matching (P0.2)** — à faire.
4. ~~Brancher le rattrapage des justifications (P1.1)~~ — sans objet avec le nouveau moteur.
5. ~~Corriger le passage explicite cote/probabilité (P1.2)~~ — fait.
6. ~~Compléter les preuves des marchés réellement présents (P1.3)~~ — fait le 21/09, à valider sur le prochain run.
7. ~~Corriger le règlement `over_2.5` (P1.4)~~ — sans objet pour le nouveau moteur.
8. **Handicap (P1.6)** — évalué par le moteur, jamais retenu faute de texte de justification ; à décider.
9. **Diagnostiquer les historiques de scraping manquants (P1.7)** — à faire.
10. **Accumuler les observations propres du nouveau moteur et mesurer sa calibration (P2.6)** — à faire (la calibration adaptative est débranchée, P2.1).
11. **Résoudre la divergence du rejeu 68/48 et nettoyer la suite permanente (P2.2, P2.5)** — non vérifié ; `audit_permanent.py` teste encore l'ancien code.
12. ~~Brancher le nouveau moteur (P1.8)~~ — fait le 21/09 ; à valider au premier run réel. **Mesurer sa calibration (P2.6), puis les finitions UI (P3).**

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

**Situation.** Le pipeline n'a produit aucune donnée depuis le run #132 (20/09 00:19 UTC) ; le run #133 a été annulé. Le nouveau moteur est branché mais **n'a encore jamais tourné en conditions réelles** : les données publiées le 21/09 sont un rejeu des entrées du 20/09 (champ `rejeu_moteur` dans les fichiers), remplacé par le prochain run. La publication (P0.1) reste à traiter.

**Au prochain run complet (le planifié de 21:00 UTC, ou un run manuel), inspecter les fichiers produits et pas seulement la couleur du run :**
1. l'étape d'autotests passe, puis le log contient `moteur_v2_6_9 -- statuts` avec **aucune `ERREUR_TECHNIQUE`** (sinon lire les lignes `ERREUR_TECHNIQUE` sur stderr) ;
2. `export_moteur/` est produit et `diagnostic_pont.json` explique les rejets (attendu : environ 60 % sans cotes BetPawa, environ 7 % sans historique) ;
3. `precalcul_leger.json` contient, pour chaque signal analysé, le bloc `moteur_v2_6_9` avec sélection et `bibliotheque` ; le champ `rejeu_moteur` a disparu ;
4. `archive/AAAA-MM.json` reçoit des enregistrements `model_version = moteur_v2_6_9` (`SELECTED` et `COUNTERFACTUAL`) sans erreur d'archivage ;
5. la page Archetype montre les matchs du jour, et pas ceux du 20/09.

Puis reprendre l'ordre du §3.
