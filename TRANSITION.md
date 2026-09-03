# Archetype Foot — Document de transition
Dernière mise à jour : 03/09/2026 (session filtre de compétitions complet +
refonte visuelle — voir section 18, la plus longue et la plus large en
portée à ce jour : touche toutes les zones du monde, mais **le nouveau
filtre n'a jamais tourné en conditions réelles**, seulement testé contre
un instantané figé de données).
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

### 18.10 Ce qui reste à faire (priorités, dans l'ordre suggéré)
1. **`precalcul_leger.json` (18.1)** -- toujours cassé, diagnostic
   instrumenté mais jamais lu. Priorité absolue avant tout le reste.
2. **Vérifier le nouveau filtre de compétitions en conditions réelles**
   (18.3) -- lancer un run complet, vérifier que la fenêtre finale est
   cohérente (pas de championnat majeur disparu par erreur, volume
   nettement réduit comme attendu), vérifier que
   `matchs_du_jour_filtre.json`/`matchs_demain_filtre.json` se génèrent et
   se committent correctement (18.6).
3. **Mesurer l'impact réel sur la durée du run** maintenant que le filtre
   réduit la fenêtre à ~37% -- et vérifier si ça suffit à résoudre le
   problème de fond (18.7) ou si l'extension du cache classement/H2H reste
   nécessaire en complément.
4. **Revenir sur le bug Premier League/Serie A/La Liga (18.8)** si
   Patrick le redemande -- diagnostic à reprendre exactement où il a été
   laissé, ne pas repartir de zéro.
5. **Revenir sur la question du ROI réel du moteur** (0.1) -- toujours
   pas fait depuis le 30/08, malgré 3 sessions entières d'infrastructure
   depuis.
6. Points de confiance moyenne à vérifier dès qu'une vraie occasion se
   présente (18.4) : Chili "Superliga", Égypte "Première Ligue", Écosse/
   Belgique (mapping des paliers), Océanie (aucun match australien/néo-
   zélandais jamais vu dans une vraie fenêtre), "Ligue Conférence Phase
   de Ligue" (jamais vue en vrai).
7. Décider du sort du hook "semaine" mort dans `index.js`
   (`catalogue_unifie.json` inexistant, 18.6) -- le finir ou le
   supprimer.
8. Purge du cache Betpawa, couverture Betpawa réelle, Phase 5/6 de la
   feuille de route -- toujours non traités depuis la session 16.
