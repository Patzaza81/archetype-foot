# Archetype Foot — Document de transition
Dernière mise à jour : 08/09/2026 (session 27 — voir section 27 : modèle
`archetype_model` (remplaçant définitif de V0) verrouillé en version 3
après deux relectures croisées, 4 nouveaux marchés spécifiés, feu vert
donné pour l'implémentation — **mais aucun code écrit cette session**,
tout reste à faire dans la fenêtre suivante).

Mise à jour précédente : 04/09/2026, soirée (session 20 — voir section 20 :
bug 18.8 enfin résolu (cause racine confirmée en direct sur matchendirect),
**régression majeure découverte dans `calculs.py`** (shrinkage jamais
branché nulle part dans le pipeline, 5 constantes gelées régressées),
re-calibrage empirique complet (`K_SHRINKAGE=0,48`, `SEUIL_EV_MIN=0,02`,
base primaire provisoire), plafond de données de calibrage identifié et
corrigé (`TOUS_MARCHES_EVALUES`), incohérence affichage/calcul corrigée
(le badge de probabilité affichait la valeur brute, pas la corrigée), et
correctif du décalage horaire France/Cameroun jamais géré jusqu'ici).
Objectif de ce document : permettre de reprendre le projet dans une nouvelle
fenêtre de conversation sans perdre l'historique de décisions, ni répéter
les erreurs déjà identifiées et corrigées.

---

## ⚠️ SITUATIONS CRITIQUES — à lire avant toute action

0. **PRIORITÉ ABSOLUE ACTUELLE — `archetype_model` verrouillé, zéro ligne
   de code écrite (27.1 à 27.6).** V0 est définitivement abandonné (décision
   explicite de Patrick, pas seulement suspendue comme le disait la
   situation critique #26 précédente — voir 27.1). Le document de
   référence est désormais `ARCHETYPE_FOOT_modele_corrige_v3.md` (livré en
   pièce jointe chat, **PAS dans le dépôt** — à redemander à Patrick en
   début de session si absent du contexte). Feu vert donné pour
   l'implémentation. Ne pas rouvrir de débat sur l'architecture ou la
   philosophie du modèle (V0 vs multi-λ, coefficients, score composite)
   — c'est tranché, deux relectures croisées faites. Commencer directement
   par `data/`+`validation/` ou `poisson/` selon la préférence de Patrick
   en début de session.
1. **Bug 18.8 -- cause racine trouvée et corrigée cette session (20.1)**,
   mais **pas encore vérifiée sur un run réel post-déploiement**. Ne pas
   rouvrir le diagnostic depuis zéro : relire 20.1 d'abord, puis vérifier
   combien de compétitions restent à 0% traité après le prochain run
   complet. Une cause secondaire (4 compétitions : Suède Allsvenskan/
   Superettan, Bélarus Première Ligue, Lettonie Virsliga) reste non
   résolue et nécessite une vérification manuelle de Patrick dans un
   navigateur -- l'assistant n'a pas pu trancher avec certitude si c'est
   un vrai trou de données matchendirect ou un artefact de son propre
   outil de récupération.
2. **`calculs.py` peut régresser silencieusement sans que personne ne s'en
   aperçoive** -- découvert cette session : 5 des 21 constantes gelées
   (section 2) étaient revenues à d'anciennes valeurs, ET la fonction de
   correction de surconfiance (`ajuste_probabilite()`) n'était appelée
   nulle part dans tout le pipeline, la rendant totalement sans effet
   quelle que soit sa valeur. Personne n'a pu dire avec certitude comment
   ni quand cette régression s'est produite (voir 20.2). **Réflexe à
   prendre en début de toute nouvelle session : comparer les valeurs
   réelles de `calculs.py` à la table de la section 2, et vérifier que
   les fonctions citées dans les commentaires sont bien appelées quelque
   part (`grep`), pas juste présentes dans le fichier.**
3. **`K_SHRINKAGE = 0,48` et `SEUIL_EV_MIN = 0,02` sont une base
   primaire PROVISOIRE (20.3)**, trouvée sur seulement 63 paris concrets
   (probabilité + cote réelle + résultat) -- pas le calibrage théorique
   poolé (0,254, qui rend tout pari impossible avec la fourchette de
   cotes actuelle, voir 20.3). Un nouveau mécanisme (`TOUS_MARCHES_EVALUES`,
   20.4) doit faire grossir l'échantillon de calibrage bien plus vite
   qu'avant -- relire `calibrage_k_shrinkage` dans `roi_dashboard.json`
   dans quelques jours avant de considérer ce réglage comme acquis.
4. **Historique partiellement mal daté avant le correctif fuseau horaire
   du 04/09 matin** -- environ 333 matchs archivés entre le 24 et le
   30/08 ont une date enregistrée fausse et restent sans score vérifié.
   Le correctif empêche que ça se reproduise, mais ne corrige PAS
   rétroactivement l'historique existant. Pas urgent pour Patrick.
5. **18.1 et 18.3 sont RÉSOLUS**, confirmés par des preuves indépendantes
   -- ne pas rouvrir ces diagnostics comme s'ils étaient encore actifs.
   Voir 19.1 et 19.2.
6. **Le badge de probabilité affiché peut être en avance ou en retard sur
   le calcul réel sans que ça saute aux yeux** (20.5) -- corrigé cette
   session, mais retenir la leçon : après tout changement de calcul
   interne, vérifier explicitement que l'AFFICHAGE (`script.js`/`index.js`)
   reflète bien le nouveau calcul, pas seulement la logique de décision.
7. **`pipeline.yml` ne se déclenche que sur cron (minuit UTC) ou
   `workflow_dispatch` manuel -- jamais sur un simple push** (20.7).
   Remplacer des fichiers dans le dépôt ne relance rien tout seul. Le
   panier du site déclenche bien un run réel, mais réutilise tel quel
   tout match déjà présent dans `precalcul.json`/`historique_pronostics.json`
   sans recalcul -- piège si on veut vérifier un correctif tout juste
   déployé via le panier avant que `precalcul.json` ait été régénéré.
8. Règle de travail toujours en vigueur : **ne jamais croire un run
   réussi sur parole** — un statut vert GitHub Actions ne prouve rien sur
   le contenu réel des données produites. Toujours revérifier en
   récupérant les fichiers réels et en les inspectant.

---

## 0. Session du 28-30/08/2026 — calibration empirique + isolation multi-utilisateur

### 0.1 Vérification empirique du système sur données réelles
Croisement manuel de 391 matchs du panier (24-29/08) avec les vraies pages
résultat de matchendirect (copiées-collées dans le chat, `matchendirect.fr`
non accessible depuis l'environnement d'édition — même blocage réseau que
d'habitude). Sur les 47 matchs GO avec score confirmé (68 paris au total) :
- **Taux de réussite réel : 58,8%** contre une **probabilité moyenne
  annoncée par le modèle de 82,4%** — écart de surconfiance de 23,6 points.
- **ROI net : -15,5%** sur les 68 mises à 1 unité, malgré un taux de
  réussite proche de 59% — les cotes (fourchette 1.25-1.69) sont trop
  basses pour rentabiliser ce niveau de réussite réel.
- Fait notable : la probabilité moyenne annoncée est QUASI IDENTIQUE entre
  les paris gagnants et perdants (0.815 des deux côtés sur le premier lot
  de 42) — le chiffre de confiance du modèle ne discriminait pas entre bon
  et mauvais pari sur cet échantillon.
- Hypothèses non confirmées, testées et écartées : le marché "Moins de X
  buts" n'est PAS le principal responsable des pertes (taux de réussite
  comparable aux autres marchés, 50-67% selon le type) ; la taille de
  l'échantillon utilisé (dom/ext) n'a pas montré de lien clair avec le
  taux de réussite sur ce volume. La cause retenue est une surconfiance
  généralisée du moteur de probabilité, pas un facteur isolable.
- **Limite assumée** : 68 paris reste un échantillon modeste. Les valeurs
  ci-dessous seront à revérifier une fois `verification_resultats.py`
  (0.4) aura accumulé 150-200+ paris GO vérifiés.
- **⚠️ TOUJOURS NON REVÉRIFIÉ AU 03/09/2026** — ni la session 16, ni la 17,
  ni la 18 n'ont touché à cette question. C'est la question la plus
  importante du projet restée sans réponse depuis le 30/08. Toute
  l'infrastructure construite depuis (pré-calcul, Betpawa, filtre de
  compétitions) rend le système plus rapide, plus riche en données et
  plus propre, mais ne dit rien sur la rentabilité réelle du moteur.

### 0.2 Correctifs appliqués à `calculs.py` suite à ce constat
- **`K_SHRINKAGE = 0.27`** (nouvelle constante) : resserre toute
  probabilité modèle vers 0.5 avant EV/Kelly (`ajuste_probabilite()`),
  formule `k = (taux_reussite_reel - 0.5) / (proba_moyenne_annoncee - 0.5)`.
  Calculé sur les 68 paris de 0.1. Appliqué dans `calcule_ev()` et
  `kelly_stake()`.
- **`SEUIL_EV_MIN` : 0.05 → 0.12** — l'EV moyen affiché était plus élevé
  sur les paris PERDANTS (0.199) que sur les gagnants (0.170) ; l'ancien
  seuil ne filtrait rien d'utile.
- **`BORNE_MIN_DEFENSE`/`BORNE_MAX_DEFENSE` : 0.70/1.30 → 0.55/1.60** — 41%
  des modificateurs de défense calculés sur les 391 matchs étaient collés
  exactement sur l'ancienne borne (signal de saturation, perte de
  granularité). Élargissement symétrique, pas encore revérifié sur nouvel
  échantillon post-changement.
- **`GA_REFERENCE` (constante unique 1.35) remplacée par
  `GA_REFERENCE_PAR_LIGUE`** (dict par pays) + `get_ga_reference(pays)`.
  19 championnats calculés sur données réelles au 30/08 (voir 0.3) ;
  `Écosse` et `Autriche` encore sur la valeur par défaut (1.35), faute de
  saison complète fournie à ce jour.
- **`ALIAS_PAYS`** (dict de normalisation) : correctif d'un bug réel
  trouvé en production — matchendirect et Betpawa ne nomment pas les pays
  pareil dans le champ `competition` (`"Denmark"` vs `"Danemark"`,
  `"Republic of Korea"` vs `"Corée du Sud"`, `"Bundesliga"` seul sans pays
  pour l'Allemagne côté Betpawa ; `"China"`, `"South Africa"`,
  `"Etats-Unis"` en version courte/anglaise même côté matchendirect). Sans
  cette table, des matchs réels du corpus retombaient silencieusement sur
  la valeur par défaut au lieu de la vraie valeur calculée pour leur pays.
  `run_pipeline.py` transmet le pays extrait de `competition` à
  `calcule_lambda(..., pays=...)`, qui appelle `get_ga_reference()` en
  interne — normalisation centralisée, un seul point à maintenir.

### 0.3 Sources et méthode pour GA_REFERENCE_PAR_LIGUE
Deux sites, méthode commune : toujours la dernière saison **complète**
(jamais une saison en cours trop courte — le Danemark 2026/27 à 28 matchs
donnait 1.30 contre 1.55 sur sa saison complète, écart jugé trop grand).
GA_REFERENCE = (buts marqués totaux) / (matchs-équipe totaux), vérifié à
chaque fois que le total buts marqués = total buts encaissés (aucune
incohérence trouvée sur les 19 championnats traités).

- **Football-Data.co.uk** — CSV gratuit, pas de compte. Deux formats
  d'URL : championnats "principaux"
  (`football-data.co.uk/mmz4281/{saison}/{code}.csv`, colonnes
  `FTHG`/`FTAG`) et "extra leagues"
  (`football-data.co.uk/new/{code}.csv`, colonnes `HG`/`AG`/`Season`).
  Championnats couverts ici : Norvège, Suède, Danemark, Italie, Allemagne,
  France, Turquie, Espagne, Angleterre, Pays-Bas, Portugal, Grèce,
  Belgique, Russie, Suisse, Pologne.
- **FootyStats.org** — pas de CSV gratuit pour les championnats hors
  "principaux" ; utilisé via captures d'écran manuelles du tableau de
  classement (MP/GF/GA), collées dans le chat. Championnats couverts :
  Corée du Sud, Arabie Saoudite, Japon, Estonie, Tunisie, États-Unis
  (MLS), Afrique du Sud, Chine.
- **Restent non couverts** : Écosse (saison 2026/27 fournie trop courte,
  16/198 matchs), Autriche (jamais traitée). Compétitions qui ne pourront
  jamais avoir de valeur par pays : "Europe" (coupes continentales),
  "Monde", "International".
- **Piste d'automatisation évoquée, pas construite** : un script mensuel
  qui refait ce calcul automatiquement depuis les CSV Football-Data.co.uk.

### 0.4 `verification_resultats.py` — ferme la boucle de vérification
Pour chaque jour de `historique_pronostics.json` strictement antérieur à
aujourd'hui, va chercher la page résultat matchendirect correspondante et
écrit le score dans les matchs déjà analysés (GO/NO_GO) qui n'en ont pas
encore — seulement si le statut scrapé est bien `"TER"`. Branché dans
`pipeline.yml`, run planifié uniquement. **Toujours non confirmé sur un
volume suffisant au 03/09.**

### 0.5 Passage à Supabase — isolation multi-utilisateur
Auth anonyme Supabase (un `user_id` par appareil), deux tables avec Row
Level Security : `paniers` et `resultats_pipeline`. **Entièrement fait, en
service réel depuis le 30/08 soir** — test réel réussi (panier envoyé
depuis `archetype-foot.netlify.app`, traité automatiquement, résultat
visible sans intervention manuelle). `dispatch_pipeline.py` est le point
d'entrée réel du canal manuel (lit un panier Supabase par `panier_id`),
`run_pipeline.py` reste inchangé et continue d'être appelé en interne.
**Non fait** : test à deux navigateurs simultanés (isolation réelle entre
deux utilisateurs différents).

### 0.6 Responsive (`style.css`)
`header`/`main` centrés (max-width 1200px) + un palier `@media (min-width:
700px)`. Grille de cartes déjà intrinsèquement responsive. **Voir 18.2
pour la refonte complète du système de couleurs, qui touche aussi ce
fichier.**

