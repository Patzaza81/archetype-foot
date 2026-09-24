# A1 — Archive historique Football-Data : décision d'architecture

## Décision verrouillée

À la fin de chaque saison, Archetype Foot archive **tous les CSV historiques publiés par Football-Data.co.uk pour la saison terminée**, pour l'ensemble des divisions/championnats réellement découvrables depuis les index officiels.

Le système ne crée pas un fichier par équipe : Football-Data publie les historiques par compétition/division. Archiver tous les CSV de la saison couvre donc l'historique de toutes les équipes présentes dans ces compétitions.

## Structure

```
data/football_data/
  snapshots/
    2526/
      raw/
        E0.csv
        F1.csv
        ...
      manifest.json
      _SNAPSHOT_COMPLETE.json
    2627/
      ...
```

- `snapshots/<saison>/raw/` = copies brutes exactes des sources.
- `manifest.json` = provenance, URL, division, taille, SHA-256, couverture et état.
- `_SNAPSHOT_COMPLETE.json` = verrou logique : le snapshot est complet et ne doit plus être téléchargé ni réécrit.
- Une saison incomplète peut être reprise ; les fichiers déjà présents ne sont jamais écrasés.
- Une saison COMPLETE est consommée localement, sans dépendance réseau.

## Pourquoi

Cette architecture évite de faire dépendre l'historique d'un fichier source qui pourrait évoluer ou être remplacé. Chaque saison terminée devient une photographie autonome et reproductible.

La saison suivante reçoit son propre snapshot. Les deux saisons ne sont jamais fusionnées physiquement.

## Séparation stricte

### Collecte / archive
Autorisé :
- découverte des CSV ;
- téléchargement ;
- contrôle de présence ;
- SHA-256 ;
- taille ;
- provenance ;
- normalisation technique séparée si nécessaire.

Interdit :
- moyenne ;
- xG dérivé ;
- probabilité ;
- EV ;
- value ;
- signal ;
- décision de marché ;
- interprétation d'une cote comme ouverture/clôture.

### Moteur
Le moteur lit les données archivées et effectue ensuite ses propres calculs. Il ne télécharge pas l'historique Football-Data.

### Matchendirect / BetPawa
Aucune fusion dans le snapshot. Les correspondances inter-sources restent un chantier séparé.

## Workflow

`.github/workflows/football_data_snapshot.yml` construit le snapshot sur demande ou lors du contrôle annuel de juillet.

Le pipeline quotidien ne doit pas transformer l'archive historique en téléchargement quotidien. La collecte opérationnelle de la saison courante reste séparée.

## Règle d'intégrité

Si un CSV déjà archivé diffère du SHA-256 enregistré, le processus s'arrête avec une erreur de conflit : il ne remplace jamais silencieusement l'archive.

## Consigne pour Claude

Ne pas revenir à un modèle « télécharger la saison passée à chaque run ».

La référence historique est désormais :

`data/football_data/snapshots/<saison>/`

Une saison COMPLETE est immuable.

Toute évolution future doit conserver :
1. l'indépendance des saisons ;
2. la conservation du brut ;
3. la traçabilité SHA-256 ;
4. l'absence de calcul de marché dans la collecte ;
5. l'utilisation locale de l'historique par le moteur ;
6. la possibilité de reconstruire les données à partir du snapshot sans réseau.

## État de l'implémentation

- `archive_football_data.py` : collecteur de snapshot complet et immuable.
- `tests/test_archive_football_data.py` : tests de complétude, reprise et verrouillage.
- `.github/workflows/football_data_snapshot.yml` : workflow annuel / manuel.
- Le premier snapshot réel doit être exécuté dans GitHub Actions avant de considérer A1 comme validé en conditions réelles.


## Catalogue des compétitions et URLs directes

Chaque snapshot produit `catalogue.json`, construit à partir des fichiers réellement découverts dans les index officiels. Il contient le code compétition, la saison et l'URL directe officielle du CSV. Les codes actuellement connus sont enrichis avec pays et nom de compétition ; tout nouveau code est conservé avec des métadonnées descriptives nulles plutôt que deviné. Le catalogue est donc une provenance dynamique, pas une liste exhaustive codée en dur.

Le manifeste reprend également ces métadonnées lorsqu'elles sont identifiables. L'URL directe enregistrée est l'URL effectivement découverte et utilisée pour le téléchargement, jamais une URL reconstruite à partir d'une hypothèse.
