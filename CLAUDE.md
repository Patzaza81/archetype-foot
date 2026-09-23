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
