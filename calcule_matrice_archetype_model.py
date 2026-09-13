"""
calcule_matrice_archetype_model.py -- (13/09/2026) construit le bilan
comportemental d'archetype_model à partir de l'archive résolue.

Lecture seule, aucun scraping, rejouable à volonté -- même esprit que
calcule_roi.py pour l'ancien moteur. Ne modifie jamais archive/ : ce script
lit seulement ce que precalcul.py a archivé et que
verifie_resultats_archetype_model.py a résolu, puis produit un résumé.

Purement descriptif (cahier des charges v2 §6.3) : ce fichier ne pilote
encore aucune décision et ne modifie aucun paramètre -- calibration.py,
qui ferait ce travail, n'existe pas encore.

Usage : python calcule_matrice_archetype_model.py
Conçu pour tourner chaque nuit via GitHub Actions, après
verifie_resultats_archetype_model.py -- sinon le bilan ne refléterait que
les résultats déjà connus lors du cycle précédent.
"""

import json

from archetype_model.learning import observations, matrice

FICHIER_BILAN = "bilan_archetype_model.json"


def construit_bilan(repertoire: str = "archive") -> dict:
    records = observations.charge_toutes_les_archives(repertoire)
    obs = observations.construire_observations(records)
    return matrice.construire_matrice(obs)


def main():
    bilan = construit_bilan()

    with open(FICHIER_BILAN, "w", encoding="utf-8") as f:
        json.dump(bilan, f, ensure_ascii=False, indent=2)

    g = bilan["global"]
    roi_txt = f"{g['roi_flat']:.3f}" if g["roi_flat"] is not None else "N/A"
    print(
        f"[matrice archetype_model] {g['observations']} observation(s) résolue(s) -- "
        f"{g['gagnes']} gagnée(s) / {g['perdus']} perdue(s) -- "
        f"ROI flat stake global : {roi_txt}"
    )


if __name__ == "__main__":
    main()