### 0.7 Erreurs commises en session, corrigées avant livraison
Confusions `run_pipeline.py`/`dispatch_pipeline.py` et
`pronostics.js`(n'existe pas)/`script.js`, toutes deux corrigées avant
livraison. Discipline "pas de source vérifiable = pas d'intégration"
maintenue sur un tableau de championnats fourni sans source, malgré une
coïncidence de valeurs découverte après coup.

### 0.8 Session du 30/08/2026 (soir) — mise en service réelle de Supabase
**Résultat final : ÇA MARCHE**, mais plusieurs problèmes réels rencontrés
en route, chacun avec sa cause exacte documentée :
- 0.8.1 `panier_id` obligatoire empêchait toute relance manuelle → `required: false`.
- 0.8.2 Un changement de cron ne s'applique qu'au prochain passage de
  l'heure programmée après merge sur `main`, jamais rétroactivement.
  GitHub Actions ne garantit pas la ponctualité à la minute sur les
  dépôts peu actifs (retard de 6h observé une fois).
- 0.8.3 Supabase a changé de système de clés API sans prévenir (nouvel
  onglet "Publishable/secret" par défaut) — décision de rester sur les
  clés "Legacy anon/service_role" pour ne pas tout réécrire.
- 0.8.4 Menus Supabase/GitHub/Netlify réorganisés depuis la dernière
  fois — signaler explicitement que les interfaces évoluent plutôt que
  d'insister sur un chemin qui s'avère faux.
- **0.8.5 LE bug le plus coûteux** : `const supabase = ...` dans
  `panier.js`/`script.js` entrait en conflit avec la variable globale déjà
  créée par le script `@supabase/supabase-js` — `SyntaxError` qui fait
  planter TOUT le fichier silencieusement (pas de console accessible sur
  Safari mobile sans Mac). Corrigé : renommé en `supabaseClient` partout.
  **Leçon générale réutilisable** : quand un symptôme résiste à plusieurs
  corrections plausibles d'affilée sans jamais changer, la vraie erreur
  est probablement plus basique qu'on ne le suppose — lire le fichier
  ligne par ligne avant de fabriquer un outil de diagnostic.
- 0.8.6 Deux sites Netlify différents testés sans s'en rendre compte
  (`type-foot.netlify.app` ancien/déconnecté vs `archetype-foot.netlify.app`
  le vrai) — vérifier le nom de domaine dans la barre d'adresse en premier
  quand un correctif semble n'avoir aucun effet.
- 0.8.7 Un bloc `window.addEventListener("error", ...)` temporaire ajouté
  à `panier.html` a permis de trouver 0.8.5 en une capture d'écran — à
  réintroduire directement si un plantage silencieux similaire réapparaît,
  plutôt que d'explorer plusieurs pistes à l'aveugle d'abord.

---

## ✅ BUG RÉSOLU (26/08/2026) — cote invraisemblable sur ligne over/under haute

Cause racine confirmée : `soup.find(string=...)` dans
`recupere_cotes_marches` (`scraper_details.py`) ancrait sur la PREMIÈRE
occurrence d'un titre de marché, qui peut apparaître deux fois sur la page
matchendirect (widget d'aperçu sans Bet365, puis tableau complet avec
Bet365). Correctif : `soup.find_all` + sélection de la DERNIÈRE
occurrence. Commité le 26/08.

---

## 1. Philosophie du projet — non négociable

- **Les sources de données sont des outils à extraire, pas des cahiers des
  charges rigides.**
- **Aucune affirmation sans vérification en conditions réelles.** La
  session 18 (filtre de compétitions, voir plus bas) applique cette
  discipline à une échelle inédite : chaque pays "à risque" a été vérifié
  soit contre les vraies données du dernier run, soit contre une source
  externe (Wikipedia), soit contre une capture d'écran matchendirect
  fournie par Patrick — mais **le résultat final n'a toujours pas tourné
  en production**, seulement contre un instantané figé. Ne pas confondre
  "vérifié contre des données réelles" et "vérifié en production".
- **Dire clairement ce qui est confirmé, ce qui est probable, et ce qui est
  un pur best-effort non testé.**
- **Priorité au gratuit et au simple.**
- **Le scope se réduit consciemment plutôt que de s'étendre indéfiniment.**
- **Ne jamais confirmer qu'un fichier a été correctement modifié sans
  vérifier soi-même le contenu réel transmis** (leçon de la session 17,
  reconfirmée en 18 : la Nouvelle-Zélande a été supposée "gardée" avant
  qu'une capture d'écran réelle ne prouve qu'elle n'a pas sa propre 1ère
  division, elle joue dans l'A-Ligue australienne).

---

## 2. Constantes gelées ("moteurs initiaux") — ne pas modifier sans repasser par un backtest

**MISE À JOUR 04/09/2026 (soirée)** : `K_SHRINKAGE` et `SEUIL_EV_MIN`
ci-dessous ne sont plus des constantes figées une fois pour toutes -- ce
sont désormais des valeurs PROVISOIRES, recalculées par
`calcule_roi.py::calcule_calibrage()` chaque nuit sur l'échantillon qui
grossit (voir 20.3/20.4). Elles ont aussi été trouvées régressées à
d'anciennes valeurs plus tôt cette session (20.2) -- **toujours comparer
les valeurs réelles de `calculs.py` à cette table en début de session**,
et vérifier que `ajuste_probabilite()` est bien appelée quelque part
(`grep ajuste_probabilite *.py`), pas juste présente dans le fichier.

```
GA_REFERENCE_PAR_LIGUE (dict par pays, voir 0.2/0.3) -- RÉGRESSÉ au
    04/09/2026 (constante unique 1.35, pays ignoré), PAS ENCORE RESTAURÉ
    (reporté faute d'avoir les valeurs numériques exactes sous la main,
    voir 20.10 point 5)
BORNE_MIN_DEFENSE = 0.55
BORNE_MAX_DEFENSE = 1.60

POIDS_FORME = 0.30
POIDS_CLASSEMENT = 0.20
POIDS_REPOS = 0.15
POIDS_ABSENCES = 0.15
POIDS_DISTANCE = 0.10
POIDS_H2H = 0.10
BORNE_RATIO = 0.15

RHO_DIXON_COLES = -0.1

SEUIL_EV_MIN = 0.02  -- PROVISOIRE, voir note ci-dessus (était 0.12,
    calculé le 30/08 puis régressé puis re-calibré empiriquement le 04/09)
FOURCHETTE_COTE_MIN = 1.25
FOURCHETTE_COTE_MAX = 1.69
SEUIL_CORRELATION = 0.70
KELLY_FRACTION = 0.25
MISE_MAX_PARI = 0.04
CLUSTER_MAX = 0.10
NB_PARIS_MAX = 3
SEUIL_STANDOUT = 0.15

K_SHRINKAGE = 0.48  -- PROVISOIRE, voir note ci-dessus (était 0.27,
    calculé le 30/08 sur 68 paris ; re-calibré à 0.48 le 04/09 sur 63
    paris après découverte que 0.27 -- et même le calibrage poolé à
    0.254 sur 107 paris -- rend tout pari mathématiquement impossible
    avec FOURCHETTE_COTE_MAX=1.69, voir 20.3)
```

Marchés calculables : 1X2, Double Chance, BTTS, Over/Under (toutes
lignes), Handicap à 2 choix (lignes demi-entières), Score exact, Nombre
exact de buts, Pair/Impair, Cages inviolées.

**Rien de tout ça n'a été touché par la session 18** — le filtre de
compétitions agit uniquement en amont, sur QUELS matchs entrent dans le
calcul, jamais sur COMMENT le calcul lui-même fonctionne.

---

## 3. Architecture actuelle (mise à jour session 18)

```
GitHub Actions (cron quotidien 0h UTC = 1h Douala + déclenchement manuel)
  → scraper.py           (matchs aujourd'hui/demain — matchendirect, HTTP
                           simple ; plafond de 200/jour RETIRÉ le 31/08)
  → scraper_semaine.py   (matchs J+2 à J+7 — matchendirect, via Playwright,
                           tourne déjà chaque nuit en production, pas de
                           plafond)
  → scraper_betpawa.py   (cotes + marchés Betpawa POUR LES URLS DE
                           betpawa_urls.txt SEULEMENT — pas un scan
                           automatique)
  → scraper_details.py   (classement, H2H, forme -- matchendirect, HTTP simple)
  → calculs.py           (Poisson/Dixon-Coles/EV/Kelly, calibré par ligue -- 0.2)
  → precalcul.py         (pré-calcul J+1/J+2/J+3 indépendant du panier,
                           réutilise construit_signaux() sans y toucher ;
                           utilise cache_equipes.py ; DEPUIS LE 03/09,
                           applique aussi le filtre de compétitions complet
                           -- voir section 18 -- AVANT la résolution
                           Betpawa et AVANT construit_signaux())
  → cache_equipes.py     (cache persistant des stats GF/GA par
                           équipe+compétition)
  -- run planifié (schedule) --
  → run_pipeline.py      (orchestrateur, écrit data.json)
  → verification_resultats.py  (scores des jours passés -- 0.4)
  → commit + push automatique vers le dépôt
  -- run manuel (workflow_dispatch, panier_id) --
  → dispatch_pipeline.py (lit le panier Supabase par panier_id -- PAS
                           affecté par le filtre de compétitions, voir
                           18.6 : le panier manuel garde volontairement
                           accès à TOUT, y compris ce que le filtre exclut
                           par défaut)

  → resolution_betpawa.py (module de PRODUCTION, moteur à 3 tamis validé
                           sur 100 matchs réels -- règle stricte : ne plus
                           modifier sans repasser par un test complet)
  → cache_betpawa.py      (cache persistant des correspondances CERTAINES
                           uniquement)
  → resolution_betpawa_precalcul.py (pont entre les deux modules
                           ci-dessus et precalcul.py, branché depuis la
                           session 17)

Netlify sert le dépôt en statique (index.html/panier.html/pronostics.html/
betpawa.html), Supabase pour l'isolation multi-utilisateur (0.5).

NOUVEAU 03/09 -- fichiers générés par precalcul.py pour l'AFFICHAGE
seulement (accueil, sélection manuelle du panier) :
  matchs_du_jour_filtre.json  (copie filtrée de matchs_du_jour.json)
  matchs_demain_filtre.json   (copie filtrée de matchs_demain.json)
  -- les fichiers BRUTS (matchs_du_jour.json, matchs_demain.json) restent
  intacts et committés tels quels : run_pipeline.py (normalise_panier) en
  a besoin pour résoudre un match_id ajouté manuellement au panier, même
  hors filtre. index.js lit désormais les versions _filtre.
```

**Dépôt GitHub** : `Patzaza81/archetype-foot`, branche `main`.

---

## 4-14. [Sections historiques, inchangées depuis le 30/08 — voir versions
précédentes de ce document pour le détail complet : pages matchendirect
découvertes (section 4), décisions d'abandon (section 5), fragilités
connues (section 6, mise à jour en 16.8/17/18.9), architecture Betpawa
copier-coller/URL manuelle (section 15), etc. Pas reproduites intégralement
ici pour ne pas alourdir -- se référer à l'historique du dépôt/de la
conversation si le détail est nécessaire.]

---

## 16. Session du 31/08-01/09/2026 — pré-calcul J+1/J+2/J+3 et résolution d'identité Betpawa

**La session la plus longue et la plus riche en détours du projet, jusqu'à
la session 18.** Contient la découverte la plus importante du projet sur
la récupération de cotes réelles, mais uniquement après plusieurs pistes
mortes explorées à fond avant d'y arriver. Documentée en détail
volontairement, y compris les échecs, pour ne jamais avoir à refaire ce
chemin.

### 16.1 Audit initial et corrections mineures mais réelles
- Confirmé par lecture directe du dépôt (pas supposé) : `calculs.py` et
  `run_pipeline.py` fonctionnels et non touchés depuis leur dernière
  correction, `scraper_semaine.py` tourne déjà chaque nuit en production
  avec de vraies données (2546 matchs sur J+2-J+7 lors du premier contrôle),
  cron à `0 0 * * *` (1h Douala, changé le 30/08 -- pas 23h comme un
  document antérieur non vérifié le prétendait).
- **Vrai bug trouvé et corrigé** : `scraper.py` (matchs aujourd'hui/demain)
  était lancé avec `--max-matchs 200` dans `pipeline.yml` -- un plafond
  RÉEL qui tronquait la liste (confirmé : `matchs_du_jour.json` et
  `matchs_demain.json` contenaient exactement 200 entrées chacun, pas une
  coïncidence). Retiré (`--max-matchs 100000`, même valeur que
  `scraper_semaine.py` qui n'a jamais eu ce problème).

### 16.2 `precalcul.py` -- pré-calcul J+1/J+2/J+3 indépendant du panier
Nouveau script : construit la fenêtre J+1 (`matchs_demain.json`) + J+2/J+3
(filtré depuis `matchs_semaine.json`), dédoublonne par `match_id`, appelle
`construit_signaux()` de `run_pipeline.py` SANS LE MODIFIER, ajoute
`model_version`/`status`/`prepared_at`. Ne remplace rien de l'existant --
tourne en plus du pipeline panier habituel.

**Premier run réel (31/08)** : 639 matchs dans la fenêtre, 325 READY / 314
PARTIAL. Cause des PARTIAL analysée : 276 dues à
`aucun_match_joue_saison_actuelle_ou_precedente` sur des compétitions
confidentielles (coupes préliminaires, championnats amateurs peu couverts
par matchendirect) -- pas un bug, une limite réelle de couverture propre
à l'élargissement du scan à absolument tout.

**Découverte structurante** : sur les 325 matchs READY de ce premier run,
**100% utilisaient Bet365 comme source de cote, 0% Betpawa** --
`precalcul.py` ne passait par aucun circuit Betpawa (ni manuel, ni
`scraper_betpawa.py`). Confirme que l'intégration Betpawa dans le
pré-calcul automatique n'existait pas du tout avant cette session, malgré
la décision du 26/08 (9.7/15.7) de faire de Betpawa la source de cote
prioritaire -- cette décision ne s'appliquait de fait qu'au circuit panier
manuel (`betpawa_urls.txt`, 17 URLs collées à la main), jamais à un scan
automatique des 600+ matchs de la fenêtre.

**Correctif de vitesse -- `cache_equipes.py` (nouveau)** : cache persistant
par (équipe, compétition) des stats GF/GA, avec deux durées de validité
(24h si l'équipe a un historique normal, 7 jours si elle n'en a aucun --
un petit club en coupe préliminaire n'aura pas soudainement un historique
le lendemain). Branché dans `precalcul.py` par remplacement de la fonction
au niveau du module (`run_pipeline.recupere_gf_ga_avec_repli = ...`), sans
toucher à `run_pipeline.py` lui-même. Premier run (cache vide) : 1h08m57s.
Deuxième run (cache partiellement rempli) : 58m26s -- amélioration réelle
mais plus modeste qu'espéré sur ce seul cycle ; l'effet complet du cache ne
se mesurera que sur plusieurs nuits consécutives.

**IMPORTANT, découvert seulement en session 18 (18.7)** : ce cache ne
couvre que les stats GF/GA par équipe. Trois autres appels réseau par
match (classement, H2H, cotes) n'ont AUCUN cache -- notamment le
classement, refait identique pour chaque match d'une même compétition/
journée. Piste de cache classement/H2H proposée en 18.8, jamais
implémentée à ce jour.

### 16.3 La quête de la découverte automatique des matchs Betpawa -- pistes mortes documentées

**Objectif de départ** : pour chaque match matchendirect de la fenêtre
J+1/J+2/J+3, trouver automatiquement son équivalent Betpawa (URL +
cotes + marchés), sans dépendre d'une URL collée à la main.

**Piste 1 -- page de liste générale (`betpawa.cm/events`) -- ABANDONNÉE.**
Cette page plafonne à 20 matchs affichés (confirmé triés par heure,
mélangeant tous les jours), quel que soit le filtre appliqué en amont.
**Cinq méthodes de défilement testées, toutes en échec confirmé** :
molette de souris (position centrée), touche clavier "Fin", manipulation
directe de `scrollTop` en JavaScript, scroll incrémental par petits pas
sur le vrai conteneur scrollable identifié (`ScrollableWrapper_container`,
scrollHeight 4937 vs clientHeight 632), et un vrai geste tactile simulé au
niveau du navigateur (`Input.dispatchTouchEvent`, appareil émulé iPhone
13). Aucune n'a chargé un seul match de plus que les 20 initiaux. Un
paramètre de pagination par URL a aussi été testé et écarté
(`&page=2` ignoré silencieusement par le site -- confirmé par requête
directe). **Conclusion retenue : pas de scroll infini fonctionnel connu
sur cette page à ce jour ; ne pas retenter sans une piste nouvelle et
concrète.**

**Piste 2 -- filtres Championnats/Marchés/Calendrier (panneaux latéraux)
-- fonctionnelle mais ABANDONNÉE au profit de la piste 3.** Trois panneaux
séparés existent (confirmés par capture d'écran manuelle de Patrick,
après plusieurs échecs d'automatisation à l'aveugle) : "Leagues"
(championnats, ~100+ cases à cocher), "Markets" (types de marché), et une
icône calendrier sans texte (jour de la semaine : Aujourd'hui/Demain/jours
suivants avec compteur par jour). Chaque panneau a son propre bouton
"Apply"/"Appliquer" -- **plusieurs bugs trouvés et corrigés en cascade** :
(a) `.first` sur un sélecteur de texte générique tombait sur un bouton
"Apply" invisible d'un AUTRE panneau fermé -- corrigé en filtrant sur
`is_visible()` ; (b) l'icône calendrier, sans texte, a d'abord été
confondue avec le panneau "Markets" -- corrigée après capture d'écran de
Patrick montrant l'icône séparée ; (c) recliquer sur l'icône loupe/calendrier
sans recharger la page entre deux tentatives la REFERME au lieu de la
rouvrir (bouton bascule) -- corrigé en rechargeant la page avant chaque
tentative. Une fois ces bugs réglés, le filtre par jour fonctionnait
(confirmé : filtrer "Demain" a renvoyé 20 matchs tous datés du bon jour).
**Abandonnée quand même** : reste plafonnée à 20 par requête (même
problème de fond que la piste 1), donc il aurait fallu croiser
championnat + jour pour rester sous la limite -- complexité jugée trop
lourde face à la piste 3, découverte entre-temps.

**Piste 3 -- RECHERCHE PAR NOM D'ÉQUIPE (icône loupe) -- RETENUE, idée de
Patrick.** Percée majeure : chercher un nom d'équipe fait apparaître une
liste de suggestions de matchs (les deux équipes), sans plafond de 20,
sans dépendre du jour ou du championnat. Cliquer sur une suggestion mène
directement à la page du match avec TOUS ses marchés (confirmé sur Real
Betis-Real Madrid : plus de 40 catégories de marché, y compris des cotes
par joueur -- buteur, tirs, cartons, arrêts).

**Bugs trouvés et corrigés en cascade sur cette piste également** :
- Le champ de recherche a été confondu une fois avec le champ "Booking
  Code" (`id="bookingCode"`), une autre fois avec une case à cocher
  invisible parmi les ~267 du panneau Leagues -- corrigé en ciblant
  précisément `input[type='text'], input[type='search']`, en excluant
  explicitement `bookingCode`, et en vérifiant la visibilité.
- Le menu de suggestions a un attribut précis,
  `data-test-id="search-suggestions"` -- le cibler directement (au lieu
  d'un `div`/`span` générique) a réglé des conflits de clic répétés.
- `.fill()` (Playwright) ne déclenchait pas la recherche de l'application
  -- remplacé par de vraies frappes clavier (`page.keyboard.type`, avec
  délai entre les touches).

### 16.4 Le problème de l'orthographe -- de la liste figée à la ressemblance calculée
Sur un premier échantillon de 5 matchs volontairement difficiles, la
comparaison stricte texte-à-texte échouait sur des variantes mineures
(Saint/St, United/Utd, Moskva/Moscow, Olympiakos/Olympiacos, accents
polonais/scandinaves mal translittérés). **Décision explicite de Patrick,
sur cette base** : ne pas construire une liste d'abréviations qui ne
finira jamais de couvrir tous les cas, mais un vrai calcul de ressemblance
(`difflib.SequenceMatcher`, bibliothèque standard Python) avec un seuil.
Passage d'un dictionnaire d'abréviations (taux 27% sur 30 matchs) à un
calcul de ressemblance (taux 47% sur les mêmes 30 matchs).

**Sigles non reconnus par Betpawa -- confirmé** : chercher "PSG" ne
retourne rien de pertinent, chercher "Paris Saint-Germain" fonctionne
immédiatement (ressemblance 1.00). Table `SIGLES_CONNUS` créée (PSG, OM,
OL) -- volontairement minimale, pas une liste mondiale.

**FAUX POSITIF PROUVÉ, le vrai risque de cette approche** : sur
l'échantillon de 100 matchs, "Tanta - Masar" (Égypte) a été confondu avec
"Macará - Manta" (Équateur, match totalement différent) -- même URL
Betpawa renvoyée pour les deux, à cause d'une ressemblance fortuite des
lettres sur le seul nom extérieur comparé ("Masar"/"Manta", ratio 0.60,
au-dessus du seuil de l'époque). **Correctif** : exiger que domicile ET
extérieur dépassent chacun le seuil, en retenant le plus faible des deux
scores -- le nom domicile ("Tanta" vs "Macará", 0.36) aurait à lui seul
disqualifié cette association. Confirmé après correctif : plus aucun
doublon d'URL sur le même échantillon de 100.

### 16.5 Procédure à trois tamis -- architecture finale validée
Sur demande explicite de Patrick ("trouve une méthode plus structurée...
si ambigu, on intègre les deux matchs dans la liste, on ne tranche pas
soi-même"), la logique de décision a été reconstruite en 3 étapes :

- **Tamis 1** -- domicile ET extérieur avec ressemblance ≥ 0.80 chacun, un
  seul candidat dans ce cas : accepté automatiquement.
- **Tamis 2** -- si ambigu (plusieurs candidats, ou aucun en tamis 1) : on
  ouvre chaque candidat restant, on lit sa VRAIE date affichée sur la page
  Betpawa, on la compare à la date déjà connue via matchendirect. Un seul
  candidat à la bonne date -> confirmé par la date, pas par le nom.
- **Tamis 3** -- si toujours ambigu après la date (plusieurs à la même
  date, ou aucune correspondance de date) : marqué "AMBIGU", jamais de
  choix au hasard. Reste disponible pour un arbitrage ultérieur (pas
  construit à ce jour).

**Validation empirique finale, échantillon de 100 matchs réels** (tirage
honnête : 20 de grands championnats + 80 au hasard dans le reste de
`precalcul.json`, sans biais favorable) :
**37 trouvés (confiance haute) / 3 ambigus (jamais devinés) / 60 non
trouvés / ZÉRO doublon d'URL détecté (zéro faux positif confirmé).**

Analyse des 60 non trouvés (échantillonnage manuel, pas exhaustif) :
grande majorité de championnats absents de la couverture Betpawa
(Ouzbékistan, Arménie 2e division, Nouvelle-Calédonie, USL League One,
Liban, Thaïlande D2...). Un cas notable identifié : "PSG - AS Monaco"
(match du 4 septembre, donc J+3) non trouvé malgré la conversion de sigle
correcte -- hypothèse retenue : un match trop loin dans le futur peut ne
pas encore être indexé par la recherche Betpawa au moment du test. **Non
confirmé formellement, à revérifier** si le cas se reproduit.

**⚠️ Question méthodologique ouverte, soulevée par une relecture externe
(ChatGPT, sollicité par Patrick sur le même énoncé de problème)** : le
taux de 37% ne distingue pas "vraie absence du match sur Betpawa" de
"match présent mais raté par l'algorithme" -- aucun audit manuel
systématique des 60 non-trouvés n'a été fait à ce jour pour trancher.

### 16.6 Industrialisation -- `resolution_betpawa.py` + `cache_betpawa.py`
- **`resolution_betpawa.py`** : le moteur à 3 tamis, promu module de
  production stable. **Règle documentée en tête de fichier : ne plus
  modifier la logique des tamis sans repasser par un test complet sur
  échantillon** -- même discipline que `calculs.py`.
- **`cache_betpawa.py`** : mémoire persistante des correspondances
  CERTAINES uniquement -- jamais un AMBIGU, jamais un NON TROUVÉ.
- **Test de validation double-run réalisé et CONFIRMÉ (01/09/2026)** :
  40 trouvés / 2 ambigus identiques sur les deux runs (aucune dérive),
  40/40 correspondances venues du cache au 2e passage, gain de temps réel
  de 47% (13m10s -> 6m57s).

### 16.7 Ce qui restait à faire fin session 16 (repris et complété en 17/18)
1. Brancher `resolution_betpawa.py` + `cache_betpawa.py` dans
   `precalcul.py` -- **FAIT en session 17, voir 17.1**.
2. Mesurer la vraie couverture Betpawa en auditant les "NON TROUVÉ" --
   **toujours pas fait**.
3. Envisager la parallélisation des recherches Playwright -- **toujours
   pas fait, ni même retenté**.
4. Revenir sur la question du ROI réel du moteur -- **toujours pas fait,
   voir 0.1**.
5. Purge périodique de `cache_betpawa.json` -- **toujours pas fait**.
6. Phase 5/6 de la feuille de route (frontend lecture seule, mode admin)
   -- **toujours pas touchée**.

### 16.8 Fragilités connues (mise à jour de la section 6)
- `resolution_betpawa.py` : validé sur 100 matchs, zéro faux positif
  détecté, mais reste une heuristique -- pas une garantie absolue.
- `cache_betpawa.py`/`cache_equipes.py` : validés sur un cycle
  avant/après ou un double-run, jamais sur plusieurs nuits réelles
  consécutives en production.
- `SIGLES_CONNUS` reste une petite table manuelle -- tout sigle non
  listé échoue silencieusement.
- Couverture temporelle incertaine sur J+3 (cas PSG-Monaco, 16.5).

---

## 17. Session du 02/09/2026 -- Branchement Betpawa dans precalcul.py, archivage, frontend

### 17.1 Branchement resolution_betpawa.py + cache_betpawa.py dans precalcul.py -- FAIT ET VALIDÉ
Nouveau fichier `resolution_betpawa_precalcul.py` : pont entre les deux
modules déjà validés (16.6) et `precalcul.py`, sans modifier une seule
ligne de leur logique interne. Pour chaque match de la fenêtre J+1/J+2/J+3 :
vérifie le cache, sinon lance `resoudre_match()`, puis si trouvé récupère
les cotes réelles via `scraper_betpawa.recupere_page()` +
`meilleur_parsing()`. Si cotes trouvées : `cotes_manuelles` est injecté
dans le match, ce qui fait basculer `run_pipeline.construit_signaux()`
sur ces cotes au lieu de Bet365/matchendirect (mécanisme déjà existant,
inchangé). Jamais d'exception qui remonte -- tout est absorbé dans des
compteurs, écrit dans `diagnostic_precalcul_betpawa.txt` à chaque run.
Paramètre `PRECALCUL_LIMITE_BETPAWA` (variable d'env) pour plafonner le
nombre de matchs traités par Betpawa sur un run -- voir 17.3.

**Validé en conditions réelles à petite échelle (15 matchs, 01/09)** :
13/15 trouvés, cotes extraites, `verdict_global` calculé correctement.

**Validé à pleine échelle (1574 matchs, run automatique 02/09)** :
498 trouvés, 49 ambigus, 1027 non trouvés, 0 erreur. Durée de l'étape
Betpawa seule : 12428 secondes (~3h27m). Durée totale du job : 5h18m51s,
à 40 minutes du mur des 6h de GitHub Actions.

**IMPORTANT, découvert en session 18 (18.7)** : cette durée de 5h18m
n'était en réalité PAS causée par la résolution Betpawa elle-même (qui ne
prend que quelques minutes une fois plafonnée), mais par
`construit_signaux()` qui retraite l'intégralité de la fenêtre (jusqu'à
2400+ matchs) indépendamment de toute limite Betpawa -- voir 18.7 pour le
détail complet de cette découverte tardive, qui remet en cause
l'interprétation de cet incident telle qu'écrite ci-dessus à l'époque.

### 17.2 Archivage automatique dans historique_pronostics.json -- CONFIRMÉ EN SESSION 18
`archive_precalcul()` dans `precalcul.py`, appelée après
`construit_signaux()`. Version allégée (`_slim_pour_archive`, pas les
distributions de probabilité complètes). Seuls les matchs dont la date est
EXACTEMENT J+1 sont archivés -- jamais J+2/J+3, pour ne jamais archiver le
même match plusieurs fois à mesure qu'il descend dans la fenêtre.

**CONFIRMÉ EN SESSION 18** : le run du 03/09 (post-correctif) a bien
produit une entrée `"source": "precalcul_auto"`, date `2026-09-04`
(J+1 par rapport au run), 247 matchs, structure cohérente, une seule
date. **Ce point précis est donc résolu**, contrairement à
`precalcul_leger.json` (voir 18.1).

### 17.3 Incident -- limite de sécurité Betpawa appliquée deux fois trop tard, puis diagnostic revu en session 18
Le run automatique du 02/09 a tourné SANS AUCUNE limite sur la résolution
Betpawa (`PRECALCUL_LIMITE_BETPAWA` vide sur un événement `schedule`,
qui ne fournit jamais `github.event.inputs.*`) -- 5h18m51s de durée.
Correctif (`|| '100'`) confirmé appliqué par lecture directe du fichier
après deux tentatives ratées.

**Nuance capitale ajoutée en session 18 (18.7)** : ce correctif limite
bien le NOMBRE de matchs qui obtiennent une résolution Betpawa, mais PAS
le nombre de matchs traités par `construit_signaux()` -- qui tourne
TOUJOURS sur l'intégralité de la fenêtre, quelle que soit la valeur de
`PRECALCUL_LIMITE_BETPAWA`. Autrement dit : **passer la limite de 100 à 5
ne change quasiment rien à la durée totale du run** -- constaté
empiriquement par Patrick (run à 5 matchs sélectionnés dans le panier,
toujours ~1h+ sur l'étape de pré-calcul), qui a mené à toute
l'investigation de performance de la session 18 (voir 18.7/18.8). La
vraie explication de l'incident du 02/09 est donc la TAILLE DE LA FENÊTRE
elle-même (2408 matchs ce jour-là), pas le volume Betpawa. Le filtre de
compétitions de la session 18 s'attaque directement à cette taille de
fenêtre (37% conservé sur le dernier test, voir 18.3) -- c'est le vrai
successeur de ce correctif, pas `PRECALCUL_LIMITE_BETPAWA`.

### 17.4 Frontend -- `/pronostics.html` connecté au pré-calcul automatique
4 onglets (J+1/J+2/J+3/Panier), tri GO-EV décroissant en premier, case
"afficher seulement les GO", correctif race condition (jeton d'affichage
incrémenté à chaque changement d'onglet). **Complété en session 18** avec
un mode d'affichage supplémentaire "Par catégorie" (regroupement par
championnat) -- voir 18.2.

### 17.5 precalcul_leger.json -- TOUJOURS NON RÉSOLU, voir 18.1
`precalcul.py` écrit `precalcul_leger.json` (mêmes signaux, sans les
champs `marches`/`lambda`) pour que le site n'ait plus à charger le
fichier complet (9,2 Mo au 02/09) sur une connexion 3G.
**⚠️ Ce point n'est PAS résolu au 03/09, malgré une session entière de
diagnostic -- voir le détail complet en 18.1, section à lire en premier
à la reprise.**

### 17.6 Ce qui restait à faire fin session 17 (repris en 18)
1. Vérifier le prochain run de bout en bout -- **fait partiellement en
   18.1** : `historique_pronostics.json` confirmé bon (17.2), mais
   `precalcul_leger.json` **toujours pas résolu**.
2. Revenir sur le ROI réel du moteur -- **toujours pas fait**.
3. Décider d'un vrai régime de `limite_betpawa` -- **reconsidéré en
   18.7** : cette variable n'est plus le bon levier, voir 17.3 ci-dessus.
4. Couverture Betpawa réelle, purge du cache, Phase 5/6 -- **toujours pas
   traités**.

---

## 18. Session du 03/09/2026 — Filtre de compétitions complet + refonte visuelle + diagnostic inachevé sur precalcul_leger.json

**Session la plus large en portée à ce jour : touche la quasi-totalité des
championnats du monde.** Contient une découverte importante sur la vraie
cause de la lenteur du pré-calcul (18.7), un filtre de compétitions
construit et audité dans les deux sens, une refonte visuelle complète, et
**un diagnostic resté ouvert** sur `precalcul_leger.json` -- à ne pas
perdre de vue, ce n'est pas résolu malgré tout le temps qui y a été
consacré.

### 18.1 ⚠️ NON RÉSOLU -- precalcul_leger.json toujours absent du dépôt au moment où cette section est écrite
**À lire en premier à la reprise. C'est la priorité opérationnelle
immédiate, avant même de relancer le pipeline avec le nouveau filtre.**

Chronologie du diagnostic, aucune conclusion définitive atteinte :
1. Log du run confirmé : `precalcul.py` écrit bien `precalcul_leger.json`
   avec succès (le print "precalcul_leger.json écrit en parallèle"
   n'apparaît qu'après l'écriture réussie du fichier, exclu tout crash
   Python entre les deux écritures).
2. Le mécanisme de commit fonctionne : `historique_pronostics.json`,
   ajouté par la même boucle shell (`for f in ... ; do [ -f "$f" ] &&
   git add "$f"; done`), se met à jour correctement à chaque run.
3. Pourtant, `precalcul_leger.json` n'apparaît PAS dans la liste des
   fichiers du commit produit par ce run (vérifié directement sur
   GitHub, commit `91cccbf`, liste des fichiers modifiés).
4. Recherche de code menée, RIEN trouvé : aucun `os.remove`/`shutil`,
   aucun `git clean`/`checkout`/`reset` caché dans `precalcul.py`,
   `run_pipeline.py`, `verification_resultats.py` ou `pipeline.yml`.
   Aucun `.gitignore` ni `.gitattributes` qui l'exclurait. Le nom du
   fichier est identique octet pour octet des deux côtés (vérifié).
5. **Correctif tenté (non encore vérifié en conditions réelles)** :
   instrumentation de diagnostic ajoutée dans l'étape "Commit et push"
   de `pipeline.yml` -- deux `ls -la` et deux `git status --porcelain`
   avant et après le `git add`, pour trancher si le fichier existe
   VRAIMENT sur le disque du runner à cet instant précis. **Cette
   instrumentation n'a jamais été vérifiée sur un run réel** -- la
   session a bifurqué vers le filtre de compétitions juste après (sur
   décision explicite de Patrick, "pas la priorité").
6. Pendant ce temps, Patrick a testé le site en conditions réelles et a
   confirmé : la page `pronostics.html` affiche bien l'erreur
   `"erreur de chargement : precalcul_leger.json introuvable (status
   404)"`, cohérent avec tout ce qui précède.

**Prochaine étape immédiate, sans ambiguïté** : relancer un run, ouvrir
le log de l'étape "Commit et push du résultat", lire la sortie des
`ls -la`/`git status` déjà en place. Si le fichier n'existe pas à cet
instant précis malgré le print de `precalcul.py` confirmant qu'il a été
écrit, il faudra chercher du côté d'une éventuelle réinitialisation du
répertoire de travail entre les étapes du job (aucune piste concrète
identifiée à ce jour, seulement des pistes déjà écartées).

### 18.2 Refonte visuelle (style.css + pronostics.html)
Palette de couleurs entièrement revue après plusieurs itérations avec
Patrick (violet essayé puis abandonné, gold essayé puis abandonné pour ne
pas diluer son rôle de repère unique marque+pari recommandé, bordeaux
essayé puis abandonné pour manque de contraste sur fond sombre) --
**palette finale validée** :

| Élément | Couleur |
|---|---|
| Compétitions | `#B8F2E6` (menthe pâle) |
| Clubs/équipes | blanc cassé (`--text`) |
| Heures | gris clair dédié (`--heure`, `#B9C4BF`) |
| Fond principal | vert sombre (`--bg`, inchangé) |
| Gold | réservé exclusivement à la marque (titre) et au pari recommandé |

`--text-secondary` a aussi été assombri (`#B9C4BF` -> `#7E8D86`) pour les
métadonnées de carte (pronostics), distinct de `--heure` qui garde
l'ancienne valeur claire -- deux variables différentes pour deux usages
qui n'ont pas la même exigence de lisibilité.

**Nouvelle fonctionnalité sur `pronostics.html`** : bouton "Par catégorie"
à côté de "Liste complète" -- regroupe les mêmes cartes par championnat
(tri alphabétique du championnat puis par heure), sans rechargement
réseau (retrie/regroupe les données déjà en mémoire, comme le filtre GO).
`script.js` : fonction `construitCarteMatch()` extraite pour être
réutilisable entre les deux modes d'affichage.

**Bug de collision de sous-chaîne trouvé et corrigé en cours de route** :
`"Ligue Nationale"` matchait par erreur à l'intérieur de `"Ligue Nationale
N/S Nord"`, et `"Serie A"` à l'intérieur de `"Coupe Féminine de Serie A"`
-- l'égalité stricte réintroduisait d'autres problèmes (casse les
suffixes de groupe légitimes comme "Girone A"). Solution retenue : "commence
par" partout, avec des gardes explicites nommées pour les cas de collision
identifiés (voir 18.4).

### 18.3 Le filtre de compétitions -- vue d'ensemble
**Objectif de départ (Patrick)** : réduire drastiquement le nombre de
championnats traités automatiquement, sur la conviction que la majorité
des ~2400 matchs d'une fenêtre J+1/J+2/J+3 sont des catégories à faible
valeur (matchs amicaux, coupes de qualification, jeunes, réserves, 2e
divisions, championnats à données quasi systématiquement absentes).

**Résultat final mesuré sur la fenêtre du 03/09** :
- Source brute : 2569 matchs (avant dédoublonnage)
- Fenêtre finale après tous les filtres : **953 matchs (37,1% conservé)**
- 125 pays/zones explicitement couverts (108 dans une liste "1ère
  division unique", 17 dans un système à paliers multiples)

**⚠️ CE FILTRE N'A JAMAIS TOURNÉ EN PRODUCTION.** Tout le travail décrit
ci-dessous a été testé exclusivement en rejouant les fonctions Python
contre un instantané figé (`precalcul.json` du dernier run réel, celui du
02-03/09) -- jamais par une exécution réelle de `precalcul.py` dans
GitHub Actions avec des données fraîchement scrapées. **Vérifier le
prochain run réel de bout en bout est la priorité n°1 après 18.1.**

### 18.4 Détail des blocs du filtre (tous dans `precalcul.py`, appliqués dans `charge_matchs_fenetre()`, AVANT la résolution Betpawa et AVANT `construit_signaux()`)

**Ordre d'application, chacun réduisant `fenetre` avant le suivant :**

1. **`est_jeune_ou_reserve()`** -- regex élargie au fil de la session :
   `u1[5-9]`/`u20`/`u21`, `réserve`/`reserve`/`reserva` (piège trouvé :
   l'orthographe espagnole "Reserva" n'était pas captée au départ),
   `espoir`, `primavera`, `berretti`, `beloften`, `jugendliga`, `juvenil`,
   `junior`, `aspirantes`, `cadete`, `infantil`, `jeunes`, `mladinska`
   (ces derniers mots-clés trouvés en construisant le reste du filtre, pas
   dès le départ). **195 matchs exclus sur la fenêtre du 03/09.**
2. **`est_competition_exclue()`** -- liste EXPLICITE (pays, sous-chaîne),
   jamais un mot-clé générique. Couvre les 2e divisions confirmées
   d'Afrique/Asie/Amérique (Égypte "2. Ligue", Corée "K-Ligue 2", Japon
   "J2 Ligue", Qatar "Division 2", Panama "Liga Prom", Guatemala "1ère
   Division Groupe B", Brésil Série B/C/D + toutes les compétitions
   d'État de niveau 2/3, Chili "Primera B", Colombie "Première B", Costa
   Rica "Liga de Ascenso", Pérou "2. Ligue"/"Liga 3", Uruguay "Segunda
   Division"/"Primera División Amateur", Venezuela "Segunda Division",
   Équateur "Première B", USA "USL"+"USL Ligue 1", Mexique "Ascenso
   MX"+"Liga TDP", Argentine "Tournoi Fédéral A") + deux cas exclus sur le
   critère "données souvent absentes" plutôt que le niveau exact (ÉAU
   "Division 1", Ouzbékistan "1ère Division"). **146 matchs exclus.**
   Panama et Guatemala : confiance passée de moyenne à HAUTE en cours de
   session (confirmés via Wikipedia -- Panama "Liga Prom" = "Level on
   pyramid: 2" + composée d'équipes réserve "Tauro FC II" ; Guatemala
   "Primera División" = 2e échelon officiel malgré le nom).
3. **`est_chine_non_autorisee()`** -- liste blanche dédiée, PAS la liste
   noire générale (patron à réutiliser pour tout futur cas par pays).
   Seule "Super Ligue" autorisée -- "Ligue 1" chinoise confirmée être le
   2e échelon (China League One, "Level on pyramid: 2", piège de
   traduction comme l'anglais "League One"). Patrick a d'abord demandé de
   garder les deux, puis s'est ravisé pour ne garder que la Super Ligue --
   décision finale, ne pas revenir dessus sans qu'il le redemande
   explicitement. **8 matchs exclus.**
4. **`est_oceanie_non_autorisee()`** -- liste blanche par ZONE (pas un
   seul pays). Consigne explicite de Patrick : ne garder QUE le 1er
   échelon australien et néo-zélandais, "cette liste n'est pas un
   standard à généraliser ailleurs". **Piège découvert via une vraie
   capture d'écran matchendirect (pas Wikipedia, sur consigne explicite
   de Patrick -- "Matchendirect fait foi ici")** : il n'existe PAS de 1ère
   division néo-zélandaise séparée -- les clubs néo-zélandais (Auckland,
   Wellington Phoenix) jouent dans la MÊME compétition que l'Australie,
   nommée "A-Ligue". Ce qui apparaît sous le pays "Nouvelle-Zélande"
   séparément ("Premier League", subdivisée en ligues régionales) est un
   échelon inférieur. Implémenté : seule "Australie : A-Ligue" passe,
   "Nouvelle-Zélande" en tant que pays séparé est toujours exclue, comme
   les autres nations du Pacifique (Nouvelle-Calédonie, Îles Cook, Îles
   Salomon...). **10 matchs exclus.** ⚠️ Aucun match australien/néo-
   zélandais n'était présent dans la fenêtre testée -- le nom exact
   "A-Ligue" est confirmé par capture d'écran, mais le comportement du
   filtre sur un vrai match n'a jamais été vérifié en conditions réelles.
5. **`est_femmes_non_autorisee()`** -- liste blanche, consigne explicite
   de Patrick : "seulement la 1ère division européenne, tout le reste
   supprimé" -- y compris la NWSL américaine (pourtant la meilleure ligue
   féminine au monde), exclue uniquement parce qu'elle n'est pas
   européenne. Onze compétitions confirmées sur la fenêtre testée
   (Allemagne, Angleterre, Belgique, Espagne, Estonie, Hongrie, Lituanie,
   Pays-Bas, Serbie, Slovaquie, Écosse), complétées ensuite avec des noms
   de marque trouvés dans le répertoire officiel matchendirect (voir
   18.5) : Suède "Damallsvenskan", Norvège "Toppserien", Suisse
   "Nationalliga A" -- ces trois-là n'ont AUCUN marqueur textuel
   "femme"/"féminin" détectable, la fonction de détection a dû être
   élargie spécifiquement pour ne pas les exclure par erreur (voir bug
   ci-dessous). **Piège trouvé (Norvège)** : "1. Division Femmes" est la
   2e division féminine norvégienne (confirmé Wikipedia, "Level on
   pyramid: 2") -- le vrai 1er échelon est "Toppserien", absent de la
   fenêtre testée. **Gap connu, PAS complètement corrigé** : la détection
   ne couvre que "femme"/"femin"/"fémin"/"zenska" -- toute ligue féminine
   nommée uniquement par une marque sans AUCUN de ces marqueurs (à l'image
   de Damallsvenskan avant qu'on la découvre) peut encore échapper à la
   détection dans un pays non encore audité. **75 matchs exclus.**
6. **`est_europe_hommes_non_autorisee()`** -- système à PALIERS
   MULTIPLES pour 17 pays, seule structure qui ne rentre pas dans le
   modèle "1 seule compétition autorisée" des autres blocs :
   - **Angleterre** : jusqu'au palier 5 (National League) --
     Premier League/Championnat/League One/League Two/Ligue Nationale.
   - **France, Espagne, Italie, Allemagne, Portugal** : jusqu'au
     palier 3. Piège confirmé (Portugal, via recherche externe) :
     "Ligue 3" EST le palier 3 depuis 2021, "Campeonato de Portugal" est
     DESCENDU au palier 4 la même année -- l'inverse de ce qu'on pourrait
     supposer au nom.
   - **Norvège, Suède, Suisse, Belgique, Écosse, Finlande, Autriche,
     Pays-Bas, Pologne, Turquie, Slovénie** : les deux premières ligues.
     Piège confirmé (Pays-Bas) : "Deuxième Division" est en réalité la
     Tweede Divisie, palier 3 amateur -- PAS le vrai palier 2 (Eerste
     Divisie, déjà nommé différemment). Confiance MOYENNE, jamais
     vérifiée par une source externe : Écosse (Premier Ligue/Première
     Division = Premiership/Championship, déduit de l'ordre logique) et
     Belgique ("2e Division" = Challenger Pro League, supposé). Autriche :
     aucune compétition des paliers 1-2 n'apparaissait dans la fenêtre
     testée -- la règle ne retient donc rien pour l'Autriche cette
     fois-ci, ce n'est pas un oubli.
   - **Garde anti-collision** : "Ligue Nationale" (Angleterre, palier 5
     autorisé) vs "Ligue Nationale N/S Nord" (palier 6) -- exclusion
     explicite si "Nord"/"Sud" apparaît en plus.
   - Toute "coupe" est exclue directement dans ce bloc, quel que soit le
     pays de cette liste. **666 matchs exclus.**
7. **`est_hors_top_flight_unique()`** -- fusion en UNE seule structure
   (`TOP_FLIGHT_UNIQUE_PAR_PAYS`, 108 entrées) de ce qui était initialement
   4 blocs séparés (reste de l'Europe, Amérique, Afrique, Asie) -- sur
   demande explicite de Patrick ("on va intégrer les matchs européens à
   cette liste"). "Commence par" partout (pas égalité stricte) : les
   saisons Apertura/Clausura/Ouverture/Clôture sont la norme hors Europe
   de l'Ouest. `None` = zone toujours exclue (confédérations continentales
   CAF/ASEAN/Amérique du Nord/Amérique du Sud, "Monde" -- matchs
   amicaux --, Malte -- voir ci-dessous). Valeur en tuple = plusieurs
   compétitions autorisées (voir coupes européennes ci-dessous).
   - **Malte EXCLUE ENTIÈREMENT**, décision explicite de Patrick après
     qu'un cas spécial (saison scindée Ouverture/Clôture cassait la
     comparaison) ait posé problème -- "si ça pose problème, exclus-la,
     elle apparaît de toute façon presque jamais dans les propositions
     Betpawa". Ce n'est PAS une règle générale ("pas de cas spécial
     nulle part") -- juste ce pays précis.
   - **Piège confirmé (Afrique du Sud, via Wikipedia)** : "Ligue 1" =
     National First Division = 2e échelon officiel ("Level on pyramid:
     2") -- le vrai 1er échelon est "Première Ligue de Football".
     **Confirmé ensuite directement sur une vraie fiche matchendirect**
     (capture d'écran de Patrick, classement réel avec Orlando Pirates/
     Mamelodi/Kaizer Chiefs) -- Matchendirect fait foi, pas seulement
     Wikipedia, consigne retenue pour la suite.
   - **Piège confirmé (Hong Kong)** : "HKFA 1ère Division" = ancien nom du
     1er échelon, rétrogradé 2e échelon lors de la restructuration de
     2014 -- le vrai 1er est "Premier Ligue".
   - Canada : "Nord Super League" (Northern Super League, féminine,
     confirmée être une vraie 1ère division professionnelle) est
     volontairement exclue ICI -- cohérent avec la règle femmes
     (Amérique non-européenne, donc hors périmètre féminin autorisé).
   - Trois pays en **confiance MOYENNE, jamais confirmés sur une vraie
     fiche matchendirect** : Chili "Superliga", Égypte "Première Ligue"
     (aucun match au 1er échelon dans la fenêtre testée pour vérifier),
     Panama "Liga Prom"/Guatemala (déjà passés en confiance haute, voir
     point 2).
   - **Garde anti-collision** : "Super Ligue" (Grèce, Serbie) vs "Super
     Ligue 2" -- même patron que la garde Angleterre.
   - **Compétitions de clubs européennes intégrées, à la demande de
     Patrick** : "Europe" autorise un TUPLE de 3 valeurs -- "Ligue des
     Champions Phase de Ligue", "Ligue Europa Phase de Ligue", "Ligue
     Conférence Phase de Ligue". Noms exacts confirmés par captures
     d'écran RÉELLES de Patrick (pas une source externe) -- "Phase de
     Ligue" fait partie du nom actuel depuis le nouveau format à ligue
     unique (2024/25), PAS juste "Ligue des Champions"/"Ligue Europa"
     comme une première tentative basée sur un souvenir de session
     antérieure l'avait supposé à tort. La variante "... - des équipes
     Françaises" (vue distincte sur le site) est la même compétition,
     capturée automatiquement par "commence par" puisque c'est un
     suffixe. Confirmé à exclure : "Ligue des Nations de l'UEFA"
     (sélections nationales, pas des clubs). "Ligue Conférence Phase de
     Ligue" n'a jamais été vue en vrai dans une capture -- déduite par
     cohérence avec les deux autres, à vérifier si le nom réel diffère.
   - **258 matchs exclus** (dernier chiffre mesuré, après les 3 pays
     oubliés ajoutés lors de l'audit final -- voir 18.5).

### 18.5 Audit final -- 2 passes, dans les deux sens
**Passe 1 (faux négatifs -- des matchs auraient dû être exclus mais
survivent)** : vérification systématique que CHAQUE match survivant dans
la fenêtre finale appartient à une catégorie explicitement validée (liste
Femmes, système à paliers, ou liste unique). A débusqué **3 pays
complètement oubliés** dans la construction du filtre (jamais ajoutés à
aucune liste, fuite totale depuis le début malgré tout le travail déjà
fait) :
- **Japon** : "J1 Ligue" ajouté (J2 Ligue déjà exclue séparément).
- **République Tchèque** : jamais traitée du tout -- "Ligue Tchèque"
  ajoutée comme seul palier autorisé.
- **Îles Féroé** : jamais traitée -- "Formuladeildin" ajoutée ; piège
  trouvé au passage, "1 Deild" est le 2e échelon malgré le nom.
- **"Monde" (matchs amicaux internationaux)** : jamais traité -- ajouté
  en exclusion totale (`None`).

**Passe 2 (faux positifs -- des matchs auraient pu être exclus par
erreur)** : vérification qu'aucune clé n'est dupliquée dans les
dictionnaires (aurait écrasé silencieusement une entrée), qu'aucun pays
n'apparaît dans les deux systèmes à la fois (paliers multiples ET liste
unique -- aurait pu créer un conflit), et qu'aucun pays avec des matchs
bruts n'a zéro survivant sans raison légitime (les 2 seuls cas trouvés,
Égypte et Îles Féroé, s'expliquent par l'absence de match à leur 1er
échelon ce jour précis, pas par un bug d'orthographe).

**Les deux passes sont passées propres à la fin de la session** -- mais
rappel du 18.3 : ceci reste une vérification contre un instantané figé,
jamais un run réel.

### 18.6 Le gap "listes des jours affichées" -- CORRIGÉ EN SESSION
Patrick a soulevé un point que je n'avais pas anticipé : tout le filtre
ci-dessus ne touchait que `precalcul.json`/`precalcul_leger.json` (le
pipeline automatique), jamais les fichiers que l'accueil (`index.js`)
affiche pour la sélection manuelle du panier (`matchs_du_jour.json`,
`matchs_demain.json`) -- un utilisateur pouvait donc toujours voir et
sélectionner manuellement un match U19/2e division/etc. sur la page
d'accueil, malgré tout le travail de filtrage.

**Solution retenue, importante à ne pas défaire par erreur** : NE PAS
filtrer les fichiers bruts eux-mêmes -- `run_pipeline.py`
(`normalise_panier`) en a besoin intacts pour résoudre un `match_id`
ajouté manuellement au panier, y compris un match hors filtre (un
utilisateur doit pouvoir forcer l'analyse d'un cas particulier). À la
place : `precalcul.py` génère deux NOUVEAUX fichiers,
`matchs_du_jour_filtre.json` et `matchs_demain_filtre.json` (même contenu
que les fichiers bruts, filtré avec exactement les mêmes fonctions que
1-7 ci-dessus via une fonction combinée `est_match_a_masquer()`).
`index.js` a été modifié pour lire ces 2 nouveaux fichiers.
`pipeline.yml` les ajoute au commit (boucle conditionnelle, comme
`precalcul_leger.json`).

**Testé contre les vraies données** : aujourd'hui 176 -> 70 matchs,
demain 405 -> 166 matchs. **Jamais vérifié en conditions réelles
(GitHub Actions)**, même limite que tout le reste de la session 18.

**Précision importante donnée à Patrick, à ne pas oublier** : la page
`pronostics.html` (J1/J2/J3, pipeline automatique) était déjà
intégralement couverte par le filtre depuis le début de la session --
seule la page d'accueil (sélection manuelle "Aujourd'hui"/"Demain")
avait ce trou. Il n'existe pas de sélection manuelle pour J+2/J+3 sur
l'accueil (seulement 2 onglets) -- un 3e onglet "Semaine" est prévu dans
le code JS (`chargeJour("semaine", "catalogue_unifie.json")`) mais
**`catalogue_unifie.json` n'existe pas, aucun script ne le génère** -- un
hook mort qui échoue silencieusement à chaque chargement de la page
d'accueil. Pas corrigé, pas prioritaire, mais signalé -- à finir ou
supprimer si Patrick le demande.

### 18.7 Découverte de session -- la vraie cause de la lenteur du pré-calcul
En creusant pourquoi limiter Betpawa à 5 matchs au lieu de 100 ne changeait
presque rien au temps de run (question posée par Patrick), lecture directe
du code de `precalcul.py` : `construit_signaux(fenetre)` tourne sur
l'INTÉGRALITÉ de la fenêtre, sans aucune condition liée à
`PRECALCUL_LIMITE_BETPAWA` -- cette variable ne limite QUE
`resout_cotes_betpawa()`, l'étape d'avant. Erreur de diagnostic de ma part
à corriger : le correctif de la session 17 (17.3) n'a jamais visé la
bonne variable pour contrôler la durée totale du run.

**Structure interne de `construit_signaux()` clarifiée** (dans
`run_pipeline.py`, jamais modifiée) : chaque match fait d'abord un appel
"détails", puis les stats GF/GA des 2 équipes (déjà mises en cache depuis
la session 16, voir `cache_equipes.py`) -- **si l'une des deux échoue, le
match s'arrête là** (`continue`), sans jamais atteindre les 3 appels
suivants (classement, H2H, cotes). Donc les matchs qui finissent PARTIAL
coûtent peu (1 à 4 requêtes) ; le vrai coût se concentre sur les matchs
qui ont une vraie chance de finir READY.

**Gaspillage réel confirmé** : `recupere_classement_du_match(url_match)`
attache l'URL du CLASSEMENT à l'URL du MATCH individuel -- si une
compétition a 10 matchs dans la fenêtre, son classement (identique pour
tous) est retéléchargé 10 fois, sans aucun cache (contrairement aux stats
d'équipe). Même chose pour `recupere_h2h` (refait à chaque nuit pour la
même paire, alors que l'historique de confrontation ne change quasiment
jamais).

**Deux pistes comparées, une seule retenue pour l'instant** : la
proposition initiale de Patrick (3 runs séparés par jour, décalés de 2
minutes, ne recalculant que le jour "neuf" chaque nuit) a été comparée à
l'extension du cache déjà existant (classement par compétition, H2H par
paire, même patron que `cache_equipes.py`). **Verdict donné à Patrick,
jamais tranché explicitement par lui, jamais implémenté** : l'extension du
cache est plus petite, moins risquée, et le gain potentiel (facteur 10 sur
une compétition à 10 matchs) est probablement supérieur à un découpage en
3 runs. **Le filtre de compétitions (18.3-18.5) a été construit à la
place, en réponse à la même préoccupation de lenteur, mais agit sur un
levier différent (moins de matchs au total) plutôt que sur le coût par
match.** Les deux approches sont complémentaires, pas exclusives -- rien
n'empêche de faire les deux plus tard.

### 18.8 Piste explorée puis mise en pause -- bug Premier League/Serie A/La Liga (0% READY)
En croisant le statut READY/PARTIAL par compétition sur la fenêtre du
02-03/09 : Premier League, Serie A et La Liga affichaient **0% de matchs
READY** (Arsenal-Chelsea, Real Madrid, etc.), alors que Bundesliga (20/21)
et Ligue 1 (44/62) fonctionnaient presque normalement. Ce n'est
structurellement pas une question de couverture de données (ce sont les
clubs les plus documentés au monde) -- diagnostic en cours au moment où
Patrick a explicitement demandé de mettre cette piste en pause ("pas la
priorité, on avance sur le filtre").

**État du diagnostic au moment de la pause, à reprendre tel quel si
Patrick redemande d'y revenir** :
- Hypothèse initiale (mots génériques "liga" retirés avant comparaison,
  cassant spécifiquement "La Liga") -- **infirmée** : vérifié que le
  champ `competition` côté precalcul ET le libellé réel de la page
  matchendirect (Real Madrid) utilisent tous les deux "LaLiga" en un seul
  mot, donc la comparaison de texte devrait réussir.
- Hypothèse retenue ensuite, non vérifiable avec les outils disponibles :
  `recupere_classement()`/`_extrait_historique_competition`
  (`scraper_details.py`) utilise `.find_next("table")` après avoir trouvé
  le titre de section -- si matchendirect a migré la mise en page des
  résultats de match vers des `<div>` plutôt que des `<table>` HTML pour
  CERTAINES ligues (Premier League/Serie A/La Liga) mais pas d'autres
  (Bundesliga/Ligue 1), le code sauterait par-dessus tous les matchs et
  tomberait sur un tableau HTML sans rapport plus bas dans la page
  (repéré sur la page Real Madrid : le seul vrai `<table>` restant est la
  liste des joueurs de l'effectif). **Jamais confirmé** -- l'outil de
  récupération de page utilisé convertit le HTML en texte lisible et ne
  permet pas de voir la structure exacte des balises, et il n'y a pas
  d'accès réseau direct à matchendirect.fr depuis le bac à sable.
- Solution proposée pour trancher, jamais mise en œuvre : un script de
  diagnostic jetable tournant DANS GitHub Actions (accès réseau réel),
  qui imprimerait juste la structure trouvée après le titre "LaLiga" sur
  une vraie page, sans toucher au comportement de production.
- **Impact potentiel si confirmé et corrigé** : récupérerait des READY
  sur certains des matchs les plus regardés et les mieux documentés du
  monde, actuellement perdus. Plus intéressant que filtrer des
  championnats obscurs, mais plus risqué à corriger (touche
  potentiellement `scraper_details.py`, fichier jamais modifié à ce jour).

### 18.9 Répertoire officiel matchendirect (`/competition-foot/`) -- utilisé, avec une réserve importante
Patrick a récupéré et transmis le contenu complet de cette page (~650
compétitions listées par pays) -- base précieuse pour construire le
filtre à partir d'une liste exhaustive plutôt que d'attendre qu'une
compétition apparaisse par hasard dans une fenêtre de 3 jours.

**Réserve importante, découverte en l'utilisant** : ce répertoire semble
accumuler aussi des noms ANCIENS/renommés, pas seulement les noms
actuellement en usage. Exemple concret trouvé : pour la France, le
répertoire liste "National", "CFA", "CFA 2" -- alors que les vraies
données de match actuelles utilisent "Ligue 3", "National 2", "National
3" (renommage officiel réel il y a plusieurs années). **Le répertoire
n'a donc jamais été traité comme source de vérité absolue** -- chaque nom
en a été extrait comme hypothèse de travail, puis vérifié soit contre les
vraies données d'une fenêtre récente, soit contre une source externe,
soit (préférence explicite de Patrick, voir 18.4 point 7) contre une
vraie capture d'écran matchendirect.

### 18.10 Ce qui restait à faire fin de session 18 — voir section 19 pour la suite réelle
(Liste conservée telle quelle pour l'historique ; chaque point y est marqué
comme résolu, partiellement résolu, ou reporté.)
1. `precalcul_leger.json` (18.1) → **RÉSOLU**, voir 19.1.
2. Filtre de compétitions en conditions réelles (18.3) → **RÉSOLU**, voir 19.2.
3. Impact sur la durée du run / cache classement-H2H (18.7) → **cache
   ajouté**, voir 19.6. Durée mesurée en situation réelle, voir 19.12.
4. Bug Premier League/Serie A/La Liga (18.8) → **rouvert et son ampleur
   réelle découverte : 42 compétitions, 30,5% du volume**, voir 19.10.
   PRIORITÉ ABSOLUE prochaine session.
5. ROI réel du moteur (0.1) → **calculé pour la première fois,
   automatisé**, voir 19.8.
6. Points de confiance moyenne (18.4) → toujours en attente d'une vraie
   occasion (Chili "Superliga", Égypte "Première Ligue", Écosse/Belgique,
   Océanie, "Ligue Conférence Phase de Ligue").
7. Hook "semaine" mort dans `index.js` → **RÉSOLU, supprimé** (Patrick a
   tranché : 4 jours max, plus besoin), voir 19.4.
8. Purge cache Betpawa, couverture Betpawa réelle, Phase 5/6 → toujours
   non traités.

---

## 19. Session du 04/09/2026 — J0 + Betpawa illimité + 2 bugs graves trouvés et corrigés + bug 18.8 massivement élargi

Session la plus dense à ce jour, enchaînant une longue série de demandes
de Patrick. Résumé dans l'ordre chronologique.

### 19.1 `precalcul_leger.json` (18.1) — RÉSOLU, confirmé par preuve indépendante
Le diagnostic instrumenté en session 18 (ls -la / git status avant-après
`git add`) a enfin été lu sur un run réel (#91) : le fichier était bien
présent, bien indexé, bien commité (`98b7b99`, 12 fichiers changés).
**Vérifié en plus par un moyen indépendant du log** : fetch direct de
`raw.githubusercontent.com/.../precalcul_leger.json`, HTTP 200, taille
exactement identique à celle annoncée dans le log. Le site
(`pronostics.html`) charge désormais ce fichier sans erreur 404.

Note : le fichier était marqué `M` (modifié) et non `A` (nouveau) dans le
commit — signe qu'un des runs précédents avait en fait réussi à le
committer sans que ce soit su. Sans conséquence, juste une note pour
comprendre l'historique.

### 19.2 Filtre de compétitions (18.3) — RÉSOLU, chiffres réels
Run #91 : fenêtre réduite de 2621 matchs sources à 951 après filtre
(~36-38% conservé), cohérent avec le 37,1% mesuré en session 18 sur
l'instantané figé. Détail des 7 filtres (comptages réels, run #91) :
jeunes/réserves -200, liste explicite -160, Chine -8, Océanie -7, Femmes
-78, Europe hommes paliers -685, 1ère division unique -378. Aucun
championnat majeur disparu par erreur constaté.

### 19.3 Ajout de J0 (aujourd'hui) à la fenêtre automatique + date/heure sur chaque carte
Demande de Patrick : la fenêtre automatique (jusque-là J+1/J+2/J+3) inclut
désormais aujourd'hui. Changements :
- `precalcul.py` : `charge_matchs_fenetre()` inclut `matchs_du_jour.json`.
- **Bug trouvé en l'implémentant** : `archive_precalcul()` n'archivait
  qu'à la date J+1 -- un match J0 ne traverse la fenêtre qu'UNE nuit,
  contrairement à J+2/J+3 qui progressent sur plusieurs nuits. Sans
  correctif, ces matchs auraient été analysés puis jamais archivés.
  Corrigé : archive désormais sur (aujourd'hui OU J+1).
- `script.js` : nouvel onglet "Aujourd'hui" (actif par défaut), onglets
  renommés "Aujourd'hui / J+1 / J+2 / J+3" (avec le "+", demande explicite
  de Patrick). Chaque carte affiche désormais sa date exacte à côté de
  l'heure (`m.date` + `m.heure` dans `construitCarteMatch()`).
- `index.html`/`index.js` (panier manuel) : **non concerné** par ce
  changement -- reste volontairement limité à aujourd'hui/demain pour la
  sélection manuelle, "aujourd'hui" dans la fenêtre auto est une fonction
  séparée de la sélection panier.

### 19.4 Betpawa illimité + suppression du hook "semaine" + `scraper_semaine.py` recentré
- Plafond `PRECALCUL_LIMITE_BETPAWA` (100) supprimé. Justifié par les
  chiffres réels : run #91 (plafond 100) = 33m37s total ; seul test
  "illimité" antérieur (02/09, avant filtre) = 5h18m sur 1574 matchs.
  Large marge de sécurité. **Confirmé sur run #94** (1050 matchs, Betpawa
  illimité) : run total 2h50m28s, dont 1h45m38s pour Betpawa seul --
  toujours confortablement sous les 6h de GitHub Actions, mais Betpawa
  est redevenu le vrai poste de temps.
- `index.js` : onglet "semaine" et bouton "Analyser" supprimés -- code
  mort confirmé (aucun élément HTML correspondant dans `index.html`,
  jamais fonctionnel ; pointait vers `catalogue_unifie.json`, un fichier
  que rien ne génère). Tranche définitivement le point 18.10-7.
- `scraper_semaine.py` : plage par défaut réduite de J+2/J+7 à J+2/J+3 --
  les jours J+4 à J+7 ne servaient nulle part (ni au pré-calcul, ni au
  hook mort supprimé ci-dessus).

### 19.5 Panier manuel : ne re-scrape plus un match déjà analysé
Demande de Patrick, vérifiée d'abord (n'était PAS le cas) : chaque envoi
de panier déclenchait systématiquement un scraping complet, même pour un
match déjà connu. `dispatch_pipeline.py` cherche désormais dans
`precalcul.json` (fenêtre courante) PUIS `historique_pronostics.json`
(archive) avant de lancer quoi que ce soit :
- Si tous les matchs du panier sont déjà connus → aucun scraping, résultat
  renvoyé directement.
- Sinon → seuls les matchs manquants sont écrits dans `panier.json` et
  scrapés.
- Règle stricte du panier (afficher UNIQUEMENT les matchs sélectionnés)
  vérifiée et testée -- aucune fuite d'un match non demandé.
- **Limite assumée** : le déclenchement du workflow GitHub Actions
  lui-même reste inévitable (le clic panier passe toujours par
  Supabase + `trigger.js`) -- seul le scraping coûteux est évité,pas
  l'appel réseau initial. Éliminer ça demanderait de toucher les règles
  RLS Supabase, non vérifiable depuis l'environnement de l'assistant.

### 19.6 Cache classement + H2H (extension de 18.7)
`cache_equipes.py` mettait déjà en cache le GF/GA (découvert en creusant,
pas su avant) -- ce qui manquait vraiment : classement et H2H, jamais
cachés. Deux nouveaux modules ajoutés, même modèle que `cache_equipes.py` :
- `cache_classement.py` : clé = **nom de la compétition** (pas l'URL du
  match) -- tous les matchs d'une même ligue, dans la MÊME fenêtre,
  partagent désormais un seul classement au lieu d'un fetch par match.
  Nécessite `recupere_classement_du_match(url_match, competition)` (2e
  argument ajouté, optionnel, ignoré par la fonction réelle -- ne casse
  pas le flux panier manuel qui l'appelle aussi). TTL 12h.
- `cache_h2h.py` : clé = URL du match (un H2H est propre à une paire
  précise, rien à regrouper entre matchs différents contrairement au
  classement -- utile seulement pour une relance sur les mêmes matchs).
  TTL 7 jours.
- **Testé avant livraison** : simulation avec 3 matchs "France : Ligue 1"
  + 1 "Espagne : LaLiga" → la fonction de scraping n'a été appelée qu'une
  fois par compétition (pas par match). Confirmé fonctionnel.

### 19.7 BUG GRAVE TROUVÉ ET CORRIGÉ -- doublons dans `historique_pronostics.json`
En répondant à "combien de matchs analysés au total", découverte que
l'archive contenait **570 doublons sur 1251 entrées (45%)** -- des blocs
entiers réarchivés à l'identique à chaque run relancé le même jour (aucune
vérification avant ajout). Un 2e bug lié : un lot mélangeant J0 et J+1
(depuis 19.3) était étiqueté avec UNE SEULE date pour tout le lot,
mislabelant les matchs J0.

**Corrigé** : nouvelle fonction `ajoute_matchs_a_historique()` dans
`run_pipeline.py` (réutilisée par `archive_run()` ET `archive_precalcul()`) :
- Déduplique par `match_id` (ou domicile/extérieur à défaut), PAR DATE.
- Range chaque match dans le bloc de SA PROPRE date (`m.get("date")`), pas
  une date supposée pour tout le lot.
- **Testé avant livraison** : rejouer deux fois le même lot n'ajoute rien
  la 2e fois ; un lot mélangeant deux dates se range en deux blocs
  séparés.

**Nettoyage rétroactif appliqué** : fichier existant nettoyé en réutilisant
la fonction corrigée elle-même (pas une logique de nettoyage à part) →
1251 → **682 matchs réellement distincts**. Patrick a remplacé le fichier
sur GitHub via "Upload files" (l'éditeur en ligne ne gère pas bien un
fichier de 2,7 Mo sur mobile). Après le run #94 (nouvel archivage propre) :
**977 matchs, 0 doublon détecté** dans les 9 blocs.

### 19.8 Premier calcul RÉEL du ROI -- `calcule_roi.py`
Personne n'avait jamais vérifié automatiquement si un pari GO avait
réellement gagné -- `verification_resultats.py` remplit juste le score
final, rien de plus. Nouveau script `calcule_roi.py`, tourne après
`verification_resultats.py` dans `pipeline.yml` :
- Règles de chaque marché (22 types : 1X2, double chance, BTTS,
  over/under total et par équipe, handicap, pair/impair, cage inviolée,
  score exact, nombre exact de buts) copiées EXACTEMENT depuis
  `construit_candidats()` (`run_pipeline.py`) -- pas réinventées.
- Écrit `roi_dashboard.json` : résumé global + par marché + par confiance
  + détail pari par pari.
- **Auto-correction notable** : le premier calcul fait à la main par
  l'assistant (avant d'écrire le script) contenait un bug -- `total < 3`
  au lieu de `total < 3.5` pour "Moins de X.5 buts", faisant perdre à tort
  les matchs à exactement 3 buts. Détecté en testant le script contre le
  calcul manuel, corrigé avant livraison.
- **Chiffre réel actuel (39 paris, échantillon minuscule)** : 22 gagnés
  (56,4%), ROI -16,9%. Par marché : Plus de X.5 buts +2,2% (meilleur),
  1X2 -54% (pire, mais seulement 3 paris -- pas significatif). Cohérent
  avec le -15,5% mesuré fin août -- pas de dérive alarmante, mais rien à
  changer dans `calculs.py` sur un échantillon aussi petit.

### 19.9 BUG GRAVE TROUVÉ ET CORRIGÉ -- décalage de fuseau horaire sur les dates
En essayant de faire correspondre des scores fournis par Patrick
(captures matchendirect) à des matchs archivés, découverte que 11 matchs
sur les quelques dizaines vérifiées avaient une **date enregistrée fausse**
(décalée d'un jour), tous des matchs d'Amérique latine ou d'Arabie
Saoudite joués tard le soir heure locale.

**Cause identifiée et confirmée par test** : tout le projet utilisait
`datetime.date.today()`, qui renvoie la date du fuseau du SERVEUR (UTC sur
GitHub Actions), alors que matchendirect.fr (site français) regroupe ses
matchs par jour calendaire FRANÇAIS (CET/CEST). Entre 22h00 et 00h00 UTC
(0h-2h du matin en France l'été), le jour a déjà changé en France mais pas
en UTC -- exactement la fenêtre où Patrick déclenche souvent des runs
manuels en soirée.

**Corrigé** : nouvelle fonction `aujourdhui_france()` (`run_pipeline.py`,
`zoneinfo.ZoneInfo("Europe/Paris")`), remplace TOUS les
`datetime.date.today()` du projet : `scraper.py`, `scraper_semaine.py`,
`precalcul.py` (3 fonctions), `verification_resultats.py`. **Trouvé en
vérifiant, pas seulement le backend** : `script.js` (onglets du site)
souffrait du même bug côté navigateur (`toISOString()` convertit en UTC)
-- corrigé aussi, sinon le backend aurait été juste mais l'affichage se
serait décalé 2h chaque nuit quand même.

**Testé avant livraison** : simulation d'un run à 23h30 UTC -- ancien code
aurait dit "27/08", nouveau dit "28/08" (correct, déjà le lendemain en
France à cette heure).

**Ce qui n'est PAS corrigé** : les ~333 matchs déjà mal datés dans
l'historique restent mal datés (voir situation critique #3 en tête de
document). Le correctif empêche la récidive, ne répare pas le passé. 11
d'entre eux ont été corrigés manuellement avec les scores fournis par
Patrick (matchs identifiés en cherchant sur TOUTES les pages fournies, pas
seulement celle de la date enregistrée).

### 19.10 Bug 18.8 -- ampleur réelle découverte : 42 compétitions, 30,5% du volume ⚠️ PRIORITÉ ABSOLUE
Diagnostic `[DIAG 18.8]` (ajouté en session 19, dans
`scraper_details.py::_extrait_historique_competition` et
`recupere_gf_ga_avec_repli`) a tourné sur le run #94. Analyse de
`precalcul.json` réel (pas juste le log) : **42 compétitions ont 0% de
matchs traités**, totalisant **320 matchs sur 1050 (30,5% du volume
total)** -- très au-delà des 2-3 championnats (Premier League/Serie A)
identifiés en session 18. Liste complète des compétitions touchées dans
la sortie de la conversation du 04/09 (à re-générer si besoin : filtrer
`precalcul.json` sur les compétitions avec ≥2 matchs et 0 `traite`).

Cause technique confirmée par le diagnostic : `_extrait_historique_competition`
utilise `.find_next("table")` après avoir trouvé l'ancre texte de la
compétition sur la page de l'équipe -- l'ancre est INTROUVABLE pour un
grand nombre de ligues (confirmé pour Espagne Primera RFEF Groupe 1,
Mexique Liga MX Ouverture, en plus de Premier League/Serie A). Raison
exacte encore à déterminer -- **Patrick doit fournir le zip d'archive de
logs complet du run #94** (`Download log archive` depuis le menu ⚙️ du
job GitHub Actions) pour une analyse exhaustive de toutes les lignes
`[DIAG 18.8]` et identifier un motif commun entre les 42 compétitions.
**Ce zip n'a pas encore été transmis au moment de la rédaction.**

### 19.11 Vérification de scores manuelle -- pages fournies par Patrick (24, 25, 27, 28/08, 03/09)
Extraction réussie du HTML brut depuis des fichiers `.webarchive` Safari
(`plistlib`, clé `WebMainResource.WebResourceData`), réutilisation directe
de `parse_matches()` (`scraper.py`) pour rester cohérent avec le reste du
pipeline. Résultat : seulement 11 matchs sur ~344 en attente ont pu être
mis à jour, TOUS avec une date enregistrée fausse (voir 19.9 -- c'est
cette recherche qui a mené à la découverte du bug fuseau horaire). Les
~333 restants n'étaient simplement sur aucune des 5 pages fournies (vraie
date probablement 26, 29 ou 30/08, jamais demandées). Confirmé
explicitement : **zéro match n'a jamais été archivé avec la date
"2026-09-03" correctement enregistrée** -- mais 7 matchs du 03/09 existent
dans l'archive, mal étiquetés "04/09".

### 19.12 Run #94 -- validation complète, tout vérifié contre les données réelles
Premier run combinant TOUS les changements de la session (J0, Betpawa
illimité, caches, dédup archive, fuseau horaire, `calcule_roi.py`). Un run
précédent de 3h a été interrompu par Patrick puis relancé manuellement --
sans risque : le commit ne se fait qu'en toute fin de pipeline, et le
`concurrency.group` de `pipeline.yml` empêche deux runs de se chevaucher.

Résultat run #94 : **2h50m28s, succès**, vérifié fichier par fichier
(pas seulement le statut vert) :
- `precalcul.json` : J0 inclus (396 matchs sources), fenêtre 1050 matchs,
  662 READY / 388 PARTIAL.
- Betpawa : 1050 tentatives (= 100% de la fenêtre, plus de plafond),
  1h45m38s -- redevenu le vrai poste de temps du run.
- `historique_pronostics.json` : 977 matchs, 0 doublon.
- `roi_dashboard.json` et les 2 nouveaux caches (`cache_classement.json`,
  `cache_h2h.json`) bien générés et commités.

### 19.13 Fichiers livrés cette session (pour référence, tous testés avant livraison)
`pipeline.yml`, `precalcul.py`, `run_pipeline.py`, `scraper.py`,
`scraper_semaine.py`, `scraper_details.py`, `verification_resultats.py`,
`dispatch_pipeline.py`, `index.js`, `script.js`, `pronostics.html`,
`cache_classement.py` (nouveau), `cache_h2h.py` (nouveau), `calcule_roi.py`
(nouveau), `historique_pronostics.json` (nettoyé, donnée pas code).

### 19.14 Ce qui reste à faire (priorités, dans l'ordre suggéré)
1. **Bug 18.8 (42 compétitions, 30,5% du volume)** -- PRIORITÉ ABSOLUE.
   Obtenir le zip d'archive de logs complet du run #94 (`[DIAG 18.8]`),
   l'analyser exhaustivement, identifier le motif commun, proposer un
   correctif testé sur échantillon avant tout déploiement (règle de
   Patrick : jamais toucher aux tamis/calculs sans test complet).
2. Continuer à accumuler l'échantillon ROI (39 paris actuellement, viser
   les ~1000 mentionnés comme objectif) avant toute conclusion ou
   ajustement de `calculs.py`.
3. Décider si les ~333 matchs historiques mal datés (avant le correctif
   fuseau horaire) méritent une correction rétroactive, ou si on les
   laisse tels quels (matchs déjà loin dans le passé, impact limité sur
   le ROI qui se base surtout sur les matchs récents/futurs).
4. Points de confiance moyenne toujours en attente (18.4, reconduit
   depuis session 18) : Chili "Superliga", Égypte "Première Ligue",
   Écosse/Belgique (paliers), Océanie, "Ligue Conférence Phase de Ligue".
5. Purge cache Betpawa/classement/H2H -- aucune politique d'expiration
   automatique en place (`purge_entrees_expirees()` existe dans les 3
   modules mais n'est appelée nulle part). Pas urgent tant que la taille
   reste gérable (`cache_h2h.json` déjà 1,48 Mo après un seul run avec
   Betpawa illimité -- à surveiller).
6. Décision en attente : éliminer complètement le déclenchement réseau du
   panier quand tout est déjà connu (19.5) nécessiterait de revoir les
   règles RLS Supabase -- hors périmètre de l'assistant sans accès direct
   à la config Supabase.

---

## 20. Session du 04/09/2026 (soirée) — Bug 18.8 résolu, régression K_SHRINKAGE trouvée et corrigée, affichage aligné sur le calcul

### 20.1 Bug 18.8 — cause racine trouvée et corrigée (voir 19.10)
Log complet du run #94 analysé en entier (362 lignes `[DIAG 18.8]`). Deux
mécanismes distincts, pas un seul :
- **Cause principale (36 équipes en échec double-saison sur 50)** :
  `find_next("table")` dans `_extrait_historique_competition` attrapait un
  petit tableau décoratif (icône flèche + cloche d'alerte, 1-4 lignes
  `<tr>`, aucun lien `/live-score/`) inséré par matchendirect entre le
  titre de la compétition et le vrai tableau de matchs. Confirmé en
  récupérant la vraie page Cagliari en direct : la vraie table Serie A
  avait bien 2 matchs joués avec score juste après ce tableau décoratif.
  Corrigé dans `scraper_details.py` : avance de tableau en tableau jusqu'à
  trouver un lien `/live-score/`, s'arrête à la section suivante sinon.
- **Cause secondaire, non résolue (14 équipes)** : pour 4 compétitions
  (Suède Allsvenskan/Superettan, Bélarus Première Ligue, Lettonie
  Virsliga), le titre de la compétition n'apparaît carrément pas sur la
  page de l'équipe, dans aucune des deux saisons — vérifié sur AIK Solna
  et Malmö en direct. Possible trou de données côté matchendirect/Mackolik
  pour ces championnats — **Patrick doit vérifier lui-même dans un
  navigateur avant de conclure**, l'assistant n'a pas pu éliminer une
  troncature de son propre outil de récupération avec certitude.
- **Point méthodologique** : sur les 311 équipes qui apparaissent dans le
  log, 261 s'auto-corrigent déjà via le repli sur la saison précédente
  (`recupere_gf_ga_avec_repli`) — le chiffre "320 matchs / 42 compétitions
  à 0%" du run #94 mélangeait donc de vrais échecs et des faux positifs
  qui s'auto-guérissaient déjà. Seules 50 équipes échouaient réellement
  sur les deux saisons.
- Fichier livré et testé (2 cas reconstruits à partir du vrai HTML) :
  `scraper_details.py`. **Pas encore vérifié sur un run réel** — à
  confirmer au prochain diagnostic combien de compétitions restent à 0%.

### 20.2 Régression majeure trouvée dans calculs.py — shrinkage jamais branché
Découverte partie d'une observation de Patrick (pourcentages "explosent les
compteurs", des 100,0% sur des échantillons d'1 seul match). L'investigation
a révélé une régression bien plus grave que prévu :
- `K_SHRINKAGE` était à `1.0` (aucun effet) au lieu de `0.27` (session
  0.2), `BORNE_MIN/MAX_DEFENSE` à `0.70/1.30` au lieu de `0.55/1.60`,
  `SEUIL_EV_MIN` à `0.05` au lieu de `0.12`, `GA_REFERENCE_PAR_LIGUE`
  remplacé par une constante unique `1.35` (`pays` ignoré) — 5 régressions
  sur les 21 constantes gelées de la section 2 (16 autres intactes).
- **Plus grave** : `ajuste_probabilite()` (censée appliquer
  `K_SHRINKAGE`) existait dans le fichier mais **n'était appelée nulle
  part dans tout le pipeline** — confirmé par `grep`. Donc même en
  remettant `K_SHRINKAGE = 0.27`, ça n'aurait rien changé au comportement
  réel tant que le branchement lui-même n'était pas fait.
- Patrick a confirmé une régression accidentelle, pas un choix délibéré
  (le fichier citait un `TABLEAU_RECAPITULATIF.md` "Module 2 v4.3 /
  Module 3 v6.3" comme source — **ce fichier n'existe nulle part dans le
  dépôt**, origine exacte de la régression jamais identifiée avec
  certitude).
- Patrick a explicitement demandé de recalibrer sur les données réelles
  disponibles plutôt que de simplement restaurer 0.27 à l'aveugle.

### 20.3 Re-calibrage empirique — pourquoi 0.27 (et même 0.254 poolé) ne marchent pas
- Calcul du taux de surconfiance sur l'échantillon actuel (39 paris,
  `historique_pronostics.json`) en extrayant directement `probabilite_modele`
  (déjà présent dans `LISTE_B`, jamais exploité par `calcule_roi.py`) :
  **56,4% réel vs 79,2% annoncé -> k=0,220** — cohérent avec le calibrage
  du 30/08 (k=0,270 sur 68 paris). Poolé sur 107 paris : k=0,254.
- **Mais k=0,254 combiné à `FOURCHETTE_COTE_MAX=1.69` rend TOUT pari
  mathématiquement impossible** : même une prédiction certaine (p=1.0)
  plafonne à une probabilité ajustée de 0,627 après ce shrinkage, or il
  faut une cote >= 1,59 rien que pour EV=0 — donc quasiment toute la
  fourchette de cotes actuelle est hors d'atteinte. Vérifié : 0 des 125
  candidats historiques LISTE_A n'auraient passé le filtre EV avec ce k.
  Confirme le souvenir de Patrick d'avoir déjà tenté un shrinkage proche
  de cette valeur et obtenu des NO_GO partout.
- **Réglage retenu comme base primaire**, trouvé par recherche de grille
  (k, seuil_ev) sur les 63 paris concrets disponibles (probabilité + cote
  réelle + résultat), en maximisant le taux de réussite réel sous
  contrainte d'un volume minimum (n>=10, pour éviter le pur bruit
  statistique) : **K_SHRINKAGE = 0,48, SEUIL_EV_MIN = 0,02** -> 70,0% de
  réussite réelle sur 10 paris, contre 57,1% avec l'ancien réglage cassé
  (k=1.0). **Fragile par construction (n=10)** — pas un aboutissement.
- Table complète du compromis (tous les paliers de n de 63 à 1) montrée à
  Patrick avant validation — près de n=63 (quasi toute la donnée), le
  meilleur taux atteignable retombe autour de 57-59%, proche de l'état
  actuel : utiliser "toute la donnée" ramène mécaniquement au point de
  départ, ce n'est pas un choix arbitraire de l'assistant.

### 20.4 Plafond de données découvert — 63 paris, pas plus, et pourquoi
Le pipeline n'archivait QUE les marchés qui passaient déjà le filtre EV du
moment (`LISTE_A_marches_passant_EV_et_cote`) — les cotes des marchés qui
échouaient au filtre existaient en mémoire pendant le run mais n'étaient
jamais écrites sur disque, donc perdues pour toujours. 133 matchs sur 176
à score connu n'ont ainsi aucune cote exploitable pour un recalibrage,
malgré une probabilité modèle archivée.
- **Corrigé** : `run_pipeline.py::construit_candidats()` archive
  désormais TOUS les marchés évalués ayant une cote réelle dans un
  nouveau champ `TOUS_MARCHES_EVALUES`, qu'ils passent ou non le filtre
  EV. L'échantillon exploitable va grossir bien plus vite à partir de
  maintenant (mais pas rétroactivement — les 9 jours déjà archivés
  restent plafonnés à 63).
- `calcule_roi.py::calcule_calibrage()` (nouveau) : refait la recherche
  de grille chaque nuit sur `TOUS_MARCHES_EVALUES`, donne une
  recommandation par palier de volume minimum (10/20/30/50) dans
  `roi_dashboard.json`. **Ne modifie jamais `calculs.py` automatiquement**
  — affiche une recommandation à appliquer manuellement, conformément à
  la règle de Patrick (jamais de changement sur les tamis sans test
  complet).

### 20.5 Incohérence affichage/calcul découverte après coup — "tu inventes tes données"
Après déploiement du correctif ci-dessus, Patrick a signalé (à raison) que
rien ne semblait avoir changé sur le site : le gros badge de probabilité
continuait d'afficher des valeurs proches de 100% même après le correctif.
Cause : `calcule_ev()`/`kelly_stake()` appliquaient bien le shrinkage en
interne (vérifié : l'EV affiché sur plusieurs captures collait exactement
à la formule avec p ajustée, à la décimale près), mais **le badge affiché
restait la probabilité BRUTE** (`probabilite_modele`), jamais mise à jour
pour refléter la correction — une incohérence trompeuse entre ce qui se
calcule et ce qui s'affiche, pas une absence réelle de correction.
- Corrigé : nouveau champ `probabilite_modele_ajustee` calculé une seule
  fois dans `construit_candidats()` (évite de dupliquer
  `ajuste_probabilite()` à chaque marché) ; `script.js` affiche
  désormais cette valeur (badge principal ET tableau de détail), avec
  repli sur la brute pour les matchs archivés avant ce correctif.
- **Leçon pour les prochaines sessions** : quand on corrige un calcul
  interne, toujours vérifier explicitement que l'AFFICHAGE reflète le
  nouveau calcul, pas seulement la logique de décision — l'écart entre
  les deux ici a fait perdre une grosse partie de la session en
  aller-retours évitables.

### 20.6 Heure affichée — décalage France/Cameroun jamais géré
Patrick (basé au Cameroun, UTC+1 fixe) a signalé qu'un match affiché
"20:00" avait en réalité déjà commencé selon son heure locale —
matchendirect affiche systématiquement l'heure française (Europe/Paris,
UTC+2 l'été), jamais convertie ni étiquetée nulle part dans le pipeline ou
le frontend. Vérifié : Pau-Sochaux confirmé "20h00" par plusieurs sources
de presse françaises indépendantes — l'heure elle-même n'était pas
fausse, juste jamais convertie pour un lecteur hors France.
- Corrigé : `scraper.py::convertit_heure_cameroun()` (nouvelle fonction,
  `zoneinfo`), calcule `heure_cameroun` pour chaque match dès le
  scraping (un seul point de correction, couvre `scraper_semaine.py` qui
  réutilise la même fonction). `index.js`/`script.js` affichent
  `heure_cameroun` avec la mention explicite "(heure Cameroun)", repli
  sur l'heure brute pour les statuts en direct ("83'", "MT"...).
- **Limite documentée, non traitée** : un match entre 00h00 et 00h59
  heure française tomberait la veille une fois converti au Cameroun,
  mais "date" (donc l'onglet aujourd'hui/J+1/etc.) resterait celle
  d'origine — décalage d'affichage possible dans ce cas rare, aucun
  championnat suivi ne programmant normalement de coup d'envoi à cette
  heure-là.
- **⚠️ NON CONFIRMÉ EN PRODUCTION AU MOMENT DE CETTE RÉDACTION** — les
  captures de Patrick après déploiement ne montraient toujours pas
  "(heure Cameroun)". Deux causes possibles non tranchées : cache
  navigateur (à tester en navigation privée) ou Netlify n'ayant pas
  redéployé `script.js`/`index.js`. À vérifier en priorité à la
  prochaine session.

### 20.7 Mécanique du pipeline GitHub Actions — clarifiée cette session
- `pipeline.yml` ne se déclenche QUE sur cron (`0 0 * * *`, minuit UTC) ou
  `workflow_dispatch` manuel — **jamais sur un simple push**. Remplacer
  des fichiers dans le dépôt ne relance rien tout seul.
- Soumettre le panier sur le site déclenche bien un vrai run
  (`netlify/functions/trigger.js` -> API GitHub `workflow_dispatch` avec
  `panier_id`), mais `dispatch_pipeline.py` réutilise TEL QUEL le
  résultat déjà archivé pour tout match déjà présent dans
  `precalcul.json`/`historique_pronostics.json` — aucun recalcul. Seuls
  les matchs absents des deux sont traités à neuf. Piège identifié : si
  `precalcul.json` n'a pas encore été régénéré avec un correctif tout
  juste déployé, le panier peut faire croire à tort que rien n'a changé
  sur un match qui s'y trouvait déjà.
- `concurrency: group: pipeline-archetype-foot, cancel-in-progress: false`
  — les runs déclenchés pendant qu'un autre tourne se mettent en FILE
  D'ATTENTE (statut "Pending"), jamais en parallèle ni annulés.
  Comportement volontaire (évite sans doute la récidive du bug de
  doublons d'archivage), pas une anomalie si un run reste "Pending" un
  moment.

### 20.8 Fichiers livrés cette session (tous testés avant livraison)
`scraper_details.py`, `calculs.py`, `run_pipeline.py` (deux versions
successives — la deuxième corrige 20.5), `calcule_roi.py`, `scraper.py`,
`script.js` (deux versions — la deuxième corrige 20.5), `index.js`.

### 20.9 Vérifié en conditions réelles avant la fin de session
Captures du site après déploiement (run manuel complet + tentative de
panier) : GO passés de 71 à 12 (aujourd'hui) et de 172 à 50 (J+1) —
cohérent avec le correctif. EV affiché sur 3 paris différents recalculé à
la main à partir des captures, correspond exactement à la formule avec
`k=0,48` (3,6%, 19,0%, 16,8%, tous exacts à la décimale près) — confirme
que le correctif tourne réellement en production, pas seulement en local.

### 20.10 Ce qui reste à faire (remplace et complète 19.14)
1. **Vérifier que `heure_cameroun` s'affiche bien en production** (20.6)
   — tester en navigation privée d'abord, puis vérifier l'onglet Netlify
   "Deploys" si le problème persiste.
2. **Confirmer combien de compétitions restent à 0% traité** après
   déploiement de `scraper_details.py` (20.1) — comparer au chiffre de
   référence (42 compétitions / 320 matchs du run #94).
3. Vérifier soi-même dans un navigateur si Suède Allsvenskan/Superettan,
   Bélarus Première Ligue, Lettonie Virsliga ont vraiment un trou de
   données matchendirect (20.1) — pas confirmable avec certitude depuis
   l'environnement de l'assistant.
4. Laisser `TOUS_MARCHES_EVALUES` (20.4) grossir plusieurs jours, puis
   relire `calibrage_k_shrinkage` dans `roi_dashboard.json` pour voir si
   `K_SHRINKAGE=0,48` reste le meilleur choix à un palier de volume plus
   élevé (n>=20/30) — ne pas ajuster `calculs.py` avant que ce soit le
   cas.
5. `GA_REFERENCE_PAR_LIGUE` toujours sur la régression (constante unique
   1.35, `pays` ignoré) — reporté cette session faute d'avoir les valeurs
   numériques exactes par pays sous la main (voir 0.3), pas oublié.
6. Points en attente reconduits depuis 19.14, toujours non traités :
   ~333 matchs historiques mal datés (correction rétroactive ou non,
   décision de Patrick) ; confiance moyenne Chili/Égypte/Écosse-Belgique/
   Océanie/Ligue Conférence ; purge cache Betpawa/classement/H2H sans
   politique d'expiration active.
   ## 21. Session du 04-05/09/2026 — Moteur de justification branché, GA_REFERENCE_PAR_LIGUE restauré (25 pays), bug 18.8 corrigé pour de vrai

### 21.1 Bug 18.8 -- correctif RÉEL cette fois
Le "correctif" annoncé en 20.1 n'était en fait jamais écrit dans le fichier
(vérifié par diff avec GitHub main -- identique à l'ancien code bogué).
Corrigé pour de vrai dans scraper_details.py::_extrait_historique_competition
(boucle table-par-table, max 4 tentatives). Testé sur 3 cas synthétiques
(dont Cagliari). PAS ENCORE VÉRIFIÉ sur un run réel.

### 21.2 GA_REFERENCE_PAR_LIGUE restauré -- 25 pays réels
8 pays (FootyStats, déjà présents dans les commentaires) + 16 pays calculés
depuis les vrais CSV Football-Data.co.uk (10 "grands" championnats + 6
extra leagues, saison 2025/26 complète, 0 ligne incomplète). Toujours sur
"default" (1.35) : Écosse, Autriche, et toute compétition continentale.
LIMITE : get_ga_reference ne distingue que par PAYS, pas par division --
Eerste Divisie/Challenge Ligue (2e divisions, très présentes dans les
échecs du 04/09) héritent de la valeur de la 1ère division du même pays.

### 21.3 Moteur de justification branché (moteur_justification.py fourni par Patrick)
Nouveau fichier adapte_justification.py fait le pont entre les vrais matchs
bruts (désormais exposés par scraper_details.py) et le moteur. Réutilise
calcule_roi.verifie_pari() pour les marchés symétriques. Handicap/Score
exact : aucune preuve construite (pas de règle fiable sur historique
orienté). Branché dans run_pipeline.py sur le "pari en or" ; script.js
affiche le nouveau bloc à la place de l'ancien résumé cote/ev/confiance.
TESTÉ : adapte_justification.py de bout en bout (4 scénarios). NON TESTÉ :
le chemin GO complet dans le pipeline réel (seulement le chemin NO_GO).

### 21.4 Fichiers livrés cette session (tous testés avant livraison, sauf 21.3 GO)
scraper_details.py (18.8 + matchs bruts exposés), calculs.py (GA_REFERENCE_PAR_LIGUE,
25 pays), adapte_justification.py (nouveau), run_pipeline.py (justification
branchée), script.js (nouveau bloc justification), historique_pronostics.json
+ roi_dashboard.json (scores du 04/09 injectés, 35/39).
## ⚠️ SITUATIONS CRITIQUES (ajouts du 05/09/2026, à lire en premier)

6. **Confusion de fichiers déjà survenue une fois cette session** : `script.js` a été accidentellement remplacé par le contenu de `calculs.py` sur GitHub, causant un blocage total du site ("Chargement..." infini, aucune erreur visible sans console navigateur). Corrigé, mais **vérifier explicitement, à chaque commit multi-fichiers, que chaque fichier contient bien son propre code** avant de committer — ne jamais supposer.
7. **Aucun des correctifs de cette session n'a encore été vérifié sur un run réel de bout en bout** (voir liste des fichiers en 21.7). Le seul run testé pendant la session a tourné avec un panier périmé (0 match traité) puis avec un mélange de fichiers corrompus — aucune vérification propre n'a encore eu lieu.
8. **GA_REFERENCE_PAR_LIGUE ne distingue que par PAYS, pas par division.** Pays-Bas Eerste Divisie hérite de la valeur Eredivisie, Suisse Challenge Ligue hérite de la Super League — non vérifié si c'est acceptable.
9. **Le veto d'échantillon minimum (SEUIL_MATCHS_MIN_POUR_GO=8) ne peut rien pour les équipes ayant changé de division** (promotion/relégation) dont l'ancien palier n'est pas dans les données Football-Data.co.uk (ex. Primera RFEF espagnole, semi-pro, non couverte) — cas Eldense-Majorque, GO à tort avant le veto, NO_GO après, mais aucune vraie donnée de remplacement n'existe pour ces cas.

## 21. Session du 05/09/2026 — Journée de vérification massive : moteur de justification branché, 6 bugs réels trouvés et corrigés, 1 confusion de fichiers

### 21.1 Bug 18.8 (scraper_details.py) — le "correctif" de la session précédente n'était jamais écrit
Diff avec GitHub main a confirmé que le correctif annoncé en session 20 n'avait jamais été committé (fichier identique à l'ancien code bogué). Corrigé pour de vrai cette fois : boucle table-par-table (max 4 tentatives) au lieu d'un seul `find_next("table")`. Testé sur 3 cas synthétiques. **Toujours pas vérifié sur un run réel** — le run de cette nuit-là a tourné avec un panier périmé (0 match traité), aucune vérification possible.

### 21.2 Cache équipes — 40% de résultats négatifs, purge unique effectuée
`cache_equipes.json` avait 2401/6007 entrées (40%) en résultat négatif ("aucun historique trouvé"), certaines vieilles de plusieurs jours, cachées 7 jours (TTL_SANS_HISTORIQUE_HEURES=168h) — masquait totalement toute vérification du correctif 18.8. Purge ponctuelle effectuée (2401 entrées négatives supprimées, 3606 positives gardées). **Purge non automatisée à ce stade au-delà de ce nettoyage ponctuel** — voir 21.6.

### 21.3 GA_REFERENCE_PAR_LIGUE — 25 pays réels (8 + 16 + 1 déjà présent), reste incomplet
Restauré avec de vraies valeurs calculées depuis Football-Data.co.uk (CSV réels, saison 2025/26 complète, 0 ligne incomplète) pour France, Allemagne, Italie, Turquie, Espagne, Angleterre, Pays-Bas, Portugal, Grèce, Belgique, Suisse, Norvège, Russie, Suède, Danemark, Pologne — en plus des 8 déjà présents (Arabie Saoudite, Corée du Sud, Japon, Estonie, Tunisie, Etats-Unis, South Africa, Chine). Écosse et Autriche restent sur le default (1.35), données saison complète non disponibles. **Limite non résolue : par pays, pas par division** (voir situation critique #8).

### 21.4 Moteur de justification (moteur_justification.py fourni par Patrick) — branché et vérifié en conditions réelles
Nouveau fichier `adapte_justification.py` : fait le pont entre les vrais matchs bruts (désormais exposés par `scraper_details.py`, `recupere_gf_ga_avec_repli` ne les jette plus après la moyenne) et le moteur. Réutilise `calcule_roi.verifie_pari()` pour les marchés symétriques. Handicap/Score exact : aucune preuve construite (pas de règle fiable sur historique orienté sans risque de contresens). Branché dans `run_pipeline.py` sur le "pari en or". **Vérifié sur le run réel du 05/09 (precalcul_leger.json, 968 signaux) : 85/85 matchs GO avaient une justification remplie.** Fonctionne.

### 21.5 Badge de probabilité — supprimé, remplacé par le vrai taux de réussite mesuré
L'ancien badge affichait la probabilité du MODÈLE (jamais fiable : gagnants/perdants quasi identiques en probabilité annoncée, ~5 points d'écart). Remplacé par le vrai taux de réussite mesuré (`roi_dashboard.json`, par famille de marché — ex. "Moins de N buts" regroupe 2.5/3.5/4.5), seuil minimum 15 paris avant d'afficher un chiffre (sinon "pas assez de recul"). Libellé clarifié pour dire explicitement que c'est une famille de marchés, pas la ligne exacte recommandée (retour utilisateur : plusieurs matchs différents affichant le même texte donnaient une impression de message générique/suspect — légitime, mais mal formulé).

### 21.6 Purges de cache — fonctions déjà écrites mais jamais appelées, branchées maintenant
`purge_entrees_expirees` (cache_equipes, cache_classement, cache_h2h) et `purge_matchs_joues` (cache_betpawa) existaient depuis des sessions antérieures mais n'étaient appelées nulle part — les fichiers ne faisaient que grossir. Branchées dans `precalcul.py`, isolées dans un `try` (un souci ici ne fait jamais échouer le run). Vérifié : ne change rien au comportement "cache valide → réutilisé, absent/expiré → recherché" (donc ne casse pas le mécanisme "limiter le run au lendemain aux seuls matchs manquants").

### 21.7 `probabilite_modele_ajustee` — jamais réellement implémenté malgré un commentaire l'affirmant
`serialise()` (run_pipeline.py) ne construisait jamais ce champ — le commentaire de script.js affirmant "affiche désormais l'ajustée" était faux depuis son écriture. Conséquence concrète observée en prod : un marché affichait "100.0%" de probabilité à côté d'un EV de 18.4% (incohérence, la vraie proba ajustée cohérente était 74%). Corrigé : `ajuste_probabilite()` réellement appelé dans `serialise()`.

### 21.8 Veto sur échantillon insuffisant — la confiance ne bloquait jamais un GO
Confirmé en prod : Eldense-Majorque (Segunda Division, tous deux ayant changé de division cet été) est sorti en GO avec 1 seul match domicile / 1 seul extérieur. `decision_go_nogo()` avait un commentaire explicite disant que la confiance était "descriptive uniquement, jamais un veto" — corrigé : sous 8 matchs (seuil FAIBLE déjà existant), NO_GO automatique quel que soit l'EV. Testé (6 cas). **Limite non résolue** : ne répare rien pour les équipes venant d'une division non mesurable (Primera RFEF espagnole, etc. — voir situation critique #9).

### 21.9 Deux bugs de correspondance de compétition (scraper_details.py), trouvés en vérifiant les données de justification
Vérification manuelle sur matchendirect (capture d'écran) a confirmé que Giugliano-Sorrente (Italie) est en **Girone C**, alors que le système affichait "Girone B" et utilisait un historique probablement faux (contradiction directe avec la forme réelle affichée par matchendirect) comme preuve de justification pour un GO. Cause : un "c" isolé (venant de "Série C", le palier) suffisait à matcher n'importe quelle section contenant aussi un "c" isolé — y compris une Coupe d'Italie Serie C (compétition différente). **Corrigé, ET un deuxième bug préexistant plus grave découvert en testant le premier** : "Ligue 1"/"Ligue 2" (France) matchaient déjà à tort avant même ce correctif ("1"/"2" étaient dans la liste des mots génériques ignorés). Potentiellement ancien et généralisé (n'importe quel pays avec "Division 1"/"Division 2", "League One"/"League Two"). Corrigé avec une règle explicite (identifiants de groupe/girone/numéro doivent correspondre exactement s'ils sont présents des deux côtés). 12 cas de test, tous passent.

### 21.10 Fichiers livrés cette session (aucun encore vérifié sur un run réel propre)
`scraper_details.py` (18.8 + matchs bruts exposés + correspondance compétition x2), `calculs.py` (GA_REFERENCE_PAR_LIGUE 25 pays + veto échantillon), `adapte_justification.py` (nouveau), `moteur_justification.py` (fourni par Patrick, wiré), `run_pipeline.py` (justification branchée + probabilite_modele_ajustee corrigé), `precalcul.py` (purges de cache branchées), `script.js` + `style.css` (nouveau badge taux réel + messages clarifiés + contraste), `cache_equipes.json` (négatifs nettoyés, ponctuel).

### 21.11 Point en suspens explicitement demandé par Patrick — script d'audit permanent
Proposé, pas encore construit : un script qui vérifie par le calcul (pas par lecture de commentaire) une liste d'affirmations qui ont dû être redécouvertes une à une cette session (K_SHRINKAGE a un effet réel, GA_REFERENCE diffère de 1.35 pour un pays réel, la confiance bloque un GO sous le seuil, les fonctions de purge sont vraiment appelées quelque part, Ligue 1 ≠ Ligue 2, Girone B ≠ Girone C, le moteur de justification retourne du contenu sur un cas réel). À construire en priorité — voir feuille de route ci-dessous.
## ⚠️ SITUATIONS CRITIQUES (ajouts du 06/09/2026, à lire en premier)

10. **`decision_go_nogo()` n'implémentait jamais réellement le veto d'échantillon annoncé "corrigé et testé" en 21.8** — confirmé faux par exécution directe du fichier livré ce jour-là (les paramètres étaient reçus mais jamais lus dans le corps de la fonction). Corrigé pour de vrai le 06/09, revérifié sur un run réel (Troyes-Strasbourg, 1 seul match domicile connu, NO_GO confirmé dans precalcul.json produit).
11. **Bug de nommage sur `GA_REFERENCE_PAR_COMPETITION`** : la clé utilisée était "Challenge League" (anglais) alors que matchendirect affiche "Challenge Ligue" (français) — le lookup ne matchait jamais, retombait silencieusement sur la valeur du pays. Trouvé en vérifiant sur `precalcul.json` d'un vrai run, pas en test isolé — **réflexe à généraliser : toujours tester une clé de dictionnaire contre la vraie chaîne brute produite en prod, jamais une version tapée à la main.**
12. **Famille de bugs "équipe confondue avec sa réserve/jeunes"** trouvée dans 4 fonctions de correspondance de texte différentes (`resolution_betpawa.ratio_ressemblance`, `scraper_details._memes_equipes`, `calculs._memes_equipes_ratio`, `scraper_betpawa._noms_correspondent`) — toutes corrigées avec la même liste de marqueurs (b, ii, castilla, atletic, u19-23, reserve...). **Limite non résolue et acceptée** : deux clubs homonymes mais réellement différents (Independiente Argentine vs Independiente del Valle Équateur) ne sont pas distingués — aucun marqueur textuel fiable ne permet de trancher ce cas-là.
13. **Le repli vers la saison précédente sur matchendirect (`?season=X`) est confirmé NON FIABLE de façon non déterministe**, pas un bug d'URL. Testé sur 4+ équipes jamais consultées avant (Troyes, RC Lens, AJ Auxerre échouent ; Marseille réussit), avec la MÊME méthode exacte à chaque fois. Confirmé définitivement : le menu déroulant du site utilise littéralement cette même URL comme valeur d'option HTML (`<option value="?season=2025%2F2026">`) — donc "cliquer" et "construire l'URL" sont rigoureusement identiques pour le site, aucune piste de contournement ne peut fonctionner. Cause probable : infrastructure serveur (plusieurs instances/répartition de charge), pas corrigible côté client. `scraper_details.recupere_gf_ga_avec_repli()` corrigé pour DÉTECTER cet échec (comparaison avec l'historique de la saison actuelle déjà récupéré) et jeter la tentative plutôt que risquer un double-comptage silencieux — n'améliore pas le taux de réussite du site, mais empêche une corruption des données.
14. **football-data.co.uk** : le format "extra leagues" (`/new/{code}.csv`) fonctionne toujours (revérifié ce jour avec POL/DNK fournis par Patrick, valeurs identiques à celles déjà en prod, 0 ligne incomplète). Le format "principal" (`/mmz4281/{saison}/{code}.csv`), déjà utilisé par le passé pour calibrer `GA_REFERENCE` des grands championnats, **est bloqué depuis ce jour** — page "temporarily unavailable" reproduite deux fois, y compris depuis le téléphone de Patrick (IP probablement bloquée par le site). Ne remet pas en cause les valeurs déjà calculées (saison figée), mais empêche toute récupération fraîche pour le moment.
15. **Flashscore identifié comme source fiable pour le détail domicile/extérieur par équipe** (classements séparés Domicile/Extérieur, par saison, une capture = tout un championnat) — déjà utilisé avec succès pour Suisse (Super Ligue + Challenge Ligue) et Pays-Bas (Eerste Divisie). **Pas encore fait pour les 6 grands championnats** (France, Angleterre, Espagne, Italie, Allemagne, Pays-Bas Eredivisie) — méthode validée, reste à exécuter.
16. **NOUVELLE PRIORITÉ EXPLICITE DE PATRICK pour la prochaine session** : vérifier la véracité des données produites par matchendirect ET des calculs qui les utilisent. Citation directe : *"je ne veux pas utiliser un système qui ment, s'il faut ajouter des contrôles de données pour être sûr de leur fiabilité."* Construire des contrôles de fiabilité des DONNÉES elles-mêmes (pas seulement des tests unitaires sur la logique de calcul, ce que fait déjà `audit_permanent.py`) — à définir concrètement en tout début de la prochaine session, avant toute autre tâche.

## 22. Session du 06/09/2026 — Vérification sur run réel, 5 nouveaux bugs de correspondance, enquête approfondie sur la fiabilité de matchendirect

### 22.1 Premier run complet post-correctifs de la session 21 — vérifié sur données réelles
Run complet lancé par Patrick (1h42m, succès). Audit permanent (57 vérités à ce moment) : 57/57 sur le code. Vérification supplémentaire sur les VRAIES données produites (`precalcul.json`) : le veto d'échantillon (21.8) fonctionne bien en prod (183/639 matchs vetotés), mais a révélé le bug de nommage "Challenge League"/"Challenge Ligue" (situation critique #11) — corrigé et revérifié sur la chaîne brute exacte produite par le run (avec le saut de ligne réel).

### 22.2 Diagnostic demandé par Patrick : "aucun grand championnat représenté" — constat partiellement erroné, cause légitime
Vérifié sur les vraies données : LaLiga et Serie A avaient chacun un GO ce jour-là (Patrick ne les avait pas vus, triés alphabétiquement après Albanie/Andorre/Chili). Pour Ligue 1/Bundesliga/Premier League/Eredivisie, cause dominante = marchés déjà efficients (aucun EV≥2% trouvé face aux cotes, comportement normal), pas un bug. Une minorité de cas (ex. Troyes) relève du veto d'échantillon (équipe promue, situation critique #9).

### 22.3 Audit des scraping matchendirect sur les vrais logs du run — 94/639 matchs incomplets, cause majoritaire identifiée
Analyse des logs réels (pas une supposition) : 76 matchs sans aucune donnée (ni saison actuelle ni précédente), cause dominante = échec du repli saison précédente (situation critique #13 ci-dessus), touchant indifféremment petits et grands championnats en ce début de saison.

### 22.4 Enquête approfondie sur le sélecteur de saison matchendirect (plusieurs allers-retours)
- Testé `?season=X` directement (web_fetch) sur plusieurs équipes fraîches : résultat incohérent (Marseille réussit, Troyes/RC Lens/Auxerre échouent).
- Script Playwright (`diagnostic_selecteur_saison.py`) construit pour observer le HTML réel du sélecteur : a révélé un `<select>` HTML natif avec `<option value="?season=2025%2F2026">` — confirme que l'URL utilisée par le code est EXACTEMENT celle du site, pas une invention.
- Idée de Patrick testée (naviguer réellement page ligue → équipe → saison au lieu de construire l'URL) : `diagnostic_navigation_reelle.py` construit, mais la découverte du `<select>` a rendu le test superflu — les deux méthodes convergent vers la même URL, donc le même aléa.
- Conclusion définitive : aléa serveur non déterministe, ni corrigible ni contournable côté client. Voir correctif situation critique #13.

### 22.5 Rattrapage des ~333 matchs mal datés (point 6 de l'ancienne feuille de route) — clos
`corrige_dates_historique.py` construit et exécuté via GitHub Actions (dry-run puis réel) : 96/96 matchs candidats (verdict_global présent + score manquant, datés 24-30/08) retrouvés et corrigés, décalage +1 jour confirmé pour tous, cohérent avec le bug fuseau horaire déjà connu.

### 22.6 GA_REFERENCE par division — Suisse D1 revérifiée, Suisse D2 et Pays-Bas D2 ajoutées
Suisse Super Ligue (D1) : écart trouvé entre la valeur en prod (1.6447, 750 buts/228 matchs) et une source Wikipedia (691 buts) — Wikipedia s'est révélé faux après vérification sur la vraie table Flashscore (644 buts/198 matchs = phase régulière, écart jugé non significatif par Patrick). Valeur mise à jour : 1.6263. Suisse Challenge Ligue et Pays-Bas Eerste Divisie ajoutées à `GA_REFERENCE_PAR_COMPETITION`, calculées sur tables Flashscore complètes fournies par Patrick, GF=GA vérifié à chaque fois.

### 22.7 Fichiers livrés cette session (tous testés avant livraison, vérifiés sur données réelles quand possible)
`calculs.py` (veto go_nogo réellement implémenté, GA_REFERENCE_PAR_COMPETITION Suisse D1/D2 + Pays-Bas D2, clé "Challenge Ligue" corrigée), `scraper_details.py` (`_memes_equipes` + `trouve_equipe_dans_classement` corrigés réserve/jeunes, `recupere_gf_ga_avec_repli` détecte et jette les replis saison inefficaces), `scraper_betpawa.py` (`_noms_correspondent` corrigé réserve/jeunes), `run_pipeline.py` (transmission de `competition` à `calcule_lambda`), `audit_permanent.py` (58 vérités), `corrige_dates_historique.py` (nouveau, ponctuel), scripts de diagnostic ponctuels (`diagnostic_selecteur_saison.py`, `diagnostic_fiabilite_saison.py`, `diagnostic_navigation_reelle.py`) + workflows GitHub Actions associés.

### 22.8 Feuille de route à l'issue de cette session
- ✅ Script d'audit permanent, vérification sur données réelles, GA_REFERENCE par division, audit des fonctions de correspondance, rattrapage des dates
- ⬜ Point 4 (équipes ayant changé de division sans donnée de remplacement) — décision produit toujours en attente
- ⬜ Point 7 (recalibrage K_SHRINKAGE/SEUIL_EV_MIN) — toujours après stabilisation complète
- ⬜ Détail domicile/extérieur par équipe pour les 6 grands championnats via Flashscore — méthode validée, pas exécutée
- 🆕 **PRIORITÉ SESSION SUIVANTE (demande explicite de Patrick)** : construire des contrôles de fiabilité sur les DONNÉES elles-mêmes (matchendirect et calculs en aval), pas seulement sur la logique — voir situation critique #16.

## ⚠️ SITUATIONS CRITIQUES (ajouts du 07/09/2026, à lire en premier)

17. **La correction du point #41 (orientation H2H par équipe dans `adapte_justification.py`) est délibérément incomplète** — décision explicite de Patrick de garder uniquement l'orientation domicile/extérieur (cohérente avec `calculs.calcule_ratio_h2h()`), pas le problème plus profond découvert en creusant. Pour "Over/Under par équipe" (ex. "Plus de 1.5 buts - Domicile"), `_preuve_h2h()` réduit le marché à sa forme symétrique ("Plus de 1.5 buts") avant de l'évaluer — cette forme symétrique compte le TOTAL des deux équipes, pas les buts propres de l'équipe visée. Preuve directe : `verifie_pari("Plus de 1.5 buts - Domicile", 0, 2)` = False (l'équipe visée n'a rien marqué), mais `verifie_pari("Plus de 1.5 buts", 0, 2)` = True (le total dépasse 1.5). **Conséquence concrète : l'orientation par équipe n'a AUCUN effet numérique sur le pourcentage affiché pour ce type de marché** — seul le champ d'attribution interne `equipe=` change. Pour "Cage inviolée"/"Sans marquer", aucune preuve H2H n'est produite du tout, avec ou sans ce correctif (le nom de marché sans suffixe — "Cage inviolée", "Sans marquer" — n'est reconnu par aucune règle de `verifie_pari()`, `resultat` vaut toujours `None`). **Ne pas considérer #41 comme visuellement résolu.** Architecture déjà réfléchie pour le vrai correctif si Patrick redonne le feu vert : construire l'historique H2H réorienté (buts_marques/buts_encaisses du point de vue de l'équipe visée, déjà fait pour l'orientation) puis réutiliser les fonctions de comptage PAR ÉQUIPE déjà existantes dans `construit_preuves()` (celles utilisées sur l'historique réel, pas `verifie_pari` sur la forme symétrique) au lieu de la forme symétrique.

18. **`requirements.txt` existe (créé le 06/09, point #34) mais n'est pas branché à `pipeline.yml`** — le workflow garde sa propre ligne `pip install requests beautifulsoup4 pandas lxml playwright`, indépendante de ce fichier. Les deux peuvent diverger avec le temps si l'un est modifié sans l'autre. `lxml` est un résidu déjà constaté inutile (BeautifulSoup utilise `"html.parser"` partout dans le code, jamais lxml) — jamais retiré ni de l'un ni de l'autre, décision produit à prendre avec Patrick.

19. **`betpawa_urls.txt` est un fichier orphelin** depuis la suppression du flux manuel de `scraper_betpawa.py` (#36, 06/09 : `lit_urls()`, `traite_url()`, `main()`, `cherche_url_matchendirect_auto()`, `genere_match_id()` tous supprimés, plus aucun code ne le lit). Laissé sur le disque à la demande implicite de Patrick (fichier de données, pas supprimé sans confirmation explicite). Ne pas être surpris de le trouver inerte dans le dépôt.

20. **Suite du point #16 (fiabilité des données matchendirect) — reformulé plus précisément par Patrick le 07/09/2026** : la question n'est plus seulement "les données sont-elles fiables" mais concrètement *"pourquoi certains matchs n'ont pas pu trouver des données pourtant disponibles"* — c'est-à-dire des FAUX NÉGATIFS de `scraper_details.py` : des cas où la donnée existe réellement sur matchendirect.fr mais où le code échoue à la trouver/parser. Le run réel du 07/09 (#104, logs disponibles) contient des centaines de lignes `[DIAG 18.8]` qui sont autant de candidats concrets à vérifier un par un contre le vrai site — trois motifs reviennent constamment et sont à investiguer en priorité : (a) `"ancre INTROUVABLE pour compétition cible"` (le nom de compétition scrapé ne correspond à aucun texte de la page), (b) `"tableau #1 après l'ancre ignoré (aucun lien /live-score/ ou /foot-score/ dedans)"` (heuristique de sélection de tableau qui rejette peut-être le bon tableau), (c) `"paramètre de saison IGNORÉ par le site"` (déjà expliqué et accepté comme non-corrigible côté client par la situation critique #13 — à ne pas re-creuser sans nouvelle preuve). Commencer par (a) et (b), pas par (c) qui est déjà tranché.

## 23. Session du 06-07/09/2026 — Point #9 enfin codé, Groupes 5/7/8/9 de l'audit traités, premier run réel post-correctifs vérifié

### 23.1 Point #9 (P0, jamais codé malgré sa gravité) — corrigé et vérifié en conditions réelles
Preuve initiale : 19 `match_id` dupliqués sur 2 dates dans `matchs_semaine.json`. Diagnostic affiné par rapport à l'hypothèse de l'audit externe (qui suggérait une garde URL/date façon "demain") : le recouvrement mesuré n'était que de 6-7% des matchs de chaque jour, pas 100% — pas une redirection serveur, mais matchendirect.fr qui liste réellement les matchs de 00h00-02h30 heure française sur les deux pages calendaires adjacentes. `deduplique_par_match_id()` ajoutée dans `scraper_semaine.py`, garde la première occurrence (date la plus proche). **Vérifié en conditions réelles le 07/09 (run #104) : 60 doublons détectés et écartés au premier passage.** Conséquence trouvée en creusant : `scraper_betpawa.cherche_url_matchendirect_auto()` (aujourd'hui supprimée, voir 23.4) tombait à tort en "AMBIGU" sur ces matchs.

### 23.2 Groupe 5 — résolution Betpawa (#6, #20)
- **#6** : le titre de la page Betpawa était récupéré puis jeté, jamais revérifié contre domicile/exterieur avant d'extraire les cotes. Risque réel confirmé par le code : `meilleur_parsing()`/les 3 parseurs sont génériques (1X2/BTTS/Over-Under ne dépendent d'aucun nom d'équipe dans le texte capturé) — une mauvaise URL renvoie donc de VRAIES cotes, juste pour le mauvais match. Corrigé dans `resolution_betpawa_precalcul.py` : `extrait_meta(titre)` comparé via `_noms_correspondent()` ; mismatch → cotes non extraites + cache invalidé si l'entrée venait d'un cache hit (`cache_betpawa.invalide_entree()`, nouvelle fonction). **Vérifié en conditions réelles le 07/09 : 44 mismatches détectés sur 303 tentatives.**
- **#20** : `meilleur_parsing()` choisissait le parseur avec le plus de marchés BRUTS, pas le plus plausible. `_marches_plausibles()` ajoutée (écarte un marché entier si une cote ≤ 1.0 y figure, mathématiquement impossible). Tourne à chaque résolution, sans régression observée.

### 23.3 Groupe 7 — sécurité/panier (#24, #25, #26, #27)
- **#24** : `panier_id` persisté en localStorage sur un envoi accepté (`panier.js`), `script.js` filtre `resultats_pipeline` par ce `panier_id` en priorité (repli sur l'ancien comportement si absent).
- **#25** : vérification "pas déjà en_cours" + rate-limit (3 paniers/10 min) dans `netlify/functions/trigger.js`, via Supabase avec le jeton utilisateur (RLS). Limite connue et documentée dans le code : `workflow_dispatch` est asynchrone, une double soumission très rapprochée peut passer le contrôle "en_cours" avant qu'il soit posé — le rate-limit couvre ce résidu.
- **#26** : taille max de panier (`TAILLE_MAX_PANIER = 50`, valeur choisie par défaut, jamais confirmée avec Patrick — à ajuster si besoin).
- **#27** : `panier.js` converti en construction DOM (`textContent`). `script.js` : écart assumé par rapport à la formulation littérale de l'audit — échappement (`echappeHtml()`) plutôt que reconstruction DOM complète (le fichier est un arbre de ~10 fonctions imbriquées qui se passent du HTML en chaîne, une conversion complète aurait été un chantier bien plus lourd que "peu coûteux"). Même garantie de sécurité obtenue, risque de régression moindre.

### 23.4 Groupe 8 — qualité de données (#4, #30, #31, #41)
- **#4** : le filtre réserve/jeunes ne regardait que le nom de la compétition. `est_equipe_jeune_ou_reserve()` ajoutée dans `precalcul.py`, vérifie aussi le nom d'équipe (mêmes marqueurs que les 3 autres copies déjà existantes dans le dépôt). **Vérifié en conditions réelles le 07/09 : 58 matchs supplémentaires écartés.**
- **#30/#31** : `TTL_SANS_HISTORIQUE_HEURES` (cache_equipes.py) et `TTL_HEURES` (cache_h2h.py) réduits de 7 jours à **96h (4 jours), décision explicite de Patrick** (ma proposition initiale pour #30 était 48h, refusée).
- **#41** : voir situation critique #17 ci-dessus — correctif d'orientation seul, délibérément incomplet, décision explicite de Patrick.

### 23.5 Groupe 9 — dette technique (#34, #36, #37)
- **#34** : `requirements.txt` créé (voir situation critique #18, pas encore branché à `pipeline.yml`).
- **#36** : 4 fichiers morts supprimés (`selection.html`, `selection.js`, `payload_builder.py`, `matchs_selectionnes.json`) + code mort trouvé en creusant #6 supprimé dans `scraper_betpawa.py` (`traite_url`, `main()`, `cherche_url_matchendirect_auto()`, `genere_match_id()`, `lit_urls()`, `lit_panier()`, `ecrit_panier()`, `slug()` + 5 constantes `FICHIER_*` devenues inutiles). Confirmé mort par recherche exhaustive avant suppression (aucun appelant actif). Docstring de tête de `scraper_betpawa.py` réécrite pour refléter ce que le fichier fait réellement aujourd'hui (bibliothèque de correspondance/parsing, plus un flux autonome).
- **#37** : docstring de `resolution_betpawa_precalcul.py` corrigée — affirmait "JAMAIS EXÉCUTÉ EN CONDITIONS RÉELLES", alors que `cache_betpawa.json` contenait déjà 380 entrées réelles au moment de la correction.
- **Non traités, restent ouverts** : #38 (migrer `audit_permanent.py` vers pytest — gros chantier, pas urgent), #39 (~17-18 Mo de fichiers générés versionnés dans Git — décision produit à prendre, ces fichiers sont la seule persistance du pipeline aujourd'hui, les retirer du suivi Git casserait le mécanisme actuel), #33 (cosmétique, `date.today()` résiduel dans `scraper_details.py`).

### 23.6 Premier run réel post-correctifs (#104, 07/09/2026) — tous les correctifs de cette session vérifiés en conditions réelles
46 minutes, succès complet, commit+push OK. **~45 minutes concentrées dans l'étape `precalcul.py`** — pas une régression de cette session, cause identifiée : scraping matchendirect entièrement séquentiel (`scraper_details.fetch_html`, aucune parallélisation), amplifié par le repli saison précédente (situation critique #13) qui déclenche souvent 2 requêtes par équipe au lieu d'une. Non traité, à optimiser un jour si Patrick le souhaite (paralléliser, ou limiter le repli saison). Résultats du run : 303 matchs analysés (258 READY, 45 PARTIAL), Betpawa 103/303 avec cotes réelles, 545 paris évalués au total (`roi_dashboard.json`) dont 348 gagnés (63.9%), ROI -7.7%.

### 23.7 `AUDIT_40_POINTS.md` — largement consommé, ne plus le traiter comme document vivant séparé
Sur les 8 points du Groupe 8 et les 5 du Groupe 9, seuls #33/#38/#39 restent ouverts (listés en 23.5 ci-dessus, désormais suivis ici). Les Groupes 5 et 7 (7 points) sont clos. Ne pas relire `AUDIT_40_POINTS.md` en pensant qu'il reste des points non trackés ici — sa raison d'être (feuille de route P0/P1/P2 de l'audit externe des 40 points) est épuisée, ce fichier `TRANSITION.md` fait maintenant autorité seul.

### 23.8 Feuille de route à l'issue de cette session
- ✅ Point #9 codé et vérifié en réel, Groupes 5/7/8/9 traités (sauf #33/#38/#39, restent ouverts)
- ⬜ #33, #38, #39 — non urgents, aucun ordre imposé
- ⬜ Correctif complet de #41 (voir situation critique #17) — en attente d'un feu vert de Patrick, portée déjà réfléchie
- ⬜ Brancher `requirements.txt` dans `pipeline.yml` (situation critique #18) et trancher le sort de `lxml`
- ⬜ Décider du sort de `betpawa_urls.txt` (situation critique #19)
- 🆕 **PRIORITÉ SESSION SUIVANTE (demande explicite de Patrick, reformulation précise de la priorité déjà posée en situation critique #16)** : analyser pourquoi certains matchs n'ont pas trouvé de données pourtant disponibles sur matchendirect — voir situation critique #20 pour la liste des motifs `[DIAG 18.8]` à vérifier en premier et les logs concrets du run #104 déjà disponibles comme point de départ.

## ⚠️ SITUATIONS CRITIQUES (ajouts du 07/09/2026 soir, à lire en premier)

24. **Le moteur V0 (`moteur_v0.py`) tourne en observation depuis le 07/09, mais AUCUN fichier de cette session n'est encore poussé sur le dépôt distant.** Patrick a explicitement refusé de remplacer les fichiers tant que le problème de calibration (voir 25.5 ci-dessous) n'est pas mieux compris — il doit d'abord soumettre le problème à un autre modèle pour un second avis. **Ne pas supposer que `moteur_v0.py`/`brancher_moteur_v0.py`/`verifie_historique_v0.py`/`pipeline.yml` modifié sont en place sur le dépôt réel.** Le seul fichier réellement exécuté en production à ce jour est la toute première version de `moteur_v0.py` (celle avec le clamp de référence de ligue bogué, voir 25.2) — c'est elle qui a produit `historique_v0.jsonl` (306 lignes, un seul run, le 07/09 après-midi). Vérifier l'état réel du dépôt avant de continuer, ne pas se fier à cette session seule.

25. **Le vrai sujet non résolu de fin de session — biais de sous-estimation des buts, cause non tranchée.** Sur 171 matchs réels uniques reconstruits (voir 25.4 — **corrigé le 07/09 tard : les 272 lignes archivées contenaient 101 doublons, un même match listé sur plusieurs jours d'archive ; le dédoublonnage par `match_id` ramène l'échantillon réel à 171**), λ (peu importe la formule, ancienne ou V0) sous-estime le nombre de buts réel d'environ 0,44-0,47 but/match dans les deux cas — **l'écart entre "ancien moteur" et "V0 pure" annoncé initialement (15,7% vs 18,8%) ne tient plus une fois dédoublonné : les deux sont maintenant dans la marge de bruit l'un de l'autre.** Ce qui reste vrai : la sous-estimation elle-même est réelle et substantielle, et n'est toujours pas expliquée par le mécanisme de référence de ligue (retiré, le biais persiste à l'identique). Un facteur correctif (`CORRECTION_BUTS_V0 = 1.155`) a été calibré par validation croisée temporelle (2 jours, dans les deux sens) et intégré au code local, mais **jamais poussé sur le dépôt** (voir situation critique #24). La question non tranchée : ce biais est-il structurel (propriété intrinsèque d'une moyenne mobile sur N derniers matchs) ou conjoncturel (fenêtre d'observation = tout début de saison, échantillon encore pollué par la saison précédente) ? Un indice faible (l'écart diminue entre le 29 et le 30/08) penche vers "conjoncturel" sans le prouver. Patrick a soumis ce problème à ChatGPT (voir 26.1) puis a décidé de remplacer entièrement l'approche plutôt que de corriger V0 — **voir section 26, nouvelle priorité.**

## 24. Session du 07/09/2026 (après-midi/soir) — Naissance du moteur V0, découverte et correction de 4 bugs réels via observation sur données réelles

### 24.1 Contexte et décision de fond
Après la session du 07/09 matin sur les faux négatifs de `scraper_details.py` (voir situation critique #20, toujours ouverte, non retouchée cette session), Patrick a soulevé une question plus profonde en examinant une justification affichée (Elche-Real Sociedad) : le système diagnostique-t-il vraiment le meilleur pronostic, ou "fait-il semblant d'être efficace" ? Décision : reconstruire un moteur V0 séparé, minimal, avec le moins de paramètres possible, chacun explicitement déclaré — plutôt que de continuer à réparer `calculs.py`/`adapte_justification.py` pièce par pièce. Le moteur existant n'a pas été touché et continue de tourner tel quel.

### 24.2 Bug trouvé dans `adapte_justification.py` en marge de cette réflexion, jamais corrigé
En vérifiant à la main la justification H2H d'Elche-Real Sociedad, découverte que pour les marchés **1X2, Double chance, Handicap, Score exact**, `_preuve_h2h()` retombe dans le traitement "symétrique" (car `equipe_cible_h2h` reste `None` pour ces marchés, décision du 06/09, situation critique #17) — ce qui mélange les deux sens de la rivalité H2H sans distinction, gonflant ou déformant le pourcentage affiché. Concrètement vérifié : le 15/20 (75%) affiché pour "Double chance - 1X" d'Elche était en réalité 6/10 (60%) pour Elche à domicile et 9/10 (90%) pour Real Sociedad à domicile, moyennés à tort. **N'affecte que l'affichage** (le calcul réel utilisé pour la mise, `calcule_ratio_h2h()` dans `calculs.py`, est déjà correctement orienté par équipe) — pas de conséquence financière, mais reste un bug non corrigé. Portée : `1X2 - 1/2` et `Double chance - 1X/X2` sont réellement affectés ; `1X2 - X`/`Double chance - 12` sont symétriques par nature donc non affectés ; Handicap n'affiche jamais de preuve H2H (accident d'un autre mécanisme, le suffixe stripping bloque tout) ; Score exact affecté en théorie mais rarement affiché en pratique.

### 24.3 Conception de la V0 — invariants figés avec Patrick
Après plusieurs itérations (voir l'échange complet si besoin de retracer le raisonnement), tranché ainsi :
- `N_MIN = 8` — veto dur, sample size.
- Un seul estimateur : Poisson, Dixon-Coles désactivé (`rho=0`, implémentation locale indépendante de `calculs.matrice_poisson_dixon_coles` qui n'expose pas `rho` en paramètre).
- Empirique = contrôle descriptif uniquement (jamais mélangé au calcul de probabilité), et restreint aux marchés SYMÉTRIQUES seulement (voir 24.5, bug trouvé).
- λ = moyenne brute (attaque propre + défense adverse)/2. Référence de ligue : appliquée SEULEMENT si réellement mesurée (jamais le `default`=1.35), sinon neutre — **puis totalement retirée en cours de session** (voir 24.4).
- Aucun seuil de probabilité minimale. Aucune règle de divergence avec le marché en veto (loggée uniquement). Cohérence mathématique = veto structurel sans coefficient. Plausibilité/intégrité de λ = veto (bornes 0.1-6.0, séparées explicitement des paramètres "à calibrer").
- `EV_MIN = 0.05`, explicitement provisoire. Dédoublonnage par famille de marché (un seul candidat retenu par famille : total_buts, buts_domicile, buts_exterieur, resultat, handicap ; BTTS/pair-impair/cage inviolée/sans but/score exact restent indépendants).
- `STAKE_V0 = 0.01` fixe, jamais Kelly, appliquée seulement après sélection.
- Journalisation de TOUS les marchés évalués, GO comme NO_GO comme NO_BET, dès le premier jour (corrige le plafond d'échantillon de 63 paris qui limitait la calibration K_SHRINKAGE du moteur existant).

### 24.4 Bug #1 trouvé lors de l'audit ligne par ligne (demandé explicitement par Patrick avant tout branchement) : `BORNE_MODIFIER_DEFENSE`
Une constante `(0.5, 1.5)` avait été empruntée à l'ancien moteur (`BORNE_MIN/MAX_DEFENSE`, réellement 0.55/1.60 — **valeurs même mal recopiées**) sans jamais être soumise à validation, en violation directe du principe "N_MIN, EV_MIN, STAKE — c'est tout, rien d'autre à compter". Retirée entièrement au moment de l'audit. **Mais retirer le clamp sans le remplacer a eu un effet mesuré, découvert seulement après le premier run réel** (voir 24.6) : le modificateur de référence de ligue, non borné, pouvait s'emballer même avec une référence réellement mesurée.

### 24.5 Bug #2 trouvé au même audit : `controle_empirique_v0` évaluait à tort des marchés asymétriques
`verifie_pari(marche, buts_marques, buts_encaisses)` était appelé pour TOUS les marchés, alors que `buts_marques`/`buts_encaisses` sont déjà réorientés du point de vue de l'équipe (pas les positions réelles domicile/extérieur qu'attend `verifie_pari`). Correct pour les marchés symétriques (BTTS, Total buts, Pair/Impair) ; faux pour 1X2, Double chance, Handicap, "- Domicile/Extérieur", Cage inviolée, Score exact — même classe de bug que #17/24.2, réintroduite par erreur puis retrouvée le même jour. Corrigé : restreint aux marchés symétriques uniquement (`_MARCHES_SYMETRIQUES_EMPIRIQUE`), `None` sinon.

### 24.6 Branchement réel — 2 bugs supplémentaires trouvés en le faisant tourner
- **Bug #3** : `brancher_moteur_v0.py` (script adaptateur, mode observation uniquement, ne touche à aucun fichier de décision du pipeline existant) importait `recupere_gf_ga_avec_repli` directement depuis `scraper_details.py`, contournant le cache que `precalcul.py` branche par monkey-patch sur `run_pipeline.py`. Résultat : re-scraping complet à chaque run au lieu de réutiliser `cache_equipes.json`. Corrigé : appel direct à `cache_equipes.recupere_gf_ga_avec_cache`.
- **Bug #4** : la source de la liste de matchs utilisait `run_pipeline.normalise_panier(panier.json, ...)`, qui n'a de sens que pour le canal Supabase manuel — vide/périmé sur un run automatique planifié. Corrigé : utilise `precalcul.charge_matchs_fenetre()`, la vraie fonction (déjà testée) qui construit la fenêtre réelle après tous les filtres.
- Étape ajoutée à `pipeline.yml` ("Moteur V0"), placée après le pré-calcul (bénéficie du cache réchauffé), `continue-on-error: true`, ne modifie/ne bloque jamais le pipeline existant. `historique_v0.jsonl` ajouté à la liste des fichiers commités (sinon perdu, runner éphémère).
- **`verifie_historique_v0.py` créé** (nouveau) : remplit `resultat_reel` dans `historique_v0.jsonl` une fois les matchs joués, réutilisant tel quel le mécanisme déjà testé de `verification_resultats.py` (`trouve_score`, `parse_matches`). Sans lui, `resultat_reel` restait `null` indéfiniment — la V0 n'avait aucun moyen de vérifier ses propres prédictions. Ajouté aussi à `pipeline.yml`, juste après l'étape équivalente existante. **Nécessite que `brancher_moteur_v0.py` journalise le champ `date` du match** (ajouté au `match_info`) — sans lui, impossible de savoir quand vérifier.

### 24.7 Premier run réel (306 matchs, un seul run à ce jour) — analyse
- 46 GO, 113 NO_GO, 147 NO_BET (dont 103 échantillon insuffisant N<8, 40 absence réelle de matchs joués cette saison/précédente — motif déjà identifié situation critique #20). 0 erreur technique.
- 69% des matchs traités (110/159) sans aucune cote sur aucun marché — probablement des compétitions trop mineures pour Bet365/matchendirect (Egypte D2, Grèce D2 vus dans l'échantillon), pas vérifié en direct, à surveiller.
- **EV moyen des sélections GO : 53,6%, maximum 482%** — signal d'alerte immédiat. Cause tracée exactement au bug #1 (24.4) : cas réel Al Khaleej-Al Riyadh (Arabie Saoudite, référence réellement mesurée 1.5049), modificateur observé 2.19 (jamais borné), λ_domicile poussé à 5.81 (juste sous le plafond 6.0, jamais intercepté), probabilité de marché absurde (80.8% pour "Plus de 4.5 buts"), EV affiché 482%.
- **Décision prise en conséquence : retrait NET de l'ajustement par référence de ligue**, pas un nouveau clamp (qui aurait juste réintroduit une constante à deviner). λ = moyenne brute stricte. `get_reference_verifiee()` conservée mais purement informative (`reference_disponible` loggé, jamais appliqué). Rejoué sur les 306 matchs sans re-scraper (à partir des `lambda_*_brut` déjà loggés) : EV moyen tombé à 31,3%, max à 163% — net progrès, honnêtement incomplet (résidu attribué à l'absence de shrinkage sur petit échantillon, déjà accepté comme limite de conception V0, pas un nouveau bug).

### 24.8 Simulation sur données déjà archivées (`historique_pronostics.json`, ancien moteur, 12 jours) — sur demande explicite de Patrick, pour arrêter de deviner
Méthode : reconstruction EXACTE (inversion mathématique des formules `shrink_vers_reference`/modificateur défensif de l'ancien moteur, mêmes constantes) des GF/GA bruts par équipe à partir de l'audit archivé — pas une approximation.
**CORRIGÉ après coup (en préparant l'export CSV pour ChatGPT, voir 26.1) : le chiffre initial de "272 matchs" comptait certains matchs jusqu'à 2 fois — 101 lignes étaient des doublons (même `match_id` archivé sous plusieurs jours différents, ex. listé "demain" un jour puis "aujourd'hui" le lendemain). Dédoublonné par `match_id` : 171 matchs uniques réels.** Les chiffres ci-dessous intègrent cette correction.
- **Calibration par tranche de probabilité (tous marchés confondus, sur données non dédoublonnées à l'origine — à refaire proprement sur les 171 uniques si besoin de précision)** : 1X2/Double chance déjà bien calibrés (±3 points). BTTS et TOUS les Over/Under systématiquement sous-estimés (+7 à +18,5 points selon la ligne). Extrêmes (0-20%, 90-100%) trop confiants dans les deux sens. Direction du signal jugée fiable malgré le doublon (un doublon garde la même direction d'erreur, donc ne change pas le sens de la conclusion — seule l'ampleur exacte est à considérer avec prudence).
- **Cause : λ sous-estime le nombre de buts réel d'environ +0,44 but/match (ancien moteur) et +0,47 but/match (formule V0 pure, sans référence), sur 171 matchs uniques** — les deux chiffres sont proches, dans la marge de bruit l'un de l'autre (l'écart net annoncé initialement, 15,7% vs 18,8%, ne tenait pas compte des doublons et ne doit plus être cité). Ce qui reste solide : la sous-estimation n'est PAS causée par le shrinkage/la référence de ligue (l'hypothèse initiale), puisqu'elle persiste à l'identique une fois ce mécanisme totalement retiré. Cause réelle non tranchée — voir situation critique #25.
- **Backtest réel sur cotes réellement archivées** : marché "1X2 - 1" → 43 sélections V0 GO (sur données non dédoublonnées pour ce backtest précis — nombre exact de matchs uniques concernés non revérifié), 15 gagnées (34,9%), P&L +9,32% (mise fixe 1%) — positif mais 43 paris ne prouvent rien statistiquement, et l'EV moyen affiché (40,6%) reste anormalement élevé (bruit résiduel petit échantillon, pas un edge confirmé).
- **`CORRECTION_BUTS_V0 = 1.155` calibrée par validation croisée temporelle stricte** (train 29/08 n=145 → test 30/08 n=67 jamais vu : erreur ramenée de +0.330 à -0.170 ; et l'inverse : erreur ramenée à +0.174) — les deux facteurs indépendants (1.173 et 1.114) se recoupent à moins de 0.03 l'un de l'autre. Intégrée au code (`moteur_v0.py`, appliquée au λ final, documentée comme calibrée-mais-provisoire). **Backtestée** : neutre sur 1X2 (34,9%→34,0%, attendu — ne cible pas ce marché), légère amélioration non concluante sur buts/BTTS (60,0%→63,2% sur seulement 15-19 paris). **Pas encore poussée sur le dépôt distant** — voir situation critique #24. **Statut à l'issue de la session : probablement obsolète, voir section 26 — Patrick penche pour un remplacement complet de l'approche plutôt qu'un correctif de ce type.**

### 24.9 Fichiers de cette session (LOCAUX UNIQUEMENT, jamais poussés — voir situation critique #24)
`moteur_v0.py` (nouveau), `audit_permanent.py` (14 nouvelles vérités moteur V0, ajouts uniquement, aucune régression), `brancher_moteur_v0.py` (nouveau, adaptateur mince), `verifie_historique_v0.py` (nouveau), `.github/workflows/pipeline.yml` (2 étapes ajoutées : "Moteur V0" et "Vérifier les résultats réels pour le moteur V0"). `historique_v0.jsonl` existe sur le dépôt distant (généré par l'unique run réel effectué avec la toute première version bogée, voir situation critique #24) mais ne reflète PAS l'état actuel du code local.

### 24.10 Feuille de route à l'issue de cette session
- ⬜ **PRIORITÉ ABSOLUE SESSION SUIVANTE** : lire la réponse que Patrick va rapporter d'un autre modèle sur le problème posé en situation critique #25 (biais structurel vs conjoncturel), avant toute décision sur `CORRECTION_BUTS_V0`.
- ⬜ Une fois tranché : pousser les fichiers de 24.9 sur le dépôt (actuellement locaux uniquement).
- ⬜ Laisser tourner plusieurs jours/semaines une fois poussé, pour que `verifie_historique_v0.py` accumule de vrais résultats V0 (pas reconstruits/inversés depuis l'ancien moteur) — refaire alors la même analyse de calibration directement sur les données V0.
- ⬜ Bug #24.2 (`adapte_justification.py`, orientation H2H 1X2/Double chance) reste non corrigé, cosmétique, pas urgent.
- ⬜ Situation critique #20 (faux négatifs `scraper_details.py`) reste ouverte, non retouchée cette session.
- ⬜ #33, #38, #39 (situation critique 22.8/23.8) toujours ouverts, non urgents.

## ⚠️ SITUATION CRITIQUE (ajout du 07/09/2026, fin de soirée — remplace la priorité de la section 24.10)

26. **Patrick a décidé de ne PAS continuer à corriger le moteur V0 — il veut le remplacer entièrement par une nouvelle spécification, à adapter au système existant.** Cette spécification EST la réponse produite par ChatGPT à la consultation sur le biais de sous-estimation des buts (situation critique #25) — pas un document indépendant, voir 26.1. La feuille de route de la section 24.10 (pousser les fichiers V0, puis laisser tourner) est **suspendue**, pas annulée : les découvertes de la session V0 (bugs trouvés, méthode de journalisation, etc.) restent valables et potentiellement réutilisables, mais l'action immédiate n'est plus "corriger V0", c'est "évaluer et implémenter la nouvelle spécification". Voir section 26 ci-dessous pour le contenu complet.

## 26. Session du 07/09/2026 (fin de soirée) — Consultation externe et pivot vers une nouvelle spécification complète

### 26.1 Consultation ChatGPT sur le biais de sous-estimation des buts — ET la spécification de 26.2 EST sa réponse
Avant de trancher, Patrick a soumis le problème de calibration (situation critique #25) à ChatGPT, avec deux fichiers CSV construits pour l'occasion :
- `matchs_etude_v0.csv` — 171 matchs uniques (dédoublonnés par `match_id`), avec λ ancien moteur, λ V0 brut (avant correctif), et buts réels.
- `paris_backtest_v0.csv` — 189 paris avec cote réelle, probabilité V0, EV, résultat réel.
**Ces deux fichiers ont été livrés à Patrick mais ne sont PAS dans le dépôt** — à reconstruire si besoin (méthode de reconstruction documentée en 24.8, code non sauvegardé dans un fichier du dépôt, seulement exécuté en session).

**IMPORTANT, précisé par Patrick après coup : la spécification décrite en 26.2 n'est PAS un document séparé — c'est la réponse que ChatGPT a produite à cette consultation.** Elle ne répond pas frontalement à la question méthodologique posée ("comment distinguer statistiquement un biais structurel d'un artefact conjoncturel avec seulement 2-3 semaines de données") — elle la contourne architecturalement : fenêtre strictement limitée à la saison actuelle (jamais de mélange de saisons, donc plus besoin de trancher si le mélange était la cause), et interdiction explicite d'un facteur correctif permanent sans validation walk-forward reproductible sur plusieurs périodes. À traiter comme LA proposition de ChatGPT en réponse au problème posé, pas comme une spec indépendante à évaluer sur son seul mérite technique.

### 26.2 Nouvelle spécification complète — réponse de ChatGPT (voir 26.1)
Document : `Spécification_fonctionnelle_finale___Moteur_statistique_de_sélection_de_pronostics_football.md` (fourni en pièce jointe par Patrick, pas encore dans le dépôt — **à redemander en début de session suivante si absent du contexte**). Décision de Patrick : remplacer entièrement le moteur V0 par cette spécification, adaptée au système existant. Pas encore d'implémentation — feu vert donné pour traiter ça "dans l'autre fenêtre", c'est-à-dire la prochaine session.

### 26.3 Contenu de la spécification — résumé pour ne pas avoir à la relire intégralement, mais LA RELIRE QUAND MÊME avant d'implémenter quoi que ce soit
Philosophie : très proche de celle de la V0 (pas de coefficient arbitraire, séparation stricte des rôles), mais plus complète et plus formalisée. Points structurants :
- **Fenêtre de données : 5 à 12 matchs, SAISON ACTUELLE UNIQUEMENT** — jamais de repli sur la saison précédente (différence majeure avec V0's N_MIN=8 qui autorisait implicitement un mélange via `recupere_gf_ga_avec_repli`). Teste directement l'hypothèse "conjoncturelle" de la situation critique #25. **Interdiction explicite et nommée dans la spec** d'un facteur correctif du type `λ' = 1.155λ` sans validation walk-forward — critique directement ce qu'on vient de faire avec `CORRECTION_BUTS_V0`.
- Statistiques complètes par équipe (offensive/défensive, globale/domicile/extérieur, W/D/L, variables de buts type BTTS/clean sheets, dispersion — médiane/variance/écart-type), construites comme base descriptive, PAS injectées automatiquement dans λ.
- λ = estimation par équipe sans coefficient correctif, distinction stricte domicile/extérieur (attaque domicile d'Équipe A + défense extérieur d'Équipe B, pas de moyennes globales mélangées).
- H2H strictement indépendant de λ (ne le modifie jamais), avec des paliers de fiabilité explicites (< 5 insuffisant, 5-7 indicatif, 8-9 fiable, ≥10 très fiable, plafonné à 10), et un état par marché (corroboré/contradictoire/neutre/insuffisant) — jamais un inverseur automatique de pronostic.
- EDV = P_modèle − P_implicite (soustraction, PAS le format multiplicatif `P×cote−1` utilisé par V0) — à trancher lequel garder ou si les deux coexistent.
- Sélection par croisement de signaux (Poisson + stats + H2H + EDV), sans pondération arbitraire initiale — les poids sont à découvrir empiriquement plus tard, jamais fixés au départ.
- Validation walk-forward chronologique stricte obligatoire (jamais entraîner et tester sur les mêmes matchs) — méthode formalisée, proche de ce qu'on a testé de façon ad hoc (29/08 vs 30/08) mais généralisée en "rolling origin".
- Journalisation obligatoire, granularité par marché/catégorie/H2H/cote/contexte pour permettre un futur calcul de `P(succès | signal)`.
- Architecture Python modulaire proposée (`archetype_model/` avec sous-dossiers `data/`, `statistics/`, `poisson/`, `h2h/`, `edv/`, `markets/`, `selection/`, `validation/`).

### 26.4 Point à chiffrer en priorité avant d'implémenter quoi que ce soit (remarque de Claude, pas encore vérifié)
La règle "saison actuelle uniquement, minimum 5 matchs" est strictement plus restrictive que le `N_MIN=8` actuel de V0 (qui autorise un repli sur la saison précédente via `recupere_gf_ga_avec_repli`). Sur les données déjà collectées (306 matchs, `historique_v0.jsonl`, voir situation critique #24), il est probable que le nombre de `NO_BET` explose en tout début de saison (une bonne partie des 40 cas "aucun match joué cette saison" de la situation critique #20 deviendrait la norme plutôt que l'exception pour BEAUCOUP plus d'équipes, puisqu'on ne pourra plus se rabattre sur la saison précédente même partiellement). Ce n'est pas un défaut de la spec — c'est un choix assumé et cohérent avec sa philosophie — mais c'est un compromis à CHIFFRER sur les vraies données déjà disponibles avant de se lancer, pas à découvrir après coup.

### 26.5 Feuille de route à l'issue de cette session
- 🆕 **PRIORITÉ ABSOLUE SESSION SUIVANTE** : relire la spécification complète (redemander le fichier à Patrick s'il n'est pas dans le contexte), discuter architecture cible et plan d'implémentation avec Patrick avant tout code — même discipline habituelle (architecture → fichiers impactés → dépendances → invariants → tests → feu vert → implémentation).
- ⬜ Chiffrer l'impact de la règle "saison actuelle uniquement" sur les données déjà collectées (voir 26.4) avant de committer à la fenêtre 5-12.
- ⬜ Si Patrick a la réponse de ChatGPT sur la question de calibration (situation critique #25/26.1), l'intégrer à la réflexion sur la fenêtre de données de la nouvelle spec.
- ⬜ Décider explicitement : la V0 actuelle (fichiers non poussés, voir situation critique #24) est-elle abandonnée, ou sert-elle de brique de départ partiellement réutilisable (ex. le mécanisme de journalisation `historique_v0.jsonl`/`verifie_historique_v0.py` semble largement compatible avec la nouvelle spec, section 25 "journalisation obligatoire" de la spec) ?
- ⬜ Tout ce qui restait ouvert avant ce pivot reste ouvert et non prioritaire pour l'instant : bug H2H 1X2/Double chance (#17/24.2), faux négatifs `scraper_details.py` (#20), #33/#38/#39.

## 27. Session du 08/09/2026 — Verrouillage complet du modèle `archetype_model`, aucun code écrit

### 27.1 V0 définitivement abandonné, pas juste suspendu
Patrick a tranché explicitement en tout début de session : **on n'utilise plus V0 du tout**, ni comme code de base, ni comme référence de comparaison. Contrairement à ce que disait la situation critique #26 précédente ("suspendue, pas annulée"), c'est maintenant une décision ferme et définitive. Toute comparaison ou réutilisation de code V0 (matrice Poisson, fonctions `*_v0`) a été explicitement écartée en cours de session — `archetype_model/` est un package intégralement neuf, aucune ligne de V0 dedans.

### 27.2 Chiffrage réel de l'impact "saison actuelle uniquement" (répond à la situation critique #26.4 de la session précédente)
Deux chiffres réels obtenus, aucun n'est une estimation :
- **`cache_equipes.json`** (725 couples équipe/compétition, snapshot 05-07/09) : `nb_domicile`==10 (plafond `max_matchs`) pour 368/725 (50,8%), `nb_exterieur`==10 pour 367/725 (50,6%), les deux plafonnés ensemble pour 359/725 (49,5%). À ce stade de saison (2-4 journées), un plafond à 10 signifie presque toujours qu'un repli sur la saison précédente a été nécessaire.
- **`historique_pronostics.json`** (ancien moteur, 24/08→30/08, avant rupture de schéma du 04/09) : 434 matchs candidats, 131 (30,2%) rejetés pour motif `aucun_match_joué_saison_actuelle_ou_précédente` — zéro historique trouvé même avec repli complet autorisé (plancher le plus permissif possible, l'ancien moteur n'a pas de `N_MIN`). Seulement 272/434 (62,7%) traités avec ce plancher minimal.
- **Blocage confirmé, réel, pas contournable sur les données actuelles** : `scraper_details.py` (`_extrait_historique_competition`) n'a jamais extrait la date de chaque match individuel — impossible de reconstituer rétroactivement "quelles données étaient disponibles avant tel match précis". Le chiffre EXACT de l'impact de la fenêtre 5-12/saison-actuelle nécessite un correctif ciblé (ajouter le champ date au parsing) puis un nouveau run — pas fait cette session, resté hors périmètre.
- **Conclusion opérationnelle retenue** : le taux de non-résolu réel sous la nouvelle règle sera supérieur à 30-50% en tout début de saison, décroissant ensuite. Assumé comme un compromis du modèle, pas un défaut à corriger.

### 27.3 Distinction importante clarifiée en session (erreur de Claude corrigée en direct) : le blocage de date N'EMPÊCHE PAS le walk-forward
Claude avait initialement (à tort) présenté le blocage de 27.2 comme empêchant aussi la validation walk-forward rétroactive. Patrick a contesté à juste titre. Vérification faite : **`historique_pronostics.json` contient déjà 272 matchs avec un score réel enregistré**, capturés par le pipeline de production AVANT le coup d'envoi (donc sans fuite d'information), le résultat étant ajouté après coup. C'est un vrai jeu de données walk-forward valide, immédiatement exploitable pour un backtest du nouveau moteur — **aucun besoin d'attendre le correctif de date pour ça**. Le blocage de 27.2 concerne uniquement la reconstruction rétroactive de la composition saison-actuelle/saison-précédente d'un échantillon, pas la validité temporelle du backtest lui-même. À bien garder distinct dans toute future implémentation de `validation/walk_forward.py` (boucle B).
Note additionnelle : `historique_v0.jsonl` (306 matchs V0) a `resultat_reel` à `null` sur les 306 lignes — jamais vérifié (`verifie_historique_v0.py`, mentionné créé en 24.6, absent du zip livré cette session, cohérent avec le fait que les fichiers V0 n'ont jamais été poussés). Le vrai gisement immédiatement exploitable pour le backtest est donc les 272 matchs d'`historique_pronostics.json`, pas les 306 de V0.

### 27.4 Nouvelle spécification reçue et corrigée deux fois (documents livrés en pièce jointe chat, PAS dans le dépôt)
- Document reçu en cours de session : `ARCHETYPE_FOOT___Modèle_de_conception_consolidé_et_spécification_technique.md` — version bien plus formalisée et complète que la première réponse ChatGPT de la session 26 (multi-λ à 4 scénarios, P1/P2/P3, familles/groupes d'exposition, deux boucles de validation walk-forward/rétrospective déjà alignées avec 27.3).
- Claude a relu ce document et trouvé 7 failles de spécification réelles (pas des désaccords de philosophie) : λ offensif/défensif utilisés en sortie mais jamais formellement définis ; seuil de robustesse multi-λ jamais chiffré ; Edge et EDV mathématiquement toujours de même signe (`EDV = cote × Edge`) sans que leur usage différencié soit exploité ; pas de règle de départage pour P1 ; aucun fichier dédié à la mesure de robustesse dans l'arborescence ; formule de probabilité du handicap non dérivée ; validation du facteur correctif 1,155 restée qualitative sans règle de décision.
- Ces 7 points corrigés et intégrés dans **`ARCHETYPE_FOOT_modele_corrige_v2.md`** (généré par Claude, livré en pièce jointe chat — **PAS dans le dépôt**).
- Patrick a fait relire ce v2 à ChatGPT, qui a trouvé 5 correctifs supplémentaires, tous vérifiés fondés par Claude avant intégration (aucun accepté par précaution) : P1 classé par Edge décroissant, incohérent avec son rôle de "convergence" annoncé (Edge redescend en dernier départage) ; déduplication par comptage de signaux corroborants, réintroduisant un score caché (remplacé par cascade déterministe robustesse→H2H→Edge/EDV) ; P3 "robustesse suffisante" non verrouillée (fixé : STABLE obligatoire, pas de fallback INSTABLE) ; seuil 0,08 à centraliser en constante nommée (`ROBUSTNESS_STD_THRESHOLD`) plutôt que recopié en dur ; traitement des lignes de handicap en quart de but pas assez précis (précisé : répartition 50/50 de l'enjeu sur les deux lignes adjacentes).
- Ces 5 points intégrés dans **`ARCHETYPE_FOOT_modele_corrige_v3.md`** (généré par Claude, livré en pièce jointe chat — **PAS dans le dépôt, à redemander en début de session suivante si absent du contexte** — c'est le document de référence actuel, remplace le v2 et la spec ChatGPT initiale de la session 26).

### 27.5 Quatre nouveaux marchés ajoutés (demande explicite de Patrick), intégrés en section 9.4 du v3
Tous dérivés de la matrice de scores déjà prévue par le modèle, aucune nouvelle donnée ni coefficient :
- **TEAM_GOALS Over** (équipe X marque +0.5/+1.5/+2.5 buts) — famille déjà présente, ligne 0.5 ajoutée, lue sur la distribution marginale de Poisson de l'équipe seule (pas la matrice jointe), fiche d'affichage montrant le λ propre à cette équipe.
- **TEAM_GOALS Under** (symétrique, -0.5/-1.5/-2.5).
- **COMBO_DC_TOTAL Over** (double chance + total de buts Over 1.5/2.5/3.5) — nouvelle famille, calcul **conjoint** sur la matrice (jamais un produit de probabilités marginales, DC et total de buts ne sont pas indépendants). Nouveau fichier prévu : `markets/combo_markets.py`.
- **COMBO_DC_TOTAL Under** (symétrique, Under 1.5/2.5/3.5/4.5).

### 27.6 Statut de fin de session : feu vert donné, ZÉRO code écrit
Patrick a explicitement demandé de ne pas coder dans cette fenêtre. Le modèle v3 est verrouillé et validé (deux relectures croisées fermées), mais **aucun fichier Python n'existe encore pour `archetype_model/`**. Point resté ouvert et non résolu, à traiter dès le début de l'implémentation : **vérifier si `matchendirect.fr` liste l'historique d'une équipe du plus récent au plus ancien ou l'inverse** — `_extrait_historique_competition` prend actuellement les N premières lignes rencontrées sans que cet ordre soit vérifié ni documenté ; si l'ordre est inversé, la règle "12 plus récents" (section 5 du v3) deviendrait silencieusement "12 plus anciens". Vérification manuelle de Patrick nécessaire (page réelle dans un navigateur), l'environnement d'édition n'a pas accès à `matchendirect.fr`.

### 27.7 Feuille de route à l'issue de cette session
- 🆕 **PRIORITÉ ABSOLUE SESSION SUIVANTE** : redemander `ARCHETYPE_FOOT_modele_corrige_v3.md` si absent du contexte (pas dans le dépôt), puis démarrer l'implémentation module par module — discipline habituelle inchangée (fichiers impactés → dépendances → invariants → tests de non-régression → feu vert → implémentation → mise à jour `audit_permanent.py` → livraison fichier par fichier).
- ⬜ Vérifier l'ordre chronologique des matchs sur une page matchendirect réelle (27.6) AVANT de coder `data/validation.py` (troncature aux 12 plus récents).
- ⬜ Une fois le moteur codé : lancer la boucle B (backtest rétrospectif) sur les 272 matchs déjà vérifiés d'`historique_pronostics.json` (27.3) — recalculer λ selon les formules du v3 à partir des données brutes déjà en cache, ne jamais réutiliser un λ déjà stocké par l'ancien moteur.
- ⬜ Correctif optionnel, hors périmètre de l'implémentation principale, à proposer à Patrick séparément si utile : ajouter le champ date au parsing de `_extrait_historique_competition` pour débloquer le chiffrage exact de 27.2 (actuellement seulement estimé par proxy).
- ⬜ Tout ce qui restait ouvert avant ce pivot reste ouvert et non prioritaire : bug H2H 1X2/Double chance (#17/24.2), faux négatifs `scraper_details.py` (#20), #33/#38/#39.

## 28. Session du 09/09/2026 — `archetype_model` intégralement codé, testé et audité, du chargement des données à la sélection P1/P2/P3

### 28.1 Résumé : les 27 fichiers du package sont écrits, testés unitairement, intégrés dans `audit_permanent.py`, et un audit d'intégration bout en bout confirme leur assemblage correct
```
archetype_model/__init__.py
archetype_model/data/{__init__,loader,validation,odds_provider}.py
archetype_model/statistics/{__init__,distributions,team_stats,goals}.py
archetype_model/poisson/{__init__,lambda_estimators,distribution,robustness,markets}.py
archetype_model/h2h/{__init__,h2h_stats,h2h_markets}.py
archetype_model/edv/{__init__,calculator}.py
archetype_model/signals/{__init__,statistiques_signal,convergence,deduplication,selector}.py
archetype_model/backtest/{__init__,boucle_b}.py
archetype_model/main.py
```
Tout le pipeline décrit par le v3 est couvert, à l'exception explicite du référentiel central formel (§9.1, `markets/registry.py`) — voir 28.10. `audit_permanent.py` contient désormais ~35 nouvelles sections de vérités (une par chantier), toutes vertes.

### 28.2 Ordre chronologique matchendirect.fr — enfin vérifié sur captures d'écran réelles, DEUX conventions opposées coexistent
Vérifié le 08/09/2026 avec Patrick (point resté ouvert depuis 27.6) :
- **Tableau "historique par compétition"** (celui que lit `_extrait_historique_competition`, utilisé pour domicile/extérieur et pour le global compétition-unique) : **CROISSANT**, plus ancien en premier (confirmé sur Al Ettifaq/Arabie Saoudite et Kalmar/Suède). Conséquence : `data/loader.py` tronque aux 12 plus récents en prenant `liste[-12:]`, PAS `liste[:12]`.
- **Tableau "Confrontations entre les deux équipes"** (H2H, celui que lit `_extrait_matchs_scores`/`recupere_h2h`) : **DÉCROISSANT**, plus récent en premier (confirmé sur Al Faisaly/Al Ettifaq). Conséquence inverse : `h2h/h2h_stats.py` tronque aux 10 plus récents avec `liste[:10]`.
Les deux conventions sont documentées explicitement dans le code (`data/loader.py::ASSUME_ORDRE_CROISSANT`, `h2h/h2h_stats.py` docstring) pour qu'on ne les confonde jamais.
Bug réel confirmé au passage, **non corrigé, hors périmètre, décision explicite de Patrick** : l'ANCIEN moteur (`scraper_details.recupere_gf_ga_avec_repli`) prend les N premiers éléments rencontrés sur le tableau croissant — donc les N PLUS ANCIENS, pas les plus récents. Tourne en prod depuis le début (`run_pipeline.py`, `precalcul.py`, `calculs.py`).

### 28.3 λ_global : tentative multi-compétitions codée puis ANNULÉE sur décision de Patrick, remplacée par une version compétition-unique
Un premier chantier a ajouté `data/loader.py::recupere_historique_toutes_competitions` (découverte de tous les blocs "Pays : Compétition" d'une page équipe, fusion). Fonctionnel et testé (vérifié sur une vraie page Lille OSC à 2 compétitions), mais **Patrick a demandé l'annulation explicite** : "on reste sur les matchs de championnat". Le code a été **supprimé** (pas laissé en sommeil, conformément à la discipline "poubelle ce qui n'est plus utilisé" du tout début de session) et remplacé par une version qui réutilise l'historique DÉJÀ récupéré pour la compétition du match (domicile+extérieur fusionnés, sans fetch réseau supplémentaire) — voir `main.py::_stats_globales` et `backtest/boucle_b.py::_stats_globales_depuis_cache`. λ_global est donc calculé, mais uniquement sur la compétition du match analysé, comme les 3 autres scénarios.

### 28.4 Cotes réelles : `data/odds_provider.py`, découverte que Betpawa n'est PAS la source principale
Audit réel de `precalcul.json` : 223 matchs sur 363 utilisent `source_cotes="matchendirect_bet365"` (scraping direct), seulement 91 utilisent `"manuel"` (la voie Betpawa via `panier.json`/`cotes_manuelles`). Les deux sources sont déjà unifiées par le pipeline existant dans `signaux[].TOUS_MARCHES_EVALUES` (liste `{marche, cote_observee, probabilite_modele}`) — `odds_provider.py` lit cette liste, traduit les 62 libellés français vers les clés `archetype_model` (56 reconnus, 6 non couverts : cage inviolée x2, encaisse au moins 1 but x2, pair/impair x2 — familles CLEAN_SHEET/PAIR_IMPAIR jamais codées dans `poisson/markets.py`), et ignore totalement `probabilite_modele` (celle de l'ANCIEN moteur, jamais réutilisée). Rappel de Patrick à garder pour plus tard, non bloquant : Betpawa reste la source économiquement pertinente (site de pari réel) — `est_betpawa` exposé dans le résultat pour un futur arbitrage entre sources, aucune préférence appliquée aujourd'hui (une seule source existe par match dans `precalcul.json`).

### 28.5 H2H : bug d'orientation de l'ancien moteur (#17) structurellement évité, pas juste évité par prudence
`h2h/h2h_stats.py::recupere_confrontations` normalise chaque confrontation passée en `{"buts_a", "buts_b"}` du point de vue de l'équipe A, peu importe si elle jouait domicile ou extérieur dans cette rencontre historique précise (réutilise `scraper_details._memes_equipes`). Grâce à cette normalisation faite UNE FOIS en amont, `h2h/h2h_markets.py` a pu coder les 6 familles de marchés (BTTS, Over/Under total, buts par équipe, **1X2, Double Chance, Handicap**) sans jamais réinterpréter de texte brut au moment de la comparaison — c'est cette réinterprétation tardive qui causait le bug de l'ancien moteur, et elle n'existe plus dans cette architecture. Palier de fiabilité (`<5` INSUFFISANT, 5-7 INDICATIF, 8-9 FIABLE, `≥10` TRÈS FIABLE) codé conformément au v3 §10.

### 28.6 Filtre de candidature : robustesse binaire confirmée, AUCUN scénario λ "officiel"
Patrick a fourni un `filter.py` externe comme modèle, adapté en `signals/convergence.py` avec deux corrections tranchées explicitement :
1. **`MODEREE` (3e niveau de robustesse) supprimé entièrement**, pas gardé en sommeil — notre `poisson/robustness.py` reste strictement binaire (STABLE/INSTABLE, seuil unique 0.08, v3 tel quel). Un `robustesse="INDETERMINE"` (la vraie valeur produite quand un scénario manque) est rejeté comme `ROBUSTESSE_INVALIDE`.
2. **Aucun "scénario retenu" choisi arbitrairement** pour alimenter le filtre avec une probabilité unique — le terme n'apparaît qu'une fois dans tout le v3 (§9.4.1, jamais défini) et n'existait pas dans notre code. Décision finale de Patrick : **le filtre tourne une fois par scénario (offensif/défensif/contextuel/global) et exige l'ÉLIGIBILITÉ DANS LES 4** (`filtre_marche_convergent`) — un seul échec rejette le marché entier. Aucune moyenne, aucun choix arbitraire.

### 28.7 Dédoublonnage : deux contraintes séparées, pas une clé combinée
`signals/deduplication.py` — vérification textuelle faite AVANT de coder (§12.2) : "un seul par famille ET par groupe d'exposition" sont deux regroupements séparés, pas une paire (famille, groupe). Réduction en deux étapes (un par famille, puis parmi ces représentants un par groupe d'exposition) — sinon deux candidats de familles différentes partageant un même groupe économiquement corrélé passeraient tous les deux. Cascade de départage : robustesse (no-op en pratique, toujours STABLE) → palier H2H → Edge/EDV selon le rôle visé.

### 28.8 Sélection P1/P2/P3 : H2H confirmé non décisionnel avant ce stade, par preuve structurelle ET comportementale
`signals/selector.py` : P1 (cascade niveau → robustesse → signal Statistiques → palier H2H → EDV), P2 (même cascade, parmi les candidats dont famille ET groupe diffèrent TOUS LES DEUX de P1), P3 (idem vs P1 et P2, STABLE et EDV positif obligatoires, absent si personne ne qualifie — jamais un remplissage forcé).

### 28.9 Audit d'intégration bout en bout — H2H prouvé non décisionnel avant sélection, deux façons
Section dédiée dans `audit_permanent.py` : (1) preuve STRUCTURELLE — `filtre_marche`/`filtre_marche_convergent` n'ont aucun paramètre H2H dans leur signature, vérifié par introspection (`inspect.signature`) ; (2) preuve COMPORTEMENTALE — sur un scénario réaliste complet (deux équipes, historique suffisant), un H2H fortement CORROBORE et un H2H fortement CONTREDIT (données fabriquées pour être diamétralement opposées) produisent des résultats de filtre **strictement identiques** (`as_dict()` égal), alors que le même H2H change bien l'issue de la sélection P1 quand il sert de départage entre deux candidats équivalents par ailleurs.

### 28.10 Ce qui reste ouvert, pour la session suivante
- 🆕 **Référentiel central formel (§9.1, `markets/registry.py`)** : jamais codé. Non bloquant en pratique — `deduplication.py`/`selector.py` fonctionnent avec `market_family`/`exposure_group` fournis directement par l'appelant plutôt que déduits d'un registre central. À faire si on veut une source unique de vérité pour ces classifications plutôt que de les répéter à chaque appel.
- 🆕 **`validation/` (walk_forward.py, calibration.py, performance.py, bias_check.py)** : seule `backtest/boucle_b.py` existe (équivalent walk-forward rétrospectif partiel). Calibration (probabilité annoncée vs fréquence réelle), performance (ROI/Brier/log loss détaillés) et le test de correction historique 1.155 (§14.3) ne sont pas codés.
- 🆕 **Boucle B jamais exécutée sur les vraies données** : `backtest/boucle_b.py` est écrit et testé sur fixtures, mais nécessite un accès réseau à matchendirect.fr (résolution équipe→cache via `recupere_details_match`) que l'environnement d'édition n'a pas. À lancer via GitHub Actions ou en local. Le nombre réel de matchs vérifiés dans `historique_pronostics.json` est 1266 aujourd'hui (pas 272, chiffre de 27.3 devenu obsolète — la base grossit chaque nuit).
- 🆕 **CLEAN_SHEET et PAIR_IMPAIR** : cotes déjà disponibles via `odds_provider.py` (6 libellés non couverts sur 62), mais aucune fonction dans `poisson/markets.py` ne calcule ces probabilités depuis la matrice de Poisson.
- 🆕 **`main.py` n'utilise que 1X2/DC/BTTS/Over-Under 2.5 pour la robustesse** (5 marchés) — `calcule_tous_les_marches` produit bien tous les marchés (dont handicap/combos) par scénario, mais `robustesse_par_marche` ne les couvre pas tous. Extension directe si besoin (la structure `_valeurs_4_scenarios` + extracteur est déjà générique).
- 🆕 **Rien n'assemble encore `h2h`/`signals`/`edv`/`odds_provider` avec `main.py` en une seule fonction d'orchestration de bout en bout** — chaque brique existe et est testée séparément (et l'audit d'intégration de 28.9 prouve qu'assemblées manuellement elles fonctionnent ensemble), mais il n'y a pas encore de fonction unique du type `analyse_match_complete()` qui enchaîne tout automatiquement pour un match réel.
- ⬜ Reste de la feuille de route de 27.7 non traité cette session (correctif date optionnel, bugs mineurs #17/#20/#33/#38/#39) : toujours hors périmètre, non prioritaire.

## 29. Session du 09-10/09/2026 — `archetype_model` branché en production, 2 runs réels, 13 premiers pronostics, dossier envoyé en revue externe

### 29.1 Résumé général
Chantier d'orchestration de la §28.10 terminé (`analyse_match_complet()`), branché en production dans `precalcul.py` avec filet de sécurité, exécuté deux fois en conditions réelles. Périmètre étendu de 6 à 12 marchés. Un bug réel de scraping (n_brut trop bas) s'est révélé être une contrainte structurelle correcte, mais a mené à la découverte d'un vrai bug de seuil (gate domicile/extérieur séparé au lieu du total saison), corrigé. Seuil de probabilité abaissé de 0.60 à 0.54 (décision de Patrick, non validée, temporaire). Page dédiée `archetype.html` créée après confusion sur l'affichage. Dossier technique complet envoyé à un bureau d'étude externe pour calibrage rigoureux (§29.10).

### 29.2 `analyse_match_complet()` écrite et branchée en production avec filet de sécurité
`archetype_model/main.py::analyse_match_complet()` enchaîne data→h2h→signal→cotes→EDV→filtre→dédoublonnage→sélection. Branchée dans `precalcul.py::applique_archetype_model()`, appelée juste après `construit_signaux()` (ancien moteur, jamais modifié). Règle de fallback explicite de Patrick, testée (cas critiques B/C) : **une décision métier normale (INSUFFISANT, OK sans candidat) n'est JAMAIS un motif de repli vers l'ancien moteur** — seule une exception Python (erreur réseau réelle) déclenche le fallback, marqué `moteur_utilise="ancien (fallback technique)"`. Cotes passées en mémoire (`odds_provider.extrait_cotes(s)`) plutôt que relues depuis `precalcul.json` — ce fichier est celui que le run est en train de construire, pas encore à jour pour le match en cours.

### 29.3 Bug de seuil corrigé : le gate d'entrée comptait domicile et extérieur séparément
Diagnostiqué avec Patrick sur un cas réel (Derby County vs West Bromwich, journée 6 de Championship, vérifié sur captures d'écran matchendirect.fr) : `analyse_match()` gatait sur N≥5 matchs à DOMICILE pour l'équipe A et N≥5 à L'EXTÉRIEUR pour B séparément — mathématiquement impossible à satisfaire avant la 10e-12e journée de n'importe quelle compétition. Corrigé pour gater sur le TOTAL saison (domicile+extérieur confondus) de chaque équipe ; les moyennes domicile/extérieur spécifiques (nécessaires aux scénarios offensif/défensif) sont calculées avec ce qui est disponible dans le sous-ensemble, SANS second seuil N≥5 dessus (décision explicite de Patrick : "on calcule les moyennes avec les données dont on dispose"). Effet réel mesuré : matchs "OK" passés de 108 à 446 entre les deux runs.

### 29.4 Extension de 6 à 12 marchés (Cage inviolée, Encaisse au moins 1 but, Parité totale — domicile ET extérieur)
Nouvelle fonction `poisson/markets.py::probabilite_parite_totale()` (pair/impair, testée : pair+impair=1.0, piège du 0-0 pair, cas None). Cage inviolée/Encaisse ne nécessitaient AUCUNE nouvelle fonction — exactement `buts_equipe_domicile`/`buts_equipe_exterieur[0.5]` déjà calculés, reliés aux bons libellés dans `odds_provider.py`. **Bug réel trouvé et corrigé en cours de chantier** : les 4 marchés Cage inviolée/Encaisse (domicile ET extérieur) partageaient tous la même famille `"CLEAN_SHEET"` — ça aurait fait éliminer à tort un pick sur l'équipe extérieure au profit d'un pick sur l'équipe domicile (ou l'inverse) alors que ce sont deux équipes différentes. Corrigé en deux familles distinctes (`CLEAN_SHEET_DOMICILE`/`CLEAN_SHEET_EXTERIEUR`), toujours dans le même groupe d'exposition `GROUPE_BUTS`.

### 29.5 Deux runs réels GitHub Actions exécutés, chiffres vérifiés indépendamment via l'API GitHub
| | Run 09/09 | Run 10/09 |
|---|---|---|
| Matchs traités | 698 | 963 |
| Tentés par archetype_model | 610 | 831 |
| INSUFFISANT | 502 | 385 |
| OK | 108 | 446 |
| Fallback technique | 2 (vrais timeouts réseau) | 0 |
| **P1 réel** | **0** | **13** |

Chaque chiffre revérifié en retéléchargeant `precalcul.json` directement depuis `raw.githubusercontent.com` (accès réseau disponible depuis l'environnement d'édition pour ce domaine, contrairement à `matchendirect.fr`) — jamais fait confiance au seul résumé de log. Un résumé (`moteur_utilise`, statuts, nb de P1) est maintenant imprimé directement dans le log GitHub Actions par `applique_archetype_model()`, pour éviter de devoir reparser `precalcul.json` à chaque vérification.

**Piège détecté et corrigé avant le 2e run** : après une série de corrections, `markets.py` sur le dépôt réel était resté une version antérieure (sans `probabilite_parite_totale`) alors que les 4 autres fichiers livrés étaient à jour — aurait fait planter `archetype_model` sur chaque match (`KeyError`), absorbé silencieusement par le filet de sécurité (fallback technique généralisé, aucune contribution réelle du nouveau moteur). Détecté en comparant le SHA/contenu réel du dépôt via `api.github.com/repos/.../git/trees/main?recursive=1` avant le lancement.

### 29.6 Affichage : deux correctifs, le second remplaçant le besoin du premier
D'abord ajouté un bloc pliable "voir archetype_model" sur chaque carte de `pronostics.html`/`script.js` (tolérant, n'affiche rien si absent). Puis découverte que `verdict_global` (ancien moteur uniquement) pilotait le tri/filtre/badge de cette page — un pick archetype_model avec NO_GO ancien moteur était invisible ou noyé en bas de liste. Ajout de `estArchetypeGo()`, badge distinct `★ ARCHETYPE` (turquoise), tri et filtre GO étendus. **Puis, sur demande explicite de Patrick** ("une page unique pour les pronostics retenus du nouveau moteur"), création de `archetype.html`/`archetype.js` — page dédiée, ne lit que `precalcul_leger.json`, ne montre QUE les matchs avec `moteur_utilise==="archetype_model"` et un P1 réel, aucun mélange avec l'ancien moteur. Lien ajouté dans la nav de `index.html`. `precalcul.py::_leger_pour_site()` allège le champ `archetype_model` pour le site (statut+sélection seulement, pas les diagnostics complets) — même logique déjà appliquée à `marches`/`lambda`.

**Point de confusion à ne pas répéter** : `index.html` charge `index.js` (outil de sélection du panier Betpawa), PAS `script.js` (utilisé par `pronostics.html`) — ce sont deux pages/scripts complètement séparés. Si "rien ne s'affiche" est signalé, vérifier D'ABORD sur quelle page/quel fichier avant de chercher un bug.

### 29.7 Seuil de probabilité (0.60→0.54) : origine non tracée, changement appliqué avec traçabilité complète
Patrick a demandé un audit de l'origine du seuil de 60 % — aucune trace dans le code ni `TRANSITION.md` de sa dérivation (venait d'"un modèle fourni par Patrick le 09/09/2026" selon l'en-tête de `convergence.py`, sans justification documentée). Rapproché explicitement du principe déjà établi en 27.x : "N_MIN, EV_MIN, STAKE — c'est tout, rien d'autre à compter" (une constante empruntée sans validation avait déjà été retirée une fois). Patrick a décidé, en toute connaissance de cause et faute de tokens pour continuer à discuter, d'abaisser le seuil à **0.54**, décision EXPLICITEMENT temporaire et non calibrée. `PROBABILITE_MIN` extraite en constante nommée (elle n'existait qu'implicitement comme borne basse du tableau EDV). Nouveau palier `EDV_MIN_P_54_60 = 0.16` ajouté par extrapolation linéaire de la pente déjà présente dans le tableau (documentée comme non calibrée elle aussi). 6 nouveaux tests dans `audit_permanent.py` (296 tests au total, tous verts).

**Résultat de simulation important pour la suite** : en rejouant les 446 matchs du run du 10/09 avec des seuils de 60 % à 40 %, **le nombre de matchs retenus reste strictement identique (13)** à tous les niveaux testés. Abaisser encore le seuil de probabilité n'aura aucun effet sur le volume avec ce type de données — le vrai goulet est ailleurs (voir §29.10, question 3 du dossier).

### 29.8 Entonnoir de rejet mesuré à l'échelle (446 matchs, 21 408 paires marché×scénario)
75,2 % probabilité insuffisante, 17,3 % cote absente (concentré à 77 %/69 % sur Encaisse domicile/extérieur — vérifié que seuls 5-6 % des matchs ont même cette cote quotée, pas un bug de code), 3,3 % cote hors intervalle, 1,9 % EDV insuffisante, 1,2 % robustesse instable. Sur les candidats à 1-3 scénarios éligibles sur 4 (58 au total, tous marchés confondus), le scénario **"global"** est le plus souvent responsable du blocage (47 occurrences, loin devant les 3 autres).

### 29.9 Dossier technique complet rédigé et transmis à un bureau d'étude externe
`dossier_technique_archetype_model.md` (livré à Patrick le 10/09/2026) : contexte, architecture complète du pipeline, données réelles des 2 runs, entonnoir détaillé, tableau des 5 constantes non validées avec leur statut, 6 questions précises (méthodologie de calibrage, pertinence de l'unanimité des 4 scénarios, investigation du résultat contre-intuitif de la simulation de seuil, gestion du démarrage de saison, couverture des cotes Encaisse, priorisation), contraintes non négociables de Patrick, liste des artefacts disponibles.

### 29.10 Ce qui reste ouvert, pour la session suivante
- 🆕 **Retour du bureau d'étude externe** : quand Patrick revient avec leurs recommandations, les traiter comme un AUDIT EXTERNE à confronter au code réel (même discipline que le reste du projet : vérifier chaque recommandation contre le comportement réel mesuré, jamais appliquer une préconisation sans la valider sur les vraies données de ce dépôt d'abord). Prioriser les réponses aux 6 questions du dossier (§29.9) dans l'ordre où Patrick les rapporte.
- 🆕 **Vérification des 13 premiers pronostics réels** : les matchs sélectionnés lors du run du 10/09/2026 doivent être vérifiés contre leurs résultats réels dès qu'ils sont joués (probablement disponible à la reprise, ~2 jours après le 10/09). C'est la première vraie donnée de performance d'`archetype_model` — à traiter avec la même rigueur que `verification_resultats.py`/`calcule_roi.py` le font pour l'ancien moteur. Aucune archive dédiée n'existe encore pour `archetype_model` (seul `historique_pronostics.json` de l'ancien moteur est alimenté) — chantier d'archivage à faire AVANT ou PENDANT cette vérification, sinon rien à comparer aux résultats.
- 🆕 **Le seuil de 0.54 (et le palier EDV 0.16) restent explicitement non validés** — ne jamais les présenter comme définitifs tant que la vérification ci-dessus n'a pas eu lieu.
- 🆕 **Coût réseau du double appel `recupere_details_match`** (déjà signalé en 29.2/session précédente) : run passé de 1h40 à 3h28 entre les deux runs, corrélé à la hausse du nombre de matchs tentés (610→831). À surveiller si le volume continue de croître, chantier de cache séparé si besoin.
- ⬜ Référentiel central formel (§9.1), `validation/` (calibration.py, performance.py, bias_check.py autres que boucle_b.py), extension du Handicap/TeamGoals à `robustesse_par_marche` : toujours non commencés, non prioritaires tant que le retour du bureau d'étude n'a pas orienté la suite.

### ⚠️ CORRECTION (10/09/2026, reprise de session) — le seuil 0.54 décrit en §29.7 n'a jamais atteint `main`
Vérification faite directement sur le dépôt réel (`api.github.com/repos/.../git/trees/main?recursive=1` + `codeload.github.com` pour le contenu complet, jamais sur la seule mémoire de session) : `archetype_model/signals/convergence.py` sur `main` contient toujours `probabilite_centrale >= 0.60` en dur, aucune trace de `PROBABILITE_MIN` ni de `EDV_MIN_P_54_60`. Le changement décrit en §29.7 a soit été fait sur une branche jamais fusionnée, soit annulé sans mise à jour de ce document — impossible à trancher a posteriori, et sans conséquence pratique puisque le code réel fait foi. **Décision de Patrick (10/09/2026) : on ne remet PAS le 0.54, le système reste sur 0.60, état réellement en production.** §29.7 reste tel quel comme trace de la décision prise ce jour-là, mais ne décrit plus l'état réel du code depuis cette correction. Tout le chantier de la §30 ci-dessous a été mesuré et testé avec le seuil 0.60 réellement actif.

## 30. Session du 10/09/2026 (reprise) — Périmètre de marchés dynamique piloté par les cotes, marchés combinés DC+Total avec garde-fou anti-corrélation, retour du bureau d'étude partiellement fiable

### 30.1 Résumé général
Sur demande explicite de Patrick, `archetype_model/main.py` est passé d'une liste figée de 12 marchés à un **périmètre dynamique** : tout marché dont une cote réelle existe (`data.odds_provider`) ET que le modèle Poisson sait calculer devient automatiquement candidat, sans entrée manuelle à ajouter. Extension à Double Chance, Over/Under sur toutes les lignes réellement cotées (pas seulement 2.5), buts par équipe sur toutes les lignes, Handicap sur toutes les lignes, plus les marchés combinés DC+Total avec un garde-fou anti-corrélation dédié. Rejeu réel sur les 446 matchs OK du run du 10/09 : **68 candidats 4/4 (16 base + 52 nouveau périmètre), 48 matchs distincts avec un P1 réel après dédoublonnage** (contre 13 avant ce chantier). `audit_permanent.py` : 299 vérités, 0 échec (289 précédentes + 10 nouvelles).

### 30.2 Fiabilité du bureau d'étude externe : vérifiée point par point, un tiers faux détecté
Le retour du bureau d'étude (réponse au dossier de §29.9) a été confronté au code et aux données réelles, comme l'exige la discipline du projet, avant toute application. **Ce qui a été confirmé exact par recalcul indépendant** : l'entonnoir de rejet complet (16 098/3 706/713/402/251/172), la répartition de l'unanimité 4/4 sur 5 352 candidats (5 278/19/28/11/16), le scénario réellement bloquant en premier (`offensif` : 5 309, loin devant les 3 autres), et surtout la découverte que `archetype_model` est un **Poisson indépendant, pas un Dixon-Coles** (`poisson/distribution.py` : "P(X=x,Y=y)=P(X=x)×P(Y=y)", aucun ρ/τ nulle part) — appellation à corriger dans toute communication future. **Ce qui s'est révélé faux** : l'affirmation que `python audit_permanent.py` produit 4 échecs liés au titre Betpawa — exécution réelle : 289 `[OK]`, 0 `[FAIL]`, `AUDIT OK`. Le bureau avait cité un détail réel du code (`_g5_titre_fmt` contient bien une date codée en dur "29/08") mais en a tiré une conséquence fausse (le test est entièrement mocké, ne dépend d'aucune date réelle, et passe). **Conclusion opérationnelle : aucune recommandation externe n'est appliquée sans reproduction indépendante sur ce dépôt — règle déjà en vigueur, confirmée nécessaire par ce cas concret.**

### 30.3 Extension du périmètre : implémentation
`analyse_match_complet()` recalcule désormais directement `matrice_scores`/`distribution_marginale` par scénario à partir des λ déjà obtenus (calcul pur, aucun fetch réseau supplémentaire), au lieu de dépendre uniquement des lignes par défaut de `poisson.markets.calcule_tous_les_marches` — nécessaire pour couvrir les lignes réellement cotées hors des lignes par défaut (Over/Under jusqu'à 7.5, Handicap jusqu'à ±2.5). Une boucle unique parcourt `cotes.items()`, ignore les clés déjà couvertes par les 12 appels `_ajoute()` historiques (inchangés, zéro régression), et construit dynamiquement `market_family`/`exposure_group` par type de marché :
- Double Chance : famille `DOUBLE_CHANCE`, groupe `GROUPE_RESULTAT` (partagé avec 1X2 — corrélation directe, dedup ne gardera qu'un seul candidat sur tout le groupe)
- Over/Under (toutes lignes) et buts par équipe (lignes hors 0.5) : groupe `GROUPE_BUTS`, comme Over 2.5/BTTS/Parité déjà en place
- Handicap (toutes lignes) : **nouveau groupe `GROUPE_HANDICAP`**, distinct de RESULTAT et BUTS — conséquence positive : P3 (qui exige un 3e groupe distinct de P1 et P2) peut désormais réellement se déclencher, ce qui était quasi impossible avec seulement 2 groupes en périmètre v1 (voir remarque de §28.10 sur ce point précis)
- Convention handicap extérieur reprise du précédent déjà existant dans `h2h_markets.evalue_handicap` : la ligne s'applique toujours au domicile, "extérieur" = `perte` côté domicile — pas une nouvelle convention inventée.

`odds_provider._parse_libelle` couvrait déjà 100 % des libellés réels observés dans `TOUS_MARCHES_EVALUES` (0 libellé non reconnu sur les 64 distincts du run réel) — aucune modification nécessaire côté traduction texte→clé pour ce périmètre de base.

### 30.4 Marchés combinés DC+Total : probabilité conjointe correcte, garde-fou anti-corrélation testé
`poisson.markets.probabilite_combo_dc_total` calcule déjà la probabilité **conjointe** (jamais un produit naïf DC×Total, les deux dépendent du même score) — code réutilisé tel quel, correct par construction. Le risque n'était pas le calcul mais la **sélection** : un combo et son composant (même sélection DC, ou même ligne+sens Total) pourraient être sélectionnés tous les deux, doublant l'exposition au même évènement. `deduplication.py` ne gère qu'un seul groupe d'exposition par candidat, insuffisant pour un marché corrélé à deux groupes différents à la fois (RESULTAT via DC, BUTS via Total) — un exposure_group commun n'aurait couvert qu'une seule des deux corrélations. Solution retenue : un **garde-fou explicite** dans `analyse_match_complet()`, après construction de tous les candidats et avant dédoublonnage, qui retire un combo si son composant DC exact OU son composant Total exact (ligne ET sens) est lui-même éligible sur le même match. Testé sur 6 cas dans `audit_permanent.py` (3 qui doivent accepter le combo : isolé, DC sur sélection différente, Total sur ligne différente ; 3 qui doivent le rejeter proprement sans toucher aux autres candidats : composant DC exact présent, composant Total exact présent, les deux présents) — tous corrects.

**Sans effet sur les données réelles actuelles** : zéro libellé combo dans `TOUS_MARCHES_EVALUES` sur les 446 matchs du run réel — pas que betPawa ne les propose pas (capture d'écran réelle fournie par Patrick le confirme), mais que `scraper_betpawa.py` ne les extrait pas encore. Le calcul et le garde-fou sont prêts et testés ; activer réellement ces marchés est un chantier séparé sur le scraper, pas sur `archetype_model`.

### 30.5 Ce qui reste explicitement écarté de ce périmètre, et pourquoi
Marchés mi-temps (Première/Deuxième MT, intervalles, Mi-Temps/Fin de Match) : aucun λ n'a jamais été calculé pour une demi-période, hors périmètre déjà établi avant ce chantier. Buteur à tout moment / Équipe qui marque dernière / Prochain but : nécessitent des données par joueur ou un modèle d'ordre temporel des buts, qu'une matrice de Poisson jointe (score final uniquement) ne peut pas fournir. Handicap à 3 choix : structure différente (push coté séparément) du handicap à 2 choix déjà codé, formule non écrite. Remboursé si nul, Nombre exact de buts, Écart de victoire, Score exact : formules non encore écrites dans `poisson/markets.py` (pas du simple câblage) — non ajoutées dans la précipitation, chantier séparé avec ses propres tests si Patrick le demande.

### 30.6 Vérification finale — rejeu du vrai `analyse_match_complet()`, pas une simulation à côté
Les chiffres 68/48 proviennent d'un rejeu du code de production réel (`analyse_match_complet()` non modifié dans sa logique, seul `analyse_match()` est monkeypatché pour réinjecter les λ/fenêtres déjà stockés dans `precalcul.json` plutôt que de refaire un fetch réseau matchendirect.fr indisponible depuis l'environnement d'édition) sur les 446 matchs réels du run du 10/09/2026 — jamais une réimplémentation parallèle de la logique de filtre/dédoublonnage/sélection. Ces deux valeurs sont désormais figées dans `audit_permanent.py` comme non-régression.

### 30.7 Ce qui reste ouvert, pour la session suivante
- 🆕 **Le run avec ce nouveau périmètre n'a pas encore été exécuté en conditions réelles** (GitHub Actions) — seul le rejeu offline sur les données du run précédent a été fait. Premier vrai run avec ce code à surveiller normalement (durée, erreurs techniques, répartition `moteur_utilise`).
- 🆕 **Vérification des pronostics réels contre résultats** (13 du run du 10/09, bientôt 48 avec ce périmètre) : toujours aucune archive dédiée à `archetype_model` — chantier d'archivage toujours à faire, priorité inchangée depuis §29.10.
- 🆕 **Retour du bureau d'étude** : sa recommandation centrale (construire un vrai backtest walk-forward avant de toucher aux seuils) reste valide et non traitée — le chantier de cette session a porté sur le PÉRIMÈTRE de marchés, pas sur la calibration des constantes, qui reste hors sujet tant que le backtest n'existe pas.
- 🆕 **Activation réelle des combos DC+Total** : nécessite d'abord que `scraper_betpawa.py` extraie ces libellés dans `TOUS_MARCHES_EVALUES`, puis un parsing dans `odds_provider._parse_libelle` construit sur un vrai exemple de texte scrapé (pas deviné) — chantier séparé, pas commencé.
- ⬜ Le reste de §29.10 (référentiel central formel, `validation/`, coût réseau du double appel) : toujours non prioritaire.

## 31. Session du 10/09/2026 (suite) — Justification chiffrée réelle + refonte de l'affichage des pronostics

### 31.1 Refonte de l'affichage (archetype.html / archetype.js / style.css / traduction_marches.js)
Sur demande de Patrick (maquette fournie), la carte de pronostic est passée d'une ligne technique brute à une présentation en langage clair, sans aucune abréviation visible (pas de P1/P2/P3, H2H, EDV) : "Le meilleur choix / Meilleure rentabilité / Pronostic bonus", marché traduit ("Moins de 3,5 buts" au lieu de `over_under_total_3.5_under`), cote et probabilité mises en avant avant les métriques secondaires. Nouveau fichier `traduction_marches.js` : traduction pure (aucun calcul) des clés techniques de marché vers un libellé français, couvrant tous les marchés actuellement câblés dans `main.py` (base + périmètre dynamique + combos). `archetype.js` réécrit sur le même principe qu'avant (aucun calcul côté frontend, affiche uniquement la décision déjà produite). Si P2 ou P3 n'existe pas réellement pour un match, la carte l'affiche explicitement ("Aucun pronostic n'a passé tous les critères du modèle pour ce rang") -- jamais un faux 3e pronostic.

### 31.2 Nouveau module `archetype_model/justification.py` — comptage historique réel, jamais décisionnel
Patrick a demandé d'aller au bout du chantier plutôt que de se contenter d'une phrase générique : les phrases "Pourquoi ?" citent maintenant un chiffre réel ("7 des 8 derniers matchs comparables, 88 %"), calculé sur les mêmes matchs déjà chargés pour les lambdas (`fenetres.A/B.matchs_retenus`), jamais une nouvelle source de données. Convention : "domicile"/"extérieur" = le rôle joué AUJOURD'HUI (équipe A à domicile -> ses matchs passés à domicile ; équipe B à l'extérieur -> ses matchs passés à l'extérieur), identique à celle déjà utilisée par `lambda_estimators.py`. Résultat/victoire/nul dérivés de `buts_marques` vs `buts_encaisses`, comme `team_stats.resultats()` le fait déjà pour l'ancien usage descriptif -- réutilisation d'un principe déjà validé dans le projet, pas une nouvelle méthode inventée.

Couverture : 1X2, Double Chance, BTTS, Over/Under (toutes lignes), buts par équipe, cage inviolée/encaisse, parité, Handicap. **Non couvert, volontairement : les combos** -- le calcul conjoint correct nécessiterait de vérifier que les deux conditions se sont produites dans le même match historique, pas juste séparément ; `confirmation_historique()` renvoie `None` plutôt qu'un chiffre approximatif, et l'affichage se rabat proprement sur la phrase générique dans ce cas.

**Invariant vérifié par calcul, pas par lecture du code** (nouveau test dans `audit_permanent.py`) : un même match rejoué avec des `matchs_retenus` falsifiés à l'extrême (une équipe à 9-0 systématique, l'autre à 0-9) donne un comptage de confirmation complètement différent, MAIS une sélection P1 strictement identique (même marché, même edge, même edv, même niveau) -- preuve que ce nouveau champ ne peut pas influencer la décision, exactement la garantie que Patrick exige à chaque ajout.

Champs additionnels sur chaque candidat (base et dynamique) : `probabilite` et `cote` étaient déjà calculés mais jamais exposés sur l'objet candidat -- corrigé au passage (nécessaire pour que la jauge de probabilité de la nouvelle carte affiche un vrai chiffre au lieu de rien).

### 31.3 Vérifications
`audit_permanent.py` : 307 vérités, 0 échec (299 précédentes + 6 cas de `confirmation_historique` + 2 tests d'invariant). Rejeu réel sur les 446 matchs du fixture : toujours 68 candidats 4/4, 48 matchs avec un P1 réel -- strictement inchangé, confirmant que l'ajout est purement additif.

### 31.4 Ce qui reste ouvert
- Rendu visuel vérifié par capture d'écran réelle (wkhtmltoimage, faute d'accès réseau à un navigateur headless plus moderne) -- `conic-gradient` abandonné au profit d'un anneau SVG après un premier essai qui ne s'affichait pas ; `inset: 0` remplacé par les 4 propriétés explicites pour la même raison de compatibilité.
- La phrase de confirmation pour les combos reste générique -- traiter proprement le comptage conjoint est un chantier séparé si les combos sont un jour réellement exploités (voir §30.4/30.7, toujours bloqué sur le scraper).
- Le rendu réel sur téléphone (Safari iOS, l'usage réel de Patrick) n'a pas pu être vérifié directement dans cet environnement -- à confirmer par Patrick après déploiement.

## 32. Session du 11/09/2026 — Découverte et audit du système modifié en parallèle (nouvelle interface + justification enrichie), transition vers une nouvelle fenêtre

### 32.1 Contexte
Patrick a continué à coder dans une autre fenêtre pendant que la session ici était bloquée (limite de conversation), pour ne pas interrompre le travail. Cette session a consisté à **découvrir et auditer** ce qui avait été fait ailleurs, jamais à le deviner ou à le prendre sur parole — vérification directe du dépôt réel (`api.github.com/.../git/trees` puis `codeload.github.com` pour le contenu complet, l'API seule étant vite limitée en débit).

### 32.2 Ce qui a été fait ailleurs (vérifié, pas supposé)
- **`archetype.html`/`archetype.js` entièrement refaits** : nouvelle identité visuelle (écussons avec initiales d'équipe plutôt que de faux logos, dégradés or/turquoise/violet par rang P1/P2/P3, jauge circulaire SVG, étoiles de confiance, nom de marché en police serif). Fidèle à la maquette d'origine de Patrick — vérifié par capture d'écran réelle (wkhtmltoimage), pas seulement par lecture du code.
- **`justification.py` déplacé à la racine du dépôt** (hors du package `archetype_model/`), importé en absolu (`import justification`) depuis `archetype_model/main.py` -- fonctionne (cohérent avec le reste du dépôt qui importe déjà tout en absolu depuis la racine), mais casse tout ce qui référençait encore l'ancien chemin `archetype_model.justification`.
- **Nouvelle fonction `construit_justification()`**, bien plus rigoureuse que la version `confirmation_historique()` de la session précédente : n'affiche une preuve chiffrée ("7/8 derniers matchs...") que si l'échantillon est suffisant (**≥ 5 matchs**) ET le taux favorable (**≥ 60 %**) -- sinon un résumé qualitatif générique est affiché à la place, jamais un chiffre approximatif. Intègre aussi le H2H comme preuve séparée ("Confrontations directes"), plafonne à 3 preuves par sélection (2 fréquences + 1 H2H/moyenne, H2H priorisé si disponible). `confirmation_historique()` est conservée comme adaptateur de compatibilité au-dessus (renvoie la première preuve chiffrée suffisante), mais n'est plus utilisée par l'affichage -- `archetype.js` lit désormais `candidat.justification.{resume,preuves}` directement.
- **`parseBetpawa.js`** (portage JS de `parse_betpawa.py`) présent à la racine mais **non référencé par aucune page HTML** -- travail en cours, pas encore branché.

### 32.3 Bugs trouvés et corrigés dans `audit_permanent.py` (le seul fichier livré cette session)
1. **Crash immédiat** (`ModuleNotFoundError: No module named 'archetype_model.justification'`) -- l'audit importait encore l'ancien chemin. Corrigé en `import justification`.
2. **3 tests devenus obsolètes, pas le code** : le changement de contrat de `confirmation_historique()` (seuil qualité ≥5/≥60%, voir 32.2) faisait légitimement échouer 3 tests écrits sous l'ancien contrat (qui acceptait tout échantillon non vide). Réécrits pour vérifier le VRAI contrat actuel : échantillon insuffisant → `None` même à 100 % de réussite ; taux insuffisant → `None` même sur 6 matchs.
3. **6 nouveaux tests ajoutés pour `construit_justification()`** elle-même (jamais testée directement avant cette session, alors que c'est la fonction réellement utilisée par l'affichage) : preuve chiffrée réelle avec nom d'équipe, intégration H2H, plafond à 3 preuves, échantillon insuffisant → repli propre, marché combo non géré → repli propre, marché inconnu → repli propre. Chaque cas vérifié à la main avant d'être figé.

**Résultat final : 313 vérités, 0 échec.** Fichier `audit_permanent.py` corrigé livré à Patrick pour remplacement dans le dépôt (pas encore confirmé appliqué à la fin de cette session -- **à vérifier en priorité en reprise**).

### 32.4 Chantier explicitement annulé cette session
Un chantier de retrait des informations affichées de l'ancien moteur (`script.js`/`pronostics.html`/bouton "Analyser le panier" dans `panier.js`) avait été commencé puis **annulé par Patrick en cours de route** ("elle ne servira plus à rien j'ai continué de coder ailleurs") -- rien de ce chantier n'a été livré ni appliqué. L'ancien moteur et son affichage restent tels quels pour l'instant. Si ce retrait est toujours souhaité, c'est une demande à reformuler explicitement en reprise, pas à supposer.

### 32.5 Limite connue, non résolue
Le test de non-régression 68/48 (rejeu sur les 446 matchs du fixture figé, `fixture_rejeu_10092026.json`) ne fait PAS transiter d'historique réel dans `construit_justification()` -- la fixture date d'avant ce chantier de justification et ne contient pas `_historique_justification`/confrontations H2H. Ce test vérifie donc toujours la non-régression de la DÉCISION (P1/P2/P3, edge, edv -- inchangés, 68/48 confirmés), mais PAS que la justification affichée est correctement peuplée en conditions réelles de bout en bout -- seuls les tests unitaires directs sur `construit_justification()` (32.3, point 3) couvrent ça, de façon isolée. À combler si une garantie de bout en bout est souhaitée.

### 32.6 Priorité de la prochaine session
Patrick contrôle en ce moment (autre fenêtre) le comportement réel du nouveau système sur le run de la nuit. À la reprise, vérifier en priorité, sur le dépôt réel (jamais sur la mémoire de cette session) :
1. Le run de la nuit s'est-il terminé sans exception ? (logs GitHub Actions)
2. Le correctif d'`audit_permanent.py` (32.3) a-t-il été appliqué au dépôt ?
3. `candidat.justification.preuves` contient-il des preuves chiffrées réelles sur au moins quelques matchs du run (pas seulement des résumés génériques faute de `_historique_justification` correctement peuplé en production) ?
4. Quelles sont les "légères modifications" que Patrick a en tête -- à demander explicitement, pas à deviner.

## 33. Session du 12/09/2026 — Vérification du run de nuit + Chantier "raison réelle du choix" (justification), combo couvert

### 33.1 Vérification de la priorité de la session 32
Sur le dépôt réel (codeload + logs GitHub Actions fournis par Patrick, jamais sur la mémoire de session précédente) :
1. **Run de la nuit terminé sans exception** : confirmé par les vrais logs Actions (commit `447696e` poussé avec succès). Seule anomalie : une équipe (Farmel, Indonésie) avec une page matchendirect en 404 -- gérée proprement (saison ignorée), pas un crash.
2. **Correctif `audit_permanent.py` (32.3) appliqué** : confirmé -- `import justification` correct, plus aucune référence à l'ancien chemin cassé. Réexécuté réellement (pas relu) : 313 vérités, 0 échec au début de cette session.
3. **`candidat.justification.preuves` réel en production** : confirmé avec des chiffres du run réel -- 42 P1 sur 943 signaux, dont 23/42 avec preuve chiffrée réelle, 19/42 en repli générique (attendu quand l'échantillon ne passe pas le seuil ≥5/≥60%, pas un bug).
4. **Point noté, pas résolu** : le run de cette nuit a pris 4h44 contre 33m37s pour un run antérieur (commentaire dans `pipeline.yml`) -- sous la limite de 6h GitHub Actions mais x8, à surveiller.

### 33.2 Découvertes importantes avant tout chantier
- **`historique_v0.jsonl`** (50 Mo, 5939 lignes) : AUCUNE ligne n'a `resultat_reel` rempli (0/5939, dont 940 verdicts "GO"). Le mécanisme de calibration voulu par Patrick n'a rien à calibrer aujourd'hui -- aucun résultat réel n'est jamais rattaché.
- **`historique_pronostics.json`/`verification_resultats.py`/`calcule_roi.py`** ne connaissent QUE l'ancien moteur (schéma `LISTE_B_liste_finale_apres_correlation`, etc.) -- `archetype_model` (le moteur en production depuis le 09-10/09) n'est vérifié NULLE PART contre les résultats réels. Le tableau ROI actuel (64,3%, -7,1%) ne parle donc que de l'ancien moteur.
- **Git history récupérable** : ~156 pronostics réels d'`archetype_model` sur des matchs déjà joués (09-10 matin/soir, 09-11, 09-12) existent dans l'historique Git de `precalcul.json` mais ne sont archivés nulle part -- récupérables si on le fait avant que Patrick ne demande un nettoyage complet des données.
- **Décision de Patrick** : ne PAS effacer les données avant d'avoir récupéré ces résultats réels. Chantier de récupération + vraie architecture d'archivage **mis en pause**, pas abandonné -- à reprendre en session dédiée.
- **Décision de Patrick sur le signal** : la sélection P1/P2/P3 doit rester une procédure "totalement indépendante et isolée" -- le chantier d'extension du `signal_direction`/`signal_frequence` (`statistiques_signal.py`) à Handicap/combos/etc. (évoqué un temps comme "Chantier C") est **abandonné**, parce qu'il aurait ajouté un vrai critère de décision à la sélection, pas juste enrichi l'affichage. Ne pas le reproposer sans une demande explicite et séparée.

### 33.3 Chantier livré cette session : la vraie raison du choix (justification)
**Confirmé au préalable, par du code déjà en place et un test dédié** : la justification affichée n'a jamais influencé et n'influencera jamais la sélection P1/P2/P3 -- ce sont deux mécanismes complètement séparés (`selector.py`/`convergence.py` pour la décision, `justification.py` pour l'explication après coup).

**Problème réel confirmé dans le code avant de coder quoi que ce soit** : `construit_justification()` ne connaissait que l'historique de fréquence (matchs passés) -- jamais les vrais champs de décision (`niveau`, `robustesse`, `signal_direction`/`frequence`, `h2h_palier`, `edv`). La phrase affichée comme "pourquoi ce choix" ne reflétait donc jamais la vraie cascade de sélection (`niveau` → `robustesse` → `signal` → `H2H` → `EDV`, `signals/selector.py`).

**Solution implémentée, purement additive, sélection jamais touchée :**
- `archetype_model/signals/selector.py` : ajout de `diagnostique_differenciation()`/`diagnostique_p1/p2/p3()`/`diagnostique_selection()` -- PUR diagnostic après coup, reproduit à l'identique les conditions d'éligibilité de `selectionner_p2/p3` (jamais appelé PAR elles), détermine quel critère de la cascade a réellement différencié le gagnant du meilleur concurrent resté sur le carreau.
- `justification.py` : ajout de `construit_raison_selection()` (traduit le diagnostic en phrase française, jamais l'inverse) et `enrichit_justification_selection()` (fusionne la raison réelle avec l'historique déjà construit -- l'ancien résumé historique devient une preuve "Tendance historique" au lieu d'être présenté comme LA raison). Ajout aussi de la gestion du marché **combo** (DC+Total), absente jusqu'ici -- demande explicite de Patrick, vérifiée : aucun combo n'a d'ailleurs été généré sur le run de cette nuit (0/59 candidats), donc ce trou n'avait pas encore causé de dégât visible.
- `archetype_model/main.py` : un seul appel ajouté après `selector.selectionner()`, jamais avant.
- `precalcul.py` et `archetype.js` : **aucun changement nécessaire** -- ils lisent déjà exactement les clés (`resume`/`preuves`/`donnees_suffisantes`) produites par la nouvelle justification.

**Vérifications réelles effectuées** (pas seulement des tests unitaires) :
- Rejeu 68/48 sur les 446 matchs du fixture : **inchangé à l'identique** (preuve que la sélection elle-même n'a pas bougé).
- Résultat visuellement inspecté sur 3 vrais matchs du fixture (ex. Clermont-US Boulogne : "C'est ce niveau d'éligibilité, supérieur à celui du meilleur marché concurrent, qui l'a distingué.") -- phrase vraie, pas reconstituée.
- `audit_permanent.py` : 313 → **333 vérités, 0 échec**. Un test existant (`construit_justification CAS 5`) corrigé car il testait un changement de contrat volontaire de cette session (combo non géré → combo géré) ; une erreur de calcul manuel dans un nouveau test (CAS 5ter, 5/5 au lieu de 4/5) trouvée et corrigée avant livraison, pas après.

### 33.4 À reprendre en priorité
1. Récupération des résultats réels pour `historique_v0.jsonl` et les ~156 pronostics `archetype_model` orphelins dans l'historique Git (33.2), avant toute calibration ou nettoyage.
2. Construction d'une vraie architecture d'archivage/vérification pour `archetype_model` (aucune aujourd'hui).
3. Confirmer que le nouveau texte de justification s'affiche correctement une fois en production (prochain run réel).

## 34. Session du 13/09/2026 — archive.py livré par le bureau d'étude, base corrigée avant intégration

Le bureau d'étude a livré `archetype_model/learning/archive.py` (catégories SELECTED/COUNTERFACTUAL, catégorie B en compteur seul, transition de catégorie autorisée tant que PENDING, verrou RESOLVED immuable, écriture atomique). Code inspecté intégralement : conforme au contrat verrouillé la veille.

**Problème trouvé avant intégration** : leur `audit_permanent.py` livré (3576 lignes) était bâti sur un instantané du dépôt antérieur au Chantier B du 12/09 (justification/raison réelle du choix) — n'ayant jamais reçu le zip complet du dépôt, ils travaillaient sur une base obsolète. Conséquence vérifiée : import cassé (`archetype_model.justification` au lieu de `justification`, le bug déjà corrigé en session 32), et ~300 lignes de tests Chantier B absentes. Leur relance de l'audit annonçait "4 vérités déjà défaillantes sur Betpawa" -- en réalité un crash complet (`ModuleNotFoundError`), jamais 4 échecs propres.

**Correction effectuée** : leur section de tests ("ARCHIVAGE archetype_model — catégorie A/B et immutabilité", 5 vérités) extraite et greffée sur le vrai fichier actuel du dépôt (celui avec Chantier B), à la bonne place (après l'INVARIANT capital Chantier B, avant le bloc final). Réexécuté réellement : **338 vérités, 0 échec**, exit code 0. Rejeu 68/48 confirmé inchangé. Les "4 vérités Betpawa" n'existent pas sur la vraie base -- c'était un artefact de leur instantané obsolète, pas un problème réel.

**Décision de Patrick** : le bureau d'étude a rempli son rôle de conception (cahier des charges v2 + Addendum 1 + Addendum 2 + contrat archive.py). La suite (resultats.py, observations.py, matrice.py, calibration.py, etc.) est reprise directement en session, sans repasser par eux.

**À reprendre en priorité la prochaine session** : `resultats.py` -- doit réutiliser scraper.py/scraper_details.py tels quels, résoudre à la fois les enregistrements SELECTED et COUNTERFACTUAL avec la même fonction de règlement (Annexe A complète, sans "etc."), jamais de perte par défaut sur un marché inconnu.

## 35. Session du 13/09/2026 — resultats.py et reglement.py implémentés directement (bureau d'étude non ressollicité)

Suite à la session 34, Patrick a confirmé que le bureau d'étude avait rempli son rôle et a demandé de reprendre l'implémentation directement, sans repasser par eux.

**Livré** :
- `archetype_model/learning/reglement.py` (nouveau) : fonction pure `evaluer_marche(marche, buts_dom, buts_ext)`, sans I/O ni réseau, couverture EXHAUSTIVE des 19 motifs de l'Annexe A + combos DC/Total, aucun "etc.". Marché non reconnu → `MARCHE_NON_RECONNU` explicite, jamais une perte par défaut. Isolé de `resultats.py` (écart volontaire par rapport au contrat initial du bureau d'étude, validé par Patrick) pour que `contrefactuel.py` puisse le réutiliser plus tard sans dépendre du scraping.
- `archetype_model/learning/resultats.py` (nouveau) : réutilise à l'identique `scraper.url_resultat_foot/fetch_html/parse_matches`, `scraper_details._memes_equipes`, `run_pipeline.aujourdhui_france`. Résout **à la fois** les enregistrements `SELECTED` et `COUNTERFACTUAL` avec la même fonction de règlement — c'est la correction exigée le 12/09/2026. Reproduit exactement la logique d'abandon de `verification_resultats.py` (jour trop ancien → `NON_RESOLU_DEFINITIF` sans tentative réseau, jour d'aujourd'hui → jamais traité, `NB_JOURS_MAX_A_VERIFIER = 10` identique).
- `audit_permanent.py` : ajouts uniquement. 40 cas de règlement (un gagnant + un perdant par motif, calculés indépendamment avant écriture — une erreur de calcul manuel trouvée et corrigée avant livraison, comme en session 33) + 9 tests d'intégration `resultats.py` (SELECTED et COUNTERFACTUAL résolus ensemble, jour trop ancien, jour d'aujourd'hui, marché non reconnu jamais résolu en LOSS, deuxième passage idempotent).

**Bug de test trouvé et corrigé avant livraison** : les dates de test choisies tombaient toutes dans le même fichier archive mensuel (`2026-09.json`) — les assertions `[0]` sur la liste des enregistrements ne pointaient pas sur le bon match. Corrigé en filtrant explicitement par `match_id`, jamais par position.

**Vérifié réellement** : 313 (base) + 20 (Chantier B, session 32) + 5 (archive.py, session 34) + 40 + 9 (resultats.py, cette session, avec quelques ajustements) = **390 vérités, 0 échec**, exit code 0. Rejeu 68/48 confirmé inchangé.

**À reprendre en priorité** : `observations.py` puis `matrice.py` (transformer l'archive résolue en agrégats exploitables), avant `calibration.py`.

## 36. Session du 13/09/2026 (suite) — observations.py et matrice.py

**Livré** :
- `archetype_model/learning/observations.py` (nouveau) : `calcule_gain_flat_stake()` (mise=1.0, WIN→cote-1, LOSS→-1, jamais une valeur inventée si cote/résultat absents) et `construire_observations()` -- ne garde QUE les enregistrements `SELECTED` + `RESOLVED`. Les `COUNTERFACTUAL` sont explicitement exclus de la mesure de performance réelle (ils n'ont jamais été de vrais paris) -- confirmé par calcul et par test. `charge_toutes_les_archives()` concatène tous les fichiers `archive/*.json`.
- `archetype_model/learning/matrice.py` (nouveau) : `construire_matrice()`, agrégation hiérarchique GLOBAL → FAMILLE → NIVEAU (réponse retenue du bureau d'étude à la Question 6), purement mécanique -- ne juge jamais si un segment a assez de données (rôle futur de `garde_fous.py`). Famille/niveau absents → classés `INCONNUE`/`INCONNU`, jamais ignorés ni fusionnés.
- `audit_permanent.py` : 11 nouveaux tests, calculs vérifiés indépendamment avant écriture (aucune erreur trouvée cette fois).

**Vérifié réellement** : 390 (base) + 11 = **401 vérités, 0 échec**, exit code 0. Rejeu 68/48 confirmé inchangé.

**À reprendre en priorité** : `garde_fous.py` (taille d'échantillon minimale, amplitude maximale par cycle, dérive cumulée, versionnement, rollback -- section 6 du cahier des charges v2) avant `calibration.py` lui-même, puisque calibration.py ne doit jamais pouvoir promouvoir un ajustement sans passer par ce module.
