# Sélection adaptative multi-source

## Principe

Archetype Foot ne choisit jamais entre V2.6.10 et V3 comme s'il fallait supprimer le moins bon moteur.

Les trois sources sont conservées :

- moteur_v2_6_10
- moteur_v3
- Journal

Le générateur reçoit au maximum les 10 meilleurs candidats de chaque source. Un candidat reste identifiable par sa source.

## Marge de succès

La marge de succès est une mesure conservatrice :

borne basse Wilson à 95 % du taux de réussite historique moins probabilité implicite de la cote.

La probabilité implicite est 1 / cote.

Elle n'est calculée que lorsque l'historique réel est suffisamment renseigné.

La borne basse est utilisée plutôt que le taux de réussite brut afin d'éviter qu'un petit échantillon à 100 % soit présenté comme une preuve forte.

## Niveaux

- PROUVE : au moins 40 observations résolues, marge de succès positive et ROI positif.
- ETABLI : au moins 25 observations résolues, marge de succès positive et ROI positif.
- PROMETTEUR : au moins 10 observations résolues, marge de succès positive et ROI positif.
- OBSERVE : historique réel mais preuve encore insuffisante.
- MODELE_SEUL : pas assez d'observations historiques.

Le Journal conserve ses propres niveaux A_JOUER / A_SURVEILLER et n'est pas transformé artificiellement en moteur.

## Ordre de sélection

Aucun coefficient arbitraire n'est utilisé pour additionner des métriques hétérogènes.

L'ordre déterministe est :

1. preuve empirique ;
2. marge de succès ;
3. marge du modèle ;
4. probabilité du modèle ;
5. EDV ;
6. taille de l'échantillon ;
7. cote et identité du match pour départager les égalités.

## Garde-fous

Un candidat doit :

- avoir une cote BetPawa exploitable entre 1,26 et 3,01 ;
- appartenir à un match identifié sans ambiguïté ;
- conserver sa source et son moteur ;
- ne jamais être dupliqué dans un ticket ;
- ne jamais être ajouté uniquement pour atteindre un nombre de matchs.

## Évolution

data/selection_intelligence.json conserve :

- performance globale V2.6.10 ;
- performance globale V3 ;
- performance par marché ;
- taux de réussite ;
- borne basse à 95 % ;
- ROI ;
- observations résolues.

Le V3 possède une archive indépendante data/v3/historique_selection.json. Ses résultats sont résolus uniquement lorsque le score réel est disponible.

## Tickets

Le générateur publie plusieurs scénarios :

- 2 matchs prudent ;
- 3 matchs prudent ;
- 4 matchs équilibré ;
- 5 matchs équilibré ;
- 8 matchs équilibré ;
- objectif de cote 10, avec nombre de matchs adaptatif de 2 à 12 ;
- opportunités jusqu'à 12 matchs.

Maximum absolu : 12 matchs.

Un ticket dont les critères ne sont pas satisfaits est explicitement marqué AUCUN_TICKET_SOLIDE.

La cote totale est le produit exact des cotes des jambes. La probabilité indépendante éventuelle est seulement informative : elle n'est jamais présentée comme une probabilité jointe garantie.
