# Évaluation du moteur `moteur_v2_6_9` — protocole figé le 21/09/2026

Ce protocole est écrit **avant** de connaître un seul résultat. Il ne doit pas être modifié après.

## Ce qui est figé

`snapshot_moteur_v2_6_9_2026-09-20.json` (+ `.sha256`) : **80 matchs du 20/09** analysés par le moteur, avec, pour chacun :
- les entrées exactes du moteur (moyennes de buts, effectifs, cotes) ;
- l'inventaire complet des marchés (probabilité du modèle, probabilité juste du marché, cote, EV, statut, catégorie) ;
- les choix publiés sur le site (P1/P2/P3) avec leurs justifications.

Le fichier est reproductible : rejouer `moteur_v2_6_9.py` sur les entrées figées redonne exactement l'inventaire figé (testé sur les 80 matchs). Son empreinte SHA-256 est vérifiée à chaque évaluation.

**Limites de ce jeu de données, à garder en tête :**
- c'est un **rejeu** (le 21/09) sur les entrées du run du 20/09 00:18 UTC, pas un run en direct ;
- les statistiques d'équipe viennent des fenêtres de l'ancien chargeur (saison en cours, ordre chronologique, filtrées par lieu) : une approximation de la source réelle du moteur ;
- les cotes sont celles de BetPawa à 00:18 UTC, pas à l'heure du coup d'envoi ;
- l'échantillon du premier jeu est petit (80 matchs, environ 70 choix publiés) ; le jeu principal en compte 503 ; Les marchés d'un même match sont corrélés : les intervalles sont calculés **par match**.

## Deux jeux figés

