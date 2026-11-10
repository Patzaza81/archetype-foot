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

## Résultats mesurés le 10/11/2026

Base : 2 238 matchs joués du flux commun (28/09 → 10/11), 108 721 paris cotés à 1,26 ou plus.

- **Aucun pari prouvé**, ni sur toute la base, ni dans le test marche avant.
- Test marche avant (chaque jour du 19/10 au 10/11, apprendre sur les jours d'avant, juger le jour) : 255 paris « sous observation », 47,8 % de réussite, cote moyenne 4,29, **20,3 perdus pour 100 misés** (± 14,9). Ce n'est pas un bilan réel.
- Marge du bookmaker mesurée : 7,8 % sur le 1X2 et sur plus/moins de 2,5 buts, 9,0 % sur « les deux marquent ».
- Jouer tous les paris d'une famille perd de 7,7 (les deux marquent) à 20,5 (victoire + les deux marquent) pour 100 misés. Les combinés double chance + total perdent 12,3.
- Les quatre lectures n'ajoutent pas d'information à la cote : erreur de prévision (log-loss) 0,52501 avec la cote seule, 0,52579 avec les quatre moteurs en plus (99 713 lignes jamais vues).
- Autres essais, tous perdants sur des matchs jamais vus : modèle combiné linéaire (3 124 paris, −9,2 %), arbres de décision (10 380 paris, −17,4 %), 151 règles simples famille × tranche de cote × accord des moteurs (les 6 positives à l'apprentissage donnent −4,4 % ensuite, 1 079 paris).

Conclusion : avec ces données (historiques des équipes au même lieu), aucun système ne bat la cote. MEGAPOWER le dit au lieu de forcer une sélection, et se réévalue chaque nuit.

## Tri des moteurs (`python -m megapower.tri_moteurs`)

Mesure sur les paris réellement enregistrés avant le coup d'envoi, matchs terminés. Sortie : `data/megapower/tri_moteurs.json`.
Moteurs désactivés : `config/moteurs_desactives.json` (v2r, v, dc, mixte). Désactivé = plus calculé la nuit, retiré du menu ; code, données et page conservés. Réactiver = retirer la ligne du fichier et remettre le lien dans le menu.
V2, V3 et le Journal perdent aussi, mais restent : les Tickets, l'accueil et le pipeline en dépendent.

## Tests

`tests/test_megapower.py` (cœur, gel avant le coup d'envoi, règlement, page, moteurs désactivés) : données fabriquées, aucune donnée du jour.
