"""Mesure des sources de secours (`python -m sources_calendrier.mesure`) : sur les jours que Matchendirect couvre en ce moment, combien de ses matchs chaque source
de secours retrouve-t-elle — en tout, et parmi les matchs qui ont des cotes Betpawa (les seuls utiles au système).
Lecture seule pour le reste du système : n'écrit que data/sources_calendrier/mesure.json (dernier passage) et historique.json (un résumé par passage)."""
from __future__ import annotations

import gzip
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import rapprochement as R
from .reseau import telecharger as telecharger_reel

RACINE = Path(__file__).resolve().parent.parent
CONFIG = RACINE / "config" / "sources_calendrier.json"
DOSSIER = RACINE / "data" / "sources_calendrier"
NB_EXEMPLES = 25


def config(chemin: Path = CONFIG) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _source(nom: str):
    return importlib.import_module(f"sources_calendrier.sources.{nom}")


FLUX = RACINE / "data" / "archive_test"


def avec_cotes(jours: list[str], flux: Path = FLUX) -> set[str]:
    """Identifiants Matchendirect des matchs du flux commun qui ont des cotes Betpawa, pour ces jours."""
    out = set()
    for j in jours:
        f = flux / f"{j}.json.gz"
        if f.exists():
            out |= {k for k, x in json.load(gzip.open(f)).items() if x.get("cotes_betpawa")}
    return out


def _part(n: int, total: int) -> float | None:
    return round(n / total, 4) if total else None


def mesurer(conf: dict, telecharger=telecharger_reel, racine: Path = RACINE, maintenant: datetime | None = None, flux: Path = FLUX) -> dict:
    maintenant = maintenant or datetime.now(timezone.utc)
    principale = next(s for s in conf["sources"] if s.get("role") == "principale")
    mod = _source(principale["nom"])
    tous_jours = sorted({m.get("date") for f in principale["fichiers"] if (racine / f).exists() for m in json.loads((racine / f).read_text(encoding="utf-8")) if m.get("date")})
    reference, erreurs_ref = mod.lire(tous_jours, principale, None, racine)
    cotes = avec_cotes(tous_jours, flux) & {m.id_source for m in reference}
    ref_par_id = {m.id_source: m for m in reference}
    out = {"mesure_le": maintenant.isoformat(timespec="seconds"), "mode": conf.get("mode"), "jours": tous_jours,
           "reference": {"source": principale["nom"], "matchs": len(reference), "avec_cotes_betpawa": len(cotes), "erreurs": erreurs_ref,
                         "par_jour": {j: sum(1 for m in reference if m.jour == j) for j in tous_jours}}, "sources": []}
    for s in conf["sources"]:
        if s.get("role") != "secours" or not s.get("actif"):
            continue
        try:
            matchs, erreurs = _source(s["nom"]).lire(tous_jours, s, telecharger)
        except Exception as e:                                # noqa: BLE001 : une source cassée est notée, elle n'arrête pas la mesure des autres
            matchs, erreurs = [], [f"source en panne : {type(e).__name__} : {str(e)[:200]}"]
        r = R.rapprocher(reference, matchs)
        trouves = set(r["paires"])
        pris = {c.cle() for c in r["paires"].values()}
        manquants = [ref_par_id[i] for i in r["sans"] if i in cotes]
        out["sources"].append({
            "source": s["nom"], "joignable": bool(matchs) or not erreurs, "erreurs": erreurs, "matchs_lus": len(matchs),
            "retrouves": len(trouves), "part_retrouvee": _part(len(trouves), len(reference)),
            "retrouves_avec_cotes": len(trouves & cotes), "part_retrouvee_avec_cotes": _part(len(trouves & cotes), len(cotes)),
            "ambigus": len(r["ambigus"]), "ambigus_avec_cotes": len(set(r["ambigus"]) & cotes),
            "matchs_absents_de_la_reference": sum(1 for c in matchs if c.cle() not in pris),
            "exemples_avec_cotes_non_retrouves": [{"jour": m.jour, "domicile": m.domicile, "exterieur": m.exterieur, "competition": m.competition} for m in manquants[:NB_EXEMPLES]],
            "exemples_retrouves": [{"reference": f"{ref_par_id[i].domicile} - {ref_par_id[i].exterieur}", "source": f"{c.domicile} - {c.exterieur}", "jour": c.jour} for i, c in list(r["paires"].items())[:NB_EXEMPLES]]})
    return out


def ecrire(resultat: dict, dossier: Path = DOSSIER) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "mesure.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
    h = dossier / "historique.json"
    try:
        hist = json.loads(h.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        hist = []
    hist.append({"mesure_le": resultat["mesure_le"], "jours": resultat["jours"], "reference": {k: resultat["reference"][k] for k in ("matchs", "avec_cotes_betpawa")},
                 "sources": [{k: s[k] for k in ("source", "joignable", "matchs_lus", "retrouves", "retrouves_avec_cotes", "ambigus", "part_retrouvee", "part_retrouvee_avec_cotes")} | {"nb_erreurs": len(s["erreurs"])}
                             for s in resultat["sources"]]})
    h.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")


def resume(resultat: dict) -> str:
    ref = resultat["reference"]
    L = [f"sources de calendrier : {ref['matchs']} matchs Matchendirect sur {len(resultat['jours'])} jour(s), dont {ref['avec_cotes_betpawa']} avec cotes Betpawa"]
    pct = lambda v: "—" if v is None else f"{100 * v:.0f} %"
    for s in resultat["sources"]:
        L.append(f"  {s['source']:13s} {'joignable' if s['joignable'] else 'INJOIGNABLE'} · {s['matchs_lus']} matchs lus · retrouvés {s['retrouves']} ({pct(s['part_retrouvee'])})"
                 f" · avec cotes {s['retrouves_avec_cotes']} ({pct(s['part_retrouvee_avec_cotes'])}) · ambigus {s['ambigus']} · {len(s['erreurs'])} erreur(s)")
        for e in s["erreurs"][:5]:
            L.append(f"      erreur : {e}")
    return "\n".join(L)


def main() -> None:
    r = mesurer(config())
    ecrire(r)
    print(resume(r))


if __name__ == "__main__":
    main()
