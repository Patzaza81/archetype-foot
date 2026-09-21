"""Intégrité du dépôt après un nettoyage (21/09/2026).

La suppression de archetype_model/main.py a laissé, sans qu'aucun test ne le voie :
  - archetype_model/backtest/boucle_b.py non importable (`from ..main import SCENARIOS`) ;
  - audit_permanent.py qui ne compilait plus (blocs coupés en plein milieu).
Ces tests détectent cette classe de casse AVANT qu'un run de plusieurs heures ne la découvre.
"""
import glob
import importlib
import os
import pkgutil
import py_compile
import re
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fichiers_python():
    return sorted(f for f in glob.glob(os.path.join(RACINE, "**", "*.py"), recursive=True) if "__pycache__" not in f)


@pytest.mark.parametrize("chemin", _fichiers_python(), ids=lambda p: os.path.relpath(p, RACINE))
def test_tout_fichier_python_compile(chemin, tmp_path):
    py_compile.compile(chemin, doraise=True, cfile=str(tmp_path / "x.pyc"))


def test_tout_module_d_archetype_model_est_importable():
    sys.path.insert(0, RACINE)
    import archetype_model
    casses = []
    for m in pkgutil.walk_packages(archetype_model.__path__, "archetype_model."):
        try:
            importlib.import_module(m.name)
        except Exception as e:
            casses.append(f"{m.name} : {type(e).__name__}: {e}")
    assert not casses, casses


def test_chaque_script_du_workflow_est_importable():
    sys.path.insert(0, RACINE)
    with open(os.path.join(RACINE, ".github", "workflows", "pipeline.yml"), encoding="utf-8") as f:
        # étapes réellement actives : les lignes commentées (« # run: python ... ») sont ignorées
        scripts = sorted(set(re.findall(r"^\s*(?:run:\s*|)python (\w+)\.py", f.read(), re.M)))
    assert {"precalcul", "scraper", "verifie_resultats_archetype_model", "moteur_v2_6_9", "pont_moteur"} <= set(scripts), scripts
    casses = []
    for nom in scripts:
        try:
            importlib.import_module(nom)
        except Exception as e:
            casses.append(f"{nom} : {type(e).__name__}: {e}")
    assert not casses, casses


def test_le_workflow_ne_lance_plus_la_calibration_de_l_ancien_modele():
    with open(os.path.join(RACINE, ".github", "workflows", "pipeline.yml"), encoding="utf-8") as f:
        actif = [l for l in f.read().splitlines() if not l.lstrip().startswith("#")]
    assert not any("calibre_archetype_model.py" in l for l in actif)
