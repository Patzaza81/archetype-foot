# Inventaire Football-Data

Etape exclusivement d'inventaire : aucun modele predictif, aucune selection de marche, aucun reglage.

## Lancer
- Automatique : workflow `inventaire_football_data` (push sur la branche `inventaire-fd` ou lancement manuel).
- Local : `python inventaire_football_data.py --racine .` puis `python -m unittest discover -s tests`.

## Entrees / sorties
- Lecture seule : `data/football_data/snapshots/<saison>/raw/*.csv` et `.../nouvelles_ligues/raw/*.csv`.
- Regles : `config/inventaire_regles.json` (versionnees, fixees avant observation des resultats).
- Sorties dans `data/inventaire/` : `manifest_global.json`, `profils_capacite.json`, `anomalies.json`, `rapport_inventaire.md`, `dernier_run.json`.

## Principes
- Lignes mesurees != lignes avec score. Une ligne sans score n'est jamais un match exploitable.
- Colonne absente != colonne presente mais vide != partielle != complete (sur les matchs joues).
- Editions d'un meme fichier (ex. ARG) traitees separement, jamais fusionnees.
- Annee civile vs saison a cheval : lues dans le manifest du snapshot (`season_format`), controle des dates.
- Changements de nom : seulement des candidats, jamais de fusion.
- Doublons : ligne exacte, cle date+equipes, memes equipes+score+cotes a des dates differentes, equipe jouant 2 fois le meme jour.

## Statuts (voir `statuts` dans la config)
- CAPACITE_CONFIRMEE : 5 saisons avec matchs joues, colonnes requises a 100 % sur les matchs joues partout, controles de coherence evaluables et sans violation.
- CAPACITE_INEXPLOITABLE : colonne requise jamais renseignee.
- CAPACITE_LIMITEE : tout le reste (raisons dans `profils_capacite.json`).

## Garde-fous
- Empreinte des archives avant/apres execution ; toute difference = echec.
- Archive absente, hash/lignes differents du manifest, snapshot incomplet : aucun profil publie.
- Empreintes du script et de la config enregistrees dans chaque sortie.

## Complements manuels
`data/inventaire/complements_manuels.json` : entrees `{competition, saison, colonnes, source, date_ajout}`. Declarees dans le profil, sans effet sur le statut automatique.

## Regles 1.0.1 et recomptage independant
- Cotes decimales (1X2, +/-2.5) valides si > 1; cotes de handicap asiatique valides si > 0 (peuvent etre < 1). `0`, `#`, `x`, `1xBet` = codes de remplissage, jamais des cotes.
- Trois categories distinctes: valeurs manquantes (cases vides), codes de remplissage (non numerique ou 0 dans une colonne numerique), erreurs de donnees (incoherences, cotes hors domaine, dates hors saison).
- `recomptage_independant.py` recompte chaque colonne depuis les CSV sans importer l'inventaire et liste les ecarts (`recomptage_independant.json`). Le workflow echoue s'il y a un ecart.
- `comparaison_v1.0.0_vs_recomptage.md` documente les ecarts de la premiere version.
- Limite: le recomptage est un code distinct mais ecrit avec la meme definition de validite; il valide l'arithmetique, pas la definition.
