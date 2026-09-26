# RÈGLE DU DOUBLE CONTRÔLE — TRÈS IMPORTANTE

> Décidée le 26/09/2026 par Patrick. **Obligatoire pour tout nouveau moteur de sélection.**
> Code : `regles_selection.py` (fonction `double_controle`). Tests : `tests/test_regles_selection.py`.
> Toute IA ou tout développeur qui construit ou modifie un moteur doit la relire avant de commencer.

## Le principe

Un pari n'est retenu que s'il passe **deux contrôles**. S'il en rate un seul, il est écarté.

1. **Contrôle saison, dans les deux sens**
   - l'équipe à domicile est jugée sur **ses matchs à domicile** ;
   - l'équipe à l'extérieur est jugée sur **ses matchs à l'extérieur** ;
   - les deux sont aussi jugées sur leur **saison complète**.
2. **Contrôle forme récente**
   - les **6 derniers matchs** de chaque équipe (tous lieux) ;
   - les **3 derniers matchs au même lieu**.

## Pourquoi (les erreurs qui ont fait naître la règle)

- **Victoire justifiée par la seule faiblesse de l'adversaire** : interdit. Il faut aussi prouver que l'équipe choisie sait gagner (points par match, victoires au même lieu, buts marqués).
- **Moins de 2,5 buts vu d'un seul côté** : Livourne – Pianese était proposé alors que Livourne n'a que 33 % de matchs à moins de 2,5 buts à domicile.
- **Plus de buts vu d'un seul côté** : Holywell – Briton Ferry (+2,5) alors que Briton Ferry n'a que 50 % de matchs à +2,5 à l'extérieur.
- **Moyenne de saison qui cache une chute récente** (cas d'origine) : Real Salt Lake – New England, « les deux équipes marquent ». Sur la saison, Salt Lake marque dans 75 % de ses matchs à domicile. Mais sur ses 6 derniers matchs (0-1, 2-2, 1-2, 0-2, 0-3, 0-2), il n'a marqué que 2 fois et 0 fois lors de ses 2 derniers à domicile.

## Les seuils (version 1.0.0, inchangés en 1.1.0)

« Au lieu » = domicile pour l'équipe qui reçoit, extérieur pour celle qui se déplace.
Buts attendus = moyenne (buts marqués par l'un au lieu, buts encaissés par l'autre à son lieu), des deux côtés.

| Marché | Contrôle saison (deux sens) | Contrôle forme récente |
|---|---|---|
| Victoire (1 ou 2) | Équipe : ≥ 50 % de victoires au lieu, ≥ 1,6 pt/match sur la saison, ≥ 1,4 but marqué/match au lieu. Adversaire : ≤ 34 % de victoires à son lieu, ≥ 1,2 but encaissé/match à son lieu | Équipe : ≥ 3 victoires et ≤ 2 défaites sur 6. Adversaire : ≤ 2 victoires sur 6 |
| Double chance (1X ou X2) | Équipe : invaincue ≥ 70 % au lieu, ≥ 1,45 pt/match. Adversaire : ≤ 40 % de victoires à son lieu. L'équipe marque au moins autant que l'adversaire, chacun à son lieu | Équipe invaincue ≥ 4 sur 6. Adversaire ≤ 3 victoires sur 6 |
| Moins de 2,5 buts | Chaque équipe ≥ 60 % de matchs à -2,5 à son lieu, ≥ 55 % sur la saison, buts attendus ≤ 2,3 | Chaque équipe ≥ 4 matchs sur 6 à -2,5 |
| Moins de 3,5 buts | Chaque équipe ≥ 75 % à -3,5 à son lieu, buts attendus ≤ 2,7 | Chaque équipe ≥ 4 sur 6 à -3,5 |
| Plus de 2,5 buts | Chaque équipe ≥ 60 % à +2,5 à son lieu, ≥ 55 % sur la saison, buts attendus ≥ 2,9 | Chaque équipe ≥ 3 sur 6 et au moins 7 sur 12 au total |
| Plus de 3,5 buts | Chaque équipe ≥ 50 % à +3,5 à son lieu, buts attendus ≥ 3,4 | Chaque équipe ≥ 3 sur 6 et au moins 7 sur 12 au total |
| Les deux équipes marquent | Chaque équipe marque ≥ 70 % et encaisse ≥ 60 % à son lieu, BTTS ≥ 55 % à son lieu, buts attendus ≥ 1,0 de chaque côté | Chaque équipe marque ≥ 4 sur 6 et encaisse ≥ 4 sur 6, et marque ≥ 2 sur ses 3 derniers au même lieu |

**Échantillon minimum** : 3 matchs au lieu pour chaque équipe et 5 matchs récents. En dessous, le pari est écarté.
**Marché non couvert** par ce tableau : écarté tant que ses seuils n'ont pas été écrits ici et testés.

## Ajout de la version 1.1.0 (26/09/2026, soir)

### Seulement la même compétition
- Tous les matchs utilisés sont ceux de la **même compétition ou du même tournoi** que le match analysé. **Jamais de matchs de coupe ni d'une autre compétition.**

### Pari « limite »
- Un pari retenu est **limite** s'il passe **sans aucune marge** : l'adversaire a exactement le nombre maximum de victoires récentes autorisé (2 sur 6 pour une victoire, 3 sur 6 pour une double chance).
- **Dans un combiné, un pari limite est exclu dès qu'un autre pari propre (retenu et non limite) est disponible.** Un pari qu'on signale soi-même comme limite n'a pas sa place dans un ticket où l'on ne tolère aucune erreur.
- Cas d'origine : York – Gillingham, « York ou nul ». Le pari passait les deux contrôles, mais Gillingham avait gagné 3 de ses 6 derniers matchs de championnat, exactement le maximum. Il aurait dû être écarté des combinés.
- Code : `double_controle` renvoie `limite` et `marge_nulle` ; `choisir_pour_combine` applique l'exclusion.

## Règles d'usage

- La règle **filtre** : elle ne remplace ni le modèle de probabilité ni le prix (cote). Un pari doit aussi être cohérent avec la cote BetPawa.
- Les seuils ne se changent **qu'après validation sur des matchs réels terminés**. On met alors à jour ce fichier, `VERSION_REGLE` dans le code et les tests.
- Chaque pari retenu publie les raisons des deux contrôles (lignes ✓), pour respecter la règle maîtresse de CLAUDE.md : critère réel → marché retenu → justification correspondante.
- Données : Football-Data d'abord (saison en cours), Matchendirect en complément. La règle ne fait aucune collecte.

## Tests

`tests/test_regles_selection.py` rejoue 30 cas réels du 26/09/2026 : pour chacune des 5 familles, 3 paris qui doivent passer et 3 qui doivent être écartés, dont le cas Real Salt Lake. Il ajoute des cas construits : victoire refusée quand seul l'adversaire est faible, moins de 2,5 fermé d'un seul côté, échantillon trop petit, marché non couvert.
Version 1.1.0 : le cas réel York (retenu mais limite), 3 adversaires en marge nulle et 3 sans, et l'exclusion des paris limites dans un combiné.
