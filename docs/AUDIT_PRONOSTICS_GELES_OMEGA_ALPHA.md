# Rejeu d'impact Omega et Alpha (01/11/2026)

Question : les historiques tronqués et les auto-références des blocs d'équipe ont-ils changé les pronostics déjà gelés ?
Mesure seule : aucune fiche, cote, journal, règle ni moteur modifié. Aucune correction rétroactive.

## Méthode
- **Fidélité** : chaque gel est rejoué avec le code ET l'archive du commit qui l'a écrit (pas le code actuel). Résultat : **Omega 1 508/1 508 lignes et Alpha 1 073/1 073 reproduites à l'identique** (Alpha : sur les onglets réellement gelés ; le gel du 24/10 03:38 n'avait pas d'onglet « calibrées »). Aucun cas « non reproductible ».
- **Trois lectures, séparées** :
  - **L** (troncature seule) : on ajoute au bloc les matchs du même club et de la même compétition connus d'autres blocs de l'archive, datés avant le match. Club = identifiant de l'URL équipe, jamais le nom. Un score contradictoire entre blocs n'est pas ajouté (3 cas) ;
  - **S** (auto-références seules) : on retire les lignes dont l'adversaire est l'équipe elle-même ;
  - **LS** : les deux.
- **Périmètre** : dernier gel avant le coup d'envoi de chaque match (règle de `bilan_reel.py`). Alpha : seulement les marchés que la page affiche (règle `af-alpha-selection.js`). Bilans : matchs terminés seulement.
- **Classes** : inchangé · probabilité modifiée (Alpha : valeur modifiée) · sélection supprimée · sélection ajoutée · non reproductible · indéterminé. « Indéterminé » = aucun écart visible, mais un bloc sans identifiant de club (ou en conflit) empêche d'affirmer qu'il n'y a pas de troncature.
- Détail match par match et marché par marché : `docs/audit_gel_omega_alpha/resultats/rejeu_{omega,alpha}_detail.json.gz` ; synthèse : `rejeu_synthese.json`. Scripts : `docs/audit_gel_omega_alpha/`.

## Exposition (mesure 1 = perte de matchs, mesure 2 = auto-références)
| | Omega | Alpha |
|---|---|---|
| Matchs avec gel valide (matchs du 20/10 au 04/11 ; dont à venir) | 938 (27/10→04/11) | 1 073 (20/10→04/11) |
| Matchs terminés | 397 (27→31/10) | 807 (20→31/10) |
| Matchs avec ≥ 1 bloc tronqué (mesure 1) | 119 | 329 |
| Matchs avec ≥ 1 auto-référence (mesure 2) | 4 | 7 |
| Matchs avec ≥ 1 bloc sans identifiant de club (non mesurable) | **426 (45 %)** | 9 |
| Matchs avec conflit de scores | 0 | 3 |

Les deux mesures sont indépendantes : 11,6 % des blocs identifiables sont tronqués, mais la part de pronostics touchés est celle du tableau ci-dessous, pas ce pourcentage.

## OMEGA
Matchs terminés avec paris gelés : **189 matchs, 315 paris, 27→31/10/2026** (échantillon petit, 5 jours).

| Lecture | inchangé | prob. modifiée | sélection supprimée | sélection ajoutée | indéterminé |
|---|---|---|---|---|---|
| L (189 matchs) | 120 | 43 | 1 | — | 25 |
| S (189) | 186 | 3 | 0 | — | 0 |
| LS (189) | 119 | 44 | 1 | — | 25 |

- Sur les 938 gels : L = 425 inchangés, 84 probabilités modifiées, 3 sélections supprimées, 8 ajoutées, **418 indéterminés** (blocs sans identifiant de club : Omega retombe sur le bloc brut de l'archive, qui n'a pas d'URL équipe).
- Amplitude : la probabilité du modèle bouge dans 84 matchs, mais la probabilité retenue des paris ne change que pour 16 paris (écart moyen 0,005, max 0,021).
- Bilan (terminés) : gelé 315 paris, 212 gagnés (67,3 %) ; LS 324 paris, 217 gagnés (67,0 %). Retiré : 1 pari perdu. Ajoutés : 5 gagnés, 5 perdus.
- **Lecture** : effet faible sur les probabilités retenues, quasi nul sur les sélections. Mais 45 % des matchs ne sont pas mesurables : « indéterminé » ne veut pas dire « sans effet ».

## ALPHA
Matchs terminés : **807 matchs, 7 067 marchés affichés, 20→31/10/2026** ; 3 892 gagnés (55,1 %).

| Lecture | inchangé | valeur modifiée | sélection supprimée | indéterminé |
|---|---|---|---|---|
| L (807) | 699 | 26 | 78 | 4 |
| S (807) | 805 | 0 | 2 | 0 |
| LS (807) | 697 | 26 | 80 | 4 |

- Sur les 1 073 gels : L = 929 inchangés, 27 modifiées, 108 supprimées, 9 indéterminés.
- Amplitude : 555 marchés changent de valeur (écart moyen 0,09, max 0,31). Les valeurs Alpha sont des paliers : un seul match de plus dans la série suffit à faire bouger un palier, ce qui change le classement et donc l'affichage.
- Bilan (terminés) : gelé 7 067 marchés, 55,1 % ; LS 7 078 marchés, 54,8 %. Retirés : 103 gagnés / 89 perdus. Ajoutés : 90 gagnés / 113 perdus. Écart net −0,3 point : les retraits et ajouts ne vont pas dans un sens.
- **Lecture** : environ 10 % des matchs terminés perdent au moins un marché affiché si l'historique est complété. Effet visible sur la liste affichée, sans biais net sur le taux de réussite.

## Auto-références seules (mesure 2)
Omega : 4 matchs ont une auto-référence dans leurs blocs, mais 10 gels changent (3 terminés) : les auto-références faussent aussi les références de championnat que construit Omega à partir de tous les blocs (effet indirect). Alpha : 7 matchs exposés, 2 sélections supprimées (terminés). Effet réel mais sur très peu de matchs.

## Limites (à lire avant toute conclusion)
1. **Lecture L = reconstruction, pas vérité.** Les lignes ajoutées viennent d'autres blocs de l'archive ; elles ne sont pas confirmées par une source tierce. L'écart mesuré est un ordre de grandeur de ce que vaudrait un historique complet.
2. **Omega non mesurable sur 45 % des matchs** (blocs sans identifiant de club). Alpha : 9 matchs seulement.
3. Cette mesure ne compte que les lignes perdues visibles dans l'archive actuelle. Une ligne perdue partout reste invisible : c'est un minimum.
4. Échantillon court (5 jours Omega, 12 jours Alpha). Bilans chiffrés à titre indicatif ; aucun test de significativité n'est possible ici.
5. Les bilans comparent des paris gelés réels (matchs réels) à des paris rejoués : les paris « ajoutés » ne sont pas des paris que le moteur a publiés.
6. Hors périmètre, non évalués : scraper Europe (`moteur_europe/scraper_matchendirect.py`, même logique que `_memes_equipes`), `h2h_stats.py` (deux tests séparés), lignes ambiguës ignorées (perte de données possible). Le problème n'est pas déclaré entièrement résolu tant que ces zones ne sont pas évaluées.

Aucune décision n'est prise sur cette base : ni correction, ni modification de règle, ni fusion.
