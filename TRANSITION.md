# Archetype Foot — Document de transition
Dernière mise à jour : 25/08/2026, dans la continuité d'une session longue.
Objectif de ce document : permettre de reprendre le projet dans une nouvelle
fenêtre de conversation sans perdre l'historique de décisions, ni répéter
les erreurs déjà identifiées et corrigées.

---

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
- **Playwright / navigateur automatisé** : abandonné avec BeSoccer. Aucune
  page matchendirect utilisée n'en a jamais eu besoin.
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

### 9.7 Discipline des sources, toujours en vigueur
Ordre de priorité strict : (1) matchendirect.fr, autorité en cas de
conflit ; (2) besoccer.com, repli jamais réactivé ; (3) FotMob/Sofascore,
jamais utilisées. Aucune source hors de cette liste ne doit être citée
comme preuve d'un fait utilisé dans un calcul.

### 9.8 Auto-déclaration à conserver — TOUJOURS EN VIGUEUR
`coefficients_empiriques: false` toujours présent dans `data.json` et
affiché explicitement sur le site (bloc risques, Module 4).

---

## 10. Fichiers actuels du dépôt (mis à jour 25/08)

- `scraper.py` — matchs du jour (inchangé depuis le 23/08)
- `scraper_details.py` — classement/H2H/cotes/repli saison (testé en
  conditions réelles, étendu aux lignes over/under 0.5-7.5)
- `calculs.py` — Poisson/Dixon-Coles/EV/Kelly/GO-NO_GO/corrélation (testé)
- `run_pipeline.py` — orchestrateur, flux sélection manuelle + GO/NO_GO
- `index.html` / `selection.html` — navigation croisée entre les deux pages
- `script.js` — affichage Module 4, hiérarchie visuelle à 5 niveaux
- `selection.js` — sélection avec cases turquoise
- `style.css` — thème turquoise/or/vert (refonte du 25/08)
- `matchs_du_jour.json` / `matchs_selectionnes.json` / `data.json` — générés
- `Pipeline_Football_v_15082026_h2h_rotation.zip` — document génèse original

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
- Betpawa : cote de référence = minimum du panel de bookmakers scrapés —
  Betpawa lui-même absent de tous les panels observés.

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
- BUG DE COTE (voir tout en haut du document) — priorité absolue.
- Fonction serverless Netlify (13.8).
- Vérifier le seuil de corrélation 0.70 sur un échantillon plus large.
- `index.html`/`selection.html` jamais testés sur desktop.
