# Audit contradictoire Archetype Foot — feuille de route (état final)

Document de travail pour la vérification des 40 points de l'audit externe
(+ 1 point trouvé en cours de route, justifications H2H). Les 41 points
sont maintenant tous vérifiés sur le vrai code et/ou les vraies données
du dépôt — plus aucun n'est une simple hypothèse. Complète TRANSITION.md,
ne le remplace pas.

## Méthode appliquée

4 statuts : `CONFIRMÉ` (preuve directe + démonstration), `RÉFUTÉ`,
`PARTIEL/CONTEXTUEL` (réel mais nuancé), `NON DÉMONTRABLE`. Deux niveaux
de preuve : template complet (calcul/argent/identité/risque) ou léger
(reste). Regroupement par module fonctionnel puis, ici, par cause racine
pour préparer la correction groupée.

**État du code : gelé.** Seuls #5 et #12 ont été corrigés (validés
isolés, sans dépendance). Tout le reste attend l'architecture de
correction groupée ci-dessous.

---

## Tableau final — statut, gravité, module

| # | Titre | Module | Statut | Gravité |
|---|---|---|---|---|
| 1 | Calibrage cassé (`TOUS_MARCHES_EVALUES` jeté à l'archivage) | Calcul | CONFIRMÉ | **P0** |
| 2 | Poisson tronqué 0–5, docstring mensonger sur "5+" | Calcul | CONFIRMÉ | **P0** |
| 3 | λ anormaux autorisés — démontré sur un pari GO réel (Partick-Celtic) | Calcul | CONFIRMÉ | **P0** |
| 4 | Filtre réserve/jeunes aveugle aux noms d'équipe (cause des λ extrêmes Liechtenstein) | Sélection matchs | CONFIRMÉ | P2 (déjà atténué par le veto d'échantillon) |
| 5 | Tamis 1 Betpawa ignorait la date retournée | Résolution Betpawa | CONFIRMÉ | **✅ CORRIGÉ (06/09)** |
| 6 | Résolution Betpawa ne revérifie pas le titre/équipes au moment d'extraire les cotes | Résolution Betpawa | CONFIRMÉ | P1 |
| 7 | `cherche_deja_analyses` : clé (domicile, extérieur) sans date/id | Identité de match | CONFIRMÉ | **P0** |
| 8 | `extrait_resultat_de_ce_panier` : même clé insuffisante | Identité de match | CONFIRMÉ | **P0** |
| 9 | `scraper_semaine.py` sans vérification URL/date finale | Scraping/dates | CONFIRMÉ (19 match_id dupliqués sur 2 dates, preuve directe) | **P0** |
| 10 | Le workflow publie malgré des erreurs critiques (`continue-on-error`) | Pipeline | CONFIRMÉ | **P0** |
| 11 | Panier bloqué "en_cours" indéfiniment si exception | Pipeline | CONFIRMÉ (chaîne complète avec #19 démontrée) | **P0** |
| 12 | `CLUSTER_MAX`/`plafonner_cluster` jamais appelé (+ bug de clés caché) | Calcul | CONFIRMÉ | **✅ CORRIGÉ (06/09)** |
| 13 | Calibrage surajusté — 28x d'inflation d'échantillon mesurée sur données réelles | Calcul | CONFIRMÉ | **P0** |
| 14 | `source_cotes` jamais affiché (absence totale, pas juste peu visible) | Affichage | CONFIRMÉ | P1 |
| 15 | Fallback saison précédente peu fiable | Scraping/dates | Déjà connu (TRANSITION.md #13) | — |
| 16 | Extraction équipes fragile (2 premiers liens `/equipe/`) | Scraping | CONFIRMÉ mécanisme, 0 échec observé sur 639 matchs | P2 |
| 17 | Absence de classement → ratio neutre 0.0 sans distinction | Calcul | CONFIRMÉ, impact dilué | P2 |
| 18 | Absence de H2H → ratio neutre 0.0, même ambiguïté | Calcul | CONFIRMÉ, impact dilué | P2 |
| 19 | Cotes manuelles non validées → crash `TypeError` reproduit, fait tomber tout `precalcul.py` | Données | CONFIRMÉ, remonté par démonstration | **P0** |
| 20 | `meilleur_parsing` choisit le plus bavard, pas le plus juste | Résolution Betpawa | CONFIRMÉ, impact contextuel (un seul format réel en prod) | P2 |
| 21 | Parser Bet365 dépend d'un format décimal figé | Scraping | CONFIRMÉ, échec déjà sûr (None, pas de valeur fausse) | P2 |
| 22 | `panier.json` encore lu dans le flux automatique planifié | Architecture | CONFIRMÉ (symptôme exact reproduit : 11 entrées périmées, `data.json` à 0 matchs) | P1 (pas P0 : `data.json` mort tant que Supabase tourne) |
| 23 | `scraper_betpawa.py`/`betpawa_urls.txt` encore exécutés en auto | Architecture | CONFIRMÉ, même cause que #22 | P1 |
| 24 | Résultats Supabase pas liés au `panier_id` courant | Frontend | CONFIRMÉ | P1 |
| 25 | Fonction Netlify sans rate-limit | Sécurité | CONFIRMÉ | P1 |
| 26 | Pas de taille max de panier côté serveur | Sécurité | CONFIRMÉ (schéma DB non vérifiable depuis ce dépôt) | P1 |
| 27 | XSS via `innerHTML` | Sécurité | CONFIRMÉ, impact borné au self-XSS (aucun chemin public trouvé) | P2 |
| 28 | "Pari en or" = proba max, pas meilleur EV | Calcul/UX | CONFIRMÉ, question sémantique/produit, pas un bug de calcul | P2 |
| 29 | Vérification résultats abandonnée après 10 jours (biais de sélection) | Données/Calibrage | CONFIRMÉ mécanisme, ampleur non mesurable actuellement | P2 |
| 30 | Cache négatif 7 jours peut masquer une récupération réussie | Données | CONFIRMÉ | P2 |
| 31 | H2H caché 7 jours sans revalidation | Données | PARTIEL — choix de conception documenté par l'auteur, pas un oubli | P3 |
| 32 | Fuseau horaire imparfait 00h–01h | Scraping/dates | Déjà connu (limite documentée dans scraper.py) | — |
| 33 | `date.today()` résiduel dans `_saison_actuelle_et_precedente` | Scraping/dates | CONFIRMÉ, impact quasi nul (dépend du mois, pas de l'heure) | P3 |
| 34 | Pas de `requirements.txt` | Dette technique | CONFIRMÉ | P2 |
| 35 | Cron minuit UTC vs 07h Cameroun voulu | Architecture | Mis de côté — décision produit, pas un bug | — |
| 36 | Fichiers de transition/diagnostic dans le chemin principal | Dette technique | CONFIRMÉ (sous-groupe réellement mort identifié : `selection.*`, `payload_builder.py`, `matchs_selectionnes.json` — zéro référence trouvée nulle part) | P2 |
| 37 | Documentation contradictoire avec le code réel | Dette technique | CONFIRMÉ (1 exemple précis), NON DÉMONTRABLE (1 exemple) | P3 |
| 38 | `audit_permanent.py` n'est pas une vraie suite de tests | Méthode | CONFIRMÉ dans sa forme, utilité réelle vérifiée en pratique sur cet audit | P2 |
| 39 | ~17-18 Mo de fichiers générés versionnés | Dette technique | CONFIRMÉ, chiffres vérifiés | P3 |
| 40 | Deux moteurs concurrents (ancien panier vs nouveau precalcul) | Architecture | CONFIRMÉ (reproduction exacte du symptôme cité par l'audit) | P1 |
| 41 | Justification H2H traitée comme symétrique sur marchés par équipe | Calcul/Justification | CONFIRMÉ | P1 |

---

## Architecture de correction groupée, par cause racine

Pas de correction point par point — chaque groupe ci-dessous est UN
chantier, pas N correctifs isolés.

### Groupe 1 — Identité canonique de match (P0)
**Points : #7, #8, #40, #22, #23.** Cause unique : absence de `match_id`
comme clé partout où deux matchs peuvent partager les mêmes noms
d'équipe (aller-retour, championnat vs coupe), combinée à la coexistence
de l'ancien moteur (`run_pipeline.py`/`scraper_betpawa.py` lus depuis
`panier.json`) jamais retiré du cron planifié après la migration vers
`precalcul.py`/Supabase. **Une seule correction** : introduire `match_id`
comme clé dans `dispatch_pipeline.py` (#7/#8), retirer les étapes
`run_pipeline.py`/`scraper_betpawa.py` du déclenchement `schedule` dans
`pipeline.yml` (#40/#22/#23), garder `run_pipeline.py` comme module
importable pour le seul chemin `dispatch_pipeline.py`.

### Groupe 2 — Résilience du pipeline face aux erreurs (P0)
**Points : #10, #11, #19.** Cause unique : rien dans la chaîne ne
distingue "échec local d'un match" de "échec qui doit tout arrêter", et
aucun filet ne rattrape un plantage entre le marquage `en_cours` et la
fin du traitement. Chaîne de défaillance démontrée : une cote manuelle
malformée (#19) fait planter `precalcul.py`/`dispatch_pipeline.py`,
`continue-on-error` (#10) laisse quand même publier, un panier reste
bloqué "en_cours" sans erreur visible (#11). **Une seule correction** :
try/except localisé autour du bloc `cote_1`/EV/Kelly (isole l'échec au
match fautif) + machine d'état d'échec explicite dans
`dispatch_pipeline.py` + le commit du workflow planifié doit échouer
(pas juste logguer) si `precalcul_leger.json` est absent/vide après
l'étape `precalcul.py`.

### Groupe 3 — Modèle Poisson & λ non borné (P0)
**Points : #2, #3.** Cause unique, déjà détaillée avec démonstration
chiffrée sur un pari GO réel (Partick-Celtic). **Une seule correction** :
étendre la grille Poisson (0-12 ou 0-15) ET introduire un shrinkage/
plafond sur `gf_home_domicile`/`gf_away_exterieur` proportionnel à la
taille d'échantillon avant utilisation comme base λ.

### Groupe 4 — Calibrage (P0, dépend du Groupe 3 pour les données à venir)
**Points : #1, #13, #29 (accessoire).** #13 doit être corrigé (grouper
par `match_id`, ajouter un score de calibration) AVANT de réparer #1
(remettre `TOUS_MARCHES_EVALUES` dans l'archive) — sinon on ferait
grossir un échantillon dont la méthode est fausse. #29 est accessoire
(biais de sélection sur les matchs jamais retrouvés) mais touche le même
pipeline de données de calibrage — à traiter dans la foulée, pas
séparément.

### Groupe 5 — Résolution Betpawa & cotes (P1)
**Points : #6, #20.** #6 : réutiliser le nom déjà extrait au moment de
la résolution plutôt que de revalider depuis zéro. Action complémentaire
non-code : purger `cache_betpawa.json` des entrées antérieures au
correctif #5 (résolues potentiellement via l'ancien tamis 1 buggé).

### Groupe 6 — Scraping dates/fuseaux (P0)
**Point : #9** (preuve directe : 19 match_id dupliqués sur 2 dates dans
les vraies données). Appliquer à `scraper_semaine.py` le même garde-fou
URL/date que `scraper.py` a déjà pour "demain". #33 (cosmétique, P3) à
corriger dans la foulée par cohérence (`aujourdhui_france()` partout).

### Groupe 7 — Sécurité/panier (P1, indépendant du reste)
**Points : #24, #25, #26, #27.** Aucune dépendance avec les groupes
1-6 — peut être traité en parallèle sans attendre. Persister `panier_id`
côté client (#24), rate-limit + vérif "pas déjà en_cours" dans
`trigger.js` (#25), taille max panier (#26), `textContent` au lieu
d'`innerHTML` (#27).

### Groupe 8 — Qualité de données diverses (P2, non urgent)
**Points : #4, #16, #17, #18, #21, #30, #31, #41.** Pas de calcul faux
produit par ces points (déjà vérifié un par un), mais qualité/robustesse
à améliorer. Peuvent être traités en tâche de fond, aucun ordre imposé
entre eux.

### Groupe 9 — Dette technique pure (P2/P3, aucun lien avec le calcul)
**Points : #34, #36, #37, #38, #39.** `requirements.txt`, suppression
des fichiers morts confirmés (`selection.*`, `payload_builder.py`,
`matchs_selectionnes.json`), documentation à rafraîchir, migration
`audit_permanent.py` vers `pytest` à terme. Aucune urgence, aucun risque
de régression sur le moteur.

### Mis de côté / non-bugs
**#15, #32** : déjà actés dans TRANSITION.md, pas rouverts.
**#35** : décision produit (cron 00h UTC), pas un défaut technique.

---

## Déjà corrigé (hors gel, isolés dès confirmation)

- **#5** — Tamis 1 Betpawa compare maintenant la date retournée à la
  date attendue. Testé sur 7 cas.
- **#12** — `plafonner_cluster()` réellement appelée sur `LISTE_B`, bug
  de clés (`ev`/`mise` vs `ev_brut`/`mise_pct_bankroll`) corrigé en même
  temps. Testé sur 6 cas.
- `audit_permanent.py` passe à 60/60 vérités avec ces deux correctifs.

---

## Prochaine étape

Les 9 groupes ci-dessus sont la base de la phase "architecture cible"
annoncée dans la méthode initiale. Reste à décider : ordre de traitement
des groupes P0 (1 à 4 — probablement 3 puis 4, puis 1, puis 2, vu les
dépendances internes à chacun), et si les groupes P1/P2 indépendants
(5, 6, 7) peuvent être menés en parallèle du travail sur les groupes P0.
