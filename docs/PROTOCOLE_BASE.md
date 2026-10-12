# Protocole BASE / SUPER BASE — version 1

- **Rédigé le** : 12/10/2026, 23 h 45 UTC (13/10/2026, 0 h 45 à Douala). La date qui fait foi est celle du commit Git de ce fichier.
- **Statut** : PROJET, à auditer. Aucun code n'est écrit avant validation de ce document.
- **Périmètre** : couche d'analyse en lecture seule. Elle ne modifie ni V2.6.10, ni V3, ni le Journal, ni les indices existants, ni `main`.

## 1. Principe

Les moteurs produisent les pronostics. La couche BASE lit l'historique déjà réglé et mesure si une configuration de paris (marché + tranche de cote + au plus un filtre) a été rentable.

Elle affiche toujours séparément :
- le **taux de réussite** ;
- la **rentabilité réelle** (ROI calculé avec la cote de chaque pari) ;
- le **seuil de rentabilité** (moyenne de 1 ÷ cote). C'est un repère, pas une preuve d'avantage ;
- la **référence** : tous les matchs du même marché, de la même tranche et de la même période.

Quand les données sont insuffisantes, le statut est **NON ÉVALUÉ**. Aucune tranche de cote n'est ajustée après coup.

## 2. Hypothèse déclarée

**H1 — « Moins de 3,5 buts », cote BetPawa entre 1,27 et 1,39 inclus.**

- H1 est une hypothèse à tester, pas un résultat. Rien dans les données actuelles ne la montre rentable (voir § 9).
- **Début du test : premier match dont le coup d'envoi est postérieur au commit de ce fichier**, soit à partir du 13/10/2026, 0 h 00 UTC.
- Les matchs du 12/10 sont exclus : ils étaient déjà joués quand ce protocole a été écrit, donc leurs résultats pouvaient être connus.

## 3. Tranches de cote (fixées avant le test, jamais modifiées)

Les cotes ont deux décimales. Bornes incluses.

| Tranche | Bornes | Rôle |
|---|---|---|
| T-1 | 1,20 – 1,26 | voisine, pour comparaison |
| **H1-a** | **1,27 – 1,33** | moitié basse de H1, information seulement |
| **H1-b** | **1,34 – 1,39** | moitié haute de H1, information seulement |
| T+1 | 1,40 – 1,46 | voisine, pour comparaison |

La décision porte sur **H1 entière (1,27 – 1,39)**. H1-a, H1-b, T-1 et T+1 sont affichées pour détecter un effet de bord. Elles ne reçoivent jamais de statut.

## 4. Données

### 4.1 Source unique : l'archive de test

Fichiers `data/archive_test/AAAA-MM-JJ.json.gz`, déjà produits chaque nuit par le pipeline existant. Champs utilisés :
- `cotes_betpawa.over_under_3.5.moins` : cote du pari ;
- `cotes_betpawa.over_under_3.5.plus` : cote opposée (pour mesurer la marge) ;
- `run.pris_le` : heure du relevé ;
- `coup_d_envoi_utc` ;
- `score.buts_dom`, `score.buts_ext` ;
- `equipe_dom.matchs`, `equipe_ext.matchs` : historiques figés avant le match.

**Pourquoi l'archive de test et non `historique_pronostics.json`** : elle garde les deux côtés de la cote, l'heure du relevé et les historiques d'équipe figés au coup d'envoi.

### 4.2 Gel avant le match (vérifié le 12/10 sur 1 284 matchs archivés)

| Constat | Nombre |
|---|---|
| Relevé pris avant le coup d'envoi | 1 186 |
| Relevé pris **après** le coup d'envoi | **27** |
| Heure du relevé ou du coup d'envoi absente | 71 |

Délai entre relevé et coup d'envoi : médiane 8,6 h, maximum 78 h.

**Conséquence** : la cote utilisée n'est pas la cote de clôture. C'est la cote au moment du dernier relevé avant le match.

