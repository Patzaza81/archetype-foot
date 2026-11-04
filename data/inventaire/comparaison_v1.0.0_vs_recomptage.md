# Comparaison : inventaire v1.0.0 vs recomptage independant

Recomptage: `recomptage_independant.py` (code separe, lit les CSV directement).

- Colonnes comparees (competition x saison x colonne): 14405
- Colonnes ou v1.0.0 differe du recomptage: 8

## Ecarts v1.0.0 -> recomptage

- G1 | 2526 | BMGMCA | v1.0.0 (valides_joues,valides_total,invalides)=[202, 202, 0] | recomptage=[200, 200, 2]
- G1 | 2526 | BMGMCD | v1.0.0 (valides_joues,valides_total,invalides)=[202, 202, 0] | recomptage=[200, 200, 2]
- G1 | 2526 | BMGMCH | v1.0.0 (valides_joues,valides_total,invalides)=[202, 202, 0] | recomptage=[200, 200, 2]
- SC1 | 2526 | BMGMCA | v1.0.0 (valides_joues,valides_total,invalides)=[180, 180, 0] | recomptage=[179, 179, 1]
- SC1 | 2526 | BMGMCD | v1.0.0 (valides_joues,valides_total,invalides)=[180, 180, 0] | recomptage=[179, 179, 1]
- SC1 | 2526 | BMGMCH | v1.0.0 (valides_joues,valides_total,invalides)=[180, 180, 0] | recomptage=[179, 179, 1]
- SP2 | 2526 | AvgCAHA | v1.0.0 (valides_joues,valides_total,invalides)=[461, 461, 1] | recomptage=[462, 462, 0]
- SP2 | 2526 | AvgCAHH | v1.0.0 (valides_joues,valides_total,invalides)=[461, 461, 1] | recomptage=[462, 462, 0]

Cause: (1) cotes de handicap asiatique (AvgCAHH/AvgCAHA, SP2 2526) comptees invalides en 1.0.0 car < 1; (2) colonnes BMGMCH/D/A (SC1, G1 2526) non reconnues comme cotes en 1.0.0, donc codes `0` comptes valides. Corriges en 1.0.1.

## Changements de statut de capacite v1.0.0 -> v1.0.1: 0


## Etat apres correction

Recomptage independant vs inventaire v1.0.1: voir `recomptage_independant.json` (`nb_ecarts`).
