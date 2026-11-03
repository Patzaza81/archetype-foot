# Moteur Europe-Gamma (`moteur_europe_gamma/`, page `pronostics_europe.html`) — 03/11/2026

Remplace le calcul du moteur Europe (ordre de Patrick : « oublie l'ancien moteur »). Méthode Gamma (séquences au même lieu, matrice exhaustive de scénarios, paliers de compatibilité défensive,
fréquence robuste par retrait d'une observation) appliquée à **trois échantillons** mélangés. Autonome (aucun import d'un autre moteur), hors tickets.
Branche `moteur-europe-gamma`, **non fusionnée** (fusion sur l'ordre « Fusionner »). L'ancienne page est conservée sous `pronostics_europe_ancien.html` (non liée) ; `moteur_europe/` et la collecte (`collecte_europe.py`, workflow `europe.yml`) sont inchangés : la collecte alimente toujours `data/europe/entrees_europe.json`.

## Les trois échantillons (décision de Patrick)
| échantillon | contenu (toujours au même lieu, strictement avant le jour du match) | poids de base |
|---|---|---|
| `prec` | saison européenne PRÉCÉDENTE : les 5 derniers matchs | 20 % |
| `champ` | championnat de la saison EN COURS : tous les matchs de la saison | 30 % |
| `eu` | matchs européens de la saison EN COURS : tous | 50 % |

- Fréquence d'un marché = Σ poids × fréquence de l'échantillon. Un échantillon n'entre que si les DEUX équipes y ont au moins 3 matchs (minimum fixé par Patrick pour l'Europe le 13/10) ; un échantillon absent est retiré et les poids restants sont renormalisés (la fiche affiche les poids effectifs). Il faut au moins 2 échantillons exploitables, sinon le match est exclu (« données insuffisantes »).
- Fréquence robuste g = minimum des fréquences obtenues en retirant une observation à la fois (4 séquences × chaque échantillon). Une fréquence n'est pas une probabilité.
- Calcul exact et rapide : la masse d'une paire (attaque A, attaque B) à un palier t se calcule sans énumérer les n⁴ scénarios (voir `coeur.py`) ; un test vérifie l'équivalence avec l'énumération exhaustive.

## Forces en présence
Chaque observation est pesée par la force de l'adversaire affronté = points par match de l'adversaire ÷ moyenne, dans le classement de la MÊME compétition (`cache_classement.json`). Adversaire introuvable (qualifications, saison passée, nom différent) = poids neutre 1, compté et affiché. Aucun coefficient posé à la main.

## Enjeu réel
Le classement sert par ses POINTS, jamais par le rang (le 15e et le 25e peuvent n'avoir qu'un point d'écart) : fiche = écart de points entre les deux équipes + distance en points de chaque équipe aux lignes 1/8e et play-off (points de l'équipe qui occupe le rang 8 / 24) + statut mathématique.
Phase de ligue (36 équipes, 8 matchs ; frontières rang 8 et rang 24, règle UEFA) : pour chaque frontière, l'équipe est « acquise », « perdue » ou « ouverte » selon les points actuels, les points maximum restants et ceux des autres (égalité = ouverte, départages non simulés). Enjeu NUL (les deux frontières décidées) pour une équipe = match exclu avec sa raison. Hors phase de ligue ou classement absent : non calculé. L'enjeu est affiché sur chaque fiche.

## Sélection
Sans calibrage (état actuel) : « aperçu NON calibré » = marché de plus forte fréquence robuste parmi ceux dont la cote est connue et ≥ 1,26, un seul, étiqueté, compté à part dans le bilan (jamais mélangé aux paris calibrés). Avec `parametres.json` (seuils appris par marché, même protocole que Gamma) : règle Gamma (g ≥ seuil, cote ≥ 1,26, jamais deux fois le même événement). « AUCUN MARCHÉ RETENU » est valide.

## Journal et page
`data/europe_gamma/journal.jsonl` (ajout seul, dernier gel avant le coup d'envoi), `data/europe_gamma/pronostics.json`. Étape `python -m moteur_europe_gamma.suivi pipeline` dans `pipeline.yml`. Un contrôle mathématique raté exclut le match et fait échouer l'étape. Bilan = uniquement des matchs réellement gelés avant le coup d'envoi.

## Limites constatées à la livraison (données du 02/11/2026, 151 matchs collectés)
- Échantillons exploitables par match (minimum 3 par équipe) : 0 échantillon : 24 matchs ; 1 : 60 ; 2 : 59 ; 3 : 8. Seuls les matchs à ≥ 2 échantillons sont analysés. L'échantillon Europe en cours (50 %) n'est exploitable que pour 28 matchs : en phase de ligue, une équipe n'a joué que 1 à 3 matchs européens de la saison à chaque lieu (hors qualifications).
- Forces : adversaires résolus dans le classement : championnat ≈ 62 %, Europe en cours ≈ 34 % (le reste = qualifications ou noms non appariés), saison passée 0 % (aucun classement conservé).
- Calibrage : aucun seuil appris (≈ 50 matchs européens joués et évaluables, loin des 30 prédictions par marché exigées). Les paris sont donc des aperçus non calibrés tant que les résultats réels ne s'accumulent pas.