**Règles d'exclusion** (appliquées avant tout calcul, chaque exclusion comptée et affichée) :
1. `run.pris_le` ou `coup_d_envoi_utc` absent → exclu (motif `HORODATAGE_ABSENT`).
2. `run.pris_le` ≥ `coup_d_envoi_utc` → exclu (motif `RELEVE_APRES_COUP_D_ENVOI`).
3. Cote « moins de 3,5 » absente → hors univers.
4. Match sans score 7 jours après son coup d'envoi → `NON_REGLE`, compté à part, jamais supprimé ni compté perdu.
5. Match reporté ou abandonné → exclu (motif `ANNULE`).

### 4.3 Conservation des paris perdants

Tout match admis entre dans les calculs, gagné ou perdu. Aucune ligne n'est retirée après le résultat. Un match apparaît **une seule fois** par configuration, même si plusieurs relevés existent : on garde le dernier relevé admis.

### 4.4 Intégrité de l'archive

À chaque point de contrôle (§ 7), l'empreinte SHA-256 de chaque fichier journalier de l'archive est enregistrée. Si une empreinte enregistrée change plus tard, le point de contrôle est déclaré `ARCHIVE_MODIFIEE` et n'est plus valable.

## 5. Configurations BASE déclarées (liste fermée)

| Code | Définition | Source du filtre |
|---|---|---|
| **B0** | H1, tous les matchs admis | aucune : c'est la référence |
| **B1** | B0 ∩ V3 a évalué « moins de 3,5 » sur ce match avec une probabilité ≥ 1 ÷ cote | `data/v3/journal/*.json`, calcul antérieur au coup d'envoi |
| **B2** | B0 ∩ pari « Match à moins de 3,5 buts » du Journal vu par le générateur avant le coup d'envoi | `data/selection_generateur_historique.json` |
| **B3** | B0 ∩ choix de production V2.6.10 « over_under_total_3.5_under » | `moteur_en_production` de l'archive de test |
| **B4** | B0 ∩ les deux équipes ont au moins 3 matchs au même lieu | historiques figés de l'archive de test |

**Remarques** :
- B4 vient d'une observation faite après coup dans l'audit (moins de 3 matchs au lieu : 64,6 % de réussite sur 65 matchs). C'est pour cela qu'elle est déclarée ici et testée seulement sur l'avenir.
- Les championnats pris un par un ne sont pas des configurations : trop de candidats (93 ligues dans H1), trop peu de matchs chacun. Ils sont affichés à titre descriptif, sans statut.
- Ajouter une configuration = nouvelle version du protocole, avec sa propre date de début. Une configuration ajoutée n'hérite d'aucun match antérieur à sa déclaration.

**Contrôles de rapprochement** :
- B1 : relier par `match_id`.
- B2 : les paris du Journal n'ont pas de `match_id`. Rapprochement par date + noms normalisés, comme dans `suivi_selection_generateur.py`. Avant usage, ce rapprochement est testé sur au moins 3 cas qui doivent correspondre et 3 cas qui ne doivent pas correspondre. Un pari non rapproché est compté `NON_RAPPROCHE`.
- B1 et B2 : tout calcul horodaté après le coup d'envoi est exclu. Constat du 12/10 : 20 fiches V3 sur 961 et 5 paris du générateur sont dans ce cas.

## 6. Mesures

Pour chaque configuration et chaque tranche :

| Mesure | Définition |
|---|---|
| Matchs | nombre de matchs distincts admis |
| Réussite | gagnés ÷ matchs, avec intervalle de Wilson |
| Seuil | moyenne de 1 ÷ cote des paris |
| ROI | (Σ gains − Σ mises) ÷ Σ mises, mise fixe de 1, **cote réelle de chaque pari** |
| Intervalle du ROI | bootstrap par jour de match (10 000 tirages), parce que les matchs d'un même jour partagent les mêmes conditions |
| Écart à la référence | ROI(Bx) − ROI(B0) sur la même période, intervalle par bootstrap par jour |
| Marge du marché | moyenne de (1 ÷ cote moins + 1 ÷ cote plus − 1), pour information |

