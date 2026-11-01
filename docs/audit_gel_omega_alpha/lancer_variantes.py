"""Construit les variantes (variantes.py) pour chaque commit de gel puis rejoue chaque gel sous L, S et LS (pilote.py). Lecture seule.
Usage : python lancer_variantes.py <dossier_travail> <union.pkl>"""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

W = Path(sys.argv[1]); UNION = sys.argv[2]; ICI = Path(__file__).parent
commits = json.load(open(W / "commits.json"))


def construire(c):
    if not (W / f"t_{c}" / "info_blocs.json").exists():
        p = subprocess.run([sys.executable, str(ICI / "variantes.py"), str(W / f"t_{c}"), UNION], capture_output=True, text=True)
        if p.returncode: raise SystemExit(f"variantes {c}: {p.stderr[-300:]}")


def rejouer(t):
    (cle, c), v = t
    moteur, ts = cle.split("|")
    sortie = W / f"v_{moteur}_{ts.replace(':', '')}_{v}.json"
    if sortie.exists(): return
    p = subprocess.run([sys.executable, str(ICI / "pilote.py"), str(W / f"t_{c}"), moteur, ts, str(W / f"t_{c}/var_{v}/data/archive_test"), str(sortie)], capture_output=True, text=True)
    if p.returncode: print("ERREUR", cle, v, p.stderr[-200:], flush=True)


with ThreadPoolExecutor(2) as ex:
    list(ex.map(construire, sorted(set(commits.values()))))
    print("variantes construites", flush=True)
    list(ex.map(rejouer, [(kv, v) for kv in commits.items() for v in ("L", "S", "LS")]))
print("TERMINÉ", flush=True)
