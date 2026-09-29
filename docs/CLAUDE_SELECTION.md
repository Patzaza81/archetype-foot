# Instructions — sélection et justification

## Règle du double contrôle — 26/09/2026

Tout nouveau moteur de sélection DOIT appliquer `regles_selection.double_controle` avant de retenir un pari.

Un pari n'est retenu que s'il passe les DEUX contrôles :
1. **Saison, dans les deux sens** : l'équipe à domicile jugée sur ses matchs à domicile ET l'équipe à l'extérieur sur ses matchs à l'extérieur, plus leur saison complète. Une victoire ne se justifie jamais par la seule faiblesse de l'adversaire.
2. **Forme récente** : les 6 derniers matchs de chaque équipe et les 3 derniers au même lieu.

Ajouts du 26/09 au soir (version 1.1.0) :
- Seulement la même compétition : jamais les coupes.
- Pari limite (adversaire exactement au maximum de victoires récentes autorisé) : exclu d'un combiné dès qu'un pari propre est disponible.

Détails : `docs/REGLE_DOUBLE_CONTROLE.md`. Tests : `tests/test_regles_selection.py`.

## Justification des marchés retenus

Cette règle est permanente.

Chaque marché retenu doit correspondre à une justification précise expliquant pourquoi CE marché a été retenu. Elle ne doit jamais être inventée, reconstruite après coup, générique ou choisie parce qu'une statistique disponible « fait joli ».

Chaîne obligatoire :
**critère réel de sélection → marché retenu → justification correspondante**

Deux niveaux à conserver :
1. **Preuve spécifique au marché** : pourquoi le marché est cohérent avec les données réelles.
2. **Cause de sélection finale** : pourquoi ce marché a été retenu parmi les candidats éligibles.

Une preuve EV générique ne remplace jamais une preuve spécifique au marché.

### NO DATA → NO GO

Si un marché n'a pas de preuve spécifique calculable sur les données réelles, il ne doit pas être retenu ni affiché comme choix.

La sélection est souveraine : si un marché est sélectionné, il a déjà satisfait les exigences de sélection. La justification explique le choix ; elle ne constitue pas un filtre supplémentaire.

### Causes de sélection V2.6.9

- **P1** : probabilité modèle la plus élevée parmi les marchés éligibles restants disposant d'une justification spécifique.
- **P2** : EDV le plus élevé parmi les marchés éligibles restants disposant d'une justification spécifique, après retrait de P1.
- **P3** : EDV le plus élevé parmi les marchés restants satisfaisant simultanément cote >= 2,91 et probabilité >= 20 %, avec justification spécifique.

Ces causes doivent être produites par la même logique que la sélection, puis attachées au bloc justification.

Interdit :
**marché retenu → chercher ensuite une statistique quelconque → appeler cela justification.**

Toute modification future de la sélection doit modifier simultanément son contrat de justification et ses tests.

## Couverture des familles

La bibliothèque de justification doit couvrir tous les marchés réellement émis par `moteur_v2_6_9` et reconnus par `branchement_moteur.py` :
- 1X2 : victoire domicile, nul, victoire extérieure ;
- Double chance : 1X, X2, 12 ;
- BTTS : oui, non ;
- Total de buts : over/under sur toutes les lignes réellement produites ;
- Buts d'une équipe : over/under sur les lignes réellement produites ;
- Cage inviolée : domicile, extérieur ;
- Handicap : domicile/extérieur sur les lignes réellement produites.

Aucun type ne doit être justifié par une preuve appartenant à un autre marché. En particulier :
- une victoire sèche ne doit pas être justifiée par une simple série « sans défaite » ;
- un handicap doit être justifié par la capacité historique à couvrir sa propre ligne ;
- une cage inviolée doit être reliée à la capacité à ne pas concéder ;
- 1X2 nul et « pas de nul » doivent reposer sur des signaux opposés ;
- les lignes Over/Under et les buts d'équipe doivent utiliser la ligne exacte du marché.

## Justification visible

Le texte utilisateur doit :
1. nommer naturellement l'équipe ou le contexte ;
2. expliquer le mécanisme sportif soutenant ce marché précis ;
3. conserver les chiffres utiles ;
4. varier l'angle selon la preuve disponible ;
5. éviter les phrases génériques interchangeables ;
6. ne jamais transformer une statistique disponible en justification si elle n'explique pas réellement le marché.

La variation est déterministe et fondée sur la preuve disponible.

## Conditions réelles

- La justification restitue le chemin quantitatif réel ayant conduit au marché retenu.
- Les données H2H sont affichées séparément à titre indicatif. Elles n'influencent ni le choix du marché ni sa justification.
- Pour un total de buts (+/- X,5), la preuve porte sur le total du match et suit les données réellement utilisées par le moteur : buts marqués/encaissés dans le contexte domicile/extérieur, volume total observé, puis probabilité modèle du seuil exact.
- Exemple Stockport–Peterborough du 26/09/2026 : 3 matchs de Stockport à domicile et 3 de Peterborough à l'extérieur ; moyenne 4,00 buts ; Stockport 3,00 marqués / 2,33 encaissés à domicile ; Peterborough 0,33 marqué / 2,33 encaissés à l'extérieur ; lambda domicile 2,67, extérieur 1,33 ; 56,7 % pour +3,5. La justification doit suivre ce chemin, pas seulement afficher une statistique isolée.
