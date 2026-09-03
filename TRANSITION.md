# Archetype Foot — Document de transition
Dernière mise à jour : 01/09/2026 (session pré-calcul J+1/J+2/J+3 +
association automatique Betpawa, voir section 16 — nouvelle session la
plus longue à ce jour, contient la découverte la plus importante du
projet sur la récupération de cotes).
Objectif de ce document : permettre de reprendre le projet dans une nouvelle
fenêtre de conversation sans perdre l'historique de décisions, ni répéter
les erreurs déjà identifiées et corrigées.

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
- **⚠️ TOUJOURS NON REVÉRIFIÉ AU 01/09/2026** — la session 16 (pré-calcul +
  Betpawa) n'a pas touché à cette question. C'est la question la plus
  importante du projet restée sans réponse depuis le 30/08 : les
  correctifs de 0.2 (K_SHRINKAGE etc.) n'ont jamais été revalidés sur un
  nouvel échantillon. Toute l'infrastructure construite en session 16 rend
  le système plus rapide et plus riche en données, mais ne dit rien sur
  la rentabilité réelle du moteur.

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
volume suffisant au 01/09** (voir 0.1).

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
700px)`. Grille de cartes déjà intrinsèquement responsive.

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
  session 16 (voir plus bas) est le meilleur exemple à ce jour de cette
  discipline appliquée strictement : chaque hypothèse (scroll, filtre
  jour, sigle PSG, faux positif de nom) a été vérifiée par un test réel
  avant d'être actée, y compris quand ça demandait de recommencer
  plusieurs fois.
- **Dire clairement ce qui est confirmé, ce qui est probable, et ce qui est
  un pur best-effort non testé.**
- **Priorité au gratuit et au simple.**
- **Le scope se réduit consciemment plutôt que de s'étendre indéfiniment.**

---

## 2. Constantes gelées ("moteurs initiaux") — ne pas modifier sans repasser par un backtest

```
GA_REFERENCE_PAR_LIGUE (dict par pays, voir 0.2/0.3)
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

SEUIL_EV_MIN = 0.12
FOURCHETTE_COTE_MIN = 1.25
FOURCHETTE_COTE_MAX = 1.69
SEUIL_CORRELATION = 0.70
KELLY_FRACTION = 0.25
MISE_MAX_PARI = 0.04
CLUSTER_MAX = 0.10
NB_PARIS_MAX = 3
SEUIL_STANDOUT = 0.15

K_SHRINKAGE = 0.27
```

Marchés calculables : 1X2, Double Chance, BTTS, Over/Under (toutes
lignes), Handicap à 2 choix (lignes demi-entières), Score exact, Nombre
exact de buts, Pair/Impair, Cages inviolées.

---

## 3. Architecture actuelle (mise à jour session 16)

```
GitHub Actions (cron quotidien 0h UTC = 1h Douala + déclenchement manuel)
  → scraper.py           (matchs aujourd'hui/demain — matchendirect, HTTP
                           simple ; plafond de 200/jour RETIRÉ le 31/08,
                           voir 16.1 — était un vrai bug, pas voulu)
  → scraper_semaine.py   (matchs J+2 à J+7 — matchendirect, via Playwright,
                           tourne déjà chaque nuit en production, pas de
                           plafond)
  → scraper_betpawa.py   (cotes + marchés Betpawa POUR LES URLS DE
                           betpawa_urls.txt SEULEMENT — pas un scan
                           automatique, voir 16.2 pour la limite réelle
                           découverte ce jour-là)
  → scraper_details.py   (classement, H2H, forme -- matchendirect, HTTP simple)
  → calculs.py           (Poisson/Dixon-Coles/EV/Kelly, calibré par ligue -- 0.2)
  → precalcul.py         (NOUVEAU 31/08 — voir 16.3 — pré-calcul J+1/J+2/J+3
                           indépendant du panier, réutilise construit_signaux()
                           sans y toucher ; utilise cache_equipes.py)
  → cache_equipes.py     (NOUVEAU 31/08 — cache persistant des stats
                           GF/GA par équipe+compétition, voir 16.3)
  -- run planifié (schedule) --
  → run_pipeline.py      (orchestrateur, écrit data.json)
  → verification_resultats.py  (scores des jours passés -- 0.4)
  → commit + push automatique vers le dépôt
  -- run manuel (workflow_dispatch, panier_id) --
  → dispatch_pipeline.py (lit le panier Supabase par panier_id)

