"""Intégrité du dépôt après nettoyage : compilation et import des composants réellement utilisés."""
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
        # On relève les commandes Python actives du workflow, qu'elles soient
        # sur la même ligne que "run:" ou dans un bloc "run: |".
        # Les lignes YAML commentées ne doivent jamais être considérées.
        lignes_actives = [l for l in f.read().splitlines() if not l.lstrip().startswith("#")]
    scripts = sorted(set(
        re.findall(r"^\s*(?:run:\s*)?python\s+([A-Za-z_]\w*)\.py(?:\s+.*)?$", "\n".join(lignes_actives), re.M)
    ))
    scripts_attendus = {
        "moteur_v2_6_9", "pont_moteur", "scraper", "scraper_semaine",
        "precalcul", "verifie_resultats_archetype_model", "evaluation_scores",
        "bilan_shrink_v1", "construit_etat_systeme", "notifie_constat_majeur",
    }
    assert scripts_attendus <= set(scripts), scripts
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


# Parité avec l'environnement du workflow.
PAQUETS_DU_WORKFLOW = {"requests", "bs4", "pandas", "lxml", "playwright", "pytest"}


def _imports_des_tests():
    import ast
    out = []
    for f in sorted(glob.glob(os.path.join(RACINE, "tests", "*.py"))):
        for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
            if isinstance(n, ast.Import):
                out += [(os.path.basename(f), a.name.split(".")[0]) for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                out.append((os.path.basename(f), n.module.split(".")[0]))
    return out


def test_les_tests_n_importent_que_la_bibliotheque_standard_le_depot_et_les_paquets_du_workflow():
    modules_du_depot = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(RACINE, "*.py"))} | {
        d for d in os.listdir(RACINE) if os.path.isdir(os.path.join(RACINE, d))}
    inconnus = sorted({(f, m) for f, m in _imports_des_tests()
                       if m not in sys.stdlib_module_names and m not in modules_du_depot and m not in PAQUETS_DU_WORKFLOW})
    assert not inconnus, f"paquet absent du workflow (le runner ne l'a pas) : {inconnus}"


def test_aucun_test_ne_lit_un_chemin_absolu_de_la_machine_de_developpement():
    fautifs = []
    for f in sorted(glob.glob(os.path.join(RACINE, "tests", "*.py"))):
        if os.path.basename(f) == "test_integrite_du_depot.py":
            continue
        for i, l in enumerate(open(f, encoding="utf-8").read().splitlines(), 1):
            if re.search(r"[\"'](/home/|/tmp/|/mnt/|C:\\\\)", l):
                fautifs.append(f"{os.path.basename(f)}:{i}")
    assert not fautifs, fautifs
