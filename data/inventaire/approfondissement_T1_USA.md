# Étape 6d — approfondissement : T1 extérieur et USA BTTS

Code : `approfondissement.py`. Contexte = conditions de la 1re famille validée. Résidu = issue − P1. Analyses exploratoires pour expliquer, pas pour valider.

## T1 — victoire de l'équipe extérieure
- Contexte : elo_diff <= -1.090 ; ext_sans_marquer_ext > 0.140 → 164 matchs, victoire extérieure 74.4% contre 47.3% annoncé par P1 ; reproduit dans les 5 saisons (63,6 / 87,9 / 70,8 / 73,0 / 70,6 % contre 41–51 % annoncé).
- Même contexte sur les autres marchés : domicile −0,15 (z −4,3), nul −0,12 (z −3,5), extérieur +0,27 (z +7,0), BTTS −0,08 : la masse se déplace du domicile et du nul vers l'extérieur.
- Fiabilité de P1 par déciles : les 5 premiers déciles de probabilité extérieure sont surestimés (jusqu'à −0,08), le dernier est sous-estimé (0,512 annoncé, 0,657 observé, z 3,9). **P1 est trop resserré** : il sous-estime les grands écarts de force.
- Facteur explicatif : l'écart Elo. Résidu extérieur par cinquième d'écart Elo : +0,117 (z 4,5) pour les plus gros favoris à l'extérieur, −0,078 (z −3,8) pour les plus gros favoris à domicile ; la variable « sans marquer à l'extérieur » n'est pas monotone et pèse peu.
- Pas un effet de deux ou trois clubs : Galatasaray, Fenerbahçe, Büyükşehir font 56 % du contexte (résidus +0,29, +0,48, +0,26), mais sans eux le résidu reste +0,198 (z 3,4 ; 71 matchs).
- Le lissage k de P1 n'explique pas : k = 5 est déjà le meilleur de la grille (perte 0,5553).
- Ce que la mesure dit : le gain est une recalibration en fonction de l'écart de force (queues), que les modèles linéaires du test des facteurs ne capturent pas (coefficient Elo stable −0,80 / −0,76 / −0,71 par écart-type mais gain vs recalibrage ≈ 0). Rejeu des familles : +0,0277 (2425), +0,0131 (2526).

## USA — BTTS
- Contexte : mu_dom > 1.460 ; ext_bc_exterieur <= 1.900 ; journee_min > 8.500 ; x_att_dom_def_ext > 2.362 → 1057 matchs (42% du championnat), BTTS 65.9% contre 56.6% annoncé.
- Ce n'est pas propre à BTTS : même contexte, plus de 1,5 / 2,5 / 3,5 buts = +0,059 / +0,076 / +0,057 (z 4,7 / 5,0 / 4,0) ; domicile −0,03, extérieur −0,01. C'est un contexte « riche en buts » sous-estimé par P1.
- Pas de concentration par équipe : 30 équipes, les 3 plus fréquentes ne font que 15 % ; sans elles résidu +0,092 (z 5,6).
- P1 sous-estime BTTS dans presque tous les déciles (fréquence 59,4 % contre 55,5 % annoncé en moyenne ; 9 déciles sur 10 sous-estimés). Buts par match 2,77 / 2,97 / 2,75 / 3,11 / 3,02 selon les saisons ; l'écart du contexte se réduit : +0,15 (2122), +0,14, +0,08, +0,07, +0,06 (2526) à mesure que P1 apprend le niveau de buts.
- Saison : résidu −0,008 en début de saison (≤ 6 matchs joués par la plus jeune des deux équipes), +0,02 jusqu'à 13, puis +0,07, +0,06 et +0,05 ensuite ; les classes de facteurs sont non monotones (pic pour mu_dom 1,6–1,7 et attaque × défense 2,6–2,9, quasi nul aux extrêmes).
- Sensibilité de P1 : plus on lisse (k = 40), mieux c'est (perte 0,6785 contre 0,6857 pour k = 2) : les forces par équipe y sont bruitées.
- Rejeu : une seule famille, 2526 = −0,0057 de perte log, écart de calibration 0,016 → 0,049. **Le phénomène était un biais de niveau en décroissance, pas une règle durable.**

Détail : `approfondissement_T1_USA.json`.
