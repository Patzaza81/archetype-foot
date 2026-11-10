"""Garde-fou (10/11/2026) : un test qui lit data/ (réécrit chaque nuit par les workflows) fait échouer les autotests du pipeline dès qu'un jour est
vide ou différent, sans qu'aucun code n'ait changé (échecs répétés du 05, 06, 08, 09 et 10/11). Tout nouveau test qui lit data/ doit :
  - soit porter @pytest.mark.donnees_du_jour (non bloquant dans le pipeline, erreur visible) ;
  - soit lire un fichier figé de tests/fixtures/ ;
  - soit être ajouté ci-dessous APRÈS avoir été vérifié sur un jour vide (tickets vides, aucun match) : c'est un contrôle de structure, pas de contenu."""
import ast, glob, os, re

RACINE = os.path.join(os.path.dirname(__file__), "..")
LECTURE_DATA = re.compile(r"""["']data["']\s*/|["']data/|["']data["']\s*,|\bdata/""")
# Tests existants qui lisent data/ et ont été vérifiés sur les états des données du 03 au 10/11/2026 (dont un jour sans ticket) : invariants de structure.
AUTORISES = {l.strip() for l in open(os.path.join(os.path.dirname(__file__), "donnees_du_jour_autorises.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")}

def _tests_lisant_data():
    out = {}
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "test_*.py"))):
        if os.path.basename(f) == os.path.basename(__file__): continue
        src = open(f, encoding="utf-8").read(); arbre = ast.parse(src)
        for n in ast.walk(arbre):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
                seg = ast.get_source_segment(src, n) or ""
                if "fixtures" in seg and "data" not in seg.replace("fixtures", ""): continue
                if LECTURE_DATA.search(seg):
                    marque = any("donnees_du_jour" in ast.unparse(d) for d in n.decorator_list)
                    out[f"{os.path.basename(f)}::{n.name}"] = marque
    return out

def test_tout_test_qui_lit_data_est_marque_ou_autorise():
    inconnus = sorted(k for k, marque in _tests_lisant_data().items() if not marque and k not in AUTORISES)
    assert not inconnus, ("Ces tests lisent data/ (réécrit chaque nuit) sans @pytest.mark.donnees_du_jour : " + ", ".join(inconnus) +
                          " — marquez-les ou lisez un fichier figé de tests/fixtures/ (voir tests/test_garde_donnees_du_jour.py)")

def test_le_pipeline_separe_code_et_donnees_du_jour():
    y = open(os.path.join(RACINE, ".github", "workflows", "pipeline.yml"), encoding="utf-8").read()
    assert 'pytest tests -q -m "not donnees_du_jour"' in y and "pytest tests -q -m donnees_du_jour" in y and "--deselect" not in y
