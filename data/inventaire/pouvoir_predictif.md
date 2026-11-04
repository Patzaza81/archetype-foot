# Pouvoir predictif des marches (scores seuls, validation chronologique)

Tests: 912 (competition x methode x marche); seuil Bonferroni z>3.87.
Gain = perte log (reference - methode) par match; >0 = bat la frequence historique de la competition. 'avantage' = z>1.96 ET gain>0 dans TOUTES les saisons test; 'avantage_robuste' = idem avec z au-dessus du seuil Bonferroni.

## 1. Par marche et methode (38 competitions)

| Marche | Methode | avantage_robuste | avantage | indetermine | aucun_avantage | gain moyen |
|---|---|---|---|---|---|---|
| 1X2 | P1 | 25 | 6 | 7 | 0 | +0.0551 |
| 1X2 | P2 | 21 | 9 | 8 | 0 | +0.0485 |
| 1X2 | F | 22 | 5 | 10 | 1 | +0.0308 |
| dom | P1 | 24 | 11 | 3 | 0 | +0.0460 |
| dom | P2 | 21 | 11 | 6 | 0 | +0.0404 |
| dom | F | 25 | 7 | 6 | 0 | +0.0296 |
| nul | P1 | 3 | 7 | 21 | 7 | +0.0035 |
| nul | P2 | 2 | 6 | 19 | 11 | +0.0024 |
| nul | F | 0 | 0 | 17 | 21 | -0.0001 |
| ext | P1 | 24 | 7 | 7 | 0 | +0.0396 |
| ext | P2 | 23 | 8 | 6 | 1 | +0.0358 |
| ext | F | 22 | 7 | 8 | 1 | +0.0260 |
| o15 | P1 | 1 | 7 | 26 | 4 | +0.0041 |
| o15 | P2 | 0 | 6 | 23 | 9 | +0.0028 |
| o15 | F | 0 | 6 | 19 | 13 | +0.0017 |
| o25 | P1 | 0 | 9 | 24 | 5 | +0.0054 |
| o25 | P2 | 0 | 5 | 28 | 5 | +0.0038 |
| o25 | F | 0 | 7 | 28 | 3 | +0.0027 |
| o35 | P1 | 0 | 9 | 24 | 5 | +0.0054 |
| o35 | P2 | 1 | 2 | 31 | 4 | +0.0039 |
| o35 | F | 0 | 5 | 26 | 7 | +0.0025 |
| btts | P1 | 0 | 4 | 23 | 11 | +0.0016 |
| btts | P2 | 0 | 2 | 20 | 16 | +0.0006 |
| btts | F | 0 | 1 | 21 | 16 | +0.0003 |

## 2. Cas avec avantage (tous, sans selection sur le test)

