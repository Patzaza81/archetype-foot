# Onglet « +1,5 buts » d'Analyse Verdict : la règle de buts de Patrick (21/11/2026)

Onglet **uniquement pour sa règle**, marché **plus de 1,5 buts** seulement. Code : `verif_regle_buts.py` (étude et évaluation), intégré à `verif_pronostic.py` (`fiche_match`, `page_donnees`, `selections_page`) et à `archetype_verif.js`. Données : `data/verif_pronostics/regle_buts.json` (réécrit par `python verif_regle_buts.py`).

## La règle (ses valeurs, aucune n'est calibrée par moi)

- Au moins **4 matchs au même lieu** pour chaque équipe (domicile pour l'une, extérieur pour l'autre), saison en cours, avant le match.
- Somme des buts **marqués** par match des deux équipes (chacune à son lieu) **≥ 3,5**.
- Somme des buts **encaissés** par match des deux équipes **≥ 2,8**.
- Marché affiché : « plus de 1,5 buts », cote **≥ 1,24** (sa décision du 21/11). Cette cote ne s'applique qu'à cet onglet : les autres onglets gardent la cote minimale 1,26 (`config/verif_pronostic.json`), et la PR #180 n'est pas nécessaire.
- Le verdict de la page (Tient / Réserve / Ne tient pas) ne filtre pas : seule la règle décide, le verdict est affiché à titre d'information.

## Étude sur les matchs déjà joués (`data/bloc_saisons`, 11 127 matchs évaluables)

- Règle remplie : **599 matchs, +1,5 réussi 83,6 %** (intervalle à 95 % : 80,5 à 86,4 %). Hors règle : 75,7 % sur 10 528 matchs.
- Cote d'équilibre 1,196 ; prudente (borne basse) **1,243**, d'où le 1,24.
- Réserve connue : une bonne partie de l'écart vient du championnat (les ligues riches en buts remplissent plus souvent la règle) ; l'effet propre de la règle est d'environ 2,4 points (p ≈ 0,07), pas démontré. Le taux est mesuré sur la période de l'archive, pas garanti pour la suite.

## Ce que l'onglet affiche aujourd'hui (21/11/2026, vérifié par un recalcul indépendant sur les données brutes)

La règle est remplie pour 44 matchs du 21 au 24/11, mais la cote du +1,5 est presque toujours sous 1,24 (de 1,04 à 1,21, le marché les juge très probables). Seuls 3 matchs passent : Željezničar – Borac (1,27), Árabe – San Francisco (1,33), Erzurumspor – Goztepe (1,31). L'onglet est donc **rare par construction**.

## Mesure réelle

La sélection « regle_buts » est gelée avant chaque coup d'envoi (`data/verif_pronostics/journal_selections.jsonl`, comme Top 20, Règles et Étude) ; le bilan réel s'affiche dans le tableau de la page quand des matchs sont terminés.

Tests : `tests/test_verif_regle_buts.py`.
