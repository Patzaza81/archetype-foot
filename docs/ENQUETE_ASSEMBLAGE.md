# Enquête sur l'assemblage `data/assemblage/equipes.json` (01/11/2026)

Branche `enquete-assemblage` (depuis `main` 6068a9d). Aucun moteur, aucune route, aucun contrat de données, ni `calculs.py` / `run_pipeline.py` / `scraper_details.py` modifiés ;
aucune donnée historique supprimée ni restaurée ; aucune fusion. Le chargeur de Gamma (`moteur_dc/donnees.py`) n'est PAS modifié : le correctif est proposé (diff) et prouvé par les tests.

## 1. Cause racine (démontrée)
Le commit `2c80acc` (31/10, 19 h 58 UTC) n'est pas fautif en lui-même : `assemblage_equipes.py` est déterministe et ne perd rien (une entrée du cache = une équipe assemblée, test de reproductibilité).
Trois causes s'empilent :

| # | Couche | Cause | Preuve |
|---|---|---|---|
| 1 | **Source : le cache** | `cache_equipes_saison.json` n'est pas une base de championnats. Il ne contient que les équipes des matchs AVEC cotes BetPawa de la fenêtre J0 à J+3 (`precalcul.charge_stats_saison`), pour 30 h (96 h sans historique), puis `precalcul.py:1153` les purge (`cache_equipes.purge_entrees_expirees`). Une équipe sans match coté dans la fenêtre sort du cache, donc de l'assemblage. | Taille du cache : 427 à 1 359 entrées d'un run à l'autre ; Série B : 0 équipe le 19/10, 18 le 22/10, 12 le 31/10. Le 31/10 19 h 49 (`f9f505f`) : 394 entrées disparues (373 vieilles de 30 à 96 h, 21 de plus de 96 h), 143 apparues. |
| 2 | **Assemblage** | L'assemblage reflète ce cache sans signaler qu'un championnat est incomplet (Cremonese, Mantova, Benevento, Cesena, Sudtirol hors cache : 14 clubs sur 20). Aucun contrôle d'intégrité ni de couverture avant publication (`journal.yml` : étape `continue-on-error` ; `contrat_moteur.py --verifier` ne contrôle que les types, les dates et l'ordre, et déclare l'assemblage actuel CONFORME). | `controle_assemblage.py` (nouveau) trouve 79 auto-rencontres, 7 championnats cotés sans aucun match. |
| 3 | **Consommateur : chargeur de Gamma** `moteur_dc/donnees.py`, `Ligues`, ligne 116 | Pour un adversaire absent du cache (alias « ?Cremonese »), le chargeur le rattache à une équipe qui a, le même jour, un score inverse, **même quand l'autre côté est lui aussi inconnu** (`or not res2`). Un 0-0 est son propre inverse, donc n'importe quelle équipe ayant joué un nul ce jour-là convient ; un seul rattachement faux est ensuite appliqué à TOUS les matchs de l'alias. | « Cremonese » rattaché à Virtus, « Mantova » à Juve-Stabia : 12 matchs mal attribués, Virtus contre Virtus (19/09), Juve-Stabia à 15 matchs au lieu de 9, Virtus à 13 au lieu de 9. |

Ce n'est pas propre à la Série B : auto-rencontres vues par le moteur 66 (`1dc1035`) puis 79 (`6068a9d`), alors que la source n'en contient que 2 (Cerro/Cerro Largo, America Cali). Les 77 autres sont fabriquées par le chargeur.

