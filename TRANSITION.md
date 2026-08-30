# Archetype Foot — Document de transition
Dernière mise à jour : 30/08/2026 soir (mise en service réelle de Supabase,
voir section 0.8 -- inclut le bug le plus coûteux de tout le projet à ce
jour et sa correction), dans la continuité d'une session longue.
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
  **CORRECTION d'une affirmation périmée (section 5)** : "Football-Data.co.uk,
  piste identifiée mais jamais retenue" ne tient plus — largement utilisé
  et fiable pour cet usage précis (moyennes de championnat, pas de
  scraping temps réel de match).
- **FootyStats.org** — pas de CSV gratuit pour les championnats hors
  "principaux" ; utilisé via captures d'écran manuelles du tableau de
  classement (MP/GF/GA), collées dans le chat. Championnats couverts :
  Corée du Sud, Arabie Saoudite, Japon, Estonie, Tunisie, États-Unis
  (MLS), Afrique du Sud, Chine.
  **CORRECTION d'une affirmation périmée (section 5)** : "FootyStats.org,
  payant dès le premier palier, écarté" reste vrai pour l'API/le plan
  payant, mais FAUX pour la consultation web gratuite utilisée ici (aucun
  compte requis pour voir un tableau de classement).
- **Restent non couverts** : Écosse (saison 2026/27 fournie trop courte,
  16/198 matchs), Autriche (jamais traitée). Compétitions qui ne pourront
  jamais avoir de valeur par pays : "Europe" (coupes continentales),
  "Monde", "International".
- **Piste d'automatisation évoquée, pas construite** : un script mensuel
  qui refait ce calcul automatiquement depuis les CSV Football-Data.co.uk
  (faisable, pas de scraping HTML) ; pour FootyStats, il faudrait du vrai
  scraping HTML (pas de CSV gratuit), plus fragile — à réserver aux
  championnats non couverts par Football-Data.co.uk si jugé utile.

### 0.4 `verification_resultats.py` — nouveau script, ferme la boucle de vérification
Avant ce script, la vérification de calibration dépendait entièrement de
copier-coller manuel des pages résultat matchendirect (ce qui a servi pour
0.1). Nouveau fichier à la racine : pour chaque jour de
`historique_pronostics.json` strictement antérieur à aujourd'hui, va
chercher la page résultat matchendirect correspondante (réutilise
`parse_matches`/`url_resultat_foot`/`fetch_html` de `scraper.py`, et
`_memes_equipes` de `scraper_details.py` pour le rapprochement de noms),
et écrit le score dans les matchs déjà analysés (GO/NO_GO) qui n'en ont pas
encore — seulement si le statut scrapé est bien `"TER"` (jamais un score
partiel ou un match reporté). Branché dans `pipeline.yml`, run planifié
uniquement (`if: github.event_name == 'schedule'`), juste avant le commit.
Testé avec des données simulées (réseau bloqué dans l'environnement
d'édition, comme toujours) — à confirmer sur le premier run réel de
production (regarder les logs GitHub Actions : ligne `[verification] X
score(s) renseigné(s)`).

### 0.5 Passage à Supabase — isolation multi-utilisateur
**Problème identifié** : le site est architecturé autour d'un seul panier
partagé (`panier.json`) et d'un seul résultat partagé (`data.json`,
`historique_pronostics.json`), régénérés à chaque run GitHub Actions. Deux
personnes envoyant un panier à peu près en même temps se marchaient dessus
— la dernière analyse écrasait celle de la précédente pour tout le monde,
sans qu'aucune des deux ne s'en rende compte.

