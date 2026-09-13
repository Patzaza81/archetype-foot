"""
verifie_resultats_archetype_model.py -- (13/09/2026) point d'entrée du
pipeline nocturne pour la vérification des résultats réels d'archetype_model.

Existe en fichier séparé à la racine, plutôt que d'appeler directement
archetype_model/learning/resultats.py comme script : ce module utilise des
imports absolus au dépôt (`from scraper import ...`, `from run_pipeline
import ...`) qui supposent que la racine du dépôt est sur sys.path -- déjà
le cas ici puisque ce fichier est lui-même à la racine.

Usage : python verifie_resultats_archetype_model.py
Conçu pour tourner chaque nuit via GitHub Actions, après
verification_resultats.py (ancien moteur) et calcule_roi.py -- l'ordre
archivage -> vérification -> analyse est celui défini au cahier des
charges v2 §7.
"""

from archetype_model.learning.resultats import verifier_resultats


def main():
    resume = verifier_resultats()
    print(
        f"[resultats archetype_model] {resume['resolus']} résolu(s) -- "
        f"{resume['restants']} encore en attente après ce passage -- "
        f"{resume['abandonnes']} marqué(s) NON_RESOLU_DEFINITIF -- "
        f"{resume['non_reconnus']} marché(s) non reconnu(s) "
        "(alerte, voir stderr)."
    )


if __name__ == "__main__":
    main()
