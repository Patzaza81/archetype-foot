# Moteur MEGAPOWER (10/11/2026)

Page `pronostics_megapower.html` · code `megapower/` · données `data/megapower/` · étape du pipeline nocturne `python -m megapower.suivi pipeline`.

## But

Réunir Analyse Verdict, Alpha, Omega et Gamma, apprendre sur les résultats connus ce qu'un pari vaut vraiment face à sa cote, et ne proposer que ce qui paie.

## Ce que MEGAPOWER reprend de chaque moteur (`megapower/signaux.py`)

Tous les marchés dépendent du score final. Chaque moteur donne donc une répartition de scores, lue sur les 112 marchés du catalogue d'Analyse Verdict.

| Moteur | Ce qui est repris | Code réutilisé tel quel |
|---|---|---|
| Analyse Verdict | scores de la saison au même lieu (4 matchs minimum), buts attendus, xG, verdict par marché, cote minimale | `verif_pronostic.constat`, `config/verif_pronostic.json` |
| Alpha | séries appariées des 7 derniers matchs au même lieu (scénario des attaques, scénario des défenses) | `alpha_serie.coeur.serie_lieu`, `scenarios` |
| Omega | buts attendus rapprochés de la moyenne, grille Poisson / Dixon-Coles | `moteur_omega.modele`, `moteur_omega/parametres.json` |
| Gamma | tous les croisements attaque × attaque (19 derniers au plus), palier strict avec les défenses, fréquence robuste (une observation retirée) | même calcul que `moteur_omega_v3.coeur`, sur les mêmes séquences |

## Comment il décide (`megapower/coeur.py`)

1. Par famille de marchés (11 familles), il apprend la vraie réussite d'un pari selon sa cote.
2. L'accord des quatre lectures (la majorité voit-elle le pari plus probable que la cote ?) n'entre dans une famille que s'il améliore la prévision de la 2e moitié des matchs à partir de la 1re.
3. Réussite apprise × cote − 1 = gain attendu pour 1 misé.
4. **Prouvé** : la borne basse (95 %) du gain attendu est positive. Seuls ces paris sont proposés.
5. **Sous observation** : gain attendu positif sur toute la période et sur chacune de ses deux moitiés. Gelé et suivi, mais la page dit de ne pas le jouer.
6. Un seul pari par match. « Aucun pari » est une réponse valide.

Aucun seuil posé à la main. Seules valeurs fixées : la cote minimale (règle de Patrick, lue dans `config/verif_pronostic.json`) et le niveau de preuve de 95 %.

## Suivi (`megapower/suivi.py`)

Chaque nuit : réapprentissage sur tous les matchs joués, test « marche avant », gel avant le coup d'envoi (`data/megapower/journal.jsonl`, ajout seul), règlement, page (`data/megapower/pronostics.json`).
Bilan réel = dernier gel avant le coup d'envoi, match terminé. Rien d'autre.

## Résultats mesurés le 11/11/2026

Base : 2 092 matchs joués du flux commun (28/09 → 10/11), 105 046 paris cotés à 1,26 ou plus, cotes relevées avant le coup d'envoi seulement.

- **Aucun pari prouvé**, ni sur toute la base, ni dans le test marche avant.
- Test marche avant (chaque jour du 19/10 au 10/11, apprendre sur les jours d'avant, juger le jour) : 220 paris « sous observation », 44,6 % de réussite, cote moyenne 4,00, **23,5 perdus pour 100 misés** (± 15,6). Ce n'est pas un bilan réel.
- Jouer tous les paris d'une famille perd de 7,7 (les deux marquent) à 21,1 (victoire + les deux marquent) pour 100 misés. Les combinés double chance + total perdent 11,4.
- Marge du bookmaker mesurée le 10/11 (avant nettoyage des cotes) : 7,8 % sur le 1X2 et sur plus/moins de 2,5 buts, 9,0 % sur « les deux marquent ».
- Mesures du 10/11 (avant nettoyage, 2 238 matchs) : les quatre lectures n'ajoutent pas d'information à la cote (log-loss 0,52501 avec la cote seule, 0,52579 avec les quatre moteurs, 99 713 lignes jamais vues) ; modèle combiné linéaire −9,2 % (3 124 paris), arbres de décision −17,4 % (10 380 paris), 151 règles simples : les 6 positives à l'apprentissage donnent −4,4 % ensuite (1 079 paris).

Conclusion : avec les seuls historiques des équipes, aucun système ne bat la cote. MEGAPOWER le dit au lieu de forcer une sélection, et se réévalue chaque nuit.

## Défaut de données corrigé le 11/11/2026 : cotes relevées pendant le match

Dans le flux commun, 45 matchs joués avaient des cotes relevées APRÈS le coup d'envoi et 162 n'avaient pas d'heure de coup d'envoi (exemple du 31/10 : nul coté 1,36 sur un 0-0 en cours).
Une cote relevée pendant le match connaît déjà une partie du résultat. `megapower.donnees.cotes_avant_match` écarte ces matchs. Les autres moteurs lisent le même flux sans ce filtre.

Garde ajoutée le même jour : jamais de pari à une cote plus haute que la plus haute cote déjà gagnée dans la famille (au-delà, le modèle devine).

## Étude du 11/11/2026 : information extérieure (cotes d'autres bookmakers, Football-Data)

Question : quand Betpawa paie plus que le prix « juste » d'un marché de référence, est-ce rentable ? 780 matchs rapprochés (même division, mêmes équipes, même score), 28/09 → 08/11, marchés 1X2, double chance, plus/moins de 2,5 buts.

| Référence | Paris où Betpawa paie plus | Pour 100 misés |
|---|---|---|
| Moyenne des bookmakers, avant-match | 355 | −14,9 (± 18,6) |
| Bet365, avant-match | 396 | −16,7 (± 15,8) |
| Betfair Exchange, avant-match | 355 | −1,4 (± 17,2) ; moitiés : +28,0 puis −21,7 |
| Betfair Exchange, clôture | 699 | +3,5 (± 9,4) ; avantage ≥ 2 % : 388 paris, +12,6 (± 12,8) |

Lecture : la seule piste positive est le prix Betfair de clôture. Mais ce prix n'existe qu'au coup d'envoi, alors que la cote Betpawa de l'archive a été relevée des heures avant : c'est de la triche (information du futur), pas un système jouable.
Pour la rendre jouable, il faut relever le prix Betfair (ou Pinnacle) au même moment que la cote Betpawa, puis geler et suivre. Le dépôt ne collecte pas ces prix en direct aujourd'hui.

## Tri des moteurs (`python -m megapower.tri_moteurs`)

Mesure sur les paris réellement enregistrés avant le coup d'envoi, matchs terminés. Sortie : `data/megapower/tri_moteurs.json`.
Moteurs désactivés : `config/moteurs_desactives.json` (v2r, v, dc, mixte). Désactivé = plus calculé la nuit, retiré du menu ; code, données et page conservés. Réactiver = retirer la ligne du fichier et remettre le lien dans le menu.
V2, V3 et le Journal perdent aussi, mais restent : les Tickets, l'accueil et le pipeline en dépendent.

## Tests

`tests/test_megapower.py` (cœur, gel avant le coup d'envoi, règlement, page, moteurs désactivés) : données fabriquées, aucune donnée du jour.
