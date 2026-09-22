# -*- coding: utf-8 -*-
"""Miroir, pour shrink_v1, de verifie_resultats_archetype_model.py + calcule_matrice_archetype_model.py.

N'appelle QUE des fonctions déjà génériques sur `repertoire` (archetype_model.learning.resultats.verifier_resultats,
observations.charge_toutes_les_archives) : aucune logique dupliquée, aucun risque de divergence avec le comportement
du moteur principal. Ne touche jamais à archive/ (moteur_v2_6_9) ni à bilan_archetype_model.json -- lit et écrit
exclusivement sous archive_shrink/ et bilan_shrink_v1.json. Ne participe à AUCUNE auto-calibration : calibre_
archetype_model.py ne lit que repertoire="archive" (son défaut) et n'est pas appelé ici.

Usage : python bilan_shrink_v1.py
Placer dans le pipeline nocturne juste après moteur_shrink_pipeline (voir precalcul.py), au même endroit que
verifie_resultats_archetype_model.py + calcule_matrice_archetype_model.py pour le moteur principal."""
import json

from archetype_model.learning import observations, matrice
from archetype_model.learning.resultats import verifier_resultats

REPERTOIRE = "archive_shrink"
FICHIER_BILAN = "bilan_shrink_v1.json"


def construit_bilan(repertoire: str = REPERTOIRE) -> dict:
    records = observations.charge_toutes_les_archives(repertoire)
    obs = observations.construire_observations(records)
    return matrice.construire_matrice(obs)


def main():
    resume_verif = verifier_resultats(REPERTOIRE)
    print(f"[resultats shrink_v1] {resume_verif['resolus']} résolu(s) -- {resume_verif['restants']} en attente -- "
          f"{resume_verif['abandonnes']} NON_RESOLU_DEFINITIF -- {resume_verif['non_reconnus']} marché(s) non reconnu(s).")

    bilan = construit_bilan()
    with open(FICHIER_BILAN, "w", encoding="utf-8") as f:
        json.dump(bilan, f, ensure_ascii=False, indent=2)

    g = bilan["global"]
    roi_txt = f"{g['roi_flat']:.3f}" if g["roi_flat"] is not None else "N/A"
    print(f"[bilan shrink_v1] {g['observations']} observation(s) résolue(s) -- {g['gagnes']} gagnée(s) / "
          f"{g['perdus']} perdue(s) -- ROI flat stake global : {roi_txt}")


if __name__ == "__main__":
    main()
