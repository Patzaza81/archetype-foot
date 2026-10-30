# Moteur DC (`moteur_dc/`) — version 2 (30/10/2026)

Architecture de Patrick (5 modules reçus le 30/10/2026), ordre du 30/10/2026 : réintégrer les Modules 1, 1.5, 3 et 4 et brancher les paramètres du
Module 1 dans Dixon-Coles ; Module 5 (cotes, EV, Kelly) laissé de côté. Branche `moteur-dc`, jamais fusionnée sans « Fusionner ».
Autonome (aucun import d'un autre moteur), hors générateur de tickets. Statut : observation.

## Chaîne d'un match (`coeur.analyser`)
| Module | Fichier | Ce qu'il fait |
|---|---|---|
| 1 | `module1.py` | Les 44 paramètres de chaque équipe du championnat (classement, moyennes, terrain, fréquences, amplitude, score modal, Forme_PPM, streak, volatilité, xPts, IE, RC, rangs, profil 1-5 et Style_Tag, CBD/CBE, gap), avec les matchs STRICTEMENT antérieurs au jour du match. |
| 1.5 | `contrat.py` | `match_input` (structure de la Section A) et contrôles stricts : Filtre 0 (≥ 4 matchs à domicile / à l'extérieur), types, NaN, historiques d'au moins 4 matchs en ordre chronologique strict. Erreur = match exclu, raison gelée. |
| 2 | `modele.py` + `ajustements.py` | Dixon-Coles pénalisé (shrinkage) sur le championnat entier ; Forme→xi, IE→λ, Amplitude et Score modal→ρ, Profil croisé→λ. Chaque effet a une force apprise hors échantillon. |
| 3 | `coeur.py`, `marches.py` | 103 marchés (1N2, double chance, plus/moins, BTTS, **Multigoal 0-1 / 2-3 / 4+**, buts par équipe, handicaps, combinés) par SOMME des cases de la grille ; k/n sur les matchs comparables (A à domicile + B à l'extérieur, score orienté) ; Base = fréquence du marché dans le championnat cette saison avant le match. |
| 4 | `selecteur.py` | **Option B de Patrick (30/10/2026)** : ordre de Patrick (30/10, 17 h 39) : 1. Edge = P − Base ≥ 10 % (et ≥ EMAC) ; 2. plancher P ≥ 60 % ; 3. Wilson calculé sur les seuls validés, simple avertissement. Bonferroni et Z supprimés comme filtre (Z affiché). Intervalle de Wilson à 95 % de p̂ = simple avertissement (paris avertis classés après). Une issue par marché, jamais deux fois le même événement. Classement par probabilité ; principal = le plus probable. **Aucune cote.** |

Précisions imposées par la spécification (aucune valeur choisie) :
- Forme_PPM : avec J ≤ 5 la formule reçue divise par 0 ou par un nombre négatif → PPM simple.
- Profil : seuils de Patrick (IE > 1,2 = Opportuniste), sinon attaque et défense comparées à la médiane du championnat.
- Dynamique de forme = |Forme_PPM − PPM|. IE et amplitude au lieu du match (contrat 1.5).
- EMAC : la formule reçue (moyenne de |P − Y|, Y = 0/1) vaut 0,4 à 0,5 quel que soit le modèle ; remplacée par l'erreur de calibration par
  dixième de probabilité (pondérée). Production : 30 derniers jours du journal gelé (tous les marchés des matchs terminés), sinon valeur du calibrage.

## Calibrage (`python -m moteur_dc.calibrage [tout|reprise]`) — résultats du 30/10/2026
1. Hyperparamètres (Football-Data 2025-26, 9 488 matchs, vraisemblance prédictive) : σ = 0,25 ; xi = 0,004 ; ρ = −0,04.
2. Forces des effets (même protocole, la grille s'étend tant que ça s'améliore) :
   forme **−1,0** (le contraire de l'hypothèse : une équipe en pleine dynamique gagne à garder ses anciens matchs), IE **0**, amplitude **+0,02**,
   score modal **−0,08**, style croisé **0**. Gain : −2,91781 → −2,91753 par match (négligeable).
3. Validation Football-Data 2026-27 (1 598 matchs) : sans effet −2,99588 ; avec les forces apprises −2,99622 (**pire**) ; la forme a été remise à 0
   par la règle fixée avant le calcul ; final (amplitude + score modal) −2,99561. **Les paramètres du Module 1 n'apportent presque rien au
   Dixon-Coles du championnat entier** (+0,0003 par match). IE et style croisé : aucun effet mesurable, force 0.
4. EMAC = **0,0054** (par famille 0,005 à 0,013) : le modèle est très bien calibré en moyenne.
5. Contrôle du Module 4 sur l'archive ARCHETYPE (827 matchs joués analysables, calibrage seulement, pas un bilan) : **0 pari**.
   Pourquoi : avec EMAC = 0,0054, l'étape 0 exige |P − p̂| ≤ 0,011 alors que p̂ vient d'environ 20 matchs (erreur d'échantillonnage ≈ 0,10) ;
   et avec m = 103 marchés, Z doit dépasser 3,30 : sur 20 matchs, un marché dont la base dépasse 65 % ne peut JAMAIS passer (il faudrait p̂ > 1).
   Variante mesurée (non appliquée) où l'étape 0 tient compte de l'erreur d'échantillonnage de p̂ : 36 paris principaux sur 827 matchs,
   probabilité moyenne 22 %, réussite 10 % (développement) et 27 % (réserve). Le Module 4 choisit des marchés qui s'écartent du championnat,
   pas des marchés qui gagnent souvent.
6. Production au 30/10/2026 : 586 matchs gelés, 436 analysés, 1 pari (handicap −1,5 extérieur, P = 41,6 %).
   30 matchs exclus par le contrat parce qu'une équipe a deux matchs le même jour dans l'assemblage (donnée à vérifier, ex. Trefelin, Cymru Premier).

## Production (`python -m moteur_dc.suivi pipeline`)
Étape « Moteur DC » de `pipeline.yml` (après omega, `continue-on-error`, `scipy` installé). Journal `data/dc/journal.jsonl` (ajout seul, dernier gel
avant le coup d'envoi = celui qui compte, résultats réglés une fois) ; il garde les probabilités des 103 marchés de chaque match analysé (EMAC glissante).
Page `data/dc/pronostics.json`. Bilan réel : `python bilan_reel.py` (lignes DC). Le journal de la version 1 (jamais en production) a été effacé.

## Corrections du 30/10/2026 (Patrick) et matchs du soir
Étape 0 par intervalle de Wilson, classement par probabilité. Rapport : `python -m moteur_dc.rapport <début UTC> <fin UTC>` (→ `data/dc/rapport_*.json`).
Matchs du 30/10/2026 entre 18 h et 22 h (Douala) : 57 matchs, 46 analysés, **0 pari**. L'étape 0 ne rejette presque plus rien (95 marchés sur 4 738) ;
tout tombe à l'étape 1 : les tendances fortes du modèle (80 à 97 %) sont confirmées par les données (P dans l'intervalle de Wilson) mais leur Z
vaut environ 0, car le marché est aussi fréquent dans tout le championnat. Le Z contre la base ne mesure pas la réussite, il mesure l'écart au championnat.
Gel du même jour (tous les matchs à venir) : 12 paris sur les 31/10-02/11, probabilité de 0,9 % à 67 %, aucun à 70 % ou plus.
Information (non appliqué) : Z simple 1,645 → 34 matchs avec pari, 119 paris dont 17 à P ≥ 70 % ; sans l'étape 1 → un pari par match analysé,
principal entre 79 et 97 %, cotes de 1,03 à 1,32 quand elles existent.

## Option B appliquée le 30/10/2026
Matchs du soir (18 h-22 h Douala) : 57 matchs, 46 analysés, 33 paris sur 19 matchs, tous à P > 75 %, 1 avec avertissement Wilson.
Cotes connues : 1,05 à 1,36 ; 15 paris sans cote BetPawa.

Ordre Edge ≥ 10 % puis P ≥ 60 % (même soir) : 90 paris sur 26 matchs, P moyenne 73,7 % (principaux 80,6 %), 2 avertissements ;
4 victoires (1N2), 19 double chance, 18 combinés double chance + buts.

## Points ouverts
- Page `pronostics_dc.html` non faite.
- Tests : `tests/test_moteur_dc.py` (30 tests, 3 cas qui passent et 3 qui échouent pour le contrat et le Module 4).
