"""Rapport lisible des pronostics DC sur une fenêtre de coups d'envoi (à venir). Usage :
python -m moteur_dc.rapport 2026-10-30T17:00 2026-10-30T21:00   (heures UTC ; Douala = UTC+1)

Pour chaque match : équipes, statut (analysé / exclu et pourquoi), paris validés par le Module 4 (P, p̂, intervalle de Wilson, Z, base, Edge),
et les 3 tendances les plus probables du modèle avec la décision du Module 4 pour chacune. Écrit data/dc/rapport_<debut>.json.
Ce sont des PRONOSTICS (matchs à venir), pas un bilan : le bilan réel vient de `python bilan_reel.py` une fois les matchs terminés.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import coeur, donnees as D, module1 as M1, suivi

ROOT = Path(__file__).resolve().parent.parent


def _ligne(l: dict[str, Any]) -> dict[str, Any]:
    pr = l.get("preuve") or {}
    return {"marche": l["marche"], "P": round(l["p"], 4), "p_hat": pr.get("p_hat"), "k": pr.get("k"), "n": pr.get("n"), "wilson": pr.get("wilson"),
            "z": pr.get("z"), "base": l.get("base"), "edge": l.get("edge"), "cote": l.get("cote"), "decision": l.get("decision")}


def rapport(debut: datetime, fin: datetime, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or suivi.charger_parametres()
    ligues = D.charger_ligues()
    matchs = [m for m in D.charger_archive(ligues) if (k := suivi._ko(m.get("coup_d_envoi_utc"))) and debut <= k <= fin]
    lignes = suivi._lire(suivi.JOURNAL)
    caches: dict[tuple, Any] = {}
    out, etapes = [], Counter()
    for m in sorted(matchs, key=lambda m: m["coup_d_envoi_utc"]):
        liste = ligues.matchs.get(m["ligue"]) or []
        cle = (m["ligue"], m["jour"])
        if cle not in caches:
            t = M1.tableau(liste, m["jour"]) if liste else None
            fit = coeur.ajuster_ligue(liste, m["jour"], params, t) if liste else None
            caches[cle] = (fit, t, coeur.bases_ligue(liste, m["jour"]) if fit else None)
        fit, t, bases = caches[cle]
        r = {"coup_d_envoi_utc": m["coup_d_envoi_utc"], "competition": m.get("competition"), "domicile": m["domicile"], "exterieur": m["exterieur"]}
        if fit is None:
            out.append({**r, "statut": "exclu", "raison": "championnat sans match connu"})
            continue
        a = coeur.analyser(m, liste, params, fit, t, bases)
        if a["statut"] != "analyse":
            out.append({**r, "statut": "exclu", "raison": a["raison"]})
            continue
        e, source, _ = suivi.emac_glissante(lignes, m["jour"], [], params["emac"])
        s = coeur.selectionner(a, params, e)
        for l in a["marches"]:
            etapes[l["decision"].split(" :")[0]] += 1
        paris = ([s["principal"]] if s["principal"] else []) + s["autres"]
        top = sorted(a["marches"], key=lambda l: -l["p"])[:3]
        out.append({**r, "statut": "analyse", "buts_attendus": {k: round(v, 2) for k, v in a["buts_attendus"].items()},
                    "paris_valides": [_ligne(l) for l in paris], "tendances": [_ligne(l) for l in top],
                    "z_seuil": s["z_seuil"], "emac": s["emac"]})
    paris = [p for x in out for p in x.get("paris_valides", [])]
    resume = {"fenetre_utc": [debut.isoformat(), fin.isoformat()], "matchs": len(out), "analyses": sum(x["statut"] == "analyse" for x in out),
              "matchs_avec_pari": sum(bool(x.get("paris_valides")) for x in out), "paris": len(paris),
              "paris_P_70_et_plus": sum(p["P"] >= 0.70 for p in paris), "marches_par_etape": dict(etapes)}
    return {"resume": resume, "matchs": out}


def texte(r: dict[str, Any]) -> str:
    z = r["resume"]
    L = [f"{z['matchs']} matchs ({z['analyses']} analysés) | {z['paris']} paris validés sur {z['matchs_avec_pari']} matchs | "
         f"dont {z['paris_P_70_et_plus']} à P ≥ 70 % | marchés par étape : {z['marches_par_etape']}"]
    for x in r["matchs"]:
        h = (datetime.fromisoformat(x["coup_d_envoi_utc"].replace("Z", "+00:00")) + timedelta(hours=1)).strftime("%H:%M")
        L.append(f"\n{h} {x['domicile']} – {x['exterieur']} ({x['competition']})")
        if x["statut"] != "analyse":
            L.append(f"   EXCLU : {x['raison']}")
            continue
        for p in x["paris_valides"]:
            L.append(f"   VALIDÉ  {p['marche']} : P {p['P']:.0%} | p̂ {p['p_hat']:.0%} ({p['k']}/{p['n']}) Wilson [{p['wilson'][0]:.0%} ; {p['wilson'][1]:.0%}]"
                     f" | Z {p['z']} | base {p['base']:.0%} | cote {p['cote'] or '—'}")
        for p in x["tendances"]:
            w = p["wilson"]
            L.append(f"   tendance {p['marche']} : P {p['P']:.0%} | p̂ {p['p_hat']:.0%} ({p['k']}/{p['n']})"
                     + (f" Wilson [{w[0]:.0%} ; {w[1]:.0%}]" if w else "") + f" | Z {p['z']} → {p['decision']}")
    return "\n".join(L)


if __name__ == "__main__":
    d = datetime.fromisoformat(sys.argv[1]).replace(tzinfo=timezone.utc)
    f = datetime.fromisoformat(sys.argv[2]).replace(tzinfo=timezone.utc)
    r = rapport(d, f)
    sortie = ROOT / "data" / "dc" / f"rapport_{d.strftime('%Y-%m-%d_%Hh')}.json"
    sortie.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(texte(r))
    print(f"\nJSON : {sortie.relative_to(ROOT)}")
