"""Audit du 01/11/2026 (ordre de Patrick) : mesure de l'effet du filtre EV > 0 et du tri par EV. Usage : python -m moteur_dc.audit

Deux mesures, annoncées avec leur nombre de matchs, de paris et leur période :
1. JOURNAL RÉEL : paris gelés AVANT le coup d'envoi, matchs terminés (règle de bilan_reel.py). « Avant » = tous ces paris (règle de production) ; « après » = ceux d'EV > 0 (filtre expérimental).
2. REJEU de l'archive ARCHETYPE (cotes BetPawa prises avant le coup d'envoi), marche avant, règle de production (probabilité) contre règle expérimentale (EV).
   Les seuils par marché ont été appris sur cette même archive : le rejeu est donc OPTIMISTE pour les deux règles ; le filtre EV, lui, n'a aucun paramètre.
3. CONTRÔLE de la décomposition des λ sur tous les matchs rejoués : le produit des facteurs gelés doit redonner les buts attendus.
Rendement THÉORIQUE = moyenne de P × cote − 1 selon le modèle ; rendement RÉEL = moyenne de (cote − 1 si gagné, −1 sinon) par pari, mise de 1.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as K, coeur, suivi

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "dc_audit_resultats.json"
TIRAGES = 4000


def _stats(paris: list[dict[str, Any]], par_match: bool = True) -> dict[str, Any]:
    """paris : {match, p, cote, gagne}. Intervalle à 95 % du rendement réel par bootstrap PAR MATCH (les paris d'un même match ne sont pas indépendants)."""
    if not paris:
        return {"paris": 0, "matchs": 0}
    gain = [(p["cote"] - 1) if p["gagne"] else -1.0 for p in paris]
    out = {"paris": len(paris), "matchs": len({p["match"] for p in paris}), "gagnes": sum(p["gagne"] for p in paris),
           "reussite": round(sum(p["gagne"] for p in paris) / len(paris), 4), "p_moyenne": round(float(np.mean([p["p"] for p in paris])), 4),
           "cote_moyenne": round(float(np.mean([p["cote"] for p in paris])), 3),
           "rendement_theorique": round(float(np.mean([p["p"] * p["cote"] - 1 for p in paris])), 4), "rendement_reel": round(float(np.mean(gain)), 4)}
    groupes: dict[str, list[float]] = {}
    for p, g in zip(paris, gain):
        groupes.setdefault(p["match"], []).append(g)
    liste = list(groupes.values())
    rng = random.Random(20261101)
    moy = sorted(float(np.mean([g for i in [rng.randrange(len(liste)) for _ in liste] for g in liste[i]])) for _ in range(TIRAGES))
    out["rendement_reel_ic95_par_match"] = [round(moy[int(0.025 * TIRAGES)], 4), round(moy[int(0.975 * TIRAGES)], 4)]
    return out


def journal_reel() -> dict[str, Any]:
    lignes = suivi._lire(suivi.JOURNAL)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    avant, a_venir = [], []
    for mid, l in suivi.derniers_pronostics(lignes).items():
        f = l["fiche"]
        paris = [x for x in ([f["principal"]] if f.get("principal") else []) + (f.get("autres") or []) if x.get("cote")]
        if mid in res:
            g = {json.dumps(r["cle"]): r["gagne"] for r in res[mid]["paris"]}
            avant += [{"match": mid, "p": x["p"], "cote": x["cote"], "gagne": g[json.dumps(x["cle"])], "ko": f.get("coup_d_envoi_utc")} for x in paris]
        elif _futur(f):
            a_venir += [{"match": mid, "p": x["p"], "cote": x["cote"]} for x in paris]
    apres = [p for p in avant if p["p"] * p["cote"] - 1 > 0]
    ko = sorted(p["ko"] for p in avant if p["ko"])
    # matchs dont le pari principal change : principal « avant » = le plus probable ; « après » = le plus rentable parmi les paris d'EV > 0
    chg = 0
    for mid in {p["match"] for p in avant}:
        ps = [p for p in avant if p["match"] == mid]
        pr_avant = max(ps, key=lambda p: p["p"])
        ev_ok = [p for p in ps if p["p"] * p["cote"] - 1 > 0]
        if ev_ok and max(ev_ok, key=lambda p: p["p"] * p["cote"]) is not pr_avant:
            chg += 1
    return {"source": "data/dc/journal.jsonl : paris gelés avant le coup d'envoi, matchs terminés, cote connue", "periode": [ko[0], ko[-1]] if ko else None,
            "avant_filtre_ev": _stats(avant), "apres_filtre_ev": _stats(apres), "rejetes_par_ev": _stats([p for p in avant if p not in apres]),
            "matchs_dont_le_pari_principal_change": chg, "paris_a_venir_avant": len(a_venir), "paris_a_venir_apres": sum(p["p"] * p["cote"] - 1 > 0 for p in a_venir),
            "lecture": "échantillon court : lire les ordres de grandeur, pas une preuve"}


def _futur(f: dict[str, Any]) -> bool:
    ko = suivi._ko(f.get("coup_d_envoi_utc"))
    return ko is not None and ko > datetime.now(ko.tzinfo)


def rejeu_archive(params: dict[str, Any]) -> dict[str, Any]:
    an = K.analyses_archive(params, log=lambda *a: None)
    coupe = K.COUPE_ARCHIVE
    out: dict[str, Any] = {"source": "archive ARCHETYPE rejouée en marche avant (cotes BetPawa prises avant le coup d'envoi)", "coupe": coupe}
    err_max = 0.0
    for nom, groupe in (("calibrage_avant_coupe", [x for x in an if x["m"]["jour"] < coupe]), ("validation_apres_coupe", [x for x in an if x["m"]["jour"] >= coupe]),
                        ("ensemble", an)):
        res: dict[str, Any] = {"matchs_analyses": len(groupe)}
        for regle in ("probabilite", "ev"):
            paris, principaux = [], []
            for x in groupe:
                a = json.loads(json.dumps(x["a"], default=float))                    # la sélection écrit dans les lignes : copie propre pour chaque règle
                s = coeur.selectionner(a, params, regle=regle)
                for q, l in enumerate(([s["principal"]] if s["principal"] else []) + s["autres"]):
                    gagne = bool(coeur.TESTS[tuple(l["cle"])](x["m"]["h"], x["m"]["a"]))
                    ligne = {"match": x["m"]["id"], "p": l["p"], "cote": l["cote"], "gagne": gagne}
                    paris.append(ligne)
                    if q == 0:
                        principaux.append(ligne)
            res[{"probabilite": "production_probabilite", "ev": "experimental_ev"}[regle]] = {"tous_les_paris": _stats(paris), "paris_principaux": _stats(principaux)}
        out[nom] = res
    for x in an:
        d = x["a"]["decomposition"]
        e1 = abs(d["lambda_dom"]["niveau_ligue"] * d["lambda_dom"]["avantage_terrain"] * d["lambda_dom"]["attaque_dom"] * d["lambda_dom"]["faiblesse_defensive_ext"] - d["lambda_dom"]["valeur"])
        e2 = abs(d["lambda_ext"]["niveau_ligue"] * d["lambda_ext"]["attaque_ext"] * d["lambda_ext"]["faiblesse_defensive_dom"] - d["lambda_ext"]["valeur"])
        err_max = max(err_max, e1, e2)
    out["controle_decomposition"] = {"matchs": len(an), "ecart_max_produit_des_facteurs_vs_buts_attendus": err_max,
                                     "verdict": "reproductible" if err_max < 1e-4 else "ÉCART"}
    return out


def exemple(params: dict[str, Any], equipe: str = "Arezzo") -> dict[str, Any]:
    """Décomposition des λ d'un match (celui du premier club dont le nom commence par `equipe`, à défaut le premier match analysable de l'archive)."""
    from . import donnees as D, module1 as M1
    ligues = D.charger_ligues()
    matchs = D.charger_archive(ligues)
    cand = [m for m in matchs if str(m["domicile"]).startswith(equipe)] + matchs
    for m in cand:
        liste = ligues.matchs.get(m["ligue"]) or []
        t = M1.tableau(liste, m["jour"]) if liste else None
        fit = coeur.ajuster_ligue(liste, m["jour"], params, t) if liste else None
        if fit is None:
            continue
        a = coeur.analyser(m, liste, params, fit, t, coeur.bases_ligue(liste, m["jour"]))
        if a["statut"] == "analyse":
            s = coeur.selectionner(a, params, params["emac"])
            return {"match": f"{m['domicile']} – {m['exterieur']} ({m['jour']})", "buts_attendus": {k: round(v, 3) for k, v in a["buts_attendus"].items()},
                    "decomposition": a["decomposition"], "paris": [{"marche": x["marche"], "p": round(x["p"], 4), "cote": x["cote"], "ev": x["ev"],
                                                                    "dom": x["preuve"]["dom"], "ext": x["preuve"]["ext"], "estimation": x["preuve"]["estimation"]}
                                                                   for x in ([s["principal"]] if s["principal"] else []) + s["autres"]]}
    return {}


def main() -> None:
    params = suivi.charger_parametres()
    out = {"genere_le": datetime.now().isoformat(timespec="seconds"), "journal_reel": journal_reel(), "rejeu_archive": rejeu_archive(params),
           "exemple_decomposition_lambda": exemple(params)}
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"écrit : {SORTIE}")


if __name__ == "__main__":
    main()
