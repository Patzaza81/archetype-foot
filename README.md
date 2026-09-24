# ARCHETYPE Foot

Système d'analyse de matchs de football : collecte automatique des matchs et des cotes, modèle statistique
(Poisson, `moteur_v2_6_9.py`), sélection de pronostics **justifiés par des données réelles**, et publication sur un site pensé pour
le mobile (iPhone). Le tout tourne chaque nuit sur GitHub Actions et se publie sur Netlify.

> Ce document décrit l'**architecture et les règles**, qui changent peu. L'état courant s'obtient avec
> `git log` et `ROADMAP.md`. Dernière vérification de ce README : 24/09/2026 (journal de rentabilité, page du second moteur).

---

## 1. Vue d'ensemble

```
matchendirect.fr ─┐                                   ┌─▶ pont_moteur.py ─▶ moteur_v2_6_9.py (le moteur)
betpawa.cm ───────┴─▶ SCRAPING ─▶ matchs_*.json ─▶ precalcul.py ─┤
                      (scraper*.py, resolution_betpawa*.py)      └─▶ bibliotheque_justification.py (les textes)
                                                                  │
                                    precalcul.json (complet) + precalcul_leger.json (site)
                                                                  │
                     vérification des résultats · tickets · calibration · état système
                                                                  │
                                            git push ─▶ Netlify ─▶ site (pages HTML/JS/CSS statiques)
```

Le site est **entièrement statique** : il lit des fichiers JSON produits par le pipeline. Le navigateur ne choisit
aucun pronostic et ne calcule aucune statistique.

---

## 2. Le pipeline nocturne

Workflow : `.github/workflows/pipeline.yml` — déclenché chaque jour à **21:00 UTC** (22:00 au Cameroun) ou à la main
(`workflow_dispatch`). Avant tout scraping, une étape **fail-fast** lance les autotests du moteur et du pont puis `pytest` : un moteur cassé arrête le job en quelques secondes. Un seul run à la fois (`concurrency`, sans annulation du run en cours). Les runs réussis récents
durent de 1 h 30 à 3 h 30, l'essentiel du temps étant la résolution BetPawa.