**Ce qui n'est jamais fait** : retirer la marge pour fabriquer une « vraie probabilité ». Le constat du 12/10 montre que la marge pèse surtout sur « plus de 3,5 ». Une répartition égale donnerait 69,8 % là où la réussite réelle est de 74,7 %.

## 7. Règles de décision

### 7.1 Statuts

| Statut | Condition |
|---|---|
| **NON ÉVALUÉ** | moins de 150 matchs admis, ou moins de 21 jours de matchs |
| **EN COURS** | assez de matchs pour afficher, pas encore de point de contrôle atteint |
| **NEUTRE** | point de contrôle atteint, aucune condition ci-dessous remplie |
| **DÉFAVORABLE** | borne haute du ROI < 0 au point de contrôle |
| **PROMETTEUR** | ROI > 0 et, pour B1 à B4, écart à la référence > 0, mais bornes basses ≤ 0 |
| **VALIDÉ** | au point de contrôle : borne basse du ROI > 0 **et**, pour B1 à B4, borne basse de l'écart à la référence > 0 |

Un statut VALIDÉ n'est pas une garantie. Il redevient NEUTRE si le point de contrôle suivant ne le confirme pas.

### 7.2 Points de contrôle (fixés à l'avance)

- **C1** : quand B0 atteint 300 matchs admis.
- **C2** : quand B0 atteint 600 matchs admis.
- Ordre de grandeur, pas une promesse : l'archive compte environ 575 matchs par mois dans H1 (269 en 14 jours). C1 vers début novembre, C2 vers mi-novembre.
- Pour B1 à B4, beaucoup plus rares (B1 : 15 matchs en 14 jours au rythme actuel), le statut reste NON ÉVALUÉ tant que le seuil de 150 matchs n'est pas atteint, même après C2.

Les tableaux peuvent être consultés à tout moment, mais **un statut ne change qu'à un point de contrôle**. Regarder chaque jour et s'arrêter au premier bon chiffre fausserait le test.

### 7.3 Niveau d'exigence

- **5 configurations** sont testées et chacune est regardée à 2 points de contrôle. Pour limiter les faux positifs, les intervalles de décision sont à **99 %** et non à 95 %.
- Les intervalles à 95 % sont affichés pour information.

## 8. SUPER BASE

### 8.1 Ce que mesurent les indices existants (constat du 12/10, à reproduire par le code avant usage)

- **Indice x/4** (`moteur_v3/performance.py`) : test sur la moyenne et le pire match de chaque équipe, au même lieu.
  - Définition modifiée le 10/10 (v3) puis le 12/10 (v4). L'archive des indices mélange les deux versions, et 625 lignes sur 1 027 y ont été calculées après coup.
  - Recalculé en v4 sur 845 matchs de l'archive de test, dans H1 : 4/4 = 72,1 % (43 matchs), 0/4 = 77,8 % (27 matchs). Aucun écart exploitable.
  - Toutes cotes confondues : les 4/4 réussissent à 70,8 % ; la cote, une fois sa marge retirée, prévoyait 70,6 %.
- **Niveau d'échantillon V3** : nombre de matchs au même lieu. Il est repris dans B4.
- **Niveaux de confiance PROUVE / ÉTABLI** (`selection_adaptative.py`) : ils dépendent de l'archive V3, aujourd'hui jamais réglée (§ 10).
- **`calibrage_externe.py`** : ses règles sont validées sur les mêmes données que celles qui les ont fait découvrir. Il n'est pas utilisé comme critère.

### 8.2 Règle d'entrée d'un indice

