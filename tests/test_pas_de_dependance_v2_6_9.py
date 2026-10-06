# -*- coding: utf-8 -*-
"""Phase 3 et 20 de la feuille de route : v2.6.10 est autonome, et rien en production n'importe plus moteur_v2_6_9.

Les archives, les tests historiques et l'outil de comparaison sont explicitement exclus de la liste de production.
"""
import os
import re

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPORT_V269 = re.compile(r"^\s*(import\s+moteur_v2_6_9\b|from\s+moteur_v2_6_9\s+import\b)", re.M)

PRODUCTION = [
    "branchement_moteur.py", "pont_moteur.py", "precalcul.py", "construit_etat_systeme.py",
    "journal_rentabilite.py", "enregistre_scores_historique.py", "banc_historique.py", "moteur_v3_pipeline.py",
]


def _lire(chemin):
    with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
        return f.read()


def test_le_paquet_moteur_v2_6_10_n_importe_pas_v2_6_9():
    dossier = os.path.join(RACINE, "moteur_v2_6_10")
    for nom in sorted(os.listdir(dossier)):
        if nom.endswith(".py"):
            assert not IMPORT_V269.search(_lire(os.path.join("moteur_v2_6_10", nom))), f"moteur_v2_6_10/{nom} importe moteur_v2_6_9"


def test_aucun_fichier_de_production_n_importe_v2_6_9():
    fautifs = [f for f in PRODUCTION if os.path.exists(os.path.join(RACINE, f)) and IMPORT_V269.search(_lire(f))]
    assert not fautifs, f"imports de production de moteur_v2_6_9 : {fautifs}"


def test_le_moteur_v2_6_10_s_importe_sans_moteur_v2_6_9_charge():
    import subprocess
    import sys
    code = ("import sys; sys.modules['moteur_v2_6_9'] = None; import moteur_v2_6_10; "
            "assert moteur_v2_6_10.NOM_MOTEUR == 'moteur_v2_6_10'")
    r = subprocess.run([sys.executable, "-c", code], cwd=RACINE, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