| # | Étape | Script | Sortie principale |
|---|---|---|---|
| 1 | Listes de matchs J0 et J+1 | `scraper.py` | `matchs_du_jour.json`, `matchs_demain.json` |
| 2 | Liste J+2 et J+3 (non bloquante) | `scraper_semaine.py` | `matchs_semaine.json` |
| 3 | Pré-calcul J0 → J+3 + résolution BetPawa + **moteur** | `precalcul.py` (→ `branchement_moteur.py`) | `precalcul.json` (complet), `precalcul_leger.json` (site), `export_moteur/` (entrées exactes du moteur), `matchs_*_filtre.json`, `historique_pronostics.json`, `archive/AAAA-MM.json` |
| 4 | Garde : le pré-calcul a-t-il produit un résultat exploitable ? | (dans le workflow) | arrête le job sinon |
| 5 | Vérification des résultats réels | `verifie_resultats_archetype_model.py` | règlement de l'archive (`SELECTED` / `COUNTERFACTUAL`) |
| 6 | Tickets fictifs (mode observation) | `observe_tickets_archetype_model.py` | `tickets_observes/AAAA-MM.json` |
| 7 | Tentative de vrais tickets (seuil réel, jamais assoupli) | `genere_tickets_reels_archetype_model.py` | `vrais_tickets/AAAA-MM.json` |
| 8 | Bilan comportemental | `calcule_matrice_archetype_model.py` | `bilan_archetype_model.json` |
| 9 | ~~Calibration adaptative~~ **désactivée** (elle réglait l'ancien modèle) | `calibre_archetype_model.py` | — |
| 10 | État système pour la page Système | `construit_etat_systeme.py` | `etat_systeme.json` |
| 11 | Commit et push du résultat | (dans le workflow) | mise à jour du dépôt |
| 12 | Signalement des constats majeurs | `notifie_constat_majeur.py` | Issue GitHub, s'il y en a |

Les étapes 4 à 12 ne tournent que pour un run planifié ou une relance complète. L'audit passif écrit en plus
`data/audit_status.json`, `data/audit_telemetry.json` et `data/audit_odds_snapshots.json`.

⚠ Plusieurs étapes sont en `continue-on-error` : **un run vert ne prouve pas que tout a fonctionné**. Il faut
inspecter les fichiers produits (règle de `ROADMAP.md`).

---

## 3. Les moteurs

### 3.1 Scraping
Sources : `matchendirect.fr` (listes, équipes, H2H, classements : HTTP simple avec `requests`) et `betpawa.cm`
(cotes : navigateur automatisé Playwright).

| Fichier | Rôle |
|---|---|
| `scraper.py`, `scraper_semaine.py` | Listes de matchs (la seconde passe par Playwright pour J+2/J+3) |
| `scraper_details.py` | Pages d'équipes : classement, forme, H2H, historique de buts |
| `resolution_betpawa.py`, `resolution_betpawa_precalcul.py`, `scraper_betpawa.py`, `parse_betpawa*.py` | Trouver le match sur BetPawa et lire ses cotes |
| `cache_equipes.py`, `cache_h2h.py`, `cache_classement.py`, `cache_betpawa.py` | Mémoires persistantes (`cache_*.json`) pour ne pas refaire les mêmes requêtes |

Règle de sécurité du matching BetPawa : **mieux vaut aucun match qu'un mauvais match** (aucune correspondance
ambiguë n'est acceptée).

`run_pipeline.py` et `calculs.py` forment l'**ancien moteur**. `archetype_model` est prioritaire ; l'ancien moteur ne
sert de repli qu'en cas d'*erreur technique* (exception), jamais pour une décision métier normale. `precalcul.py` continue
d'en calculer les champs historiques (listes A/B, Kelly, `verdict_global`…), que le site ne lit pas, et
`scraper.py` en importe `aujourdhui_france()`.

### 3.2 Le moteur : `moteur_v2_6_9.py`
Le moteur du pipeline est `moteur_v2_6_9.py` (spec V2.6.2 + vérificateurs V1 à V12) : un couple de λ par match (moyenne
buts marqués / encaissés, domicile à domicile et extérieur à l'extérieur), matrice de Poisson, puis pour chaque marché coté :
probabilité, edge, EV, statut, catégorie A à D (D = EV > 30 % ou deux artefacts, écartée). Ses constantes sont **fixes dans
le code** : il n'y a plus de calibration adaptative. `python moteur_v2_6_9.py --autotest` vérifie ses invariants.

| Fichier | Rôle |
|---|---|
| `pont_moteur.py` | Traduit un signal du pipeline (cotes BetPawa imbriquées, statistiques d'équipe) vers l'entrée du moteur ; exporte les entrées dans `export_moteur/` (un fichier par date : `python moteur_v2_6_9.py export_moteur/matchs_moteur_AAAA-MM-JJ.json --date AAAA-MM-JJ` rejoue le calcul) |
| `branchement_moteur.py` | Exécute le moteur dans le pipeline et convertit sa sortie : nom canonique des marchés, justification, règle NO DATA → NO GO, sélection P1/P2/P3, archive |

**Données d'entrée du moteur : `stats_saison_en_cours.py`.** Statistiques d'équipe = **saison en cours uniquement, matchs les
plus récents** (12 par lieu, domicile pour l'équipe qui reçoit, extérieur pour la visiteuse), via le chargeur `archetype_model/data/loader.py`
(une requête, jamais de `?season=`, ordre chronologique). Cache distinct : `cache_equipes_saison.json`. Aucun repli sur la saison
précédente (décision non négociable du 08/09/2026) : une équipe sans match cette saison est refusée. En début de saison les
échantillons sont donc petits ; le moteur l'affiche (« Fenêtre d'analyse trop courte », visible dans les détails). L'ancien collecteur à
repli (`scraper_details.recupere_gf_ga_avec_repli`) ne sert plus qu'à l'ancien calcul de `construit_signaux()` : mélange de saisons et
N plus anciens matchs, il ne doit pas alimenter le moteur.

Règles de décision (`branchement_moteur.py`, D1 à D6) : **un match n'est analysé que si l'équipe qui reçoit a au moins 2 matchs à domicile et la visiteuse au moins 2 matchs à l'extérieur cette saison** (sinon refus `echantillon_insuffisant`, avec les deux effectifs) ; candidat = value bet hors catégorie D ; sans preuve spécifique à son
marché, pas de choix ; au plus trois choix — **P1 favori** (probabilité la plus haute), **P2 value** (meilleur EV des
restants), **P3 coup de poker** (meilleur EV des restants avec cote ≥ 2,91 et probabilité ≥ 20 %), mêmes règles que le
site ; aucun repli sur l'ancien moteur (une exception sur un match donne `ERREUR_TECHNIQUE`) ; solidité affichée = catégorie
A/B/C.

Le bloc produit sur chaque signal est `moteur_v2_6_9` (`moteur_utilise = "moteur_v2_6_9"`) : statut (`OK`, `SKIP`,
`NON_EXPORTABLE`, `ERREUR_TECHNIQUE`), verdict, λ, `selection` P1/P2/P3 avec justification, `candidats`, `rejets`, `inventaire`
complet. Les choix retenus sont archivés en `SELECTED`, les autres value bets en `COUNTERFACTUAL` (`model_version` =
`moteur_v2_6_9`).

**Ancien modèle `archetype_model/` — débranché puis nettoyé le 21/09/2026.** `archetype_model/main.py` (point d'entrée),
`rattrapage_justification.py`, le repli sur l'ancien moteur et le test de bout en bout de l'ancien moteur sont **supprimés** ; les
scénarios de l'ancien moteur ont quitté `audit_permanent.py`. Le dossier `archetype_model/` reste, car `precalcul.py` et le
nouveau système en utilisent encore : `learning/` (archive, règlement des résultats, bilan), `h2h/` (confrontations directes),
`data/odds_provider.py`. Les sous-paquets `poisson/`, `signals/`, `edv/`, `statistics/` ne sont plus appelés en production
(`backtest/boucle_b.py` et l'audit s'en servent encore) : suppression à décider séparément. `tests/test_integrite_du_depot.py`
vérifie que tout fichier compile, que tout module d'`archetype_model` s'importe et que tout script du workflow s'importe.

### 3.3 La bibliothèque de justification
`bibliotheque_justification.py` (avec son enveloppe `justification.py`) écrit le texte que le site affiche : une
synthèse, des preuves statistiques, et les statistiques exactes ayant servi. Contrat de sortie par choix :

```
justification = { resume, preuves: [ { type, texte, valeur } ], donnees_suffisantes, bibliotheque: { … } }
```

- **NO DATA → NO GO** : un marché sans preuve *spécifique à ce marché* est rejeté avant sélection
  (`JUSTIFICATION_INSUFFISANTE`, dans `archetype_model/main.py`). La preuve EV, valable pour tous les marchés,
  ne suffit jamais.
- Une donnée n'est publiée que si elle est **calculable exactement** sur les historiques fournis (minimum 5 matchs
  au total, 3 par lieu). Les seuils sont dans le module.
- Familles couvertes (quand les données les permettent) : 1X2 (domicile, nul, extérieur), double chance (1X, 12, X2),
  les deux équipes marquent (oui, non), plus/moins de buts (toutes les lignes), buts d'une équipe. **Non couverts** : handicap à 3 issues
  (aucune cote ne lui parvient) et les marchés hérités de l'ancien moteur.
- Les justifications du moteur sont calculées directement dans `branchement_moteur.py` ; aucun rattrapage séparé n'est exécuté.
- `moteur_justification.py` et `adapte_justification.py` sont l'ancien moteur de justification, relié à `run_pipeline.py`.

### 3.4 Tickets
Dossier `tickets/` : `builder.py` (combinaison avec contrôle de dépendance), `cycle.py` (cadence), `observation.py`
(tickets fictifs). Principe : **0 ticket est un résultat honnête** ; les critères ne sont jamais dégradés pour remplir
un quota.

---

## 4. Le site

Hébergé sur Netlify (`netlify.toml` : publie la racine du dépôt, en-têtes anti-cache). Aucun build, aucun framework.

| Page | Fichiers | Données lues |
|---|---|---|
| `index.html` — Accueil, ajout au panier | `index.js`, `style.css`, `theme.css`, `theme.js` | `matchs_du_jour_filtre.json`, `matchs_demain_filtre.json` |
| `archetype.html` — Pronostics | `archetype.js`, `archetype.css`, `traduction_marches.js`, `ui_mappings.js` | `precalcul_leger.json` |
| `panier.html` — Panier | `panier.js` + ceux d'Archetype | `precalcul_leger.json` + panier du navigateur |
| `systeme.html` — Bilan système | `systeme.js`, `style.css`, `theme.css` | `etat_systeme.json` |
| `admin.html` — Audit / calibration | `admin.js`, `style.css`, `theme.css` | `data/audit_status.json`, `data/audit_telemetry.json`, `config/journal_promotion.jsonl` |
| `archetype_shrink.html` et `pronostics_shrink.html` — Pronostics du second moteur | `archetype_shrink.js` + ceux d'Archetype (même gabarit, même carte) | `precalcul_shrink_leger.json` (bloc `shrink_v1`) |
| `journal.html` — Journal de rentabilité | `journal.js`, `journal.css` + `archetype.css` | `journal.json` |
| `presentation-site.html` | autonome | aucune (maquette temporaire) |

**Cartes de match (Archetype et Panier).** Une seule fonction, `construitCarte()` dans `archetype.js`, construit les
cartes des deux pages : le panier est donc identique à la page principale, avec en plus le bouton « Retirer ».
Chaque carte a trois onglets — **Favori du Modèle** (choix le plus probable), **Value Bet** (meilleur EV parmi les
restants), **Coup de Poker** (cote ≥ 2,91 et probabilité ≥ 20 %) — réattribués depuis P1/P2/P3 par
`remappeEnOngletsApp()` (mêmes règles que le moteur, vérifiées par un test de contrat). Le bloc lu est `signal[CLE_MOTEUR]`
(`CLE_MOTEUR = "moteur_v2_6_9"` dans `archetype.js`) : changer de moteur = changer cette constante. Le bouton « Détails de l'analyse » ouvre des tableaux (synthèse, preuves avec icônes,
forme de chaque équipe, H2H, métriques combinées) alimentés par `justification.bibliotheque`.

Règles d'affichage : jamais de tableau vide, jamais de « — » ni « N/A » (une valeur non calculable n'a pas de ligne),
badge EV distinct, message neutre unique si `donnees_suffisantes` est faux, **le site ne recalcule rien**.

Conventions :
- `archetype.css` : classes préfixées `ax-`, aucun `!important`, variables portées par `.ax-carte`, mode nuit par `body.theme-nuit`.
- `ui_mappings.js` : contrat visuel figé (type de preuve → icône, couleur, libellé français).
- Après toute modification de `archetype.js`, `archetype.css` ou `ui_mappings.js`, **changer le paramètre `?v=`** dans
  `archetype.html` et `panier.html` pour que les téléphones rechargent les fichiers.
- Mémoire du navigateur : `archetype_panier` (panier), `archetype_theme_nuit` (mode nuit).
- Accueil, Système et Admin utilisent encore l'ancienne charte (`style.css` + `theme.css`, avec de nombreux `!important`).

### 4.1 Le journal de rentabilité (`journal.html`, depuis le 24/09/2026)

**Aucun moteur de prédiction.** `journal_rentabilite.py` fait une comptabilité : chaque cote BetPawa relevée avant un
match terminé est réglée sur le score final, et on calcule ce qu'aurait rapporté une mise de 1 à chaque fois (ROI).
Sources : `data/echantillon_betpawa_501.json` (501 matchs figés, 09-20/09) + `historique_pronostics.json` (matchs à
`source_cotes = "manuel"`, c'est-à-dire cotés BetPawa). Seule la rubrique « Moteurs » lit les choix des deux moteurs
(`archive/`, `archive_shrink/`, `precalcul_*leger.json`), sans les recalculer.

Workflow **séparé** : `.github/workflows/journal.yml`, lancé à la fin de chaque pipeline (réussi ou non) et à 05:30 UTC
en secours ; lance `tests/test_journal_rentabilite.py` puis `journal_rentabilite.py`, et ne publie que `journal.json`.

La page a une barre de rubriques (un bouton chacune, une seule affichée ; l'adresse retient la rubrique : `journal.html#equipes`) :

| Rubrique | Contenu | Règle |
|---|---|---|
| Marchés rentables | Pour chaque championnat, chaque marché au ROI positif (≥ 10 matchs) : gagnés/joués, cote moyenne, ROI, niveau | ROI négatifs calculés mais **jamais affichés** (choix du propriétaire) |
| Équipes à suivre | Marché passant dans ≥ 70 % des matchs d'une équipe, sur ≥ 5 matchs ; prochain match et cote BetPawa | Marchés banals (≥ 70 % en général) exclus ; une équipe à moins de 5 matchs dans les données n'apparaît pas |
| Conseils | Marchés des matchs à venir | **Même championnat, même marché**, segment « Prouvé » ou « À surveiller », et cote du jour dans la fourchette des cotes mesurées. Aucune moyenne « tous championnats » |
| Moteurs | Choix P1/P2/P3 des deux moteurs situés dans une zone rentable ; championnats et familles où ils ont gagné | idem Conseils |
| Méthode | Règles et qualité des données | — |

Niveaux : **Prouvé** (`A_JOUER`) = IC 95 % entièrement positif, gagnant sur chaque moitié, ≥ 40 matchs ;
**À surveiller** (`A_SURVEILLER`) = gagnant au total et sur chaque moitié, ≥ 25 matchs ; **Non confirmé** = gagnant au total
seulement (des centaines de segments étant scrutés, une partie de ces gains vient de la chance).

---

## 5. Fichiers de données (versionnés, réécrits par le pipeline)

| Fichier | Contenu |
|---|---|
| `matchs_du_jour.json`, `matchs_demain.json`, `matchs_semaine.json` (+ `*_filtre.json`) | Programmes bruts et filtrés |
| `precalcul.json` (~9 Mo) | Sortie complète du pré-calcul (diagnostics, fenêtres, tous les candidats) |
| `precalcul_leger.json` | Version allégée lue par le site : choix retenus et leur justification |
| `cache_equipes.json`, `cache_h2h.json`, `cache_classement.json`, `cache_betpawa.json` | Mémoires du scraping |
| `historique_pronostics.json`, `archive/AAAA-MM.json` | Historique et archive des observations à régler |
| `bilan_archetype_model.json`, `etat_systeme.json`, `data/audit_*.json` | Bilans et audit |
| `config/*` | Paramètres calibrables, état et journaux de calibration |
| `export_moteur/` | Entrées exactes du moteur (un fichier par date, écrasés à chaque run) et `diagnostic_pont.json` (matchs rejetés, avec la raison) |
| `tickets_observes/`, `vrais_tickets/` | Tickets fictifs et réels, un fichier par mois |
| `data/football_data/` | Football-Data : snapshots immuables des saisons terminées, saison en cours normalisée (`CONTRAT.md`) |
| `data/correspondances/equipes.json` | Noms d'équipes Football-Data ↔ Matchendirect, reliés par preuves (A3) |
| `data/assemblage/equipes.json` | Matchs de chaque équipe à venir : Football-Data en base, jours manquants Matchendirect (provisoires) |
| `journal.json` | Sortie de `journal_rentabilite.py` (workflow `journal.yml`) : segments, conseils, équipes à suivre, résultats des moteurs |
| `data/echantillon_betpawa_501.json` | Base figée du journal : 501 matchs terminés (09-20/09/2026), cotes BetPawa d'avant-match + score |

---

## 6. Installer et lancer en local

Python 3.12. Dépendances réellement utilisées : `requests`, `beautifulsoup4`, `pandas`, `playwright`.

```bash
pip install requests beautifulsoup4 pandas playwright pytest
playwright install chromium

python scraper.py --max-matchs 100000        # listes J0 et J+1
python scraper_semaine.py --max-matchs 100000
python precalcul.py                          # PRECALCUL_LIMITE_BETPAWA=20 limite la résolution BetPawa

python3 -m http.server 8000                  # prévisualiser le site : http://localhost:8000/index.html
```

Ne pas ouvrir les pages par double-clic : le navigateur bloque alors le chargement des fichiers JSON.
`requirements.txt` n'est pas encore branché sur le workflow (qui a sa propre ligne `pip install`).

---

## 7. Tests et contrôles

```bash
python -m pytest tests -q
```

`tests/` couvre l'audit passif, la bibliothèque de justification et les marchés retenus de bout en bout.
`audit_permanent.py` est une suite d'audit plus large, lancée à la main.

Limites connues : le workflow ne lance **ni `pytest` ni contrôle de syntaxe JavaScript**, et aucun test automatique
de l'interface n'est versionné. Un JavaScript cassé n'est donc détecté qu'à l'ouverture de la page (cela s'est produit
le 19/09/2026 : la page Archetype restait vide).

---

## 8. Principes du projet

Décisions du propriétaire, documentées dans le code et dans `ROADMAP.md` (§4), toujours en vigueur :

- **NO DATA → NO GO** : pas de justification générique inventée pour combler un vide.
- **Mieux vaut aucun match qu'un mauvais match** (matching BetPawa).
- Ne jamais dégrader les critères des tickets pour atteindre un quota.
- Ne pas promouvoir un paramètre de calibration sur un échantillon insuffisant ; ne pas confondre validation
  logique et validation prédictive.
- Pas de repli sur un autre moteur : un moteur qui échoue produit un statut d'erreur visible, jamais une décision inventée.
- Le site est de la présentation : il ne choisit et ne calcule rien.
- Ne pas modifier `calculs.py`, `run_pipeline.py` ou `scraper_details.py` sans preuve et test ciblé.
- Ne pas considérer un run vert comme preuve suffisante : inspecter les fichiers produits.

---

## 9. Points d'attention (constatés le 21/09/2026)

- Le dépôt est **privé**, mais `netlify.toml` publie toute la racine : le code, les données et `admin.js` sont servis
  avec le site. Le mot de passe de la page Admin est écrit **en clair** dans `admin.js` (vérification côté navigateur
  uniquement) : ce n'est pas une protection.
- Les gros fichiers JSON sont recommités chaque nuit : le dépôt grossit vite (`.git` ≈ 71 Mo le 20/09).
- Publication du résultat : un `git pull --rebase` en conflit sur les fichiers de données peut faire perdre un run entier
  (run n°129, voir `ROADMAP.md` P0.1). Éviter de pousser des données pendant qu'un run tourne.
- **Le moteur v2.6.9 n'a aucune mesure de calibration** (Poisson indépendant, constantes non calibrées). Le rejeu du 20/09 donne 107 choix pour 71 matchs ; l'archive (`model_version = moteur_v2_6_9`) sert à mesurer, voir `ROADMAP.md` P2.6.
- L'archive grossit d'environ 0,9 Mo par jour (27 Mo par mois, un fichier par mois) ; le coût d'écriture reste faible.
- La télémétrie d'audit passif et la calibration ne tournent plus : `data/audit_*.json` et `config/` sont figés au 20/09.
- Les nouveaux textes de justification (nul, double chance 12, « les deux équipes marquent : non », lignes de buts,
  buts d'une équipe) et les champs `bibliotheque` complets n'apparaissent dans les données qu'après un run complet du pipeline.

---

### Ajouts du 24/09/2026

- **Convention des handicaps dans `historique_pronostics.json`** : la ligne affichée est celle de l'équipe **à domicile**.
  « Handicap -0.5 - Extérieur » = l'extérieur reçoit +0.5 (même cote que la double chance X2 dans 99 % des 733 matchs
  vérifiés). `journal_rentabilite.ligne_propre()` applique cette convention ; le moteur lit les cotes par `pont_moteur.py`,
  qui la gère déjà.
- **Cotes de handicap incohérentes** avec le 1X2 du même match (côtés inversés au relevé) : retirées par
  `journal_rentabilite.controle_coherence()` (42 au 24/09), jamais corrigées à la main.
- **Données par équipe encore courtes** : au 24/09, aucune équipe n'a plus de 5 matchs dans les données ; la rubrique
  « Équipes à suivre » se renforcera avec les nuits.
- **Saisons d'équipes parfois fausses** (`cache_equipes_saison.json`) : `scraper_details._extrait_historique_competition`
  prend le premier tableau de matchs qui suit un texte « ressemblant » au nom de la compétition, sans vérifier que ce
  tableau est celui de la compétition (ex. The New Saints : le match amical Glentoran 1-1 enregistré comme sa saison de
  Cymru Premier). **Contrôle** : `controle_saisons.py` (workflow `journal.yml`) compare chaque saison enregistrée aux
  scores connus par les pages de match et publie `controle_saisons.json`, affiché sur la page Système (23 % d'équipes
  incohérentes au 24/09). **Correction (24/09)**, vérifiée sur 8 vraies pages capturées
  par `.github/workflows/diagnostic_pages.yml` (se lance quand `diagnostic/pages_a_capturer.txt` change) : seuls les
  titres de compétition (h2/h3/h4 avec « : ») servent d'ancre, le meilleur titre est retenu, un titre ajoutant coupe /
  amicaux / femmes / jeunes absent de la cible est refusé, et le tableau lu doit précéder le titre suivant
  (`_section_competition`). Garde-fou dans `stats_saison_en_cours.py` : une saison qui contredit un score connu est
  refusée (`saison_incoherente_avec_resultats_connus`). Tests sur pages réelles : `tests/test_lecture_saison_pages_reelles.py`.
  `cache_equipes_saison.json` a été vidé le 24/09 pour forcer une relecture de toutes les équipes.
- **Page du second moteur** : `archetype_shrink.js` filtrait sur `moteur_utilise`, alors que le pipeline marque le second
  moteur dans `shrink_v1_utilise` ; la page était toujours vide (corrigé le 24/09).

## 10. Documents du projet

| Document | Contenu |
|---|---|
| `ROADMAP.md` | Chantiers en cours et priorités. Certains renvois « TRANSITION.md §N » y désignent l'ancien journal de sessions (voir ci-dessous) |
| `DIALOGUE_IA_MATRICE.md` | Cahier des charges de la recalibration du moteur de sélection (15–18/09/2026) |
| `requirements.txt` | Dépendances Python |
| Run limité | Actions → *Pipeline quotidien* → Run workflow → `jours` = 2 : aujourd'hui + demain seulement (saute la liste J+2/J+3, garde les correspondances BetPawa de J+2/J+3) ; 4 = fenêtre complète (défaut, planifié) |
| Autotests | `python moteur_v2_6_9.py --autotest` · `python pont_moteur.py --autotest` · `python -m pytest tests -q` |
| Journal | `python journal_rentabilite.py` (écrit `journal.json`) · Actions → *Journal de rentabilité* → Run workflow |

**Ancien journal de sessions.** `TRANSITION.md` (et sa copie `TRANSITION 4.md`) ont été supprimés le 21/09/2026 : 269 Ko
de récit chronologique, en-tête daté du 08/09 alors que le contenu allait jusqu'au 20/09, plus de 30 fichiers cités qui n'existent
plus. Ils restent lisibles dans l'historique Git :

```bash
git show c1ce4c9:TRANSITION.md
```

Plusieurs commentaires du code citent encore « TRANSITION.md §N » : ce sont des renvois historiques, sans effet.