Aucun indice n'est un critère SUPER BASE au départ. Un indice ne peut le devenir que si toutes ces conditions sont remplies :

1. Sa version est figée et déclarée dans une nouvelle version de ce protocole, avant le test.
2. Il est calculable avant le match pour **tous** les matchs de la BASE parente, pas seulement pour les sélections. L'archive de test le permet.
3. Sa BASE parente est au moins PROMETTEUR.
4. Sur les matchs postérieurs à sa déclaration, le sous-ensemble filtré par l'indice bat sa BASE parente : borne basse à 99 % de l'écart de ROI > 0, avec au moins 150 matchs dans le sous-ensemble.

Tant que ces conditions ne sont pas remplies, l'indice reste affiché comme information, avec le statut NON ÉVALUÉ.

## 9. État de départ (description seulement, pas une preuve)

Chiffres de l'audit du 12/10, sur des matchs antérieurs au test. Ils servent de repère et ne comptent pas dans les décisions.

| Ensemble | Matchs | Réussite | Seuil (1 ÷ cote) | ROI |
|---|---|---|---|---|
| H1, archive de test (28/09 – 11/10) | 269 | 74,7 % | 75,6 % | −1,0 % |
| H1, univers du Journal (08/09 – 11/10) | 518 | 74,7 % | 75,5 % | −1,0 % (95 % : −6 % ; +4 %) |

Les sous-ensembles des moteurs dans H1 comptent de 5 à 23 matchs : NON ÉVALUÉ.

**Correction d'une erreur de l'audit** : la réponse du 12/10 indiquait « environ 170 matchs par mois » dans H1. Le chiffre correct est **environ 450 à 575 par mois**, selon la source.

## 10. PR 45 : effets vérifiés et décision pour ce protocole

La PR 45 corrige le règlement de `data/v3/historique_selection.json`. Effets mesurés sur les données du 12/10 :
- 74 paris V3 réglés au lieu de 0.
- 11 candidats V3 sur 23 changent de source de probabilité. Exemple : 0,9055 devient 0,417, et le gain espéré passe de +0,28 à −0,41.
- Ces 11 candidats montent pourtant dans le classement (rang de preuve 2 → 3), même quand le gain espéré devient négatif.
- Le top 15 de V3 change de 3 paris.

**Décision pour ce protocole : la PR 45 n'est pas nécessaire.** La BASE règle elle-même les paris V3 à partir de `data/v3/journal/*.json` et des scores, en lecture seule. La PR 45 reste une décision séparée sur le classement des moteurs, hors de ce protocole.

## 11. Mise en œuvre (après validation de ce document seulement)

- **Branche dédiée**, jamais fusionnée sans décision explicite.
- **Un module** `base_protocole.py` en lecture seule. Il n'écrit que dans `data/base/` sur la branche dédiée.
- **Tests dédiés** :
  - chaque règle d'exclusion du § 4.2 ;
  - le rapprochement du Journal (3 cas qui passent, 3 qui échouent) ;
  - un match perdu reste compté ;
  - un statut ne change qu'à un point de contrôle ;
  - une empreinte modifiée invalide le point de contrôle.
- **Pas de workflow programmé** :
  - GitHub ne lance les tâches programmées que depuis la branche principale, et la branche principale ne doit pas être modifiée.
  - Ce n'est pas nécessaire : l'archive de test est déjà figée chaque nuit par le pipeline existant, et le calcul peut être relancé à tout moment sur la branche dédiée.
  - Les empreintes du § 4.4 prouvent que l'archive n'a pas changé entre-temps.
- **Aucune page du site** avant le point de contrôle C1.

## 12. Ce que ce protocole ne permet pas d'affirmer

- Que les cotes relevées sont celles disponibles au moment de parier (relevé médian 8,6 h avant le match).
- Qu'un résultat sur BetPawa se transpose à un autre bookmaker.
- Qu'un statut VALIDÉ restera vrai : un marché peut s'ajuster.