| Comp | Marche | Methode | Matchs test | Gain/match | z | Saisons | Reussite methode | Reussite reference | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| ARG | dom | P2 | 2254 | +0.0088 | 3.03 | 4/4 | 0.587 | 0.573 | avantage |
| ARG | dom | P1 | 2254 | +0.0095 | 2.87 | 4/4 | 0.586 | 0.573 | avantage |
| ARG | ext | P2 | 2254 | +0.0066 | 2.28 | 4/4 | 0.747 | 0.747 | avantage |
| ARG | 1X2 | P1 | 2254 | +0.0081 | 2.18 | 4/4 | 0.426 | 0.427 | avantage |
| ARG | ext | F | 2254 | +0.0053 | 2.03 | 4/4 | 0.747 | 0.747 | avantage |
| ARG | o15 | F | 2254 | +0.0030 | 2.0 | 4/4 | 0.625 | 0.625 | avantage |
| AUT | 1X2 | F | 774 | +0.0441 | 5.84 | 4/4 | 0.474 | 0.398 | avantage_robuste |
| AUT | dom | F | 774 | +0.0380 | 5.7 | 4/4 | 0.634 | 0.602 | avantage_robuste |
| AUT | ext | F | 774 | +0.0333 | 5.14 | 4/4 | 0.676 | 0.668 | avantage_robuste |
| AUT | ext | P1 | 774 | +0.0474 | 4.52 | 4/4 | 0.700 | 0.668 | avantage_robuste |
| AUT | ext | P2 | 774 | +0.0457 | 4.25 | 4/4 | 0.685 | 0.668 | avantage_robuste |
| AUT | dom | P2 | 774 | +0.0461 | 3.82 | 4/4 | 0.618 | 0.602 | avantage |
| B1 | dom | F | 1241 | +0.0386 | 8.62 | 4/4 | 0.634 | 0.567 | avantage_robuste |
| B1 | dom | P1 | 1241 | +0.0650 | 7.67 | 4/4 | 0.669 | 0.567 | avantage_robuste |
| B1 | 1X2 | F | 1241 | +0.0370 | 7.61 | 4/4 | 0.490 | 0.433 | avantage_robuste |
| B1 | 1X2 | P1 | 1241 | +0.0729 | 7.28 | 4/4 | 0.507 | 0.433 | avantage_robuste |
| B1 | ext | F | 1241 | +0.0318 | 6.84 | 4/4 | 0.700 | 0.689 | avantage_robuste |
| B1 | 1X2 | P2 | 1241 | +0.0643 | 6.53 | 4/4 | 0.500 | 0.433 | avantage_robuste |
| B1 | dom | P2 | 1241 | +0.0548 | 6.3 | 4/4 | 0.645 | 0.567 | avantage_robuste |
| B1 | ext | P2 | 1241 | +0.0452 | 5.46 | 4/4 | 0.700 | 0.689 | avantage_robuste |
| B1 | ext | P1 | 1241 | +0.0475 | 5.45 | 4/4 | 0.699 | 0.689 | avantage_robuste |
| B1 | nul | P1 | 1241 | +0.0076 | 3.09 | 4/4 | 0.744 | 0.744 | avantage |
| B1 | o35 | P1 | 1241 | +0.0087 | 2.68 | 4/4 | 0.686 | 0.685 | avantage |
| B1 | nul | P2 | 1241 | +0.0063 | 2.32 | 4/4 | 0.744 | 0.744 | avantage |
| B1 | o15 | P1 | 1241 | +0.0063 | 2.0 | 4/4 | 0.774 | 0.774 | avantage |
| BRA | dom | P1 | 1520 | +0.0328 | 6.21 | 4/4 | 0.615 | 0.528 | avantage_robuste |
| BRA | 1X2 | P1 | 1520 | +0.0374 | 6.11 | 4/4 | 0.485 | 0.472 | avantage_robuste |
| BRA | dom | P2 | 1520 | +0.0310 | 5.48 | 4/4 | 0.606 | 0.528 | avantage_robuste |
| BRA | 1X2 | P2 | 1520 | +0.0330 | 5.45 | 4/4 | 0.480 | 0.472 | avantage_robuste |
| BRA | ext | P1 | 1520 | +0.0219 | 4.95 | 4/4 | 0.741 | 0.739 | avantage_robuste |
| BRA | dom | F | 1520 | +0.0206 | 4.9 | 4/4 | 0.595 | 0.528 | avantage_robuste |
| BRA | ext | P2 | 1520 | +0.0179 | 4.01 | 4/4 | 0.743 | 0.739 | avantage_robuste |
| BRA | 1X2 | F | 1520 | +0.0166 | 3.57 | 4/4 | 0.474 | 0.472 | avantage |
| BRA | ext | F | 1520 | +0.0134 | 3.42 | 4/4 | 0.738 | 0.739 | avantage |
| BRA | nul | P1 | 1520 | +0.0057 | 3.04 | 4/4 | 0.733 | 0.733 | avantage |
| BRA | nul | P2 | 1520 | +0.0047 | 2.57 | 4/4 | 0.733 | 0.733 | avantage |
| BRA | o15 | P1 | 1520 | +0.0040 | 1.99 | 4/4 | 0.711 | 0.711 | avantage |
| CHN | ext | F | 1026 | +0.0552 | 8.94 | 4/4 | 0.713 | 0.688 | avantage_robuste |
| CHN | dom | F | 1026 | +0.0562 | 8.85 | 4/4 | 0.647 | 0.552 | avantage_robuste |
| CHN | 1X2 | P1 | 1026 | +0.1140 | 8.4 | 4/4 | 0.556 | 0.448 | avantage_robuste |
| CHN | dom | P1 | 1026 | +0.0932 | 7.87 | 4/4 | 0.681 | 0.552 | avantage_robuste |
| CHN | 1X2 | F | 1026 | +0.0615 | 7.55 | 4/4 | 0.525 | 0.448 | avantage_robuste |
| CHN | ext | P1 | 1026 | +0.0841 | 7.09 | 4/4 | 0.730 | 0.688 | avantage_robuste |
| CHN | 1X2 | P2 | 1026 | +0.0978 | 6.97 | 4/4 | 0.539 | 0.448 | avantage_robuste |
| CHN | dom | P2 | 1026 | +0.0804 | 6.53 | 4/4 | 0.682 | 0.552 | avantage_robuste |
| CHN | ext | P2 | 1026 | +0.0779 | 6.46 | 4/4 | 0.723 | 0.688 | avantage_robuste |
| CHN | o25 | P1 | 1026 | +0.0127 | 3.34 | 4/4 | 0.567 | 0.552 | avantage |
| CHN | o35 | P1 | 1026 | +0.0188 | 3.14 | 4/4 | 0.655 | 0.650 | avantage |
| CHN | o35 | F | 1026 | +0.0128 | 3.02 | 4/4 | 0.650 | 0.650 | avantage |
| CHN | o35 | P2 | 1026 | +0.0173 | 2.55 | 4/4 | 0.650 | 0.650 | avantage |
| D1 | dom | F | 1224 | +0.0444 | 8.65 | 4/4 | 0.645 | 0.566 | avantage_robuste |
| D1 | 1X2 | P1 | 1224 | +0.0764 | 7.7 | 4/4 | 0.521 | 0.434 | avantage_robuste |
| D1 | dom | P1 | 1224 | +0.0625 | 7.44 | 4/4 | 0.652 | 0.566 | avantage_robuste |
| D1 | 1X2 | P2 | 1224 | +0.0713 | 7.29 | 4/4 | 0.514 | 0.434 | avantage_robuste |
| D1 | dom | P2 | 1224 | +0.0589 | 7.11 | 4/4 | 0.638 | 0.566 | avantage_robuste |
| D1 | 1X2 | F | 1224 | +0.0446 | 6.84 | 4/4 | 0.507 | 0.434 | avantage_robuste |
| D1 | ext | F | 1224 | +0.0357 | 6.54 | 4/4 | 0.696 | 0.685 | avantage_robuste |
| D1 | ext | P1 | 1224 | +0.0586 | 6.5 | 4/4 | 0.703 | 0.685 | avantage_robuste |
| D1 | ext | P2 | 1224 | +0.0546 | 6.31 | 4/4 | 0.706 | 0.685 | avantage_robuste |
| D1 | o35 | P1 | 1224 | +0.0138 | 3.06 | 4/4 | 0.596 | 0.588 | avantage |
| D1 | o35 | F | 1224 | +0.0091 | 2.66 | 4/4 | 0.588 | 0.588 | avantage |
| D2 | 1X2 | P1 | 1224 | +0.0225 | 4.16 | 4/4 | 0.460 | 0.447 | avantage_robuste |
| D2 | dom | P1 | 1224 | +0.0209 | 4.15 | 4/4 | 0.598 | 0.553 | avantage_robuste |
| D2 | 1X2 | P2 | 1224 | +0.0213 | 3.63 | 4/4 | 0.455 | 0.447 | avantage |
| D2 | dom | P2 | 1224 | +0.0168 | 3.15 | 4/4 | 0.600 | 0.553 | avantage |
| D2 | ext | P2 | 1224 | +0.0142 | 2.97 | 4/4 | 0.691 | 0.695 | avantage |
| D2 | ext | P1 | 1224 | +0.0129 | 2.74 | 4/4 | 0.693 | 0.695 | avantage |
| D2 | ext | F | 1224 | +0.0090 | 2.63 | 4/4 | 0.694 | 0.695 | avantage |
| D2 | dom | F | 1224 | +0.0091 | 2.5 | 4/4 | 0.564 | 0.553 | avantage |
| DNK | dom | F | 770 | +0.0254 | 4.16 | 4/4 | 0.609 | 0.582 | avantage_robuste |
| DNK | ext | F | 770 | +0.0235 | 4.12 | 4/4 | 0.682 | 0.680 | avantage_robuste |
| DNK | 1X2 | P1 | 770 | +0.0387 | 3.44 | 4/4 | 0.484 | 0.418 | avantage |
| DNK | 1X2 | P2 | 770 | +0.0372 | 3.36 | 4/4 | 0.475 | 0.418 | avantage |
| DNK | ext | P1 | 770 | +0.0302 | 3.13 | 4/4 | 0.690 | 0.680 | avantage |
| DNK | 1X2 | F | 770 | +0.0209 | 3.12 | 4/4 | 0.460 | 0.418 | avantage |
| DNK | dom | P2 | 770 | +0.0297 | 3.0 | 4/4 | 0.618 | 0.582 | avantage |
| DNK | dom | P1 | 770 | +0.0276 | 2.69 | 4/4 | 0.612 | 0.582 | avantage |
| DNK | o25 | P1 | 770 | +0.0062 | 1.98 | 4/4 | 0.558 | 0.540 | avantage |
| E0 | dom | F | 1520 | +0.0456 | 9.37 | 4/4 | 0.641 | 0.555 | avantage_robuste |
| E0 | 1X2 | F | 1520 | +0.0509 | 8.98 | 4/4 | 0.516 | 0.445 | avantage_robuste |
| E0 | 1X2 | P1 | 1520 | +0.0802 | 8.61 | 4/4 | 0.528 | 0.445 | avantage_robuste |
| E0 | ext | F | 1520 | +0.0415 | 8.59 | 4/4 | 0.696 | 0.685 | avantage_robuste |
| E0 | 1X2 | P2 | 1520 | +0.0700 | 8.33 | 4/4 | 0.529 | 0.445 | avantage_robuste |
| E0 | dom | P1 | 1520 | +0.0669 | 7.87 | 4/4 | 0.658 | 0.555 | avantage_robuste |
| E0 | dom | P2 | 1520 | +0.0576 | 7.56 | 4/4 | 0.634 | 0.555 | avantage_robuste |
| E0 | ext | P1 | 1520 | +0.0593 | 7.19 | 4/4 | 0.700 | 0.685 | avantage_robuste |
| E0 | ext | P2 | 1520 | +0.0529 | 6.51 | 4/4 | 0.707 | 0.685 | avantage_robuste |
| E0 | o15 | P1 | 1520 | +0.0051 | 2.74 | 4/4 | 0.805 | 0.805 | avantage |
| E0 | o15 | P2 | 1520 | +0.0048 | 2.64 | 4/4 | 0.805 | 0.805 | avantage |
| E0 | o25 | P2 | 1520 | +0.0055 | 2.37 | 4/4 | 0.566 | 0.572 | avantage |
| E0 | nul | P2 | 1520 | +0.0045 | 2.05 | 4/4 | 0.759 | 0.759 | avantage |
| E0 | o25 | F | 1520 | +0.0033 | 2.02 | 4/4 | 0.569 | 0.572 | avantage |
| E1 | 1X2 | P1 | 2208 | +0.0259 | 5.91 | 4/4 | 0.459 | 0.433 | avantage_robuste |
| E1 | dom | P1 | 2208 | +0.0240 | 5.71 | 4/4 | 0.608 | 0.567 | avantage_robuste |
| E1 | ext | F | 2208 | +0.0149 | 5.29 | 4/4 | 0.697 | 0.696 | avantage_robuste |
| E1 | 1X2 | P2 | 2208 | +0.0201 | 4.84 | 4/4 | 0.449 | 0.433 | avantage_robuste |
| E1 | dom | F | 2208 | +0.0129 | 4.75 | 4/4 | 0.582 | 0.567 | avantage_robuste |
| E1 | dom | P2 | 2208 | +0.0177 | 4.61 | 4/4 | 0.597 | 0.567 | avantage_robuste |
| E1 | ext | P2 | 2208 | +0.0146 | 4.36 | 4/4 | 0.695 | 0.696 | avantage_robuste |
| E1 | ext | P1 | 2208 | +0.0165 | 4.31 | 4/4 | 0.697 | 0.696 | avantage_robuste |
| E1 | 1X2 | F | 2208 | +0.0126 | 3.97 | 4/4 | 0.453 | 0.433 | avantage_robuste |
| E1 | btts | P1 | 2208 | +0.0033 | 2.29 | 4/4 | 0.522 | 0.508 | avantage |
| E2 | 1X2 | P1 | 2208 | +0.0407 | 7.69 | 4/4 | 0.494 | 0.438 | avantage_robuste |
| E2 | dom | P1 | 2208 | +0.0347 | 7.08 | 4/4 | 0.609 | 0.562 | avantage_robuste |
| E2 | ext | P1 | 2208 | +0.0319 | 6.76 | 4/4 | 0.689 | 0.685 | avantage_robuste |
| E2 | dom | F | 2208 | +0.0200 | 5.93 | 4/4 | 0.595 | 0.562 | avantage_robuste |
| E2 | ext | F | 2208 | +0.0168 | 5.79 | 4/4 | 0.685 | 0.685 | avantage_robuste |
| E2 | 1X2 | P2 | 2208 | +0.0303 | 5.61 | 4/4 | 0.476 | 0.438 | avantage_robuste |
| E2 | ext | P2 | 2208 | +0.0239 | 5.34 | 4/4 | 0.683 | 0.685 | avantage_robuste |
| E2 | 1X2 | F | 2208 | +0.0195 | 5.03 | 4/4 | 0.468 | 0.438 | avantage_robuste |
| E2 | dom | P2 | 2208 | +0.0250 | 4.81 | 4/4 | 0.601 | 0.562 | avantage_robuste |
| E3 | 1X2 | P1 | 2208 | +0.0167 | 4.81 | 4/4 | 0.447 | 0.426 | avantage_robuste |
| E3 | ext | P1 | 2208 | +0.0139 | 4.32 | 4/4 | 0.693 | 0.692 | avantage_robuste |
| E3 | dom | P1 | 2208 | +0.0110 | 3.57 | 4/4 | 0.584 | 0.574 | avantage |
| E3 | 1X2 | P2 | 2208 | +0.0115 | 3.2 | 4/4 | 0.438 | 0.426 | avantage |
| E3 | ext | P2 | 2208 | +0.0092 | 3.0 | 4/4 | 0.692 | 0.692 | avantage |
| E3 | dom | P2 | 2208 | +0.0073 | 2.52 | 4/4 | 0.580 | 0.574 | avantage |
| E3 | dom | F | 2208 | +0.0061 | 2.34 | 4/4 | 0.583 | 0.574 | avantage |
| E3 | 1X2 | F | 2208 | +0.0062 | 2.06 | 4/4 | 0.434 | 0.426 | avantage |
| EC | 1X2 | P1 | 2208 | +0.0473 | 8.22 | 4/4 | 0.467 | 0.430 | avantage_robuste |
| EC | dom | P1 | 2208 | +0.0398 | 7.98 | 4/4 | 0.634 | 0.570 | avantage_robuste |
| EC | 1X2 | P2 | 2208 | +0.0360 | 6.54 | 4/4 | 0.457 | 0.430 | avantage_robuste |
| EC | dom | F | 2208 | +0.0217 | 6.51 | 4/4 | 0.608 | 0.570 | avantage_robuste |
| EC | dom | P2 | 2208 | +0.0313 | 6.24 | 4/4 | 0.616 | 0.570 | avantage_robuste |
| EC | ext | P1 | 2208 | +0.0316 | 6.12 | 4/4 | 0.698 | 0.687 | avantage_robuste |
| EC | ext | F | 2208 | +0.0162 | 5.17 | 4/4 | 0.686 | 0.687 | avantage_robuste |
| EC | ext | P2 | 2208 | +0.0235 | 5.14 | 4/4 | 0.688 | 0.687 | avantage_robuste |
| EC | 1X2 | F | 2208 | +0.0177 | 4.86 | 4/4 | 0.448 | 0.430 | avantage_robuste |
| EC | o35 | P2 | 2208 | +0.0123 | 4.1 | 4/4 | 0.690 | 0.690 | avantage_robuste |
| EC | o35 | F | 2208 | +0.0090 | 3.79 | 4/4 | 0.690 | 0.690 | avantage |
| EC | o15 | F | 2208 | +0.0056 | 3.35 | 4/4 | 0.785 | 0.785 | avantage |
| EC | nul | P1 | 2208 | +0.0048 | 2.95 | 4/4 | 0.743 | 0.743 | avantage |
| EC | o35 | P1 | 2208 | +0.0103 | 2.9 | 4/4 | 0.689 | 0.690 | avantage |
| EC | o25 | P2 | 2208 | +0.0084 | 2.81 | 4/4 | 0.571 | 0.526 | avantage |
| EC | o15 | P2 | 2208 | +0.0068 | 2.78 | 4/4 | 0.785 | 0.785 | avantage |
| EC | o25 | P1 | 2208 | +0.0094 | 2.73 | 4/4 | 0.568 | 0.526 | avantage |
| F1 | 1X2 | F | 1298 | +0.0515 | 9.24 | 4/4 | 0.515 | 0.437 | avantage_robuste |
| F1 | dom | F | 1298 | +0.0427 | 8.87 | 4/4 | 0.621 | 0.563 | avantage_robuste |
| F1 | ext | F | 1298 | +0.0378 | 8.07 | 4/4 | 0.684 | 0.676 | avantage_robuste |
| F1 | 1X2 | P1 | 1298 | +0.0711 | 7.44 | 4/4 | 0.515 | 0.437 | avantage_robuste |
| F1 | 1X2 | P2 | 1298 | +0.0654 | 7.4 | 4/4 | 0.509 | 0.437 | avantage_robuste |
| F1 | dom | P1 | 1298 | +0.0599 | 6.92 | 4/4 | 0.642 | 0.563 | avantage_robuste |
| F1 | dom | P2 | 1298 | +0.0538 | 6.89 | 4/4 | 0.639 | 0.563 | avantage_robuste |
| F1 | ext | P1 | 1298 | +0.0518 | 6.55 | 4/4 | 0.700 | 0.676 | avantage_robuste |
| F1 | ext | P2 | 1298 | +0.0468 | 6.22 | 4/4 | 0.702 | 0.676 | avantage_robuste |
| F1 | o25 | P1 | 1298 | +0.0085 | 2.66 | 4/4 | 0.551 | 0.545 | avantage |
| F1 | o35 | F | 1298 | +0.0041 | 2.29 | 4/4 | 0.686 | 0.686 | avantage |
| F1 | o35 | P1 | 1298 | +0.0087 | 2.18 | 4/4 | 0.684 | 0.686 | avantage |
| F2 | 1X2 | P1 | 1371 | +0.0144 | 2.96 | 4/4 | 0.444 | 0.426 | avantage |
| F2 | ext | P1 | 1371 | +0.0106 | 2.58 | 4/4 | 0.700 | 0.701 | avantage |
| F2 | dom | P2 | 1371 | +0.0115 | 2.51 | 4/4 | 0.596 | 0.574 | avantage |
| F2 | dom | F | 1371 | +0.0084 | 2.37 | 4/4 | 0.577 | 0.574 | avantage |
| F2 | dom | P1 | 1371 | +0.0115 | 2.23 | 4/4 | 0.593 | 0.574 | avantage |
| F2 | 1X2 | P2 | 1371 | +0.0109 | 2.21 | 4/4 | 0.430 | 0.426 | avantage |
| F2 | ext | P2 | 1371 | +0.0069 | 2.07 | 4/4 | 0.701 | 0.701 | avantage |
| FIN | dom | F | 683 | +0.0358 | 5.25 | 4/4 | 0.608 | 0.570 | avantage_robuste |
| FIN | dom | P1 | 683 | +0.0514 | 5.15 | 4/4 | 0.631 | 0.570 | avantage_robuste |
| FIN | 1X2 | P1 | 683 | +0.0594 | 5.07 | 4/4 | 0.527 | 0.430 | avantage_robuste |
| FIN | 1X2 | P2 | 683 | +0.0541 | 4.79 | 4/4 | 0.517 | 0.430 | avantage_robuste |
| FIN | dom | P2 | 683 | +0.0488 | 4.77 | 4/4 | 0.630 | 0.570 | avantage_robuste |
| FIN | ext | P1 | 683 | +0.0446 | 4.28 | 4/4 | 0.676 | 0.665 | avantage_robuste |
| FIN | 1X2 | F | 683 | +0.0308 | 4.17 | 4/4 | 0.501 | 0.430 | avantage_robuste |
| FIN | ext | P2 | 683 | +0.0407 | 3.89 | 4/4 | 0.685 | 0.665 | avantage_robuste |
| FIN | ext | F | 683 | +0.0243 | 3.76 | 4/4 | 0.668 | 0.665 | avantage |
| G1 | dom | F | 949 | +0.0624 | 10.56 | 4/4 | 0.686 | 0.584 | avantage_robuste |
| G1 | 1X2 | P1 | 949 | +0.1301 | 10.16 | 4/4 | 0.532 | 0.416 | avantage_robuste |
| G1 | 1X2 | P2 | 949 | +0.1257 | 9.94 | 4/4 | 0.528 | 0.416 | avantage_robuste |
| G1 | 1X2 | F | 949 | +0.0711 | 9.76 | 4/4 | 0.510 | 0.416 | avantage_robuste |
| G1 | ext | F | 949 | +0.0544 | 9.43 | 4/4 | 0.697 | 0.683 | avantage_robuste |
| G1 | ext | P2 | 949 | +0.0960 | 8.96 | 4/4 | 0.733 | 0.683 | avantage_robuste |
| G1 | ext | P1 | 949 | +0.0962 | 8.86 | 4/4 | 0.739 | 0.683 | avantage_robuste |
| G1 | dom | P1 | 949 | +0.1031 | 8.74 | 4/4 | 0.707 | 0.584 | avantage_robuste |
| G1 | dom | P2 | 949 | +0.0980 | 8.42 | 4/4 | 0.713 | 0.584 | avantage_robuste |
| G1 | nul | P1 | 949 | +0.0108 | 3.09 | 4/4 | 0.733 | 0.733 | avantage |
| G1 | nul | P2 | 949 | +0.0089 | 2.68 | 4/4 | 0.733 | 0.733 | avantage |
| G1 | o25 | P1 | 949 | +0.0063 | 2.01 | 4/4 | 0.550 | 0.508 | avantage |
| I1 | ext | F | 1520 | +0.0559 | 11.02 | 4/4 | 0.699 | 0.683 | avantage_robuste |
| I1 | 1X2 | F | 1520 | +0.0609 | 10.46 | 4/4 | 0.497 | 0.407 | avantage_robuste |
| I1 | 1X2 | P1 | 1520 | +0.0978 | 10.27 | 4/4 | 0.530 | 0.407 | avantage_robuste |
| I1 | ext | P1 | 1520 | +0.0794 | 9.6 | 4/4 | 0.726 | 0.683 | avantage_robuste |
| I1 | dom | F | 1520 | +0.0481 | 9.5 | 4/4 | 0.652 | 0.593 | avantage_robuste |
| I1 | 1X2 | P2 | 1520 | +0.0856 | 9.4 | 4/4 | 0.517 | 0.407 | avantage_robuste |
| I1 | ext | P2 | 1520 | +0.0730 | 9.33 | 4/4 | 0.723 | 0.683 | avantage_robuste |
| I1 | dom | P1 | 1520 | +0.0714 | 8.46 | 4/4 | 0.665 | 0.593 | avantage_robuste |
| I1 | dom | P2 | 1520 | +0.0631 | 7.84 | 4/4 | 0.672 | 0.593 | avantage_robuste |
| I2 | dom | P1 | 1520 | +0.0168 | 3.58 | 4/4 | 0.609 | 0.594 | avantage |
| IRL | 1X2 | P1 | 723 | +0.0692 | 6.45 | 4/4 | 0.492 | 0.434 | avantage_robuste |
| IRL | dom | F | 723 | +0.0361 | 5.83 | 4/4 | 0.624 | 0.566 | avantage_robuste |
| IRL | 1X2 | P2 | 723 | +0.0595 | 5.73 | 4/4 | 0.479 | 0.434 | avantage_robuste |
| IRL | dom | P1 | 723 | +0.0575 | 5.45 | 4/4 | 0.631 | 0.566 | avantage_robuste |
| IRL | ext | P1 | 723 | +0.0463 | 5.31 | 4/4 | 0.719 | 0.711 | avantage_robuste |
| IRL | ext | F | 723 | +0.0294 | 5.16 | 4/4 | 0.717 | 0.711 | avantage_robuste |
| IRL | ext | P2 | 723 | +0.0422 | 5.11 | 4/4 | 0.725 | 0.711 | avantage_robuste |
| IRL | 1X2 | F | 723 | +0.0379 | 5.01 | 4/4 | 0.468 | 0.434 | avantage_robuste |
| IRL | dom | P2 | 723 | +0.0505 | 4.77 | 4/4 | 0.643 | 0.566 | avantage_robuste |
| IRL | nul | P1 | 723 | +0.0064 | 2.14 | 4/4 | 0.723 | 0.723 | avantage |
| IRL | o25 | F | 723 | +0.0069 | 2.08 | 4/4 | 0.573 | 0.539 | avantage |
| JPN | o15 | P1 | 1376 | +0.0088 | 2.73 | 4/4 | 0.706 | 0.706 | avantage |
| JPN | o15 | F | 1376 | +0.0083 | 2.66 | 4/4 | 0.706 | 0.706 | avantage |
| JPN | ext | F | 1376 | +0.0086 | 2.22 | 4/4 | 0.685 | 0.686 | avantage |
| JPN | dom | F | 1376 | +0.0100 | 2.19 | 4/4 | 0.601 | 0.589 | avantage |
| JPN | dom | P1 | 1376 | +0.0144 | 2.17 | 4/4 | 0.608 | 0.589 | avantage |
| MEX | dom | P1 | 1358 | +0.0488 | 8.04 | 4/4 | 0.624 | 0.540 | avantage_robuste |
| MEX | 1X2 | P1 | 1358 | +0.0531 | 7.47 | 4/4 | 0.504 | 0.460 | avantage_robuste |
| MEX | dom | F | 1358 | +0.0274 | 7.34 | 4/4 | 0.577 | 0.540 | avantage_robuste |
| MEX | dom | P2 | 1358 | +0.0393 | 7.13 | 4/4 | 0.603 | 0.540 | avantage_robuste |
| MEX | 1X2 | P2 | 1358 | +0.0445 | 6.67 | 4/4 | 0.497 | 0.460 | avantage_robuste |
| MEX | 1X2 | F | 1358 | +0.0296 | 6.59 | 4/4 | 0.486 | 0.460 | avantage_robuste |
| MEX | ext | F | 1358 | +0.0229 | 6.02 | 4/4 | 0.718 | 0.718 | avantage_robuste |
| MEX | ext | P1 | 1358 | +0.0323 | 5.19 | 4/4 | 0.726 | 0.718 | avantage_robuste |
| MEX | ext | P2 | 1358 | +0.0256 | 4.65 | 4/4 | 0.721 | 0.718 | avantage_robuste |
| MEX | nul | P1 | 1358 | +0.0052 | 2.02 | 4/4 | 0.742 | 0.742 | avantage |
| N1 | ext | F | 1224 | +0.0671 | 11.63 | 4/4 | 0.730 | 0.694 | avantage_robuste |
| N1 | 1X2 | F | 1224 | +0.0809 | 11.56 | 4/4 | 0.542 | 0.444 | avantage_robuste |
| N1 | dom | F | 1224 | +0.0691 | 11.23 | 4/4 | 0.666 | 0.556 | avantage_robuste |
| N1 | 1X2 | P2 | 1224 | +0.1168 | 10.75 | 4/4 | 0.547 | 0.444 | avantage_robuste |
| N1 | 1X2 | P1 | 1224 | +0.1183 | 10.02 | 4/4 | 0.546 | 0.444 | avantage_robuste |
| N1 | ext | P2 | 1224 | +0.0914 | 9.34 | 4/4 | 0.736 | 0.694 | avantage_robuste |
| N1 | dom | P2 | 1224 | +0.0915 | 9.03 | 4/4 | 0.663 | 0.556 | avantage_robuste |
| N1 | ext | P1 | 1224 | +0.0890 | 8.57 | 4/4 | 0.730 | 0.694 | avantage_robuste |
| N1 | dom | P1 | 1224 | +0.0951 | 8.55 | 4/4 | 0.676 | 0.556 | avantage_robuste |
| N1 | o15 | F | 1224 | +0.0047 | 3.41 | 4/4 | 0.829 | 0.829 | avantage |
| NOR | 1X2 | P1 | 966 | +0.0563 | 6.0 | 4/4 | 0.523 | 0.467 | avantage_robuste |
| NOR | ext | P1 | 966 | +0.0467 | 5.94 | 4/4 | 0.691 | 0.680 | avantage_robuste |
| NOR | ext | F | 966 | +0.0335 | 5.69 | 4/4 | 0.679 | 0.680 | avantage_robuste |
| NOR | 1X2 | P2 | 966 | +0.0478 | 5.48 | 4/4 | 0.507 | 0.467 | avantage_robuste |
| NOR | dom | P1 | 966 | +0.0440 | 5.45 | 4/4 | 0.618 | 0.533 | avantage_robuste |
| NOR | dom | F | 966 | +0.0294 | 5.2 | 4/4 | 0.613 | 0.533 | avantage_robuste |
| NOR | 1X2 | F | 966 | +0.0320 | 4.95 | 4/4 | 0.512 | 0.467 | avantage_robuste |
| NOR | dom | P2 | 966 | +0.0382 | 4.85 | 4/4 | 0.635 | 0.533 | avantage_robuste |
| NOR | ext | P2 | 966 | +0.0379 | 4.6 | 4/4 | 0.688 | 0.680 | avantage_robuste |
| NOR | btts | P1 | 966 | +0.0056 | 2.19 | 4/4 | 0.576 | 0.573 | avantage |
| P1 | 1X2 | P1 | 1224 | +0.1464 | 12.18 | 4/4 | 0.559 | 0.442 | avantage_robuste |
| P1 | dom | F | 1224 | +0.0743 | 12.14 | 4/4 | 0.677 | 0.558 | avantage_robuste |
| P1 | ext | F | 1224 | +0.0752 | 11.57 | 4/4 | 0.744 | 0.681 | avantage_robuste |
| P1 | 1X2 | F | 1224 | +0.0929 | 11.5 | 4/4 | 0.550 | 0.442 | avantage_robuste |
| P1 | 1X2 | P2 | 1224 | +0.1414 | 11.21 | 4/4 | 0.551 | 0.442 | avantage_robuste |
| P1 | dom | P1 | 1224 | +0.1135 | 10.95 | 4/4 | 0.685 | 0.558 | avantage_robuste |
| P1 | ext | P1 | 1224 | +0.1137 | 10.61 | 4/4 | 0.770 | 0.681 | avantage_robuste |
| P1 | dom | P2 | 1224 | +0.1056 | 10.59 | 4/4 | 0.688 | 0.558 | avantage_robuste |
| P1 | ext | P2 | 1224 | +0.1114 | 10.35 | 4/4 | 0.766 | 0.681 | avantage_robuste |
| P1 | nul | P2 | 1224 | +0.0175 | 4.89 | 4/4 | 0.761 | 0.761 | avantage_robuste |
| P1 | nul | P1 | 1224 | +0.0167 | 4.53 | 4/4 | 0.761 | 0.761 | avantage_robuste |
| P1 | o15 | P1 | 1224 | +0.0104 | 3.79 | 4/4 | 0.725 | 0.725 | avantage |
| P1 | o25 | P1 | 1224 | +0.0141 | 3.54 | 4/4 | 0.574 | 0.501 | avantage |
| P1 | o25 | P2 | 1224 | +0.0126 | 3.23 | 4/4 | 0.563 | 0.501 | avantage |
| POL | dom | F | 1224 | +0.0180 | 3.71 | 4/4 | 0.596 | 0.561 | avantage |
| POL | dom | P1 | 1224 | +0.0222 | 3.34 | 4/4 | 0.608 | 0.561 | avantage |
| POL | o25 | P1 | 1224 | +0.0073 | 2.64 | 4/4 | 0.545 | 0.512 | avantage |
| POL | 1X2 | F | 1224 | +0.0120 | 2.32 | 4/4 | 0.444 | 0.439 | avantage |
| POL | o35 | P1 | 1224 | +0.0057 | 2.2 | 4/4 | 0.721 | 0.721 | avantage |
| POL | o25 | P2 | 1224 | +0.0056 | 2.07 | 4/4 | 0.540 | 0.512 | avantage |
| POL | o35 | P2 | 1224 | +0.0046 | 2.02 | 4/4 | 0.721 | 0.721 | avantage |
| ROU | dom | F | 1278 | +0.0219 | 4.35 | 4/4 | 0.589 | 0.568 | avantage_robuste |
| ROU | 1X2 | P1 | 1278 | +0.0354 | 4.2 | 4/4 | 0.459 | 0.432 | avantage_robuste |
| ROU | dom | P1 | 1278 | +0.0318 | 4.03 | 4/4 | 0.622 | 0.568 | avantage_robuste |
| ROU | ext | F | 1278 | +0.0146 | 3.33 | 4/4 | 0.718 | 0.721 | avantage |
| ROU | 1X2 | F | 1278 | +0.0199 | 3.26 | 4/4 | 0.454 | 0.432 | avantage |
| ROU | dom | P2 | 1278 | +0.0232 | 2.88 | 4/4 | 0.594 | 0.568 | avantage |
| ROU | 1X2 | P2 | 1278 | +0.0236 | 2.83 | 4/4 | 0.459 | 0.432 | avantage |
| ROU | ext | P1 | 1278 | +0.0200 | 2.82 | 4/4 | 0.714 | 0.721 | avantage |
| ROU | ext | P2 | 1278 | +0.0150 | 2.29 | 4/4 | 0.713 | 0.721 | avantage |
| RUS | dom | F | 968 | +0.0537 | 8.97 | 4/4 | 0.630 | 0.546 | avantage_robuste |
| RUS | 1X2 | P1 | 968 | +0.0790 | 8.54 | 4/4 | 0.540 | 0.454 | avantage_robuste |
| RUS | dom | P1 | 968 | +0.0778 | 8.15 | 4/4 | 0.638 | 0.546 | avantage_robuste |
| RUS | 1X2 | P2 | 968 | +0.0694 | 7.78 | 4/4 | 0.523 | 0.454 | avantage_robuste |
| RUS | dom | P2 | 968 | +0.0681 | 7.7 | 4/4 | 0.647 | 0.546 | avantage_robuste |
| RUS | 1X2 | F | 968 | +0.0447 | 7.22 | 4/4 | 0.520 | 0.454 | avantage_robuste |
| RUS | ext | P1 | 968 | +0.0444 | 5.86 | 4/4 | 0.729 | 0.715 | avantage_robuste |
| RUS | ext | P2 | 968 | +0.0419 | 5.54 | 4/4 | 0.717 | 0.715 | avantage_robuste |
| RUS | ext | F | 968 | +0.0261 | 5.46 | 4/4 | 0.717 | 0.715 | avantage_robuste |
| RUS | nul | P1 | 968 | +0.0058 | 3.89 | 4/4 | 0.739 | 0.739 | avantage_robuste |
| RUS | btts | P1 | 968 | +0.0100 | 2.81 | 4/4 | 0.569 | 0.532 | avantage |
| RUS | nul | P2 | 968 | +0.0048 | 2.65 | 4/4 | 0.739 | 0.739 | avantage |
| RUS | o15 | P1 | 968 | +0.0144 | 2.48 | 4/4 | 0.763 | 0.766 | avantage |
| RUS | btts | P2 | 968 | +0.0061 | 2.1 | 4/4 | 0.549 | 0.532 | avantage |
| RUS | o25 | F | 968 | +0.0052 | 2.04 | 4/4 | 0.550 | 0.509 | avantage |
| SC0 | dom | F | 912 | +0.0650 | 9.57 | 4/4 | 0.641 | 0.533 | avantage_robuste |
| SC0 | 1X2 | F | 912 | +0.0768 | 8.82 | 4/4 | 0.548 | 0.467 | avantage_robuste |
| SC0 | ext | F | 912 | +0.0625 | 8.58 | 4/4 | 0.729 | 0.697 | avantage_robuste |
| SC0 | 1X2 | P1 | 912 | +0.1131 | 7.69 | 4/4 | 0.561 | 0.467 | avantage_robuste |
| SC0 | 1X2 | P2 | 912 | +0.1095 | 7.32 | 4/4 | 0.548 | 0.467 | avantage_robuste |
| SC0 | dom | P1 | 912 | +0.0910 | 7.07 | 4/4 | 0.661 | 0.533 | avantage_robuste |
| SC0 | dom | P2 | 912 | +0.0866 | 6.34 | 4/4 | 0.663 | 0.533 | avantage_robuste |
| SC0 | ext | P1 | 912 | +0.0824 | 6.33 | 4/4 | 0.746 | 0.697 | avantage_robuste |
| SC0 | ext | P2 | 912 | +0.0792 | 6.07 | 4/4 | 0.751 | 0.697 | avantage_robuste |
| SC0 | nul | P2 | 912 | +0.0117 | 3.2 | 4/4 | 0.770 | 0.770 | avantage |
| SC0 | nul | P1 | 912 | +0.0125 | 3.07 | 4/4 | 0.770 | 0.770 | avantage |
| SC0 | o15 | P2 | 912 | +0.0096 | 2.94 | 4/4 | 0.787 | 0.787 | avantage |
| SC0 | o25 | P1 | 912 | +0.0122 | 2.66 | 4/4 | 0.560 | 0.509 | avantage |
| SC0 | o25 | F | 912 | +0.0045 | 2.21 | 4/4 | 0.538 | 0.509 | avantage |
| SC1 | ext | P1 | 720 | +0.0180 | 3.3 | 4/4 | 0.689 | 0.690 | avantage |
| SC1 | 1X2 | P1 | 720 | +0.0273 | 3.25 | 4/4 | 0.444 | 0.407 | avantage |
| SC1 | 1X2 | P2 | 720 | +0.0177 | 3.14 | 4/4 | 0.433 | 0.407 | avantage |
| SC1 | ext | P2 | 720 | +0.0109 | 2.94 | 4/4 | 0.690 | 0.690 | avantage |
| SC1 | dom | P1 | 720 | +0.0238 | 2.79 | 4/4 | 0.607 | 0.593 | avantage |
| SC2 | ext | P1 | 720 | +0.0416 | 3.82 | 4/4 | 0.676 | 0.667 | avantage |
| SP1 | dom | F | 1520 | +0.0468 | 9.8 | 4/4 | 0.634 | 0.537 | avantage_robuste |
| SP1 | dom | P1 | 1520 | +0.0709 | 9.1 | 4/4 | 0.656 | 0.537 | avantage_robuste |
| SP1 | 1X2 | P1 | 1520 | +0.0837 | 9.09 | 4/4 | 0.526 | 0.463 | avantage_robuste |
| SP1 | dom | P2 | 1520 | +0.0647 | 8.86 | 4/4 | 0.649 | 0.537 | avantage_robuste |
| SP1 | 1X2 | F | 1520 | +0.0522 | 8.76 | 4/4 | 0.503 | 0.463 | avantage_robuste |
| SP1 | 1X2 | P2 | 1520 | +0.0778 | 8.69 | 4/4 | 0.527 | 0.463 | avantage_robuste |
| SP1 | ext | F | 1520 | +0.0383 | 8.0 | 4/4 | 0.720 | 0.717 | avantage_robuste |
| SP1 | ext | P1 | 1520 | +0.0547 | 6.92 | 4/4 | 0.722 | 0.717 | avantage_robuste |
| SP1 | ext | P2 | 1520 | +0.0512 | 6.65 | 4/4 | 0.724 | 0.717 | avantage_robuste |
| SP1 | nul | P1 | 1520 | +0.0111 | 4.92 | 4/4 | 0.746 | 0.746 | avantage_robuste |
| SP1 | o15 | P1 | 1520 | +0.0115 | 4.25 | 4/4 | 0.732 | 0.732 | avantage_robuste |
| SP1 | nul | P2 | 1520 | +0.0101 | 4.18 | 4/4 | 0.746 | 0.746 | avantage_robuste |
| SP1 | o35 | P1 | 1520 | +0.0149 | 3.8 | 4/4 | 0.751 | 0.752 | avantage |
| SP1 | o25 | P1 | 1520 | +0.0146 | 3.7 | 4/4 | 0.569 | 0.519 | avantage |
| SP1 | o25 | F | 1520 | +0.0093 | 3.65 | 4/4 | 0.561 | 0.519 | avantage |
| SP1 | o35 | F | 1520 | +0.0061 | 3.51 | 4/4 | 0.752 | 0.752 | avantage |
| SP1 | btts | F | 1520 | +0.0049 | 3.21 | 4/4 | 0.552 | 0.508 | avantage |
| SP1 | o15 | P2 | 1520 | +0.0081 | 3.09 | 4/4 | 0.732 | 0.732 | avantage |
| SP1 | o25 | P2 | 1520 | +0.0112 | 2.7 | 4/4 | 0.560 | 0.519 | avantage |
| SP1 | btts | P1 | 1520 | +0.0063 | 2.58 | 4/4 | 0.542 | 0.508 | avantage |
| SP1 | btts | P2 | 1520 | +0.0039 | 2.22 | 4/4 | 0.547 | 0.508 | avantage |
| SP2 | 1X2 | P1 | 1848 | +0.0146 | 3.39 | 4/4 | 0.455 | 0.455 | avantage |
| SP2 | o15 | P1 | 1848 | +0.0081 | 3.26 | 4/4 | 0.664 | 0.664 | avantage |
| SP2 | dom | P1 | 1848 | +0.0116 | 3.17 | 4/4 | 0.571 | 0.545 | avantage |
| SP2 | o15 | P2 | 1848 | +0.0059 | 2.99 | 4/4 | 0.664 | 0.664 | avantage |
| SP2 | o25 | F | 1848 | +0.0039 | 2.74 | 4/4 | 0.577 | 0.573 | avantage |
| SP2 | dom | P2 | 1848 | +0.0100 | 2.65 | 4/4 | 0.570 | 0.545 | avantage |
| SP2 | 1X2 | P2 | 1848 | +0.0114 | 2.61 | 4/4 | 0.455 | 0.455 | avantage |
| SP2 | o15 | F | 1848 | +0.0025 | 2.39 | 4/4 | 0.664 | 0.664 | avantage |
| SP2 | ext | P2 | 1848 | +0.0066 | 2.21 | 4/4 | 0.746 | 0.746 | avantage |
| SP2 | dom | F | 1848 | +0.0066 | 2.11 | 4/4 | 0.560 | 0.545 | avantage |
| SWE | ext | F | 964 | +0.0279 | 5.28 | 4/4 | 0.659 | 0.662 | avantage_robuste |
| SWE | 1X2 | P1 | 964 | +0.0485 | 4.91 | 4/4 | 0.499 | 0.441 | avantage_robuste |
| SWE | dom | P1 | 964 | +0.0406 | 4.63 | 4/4 | 0.646 | 0.559 | avantage_robuste |
| SWE | ext | P1 | 964 | +0.0377 | 4.48 | 4/4 | 0.664 | 0.662 | avantage_robuste |
| SWE | dom | F | 964 | +0.0231 | 4.39 | 4/4 | 0.614 | 0.559 | avantage_robuste |
| SWE | 1X2 | F | 964 | +0.0254 | 4.15 | 4/4 | 0.486 | 0.441 | avantage_robuste |
| SWE | ext | P2 | 964 | +0.0333 | 4.03 | 4/4 | 0.673 | 0.662 | avantage_robuste |
| SWE | 1X2 | P2 | 964 | +0.0373 | 3.65 | 4/4 | 0.494 | 0.441 | avantage |
| SWE | dom | P2 | 964 | +0.0319 | 3.56 | 4/4 | 0.631 | 0.559 | avantage |
| SWE | o15 | P2 | 964 | +0.0129 | 2.71 | 4/4 | 0.774 | 0.774 | avantage |
| SWE | o15 | F | 964 | +0.0098 | 2.69 | 4/4 | 0.774 | 0.774 | avantage |
| SWZ | dom | P1 | 868 | +0.0229 | 3.36 | 4/4 | 0.604 | 0.558 | avantage |
| SWZ | ext | P2 | 868 | +0.0222 | 3.23 | 4/4 | 0.713 | 0.709 | avantage |
| SWZ | 1X2 | P1 | 868 | +0.0254 | 3.08 | 4/4 | 0.452 | 0.442 | avantage |
| SWZ | 1X2 | P2 | 868 | +0.0243 | 2.86 | 4/4 | 0.456 | 0.442 | avantage |
| SWZ | dom | F | 868 | +0.0136 | 2.66 | 4/4 | 0.596 | 0.558 | avantage |
| SWZ | dom | P2 | 868 | +0.0174 | 2.58 | 4/4 | 0.585 | 0.558 | avantage |
| SWZ | ext | F | 868 | +0.0141 | 2.56 | 4/4 | 0.710 | 0.709 | avantage |
| SWZ | ext | P1 | 868 | +0.0179 | 2.46 | 4/4 | 0.711 | 0.709 | avantage |
| T1 | 1X2 | P1 | 1370 | +0.0847 | 9.35 | 4/4 | 0.529 | 0.454 | avantage_robuste |
| T1 | 1X2 | P2 | 1370 | +0.0780 | 8.75 | 4/4 | 0.525 | 0.454 | avantage_robuste |
| T1 | dom | F | 1370 | +0.0428 | 8.71 | 4/4 | 0.639 | 0.546 | avantage_robuste |
| T1 | dom | P1 | 1370 | +0.0653 | 8.26 | 4/4 | 0.656 | 0.546 | avantage_robuste |
| T1 | ext | P1 | 1370 | +0.0666 | 8.2 | 4/4 | 0.740 | 0.704 | avantage_robuste |
| T1 | dom | P2 | 1370 | +0.0596 | 8.04 | 4/4 | 0.647 | 0.546 | avantage_robuste |
| T1 | 1X2 | F | 1370 | +0.0480 | 8.02 | 4/4 | 0.509 | 0.454 | avantage_robuste |
| T1 | ext | F | 1370 | +0.0413 | 7.85 | 4/4 | 0.716 | 0.704 | avantage_robuste |
| T1 | ext | P2 | 1370 | +0.0615 | 7.31 | 4/4 | 0.740 | 0.704 | avantage_robuste |
| T1 | o35 | P1 | 1370 | +0.0092 | 3.3 | 4/4 | 0.686 | 0.685 | avantage |
| USA | dom | P1 | 2072 | +0.0099 | 3.39 | 4/4 | 0.569 | 0.534 | avantage |
| USA | dom | P2 | 2072 | +0.0073 | 3.3 | 4/4 | 0.557 | 0.534 | avantage |
| USA | o25 | F | 2072 | +0.0046 | 2.9 | 4/4 | 0.583 | 0.584 | avantage |
| USA | o35 | P1 | 2072 | +0.0049 | 2.33 | 4/4 | 0.657 | 0.657 | avantage |

