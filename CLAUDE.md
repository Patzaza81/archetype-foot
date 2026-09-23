# RÈGLE MAÎTRESSE — JUSTIFICATION DES MARCHÉS RETENUS

Cette règle est permanente et ne doit jamais être oubliée, simplifiée ou contournée par Claude ou un autre agent.

## Règle absolue

**Chaque marché retenu doit correspondre à une justification précise qui explique pourquoi CE marché a été retenu.**

La justification ne doit jamais être inventée, reconstruite après coup, générique ou choisie parce qu'une statistique disponible « fait joli ».

La chaîne obligatoire est :

**critère réel de sélection → marché retenu → justification correspondante**

Il faut pouvoir remonter du marché publié au critère exact qui a imposé son choix.

## Deux niveaux à conserver

1. **Preuve spécifique au marché** : elle explique pourquoi le marché lui-même est cohérent avec les données réelles.
2. **Cause de sélection finale** : elle explique pourquoi ce marché précis a été retenu parmi les candidats éligibles.

Les deux doivent rester traçables. Une preuve EV générique ne remplace jamais une preuve spécifique au marché.

## Contrat NO DATA → NO GO

Si un marché n'a pas de preuve spécifique calculable sur les données réelles, il ne doit pas être retenu ni affiché comme choix.

La sélection est souveraine : si un marché est sélectionné, cela signifie qu'il a déjà satisfait toutes les exigences de sélection. La justification ne constitue jamais un filtre supplémentaire et son absence ne peut jamais annuler rétroactivement un marché retenu. La justification doit simplement expliquer le choix à partir des éléments réellement disponibles.

## Cause de sélection actuelle du moteur V2.6.9

- **P1** : probabilité modèle la plus élevée parmi les marchés éligibles restants disposant d'une justification spécifique.
- **P2** : EDV le plus élevé parmi les marchés éligibles restants disposant d'une justification spécifique, après retrait de P1.
- **P3** : EDV le plus élevé parmi les marchés restants satisfaisant simultanément cote >= 2,91 et probabilité >= 20 %, avec justification spécifique.

Ces causes doivent être produites par la même logique que la sélection, puis attachées au bloc justification du marché retenu.

## Interdiction

Ne jamais faire :

**marché retenu → chercher ensuite une statistique quelconque → appeler cela justification.**

Faire uniquement :

**critère ayant réellement retenu le marché → justification exacte de ce critère et du marché.**

Toute modification future de la sélection doit donc modifier simultanément son contrat de justification et ses tests.


## Couverture obligatoire des familles de marchés

La bibliothèque de justification doit couvrir tous les marchés réellement émis par moteur_v2_6_9 et reconnus par branchement_moteur.py :

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


## Règle maîtresse — justification en conditions réelles

- La justification doit restituer le chemin quantitatif réel ayant conduit au marché retenu. Elle ne doit jamais chercher après coup une statistique simplement compatible avec le marché.
- Les données H2H sont affichées séparément à titre indicatif. Elles n'influencent ni le choix du marché ni sa justification. Une justification ne doit jamais devenir disponible uniquement grâce au H2H.
- Pour un total de buts (+/- X,5), la preuve doit porter sur le **total du match** et suivre les données réellement utilisées par le moteur : buts marqués/encaissés dans le contexte domicile/extérieur, volume total observé, puis probabilité modèle du seuil exact.
- Exemple réel Stockport–Peterborough du 26/09/2026 : le moteur utilise 3 matchs de Stockport à domicile et 3 matchs de Peterborough à l'extérieur. Ces six matchs produisent 4,00 buts en moyenne. Les moyennes de contexte sont Stockport 3,00 marqués / 2,33 encaissés à domicile et Peterborough 0,33 marqué / 2,33 encaissés à l'extérieur. Le moteur construit alors λ domicile = 2,67 et λ extérieur = 1,33, soit 4,00 buts attendus, puis 56,7 % pour +3,5. La justification doit suivre ce chemin, pas seulement afficher « 2,33 buts encaissés ».
- Le texte visible doit rester naturel : expliquer pourquoi le seuil précis est soutenu, avec les données utiles et la probabilité du modèle, sans jargon interne inutile.
