# Instructions — sélection et justification

## Règle du double contrôle — 26/09/2026

Tout nouveau moteur de sélection DOIT appliquer `regles_selection.double_controle` avant de retenir un pari.

Un pari n'est retenu que s'il passe les DEUX contrôles :
1. **Saison, dans les deux sens** : l'équipe à domicile jugée sur ses matchs à domicile ET l'équipe à l'extérieur sur ses matchs à l'extérieur, plus leur saison complète. Une victoire ne se justifie jamais par la seule faiblesse de l'adversaire.
2. **Forme récente** : les 6 derniers matchs de chaque équipe et les 3 derniers au même lieu.

Ajouts du 26/09 au soir (version 1.1.0) :
- **Seulement la même compétition** : les matchs utilisés sont ceux de la même compétition ou du même tournoi, jamais les coupes.
- **Pari limite** (adversaire exactement au maximum de victoires récentes autorisé, cas York – Gillingham) : exclu d'un combiné dès qu'un pari propre est disponible.

Détails, seuils et origine (cas Real Salt Lake – New England) : `docs/REGLE_DOUBLE_CONTROLE.md`. Tests : `tests/test_regles_selection.py`.

## Règle maîtresse — justification des marchés retenus

Cette règle est permanente et ne doit jamais être oubliée, simplifiée ou contournée.

Chaque marché retenu doit correspondre à une justification précise expliquant pourquoi CE marché a été retenu. Elle ne doit jamais être inventée, reconstruite après coup, générique ou choisie parce qu'une statistique disponible « fait joli ».

Chaîne obligatoire :
**critère réel de sélection → marché retenu → justification correspondante**

Il faut pouvoir remonter du marché publié au critère exact qui a imposé son choix.

Deux niveaux à conserver :
1. **Preuve spécifique au marché** : pourquoi le marché lui-même est cohérent avec les données réelles.
2. **Cause de sélection finale** : pourquoi ce marché précis a été retenu parmi les candidats éligibles.

Les deux doivent rester traçables. Une preuve EV générique ne remplace jamais une preuve spécifique au marché.

### NO DATA → NO GO

Si un marché n'a pas de preuve spécifique calculable sur les données réelles, il ne doit pas être retenu ni affiché comme choix.

La sélection est souveraine : si un marché est sélectionné, cela signifie qu'il a déjà satisfait toutes les exigences de sélection. La justification explique le choix ; elle ne constitue jamais un filtre supplémentaire et son absence ne peut jamais annuler rétroactivement un marché retenu.

### Causes de sélection V2.6.9

- **P1** : probabilité modèle la plus élevée parmi les marchés éligibles restants disposant d'une justification spécifique.
- **P2** : EDV le plus élevé parmi les marchés éligibles restants disposant d'une justification spécifique, après retrait de P1.
- **P3** : EDV le plus élevé parmi les marchés restants satisfaisant simultanément cote >= 2,91 et probabilité >= 20 %, avec justification spécifique.

Ces causes doivent être produites par la même logique que la sélection, puis attachées au bloc justification.

Interdit :
**marché retenu → chercher ensuite une statistique quelconque → appeler cela justification.**

Faire uniquement :
**critère ayant réellement retenu le marché → justification exacte de ce critère et du marché.**

Toute modification future de la sélection doit donc modifier simultanément son contrat de justification et ses tests.

## Couverture obligatoire des familles de marchés

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
- une cage inviolée doit être reliée à la capacité à ne pas concéder, pas simplement à une bonne forme ;
- 1X2 nul et « pas de nul » doivent reposer sur des signaux opposés ;
- les lignes Over/Under et les buts d'équipe doivent utiliser la ligne exacte du marché.

## Style de la justification visible

Le texte destiné à l'utilisateur ne doit pas ressembler à un journal de programme. Les noms techniques (EDV, market_family, selection_criterion, preuve_specifique_disponible, etc.) restent des données internes et ne doivent pas apparaître dans le discours utilisateur.

La formulation doit :
1. nommer naturellement l'équipe ou le contexte ;
2. expliquer le mécanisme sportif qui soutient ce marché précis ;
3. conserver les chiffres utiles ;
4. varier l'angle selon la preuve disponible : forme à domicile/extérieur, faiblesse adverse, rythme de buts, historique direct, capacité à couvrir une ligne, solidité défensive, etc. ;
5. éviter les phrases génériques interchangeables entre plusieurs marchés ;
6. ne jamais transformer une statistique disponible en justification si cette statistique n'explique pas réellement le marché retenu.

La variation doit être déterministe et fondée sur la preuve disponible, pas aléatoire : deux marchés opposés ne doivent jamais recevoir la même phrase simplement parce que le système dispose des mêmes chiffres.

## Conditions réelles

- La justification restitue le chemin quantitatif réel ayant conduit au marché retenu.
- Les données H2H sont affichées séparément à titre indicatif. Elles n'influencent ni le choix du marché ni sa justification. Une justification ne doit jamais devenir disponible uniquement grâce au H2H.
- Pour un total de buts (+/- X,5), la preuve porte sur le **total du match** et suit les données réellement utilisées par le moteur : buts marqués/encaissés dans le contexte domicile/extérieur, volume total observé, puis probabilité modèle du seuil exact.
- Exemple réel Stockport–Peterborough du 26/09/2026 : 3 matchs de Stockport à domicile et 3 de Peterborough à l'extérieur ; moyenne 4,00 buts ; Stockport 3,00 marqués / 2,33 encaissés à domicile ; Peterborough 0,33 marqué / 2,33 encaissés à l'extérieur ; lambda domicile 2,67, extérieur 1,33 ; 56,7 % pour +3,5. La justification doit suivre ce chemin, pas seulement afficher « 2,33 buts encaissés ».
- Le texte visible doit rester naturel : expliquer pourquoi le seuil précis est soutenu, avec les données utiles et la probabilité du modèle, sans jargon interne inutile.

## Tickets : marge d'erreur et rentabilité — 07/10/2026

Les deux moteurs (V2.6.10, V3) et le Journal fournissent chacun leurs paris au générateur de tickets (`generateur_tickets.py`). Cette règle n'en change ni la sélection ni l'éligibilité : elle ajoute seulement une analyse à chaque ticket (`analyse` dans `data/tickets.json`, calculée aussi côté site par `tickets_analyse.js`).

Pour chaque format de mise (paris simples, système k sur n avec k de n-3 à n, combiné) :
- **Gain espéré** = e_k(probabilité × cote) / C(n, k) − 1 (mise répartie à parts égales sur les C(n, k) combinés).
- **Bonnes requises** : plus petit nombre de paris justes qui rembourse la mise, estimé à la cote moyenne géométrique ; **erreurs tolérées** = n − bonnes requises.
- **Chance de l'atteindre** : probabilité d'avoir au moins ce nombre de paris justes (loi du nombre de succès, paris supposés indépendants).
- **Format le plus régulier** : parmi les formats à gain espéré positif, celui qui a le plus de chances d'atteindre ses bonnes requises. Le gain espéré maximal est presque toujours le combiné, qui est aussi le plus risqué.

Limites à ne pas masquer : indépendance supposée, probabilités des moteurs non recalibrées, et tolérer des erreurs ne rend pas un ticket rentable (ex. 4 justes sur 6 ne suffit pas pour un système 4 sur 6 à cote 1,50). Tests : `tests/test_generateur_tickets.py` (la partie Python et la partie JavaScript doivent donner le même calcul).
