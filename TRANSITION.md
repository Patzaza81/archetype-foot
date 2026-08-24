# Archetype Foot — Document de transition
Dernière mise à jour : 24/08/2026, dans la continuité d'une session longue.
Objectif de ce document : permettre de reprendre le projet dans une nouvelle
fenêtre de conversation sans perdre l'historique de décisions, ni répéter
les erreurs déjà identifiées et corrigées.

---

## 1. Philosophie du projet — non négociable

- **Les sources de données sont des outils à extraire, pas des cahiers des
  charges rigides.** Le document PythonAnywhere/Playwright fourni au départ
  n'a jamais été suivi tel quel — chaque choix technique a été revérifié en
  conditions réelles avant adoption.
- **Aucune affirmation sans vérification en conditions réelles.** Plusieurs
  erreurs de cette session viennent d'avoir cru un test insuffisant (mauvais
  paramètre d'URL, mauvaise méthode de test). La correction systématique :
  refaire le test, pas défendre la première conclusion.
- **Dire clairement ce qui est confirmé, ce qui est probable, et ce qui est
  un pur best-effort non testé.** Ne jamais présenter un best-effort comme
  une certitude.
- **Priorité au gratuit et au simple.** Toute solution payante ou nécessitant
  un navigateur automatisé (Playwright) a été écartée dès qu'une alternative
  HTTP simple et gratuite a été trouvée.
- **Le scope se réduit consciemment plutôt que de s'étendre indéfiniment.**
  Mi-temps abandonné, BeSoccer abandonné, comparateur multi-bookmakers jugé
  inutile — chaque abandon a une raison explicite, listée ci-dessous.

---

## 2. Constantes gelées ("moteurs initiaux") — ne pas modifier sans repasser par un backtest

Ces valeurs viennent du pipeline original (Modules 1-4) et sont déjà codées
dans `calculs.py` :

```
GA_REFERENCE = 1.35
BORNE_MIN_DEFENSE = 0.70
BORNE_MAX_DEFENSE = 1.30

POIDS_FORME = 0.30
POIDS_CLASSEMENT = 0.20
POIDS_REPOS = 0.15
POIDS_ABSENCES = 0.15
POIDS_DISTANCE = 0.10
POIDS_H2H = 0.10
BORNE_RATIO = 0.15

RHO_DIXON_COLES = -0.1

SEUIL_EV_MIN = 0.05
FOURCHETTE_COTE_MIN = 1.25
FOURCHETTE_COTE_MAX = 1.69
SEUIL_CORRELATION = 0.70
KELLY_FRACTION = 0.25
MISE_MAX_PARI = 0.04
CLUSTER_MAX = 0.10
NB_PARIS_MAX = 3
SEUIL_STANDOUT = 0.15
```

Marchés calculables (dérivés de la seule matrice Poisson/Dixon-Coles, aucune
donnée supplémentaire requise) : 1X2, Double Chance, BTTS, Over/Under (toutes
lignes), Handicap à 2 choix (lignes demi-entières uniquement — les lignes
entières avec push sont hors périmètre), Score exact, Nombre exact de buts,
Pair/Impair, Cages inviolées.

Marchés explicitement hors périmètre : tout marché mi-temps (décision
utilisateur du 24/08), tout marché non basé sur les buts (cartons, corners,
joueurs — aucun modèle statistique disponible ici).

---

## 3. Architecture actuelle

```
GitHub Actions (cron quotidien + déclenchement manuel)
  → scraper.py           (matchs du jour — matchendirect /live-foot/)
  → scraper_details.py   (classement, H2H, forme, cotes — matchendirect)
  → calculs.py           (Poisson/Dixon-Coles/EV/Kelly)
  → run_pipeline.py      (orchestrateur, écrit data.json)
  → commit + push automatique vers le dépôt
Netlify sert le dépôt en statique → index.html/script.js lisent data.json
```

**Dépôt GitHub** : `Patzaza81/archetype-foot`, branche `main`, tous les
fichiers à la racine (pas de sous-dossiers sauf `.github/workflows/`,
imposé par GitHub).

**Site Netlify** : connecté au dépôt via import Git (pas de déploiement
manuel "Drop" — celui-là a été abandonné, voir section 5).

**Aucune API tierce, aucun navigateur automatisé (Playwright) dans
l'architecture actuelle.** Tout est en HTTP simple (`requests` +
`BeautifulSoup`/`pandas.read_html`).

---

## 4. Toutes les pages matchendirect découvertes — liste exhaustive

