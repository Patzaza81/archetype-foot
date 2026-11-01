"""Pilote de rejeu LECTURE SEULE (Omega ou Alpha) : refait un gel avec le code et l'archive d'un commit donné.
Usage : python pilote.py <arbre> <omega|alpha> <gele_le> <dossier_archive> <sortie.json>
  <arbre>            dossier contenant moteur_omega/ et alpha_serie/ tels qu'au commit qui a écrit le gel
  <dossier_archive>  archive_test à lire (celle de l'arbre = lecture A0 ; une variante = lecture modifiée)
Rien n'est écrit dans un journal ni dans l'archive."""
import json
import sys
from datetime import datetime
from pathlib import Path

arbre, moteur, ts, dossier, sortie = sys.argv[1:6]
sys.path.insert(0, arbre)
maintenant = datetime.fromisoformat(ts.replace("Z", "+00:00"))
res: dict = {}
blocs_utilises: dict = {}
if moteur == "omega":
    from moteur_omega import coeur, donnees as D, suivi as S
    params = S.charger_parametres()
    matchs, refs = D.charger_archive(Path(dossier), avec_futurs=True)
    for m in matchs:
        ko = S._ko(m.get("coup_d_envoi_utc"))
        if ko is None or ko <= maintenant or m.get("h") is not None:
            continue
        a = coeur.analyser(m, refs, params)
        s = coeur.selectionner(a, params["selection"])
        f = S.fiche(m, a, s)
        res[f["match_id"]] = f
        blocs_utilises[f["match_id"]] = {"dom": m["dom_matchs"], "ext": m["ext_matchs"]}
else:
    from alpha_serie import suivi as S, parametres as P
    S.ROOT = Path(dossier).parent.parent
    params = P.charger()
    classements = S._classements()
    for m in S.charger_matchs():
        ko = S._coup_d_envoi(m)
        if ko is None or ko <= maintenant or m.get("score_final"):
            continue
        r = S.analyser(m, params, classements)
        if r["statut"] != "analyse" or not any(r["onglets"].values()):
            continue
        if r["match_id"] not in res:
            res[r["match_id"]] = {k: r[k] for k in ("match_id", "coup_d_envoi_utc", "date", "competition", "domicile", "exterieur", "k", "onglets")}
            a = m.get("assemblage") or {}
            blocs_utilises[r["match_id"]] = {"dom": (a.get("equipe_dom") or {}).get("matchs"), "ext": (a.get("equipe_ext") or {}).get("matchs")}
Path(sortie).write_text(json.dumps({"fiches": res, "blocs": blocs_utilises}, ensure_ascii=False), encoding="utf-8")
print(len(res), "fiches")
