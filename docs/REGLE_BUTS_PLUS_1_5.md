# Onglet « +1,5 buts » d'Analyse Verdict : la règle de buts de Patrick (21/11/2026)

**Depuis le 22/11/2026 (demande de Patrick)** : l'onglet montre **TOUT** « plus de 1,5 buts » coté **1,24 ou plus** (seuil propre à cet onglet, rétabli par Patrick le 22/11 ; les autres onglets gardent 1,26, `config/verif_pronostic.json`) et évaluable (4 matchs au même lieu pour chaque équipe), **quel que soit le verdict**. Le seuil de 1,24 est conservé ; plus aucun calcul de gain / cote d'équilibre. La règle de buts + le filtre du championnat ne retirent rien : ils posent le repère « Règle validée » (et le match passe en premier, dans son jour). **Tout le +1,5 de l'onglet est aussi dans l'onglet Étude** (demande de Patrick, 22/11) : règle remplie = taux de l'étude de la règle, sinon taux du match au même lieu. Les matchs « règle remplie » restent dans dans la sélection gelée `regle_buts` ; l'onglet entier est gelé sous `plus15`. Données de la carte : `plus15` dans `page_donnees` (`regle_remplie`, sommes, taux du championnat, `pari`).

Onglet d'origine (21/11) : **uniquement pour sa règle**, marché **plus de 1,5 buts** seulement. Code : `verif_regle_buts.py` (étude et évaluation), intégré à `verif_pronostic.py` (`fiche_match`, `page_donnees`, `selections_page`) et à `archetype_verif.js`. Données : `data/verif_pronostics/regle_buts.json` (réécrit par `python verif_regle_buts.py`).

## La règle (ses valeurs, aucune n'est calibrée par moi)

- Au moins **4 matchs au même lieu** pour chaque équipe (domicile pour l'une, extérieur pour l'autre), saison en cours, avant le match.
- Somme des buts **marqués** par match des deux équipes (chacune à son lieu) **≥ 3,5**.
- Somme des buts **encaissés** par match des deux équipes **≥ 2,8**.
- Marché affiché : « plus de 1,5 buts », cote **≥ 1,24**, seuil propre à cet onglet (décision de Patrick, 21/11, conservée le 22/11 ; les autres onglets : 1,26 ; la PR #180 n'est pas nécessaire).
- Le verdict de la page (Tient / Réserve / Ne tient pas) ne filtre pas : seule la règle décide, le verdict est affiché à titre d'information.

## Filtre du championnat (22/11/2026, demande de Patrick)

- Le match n'est retenu que si, dans son championnat, au moins **76 %** des matchs PRÉCÉDENTS ont compté 2 buts ou plus (taux lissé vers le taux général de 75 %, poids 10 matchs, pour les championnats peu joués).
- Le seuil n'est pas posé à la main : choisi sur la **première moitié** de la période (meilleure borne basse de l'intervalle, au moins 100 matchs de la règle), puis **vérifié sur la seconde moitié**, non vue pour ce choix. Écrit dans `regle_buts.json` (`championnat`, `etude.verification`) par `python verif_regle_buts.py`.
- Sur la page : taux du championnat calculé par `verif_pronostic.totaux_championnats` (historiques des équipes du flux, un match compté une fois, par l'équipe à domicile) et `championnat_avant` (matchs d'avant la date du match seulement). Aucune donnée de championnat = pas de pari.
- Ne vaut que pour le marché « plus de 1,5 buts » du match. Les autres onglets et marchés ne changent pas (vérifié : 3 112 matchs de la page, aucun autre champ modifié).

**Résultat honnête** : règle + championnat = 488 matchs, +1,5 réussi 86,3 % (intervalle 82,9 à 89,0 %) ; règle seule = 599 matchs, 83,6 %. Mais le gain est surtout sur la moitié qui a servi à choisir le seuil (81,4 % → 86,1 %). Sur la **moitié non vue** : 86,4 % sur 258 matchs contre 86,0 % sur 292 pour la règle seule, soit environ +0,5 point : le filtre ne nuit pas, son apport réel reste à confirmer sur les prochains matchs.

Rejeu sur les matchs terminés de la page (28/09 au 20/11) : la règle seule donnait 10 réussis sur 18, avec le filtre 6 sur 9 ; 9 matchs retirés (4 réussis sur 9). Petits échantillons : aucune conclusion.

## Étude sur les matchs déjà joués (`data/bloc_saisons`, 11 127 matchs évaluables)

- Règle remplie : **599 matchs, +1,5 réussi 83,6 %** (intervalle à 95 % : 80,5 à 86,4 %). Hors règle : 75,7 % sur 10 528 matchs.
- Cote d'équilibre 1,196 ; prudente (borne basse) **1,243**, d'où le 1,24.
- Réserve connue : une bonne partie de l'écart vient du championnat (les ligues riches en buts remplissent plus souvent la règle) ; l'effet propre de la règle est d'environ 2,4 points (p ≈ 0,07), pas démontré. Le taux est mesuré sur la période de l'archive, pas garanti pour la suite.

## Ce que l'onglet affiche aujourd'hui (21/11/2026, vérifié par un recalcul indépendant sur les données brutes)

La règle est remplie pour 44 matchs du 21 au 24/11, mais la cote du +1,5 est presque toujours sous 1,24 (de 1,04 à 1,21, le marché les juge très probables). Seuls 3 matchs passent : Željezničar – Borac (1,27), Árabe – San Francisco (1,33), Erzurumspor – Goztepe (1,31). L'onglet est donc **rare par construction**.

## Mesure réelle

La sélection « regle_buts » est gelée avant chaque coup d'envoi (`data/verif_pronostics/journal_selections.jsonl`, comme Top 20, Règles et Étude) ; le bilan réel s'affiche dans le tableau de la page quand des matchs sont terminés.

Tests : `tests/test_verif_regle_buts.py` (65 tests, dont le filtre du championnat : cas qui passent, qui échouent, sans donnée, sans fuite vers l'avenir).