**Clarification importante avant la liste** : le document génèse (section 9,
zip joint) mentionne besoccer.com, FotMob et Sofascore comme sources
complémentaires. **Pour l'instant, matchendirect seul suffit largement** —
aucune de ces sources n'a été nécessaire pour construire ce qui existe déjà,
et BeSoccer s'est révélé bloqué (protection anti-bot, voir section 5). Ne
pas aller chercher une source supplémentaire tant que matchendirect n'a pas
montré une vraie limite concrète (championnat non couvert, donnée absente
confirmée après recherche réelle sur le site).

### Pages confirmées server-rendues (HTTP simple, sans navigateur)

| # | URL / motif | Contenu | Fonction actuelle |
|---|---|---|---|
| 1 | `matchendirect.fr/live-foot/` | Matchs du jour : équipes, score, compétition, lien vers chaque match | `scraper.py::scrape_programme_du_jour` — ✅ branché, fonctionne en prod |
| 2 | `matchendirect.fr/live-score/{slug}_{id}.html` | Page par défaut d'un match : lieu, météo, arbitre, diffuseur, score mi-temps inline si joué | Non branché — donnée perdue actuellement |
| 3 | `matchendirect.fr/live-score/{slug}_{id}.html?p=face-a-face` | Forme 5 derniers matchs (par équipe, dom/ext séparés), H2H complet avec mi-temps, cotes multi-bookmakers (1N2/DC/MT-FM/BTTS/O-U 0.5-7.5) | `scraper_details.py::recupere_h2h` et `recupere_cotes_marches` — codé, jamais testé en conditions réelles |
| 4 | `matchendirect.fr/live-score/{slug}_{id}.html?p=classement` | Mini classement autour des deux équipes (aperçu, pas la page complète) | Non exploré séparément — un aperçu apparaît déjà inclus dans la page `?p=face-a-face` |
| 5 | `matchendirect.fr/live-score/{slug}_{id}.html?p=compositions` | Compositions d'équipe probables/officielles | Jamais récupéré, jamais vérifié serveur-rendu ou non |
| 6 | `matchendirect.fr/classement-foot/{pays}/{comp}.html` (+ `?p=home` / `?p=away`) | Classement Général/Domicile/Extérieur complet de la saison | `scraper_details.py::recupere_classement` — codé, bug StringIO corrigé mais **non re-testé** |
| 7 | `matchendirect.fr/statistique/{eq1}-contre-{eq2}.html` | 20 derniers résultats par équipe, stats pré-match (% +2,5 buts, % victoires, % clean sheet), tableau H2H résumé, mini classement | `scraper_details.py::recupere_20_derniers_resultats` — codé, **bloqué** : ordre du slug `{eq1}-contre-{eq2}` non déterministe (voir section 7) |
| 8 | `matchendirect.fr/equipe/{slug}.html` (+ `?season=AAAA/AAAA` pour une saison précise) | Fiche club (pays, ville, stade, entraîneur), effectif complet, calendrier de toute la saison avec scores | Jamais branché dans un scraper — piste alternative si le blocage du point 7 n'est pas résolu rapidement |
| 9 | `matchendirect.fr/cotes/` | Cotes de référence 1N2/O-U 2,5/Double Chance, tous matchs du jour sur une seule page | Identifié tôt dans la session, jamais branché — redondant avec le point 3 qui donne plus de marchés par match |

### Pages jamais explorées, mentionnées une fois sans suite

- `matchendirect.fr/live-score/{slug}.html?p=forum` — commentaires utilisateurs, aucun intérêt pour le pipeline.
- `matchendirect.fr/equipe/{slug}.html?&tri=ligue` — tri du calendrier par ligue plutôt que par date, variante mineure du point 8.



---

## 5. Décisions d'abandon — avec raison, pour ne pas les reproduire

