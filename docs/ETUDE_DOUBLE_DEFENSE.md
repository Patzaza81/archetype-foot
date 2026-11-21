# Onglet « Étude » d'Analyse Verdict (21/11/2026)

Page `pronostics_verif.html`, code `verif_etude.py` (étude + marquage), `verif_pronostic.py` (intégration), `archetype_verif.js` (affichage, filtres), table versionnée `data/verif_pronostics/etude_regles.json`. Tests : `tests/test_verif_etude.py`.

## Condition (règle de Patrick)
Une équipe marque **au moins le double** des buts par match de son adversaire **et** en encaisse **moins** (moyennes de la saison avant le match ; 4 matchs minimum au même lieu pour chaque équipe). La comparaison se fait sur les valeurs exactes, jamais sur les valeurs arrondies de la page (11/7 = 2 × 11/14 passe, 1,571 contre 0,786 arrondis ne passerait pas).

## Trois catégories d'écart de défense
Écart = buts encaissés par l'adversaire − buts encaissés par l'équipe. **Mince** : de 0 à 0,8 but (0,8 : décision de Patrick). **Moyen** : de 0,8 au seuil « grand ». **Grand** : au-delà. Le seuil « grand » est la médiane des écarts ≥ 0,8 dans l'étude (valeur dans `etude_regles.json`).

## Étude et sélection
- Matchs déjà joués uniquement (`data/bloc_saisons`), moyennes calculées AVANT chaque match (aucune fuite).
- Case = lieu de l'équipe (domicile / extérieur) × catégorie d'écart. Pour chaque case et chaque marché étudié (victoire, double chance, l'équipe marque +0,5 / +1,5, double chance + plus de 1,5 buts, double chance + moins de 4,5 buts), le taux de réussite.
- **Un marché n'est retenu que si son taux dépasse 70 % dans l'étude** (seuil de Patrick). Les marchés non étudiés ne sont jamais affichés (NO DATA → NO GO).
- Sur la page : seuls les paris qui passent déjà les filtres d'Analyse Verdict (cote ≥ 1,26, 4 matchs au même lieu, verdict « Tient » ou « Tient avec réserve ») et qui sont retenus par l'étude portent la marque `etude` ; ils sont classés par taux de l'étude, du plus au moins réussi.
- Régénérer la table : `python verif_etude.py` (relit `data/bloc_saisons`, réécrit `etude_regles.json`). Aucune valeur n'est posée à la main, sauf 0,8, 70 % et les 4 matchs, qui viennent de Patrick.

## Mesure réelle
La commande `python verif_pronostic.py page` gèle aussi la sélection « etude » de chaque match à venir (journal des sélections, empreintes chaînées) ; `bilan_selections` la mesure sur les matchs terminés (ligne « Onglet Étude » du tableau de la page). Le taux de l'étude est un taux passé, pas une probabilité.

## Limites connues
- Le bloc d'étude vient de Football-Data (37 championnats) : certains championnats de la page (féminin, Indonésie, Slovaquie, Bosnie, Serbie, Colombie, Rép. tchèque) n'y sont pas ; la règle y est appliquée sans y avoir été mesurée.
- Cases « moyen » et « grand » : 47 à 69 cas, soit environ ± 10 points ; le classement entre elles n'est pas fiable.
- Saison 2024-25 absente du dépôt (à ajouter via `archive_football_data.py`, réseau requis).