**Solution retenue** : auth anonyme Supabase (un `user_id` par appareil,
pas de compte/mot de passe — garde l'usage aussi simple qu'avant), deux
tables avec Row Level Security (RLS) :
```sql
paniers (id, user_id, matchs jsonb, statut, created_at)
resultats_pipeline (id, panier_id, user_id, data jsonb, created_at)
-- RLS : chacun ne voit/crée que ses propres lignes (auth.uid() = user_id)
```
RLS choisi plutôt qu'un filtre côté client car un filtre JS peut être
contourné (appel direct à l'API) — RLS bloque au niveau de la base, même
avec la clé anonyme exposée côté front (c'est voulu, pas une faille).

**Fichiers modifiés pour ce passage** (les 4 livrés, testés/compilés) :
- `panier.js` — session anonyme Supabase, insère le panier dans la table
  `paniers` avec le `user_id` de la session (au lieu d'un `fetch` direct
  vers `trigger.js` avec les matchs en clair), transmet seulement
  `panier_id` + jeton d'accès à `trigger.js`.
- `netlify/functions/trigger.js` — reçoit `panier_id` (plus le tableau de
  matchs), vérifie que le panier appartient bien à l'appelant en
  interrogeant Supabase AVEC le jeton utilisateur (RLS renvoie vide si le
  panier n'est pas à lui), puis déclenche `workflow_dispatch` avec
  `panier_id` en input.
- `dispatch_pipeline.py` — **remplace `run_pipeline.py` comme point
  d'entrée du canal manuel** (confusion initiale corrigée en session :
  c'est bien ce fichier qui lisait `INPUT_MATCHS_JSON`, pas
  `run_pipeline.py`). Lit le panier depuis Supabase via `panier_id` (clé
  `service_role`, contourne RLS car c'est le serveur), écrit
  `panier.json` localement à l'identique d'avant (`run_pipeline.py`
  lui-même reste inchangé), puis relit `historique_pronostics.json` pour
  en extraire les entrées de ce panier précis et les écrit dans
  `resultats_pipeline`, rattachées au `user_id` du panier.
- `script.js` (chargé par `pronostics.html`, PAS un fichier `pronostics.js`
  séparé — confusion corrigée en session) — remplace le
  `fetch("data.json")` global par une lecture Supabase filtrée sur la
  session en cours (RLS), avec un sondage automatique toutes les 20s
  pendant ~5 min (l'analyse prend "quelques minutes").
- `.github/workflows/pipeline.yml` — input `matchs_json` → `panier_id` ;
  `concurrency: {group: pipeline-archetype-foot, cancel-in-progress: false}`
  ajouté (sans ça, deux déclenchements manuels rapprochés pouvaient encore
  se marcher dessus au moment du `git push`, même avec Supabase en place
  côté résultat) ; le `git add panier.json historique_pronostics.json` est
  désormais conditionné à `if: github.event_name == 'schedule'` — ces deux
  fichiers ne sont plus le canal de résultat pour un envoi manuel, les
  committer à chaque run manuel n'avait plus d'utilité et recréait le
  risque de conflit qu'on venait de fermer côté Supabase.

**MISE À JOUR 30/08/2026 soir : entièrement fait, en service réel.** Ce qui
suit était la checklist de configuration -- gardée pour mémoire de ce qui a
été fait, avec les difficultés réelles rencontrées à chaque étape détaillées
en section 0.8 :
- ✅ Projet Supabase `archetype-foot` créé (org `TechGo`, région `eu-west`),
  SQL exécuté (voir 0.8 pour l'ordre exact des étapes qui a fonctionné).
- ✅ Connexions anonymes activées (`Authentication > Sign In / Providers >
  Anonymous Sign-Ins`) -- étape facile à oublier, sans effet visible tant
  qu'on ne l'a pas activée (pas d'erreur explicite, juste rien ne se passe).
- ✅ `SUPABASE_URL`/`SUPABASE_ANON_KEY` renseignés dans `panier.js` et
  `script.js` (clés "Legacy anon, service_role" -- voir 0.8.3, PAS les
  nouvelles clés "Publishable/secret" que Supabase met en avant par défaut
  maintenant).
- ✅ Script `@supabase/supabase-js` ajouté dans `panier.html` ET
  `pronostics.html`.
- ✅ Secrets Netlify (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) et GitHub Actions
  (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) créés.
- ✅ **Test réel effectué et réussi** le 30/08 au soir : panier envoyé
  depuis `archetype-foot.netlify.app` (⚠️ pas `type-foot.netlify.app`, un
  autre site Netlify plus ancien resté connecté à rien -- voir 0.8.6),
  traité automatiquement, résultat visible sur "Voir les pronostics" sans
  aucune intervention manuelle sur `panier.json`.
- **Non fait** : le test à deux navigateurs simultanés (isolation réelle
  entre deux utilisateurs différents) reste à faire -- un seul utilisateur
  (Patrick) a testé jusqu'ici.

### 0.6 Responsive (`style.css`)
Le site n'avait aucune media query (0 dans tout le fichier) malgré la
balise viewport — pensé mobile-only par défaut (cohérent avec l'usage
iPhone exclusif de l'utilisateur). Ajouté : `header`/`main` centrés avec
une largeur max de 1200px (toutes les pages, elles utilisent toutes ces
deux balises) + un seul palier `@media (min-width: 700px)` qui ajuste
cartes/titre/boutons sans rien changer en dessous de 700px. La grille de
cartes (`main.grille`, `grid-template-columns: repeat(auto-fill, ...)`)
était déjà intrinsèquement responsive, non touchée.

### 0.7 Erreurs commises en session, corrigées avant livraison
- Confusion initiale `run_pipeline.py` / `dispatch_pipeline.py` comme
  point d'entrée du canal manuel (0.5) — corrigée avant que le mauvais
  fichier soit livré au dépôt.
- Confusion initiale `pronostics.js` (n'existe pas) / `script.js` (le bon
  fichier, chargé par `pronostics.html`) — corrigée avant livraison.
- Un tableau de championnats (buts/match par pays) fourni deux fois par
  l'utilisateur sans source vérifiable a été écarté les deux fois — les
  valeurs qu'il contenait pour l'Arabie Saoudite et la Tunisie se sont
  révélées proches des valeurs calculées ensuite sur données réelles,
  mais rien ne permettait de le savoir au moment de le recevoir ; la
  discipline "pas de source vérifiable = pas d'intégration" a été
  maintenue malgré la coïncidence.
- Script de recoupement ponctuel (hors dépôt) avec une clé de recherche
  `'Horsens'` au lieu de `'AC Horsens'` ayant fait disparaître ce match du
  calcul intermédiaire — repéré par écart entre le total de lignes attendu
  et obtenu, corrigé avant de tirer une conclusion. Sans impact sur le
  code du dépôt (script d'analyse ponctuel dans le chat, pas un fichier
  livré).

---



## ✅ BUG RÉSOLU (26/08/2026) — cote invraisemblable sur ligne over/under haute

**Symptôme d'origine (25/08/2026)** : match Gil Vicente-Casa Pia,
lambda_home=1.96, lambda_away=0.60 → modèle donne 99.3% de probabilité sur
"Moins de 6.5 buts", cote scrapée = 1.61 (attendu : 1.00-1.05, cf. cotes
réelles observées sur des lignes similaires ailleurs dans le projet).

**Cause racine confirmée** : dans `recupere_cotes_marches`
(`scraper_details.py`), l'ancrage du titre de marché utilisait
`soup.find(string=...)`, qui retourne la PREMIÈRE occurrence du texte dans
tout le document. Or un même titre de marché peut apparaître deux fois sur
la page matchendirect : une fois dans un widget d'aperçu en haut de page
(sans Bet365 parmi les bookmakers affichés), une fois dans le tableau
complet plus bas (avec Bet365). Confirmé sur HTML réel récupéré le
26/08/2026 (match Valence-Real Betis, LaLiga) : le titre "Mi-temps -
Résultat" apparaît deux fois exactement selon ce schéma. Si un jour ce
widget d'aperçu affiche un marché réellement exploité (1N2, BTTS, une
ligne over/under) plutôt que "Mi-temps", `soup.find` ancre sur l'aperçu, et
la marche `find_all_next()` (sans limite) qui cherche ensuite le logo
Bet365 dérive à travers tout le contenu intermédiaire (Détails du match,
Pronostic...) jusqu'au prochain titre reconnu — pouvant renvoyer la cote
Bet365 d'un AUTRE marché, réelle mais mal associée, sans jamais lever
d'erreur ni de `None`. C'est le mécanisme le plus probable derrière la cote
de 1.61 : une valeur cohérente pour un marché 1N2, pas pour un
over/under 6.5.

**Correctif appliqué** : `soup.find` remplacé par `soup.find_all` +
sélection de la DERNIÈRE occurrence (le tableau complet étant
structurellement le dernier endroit où un titre de marché apparaît sur la
page). Commité sur `main` le 26/08/2026.

**Limite assumée de cette vérification** : diagnostic établi par lecture
manuelle du HTML réel (outil de fetch), pas par exécution du scraper en
conditions réelles — `matchendirect.fr` n'était pas accessible depuis
l'environnement d'édition de ce correctif. **À confirmer au prochain run
réel (GitHub Actions ou manuel)** : vérifier que `cote_1` reste renseigné
sur l'ensemble des matchs traités, en particulier sur les lignes
over/under 5.5+.

### 0.8 Session du 30/08/2026 (soir) — mise en service réelle de Supabase, et tout ce qui a mal tourné en route

**Résultat final : ÇA MARCHE.** Panier envoyé depuis le site (`archetype-foot.netlify.app`),
traité automatiquement par GitHub Actions sans aucune intervention manuelle sur
`panier.json`, résultat visible sur "Voir les pronostics". La chaîne complète
décrite en 0.5 fonctionne enfin de bout en bout. Mais le chemin pour y arriver a
révélé plusieurs problèmes réels, chacun documenté ci-dessous avec sa cause
exacte -- objectif : ne plus jamais perdre une soirée dessus.

**Ordre de lecture recommandé si un problème similaire réapparaît** : le 0.8.5
(bug de code) est CELUI qui a coûté le plus de temps -- le lire en premier.

#### 0.8.1 GitHub Actions : `panier_id` obligatoire empêchait toute relance manuelle
`workflow_dispatch.inputs.panier_id` était `required: true`. Résultat : impossible
de relancer le pipeline à la demande sans Supabase déjà configuré -- aucune façon
de tester "les matchs d'aujourd'hui" en attendant. **Corrigé** : `required: false`,
et les conditions `if:` de chaque étape (`run_pipeline.py` vs `dispatch_pipeline.py`,
commit final) gèrent maintenant le cas `panier_id` vide comme un run planifié classique.
Peut se resservir un jour si un autre champ obligatoire bloque un usage légitime :
se demander systématiquement "et si cette valeur est vide, quel comportement de
repli est raisonnable ?" avant de marquer un input `required: true`.

#### 0.8.2 GitHub Actions : cron programmé, mais jamais synchronisé avec le déploiement du fichier
Cron changé de 7h UTC à 0h UTC (1h Douala) pour que l'analyse soit prête au réveil.
Sauf qu'un changement de cron ne s'applique qu'à partir du PROCHAIN passage de
l'heure programmée après que le fichier modifié a été mergé sur `main` -- pas
rétroactivement. Poussé après minuit UTC un jour donné => le nouvel horaire ne
prend effet que la nuit suivante. **Leçon** : après tout changement de cron,
compter au moins un cycle complet (24h) avant de s'attendre à voir l'effet, et
le dire explicitement à Patrick pour éviter la fausse alerte "ça n'a pas marché".
Fait aussi ressortir un point structurel à garder en tête : GitHub Actions ne
garantit pas la ponctualité à la minute sur les dépôts peu actifs -- un run
planifié a démarré avec 6h de retard un jour de cette session (14h05 au lieu de
7h). Ne jamais promettre "prêt à telle heure précise", seulement "prêt en général
dans la nuit/matinée".

#### 0.8.3 Supabase a changé de système de clés API sans prévenir (connaissance déjà périmée en cours de session)
Supabase a introduit un nouvel onglet par défaut ("Publishable and secret API
keys") qui n'existait pas dans ce qui était su au début de cette conversation.
Les clés `anon`/`service_role` qu'utilise tout le code déjà écrit
(`panier.js`/`script.js`/`dispatch_pipeline.py`/`trigger.js`) sont désormais
reléguées dans un second onglet, "Legacy anon, service_role API keys" --
toujours fonctionnelles, juste plus dans l'onglet visible par défaut.
**Décision prise** : rester sur le système "Legacy" plutôt que migrer vers les
nouvelles clés "Publishable/secret", pour ne pas réécrire tout le code un soir
où la priorité était de faire marcher l'existant. **À surveiller** : Supabase
a averti que les clés legacy seront un jour dépréciées (pas de date donnée) --
migrer vers `sb_publishable_...`/`sb_secret_...` sera à reprendre un autre jour,
pas en urgence.

#### 0.8.4 Menus Supabase/GitHub/Netlify réorganisés depuis la dernière fois -- plusieurs faux départs de navigation
Sur Supabase, "API Keys" n'est plus sous "Settings > General" mais sous
"Settings > Configuration > API Keys", un onglet séparé. Sur GitHub mobile,
"Settings" (du dépôt) est caché derrière un bouton "More" quand la largeur
d'écran ne permet pas d'afficher tous les onglets ("Code / Issues / Pull
requests / ... / More"), et "Secrets and variables" est lui-même sous
"Security and quality" avec un sous-menu déroulant "Actions" -- pas à
confondre avec l'onglet "Actions" tout court, qui montre les *runs*, pas les
secrets. **Leçon générale, pas seulement pour ces deux plateformes** :
signaler explicitement, avant même de guider vers un menu, que ces
interfaces évoluent régulièrement et que le chemin décrit peut être
approximatif -- demander une capture de ce qui s'affiche réellement dès le
premier doute plutôt qu'insister sur un chemin qui s'avère faux plusieurs
fois de suite.

#### 0.8.5 LE bug -- `const supabase = ...` plantait TOUT le fichier, silencieusement, pendant des heures
**C'est celui qui a fait perdre le plus de temps ce soir, et il était entièrement
évitable.** `panier.js` et `script.js` déclaraient tous deux `const supabase =
createClient(...)`. Mais le script `@supabase/supabase-js` chargé juste avant
crée déjà, tout seul, une variable globale nommée `supabase` dans le navigateur.
Redéclarer un nom déjà global avec `const`/`let` est une erreur de syntaxe stricte
en JavaScript (`SyntaxError: Can't create duplicate variable that shadows a
global property: 'supabase'`) -- **le fichier entier refuse de s'exécuter**, pas
seulement la ligne fautive. Résultat observé : le panier affichait "0" indéfiniment
sur la page panier (alors que l'accueil, qui n'utilise pas Supabase, affichait le
bon nombre) -- aucune erreur visible à l'écran par défaut, puisque Safari mobile
n'a pas de console accessible sans Mac. Plusieurs pistes fausses explorées avant
de trouver la vraie cause : cache navigateur, mauvais site Netlify (voir 0.8.6,
qui était réel mais ne suffisait pas à tout expliquer), fichier corrompu au
copier-coller, conflit d'édition GitHub. **Corrigé** : renommé `supabase` en
`supabaseClient` partout dans les deux fichiers (`const supabaseClient =
window.supabase.createClient(...)`, puis tous les usages `supabase.auth...`/
`supabase.from(...)` mis à jour en conséquence).
**Leçon technique, réutilisable ailleurs** : toute variable nommée comme la
librairie globale qu'elle initialise (`supabase`, mais le même risque existe
avec `stripe`, `firebase`, etc. chargés en `<script>` classique plutôt qu'en
module) doit être vérifiée AVANT livraison, pas découverte en production --
un simple `grep` du nom de variable contre le nom du package suffit.
**Leçon de méthode, plus large** : dès qu'un symptôme résiste à plusieurs
corrections plausibles d'affilée sans jamais changer, la vraie erreur est
probablement plus basique qu'on ne le suppose (une syntaxe qui plante tout,
pas une logique métier subtile) -- la lecture ligne par ligne du fichier tel
qu'il existe réellement sur GitHub aurait révélé ce bug immédiatement dès la
première suspicion de plantage, sans attendre de fabriquer un outil de
diagnostic pour l'afficher.

#### 0.8.6 Deux sites Netlify différents testés sans s'en rendre compte
`type-foot.netlify.app` (ancien site, déconnecté du dépôt GitHub actuel,
jamais mis à jour par nos commits) contre `archetype-foot.netlify.app` (le
vrai site, relié à `github.com/Patzaza81/archetype-foot`, celui que Netlify
"Deploys" confirmait publier à chaque commit). Toutes les captures de la
première partie de la soirée montraient `type-foot.netlify.app` -- ce qui
explique une partie de la confusion ("j'ai remplacé les fichiers mais rien
ne change"), même si le vrai bug (0.8.5) restait présent sur les deux sites
une fois qu'on a basculé sur le bon. **Leçon** : quand un correctif poussé
sur GitHub semble n'avoir _aucun_ effet, même après un déploiement confirmé
"Published", vérifier en premier le nom de domaine affiché dans la barre
d'adresse -- avant de chercher un problème de cache ou de code.

#### 0.8.7 Outil de diagnostic temporaire -- utile une fois, retiré ensuite
Face à un plantage sans message d'erreur visible, un bloc HTML/JS a été
ajouté temporairement à `panier.html` (écoute `window.addEventListener("error",
...)`, affiche le message dans une bande rouge en bas d'écran) -- seul moyen
d'obtenir un vrai message d'erreur JavaScript sur iPhone sans Mac ni
console développeur accessible. A permis d'identifier 0.8.5 en une capture
d'écran, là où plusieurs échanges de suppositions n'avaient rien donné.
Retiré du fichier une fois le vrai bug confirmé et corrigé -- ne doit pas
rester en production indéfiniment (une bande d'erreur brute n'est pas destinée
aux utilisateurs finaux). **Si un plantage silencieux similaire réapparaît**,
ce bloc peut être réintroduit directement plutôt que ré-explorer plusieurs
pistes à l'aveugle d'abord -- gain de temps confirmé ce soir.

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

**MISE À JOUR 30/08/2026** : quatre de ces valeurs ont changé depuis, voir
section 0.2 pour le détail et la justification empirique de chacune.
`GA_REFERENCE` (constante unique) est remplacée par `GA_REFERENCE_PAR_LIGUE`
(dict par pays, voir 0.2/0.3) + `ALIAS_PAYS`. Les valeurs ci-dessous sont
gardées telles quelles pour mémoire historique (ce qu'était le pipeline
avant calibration) :

```
GA_REFERENCE = 1.35                    # -> GA_REFERENCE_PAR_LIGUE (0.2/0.3)
BORNE_MIN_DEFENSE = 0.70                # -> 0.55 (0.2)
BORNE_MAX_DEFENSE = 1.30                # -> 1.60 (0.2)

POIDS_FORME = 0.30
POIDS_CLASSEMENT = 0.20
POIDS_REPOS = 0.15
POIDS_ABSENCES = 0.15
POIDS_DISTANCE = 0.10
POIDS_H2H = 0.10
BORNE_RATIO = 0.15

RHO_DIXON_COLES = -0.1

SEUIL_EV_MIN = 0.05                     # -> 0.12 (0.2)
FOURCHETTE_COTE_MIN = 1.25
FOURCHETTE_COTE_MAX = 1.69
SEUIL_CORRELATION = 0.70
KELLY_FRACTION = 0.25
MISE_MAX_PARI = 0.04
CLUSTER_MAX = 0.10
NB_PARIS_MAX = 3
SEUIL_STANDOUT = 0.15

K_SHRINKAGE = 0.27                      # nouvelle constante, voir 0.2
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
  → scraper.py           (matchs aujourd'hui/demain — matchendirect, HTTP simple)
  → scraper_semaine.py   (matchs J+2 à J+7 — matchendirect, via Playwright,
                           contourne le blocage HTTP simple confirmé -- 15.9)
  → scraper_betpawa.py   (cotes + marchés Betpawa, via Playwright,
                           JS requis pour voir les cotes -- 15.7)
  → scraper_details.py   (classement, H2H, forme -- matchendirect, HTTP simple)
  → calculs.py           (Poisson/Dixon-Coles/EV/Kelly, calibré par ligue -- 0.2)
  -- run planifié (schedule) --
  → run_pipeline.py      (orchestrateur, écrit data.json)
  → verification_resultats.py  (scores des jours passés -- 0.4, NOUVEAU 30/08)
  → commit + push automatique vers le dépôt (data.json, historique_pronostics.json...)
  -- run manuel (workflow_dispatch, panier_id) --
  → dispatch_pipeline.py (lit le panier Supabase par panier_id, appelle
                           run_pipeline.py, écrit le résultat dans Supabase
                           -- REMPLACE run_pipeline.py comme point d'entrée
                           manuel depuis le 30/08, voir 0.5)
Netlify sert le dépôt en statique :
  - index.html/script.js (page "pronostics") lisent Supabase (résultat
    filtré par utilisateur -- 0.5), plus data.json directement depuis le 30/08
  - panier.html/panier.js écrivent dans Supabase (table `paniers`) avant
    de déclencher trigger.js, au lieu d'un fetch direct avec les matchs
netlify/functions/trigger.js : vérifie l'appartenance du panier via
  Supabase (RLS, jeton utilisateur) avant de déclencher workflow_dispatch
Supabase : auth anonyme + tables `paniers`/`resultats_pipeline` (RLS) --
  isolation multi-utilisateur, voir section 0.5
```

**Dépôt GitHub** : `Patzaza81/archetype-foot`, branche `main`, tous les
fichiers à la racine (pas de sous-dossiers sauf `.github/workflows/`,
imposé par GitHub).

**Site Netlify** : connecté au dépôt via import Git (pas de déploiement
manuel "Drop" — celui-là a été abandonné, voir section 5).

**Playwright (navigateur automatisé)** : réintroduit le 26/08 pour deux usages
précis, tous les deux dans `pipeline.yml`, distincts du flux matchendirect
"aujourd'hui" qui reste en HTTP simple (`requests`) — voir section 15.7 et
15.9. Le reste de l'architecture matchendirect ("aujourd'hui") continue de
fonctionner sans navigateur.

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
| 3 | `matchendirect.fr/live-score/{slug}_{id}.html?p=face-a-face` | Forme 5 derniers matchs (par équipe, dom/ext séparés), H2H complet avec mi-temps, cotes multi-bookmakers (1N2/DC/MT-FM/BTTS/O-U 0.5-7.5) | `scraper_details.py::recupere_h2h` et `recupere_cotes_marches` — codé et testé en conditions réelles |
| 4 | `matchendirect.fr/live-score/{slug}_{id}.html?p=classement` | Mini classement autour des deux équipes (aperçu, pas la page complète) | Non exploré séparément — un aperçu apparaît déjà inclus dans la page `?p=face-a-face` |
| 5 | `matchendirect.fr/live-score/{slug}_{id}.html?p=compositions` | Compositions d'équipe probables/officielles | Jamais récupéré, jamais vérifié serveur-rendu ou non |
| 6 | `matchendirect.fr/classement-foot/{pays}/{comp}.html` (+ `?p=home` / `?p=away`) | Classement Général/Domicile/Extérieur complet de la saison | `scraper_details.py::recupere_classement_du_match` — fonctionne, branché dans l'Étape 3 du Module 2 |
| 7 | `matchendirect.fr/statistique/{eq1}-contre-{eq2}.html` | 20 derniers résultats par équipe, stats pré-match | Code mort actuellement — remplacé par `recupere_gf_ga_avec_repli` (section 12), plus jamais appelé par `run_pipeline.py` |
| 8 | `matchendirect.fr/equipe/{slug}.html` (+ `?season=AAAA/AAAA` pour une saison précise) | Fiche club, effectif complet, calendrier de toute la saison avec scores | `scraper_details.py::recupere_gf_ga_avec_repli` — source principale du GF/GA actuel, avec repli saison précédente |
| 9 | `matchendirect.fr/cotes/` | Cotes de référence 1N2/O-U 2,5/Double Chance, tous matchs du jour sur une seule page | Jamais branché — redondant avec le point 3 |

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
- **Playwright / navigateur automatisé** : abandonné avec BeSoccer le 24/08,
  **RÉINTRODUIT le 26/08** pour deux usages précis et confirmés fonctionnels
  en conditions réelles : récupérer les cotes Betpawa (données chargées par
  JS, confirmé par `test_scraping_betpawa.py` qu'une requête HTTP simple ne
  les voit pas) et contourner un blocage confirmé de matchendirect sur les
  dates futures (voir 15.7 et 15.9). Le flux matchendirect "aujourd'hui"
  original n'en a toujours pas besoin.
- **Marchés mi-temps** : abandonné sur décision explicite (24/08) — "on fait
  simple".
- **Comparateur multi-bookmakers dédié (Oddspedia, etc.)** : jugé inutile
  par l'utilisateur — la formule EV n'a besoin que d'une seule cote de
  référence, pas d'un comparatif.
- **PythonAnywhere** : rejeté avant même le premier test — accès réseau
  restreint sur compte gratuit, tâches planifiées passées payantes en 2026,
  espace disque insuffisant pour Chromium.
- **Netlify Drop (déploiement manuel)** : rejeté — incompatible avec la mise
  à jour automatique quotidienne par GitHub Actions.
- **FootyStats.org** : l'API/plan payant reste écarté (30£/mois dès le
  premier palier). **NUANCE AJOUTÉE 30/08/2026** : la consultation web
  gratuite (tableau de classement, sans compte) a en revanche été utilisée
  avec succès pour calibrer `GA_REFERENCE_PAR_LIGUE` sur 8 championnats —
  voir section 0.3. Ce qui reste écarté, c'est spécifiquement l'API/le
  scraping automatisé à grande échelle, pas le site lui-même.
- **Football-Data.co.uk** : **CORRECTION 30/08/2026** — cette ligne disait
  "piste identifiée mais jamais retenue". Retenue depuis et largement
  utilisée (CSV gratuits, 16 championnats calibrés dans
  `GA_REFERENCE_PAR_LIGUE`, voir section 0.3). Erreur de cette ligne :
  jugée à tort superflue tant qu'aucun besoin de moyenne de championnat
  n'était identifié — le besoin est apparu avec la calibration empirique
  de fin août.
- **Forme, Absences, Distance (Étape 3 Module 2)** : ANNULÉS le 25/08 —
  Forme jamais formalisée, Absences non fiable à scraper, Distance jamais
  commencée (géocodage). Voir section 13.
- **Risque de rotation continentale (section 9.4)** : ANNULÉ le 25/08,
  malgré son coût nul évoqué à l'origine — non prioritaire.
- **Handicap 3 voies (Étape 0 Module 3)** : EXCLU le 25/08 — jamais observé
  comme section de cotes distincte sur matchendirect de toute façon.

---

## 6. Ce qui est fragile ou non testé — à vérifier en priorité

- **BUG OUVERT (voir tout en haut de ce document)** : cote invraisemblable
  sur ligne over/under haute (5.5+), diagnostic reporté au prochain cycle.
- **Lieu/météo/arbitre** : confirmé disponible, jamais branché dans aucun
  scraper — actuellement perdu.
- **Seuil de corrélation 0.70 (Module 3)** : possiblement trop haut pour
  s'activer en pratique sur des matchs à faible pouvoir de but — observé
  empiriquement (0.63 max sur des lignes over/under adjacentes), jamais
  confirmé comme un vrai problème sur un échantillon large. Voir section 13.
- **`scraper_betpawa.py` — détection de format par essai/erreur** : trois
  parseurs différents existent (`parse_betpawa.py`, `parse_betpawa_url.py`,
  `parse_betpawa_playwright.py`) pour trois formats de texte différents
  observés à ce jour sur Betpawa. Le script garde automatiquement celui qui
  reconnaît le plus de marchés -- fonctionne sur tous les cas testés (5
  championnats), mais un futur format non prévu donnerait 0 marché reconnu
  sans erreur explicite (voir 15.7) plutôt que d'échouer bruyamment.
- **Recherche automatique d'URL matchendirect par nom d'équipe (15.9)** :
  logique de correspondance testée sur une douzaine de cas, dont plusieurs
  pièges volontaires (voir bug Manchester City/United corrigé, 15.9) --
  reste une heuristique, pas une garantie. Conçue pour échouer proprement
  (aucune correspondance retenue) plutôt que deviner en cas de doute, mais
  un futur cas piège non anticipé reste possible.
- **`scraper_semaine.py`** : un seul run réel de validation à ce jour
  (26/08, 2531 matchs sur 6 jours) -- fonctionne, mais la fiabilité dans la
  durée (le site pourrait changer sa protection anti-robot) n'est pas
  acquise pour toujours.

---

## 7. Historique résolu (24/08) — blocage URL statistique

Blocage initial : l'ordre des deux équipes dans le slug
`/statistique/{eq1}-contre-{eq2}.html` n'était pas déterministe. RÉSOLU en
lisant le vrai lien "Stats des équipes" sur la page de match par défaut
(voir section 11.1). Ce chemin de données est désormais du **code mort** :
remplacé par le repli saison précédente sur `/equipe/{slug}.html` (section
12), jugé plus robuste et déjà en place.

---

## 9. Corrections après relecture du document génèse (24/08/2026)

Le fichier `Pipeline_Football_v_15082026_h2h_rotation.zip` (Modules 1-4
originaux, prompts système pour agent LLM) contient des éléments
méthodologiques concrets absents des sections précédentes de ce document.

### 9.1 Pondération des champs critiques (absente plus haut)

Bilan dom/ext (poids 25), 10 derniers matchs + indice de forme (25), moyenne
buts dom/ext (20), classement + points (20), H2H (10). Cette hiérarchie
n'est PAS utilisée par `confiance_lambda()` actuel (seuils arbitraires
8/15 matchs) — jamais reconsidérée depuis.

### 9.2 Filtre "même compétition" — historique, périmé

Décrit à l'origine pour `recupere_20_derniers_resultats` (fonction
aujourd'hui code mort, voir section 7). Le problème qu'il visait à résoudre
est traité différemment par `recupere_gf_ga_avec_repli` (section 12), qui
filtre nativement sur la compétition exacte avec garde-fou
promotion/relégation.

### 9.3 Convention H2H — RÉSOLUE le 25/08
`calcule_ratio_h2h` (section 13) calcule la moyenne de buts marqués par
chaque équipe sur les confrontations directes, symétrique par construction
— la question d'ordre "équipe A puis B" ne se pose plus avec cette formule.

### 9.4 Rotation continentale — ANNULÉE (voir section 5)

### 9.5 Rôle réel de BeSoccer
Repli documenté (priorité 2) jamais réactivé — matchendirect a suffi pour
tout le périmètre construit à ce jour.

### 9.6 Limite connue sur l'indice de forme — sans objet
Forme annulée entièrement le 25/08 (section 5) — cette limite ne s'applique
plus, plus aucun indice de forme n'est calculé.

### 9.7 Discipline des sources, toujours en vigueur -- précisée le 26/08
Ordre de priorité strict pour la forme/classement/H2H : matchendirect.fr,
seule autorité, jamais concurrencée. Betpawa/besoccer/FotMob/Sofascore n'y
contribuent jamais (voir décision explicite 15.8 sur Betpawa). **Exception
volontaire et unique, actée le 26/08** : pour les COTES seulement, Betpawa
est une source à part entière et concurrente de Bet365/matchendirect --
pas un repli, un choix délibéré (cotes réelles, celles sur lesquelles
l'utilisateur mise réellement). Les deux rôles ne se mélangent jamais :
Betpawa ne fournit jamais de stats, matchendirect ne fournit jamais de
cotes pour un match sourcé Betpawa.

### 9.8 Auto-déclaration à conserver — TOUJOURS EN VIGUEUR
`coefficients_empiriques: false` toujours présent dans `data.json` et
affiché explicitement sur le site (bloc risques, Module 4).

---

## 10. Fichiers actuels du dépôt (mis à jour 26/08 -- liste vérifiée
contre le dépôt réel, pas recopiée de mémoire)

**Scraping matchendirect**
- `scraper.py` — matchs aujourd'hui/demain, HTTP simple (inchangé depuis
  le 23/08, jamais touché par les travaux Betpawa)
- `scraper_semaine.py` — matchs J+2 à J+7, via Playwright (nouveau, 26/08,
  voir 15.9)
- `scraper_details.py` — classement/H2H/forme/cotes matchendirect (bug de
  cote corrigé le 26/08, voir tout en haut du document)

**Scraping/traitement Betpawa (tous nouveaux, 26/08)**
- `scraper_betpawa.py` — automatisation complète par navigateur (voir 15.7)
- `parse_betpawa.py` — parseur format copier-coller (français, séparé)
- `parse_betpawa_url.py` — parseur format récupération Claude (anglais, collé)
- `parse_betpawa_playwright.py` — parseur format navigateur automatisé
  (anglais, séparé) -- le format réellement produit par Playwright
- `GABARIT_COTES_MANUELLES.json` — documentation du format `cotes_manuelles`
- `betpawa_urls.txt` — liste d'URLs à traiter (une par ligne, format hybride
  optionnel avec `|`, voir 15.9)
- `test_scraping_betpawa.py` — script de diagnostic ponctuel (a confirmé
  qu'une requête HTTP simple ne peut pas voir les cotes Betpawa)

**Calcul et orchestration**
- `calculs.py` — Poisson/Dixon-Coles/EV/Kelly/GO-NO_GO/corrélation ;
  **calibré le 30/08/2026** (GA_REFERENCE_PAR_LIGUE, ALIAS_PAYS,
  K_SHRINKAGE, bornes défense élargies, SEUIL_EV_MIN relevé — voir
  section 0.2)
- `run_pipeline.py` — orchestrateur, inchangé depuis le passage à
  Supabase (30/08) ; étendu le 26/08 pour `cotes_manuelles`, les marchés
  handicap/O-U par équipe/pair-impair/cages inviolées, et les entrées sans
  `url_match` (voir section 15)
- `dispatch_pipeline.py` — **remplacé le 30/08** : point d'entrée réel du
  canal manuel (voir 0.5), lit désormais un panier Supabase par
  `panier_id` au lieu de `INPUT_MATCHS_JSON` en clair
- `verification_resultats.py` — **nouveau le 30/08** (voir 0.4), ferme la
  boucle de vérification automatique des scores, branché sur le run
  planifié uniquement

**Site (affichage)**
- `index.html` / `panier.html` / `pronostics.html` / `betpawa.html` —
  navigation croisée entre les quatre pages ; **30/08/2026 soir** : le
  script `@supabase/supabase-js` est bien présent dans `panier.html` ET
  `pronostics.html` (fait, testé -- voir 0.8), Supabase en service réel
- `script.js` — affichage Module 4 (chargé par `pronostics.html` — ce
  n'est PAS un fichier séparé nommé `pronostics.js`, confusion levée en
  session, voir 0.7) ; **30/08/2026** : lit Supabase avec repli sur
  `data.json` (voir 0.5) ; **30/08/2026 soir** : correctif critique
  `supabase` → `supabaseClient` (voir 0.8.5, le bug qui a bloqué toute
  la mise en service pendant des heures)
- `panier.js` — **30/08/2026** : session anonyme Supabase (voir 0.5) ;
  **30/08/2026 soir** : même correctif critique `supabase` →
  `supabaseClient` que `script.js` (voir 0.8.5) ; gère toujours les
  entrées Betpawa (étiquette, cotes conservées au copier-coller)
  (voir 0.5) ; gère toujours les entrées Betpawa (étiquette, cotes
  conservées au copier-coller)
- `style.css` — thème turquoise/or/vert ; **30/08/2026** : première passe
  responsive (max-width 1200px + un palier à 700px, voir 0.6)
- `betpawa.js` — page de dépôt Betpawa (détection auto domicile/extérieur,
  persistance de brouillon, détection d'URL collée par erreur -- 15.10)
- `parseBetpawa.js` — portage JS de `parse_betpawa.py` pour la page web
- `selection.js` — sélection avec cases turquoise
- `style.css` — thème turquoise/or/vert

**Données générées** (jamais éditées à la main, sauf `panier.json` et
`betpawa_urls.txt`)
- `matchs_du_jour.json` / `matchs_demain.json` / `matchs_semaine.json` /
  `panier.json` / `data.json` / `historique_pronostics.json`

**Autre**
- `Pipeline_Football_v_15082026_h2h_rotation.zip` — document génèse original
- `SOURCES_DONNEES_LIGUES.md` — **note 30/08/2026** : contenu finalement
  intégré directement dans ce document (section 0.3) plutôt que gardé à
  part, sur demande explicite de l'utilisateur ; ne pas recréer ce fichier
  séparément si retrouvé dans le dépôt, il est périmé par rapport à 0.3.
- `.github/workflows/pipeline.yml` — workflow unique ; **30/08/2026** :
  input `panier_id` (plus `matchs_json`), `concurrency` ajouté, étape
  `verification_resultats.py` ajoutée (run planifié uniquement, juste
  avant le commit), `git add panier.json historique_pronostics.json`
  conditionné au run planifié (voir 0.5/0.4)

## 11. Diagnostic et correctifs confirmés sur HTML réel (24/08/2026)

### 11.1 Blocage URL statistique — RÉSOLU
`recupere_details_match` lit le vrai lien "Stats des équipes" sur la page
de match par défaut. Retourne aussi lieu/météo/arbitre/diffuseur,
`url_equipe_domicile`/`url_equipe_exterieur` en un seul fetch.

### 11.2 Classement — RÉSOLU (2 correctifs)
Colonnes multi-niveaux aplaties (`columns.get_level_values(-1)`) + filtrage
des lignes non numériques avec `try/except` par ligne.

### 11.3 20 derniers résultats — historique, fonction remplacée
Voir section 7 — code mort depuis le 25/08, remplacé par le repli saison.

### 11.4 Cotes — RÉSOLU (2 correctifs), puis étendu le 25/08
Ancrage par égalité de texte strippé (pas de regex fragile) + parcours des
seuls nœuds de texte (`find_all_next(string=True)`) pour éviter le double
comptage. Étendu aux lignes over/under 0.5 à 7.5 le 25/08 — **c'est cette
extension qui a révélé le bug de cote actuellement ouvert (voir tout en
haut).**

### 11.5 Pages explorées et écartées
`?p=compositions` et `?p=forum` : écartés, coût/bénéfice défavorable.
`/equipe/{slug}.html` : PAS écarté finalement — devenu la source
principale du GF/GA via le repli saison (section 12), décision inversée
par rapport à ce qui était noté ici le 24/08.

### 11.6-11.8 : historique de session, sans action requise aujourd'hui.

---

[SECTION 12 MANQUANTE DE CE DOCUMENT — voir note ci-dessous]

---

## 13. Modules 2/3/4 (repris fidèlement, avec périmètre réduit assumé) + Sélection manuelle (25/08/2026)

### 13.1 Décisions de périmètre, actées explicitement
- Forme, Absences, Distance : ANNULÉS (Forme jamais formalisée sur ce
  projet, Absences non fiable à scraper sur matchendirect, Distance jamais
  commencée). Seuls Classement et H2H alimentent l'Étape 3 du Module 2.
- Année de repos (jours_repos) : NON implémentée.
- Risque de rotation continentale : ANNULÉ, jamais implémenté.
- Handicap 3 voies (Étape 0 Module 3) : EXCLU.
- Score exact, pair/impair, cages inviolées : calculés mais JAMAIS dans
  LISTE_A/LISTE_B — aucune cote scrapée pour ces marchés. Affichés en
  lecture seule dans le détail N1 du site.
- Betpawa : idée d'origine (25/08) abandonnée avant tout test réel --
  utiliser Betpawa comme "cote de référence" via minimum du panel de
  bookmakers scrapés. **Périmée, remplacée le 26/08** par une intégration
  directe et bien plus ambitieuse (source de cotes à part entière, pas un
  proxy) -- voir section 15.

### 13.2 Étape 3 Module 2 — Classement + H2H, branchés et testés
`calcule_ratio_classement` et `calcule_ratio_h2h` ajoutés à `calculs.py`.
`ratio_h2h_away = -ratio_h2h_home` : valide mathématiquement (clamp est une
fonction impaire). Confirmé sur run réel : `ajustement_home`/
`ajustement_away` non nuls pour la première fois de la session.

### 13.3 Étapes 1-2-4-6-7 Module 3 — GO/NO_GO complet, branché et testé
- `recupere_cotes_marches` étendue aux lignes over/under 0.5 à 7.5.
- BUG TROUVÉ EN AUDIT ET CORRIGÉ : `construit_probabilites_marches` était
  appelée avec ses lignes par défaut (0.5-4.5 seulement) — corrigé.
- `correlation_marches` (calcul exact de Pearson sur la matrice jointe) +
  `construit_liste_a`/`construit_liste_b` + `decision_go_nogo` ajoutés.
- CONFIRMÉ SUR RUN RÉEL (22 matchs, 25/08/2026) : verdicts cohérents,
  mises Kelly plausibles, "pari en or" correct, confiance FAIBLE détectée
  sur asymétrie réelle (10 matchs domicile / 1 extérieur), garde-fou
  promotion/relégation généralisé avec succès à un cas de coupe.

### 13.4 Module 4 — affichage, complet
Badge GO/NO_GO coloré, paris recommandés (LISTE_B), "pari en or" ⭐ selon
critère probabilité (pas EV), bloc risques, section dépliable N1/N2.

### 13.5 Navigation entre les deux pages du site
Corrigée — bouton croisé en en-tête de chaque page.

### 13.6 Piège opérationnel réel
`matchs_selectionnes.json` collé deux fois sans remplacer = `[...] [...]`,
JSON invalide, échec silencieux (0 match traité, sans erreur visible).
Toujours vérifier le contenu réel du fichier après un collage.

### 13.7 Refonte visuelle (25/08, en fin de session)
Palette turquoise/or/vert/rouge (rouge réservé aux alertes), hiérarchie à
5 niveaux (identification/statut/donnée principale/détails/action),
couleur jamais seul vecteur d'information (texte + icône toujours
présents). CORRECTIF IMPORTANT : la probabilité mise en avant n'est plus
systématiquement celle de la victoire domicile — c'est désormais la
probabilité du pari réellement retenu (pari en or de LISTE_B), avec un
texte "pourquoi ce pari" justifiant cote/EV/confiance. Rien n'est affiché
si NO_GO.

### 13.8 Automatisation complète (bouton unique, zéro copier-coller) — PAS FAITE
Nécessite une fonction serverless Netlify + un token GitHub (`repo` scope)
déposé par l'utilisateur dans les variables d'environnement Netlify. En
attente de confirmation utilisateur avant de coder.

### 13.9 Reste à faire
- BUG DE COTE — RÉSOLU le 26/08 (voir tout en haut du document et 14.8).
  Reste à confirmer sur un run réel de production.
- Fonction serverless Netlify (13.8).
- Vérifier le seuil de corrélation 0.70 sur un échantillon plus large.
- `index.html`/`selection.html` jamais testés sur desktop.
- 
## 14. Refonte panier.json + cotes Bet365 fixe (26/08/2026)

### 14.1 Architecture "panier" (introduite hors de cette conversation, découverte le 26/08)
Une autre session a unifié `matchs_selectionnes.json` et un ancien
`matchs_manuels.json` en un seul fichier `panier.json`, acceptant trois
formats d'entrée (simple `match_id`, objet `{match_id}`, ou objet complet
manuel avec `url_match`/`domicile`/`exterieur`/`competition`). Ajouts
associés : `matchs_demain.json` (matchs du lendemain, même structure que
`matchs_du_jour.json`) et `historique_pronostics.json` (archive
append-only de chaque run, jamais purgée -- croissance non bornée
assumée, à surveiller après plusieurs mois).
`panier.json` est vidé automatiquement après chaque run ayant traité au
moins un match, forçant une sélection consciente à chaque cycle plutôt
que de risquer un panier périmé silencieux.

### 14.2 Piège du double-tableau JSON — récidive, cause confirmée
Le même bug que `matchs_selectionnes.json` (section 13.6) s'est reproduit
sur `panier.json` : un `[]` vide collé avant la vraie liste
(`[][{...}]`), invalide comme JSON unique, donnant silencieusement 0
match traité. Cause : coller une nouvelle sélection sans remplacer
totalement le contenu précédent. Toujours vérifier le contenu réel du
fichier après un collage, pas seulement supposer qu'il est bon.

### 14.3 Correctif "25/08bis" (cotes multi-bookmakers) — ÉCHEC confirmé, ABANDONNÉ
Un correctif visant le bug historique des cotes invraisemblables sur
lignes over/under hautes (voir bug ouvert en tête de document) a tenté de
détecter un "séparateur texte" entre bookmakers pour fiabiliser le
comptage par paquets. Sur un run réel de 25 matchs, ce correctif a
produit un échec quasi total : `cote_1: null` sur les 25 matchs,
`groupes_valides: 0` sur la quasi-totalité des marchés. Cause racine
identifiée en récupérant le vrai HTML d'un match (Lyon-Fenerbahce,
26/08) : **le nom de chaque bookmaker n'existe QUE dans l'attribut `alt`
d'une image (`<img alt="bet365 logo">`), jamais comme texte visible sur
la page.** Le correctif cherchait un séparateur texte qui n'a jamais
existé ; ce qu'il détectait comme "séparateur" était très probablement le
caractère `-` (cote indisponible), cassant le comptage sur la quasi-
totalité des lignes. Correctif retiré entièrement.

### 14.4 Changement de méthode : Bet365 fixe, abandon du multi-bookmaker (26/08)
Décision explicite : un seul bookmaker fixe (Bet365) plutôt que plusieurs
bookmakers avec sélection du minimum ("proxy Betpawa", section 13.1).
Simplifie radicalement le code : ancrage direct sur l'image
`alt="bet365 logo"` (recherche par attribut, pas par texte), lecture des
valeurs qui suivent immédiatement jusqu'à la prochaine image ou fin de
section. Plus de comptage par paquets, plus de détection de séparateur.
Une cote manquante (`-`) devient `None` pour cette seule sélection, sans
invalider le reste du marché. Bookmaker absent d'une section entière ->
marché à `None`, jamais deviné.
Choix de Bet365 : seul bookmaker observé présent sur toutes les lignes
over/under du match de référence, y compris les plus hautes (6.5, 7.5)
où les autres bookmakers disparaissent souvent.
**Abandon assumé de l'approximation Betpawa** ("minimum du panel") au
profit d'une seule cote Bet365, structurellement différente (plus
généreuse que Betpawa) mais bien plus fiable techniquement.
`recupere_cotes_marches` ne renvoie plus un tuple `(marches,
diagnostics)` -- juste le dict des marchés, le diagnostic de repli n'a
plus lieu d'être avec une seule source.

### 14.5 Validation réelle du correctif (26/08, 25 matchs)
Premier run avec cotes Bet365 fixes sur la sélection réelle de 25 matchs :
`cote_1` renseigné sur la totalité des matchs traités (contre `null`
systématique avant). Plusieurs matchs passent de `NO_GO` à `GO` pour la
première fois de façon légitime (Valence-Real Betis, Abha-Al Khaleej,
Al Taawon-Al Fayha, Real Madrid-Real Sociedad), avec des EV et mises
Kelly cohérents. Un cas de confiance FAIBLE correctement signalé malgré
un EV élevé (Abha-Al Khaleej, 1 seul match domicile disponible) --
prudence recommandée sur ce type de cas malgré un verdict GO technique.

### 14.6 Limite connue, assumée
Bet365 ne couvre pas forcément tous les marchés sur les compétitions
confidentielles (petites coupes, championnats mineurs, jeunes/U21) --
attendre des `cote_1: null` fréquents sur ce type de matchs, ce n'est pas
un bug mais une limite de couverture du bookmaker choisi.

### 14.7 Bug ouvert historique (tête de document) — statut
Le bug de cote invraisemblable sur ligne over/under haute (Gil Vicente-
Casa Pia, 25/08) est traité indirectement : la nouvelle méthode Bet365
fixe élimine la cause structurelle (comptage par paquets sensible à un
bookmaker manquant). Le cas précis n'a pas été retesté sur ce match
exact (déjà commencé), mais le mécanisme qui produisait l'erreur n'existe
plus dans le nouveau code.

### 14.8 Bug de cote — cause racine réelle confirmée et corrigée (26/08)
Le passage à Bet365 fixe (14.4) n'était pas la cause du bug de cote
invraisemblable -- une deuxième cause, indépendante, a été identifiée en
récupérant du HTML réel (match Valence-Real Betis, LaLiga, 26/08) :
`recupere_cotes_marches` ancrait sur un titre de marché via
`soup.find(string=...)`, qui retourne la PREMIÈRE occurrence dans tout le
document. Un même titre de marché peut apparaître deux fois sur la page
matchendirect -- une fois dans un widget d'aperçu en haut (sans Bet365),
une fois dans le tableau complet plus bas (avec Bet365). Confirmé
concrètement : "Mi-temps - Résultat" apparaît selon ce schéma exact sur
la page réelle inspectée. Si l'aperçu affiche un jour un marché
réellement exploité (1N2, BTTS, une ligne over/under) au lieu de
"Mi-temps", l'ancrage sur la première occurrence fait dériver la marche
`find_all_next()` (sans limite) à travers le contenu intermédiaire de la
page jusqu'au prochain titre reconnu, renvoyant potentiellement la cote
Bet365 d'un AUTRE marché -- réelle, mais mal associée, sans jamais
produire de `None` ni d'erreur. Correctif : `soup.find` -> `soup.find_all`
+ sélection de la DERNIÈRE occurrence (le tableau complet étant
structurellement en dernière position sur la page). Commité sur `main`.
Non testé en conditions réelles de production (accès réseau à
matchendirect.fr indisponible depuis l'environnement d'édition) --
à confirmer au prochain run réel, en particulier `cote_1` sur les lignes
over/under 5.5+.

---

## 15. Intégration Betpawa (26/08)

### 15.1 Cotes manuelles -- principe
Nouveau champ optionnel `cotes_manuelles` dans une entrée `panier.json`.
Présent -> `construit_signaux()` saute le scraping matchendirect/Bet365 et
utilise ce dict directement comme `cotes_marches`. Absent -> comportement
strictement inchangé (scraping normal). Structure attendue : voir
`GABARIT_COTES_MANUELLES.json`, à la racine du dépôt.

### 15.2 Nouveaux marchés dans l'analyse automatique
`construit_candidats()` étendu : handicap 2 choix (lignes demi-entières
uniquement), over/under par équipe, pair/impair, cages inviolées. Ces
marchés étaient déjà calculés par `calculs.py` mais jamais exploités faute
de cote scrapée -- aucun effet sur les matchs matchendirect/Bet365 (cote
toujours absente pour ces clés côté scraping), actifs uniquement quand des
cotes manuelles les fournissent.

Score exact et nombre exact de buts restent **volontairement exclus** par
défaut (`INCLURE_SCORE_EXACT_DANS_ANALYSE` / `INCLURE_NOMBRE_EXACT_BUTS_
DANS_ANALYSE` dans `run_pipeline.py`, tous deux `False`) -- probabilités
individuelles trop faibles, marché le plus sensible à une erreur de modèle.
Bascule à `True` volontairement si le risque est jugé acceptable.

### 15.3 Matchs sans URL matchendirect
`normalise_panier()` accepte maintenant une entrée avec `cotes_manuelles`
mais SANS `url_match` (à condition d'un `match_id` explicite). `construit_
signaux()` la traite proprement : `raison_non_traite` explicite ("pas
d'URL matchendirect, forme/classement/H2H indisponibles, lambda non
calculable"), jamais un plantage ni une valeur devinée. Cas fréquent pour
un match Betpawa dont le championnat n'est pas couvert par matchendirect --
reste un point ouvert (voir 15.6) si on veut vraiment analyser ces matchs.

### 15.4 Deux méthodes d'apport, en parallèle, chacune indépendante
**Décision (26/08)** : garder les deux, pas de méthode unique -- si l'une
échoue pour un match donné, basculer sur l'autre.

- **Copier-coller** (page `betpawa.html`, `betpawa.js`, `parseBetpawa.js`) :
  Patrick colle le texte brut copié depuis l'app Betpawa (téléphone),
  domicile/extérieur détectés automatiquement depuis le texte (ligne après
  "Retour"), compétition saisie manuellement mais persistée d'un ajout à
  l'autre (`localStorage`, clé `archetype_derniere_competition`) -- elle
  n'apparaît pas dans le texte copiable sur cette page Betpawa. Tout se
  passe dans le navigateur, pousse directement dans le panier partagé
  (`localStorage` `archetype_panier`, même clé que `index.js`/`panier.js`).
  Validation de formulaire précise : champ manquant nommé explicitement et
  entouré en rouge (pas de message générique après deux confusions
  placeholder/valeur remplie).

- **URL** (`parse_betpawa_url.py`, exécuté par Claude dans le chat, pas
  déployé côté site) : Patrick donne l'URL `betpawa.cm/event/...`, Claude
  la récupère et en extrait domicile/extérieur/compétition (fiable, depuis
  les métadonnées de la page, jamais depuis un copier-coller) + toutes les
  cotes, puis renvoie l'entrée `panier.json` complète à coller à la main.
  Format de page RADICALEMENT différent du copier-coller : étiquette et
  valeur collées sans séparateur ("11.94" = "1" + "1.94"), nécessite un
  parseur dédié (pas un portage du premier). Fonctionne uniquement en
  circuit manuel via le chat -- une page du site ne peut pas récupérer une
  URL betpawa.cm elle-même (CORS, hors de notre contrôle).

### 15.5 Couverture des marchés Betpawa -- limite réelle, pas un bug
Testé sur 5 matchs réels, 4 championnats : Angleterre (25+ marchés),
Afrique du Sud (18-19), Corée du Sud (23), **Arménie (2 marchés
seulement -- 1X2 et double chance)**. La richesse de l'offre Betpawa varie
énormément selon la confidentialité du championnat -- attendre des
`cotes_manuelles` très pauvres sur les petites ligues, ce n'est pas un
défaut du parseur.

Une URL de type `betpawa.cm/events/group/...` (liste de matchs d'un
championnat) N'EST PAS une page de match individuel -- `parse_betpawa_url.py`
ne la traite pas. Toujours donner l'URL `/event/...` du match précis.

### 15.6 Stats Betpawa comme source de forme -- TRANCHÉ, pas reporté (voir 15.8)

### 15.7 Automatisation complète par navigateur (26/08, après 15.4)
Décision utilisateur : Betpawa devient la priorité absolue pour les cotes
("on mise sur ces cotes réelles"), matchendirect passe au second plan pour
les stats. `scraper_betpawa.py` automatise entièrement la méthode URL
(15.4) : lit `betpawa_urls.txt`, ouvre chaque page avec Playwright/Chromium,
extrait domicile/extérieur/compétition depuis le titre de la page, puis les
cotes. Tourne dans `pipeline.yml`, zéro intervention manuelle au-delà de
l'ajout de l'URL au fichier.

**Découverte critique en cours de route** : le format de texte capturé par
un vrai navigateur automatisé est un TROISIÈME format, différent des deux
déjà connus (copier-coller téléphone : français, séparé ; récupération
Claude : anglais, collé) -- anglais, mais séparé. Confirmé sur capture
d'écran d'un run réel GitHub Actions. `parse_betpawa_playwright.py` créé
pour ce format précis. `scraper_betpawa.py` essaie les trois parseurs et
garde celui qui reconnaît le plus de marchés -- résiste au format réel sans
savoir à l'avance lequel des trois s'appliquera.

**Bug de dédoublonnage trouvé et corrigé** : un match déjà présent dans
`panier.json` (ex. d'un run précédent ayant échoué, 0 marché) était
purement et simplement IGNORÉ au lieu d'être mis à jour -- les cotes
fraîchement récupérées étaient jetées silencieusement. Corrigé : une
entrée existante est désormais REMPLACÉE, jamais ignorée.

**Validé en conditions réelles** (26/08, AC Horsens - Viborg FF,
Superliga danoise) : 25 marchés extraits automatiquement, aucune
intervention manuelle après l'ajout de l'URL.

### 15.8 Décision finale sur les stats Betpawa -- matchendirect reste seul
Une tentative réelle d'extraire classement/forme/H2H depuis Betpawa (pour
remplacer entièrement matchendirect comme source de forme, cf. ancienne
section 15.6) a échoué techniquement : même après avoir cliqué sur les
onglets "Team stats"/"H2H"/"Form" avec Playwright, ces données
n'apparaissent PAS dans le texte capturé -- confirmé deux fois sur capture
d'écran de run réel. Hypothèse la plus probable : données visibles
seulement après connexion à un compte Betpawa (page affiche
"LOGIN"/"JOIN NOW"), pendant que l'outil de récupération de Claude (pas un
navigateur) y accède autrement (contenu pré-généré pour le référencement,
accessible sans connexion).

**Décision explicite de l'utilisateur, définitive** : ne pas poursuivre
cette piste. Matchendirect reste l'UNIQUE source de forme/classement/H2H,
Betpawa reste l'UNIQUE source de cotes pour les matchs qu'il apporte. Les
deux rôles ne se mélangent jamais (voir 9.7). Toute reprise future de
l'idée "stats Betpawa" doit repartir de ce constat d'échec technique, pas
le reconsidérer comme une option jamais essayée.

### 15.9 Système hybride Betpawa (cotes) + matchendirect (forme) (26/08)
`betpawa_urls.txt` accepte un format à deux URLs par ligne, séparées par
`|` : `URL_BETPAWA | URL_MATCHENDIRECT`. La deuxième URL alimente
`url_match`, permettant un vrai calcul GO/NO_GO complet (lambda calculé
sur données matchendirect, comparé aux cotes Betpawa). Sans elle, le match
reste "non traité" (15.3).

**Recherche automatique ajoutée pour éviter la saisie manuelle** :
`cherche_url_matchendirect_auto()` compare les noms d'équipe Betpawa à
`matchs_du_jour.json`/`matchs_demain.json`/`matchs_semaine.json` (J+2 à
J+7, voir ci-dessous) avant de retomber sur l'URL manuelle du `|`. Ne
retient jamais une correspondance ambiguë (plusieurs candidats) -- mieux
vaut aucune URL automatique qu'une mauvaise.

**BUG DANGEREUX TROUVÉ ET CORRIGÉ avant tout déploiement** : la première
version de cette recherche traitait "Manchester City" et "Manchester
United" comme la même équipe (les mots "United"/"City"/"Real"/"Athletic"
etc. étaient traités comme du bruit générique à ignorer, réduisant
"Manchester United" à "Manchester", inclus dans "Manchester City"). Ces
mots sont précisément ce qui distingue des clubs rivaux d'une même ville
-- retirés de la liste des mots ignorés. Testé ensuite sur une douzaine de
cas pièges (Real Madrid/Real Betis, Athletic Bilbao/Atletico Madrid,
Newcastle United/Sheffield United...) avant validation. Point de vigilance
permanent : c'est une heuristique de correspondance de texte, pas une
identité garantie -- un futur cas piège non anticipé reste possible (voir
section 6).

**`scraper_semaine.py` créé pour élargir la fenêtre de recherche
automatique** : `scraper.py` ne couvre qu'aujourd'hui/demain, et "demain"
échoue en pratique (redirection confirmée vers la page du jour, voir
section 3). Un nouveau script, séparé de `scraper.py` (zéro risque sur le
flux "aujourd'hui" qui fonctionne), utilise Playwright pour récupérer
J+2 à J+7 -- Playwright contourne le blocage qui empêche une requête HTTP
simple de voir ces pages. Confirmé en conditions réelles (26/08) : 6 jours
récupérés, 2531 matchs au total, sans limite de nombre par jour (le
plafond initial de 200/jour a été retiré à la demande explicite de
l'utilisateur -- le temps de calcul en plus est jugé négligeable).

### 15.10 Corrections d'ergonomie sur betpawa.js (26/08)
Deux confusions récurrentes corrigées à la racine plutôt que par un
rappel répété :
- **URL collée dans le champ texte des marchés** : la page attend le texte
  copié des cotes, pas un lien -- confusion survenue plusieurs fois de
  suite malgré des rappels. Détection automatique (`^https?://`) avec
  message explicite redirigeant vers le bon circuit (chat ou
  `betpawa_urls.txt`), avant toute autre validation.
- **Perte de saisie au rechargement de la page** : Safari recharge parfois
  la page en arrière-plan (gestion mémoire iOS) quand l'utilisateur change
  d'application pour aller chercher une URL ailleurs, vidant le
  formulaire. Chaque champ se sauvegarde désormais à chaque frappe
  (`localStorage`) et se restaure au chargement -- un rechargement ne perd
  plus rien. Effacé automatiquement après un ajout réussi. Attention au
  point d'ordre d'exécution : la restauration du brouillon doit passer
  AVANT le pré-remplissage de la dernière compétition utilisée (15.4),
  sinon ce dernier écrase une saisie de compétition en cours avec une
  valeur plus ancienne.
