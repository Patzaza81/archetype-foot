"""Chargement du jeu d'évaluation : matchs de data/archive_test avec score, 2 historiques et cotes."""
import glob
import gzip
import json
import os

import journal_rentabilite as J

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def charge(racine=RACINE, a_venir=False):
    """a_venir=False : matchs joués seulement. a_venir=True : matchs sans score (h/a = None) en plus."""
    A = {}
    for f in sorted(glob.glob(os.path.join(racine, "data", "archive_test", "*.json.gz"))):
        d = json.load(gzip.open(f))
        it = d.get("matchs", d)
        it = it.values() if isinstance(it, dict) else it
        for m in it:
            A[m["match_id"]] = m
    out = []
    for m in A.values():
        sc = m.get("score") or {}
        joue = sc.get("buts_dom") is not None
        if not joue and not a_venir:
            continue
        if not (m.get("equipe_dom") or {}).get("matchs") or not (m.get("equipe_ext") or {}).get("matchs"):
            continue
        cotes = m.get("cotes_observees") or {}
        if not cotes:
            continue
        c, _ = J.controle_coherence({k: float(v) for k, v in cotes.items() if v and float(v) > 1.0})
        out.append(dict(
            id=m["match_id"], date=m["date"], ligue=m["competition"], h=sc.get("buts_dom"), a=sc.get("buts_ext"), cotes=c,
            dom=m.get("domicile"), ext=m.get("exterieur"), kickoff=m.get("coup_d_envoi_utc"),
            hd=[x for x in m["equipe_dom"]["matchs"] if x["date"] < m["date"]],
            he=[x for x in m["equipe_ext"]["matchs"] if x["date"] < m["date"]]))
    out.sort(key=lambda m: (m["date"], m["id"]))
    return out