NOUVEAU 31/08-01/09 -- résolution d'identité Betpawa (voir section 16) :
  → resolution_betpawa.py (module de PRODUCTION, moteur à 3 tamis validé
                           sur 100 matchs réels : 37 trouvés / 3 ambigus /
                           60 non trouvés, ZÉRO faux positif -- règle
                           stricte : ne plus modifier sans repasser par un
                           test complet sur échantillon)
  → cache_betpawa.py      (cache persistant des correspondances CERTAINES
                           uniquement, jamais des AMBIGU/NON TROUVÉ, avec
                           traçabilité complète -- voir 16.5)
  -- PAS ENCORE BRANCHÉ dans precalcul.py ni pipeline.yml, voir 16.7 --

Netlify sert le dépôt en statique (index.html/panier.html/pronostics.html/
betpawa.html), Supabase pour l'isolation multi-utilisateur (0.5).
```

**Dépôt GitHub** : `Patzaza81/archetype-foot`, branche `main`.

---

## 4-14. [Sections historiques, inchangées depuis le 30/08 — voir versions
précédentes de ce document pour le détail complet : pages matchendirect
découvertes (section 4), décisions d'abandon (section 5), fragilités
connues (section 6, mise à jour ci-dessous en 16.8), architecture Betpawa
copier-coller/URL manuelle (section 15), etc. Pas reproduites intégralement
ici pour ne pas alourdir -- se référer à la version du 30/08 conservée dans
l'historique du dépôt/de la conversation précédente si le détail est
nécessaire.]

---

## 16. Session du 31/08-01/09/2026 — pré-calcul J+1/J+2/J+3 et résolution d'identité Betpawa

**La session la plus longue et la plus riche en détours de tout le projet
à ce jour.** Contient la découverte la plus importante du projet sur la
récupération de cotes réelles, mais uniquement après plusieurs pistes
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
se mesurera que sur plusieurs nuits consécutives, jamais vérifié sur plus
de 2 runs consécutifs à ce jour.

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
  construit à ce jour -- voir 16.7).

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
pas encore être indexé par la recherche Betpawa au moment du test, most
probable given qu'un autre match PSG plus proche (2 septembre, vs
Eintracht) existait bien. **Non confirmé formellement, à revérifier** si
le cas se reproduit.

**⚠️ Question méthodologique ouverte, soulevée par une relecture externe
(ChatGPT, sollicité par Patrick sur le même énoncé de problème)** : le
taux de 37% ne distingue pas "vraie absence du match sur Betpawa" de
"match présent mais raté par l'algorithme" -- aucun audit manuel
systématique des 60 non-trouvés n'a été fait à ce jour pour trancher.
Cette proposition externe a surtout reformulé l'architecture déjà
construite ici (peu d'apport nouveau), mais a soulevé cette question
valablement, ainsi que l'idée du cache de correspondances (voir 16.6,
retenue et construite) et la piste de paralléliser les recherches
Playwright pour la vitesse (évoquée, pas construite à ce jour).

### 16.6 Industrialisation -- `resolution_betpawa.py` + `cache_betpawa.py`
Sur demande explicite de Patrick, avec une règle stricte ("on ne touche
pas au moteur qui fonctionne déjà") :

- **`resolution_betpawa.py`** (NOUVEAU) : le moteur à 3 tamis, extrait tel
  quel du script de test validé, promu module de production stable.
  **Règle documentée en tête de fichier : ne plus modifier la logique des
  tamis sans repasser par un test complet sur échantillon** -- même
  discipline que `calculs.py`.
- **`cache_betpawa.py`** (NOUVEAU) : mémoire persistante des
  correspondances CERTAINES uniquement -- jamais un AMBIGU, jamais un NON
  TROUVÉ. Structure riche par match (pas juste `nom -> event_id`) :
  équipes source ET Betpawa, `event_id`, date, compétition, niveau de
  confiance, horodatage de vérification, tamis d'origine. Clé de cache =
  (domicile, exterieur, date) normalisés -- pertinent parce qu'un même
  match reste dans la fenêtre glissante J+1→J+2→J+3 jusqu'à 3 nuits de
  suite avant d'être joué, donc le cache évite de refaire toute la
  recherche+vérification chaque nuit pour un match déjà résolu. Fonction
  de purge écrite (`purge_matchs_joues`) mais jamais appelée
  automatiquement à ce jour.
- **Test de validation double-run réalisé et CONFIRMÉ (01/09/2026)** :
  lance les mêmes 100 matchs deux fois de suite, cache vide puis rempli.
  **Résultat : 40 trouvés / 2 ambigus identiques sur les deux runs (aucune
  dérive), 40/40 correspondances venues du cache au 2e passage, gain de
  temps réel de 47% (13m10s -> 6m57s, durée totale du test : 20 minutes).**
  Cache validé pour la mise en production. Note en passant : le run à vide
  (13 minutes pour 100 matchs) est nettement plus rapide que les 30-45
  minutes estimées lors du test V30 équivalent -- les optimisations
  successives du moteur (sélecteurs plus directs, moins de vérifications
  redondantes) ont aussi accéléré la résolution elle-même, indépendamment
  de l'effet du cache.

### 16.7 Ce qui reste à faire (priorités, dans l'ordre suggéré)
1. **Brancher `resolution_betpawa.py` + `cache_betpawa.py` dans
   `precalcul.py`** -- à ce jour, ces deux modules existent et sont
   validés en isolation (via `test_scraping_betpawa_liste.py`, un script
   diagnostic, PAS le pipeline réel, et le cache est maintenant confirmé
   fiable sur un double-run), mais rien ne les appelle depuis le vrai
   pré-calcul nocturne. C'est la prochaine étape concrète.
2. **Mesurer la vraie couverture Betpawa** en auditant manuellement un
   échantillon des "NON TROUVÉ" -- pour savoir si ~40% est un bon ou un
   mauvais score une fois la vraie limite du site connue (question
   soulevée en 16.5, jamais tranchée).
3. **Envisager la parallélisation** des recherches Playwright si le volume
   réel (600-800 matchs/nuit) rend le temps d'exécution actuel
   (environ 13 minutes pour 100 matchs sans cache, moins avec) inacceptable
   à l'échelle. Prudence à observer : risque de détection d'usage anormal
   par Betpawa si trop de requêtes simultanées.
4. **Revenir sur la question du ROI réel du moteur** (0.1, jamais
   revérifiée depuis le 30/08) -- reste la question la plus importante du
   projet indépendamment de tout le travail d'infrastructure de cette
   session. Toute cette session a amélioré la vitesse et la richesse des
   données, rien sur la rentabilité du moteur lui-même.
5. Programmer un appel périodique à `purge_matchs_joues()` pour
   `cache_betpawa.json`, sans quoi il grossira indéfiniment.
6. Reprendre la feuille de route plus ancienne (Phase 5 : frontend en
   lecture seule ; Phase 6 : mode administrateur) -- pas touchée du tout
   pendant cette session, entièrement concentrée sur le backend.

### 16.8 Mise à jour de la section 6 (fragilités connues)
En plus des points déjà listés au 30/08 (BUG de cote resté à confirmer en
prod, lieu/météo/arbitre jamais branchés, seuil de corrélation possiblement
trop haut) :
- **`resolution_betpawa.py`** : validé sur 100 matchs avec zéro faux
  positif détecté, mais reste une heuristique de ressemblance de texte +
  vérification de date -- pas une garantie absolue. Un futur cas piège
  non anticipé (deux matchs différents, mêmes deux noms d'équipe
  ressemblants, même date) reste théoriquement possible, quoique very
  improbable vu la double vérification.
- **`cache_betpawa.py`** : validé sur un double-run (100 matchs, 0 dérive,
  47% de gain de temps). Reste non testé sur plusieurs nuits réelles
  consécutives (matchs qui sortent de la fenêtre, cohérence du cache dans
  la durée) -- premier vrai test seulement en conditions de production.
- **`cache_equipes.py`** : même limite -- un seul cycle de comparaison
  avant/après observé (1h08m57s -> 58m26s), l'effet en régime stable sur
  plusieurs nuits consécutives n'est pas mesuré.
- **La recherche Betpawa ne trouve pas les sigles de club à 3 lettres**
  (confirmé sur PSG) -- `SIGLES_CONNUS` est une petite table manuelle,
  pas une solution générale ; tout sigle non listé échouera silencieusement
  (retournera "NON TROUVÉ", pas une erreur).
- **Couverture temporelle incertaine** : un match à J+3 peut ne pas encore
  être indexé par la recherche Betpawa au moment du scan (cas PSG-Monaco,
  16.5) -- si confirmé sur d'autres cas, le taux de détection réel pourrait
  être structurellement plus bas sur J+3 que sur J+1, question non
  tranchée à ce jour.
  ## 17. Session du 02/09/2026 -- Branchement Betpawa dans precalcul.py, archivage, frontend

### 17.1 Branchement resolution_betpawa.py + cache_betpawa.py dans precalcul.py -- FAIT ET VALIDÉ
Nouveau fichier **`resolution_betpawa_precalcul.py`** : pont entre les deux
modules déjà validés (16.6) et `precalcul.py`, sans modifier une seule
ligne de leur logique interne (règle stricte respectée). Pour chaque match
de la fenêtre J+1/J+2/J+3 : vérifie le cache, sinon lance
`resoudre_match()`, puis si trouvé récupère les cotes réelles via
`scraper_betpawa.recupere_page()` + `meilleur_parsing()`. Si cotes
trouvées : `cotes_manuelles` est injecté dans le match, ce qui fait
basculer `run_pipeline.construit_signaux()` sur ces cotes au lieu de
Bet365/matchendirect (mécanisme déjà existant dans run_pipeline.py,
inchangé). Jamais d'exception qui remonte -- tout est absorbé dans des
compteurs, écrit dans `diagnostic_precalcul_betpawa.txt` à chaque run.
Un paramètre `PRECALCUL_LIMITE_BETPAWA` (variable d'env, lue par
`resolution_betpawa_precalcul.py`) permet de plafonner le nombre de
matchs traités par Betpawa sur un run -- voir 17.3.

**Validé en conditions réelles à petite échelle (15 matchs, 01/09)** :
13/15 trouvés, cotes extraites, `verdict_global` calculé correctement à
partir des vraies cotes Betpawa (vérifié sur le JSON complet, pas
seulement un exemple) -- confirme que le branchement fonctionne de bout
en bout, pas seulement la résolution isolée.

**Validé à pleine échelle (1574 matchs, run automatique 02/09)** :
498 trouvés, 49 ambigus, 1027 non trouvés, 0 erreur. Durée de l'étape
Betpawa seule : **12428 secondes (~3h27m)**. Durée totale du job :
**5h18m51s**, à 40 minutes du mur des 6h de GitHub Actions -- **trop
proche de la limite pour être fiable en routine sans plafond** (voir
17.3).

### 17.2 Archivage automatique dans historique_pronostics.json -- CODE ÉCRIT, PAS ENCORE VÉRIFIÉ EN CONDITIONS RÉELLES
Problème identifié en cours de session : le pré-calcul nocturne produisait
des centaines de pronostics par nuit qui n'entraient jamais dans
`historique_pronostics.json` -- donc jamais utilisables par
`verification_resultats.py`, donc jamais comptés dans l'objectif
d'accumuler ~1000 matchs vérifiés avant de miser réellement (0.1).

**Solution retenue** : `archive_precalcul()` dans `precalcul.py`,
appelée après `construit_signaux()`. Deux décisions de conception à
retenir :
- **Version allégée** (`_slim_pour_archive`) -- pas les distributions de
  probabilité complètes, seulement ce qu'il faut pour calculer un ROI et
  vérifier le score plus tard (équipes, date, verdict, LISTE_B, etc.).
  Sans ça, le fichier grossirait de façon incontrôlable (chaque match
  archivé brut pèse plusieurs Ko).
- **Seuls les matchs dont la date est EXACTEMENT J+1 (demain) sont
  archivés** -- jamais J+2/J+3. Sans cette règle, un même match serait
  archivé jusqu'à 3 fois (une fois par nuit, à mesure qu'il descend de
  J+3 à J+1 dans la fenêtre), faussant tout calcul de ROI par triple
  comptage. Chaque match n'entre dans l'historique qu'une seule fois, la
  veille de son coup d'envoi.

**État de vérification réel, à ne pas confondre avec "ça marche"** : le
code existe et est raisonné, mais **aucun run n'a encore exécuté cette
version de `precalcul.py` avec succès à ce jour** -- le run automatique
du 02/09 (5h18m, voir 17.1) a tourné avec une version DU CODE ANTÉRIEURE
à cet ajout (course de vitesse entre le commit de Patrick et le
déclenchement du cron à 0h UTC). `historique_pronostics.json` ne contient
donc encore aucune entrée `"source": "precalcul_auto"` au moment où cette
section est écrite. **Prochaine étape immédiate à la reprise : vérifier
qu'un run avec le code à jour produit bien cette entrée.**

### 17.3 Incident -- limite de sécurité Betpawa appliquée deux fois trop tard
Le run automatique du 02/09 (cron 0h UTC) a tourné SANS AUCUNE limite sur
la résolution Betpawa (`PRECALCUL_LIMITE_BETPAWA` vide sur un événement
`schedule`, qui ne fournit jamais `github.event.inputs.*`) -- 5h18m51s de
durée, à 40 minutes du mur des 6h. **Deux fois de suite, Patrick a cru
avoir appliqué le correctif (`|| '100'` en repli sur la valeur de
l'input) et ne l'avait en réalité pas fait** -- confirmé les deux fois en
lisant directement le contenu du `pipeline.yml` du dépôt (zip uploadé),
pas en se fiant à une déclaration verbale. **Leçon opérationnelle
retenue pour la suite : ne jamais confirmer qu'un fichier a été
correctement remplacé sans le vérifier soi-même sur le contenu réel
transmis (zip du dépôt, ou copier-coller direct dans le message) --
jamais sur la seule affirmation de l'avoir fait.**

État à la fin de cette session : le correctif (`PRECALCUL_LIMITE_BETPAWA:
${{ github.event.inputs.limite_betpawa || '100' }}`) a été confirmé
appliqué par lecture directe du fichier. Reste à vérifier que le PROCHAIN
run planifié (cron suivant) respecte bien cette limite de 100 par défaut.

### 17.4 Frontend -- `/pronostics.html` connecté au pré-calcul automatique pour la première fois
Avant cette session, `/pronostics.html` ne lisait que `data.json` (résultat
du panier manuel) -- le pré-calcul nocturne, quel que soit son volume,
était entièrement invisible sur le site. Changements :
- **4 onglets** : J+1/J+2/J+3 (lisent le pré-calcul, dates calculées
  dynamiquement côté client à l'ouverture de la page, jamais codées en
  dur) + Panier (comportement `data.json`/Supabase strictement inchangé,
  conservé en parallèle sur décision explicite de Patrick).
- **Tri par défaut** : GO triés par EV décroissant en premier, puis
  NO_GO, puis non traités -- avant, les rares paris actionnables étaient
  noyés dans des centaines de matchs. Case à cocher "afficher seulement
  les GO" ajoutée en complément, filtre en mémoire (pas de refetch).
- **Correctif race condition** (trouvé et corrigé le jour même) : un
  changement rapide d'onglet pouvait laisser un fetch obsolète écraser
  l'affichage d'un onglet déjà quitté. Corrigé par un jeton
  d'affichage incrémenté à chaque changement d'onglet, vérifié avant
  tout rendu.

### 17.5 precalcul_leger.json -- CODE ÉCRIT, PAS ENCORE GÉNÉRÉ NI VÉRIFIÉ
`precalcul.json` est passé de 3,4 Mo (01/09, 831 matchs) à 9,2 Mo (02/09,
1574 matchs) -- chargé en entier par le site à chaque ouverture, sur une
connexion 3G annoncée par Patrick. Solution : `precalcul.py` écrit
désormais EN PLUS `precalcul_leger.json` (mêmes signaux, sans les champs
`marches` et `lambda`, les plus lourds et les moins utiles au quotidien --
le verdict, le pari recommandé, la cote et l'EV n'en dépendent jamais,
voir docstring de `_leger_pour_site`). `script.js` a été modifié pour
lire ce fichier léger au lieu de `precalcul.json`.

**État à la fin de la session : le fichier n'existe pas encore sur le
dépôt** -- confirmé par une erreur 404 sur le site
("`precalcul_leger.json introuvable`") au moment où cette section est
écrite, car aucun run n'a encore tourné avec cette version de
`precalcul.py`. Attendu au prochain run réussi. `pipeline.yml` a été mis
à jour pour committer ce nouveau fichier (`git add` complété).

### 17.6 Ce qui reste à faire (priorités, dans l'ordre suggéré)
1. **Vérifier le prochain run de bout en bout** : `precalcul_leger.json`
   existe et le site charge sans erreur 404 ; `historique_pronostics.json`
   contient une nouvelle entrée `"source": "precalcul_auto"` avec la
   bonne date (demain) ; la durée totale reste sous la limite grâce au
   plafond à 100 (17.3).
2. **Revenir sur la question du ROI réel du moteur** (0.1, toujours pas
   revérifiée) -- maintenant que l'archivage automatique existe (une fois
   vérifié), l'échantillon va enfin pouvoir grossir de façon significative
   chaque nuit sans dépendre du panier manuel. C'est le bon moment pour
   remettre cette question sur la table, comme prévu depuis le 16.7.4.
3. **Décider d'un vrai régime de `limite_betpawa`** en routine (100 est un
   choix prudent provisoire, pas un chiffre validé par une mesure de
   couverture réelle à cette valeur) -- ou avancer sur la parallélisation
   déjà évoquée en 16.7.3 si le volume complet doit un jour tourner sans
   limite de façon fiable.
4. Les points 16.7.2, 16.7.5, 16.7.6 (couverture Betpawa réelle, purge du
   cache, Phase 5/6 de la feuille de route) restent non traités, inchangés
   depuis la session précédente.