- **BeSoccer.com** : rejeté après 3 échecs réels confirmés (406 simple, 406
  avec en-têtes complets, page vide avec Playwright — détection de
  l'automatisation elle-même). Abandonné le 24/08 après avoir découvert que
  matchendirect fournissait déjà les mêmes données (classement dom/ext,
  historique de matchs) sans aucune protection.
- **Playwright / navigateur automatisé** : abandonné avec BeSoccer. Aucune
  page matchendirect utilisée n'en a jamais eu besoin.
- **Marchés mi-temps** : abandonné sur décision explicite (24/08) — "on fait
  simple". Les scores mi-temps existent par match individuel et dans le H2H,
  mais pas en liste groupée par équipe ; les récupérer en masse aurait
  multiplié le volume de requêtes.
- **Comparateur multi-bookmakers dédié (Oddspedia, etc.)** : jugé inutile
  par l'utilisateur — la formule EV n'a besoin que d'une seule cote de
  référence, pas d'un comparatif.
- **PythonAnywhere** : rejeté avant même le premier test — accès réseau
  restreint sur compte gratuit, tâches planifiées passées payantes en 2026,
  espace disque insuffisant pour Chromium.
- **Netlify Drop (déploiement manuel)** : rejeté — incompatible avec la mise
  à jour automatique quotidienne par GitHub Actions. Remplacé par un import
  Git dès la deuxième tentative de déploiement.
- **FootyStats.org** : payant dès le premier palier (30£/mois), écarté.
- **Football-Data.co.uk** : piste identifiée mais jamais retenue — fraîcheur
  de la saison en cours non confirmée au moment de la vérification.

---

## 6. Ce qui est fragile ou non testé — à vérifier en priorité

- **`recupere_cotes_marches`** (dans `scraper_details.py`) : partie la
  moins solide de tout le projet. Extraction de tableaux de cotes
  consécutifs sans repère HTML fiable (mêmes limites que partout : outil de
  récupération web qui ne montre jamais le HTML brut). À vérifier en
  premier sur le prochain run réel.
- **`recupere_20_derniers_resultats` et `recupere_h2h`** : jamais exécutés
  contre le vrai site (seulement testés en syntaxe). Fondés sur une
  technique déjà validée ailleurs (liens `/live-score/` ou `/foot-score/`
  avec score), donc risque plus faible, mais non confirmé.
- **Bug corrigé le 24/08, non encore re-testé en conditions réelles** :
  `pandas.read_html()` recevait le HTML brut directement et levait une
  erreur `[Errno 2] No such file or directory` en tentant de l'interpréter
  comme un chemin de fichier. Corrigé en enveloppant avec `io.StringIO()`
  dans `recupere_classement`. **Premier test réel de ce correctif : à
  faire.**
- **`data.json` actuellement en ligne contient des données de TEST
  fabriquées à la main** (PSG-Marseille fictif), pas de vrais matchs ni de
  vrais signaux. Le pipeline automatisé tourne et écrit un `data.json` réel
  depuis le 23/08, mais son champ `marches` n'est pas encore alimenté avec
  les vraies stats GF/GA — `construit_signaux()` dans `run_pipeline.py`
  attend encore des clés (`gf_home_domicile`, etc.) que rien ne remplit
  actuellement.
- **Lieu/météo/arbitre** : confirmé disponible, jamais branché dans aucun
  scraper — actuellement perdu.

---

## 7. Prochaines étapes concrètes, dans l'ordre

**Blocage à résoudre avant tout, trouvé en simulant la reprise du projet
(24/08, audit) — pas une simple tâche parmi d'autres** :
`recupere_20_derniers_resultats` a besoin de l'URL
`/statistique/{eq1}-contre-{eq2}.html`, mais **l'ordre des deux équipes dans
le slug n'est pas déterministe** — vérifié sur l'exemple Fulham (domicile)
vs Chelsea (extérieur), dont l'URL statistique était `chelsea-contre-fulham`
(l'équipe extérieure en premier). Deux solutions possibles, à trancher avant
l'étape 3 :
  - (a) Modifier `scraper.py` pour capter le vrai lien "Stats" affiché sur
    chaque page de match (probablement présent dans le HTML, jamais vérifié
    explicitement) plutôt que de reconstruire l'URL à la main.
  - (b) Court-circuiter `/statistique/` et utiliser uniquement
    `matchendirect.fr/equipe/{slug}.html` (point 8 de la section 4) pour le
    calendrier de chaque équipe séparément — moins pratique (deux pages au
    lieu d'une) mais l'URL équipe est déjà présente dans les données de
    classement, donc déterministe.

Même problème plus mineur pour `recupere_classement` : aucune table de
correspondance entre le nom de compétition scrapé ("France : Ligue 1
McDonald's") et le slug d'URL du classement ("classement-ligue-1") pour les
championnats autres que Ligue 1 — à construire au fur et à mesure des
championnats réellement utilisés, pas à l'avance pour tous les cas possibles.

Une fois ce blocage tranché :

1. **Committer le correctif StringIO** (déjà fait dans le fichier joint,
   à uploader sur GitHub si pas encore fait) et relancer le workflow.
   Vérifier spécifiquement les 4 sorties : classement, 20 derniers résultats,
   H2H, cotes — laquelle réussit, laquelle échoue encore.
2. **Corriger `recupere_cotes_marches` en fonction du résultat réel** — ne
   pas deviner un nouveau correctif sans avoir vu le résultat du test.
3. **Brancher `scraper_details.py` dans `run_pipeline.py`** : appeler
   `recupere_classement` et `recupere_20_derniers_resultats` pour chaque
   match du jour, en dériver les GF/GA nécessaires à `calculs.calcule_lambda`,
   remplacer les placeholders `None` actuels.
4. **Une fois un vrai match traité de bout en bout** (`traite: true` avec de
   vraies probabilités), vérifier le rendu sur le site en ligne avant de
   considérer la Phase 1 terminée.
5. Seulement après : envisager la case "10 derniers matchs uniquement" au
   lieu du classement saison complète, si le besoin s'en fait sentir une
   fois de vraies données observées.

---

---

## 9. Corrections après relecture du document génèse (24/08/2026)

Le fichier `Pipeline_Football_v_15082026_h2h_rotation.zip` (Modules 1-4
originaux, prompts système pour agent LLM) contient des éléments
méthodologiques concrets absents des sections précédentes de ce document.
Corrections apportées ici plutôt que réécrites en silence ailleurs, pour
garder la trace — même convention que le document original lui-même.

### 9.1 Pondération des champs critiques (absente plus haut)

Bilan dom/ext (poids 25), 10 derniers matchs + indice de forme (25), moyenne
buts dom/ext (20), classement + points (20), H2H (10). Cette hiérarchie doit
guider tout futur calcul de confiance — actuellement, `confiance_lambda()`
dans `calculs.py` utilise des seuils arbitraires (8/15 matchs) sans lien
avec cette pondération d'origine. À reconsidérer si un vrai score de
confiance est implémenté.

### 9.2 Bug méthodologique réel dans `recupere_20_derniers_resultats`

La spec d'origine est précise et actuellement **non respectée** par
`scraper_details.py` :
- Filtrer sur la **même compétition** que le match à analyser (exclure
  amicaux/coupes sauf échantillon insuffisant).
- Séparer domicile/extérieur : l'équipe listée en premier sur chaque ligne
  est toujours celle qui reçoit.
- **Garde-fou promotion/relégation** : si la saison en cours est trop jeune,
  on peut remonter à la saison précédente, mais seulement si le nom de la
  compétition affiché est identique. Sinon (changement de division) :
  ne jamais utiliser ces matchs comme proxy, marquer la donnée manquante
  plutôt que deviner.

Notre implémentation actuelle extrait tous les matchs sans ce filtre — à
corriger avant de brancher les vraies données dans `calculs.calcule_lambda`.

### 9.3 Convention H2H non respectée

Spec d'origine : 10 dernières confrontations maximum, score noté dans
l'ordre "équipe A puis équipe B" — **pas** l'ordre domicile/extérieur de
cette confrontation passée (le H2H mesure la relation entre les deux
équipes, pas qui recevait ce jour-là). `recupere_h2h` actuel ne fait pas
cette distinction — à corriger avant tout usage réel du H2H dans un calcul.

### 9.4 Signal gratuit oublié : rotation continentale

`jours_repos = date_du_match - date_du_dernier_match` (déjà calculable dès
qu'on a la liste des matchs d'une équipe). Si `jours_repos < 5` ET que la
compétition du dernier match est une compétition continentale connue (Ligue
des Champions/Europa/Conférence UEFA, Copa Libertadores, etc.) :
`risque_rotation_continentale = true`. **Signal pur, jamais un veto, jamais
une modification de lambda** — exactement le même patron déjà accepté pour
les autres signaux de ce projet. Candidat naturel pour une prochaine étape,
coût quasi nul.

### 9.5 Rôle réel de BeSoccer — à corriger dans la section 5

BeSoccer n'était **jamais prévu comme source principale** dans la conception
d'origine — c'est le **repli documenté** (priorité 2, après matchendirect.fr)
pour les championnats mal couverts par la source principale. Son
indisponibilité actuelle (protection anti-bot confirmée après 3 échecs
réels) laisse donc un vrai trou pour les championnats peu couverts par
matchendirect — pas un simple abandon sans conséquence comme présenté en
section 5. À rouvrir si le projet s'étend à des championnats moins connus.

### 9.6 Limite connue, sciemment non corrigée à l'origine — ne pas la "corriger" non plus

L'indice de forme (10 derniers matchs toutes compétitions) traite une
victoire de coupe contre une équipe de division inférieure comme n'importe
quel autre match, gonflant artificiellement l'indice. Décision d'origine :
ne pas corriger (coût de vérification disproportionné), seulement signaler
si détecté. Cohérent avec notre propre discipline de scope — ne pas tenter
de la corriger de notre côté sans le même arbitrage coût/bénéfice explicite.

### 9.7 Discipline des sources, formalisée

Ordre de priorité strict : (1) matchendirect.fr, autorité en cas de
conflit ; (2) besoccer.com, uniquement pour combler une absence, jamais
pour contredire ; (3) FotMob/Sofascore pour des usages ponctuels précis
(absences, corroboration). Aucune source hors de cette liste (Wikipédia,
blogs, forums) ne doit être citée comme preuve d'un fait utilisé dans un
calcul.

### 9.8 Auto-déclaration à conserver

Le pipeline d'origine affiche systématiquement `coefficients_empiriques:
false` à chaque sortie — aucune constante gelée n'est validée par backtest
historique. Si un jour l'interface affiche des signaux à l'utilisateur,
cette mention (ou son équivalent) doit rester visible, pas seulement dans
le code.

---

## 10. Fichiers joints à ce document

- `scraper.py` — matchs du jour (confirmé fonctionnel en production)
- `scraper_details.py` — classement/H2H/cotes (corrigé, non re-testé, méthodologie H2H/dom-ext à revoir selon section 9)
- `calculs.py` — moteur Poisson/Dixon-Coles/EV/Kelly (testé unitairement)
- `run_pipeline.py` — orchestrateur (fonctionne, mais signaux vides faute de données GF/GA branchées)
- `pipeline.yml` — workflow GitHub Actions (à placer dans `.github/workflows/`)
- `Pipeline_Football_v_15082026_h2h_rotation.zip` — document génèse original (Modules 1-4), à conserver et relire avant toute extension du périmètre

## 11. Diagnostic et correctifs confirmés sur HTML réel (24/08/2026)

Session de reprise après blocage URL statistique (section 7). Toutes les
causes ci-dessous sont vérifiées contre le vrai HTML matchendirect (via
fetch direct des pages, pas des suppositions) et confirmées par des runs
GitHub Actions réels après correction.

### 11.1 Blocage URL statistique — RÉSOLU
Option (a) retenue : `recupere_details_match` lit le vrai lien "Stats des
équipes" sur la page de match par défaut. Retourne aussi lieu/météo/arbitre/
diffuseur en un seul fetch. Fonctionne, testé.

### 11.2 Classement — RÉSOLU (2 correctifs)
- `pd.read_html` renvoyait des colonnes multi-niveaux
  (`('Saison Régulière', 'Equipe')`) à cause d'un en-tête de groupe sur la
  page. Correctif : aplatissement (`columns.get_level_values(-1)`).
- Un résidu subsistait : la ligne d'en-tête restait parfois comme première
  ligne de données après aplatissement, provoquant
  `invalid literal for int(): 'Saison Régulière'`. Correctif : filtrage des
  lignes dont `Pts` n'est pas numérique, plus un `try/except` par ligne
  pour ne jamais faire planter tout le classement pour une ligne isolée.

### 11.3 20 derniers résultats — RÉSOLU, enrichi
Cause : sur la page `/statistique/`, le score est dans une cellule de
tableau séparée du lien (qui ne contient que les noms d'équipes) —
contrairement à la page face-a-face où le score est dans le texte du lien.
Correctif : parsing par ligne de tableau (`<tr>`) au lieu de chercher le
score dans le lien seul (nouvelle fonction `_parse_table_matchs`).
Enrichissement : chaque résultat porte maintenant un champ `"competition"`
(dernier lien de la ligne), disponible pour implémenter le filtre "même
compétition" décrit en section 9.2 — filtre non appliqué à ce stade, juste
la donnée rendue disponible. Ne pas rebrancher sur une autre source de
données (`/equipe/{slug}.html` évalué et écarté, voir 11.5) : la colonne
existait déjà sur la page utilisée.

### 11.4 Cotes — RÉSOLU (2 correctifs)
- Le texte "Cotes 1N2" existe bien mais l'ancrage regex `^...$` échouait à
  cause d'espaces/retours à la ligne autour du nœud de texte brut. Corrigé
  par comparaison d'égalité sur texte strippé.
- Une fois le titre trouvé, double comptage des nombres : `find_all_next()`
  sans filtre renvoie à la fois une balise (`<td>3.98</td>`) ET son contenu
  texte comme deux éléments séparés — chaque cote comptée deux fois,
  décalant tout le regroupement par paquets de 3. Corrigé en ne parcourant
  que les nœuds de texte (`find_all_next(string=True)`), jamais les
  balises. Testé unitairement en local avant déploiement.
- Condition d'arrêt également revue : les titres de section ("Cotes 1N2",
  "Double chance", etc.) ne sont pas des balises h2/h3 — ce sont de simples
  nœuds de texte. Arrêt désormais sur la liste `TITRES_MARCHES_CONNUS`.

### 11.5 Pages explorées et écartées
- `?p=compositions` : compo probable disponible, mais aucun signal
  exploitable sans référentiel de force par joueur — hors scope, coût
  d'intégration réel pour bénéfice nul.
- `?p=forum` : commentaires utilisateurs, déjà écarté avant cette session.
- `/equipe/{slug}.html` : évalué comme alternative pour résoudre le filtre
  "même compétition" (section 9.2). Écarté : la colonne Compétition était
  déjà présente sur `/statistique/`, moins cher à exploiter que changer de
  source. Reste documenté comme repli si `/statistique/` casse un jour
  structurellement — donne calendrier complet segmenté par compétition,
  effectif complet avec poste/âge, fiche club.

### 11.6 Fichier livré
`scraper_details.py` v3 (314 lignes) intègre les 5 correctifs ci-dessus.
Toutes les fonctions (`details_match`, `classement`,
`20 derniers résultats`, `H2H`, `cotes`) confirmées OK sur un même run réel
avec de vraies données Fulham-Chelsea / Ligue 1.

### 11.7 Constat critique — TRANSITION.md n'existait pas sur GitHub
Ce fichier n'avait jamais été poussé sur le dépôt avant cette mise à jour.
Tout ce qui précède (sections 1-10) vivait uniquement dans les zips
uploadés en conversation, jamais synchronisé avec `main`. Reconstruit et
créé pour la première fois sur GitHub le 24/08/2026. À vérifier
systématiquement en début de session future : la présence réelle des
fichiers de référence sur le dépôt, pas seulement leur existence dans un
zip local.

### 11.8 Reste à faire (non traité cette session)
- Brancher `scraper_details.py` dans `run_pipeline.py` pour remplacer les
  placeholders `None` par les vraies données GF/GA (étape 3 de la section
  7, toujours valable).
- Implémenter le filtre "même compétition" (9.2) en exploitant le nouveau
  champ `competition` — décision prise de ne PAS le faire maintenant sans
  discussion explicite.
  ## ⚠ BUG OUVERT, NON RÉSOLU — À TRAITER EN PRIORITÉ

**Cote invraisemblable observée sur une ligne over/under haute (25/08/2026).**
Match Gil Vicente-Casa Pia : lambda_home=1.96, lambda_away=0.60 → modèle
donne 99.3% de probabilité sur "Moins de 6.5 buts", cote scrapée = 1.61.
Une probabilité aussi extrême devrait correspondre à une cote proche de
1.00-1.05 (cf. cotes réelles observées sur des lignes similaires : 1.03-1.06
sur "5.5 Plus/Moins" plus tôt dans le projet). Cote de 1.61 fortement
suspecte d'une mauvaise association ligne/colonne dans
`recupere_cotes_marches` (déjà arrivé deux fois : double comptage, ancrage
regex) — probablement spécifique aux lignes hautes (5.5-7.5 buts).

**Diagnostic reporté** : le match a commencé avant que le HTML de la page
`?p=face-a-face` ait pu être capturé — cotes disparues après coup d'envoi.

**À faire au prochain cycle, AVANT le coup d'envoi des matchs
sélectionnés** : ouvrir la page `?p=face-a-face` d'un match avec une ligne
haute probable, capturer le HTML (ou une capture d'écran de la section
over/under) avant que le match démarre, et comparer avec ce que
`recupere_cotes_marches` a effectivement extrait dans `data.json`.

**Ne pas faire confiance aux "paris en or" sur les lignes over/under 5.5+
tant que ce point n'est pas vérifié.** Les autres marchés (1X2, double
chance, BTTS, lignes 0.5-2.5) n'ont montré aucun signe d'anomalie jusqu'ici.

