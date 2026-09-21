# ROADMAP — Archetype Foot

> Les renvois « TRANSITION.md §N » de ce document désignent l'ancien journal de sessions, supprimé le 21/09/2026.
> Il reste lisible dans l'historique Git : `git show c1ce4c9:TRANSITION.md`.

Suivi des chantiers majeurs. Les statuts ci-dessous reposent sur des vérifications réelles du dépôt, des exécutions GitHub Actions et des fichiers produits. Aucune conclusion ne doit être tirée d'un simple statut vert sans inspection des sorties.

Dernière mise à jour : 21/09/2026 — après les sessions du 20-21/09 (refonte de l'interface, bibliothèque de justification étendue, README). Vérifications faites le 21/09 sur le dépôt (commit `a3d2b77`), sur l'API GitHub Actions et sur les fichiers produits.

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

- **Aucune donnée fraîche depuis le run #132.** Le site affiche donc encore les matchs du 20/09. Prochain run planifié : 21/09 à 21:00 UTC.
- Le run #132 est le dernier exécuté avant les corrections de la bibliothèque (21/09). **Le prochain run sera le premier à exécuter** : les nouveaux textes par marché, l'export de `bibliotheque` dans `precalcul_leger.json` et les corrections X2 / 1X2 extérieur. À inspecter (voir §5).
- Le 21/09, `precalcul_leger.json` a été enrichi à la main de `bibliotheque` : ajout uniquement, identique à la sortie de `precalcul._leger_pour_site` sur `precalcul.json` (vérifié ; aucune valeur retirée ni modifiée).

### Réalisé depuis la mise à jour du 20/09
- **Interface Archetype entièrement refaite** (20/09) d'après la maquette : nouveaux `archetype.html` / `archetype.css` / `archetype.js`, classes `ax-`, sans `!important`, ancien `archetype-prototype.css` supprimé. Le panier utilise les mêmes cartes.
- **Trois onglets** Favori du Modèle / Value Bet / Coup de Poker (réattribution des choix P1/P2/P3 côté site), aperçu replié qui suit l'onglet actif, phrase de justification sous chaque marché.
- **Tableaux de « Détails de l'analyse »** (21/09) : synthèse, preuves avec icônes (contrat visuel `ui_mappings.js`), forme domicile / extérieur, H2H, métriques combinées, badge Value Bet.
- **Bibliothèque de justification** (21/09) : deux plantages corrigés dans la branche X2 / 1X2 extérieur (`NameError`, `KeyError`, introduits le 20/09 par `6f60b3b`, jamais exécutés en production), texte X2 corrigé (il affirmait « sans défaite » pour une série « sans victoire »), textes ajoutés pour le nul, la double chance 12, « les deux équipes marquent : non », les lignes de buts quelconques et les buts d'une équipe.
- **Fichier allégé du site** : `precalcul.py` et `rattrapage_justification.py` exportent maintenant `bibliotheque`.
- **Tests** : 109 tests Python passent (dont 52 sur la couverture des marchés).
- **Documentation** : `README.md` créé ; `TRANSITION.md` et `TRANSITION 4.md` supprimés.

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

#### P0.3 (nouveau) Filet de sécurité avant publication — **À FAIRE**
Le workflow ne lance **ni `pytest`, ni contrôle de compilation Python, ni `node --check`** sur les scripts du site. Trois casses sont passées inaperçues jusqu'à ce que quelqu'un ouvre la page ou lance le code :
- 19/09 : erreur de syntaxe rendant le moteur non-importable (voir incident ci-dessus) ;
- 19/09 : `traduction_marches.js` en erreur de syntaxe → page Archetype vide ;
- 20/09 : `NameError` dans la bibliothèque (`6f60b3b`), détecté seulement le 21/09.

Objectif : `python -m pytest tests -q`, compilation de tous les `.py` et `node --check` des scripts du site avant l'étape de publication. Critère de sortie : une casse fait échouer le job **avant** le commit/push. Aucun test automatique de l'interface n'est versionné aujourd'hui.

---

### P1 — Justifications et marchés

#### P1.1 Brancher réellement `rattrapage_justification.py` — **À FAIRE**
Confirmé le 21/09 : aucun workflow ni script ne l'appelle. Il ne fait que recalculer les textes des candidats déjà retenus : il ne peut pas ajouter un marché rejeté auparavant (voir P1.3). Sa copie de `_leger_pour_site` exporte désormais `bibliotheque`.

#### P1.2 Supprimer le pont implicite cote/probabilité — **FAIT** (session du 19-20/09)
Le pont `inspect.currentframe()` a été retiré de `justification.py` (0 occurrence, vérifié le 21/09) ; `odds_scraped` et `market_prob_pct` sont transmis explicitement.

#### P1.3 Compléter les marchés réellement présents — **FAIT** (21/09), à valider sur le prochain run réel
La bibliothèque produit désormais un texte spécifique, calculé sur les historiques réels, pour : 1X2 (domicile, nul, extérieur), double chance (1X, 12, X2), les deux équipes marquent (oui, non), plus/moins de buts (toutes les lignes, y compris « moins de X »), buts d'une équipe. Le H2H « historique fermé » des marchés « under », qui ne pouvait jamais être produit, fonctionne.
- Non couverts : handicap à 3 issues (aucune cote ne lui parvient, voir P1.6) et cage inviolée (ancien moteur).
- Rejouée sur les 8 marchés éligibles rejetés au run #132 : **6 obtiennent un texte**, 2 restent rejetés faute de données (règle NO DATA → NO GO respectée). Sur 216 matchs réels, plus aucune exception.
- Les seuils des nouveaux textes reprennent ceux de la bibliothèque (70/30 %, 75/25 %, minimum 5 matchs au total et 3 par lieu) ; 20 % de nuls pour la double chance 12 et 35 % pour le nul ont été choisis lors de l'ajout.
- Effet attendu : davantage de choix retenus (P2/P3, donc onglets Value Bet et Coup de Poker) **à partir du prochain run complet**. À mesurer, pas à présumer.

#### P1.4 Corriger le règlement de `over_2.5` — **À FAIRE** (confirmé le 21/09)
`evaluer_marche("over_2.5", …)` renvoie `MARCHE_NON_RECONNU`, alors que le moteur **émet encore** ce nom (216 diagnostics au run du 20/09) et que la bibliothèque le reconnaît. Conséquence : 19 enregistrements d'archive dont le match est déjà joué restent `PENDING` pour toujours (26 au total avec ceux du 20/09), donc n'entrent jamais dans le bilan ni la calibration. `over_1.5` et `under_2.5` sont aussi non reconnus (non émis aujourd'hui).
Objectif : accepter la nomenclature réellement émise, vérifier toutes les variantes émises avant modification, sans alias hypothétique.

#### P1.5 Règle maîtresse : justification spécifique obligatoire par marché retenu — **FAIT et VALIDÉ**
Un marché retenu sans preuve spécifique (pas seulement l'EV générique) est rejeté avant sélection (`JUSTIFICATION_INSUFFISANTE`). La règle (commit `a3112cd`, 19/09 09:01) faisait partie du run #132 : on y observe **8 marchés éligibles rejetés pour ce motif, contre 3 retenus**. Ce rejet massif venait du manque de textes par marché : voir P1.3.

#### P1.6 Handicap : marché mort depuis le 15/09 — **À FAIRE**
- La regex de parsing `_RE_HANDICAP_3` ne correspond à aucun libellé BetPawa réel depuis `cc1f860` (15/09). Au run du 20/09, **894 libellés** « Handicap N – Domicile / Extérieur » ont été écartés (format à 2 issues) et le handicap à 3 issues ne reçoit aucune cote.
- Archive : 21 observations `SELECTED` résolues ; l'archive en compte **4 gagnées** (dont 1 sur 17 « extérieur »). Le règlement lui-même a été vérifié ligne à ligne par Patrick : correct.
- **Piste (audit indépendant du 20/09, recontrôlée le 21/09)** : le libellé « Extérieur » porte la ligne du **domicile** (`run_pipeline.py`, génération des libellés : l'extérieur couvre avec l'opposé). `reglement.py` lit ce libellé littéralement. Relus avec la ligne opposée, **12 des 21** choix gagnent (au lieu de 4), ce qui explique l'essentiel de l'échec observé sur les lignes « extérieur ». Inférence appuyée sur l'ordre de grandeur des cotes et sur le code : à confirmer avec un écran BetPawa. Elle ne rend pas le modèle bon pour autant (12/21 contre 83 % annoncés).
- Reste à faire : confirmer la convention sur un cas réel ; corriger le parsing avec la regex de l'historique (`_RE_HANDICAP`) ; corriger la convention de l'extérieur (au niveau du libellé ou du règlement, à décider) ; revalider sur les 21 observations réelles.

Critère de sortie : convention mathématique et sens du marché démontrés par des cas réels — pas encore atteint.

#### P1.7 (nouveau) Historiques de buts du scraping — **À FAIRE**
Constat du 21/09 sur `cache_equipes.json` : **161 équipes sur 1 750 (9 %) sans aucun historique** (`aucun_match_joue_saison_actuelle_ou_precedente`), concentrées sur des championnats à saison calendaire : Suède (45), Norvège (40), Estonie (14), Biélorussie (13), Japon (6), Corée du Sud (5)… Ces équipes ont pourtant joué. **Cause non établie** (hypothèse à tester : format du sélecteur de saison ; voir `diagnostic_selecteur_saison.py`).
Autres constats à instruire :
- `cache_equipes` garde les **10 premiers** matchs de la liste dans l'ordre de la page (les plus anciens) et complète avec la saison précédente : en début de saison, l'historique mélange deux saisons. `archetype_model/data/loader.py` ne le fait pas (saison en cours seule).
- Premier League : des scores du cache contredisent le classement officiel (exemple : un 10-1 pour Bournemouth le 20/09). Le pipeline ne détecte pas ces écarts.
Objectif : diagnostic reproductible sur ces championnats ; contrôle automatique « historique du cache = classement officiel ».

#### P1.8 (nouveau) Brancher le nouveau moteur d'analyse — **À VENIR** (annoncé par le propriétaire le 21/09)
Points d'attache du site, à respecter ou à adapter explicitement :
- filtre d'affichage (page principale et panier, fonction `aAuMoinsUnCandidat`) : `moteur_utilise === "archetype_model"` et au moins un choix parmi P1, P2, P3 ; **le site ne vérifie pas `statut`**. `estArchetypeGo` (statut `OK` et P1 requis) est conservée mais n'est plus utilisée par les pages ;
- par choix : `marche`, `cote`, `probabilite`, `edge`, `edv`, `niveau`, `robustesse`, `justification { resume, preuves[{type, texte, valeur}], donnees_suffisantes, bibliotheque }` ;
- `_leger_pour_site` (`precalcul.py`) décide ce qui parvient au site ; `bibliotheque` n'y est exportée que si c'est un dictionnaire ;
- réattribution en onglets côté site (`remappeEnOngletsApp`) : Favori = probabilité la plus haute, Value Bet = meilleur EDV parmi les restants, Coup de Poker = premier restant avec cote ≥ 2,91 et probabilité ≥ 20 % ;
- tout type de preuve inconnu s'affiche avec son nom brut (voir `ui_mappings.js`) : ajouter son libellé et son icône.

---

### P2 — Calibration et validation prédictive

#### P2.1 Ne pas promouvoir de nouveau paramètre avec N insuffisant — **À TRANCHER**
Journal au 21/09 : 139 décisions, **138 rejetées, 1 promue** : le 20/09, `EDV_MIN_P_71_75` de 0,05 à 0,048, sur **N = 55**. Le garde-fou codé (`garde_fous.py`) exige `TAILLE_MIN_STANDARD = 50` observations (100 pour `COTE_MIN` / `COTE_MAX`) : la promotion est **conforme au code**, mais très en dessous du jalon de cette feuille de route (150-200 observations propres).
À trancher : relever `TAILLE_MIN_STANDARD` pour l'aligner sur le jalon, ou assumer 50 (dans les deux cas, écrire la décision ici). Protocole cible inchangé : observations admissibles ; dédoublonnage par `match_id` ; exclusion des observations contaminées ; N global ; Brier/log-loss ; calibration par bins ; transformation apprise chronologiquement puis évaluée hors échantillon.

#### P2.2 Rejouer le fixture 68/48 verrouillé — **NON VÉRIFIÉ**
La suite permanente et le fixture historique doivent rester protégés ; ne jamais utiliser une modification de production pour masquer une divergence du fixture. Le 21/09, `audit_permanent.py` donne **256 contrôles OK et 9 FAIL, identiques avant et après les modifications de la bibliothèque** : combos (garde-fous CAS 1-4 et 6), « CAS 1 : les 12 candidats v2 », périmètre dynamique du handicap −0.5, deux contrôles `odds_provider`. Les échecs de combos sont probablement liés au retrait des combos du 19/09 (à confirmer) : à instruire ou à retirer de la suite.

#### P2.3 Rollback automatique — **À FAIRE**
`garde_fous.verifier_rollback()` existe (seuil de dégradation de ROI de 10 %) mais n'est toujours pas appelé par `calibre_archetype_model.py` (confirmé le 21/09).

#### P2.4 Télémétrie de résultats — **À FAIRE**
`telemetry.enregistre_scores_probabilistes()` n'est toujours appelée par aucun script (confirmé le 21/09) : la boucle score → résultat → Brier/log-loss reste ouverte.

#### P2.5 Divergence du rejeu 10/09 — **NON VÉRIFIÉ**
Le rejeu réel connu a produit 35 candidats / 29 matchs au lieu des 68 / 48 attendus. À expliquer avant de considérer la suite permanente comme représentative.

#### P2.6 (nouveau) Calibration des probabilités du modèle — **À FAIRE**
Constat de l'audit indépendant du 20/09, recalculé le 21/09 sur l'archive (13-20/09, 8 jours, observations corrélées entre elles : à lire comme un signal, pas comme une preuve définitive) :
- 87 choix `SELECTED` résolus : **55,2 % gagnés pour 82,5 % annoncés** ; ROI à plat −19,5 % ; score de Brier 0,315 pour le modèle contre 0,252 pour la probabilité implicite de la cote. L'écart de calibration représente environ 5 écarts-types ; le ROI négatif environ 2,5 (indicatif).
- Sur les 294 marchés non retenus, le modèle est au niveau du marché (Brier 0,203 contre 0,201) : c'est la **sélection** (filtre EDV) qui retient les erreurs du modèle.
- La calibration adaptative règle des seuils d'EDV, pas la probabilité : elle ne peut pas corriger ce défaut.
- Pistes à instruire : la matrice est une Poisson indépendante (aucune correction de type Dixon-Coles, malgré le docstring de `correlation.py`) ; λ estimé sur 5 à 12 matchs de la saison en cours puis restreint au lieu (environ 3 à 6 matchs) ; la marge du bookmaker n'est pas retirée de la probabilité implicite.
Critère de sortie : mesure sur 150-200 sélections propres avant toute conclusion ; aucune modification du modèle sans cette mesure.

---

### P3 — Interface / présentation

Fait le 20-21/09 : refonte de la page Archetype, panier identique, onglets, aperçu replié compact, phrase de justification sous chaque marché, tableaux de détails, mode nuit, cibles tactiles de 44 px.

Reste à traiter :
- **Page Système** : le tableau `tableau-systeme` (391 px) déborde sur les écrans de 390 px ou moins (+15 px à 390 px, +29 px à 375 px, +84 px à 320 px) ; correct à 414 px.
- **Onglets Value Bet et Coup de Poker jamais vus sur des données réelles** (un seul choix par match à ce jour) : à vérifier après le prochain run complet. Point de vigilance : sur les 106 sélections du 13-20/09, la cote maximale est 1,79 ; **aucune n'atteint le seuil de 2,91** de Coup de Poker. Sans évolution de la fourchette de cotes du moteur, cet onglet ne peut pas se remplir.
- **Tableaux de détails** : les lignes dépendant de champs nouveaux (`away_unbeaten_streak`, `away_win_rate`, `draw_rate_combined`…) n'apparaîtront qu'après un run complet.
- **Accueil, Système, Admin** utilisent encore l'ancienne charte (`style.css` + `theme.css`, avec de nombreux `!important`).
- **Admin** : le mot de passe est écrit en clair dans `admin.js` et le site publie toute la racine du dépôt (dépôt privé, site public). Envisager une protection côté hébergeur.
- Conserver la lisibilité iPhone 375-414 px et les couleurs validées.

---

## 3. Ordre strict d'exécution

1. **Corriger la publication GitHub du workflow (P0.1)** — à faire.
2. **Ajouter le filet de sécurité avant publication (P0.3)** — à faire.
3. **Réduire le temps BetPawa sans diminuer la sécurité du matching (P0.2)** — à faire.
4. **Brancher le rattrapage des justifications (P1.1)** — à faire.
5. ~~Corriger le passage explicite cote/probabilité (P1.2)~~ — fait.
6. ~~Compléter les preuves des marchés réellement présents (P1.3)~~ — fait le 21/09, à valider sur le prochain run.
7. **Corriger le règlement `over_2.5` (P1.4)** — à faire.
8. **Auditer et corriger Handicap indépendamment (P1.6)** — à faire.
9. **Diagnostiquer les historiques de scraping manquants (P1.7)** — à faire.
10. **Trancher le seuil de promotion de la calibration (P2.1), accumuler les observations propres, mesurer la calibration des probabilités (P2.6)** — à faire.
11. **Résoudre la divergence du rejeu 68/48 et nettoyer la suite permanente (P2.2, P2.5)** — non vérifié.
12. **Brancher le nouveau moteur (P1.8), puis les finitions UI dépendantes des données (P3).**

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

**Situation.** Le pipeline n'a produit aucune donnée depuis le run #132 (20/09 00:19 UTC) ; le run #133 a été annulé. La publication (P0.1) et le filet de sécurité (P0.3) ne sont toujours pas traités.

**Avant tout nouveau run complet :** traiter P0.1 et P0.3 ; un run court de validation ciblée (`workflow_dispatch` avec une limite BetPawa) doit précéder un run complet.

**Au prochain run complet (le planifié de 21:00 UTC, ou un run manuel), inspecter les fichiers produits et pas seulement la couleur du run :**
1. le job ne s'arrête pas sur une exception de la bibliothèque (X2, 1X2 extérieur) ;
2. `precalcul_leger.json` contient `bibliotheque` pour chaque choix retenu ;
3. le nombre de marchés rejetés en `JUSTIFICATION_INSUFFISANTE` a baissé (8 au run #132) et de nouveaux choix P2/P3 apparaissent ;
4. les tableaux de « Détails de l'analyse » affichent les nouvelles lignes, sans « — » ;
5. la page Archetype montre les matchs du jour, et pas ceux du 20/09.

Puis reprendre l'ordre du §3.
