# Découverte des indices par marché — méthode des victoires (26/10/2026)

Statut : ÉTUDE EN LECTURE SEULE. Aucun gel, aucune modification de production. Aucun indice n'est présenté comme validé.

## 1. Comment l'étude des victoires a découvert ses indices (preuves)

**Où sont les preuves.**
- Dans le dépôt (main) : `docs/ALPHA_SERIE.md` (sections « Validation des bandes de cotes 1X2 » et « Plus de 1,5 à chances maximales »), `data/alpha_serie/bandes_1x2.json` (`reference_etude`), commit `1b37e3c`, `alpha_serie/suivi.py` (gel et suivi).
- **Lacune à signaler** : les scripts qui ont *découvert* les règles n'avaient jamais été commités (ils étaient dans mon dossier de travail). Je les ai copiés tels quels dans `etudes/victoires_scripts_origine/` et **rejoués le 26/10/2026** ; les sorties sont dans `etudes/victoires_scripts_origine/sorties_rejouees_2026-10-26/`. Ce sont les seules preuves exécutables de la découverte.

**Les étapes réelles de la découverte des victoires** (scripts `rep1x2.py` → `v1x2.py` → `coh.py` → `gb.py` → `s1x2.py`/`s1x2b.py`/`s1x2c.py` → `odds1x2/2/3.py`) :

| # | Étape | Fichier | Ce qu'elle fait réellement |
|---|---|---|---|
| 1 | Population complète | `rep1x2.py` | Rejoue alpha sur **tous** les matchs analysés (14 161), pas seulement ceux où alpha propose une victoire. Garde les séries brutes (buts marqués/encaissés au lieu) de chaque équipe. |
| 2 | Point de départ | `v1x2.py` | Mesure le choix actuel d'alpha : victoire domicile 57,3 % avant / 55,6 % après le 01/04 ; extérieur 45 % — insuffisant. |
| 3 | Gagnants contre perdants | `coh.py` §1 | Moyennes de chaque caractéristique selon l'issue (victoire domicile, nul, victoire extérieur) sur tous les matchs. |
| 4 | Signal global | `coh.py` §2-3, `gb.py` | Régression logistique et boosting appris sur 2025, jugés après : y a-t-il un signal ? (domicile : meilleurs 2 % → 70,5 % ; extérieur → 55,7 %.) |
| 5 | **Recherche de configurations** | `s1x2.py`, `s1x2b.py`, `s1x2c.py` | Sur **14 caractéristiques bien plus larges que le moteur** (victoires, nuls, défaites, cages inviolées, matchs sans marquer, victoires par 2 buts, points par match, écart de buts…), toutes les combinaisons de **1 à 3 conditions** « caractéristique ≥ ou ≤ seuil » (24 857 règles testées pour le domicile, 7 093 pour l'extérieur). Règle gardée si son taux atteint la **cible dans chaque période de réglage** (A = 2025, B = janv.–mars 2026), classée par **fréquence** ; **jugée une seule fois** sur la période réservée (depuis le 01/04/2026). |
| 6 | Prix comme caractéristique | `odds1x2.py`, `odds2.py`, `odds3.py` | Les **bandes de cotes** sont testées sur tous les matchs, avec et sans filtre de probabilité, cotes BetPawa (archive) et Pinnacle (substitut) **séparées**, stabilité par mois (Pinnacle) et par semaine (BetPawa). Résultat : domicile 1,33–1,50 → 72,3 % (BetPawa, n=94) et 73,5 % (Pinnacle, n=211) ; extérieur 1,38–1,70 → 70,7 % et 67,5 % ; la probabilité n'ajoute rien dans la bande. |
| 7 | Gel prospectif | commit `1b37e3c` | Les deux bandes sont gelées comme règles candidates (aucun filtre de probabilité), suivi en conditions réelles, « 7 sur 10 = cible à confirmer, pas une garantie ». |

**Résultats rejoués (extraits).**
- Recherche sur variables larges (domicile, ≤ 3 conditions, ≥ 70 % en A et en B) : `la>=0.40 & gdh>=1.50` → A 70,8 %, B 71,0 %, **réservée 66,4 %** (borne basse 60,9 %, 1,27 pari/jour). Les règles à variables de séries se **dégradent** sur la période réservée.
- Ce qui a tenu : le **prix**. Bande domicile 1,33–1,50 : 72,3 % (BetPawa) et 73,5 % (Pinnacle, gagnés/matchs par mois : 2025-05 10/15, 2025-07 17/27, 2025-10 39/48, 2025-12 15/24).
- `obj.py` (Plus de 1,5) : même logique sur 8 849 paris proposés, règles à 1-2 conditions sur le total attendu, le plus petit/grand niveau d'équipe, l'écart et la valeur ; 41 règles sur 186 avec borne basse ≥ 80 % **avant et après** ; retenue : total attendu ≥ 3,4 (stabilité mensuelle contrôlée).

**Principe fondamental, tel que je le comprends à partir de ces preuves** : on ne cherche pas à *filtrer* les pronostics du moteur. On part de **tous les matchs**, on sépare **gagnants et perdants** d'après le score réel, on cherche **dans un grand éventail de caractéristiques** (dont le prix) les configurations qui les distinguent, on les **choisit sur la période de réglage** et on les **juge une seule fois** sur une période indépendante. La **rentabilité vient après**, séparément.

## 2. Ce qui différait dans mon étude précédente (branche `etude-marches-rigueur`, `alpha_serie/etude_marches.py`)

| Point | Étude des victoires | Mon étude précédente |
|---|---|---|
| Population | tous les matchs analysés | seulement les paris que le moteur propose déjà (filtrage des pronostics existants) |
| Caractéristiques | ~14 à 60, bien au-delà du moteur, dont le prix | 1 variable du moteur + « valeur » |
| Configurations | 1 à 3 conditions combinées | 1 seule condition |
| Gagnants / perdants | comparés explicitement, puis signal global testé | jamais comparés |
| Référence | matchs sans la configuration et taux de base | taux du marché + taux d'équilibre des cotes |
| Choix | cible de réussite atteinte en A **et** B, classé par fréquence, jugé une fois sur C | plus grande couverture / Wilson max sous une barre mêlant réussite et cotes |
| Cotes | évaluées **après**, séparément | **mêlées au verdict** : un rendement négatif suffisait à rejeter |
| Prix | utilisé comme caractéristique (bandes) | seulement un taux d'équilibre |
| Résultat | des règles à suivre, y compris à 70 % | 0 sur 29 : la méthode ne pouvait presque rien découvrir |

Mon erreur de fond : j'ai traité l'étude comme un *test de pronostics existants* (barre de rentabilité comprise), alors que les victoires avaient été obtenues par une *découverte* sur tous les matchs, la rentabilité étant évaluée à part.

## 3. Application aux autres marchés (même logique)
Voir la section générée ci-dessous (`python -m alpha_serie.decouverte_marches --ecrire`).