## 2. Matchs de Série B disparus et apparus (31/10 10 h 57 → 01/11 01 h 28)
Référence `1dc1035` (gel d'Arezzo – Ascoli) : 90 matchs. `6068a9d` : 81. Détail complet avec scores dans `docs/enquete_assemblage_matchs.json`.
- **22 disparus** : 12 re-attribués à tort (6 de Mantova devenus Juve-Stabia, 6 de Cremonese devenus Virtus) et 10 réellement perdus (les deux clubs absents ou non reliés).
- **13 apparus** : les 12 re-attributions + 1 vrai nouveau résultat (Catanzaro – Padova 1-1, 31/10).
- Les 12 re-attribués : Carrarese–Mantova 1-2 (22/08), Mantova–Empoli 3-1 (30/08), Mantova–Sampdoria 2-0 (13/09), Mantova–Pise 2-2 (20/09), Catanzaro–Mantova 1-3 (11/10), Mantova–Palerme 0-2 (17/10) ;
  Empoli–Cremonese 1-0 (22/08), Cremonese–Padova 3-1 (06/09), Cremonese–Virtus 0-0 (19/09, devenu Virtus–Virtus), Arezzo–Cremonese 0-0 (10/10), Pise–Cremonese 3-1 (17/10), Cremonese–Juve-Stabia 0-1 (24/10).
- Les 10 perdus : Benevento–Modena 1-2, Cremonese–Modena 0-3, Benevento–Sudtirol 1-1, Cesena–Mantova 1-1, Cesena–Cremonese 2-2, Sudtirol–Modena 1-1, Benevento–Cesena 2-0, Modena–Cesena 3-0, Virtus–Mantova 0-1, Mantova–Cremonese 0-2.
- Arezzo – Ascoli : le gel de 90 matchs était cohérent ; le rejeu à 81 matchs ne l'est pas. Les buts attendus changent peu (0,97 → 0,99) mais les forces de Juve-Stabia et de Virtus sont polluées par les matchs de Mantova et de Cremonese.

## 3. Championnats affectés (`docs/enquete_assemblage_matchs.json`, clé `championnats`)
- 76 championnats perdent des équipes dans l'assemblage brut, 35 en gagnent. Total de matchs vus par le moteur : 9 275 → 8 424.
- **11 passent à 0 match** : Costa Rica (1ère division ouverture), France Ligue 3, Hong Kong, Irlande, Kazakhstan, Myanmar, Ouganda, Ouzbékistan, Suisse Challenge League, Viêt-nam, Zimbabwe. Le dernier match connu de chacun date du 17 au 27/10 (colonne `dernier_match_avant`) ; `matchs_a_venir_fenetre` compte leurs matchs à venir, cotés ou non (0 pour la France Ligue 3, l'Irlande, le Kazakhstan, Hong Kong). Ils sortent du cache faute de match coté dans la fenêtre ; je n'ai pas vérifié si certaines saisons sont terminées.
- Championnats cotés dans la fenêtre sans aucun match dans l'assemblage actuel (Gamma ne peut pas les pronostiquer) : Bélarus Première Ligue, Costa Rica, Estonie Meistriliiga, Mali, Norvège OBOS-ligaen, Suède Damallsvenskan, Suède Superettan.

## 4. Correctif proposé (non appliqué en production) et preuves
**A. Chargeur** (`docs/enquete_assemblage_chargeur.diff`, une condition) : ne rattacher un alias que si l'autre équipe NOMME explicitement la nôtre (`o2 == t`), jamais sur « adversaire aussi inconnu ».

| Mesure | Chargeur actuel | Chargeur strict |
|---|---|---|
| Auto-rencontres, assemblage `1dc1035` | 66 | 5 (erreurs de la source) |
| Auto-rencontres, assemblage `6068a9d` | 79 | 2 (erreurs de la source) |
| Série B (`6068a9d`) : identités / matchs / auto | 18 / 81 / 1 | **20 / 82 / 0** |
| Juve-Stabia / Virtus (matchs, vrai : 9 et 9) | 15 / 13 | **9 / 9** |
| Mantova / Cremonese (vrai : 9 et 9) | 0 / 0 | 7 / 6 |
| Écart à la référence `1dc1035` | 22 disparus, 13 apparus | 9 disparus (clubs hors cache), 1 apparu (vrai résultat) |
| Matchs, tous championnats (`6068a9d`) | 8 424 | 8 464 (aucun championnat n'en perd) |

Limite : le rattachement strict peut laisser un club en deux identités quand les deux côtés écrivent des alias différents (identités « ? » plus nombreuses) : une perte de données, jamais une fausse donnée. Le choix est celui de l'intégrité.

**B. Blocage du pipeline** (`controle_assemblage.py --verifier`, code de sortie 1) : auto-rencontre brute ou vue par le moteur, doublon, scores croisés incohérents, championnat coté sans aucun match.
À brancher dans `journal.yml` après `python assemblage_equipes.py` et dans `pipeline.yml` avant l'étape « Moteur DC » (sans `continue-on-error`) ; sur l'assemblage actuel il échoue (79 auto-rencontres, 7 championnats). Non branché ici : ce serait une modification de production.
Avec le chargeur actuel, le contrôle bloquerait aussi les 77 auto-rencontres fabriquées : le blocage n'a de sens qu'avec le correctif A, ou en excluant le seuil « vue moteur » tant que A n'est pas appliqué.

**C. Source (à décider)** : l'instabilité du cache (cause 1) n'est corrigée par rien ici. Options : (i) un historique de championnat persistant alimenté par Football-Data / Matchendirect, indépendant de la fenêtre cotée ; (ii) ne pas purger les équipes d'un championnat suivi ; (iii) exiger de Gamma un minimum de clubs par championnat. Aucune n'est implémentée.

## 5. Tests (`tests/test_controle_assemblage.py`, 10 tests)
Auto-rencontre brute, doublons, scores croisés (3 cas qui passent, 3 qui échouent chacun) ; volumes avant/après et championnats passés à zéro ; championnat attendu sans match ; blocage par `--verifier` ;
Série B réelle (fixture `tests/fixtures/assemblage_serie_b_2026-11-01.json`) : chargeur actuel = 18 clubs et Virtus–Virtus (défaut documenté), chargeur strict = 20 clubs, 0 auto-rencontre, 0 doublon, identités du cache conservées ;
non-régression sur tous les championnats de l'assemblage commité (aucun match perdu, aucune auto-rencontre en plus, identités conservées) ; reproductibilité de `assemble` et de `construit_correspondances`.

## 6. Reproduire
`python controle_assemblage.py --attendus --avant <ancien equipes.json>` ; `python -m pytest tests/test_controle_assemblage.py`.
