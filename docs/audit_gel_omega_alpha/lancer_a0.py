"""Lecture A0 : rejeu à l'identique (code + archive du commit qui a écrit le gel). Vérifie que le rejeu reproduit le journal gelé.
Usage : python lancer_a0.py <dossier_travail>   (dossier_travail contient commits.json et un sous-dossier t_<commit> par commit de gel)"""
import json, subprocess, sys
from pathlib import Path

W = Path(sys.argv[1]); ROOT = Path(__file__).resolve().parents[2]
JOURNAUX = {"omega": ROOT / "data/omega/journal.jsonl", "alpha": ROOT / "data/alpha_serie/journal.jsonl"}
CH = ("match_id", "coup_d_envoi_utc", "date", "competition", "domicile", "exterieur", "k", "onglets")


def sans_alerte(o):
    return {k: [{c: v for c, v in x.items() if c != "alerte"} for x in lst] for k, lst in o.items()}


bilan = {}
for cle, c in json.load(open(W / "commits.json")).items():
    moteur, ts = cle.split("|")
    sortie = W / f"a0_{moteur}_{ts.replace(':', '')}.json"
    p = subprocess.run([sys.executable, str(Path(__file__).with_name("pilote.py")), str(W / f"t_{c}"), moteur, ts, str(W / f"t_{c}/data/archive_test"), str(sortie)], capture_output=True, text=True)
    if p.returncode:
        bilan[cle] = {"commit": c, "erreur": p.stderr.strip().splitlines()[-1][:200]}; print(cle, "ERREUR", bilan[cle]["erreur"]); continue
    R = json.load(open(sortie))["fiches"]
    lignes = [json.loads(l) for l in open(JOURNAUX[moteur]) if l.startswith('{"type":"pronostic"') and json.loads(l)["gele_le"] == ts]
    ident = marches = absent = 0
    for l in lignes:
        r = R.get(l["match_id"])
        if r is None:
            absent += 1; continue
        if moteur == "omega":
            f = l["fiche"]; ident += json.dumps(r, sort_keys=True) == json.dumps(f, sort_keys=True)
            marches += json.dumps(r.get("principal")) == json.dumps(f.get("principal")) and json.dumps(r.get("autres")) == json.dumps(f.get("autres"))
        else:
            # on compare les onglets réellement gelés (le gel du 24/10 03:38 n'avait pas d'onglet « calibrees »)
            a = sans_alerte(l["onglets"]); b = sans_alerte({o: r["onglets"][o] for o in l["onglets"]})
            ident += json.dumps({k: l[k] for k in CH if k != "onglets"}, sort_keys=True) == json.dumps({k: r[k] for k in CH if k != "onglets"}, sort_keys=True) and json.dumps(l["onglets"], sort_keys=True) == json.dumps({o: r["onglets"][o] for o in l["onglets"]}, sort_keys=True)
            marches += json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    bilan[cle] = {"commit": c, "lignes_gelees": len(lignes), "absentes_du_rejeu": absent, "fiche_identique": ident, "paris_ou_marches_identiques": marches}
    print(cle, bilan[cle])
json.dump(bilan, open(W / "a0_bilan.json", "w"), indent=1)