## 3. Marches sans aucun avantage mesure, par competition

- ARG: nul, o25, o35, btts
- AUT: nul, o15, o25, o35, btts
- B1: o25, btts
- BRA: o25, o35, btts
- CHN: nul, o15, btts
- D1: nul, o15, o25, btts
- D2: nul, o15, o25, o35, btts
- DNK: nul, o15, o35, btts
- E0: o35, btts
- E1: nul, o15, o25, o35
- E2: nul, o15, o25, o35, btts
- E3: nul, o15, o25, o35, btts
- EC: btts
- F1: nul, o15, btts
- F2: nul, o15, o25, o35, btts
- FIN: nul, o15, o25, o35, btts
- G1: o15, o35, btts
- I1: nul, o15, o25, o35, btts
- I2: 1X2, nul, ext, o15, o25, o35, btts
- IRL: o15, o35, btts
- JPN: 1X2, nul, o25, o35, btts
- MEX: o15, o25, o35, btts
- N1: nul, o25, o35, btts
- NOR: nul, o15, o25, o35
- P1: o35, btts
- POL: nul, ext, o15, btts
- ROU: nul, o15, o25, o35, btts
- RUS: o35
- SC0: o35, btts
- SC1: nul, o15, o25, o35, btts
- SC2: 1X2, dom, nul, o15, o25, o35, btts
- SC3: 1X2, dom, nul, ext, o15, o25, o35, btts
- SP1: aucun (au moins un marche avec avantage)
- SP2: nul, o35, btts
- SWE: nul, o25, o35, btts
- SWZ: nul, o15, o25, o35, btts
- T1: nul, o15, o25, btts
- USA: 1X2, nul, ext, o15, btts

Limites: archives telles quelles (voir `docs/BILAN_ARCHIVE_FD.md`); formats multi-phases melanges; equipes a libelles variables traitees comme distinctes (aucune fusion); une equipe sans historique retombe sur la moyenne de la competition; pas de cote, pas de ROI. Une frequence stable n'est pas une prevision match par match: seul le gain de perte hors echantillon le mesure.
