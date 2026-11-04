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

## Classement descriptif et completude
- `classement_descriptif.py` produit `classement_descriptif.json/.md`: trois dimensions separees (couverture, fiabilite, volume) et aucun score global ni recommandation de marche.
- Completude: `COMPLETUDE_VERIFIEE` seulement si `verifications_completude.json` contient une verification externe concordante avec l'archive; sinon `COMPLETUDE_NON_VERIFIEE`; divergence = `COMPLETUDE_INCOHERENTE` (le workflow echoue).
- Completude de l'archive (dimension DISTINCTE, 04/11/2026, decision de Patrick; ne modifie ni le statut de completude ni `comparable_sans_reserve`): cle optionnelle `signalements_archive` d'une verification, jamais d'ajout ni de comptage de match absent. Absente = `ARCHIVE_NON_EXAMINEE` (rien n'est affirme). Signalements, par priorite: `MATCH_ARCHIVE_MANQUANT` (rencontre disputee documentee et absente), `PHASE_EXCLUE_NON_DETAILLEE` (phase exclue sans rencontres individualisees: `niveau_preuve` existence_seulement), `MATCH_ATTRIBUE_NON_JOUE` (match attribue sans rencontre disputee). Liste vide explicite + `perimetre_examen` {saison_reguliere, phases_finales, matchs_additionnels, limites}: `ARCHIVE_COMPLETE_PERIMETRE_ETENDU` seulement si saison_reguliere=paires_completes_verifiees, phases_finales=individuelle ou aucune_phase_documentee, matchs_additionnels=examines; sinon `ARCHIVE_COMPLETE_PERIMETRE_PARTIEL`. Un total identique ne prouve pas l'identite des matchs. Sortie `comparable_archive_sans_reserve` = 5 saisons verifiees ET perimetre etendu.
- Une structure aller-retour complete dans l'archive est coherente mais ne prouve pas qu'une equipe n'a pas ete oubliee.
- Editions et identites d'equipes ne sont jamais fusionnees.
- Signalement `SCORE_ATTRIBUE_DIVERGENT` (04/11/2026): rencontre PRESENTE dans l'archive avec le score joue alors que le resultat officiel est un score attribue different (JPN 2021 Urawa-Shonan, RUS 2022-23 Pari NN-Torpedo). Ce n'est pas une rencontre absente ni un match attribue non joue; rien n'est modifie. Priorite de statut de saison: MATCH_ARCHIVE_MANQUANT > PHASE_EXCLUE_NON_DETAILLEE > SCORE_ATTRIBUE_DIVERGENT > MATCH_ATTRIBUE_NON_JOUE. Bilan consolide: `docs/BILAN_ARCHIVE_FD.md`.
