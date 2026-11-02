# Correctif ciblé : côté de l'équipe sur une page d'équipe (01/11/2026, branche `scraper-memes-equipes`, NON fusionnée)

Autorisé par Patrick le 01/11 « sous tests », sur branche dédiée. Fichier protégé `scraper_details.py` : **une seule fonction ajoutée (`_cote_de_la_page`) et une seule boucle modifiée** (lecture des lignes d'une page d'équipe). Contrat de sortie et format inchangés.

## Cause (démontrée)
Sur la page de l'équipe T, une ligne « A - B » était attribuée au premier côté qui « ressemble » à T (`_memes_equipes`, inclusion de sous-chaîne). « Cali » est contenu dans « America Cali » : sur la page d'América Cali, le match Cali – América Cali (identifiant `5y67q7a7…`, 1-0) était lu avec América Cali à domicile, 1-0 : copie exacte de l'enregistrement de Cali, d'où une auto-rencontre et un match à l'envers. Même mécanisme pour Cerro / Cerro Largo.

## Règle
1. Égalité exacte (même normalisation qu'avant) avec **un seul** côté : c'est ce côté.
2. Sinon, ressemblance avec **un seul** côté : ce côté (comportement antérieur).
3. Ressemblance avec les deux côtés, égalité exacte avec les deux, ou aucun côté : **la ligne est ignorée** (pas de donnée plutôt que de fausse donnée).

Aucune nouvelle heuristique de ressemblance. `_memes_equipes` **n'est pas modifiée** : elle est aussi appelée par `corrige_dates_historique.py`, `enregistre_scores_historique.py`, `archetype_model/learning/resultats.py`, `archetype_model/h2h/h2h_stats.py`.

## Preuves
- `tests/test_cote_de_la_page.py` : 23 tests. 6 cas où le côté est décidé (dont América Cali / Cali, Cerro / Cerro Largo, Real Madrid / Castilla), 4 cas ambigus ignorés (Union / Berlin, Atletico / Madrid, aucun côté, égalité des deux côtés), 5 lectures de page complètes, 8 vraies pages capturées. Avec l'ancien code, les 3 tests de lecture qui portent sur le bug **échouent** (América Cali, Cerro, ligne ambiguë) ; les 2 témoins (Cali, match ordinaire) passent avec les deux.
- **Avant/après sur 9 vraies pages équipes** (`diagnostic/pages`, capturées le 24/09) : 55 matchs lus avant, 55 après, **identiques** ; Antigua : 0 avant et après (compétition absente de la page).
- **Suite complète : 2 926 tests passent.**
- Paires de clubs d'un même championnat que `_memes_equipes` confond dans le cache actuel : **4** (América Cali / Cali, Hodd / Odd, Gardens / Tivoli Gardens, Öster / Östersund). Ce sont les cas où le correctif change une lecture.

## Limites et risques résiduels
- Pas de re-scraping possible depuis ce bac à sable (Matchendirect inaccessible) : le « avant/après sur données produites » repose sur 9 pages réelles et des pages construites ; il ne couvre pas les 1 075 équipes du cache. Premier contrôle réel : le prochain passage du pipeline, puis `audit_identites.py` et le contrôle miroir (0 observation non symétrique attendue pour América Cali et Cerro).
- Une ligne ambiguë est **perdue** au lieu d'être fausse : un match de moins dans l'historique de l'équipe. Fréquence réelle inconnue ; les 4 paires ci-dessus la bornent pour le cache actuel.
- **Non corrigé, signalé** : `moteur_europe/scraper_matchendirect.py` contient la même fonction et la même boucle (moteur Europe non modifié) ; `archetype_model/h2h/h2h_stats.py` teste les deux côtés par deux `if` indépendants.
- Les historiques déjà écrits (cache, assemblage, archive) ne sont pas réécrits : l'erreur disparaît au renouvellement du cache, pas des entrées archivées.