| Fichier | Contenu |
|---|---|
| `snapshot_historique_moteur_v2_6_9.json` | **503 matchs déjà joués (9 au 20/09)**, chacun analysé avec les cotes et historiques du **dernier run publié avant son coup d'envoi**, règle des 2 matchs par lieu comprise. Jeu principal. |
| `snapshot_moteur_v2_6_9_2026-09-20.json` | 80 matchs du 20/09 (premier jeu, contenu dans le principal pour l'essentiel) |

Les scores du jeu principal sont récupérés **automatiquement** par le pipeline chaque nuit (`evaluation_scores.py` : une requête par date sur la page des résultats, rapprochement des deux équipes avec la fonction du pipeline, score retenu seulement si le match est terminé) et écrits dans `scores_historique_moteur_v2_6_9.json`. Évaluation :

```bash
python evaluation_moteur.py evaluation/snapshot_historique_moteur_v2_6_9.json evaluation/scores_historique_moteur_v2_6_9.json
```

## Fournir les résultats à la main (autre option)

Un résultat par ligne, dans l'ordre « équipe à domicile, équipe à l'extérieur » (les équipes inversées sont détectées, le score est alors inversé avec un avertissement) :

```
Cibao - O&M 2-1
Belgrano 0-0 E. Rio Cuarto
2026-09-20 Paranaense - Bahia 3-2
```

`matchs_a_renseigner_2026-09-20.txt` liste les 80 matchs avec les noms exacts. Commande :

```bash
python evaluation_moteur.py evaluation/snapshot_moteur_v2_6_9_2026-09-20.json resultats.txt [--json rapport.json]
```

Un résultat n'est associé à un match que si **les deux équipes** correspondent ; en cas de doute la ligne est rejetée et listée avec le meilleur candidat. Jamais d'association devinée.

## Ce que mesure le rapport

| Groupe | Contenu | Rôle |
|---|---|---|
| `choix_publies` | les choix P1/P2/P3 du site | ce que voit l'utilisateur |
| `value_bets_hors_D` | tout ce que le moteur signale et ne rejette pas (A, B, C) | test du filtre de sélection |
| `value_bets_D` | les value bets que le moteur écarte (EV > 30 % ou deux artefacts) | l'écart de la catégorie D est-il justifié ? |
| `tous_les_marches` | les ~25 marchés cotés de chaque match | **calibration** : le plus d'observations |

Pour chaque groupe : taux de réussite, probabilité moyenne annoncée, probabilité juste du marché (cotes sans marge), Brier et log-loss du modèle et du marché, ROI à mise plate, intervalles de confiance à 95 % (bootstrap par match, 2 000 tirages, graine fixe).

## Règles de lecture, fixées à l'avance

1. **La calibration est le critère principal**, sur `tous_les_marches` : écart = taux de réussite − probabilité annoncée. Le modèle n'est déclaré **mal calibré** que si l'intervalle à 95 % de cet écart **exclut 0**. Sinon : « pas de preuve d'un défaut », et non « bien calibré ».
2. **Modèle contre marché** : différence de Brier (modèle − marché) sur les mêmes lignes. Négative avec un intervalle qui exclut 0 : le modèle fait mieux que les cotes. Positive avec un intervalle qui exclut 0 : les cotes font mieux que le modèle. Sinon : indécidable.
3. **ROI des choix publiés : aucune conclusion sous 150 choix** (jalon de `ROADMAP.md` P2.6). Le rapport le rappelle. Il reste descriptif, avec son intervalle.
4. **Value bets de catégorie D** : informatives seulement.
5. **Une différence entre familles de marchés** (buts, double chance, etc.) est une piste, jamais une conclusion, à ce volume.
6. **Interdit après lecture des résultats** : modifier une constante du moteur ou un seuil de la bibliothèque pour « améliorer » ce jeu. Tout changement exige un **nouveau** snapshot et un **nouvel** échantillon, sinon la mesure ne vaut plus rien.

## Ce que ce test ne peut pas dire

Avec 80 matchs, il détecte un défaut de calibration **important** et laisse passer un défaut modéré. Un résultat « pas de preuve d'un défaut » n'est pas une validation : la validation demande 150 à 200 choix propres, mesurés sur de vrais runs (`archive/`, `model_version = moteur_v2_6_9`).

## Erratum du 21/09/2026 (écrit APRÈS lecture des premiers résultats, à titre de transparence)

La règle de lecture n°1 (« calibration globale sur `tous_les_marches` ») est **défectueuse par construction** : les marchés opposés d'un même match (plus/moins de buts, oui/non) s'annulent exactement dans la moyenne (si l'un gagne, l'autre perd, et leurs probabilités valent 1 ensemble). L'écart global vaut donc environ 0 quel que soit le modèle, avec un intervalle artificiellement étroit. **Cette règle n'a aucune valeur de preuve et n'est plus utilisée.** Restent valides, et sont les seuls utilisés pour conclure : la fiabilité **par tranche de probabilité**, le **Brier modèle contre marché** (règle n°2), l'écart de calibration des **choix publiés** et des **value bets** (dont les marchés ne sont pas complémentaires), et le ROI (règle n°3). Les règles 2 à 6 sont inchangées, en particulier l'interdiction de régler le moteur sur ce jeu.

Premier rapport : `rapport_historique_2026-09-21.txt` (353 matchs avec score sur 503, scores issus de l'archive et de `historique_pronostics.json`, non recoupables entre eux : aucun match en commun).

## Banc de test historique pour tout nouveau moteur (`banc_historique.py`, 27/09/2026)

Porte obligatoire avant tout branchement d'un moteur au pipeline (V3 comprise). Un moteur = une fonction
`modele(entree) -> {marche: probabilite}` ; une règle de décision facultative = `selection(entree, probas) -> [marches]`.

```bash
python banc_historique.py                                         # modèles de référence (marché, V2, moyenne, lissé)
python banc_historique.py --modele mon_module:ma_fonction         # juger un moteur sur le jeu figé
python banc_historique.py --modele m:f --selection m:g --source tous --json rapport.json
```

- **Sources** : `snapshot` (ce jeu figé, empreinte vérifiée, refus si elle diffère) et `archive` (`data/archive_test/`,
  matchs testables avec score : listes complètes des matchs + Football-Data). Aucune donnée postérieure au match.
- **Mesures** : Brier et log-loss du modèle et du marché sans marge, écart avec intervalle à 95 % (bootstrap par match),
  par famille, par marché, par taille d'échantillon (N 0-2, 3-4, 5+), par tranche de cote, par source ; calibration par
  tranche ; ROI des sélections en mesure secondaire. Handicaps exclus (étiquettes BetPawa incohérentes).
- **Verdicts** : « ÉCHANTILLON INSUFFISANT » sous 100 matchs ou 200 observations (aucune conclusion), « AVANTAGE
  MESURABLE » (écart de log-loss entièrement sous 0), « MOINS BON QUE LE MARCHÉ » (entièrement au-dessus), sinon « AUCUN
  AVANTAGE MESURABLE » : le moteur doit alors conclure « pas d'avantage mesurable -> pas de pari ».
- Les marchés complémentaires d'un même match (plus/moins, oui/non) portent la même information : c'est pourquoi
  l'intervalle est calculé par match, et pourquoi la calibration par tranche est symétrique (voir l'erratum ci-dessus).
- **Seuils fixés dans le code, jamais ajustés après lecture d'un résultat.** Régler un moteur jusqu'à ce qu'il passe ce
  banc invaliderait la mesure (règle n°6).

Mesure de référence du 27/09/2026 (501 matchs, verrouillée par `tests/test_banc_historique.py`) : V2 (λ produit) est
« MOINS BON QUE LE MARCHÉ » (écart de log-loss +0,086, IC [+0,059 ; +0,114]) ; ses 548 sélections réussissent 63,3 %
pour 81,9 % annoncés et 62,8 % prévus par le marché, ROI −6,2 %. Aucun des modèles de référence ne bat le marché.
