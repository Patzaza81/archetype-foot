# Rubrique Corners / Cartons (11/10/2026)

Module `corners_cartons.py` → `data/corners_cartons.json` (page `corners_cartons.html` / `.js`) et
`data/corners_cartons_archive.json` (prévision de chaque match + règlement). Séparée des moteurs V2 et V3, qui ne sont pas
modifiés. Étape « Produire les probabilités corners et cartons » de `pipeline.yml` (`continue-on-error`).
Tests : `tests/test_corners_cartons.py`. Backtest reproductible : `python evaluation/backtest_corners_cartons.py`.

## Formule

```
attendu_dom = L_dom + c × (L_dom × attaque_dom × défense_ext − L_dom)
attendu_ext = L_ext + c × (L_ext × attaque_ext × défense_dom − L_ext)
```

- `L` : moyenne de la division (domicile / extérieur), tirée vers la moyenne de toutes les divisions (20 matchs fictifs).
- `attaque` / `défense` : moyenne sur TOUS les matchs de l'équipe du rapport « obtenu / moyenne du lieu », tirée vers 1 avec
  `k` matchs fictifs.
- Total et lignes par équipe : binomiale négative (variance = μ + α·μ²) ; Poisson si α = 0.
- Carton rouge : P(au moins un) = 1 − exp(−rouges par match de la division), plancher 0,02, **sans effet d'équipe**.
- « Cartons » = jaunes + rouges (un rouge compte pour un carton).

| Genre | k | c | α total | α par équipe | Lignes total | Lignes par équipe |
|---|---|---|---|---|---|---|
| Corners | 40 | 0,7 | 0,021 | 0,115 | 7,5 à 12,5 | 3,5 à 6,5 |
| Cartons | 40 | 1,0 | 0,0163 | 0 (Poisson) | 2,5 à 6,5 | 0,5 à 2,5 |

## Preuves (backtest chronologique sans fuite, saison 2025-26, 7 093 prévisions, 21 divisions)

Perte logarithmique sur les 60 % de matchs les plus récents (plus bas = mieux) :

| | Moyenne de la division seule | Formule retenue |
|---|---|---|
| Corners (lignes total 8,5 à 11,5) | 0,6526 | **0,6496** |
| Cartons (lignes total 2,5 à 5,5) | 0,6018 | **0,5965** |

- La loi en Poisson seule est moins bonne que la binomiale négative sur les corners par équipe (surdispersion 0,115).
- Sans shrinkage (k = 0) la formule fait **pire** que la seule moyenne de la division ; k = 40 et la compression c
  (0,7 corners) corrigent la surconfiance observée dans les queues de la calibration.
- Carton rouge : aucun gain avec un effet d'équipe (perte 0,4421 → 0,4419 au mieux) : taux de la division seul.
- L'arbitre améliore les cartons (0,5965 → 0,5926) mais **n'est pas utilisable** : il n'est ni dans le fichier normalisé ni
  connu au moment du pré-calcul. Il ne change rien aux corners.

## Limites à ne pas oublier

- L'ajustement par équipe n'améliore que de 0,003 (corners) à 0,005 (cartons) : ces marchés dépendent surtout du
  championnat. Entre 3 et 12 matchs joués par équipe, la formule ne bat pas clairement la moyenne de la division.
- **Aucune cote corners / cartons n'est relevée** (chantier C) : le module produit des probabilités, jamais d'EV, de value
  bet ni de pari retenu. Ne pas brancher ces marchés au générateur de tickets avant d'avoir (1) des cotes BetPawa,
  (2) un bilan réglé suffisant (`bilan` de `data/corners_cartons.json`), (3) la comparaison au marché.
- Seules les divisions dont Football-Data publie corners ET cartons sont couvertes (les 22 divisions principales). Les
  championnats supplémentaires (Argentine, Brésil, USA, Chine, Scandinavie…) n'ont pas ces champs : matchs écartés avec la
  raison `corners_cartons_non_publies_pour_ce_championnat`. Un match Matchendirect n'apporte jamais de corners ni de
  cartons (règle du 24/09).
- Saison en cours seule (jamais la précédente). Un match avec une équipe < 3 matchs publiés est écarté.

## Anti-fuite et règlement

- La prévision d'un match n'est jamais recalculée une fois que Football-Data l'a publié (`deja_joue_dans_football_data`).
- Une prévision réglée n'est plus jamais modifiée. Règlement automatique dès que Football-Data publie le score (1 à 4 jours
  de retard), match retrouvé par division + noms Football-Data + date à ± 1 jour.
- `bilan` : taux annoncé contre taux observé, perte log, comparée à la moyenne de la division seule, par famille. Une
  famille ne se juge qu'avec un échantillon suffisant (comme V2/V3 : 150-200 lignes propres).
- Rapprochement des noms : pays + compétition exacts (`data/correspondances/equipes.json`), jamais le nom de ligue seul.
