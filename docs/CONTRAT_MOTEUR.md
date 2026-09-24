# Contrat de transmission au moteur — version 1 (24/09/2026)

La collecte (chantier A) récupère, normalise, vérifie et **transmet** ; elle ne calcule rien. Le moteur d'analyse des
marchés (chantier B) lit les données d'équipes **uniquement** par `contrat_moteur.py` :

```python
import contrat_moteur as cm
doc = cm.charge_assemblage()                         # lève cm.ContratRompu si le fichier n'est pas conforme
eq = cm.equipe(doc, url_equipe, competition)         # entrée de l'équipe, ou None
```

Toute modification d'un champ : nouvelle `VERSION_CONTRAT`, mise à jour de ce document et de `tests/test_contrat_moteur.py`.

## Fichiers transmis

| Fichier | Produit par | Rôle |
|---|---|---|
| `data/assemblage/equipes.json` | `assemblage_equipes.py` | **Entrée principale** : matchs de la saison en cours de chaque équipe des matchs à venir |
| `data/correspondances/equipes.json` | `assemblage_equipes.py` | Noms Football-Data ↔ Matchendirect (pivot) |
| `data/football_data/snapshots/<saison>/` | `archive_football_data.py` | Saisons terminées, immuables (CSV bruts + manifeste SHA-256) |
| `data/football_data/normalized/<saison>/<CODE>.jsonl` | `collecte_football_data.py` | Saison en cours, une ligne par match |

Tous sont reconstruits chaque nuit par le workflow `journal.yml` (sauf les snapshots, écrits une seule fois).
Si `contrat_moteur.py --verifier` échoue, les nouvelles versions de l'assemblage et des correspondances ne sont pas
publiées : la version précédente, conforme, est conservée.

## `data/assemblage/equipes.json`

Racine : `version_contrat` (= 1), `genere_le`, `saison_football_data`, `regle`, `bilan`, `equipes` (liste).

Une équipe :

| Champ | Type | Sens |
|---|---|---|
| `cle_cache` | texte | « url de l'équipe Matchendirect \|\| compétition en minuscules » (clé unique) |
| `competition` | texte | compétition Matchendirect |
| `couverte_par_football_data` | booléen | championnat couvert **et** équipe reliée (A3) |
| `division_football_data`, `nom_football_data`, `nom_matchendirect` | texte | obligatoires si couverte |
| `raison` | texte | obligatoire si non couverte : « championnat non couvert… » ou « …équipe pas encore reliée (A3) » |
| `matchs_sans_date_ignores` | entier | matchs Matchendirect écartés faute de date vérifiable (équipes couvertes) |
| `matchs` | liste | triée par date |

Un match (vu du côté de l'équipe) :

| Champ | Type | Présent | Sens |
|---|---|---|---|
| `date` | texte AAAA-MM-JJ | toujours pour une équipe couverte | date du match |
| `domicile` | booléen | toujours | l'équipe jouait à domicile |
| `adversaire` | texte | si connu | nom dans la source du match |
| `buts_marques`, `buts_encaisses` | entier | toujours | score final |
| `source` | `football-data` ou `matchendirect` | toujours | |
| `provisoire` | booléen | toujours | `true` = jour manquant ajouté depuis Matchendirect, remplacé par Football-Data dès sa publication |
| `buts_marques_mi_temps`, `buts_encaisses_mi_temps` | entier ou null | Football-Data seulement | score à la mi-temps |
| `tirs`, `tirs_concedes`, `tirs_cadres`, `tirs_cadres_concedes` | entier ou null | Football-Data seulement | |
| `corners`, `corners_concedes` | entier ou null | Football-Data seulement | |
| `cartons_jaunes`, `cartons_rouges` | entier ou null | Football-Data seulement | |
| `xg`, `xg_concede` | nombre ou null | Football-Data seulement (divisions principales, depuis 2026-27) | |
| `saison` | texte | Football-Data seulement | code de saison (ex. `2627`) |
| `url_match` | texte ou null | Matchendirect seulement | lien de la page du match |

**Règles garanties par le contrat** (vérifiées à chaque run) : un match Football-Data n'est jamais provisoire ; un match
Matchendirect ne porte jamais de données Football-Data (mi-temps, tirs, corners, xG) ; un match provisoire n'existe que
pour une équipe couverte ; pour une équipe couverte, jamais deux matchs à ± 1 jour (pas de doublon) et matchs triés.

**Règle pour le moteur** : `null` ou absent = donnée non publiée. Le marché qui en a besoin est **écarté** ; la donnée
n'est jamais estimée ni remplacée (décision du 24/09/2026). Exemple : un match `matchendirect` n'a pas de corners, il
ne compte pas pour un marché de corners.

## `data/correspondances/equipes.json`

`divisions.<CODE>.competition_matchendirect` et `divisions.<CODE>.equipes.<nom Football-Data>` =
`{matchendirect, preuves, similarite_nom}` ; listes `ambigues` et `non_resolues`. Un nom Matchendirect n'est relié qu'à
une seule équipe par division (vérifié).
