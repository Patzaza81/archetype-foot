# Archetype Foot — Document de transition
Dernière mise à jour : 26/08/2026 (audit complet post-intégration Betpawa,
correction de plusieurs affirmations devenues fausses en cours de session),
dans la continuité d'une session longue.
Objectif de ce document : permettre de reprendre le projet dans une nouvelle
fenêtre de conversation sans perdre l'historique de décisions, ni répéter
les erreurs déjà identifiées et corrigées.

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
  → scraper.py           (matchs aujourd'hui/demain — matchendirect, HTTP simple)
  → scraper_semaine.py   (matchs J+2 à J+7 — matchendirect, via Playwright,
                           contourne le blocage HTTP simple confirmé -- 15.9)
  → scraper_betpawa.py   (cotes + marchés Betpawa, via Playwright,
                           JS requis pour voir les cotes -- 15.7)
  → scraper_details.py   (classement, H2H, forme -- matchendirect, HTTP simple)
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
- **FootyStats.org** : payant dès le premier palier (30£/mois), écarté.
- **Football-Data.co.uk** : piste identifiée mais jamais retenue.
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
- `calculs.py` — Poisson/Dixon-Coles/EV/Kelly/GO-NO_GO/corrélation (inchangé
  par les travaux Betpawa)
- `run_pipeline.py` — orchestrateur ; étendu le 26/08 pour `cotes_manuelles`,
  les marchés handicap/O-U par équipe/pair-impair/cages inviolées, et les
  entrées sans `url_match` (voir section 15)

**Site (affichage)**
- `index.html` / `panier.html` / `pronostics.html` / `betpawa.html` —
  navigation croisée entre les quatre pages
- `script.js` — affichage Module 4
- `panier.js` — panier partagé, gère les entrées Betpawa (étiquette,
  cotes conservées au copier-coller)
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
- `.github/workflows/pipeline.yml` — workflow unique, étapes matchendirect
  (jour/semaine) puis Betpawa puis calcul, dans cet ordre

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
