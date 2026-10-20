"""Backtest du moteur alpha « séries » sur l'archive de test (marche avant, sans fuite).

Les paramètres sont calibrés sur la PREMIÈRE moitié des jours, puis le moteur est rejoué sur la SECONDE moitié (équipes figées avant le match).
Pour chaque onglet : marchés admis, réussite mesurée, réussite de base du même marché (tous les matchs de la seconde moitié), et, à l'étape 2,
rendement à mise égale avec les cotes réelles (cote >= 1,25 pour buts et équipes). Aucune promesse de rentabilité : les chiffres sont rapportés tels quels.
Usage : python -m alpha_serie.backtest
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .marches import test_du_marche

from . import calibration as C, coeur, parametres as P

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "alpha_serie_backtest.json"


def _gagne(cle: tuple[str, str], h: int, a: int) -> bool | None:
    g, s = cle
    if g == "multigoals":
        lo, hi = (int(x) for x in s.split("-"))
        return lo <= h + a <= hi
    if g == "multiscores":
        return coeur.GROUPES_MULTISCORES[s](h, a)
    p = test_du_marche(g, s)
    return None if p is None else bool(p(h, a))


def _pct(x: int, n: int) -> float | None:
    return round(x / n, 4) if n else None


def rejouer(archive: list[dict], params: dict) -> dict:
    onglets = {"buts": [], "equipes": [], "multigoals": [], "multiscores": []}
    base: dict[tuple, list[int]] = defaultdict(list)
    nb_matchs = 0
    for m in archive:
        r = coeur.analyser_match(m["dom"], m["ext"], m["jour"], params)
        if r["statut"] != "analyse":
            continue
        nb_matchs += 1
        etape2 = coeur.choisir(r, m["cotes"])
        for onglet, lst in etape2["onglets"].items():
            for f in lst:
                g = _gagne(f["cle"], m["h"], m["a"])
                if g is None:
                    continue
                # Un marché dont la cote est introuvable ne peut pas être vérifié à l'étape 2 : jamais compté dans buts / équipes.
                # Multigoals et multiscores : pas de cotes dans l'archive, ils sont jugés à part, en réussite seule.
                if f["cle"][0] in ("multigoals", "multiscores"):
                    rubrique = f["cle"][0]
                elif f.get("cote") is None:
                    continue
                else:
                    rubrique = onglet
                onglets[rubrique].append({"cle": f["cle"], "marche": f["marche"], "valeur": f["valeur"], "cote": f.get("cote"), "gagne": g})
        cles = [c for lst in coeur.CATALOGUE.values() for c in lst]       # réussite de base : tous les matchs analysables, mêmes marchés, sans filtre
        cles += [("multigoals", f"{lo}-{hi}") for lo, hi in params["multigoals"]["plages"]] + [("multiscores", n) for n in coeur.GROUPES_MULTISCORES]
        for c in cles:
            w = _gagne(c, m["h"], m["a"])
            if w is not None:
                base[c].append(int(w))
    out = {"matchs_rejoues": nb_matchs, "onglets": {}}
    for onglet, lst in onglets.items():
        par: dict[str, list] = defaultdict(list)
        for x in lst:
            par[x["marche"]].append(x)
        marches = []
        for nom, L in sorted(par.items(), key=lambda kv: -len(kv[1])):
            n, w = len(L), sum(x["gagne"] for x in L)
            avec_cote = [x for x in L if x["cote"]]
            b = base.get(L[0]["cle"])
            marches.append({"marche": nom, "n": n, "reussite": _pct(w, n), "base": _pct(sum(b), len(b)) if b else None,
                            "rendement": round(sum((x["cote"] if x["gagne"] else 0) - 1 for x in avec_cote) / len(avec_cote), 4) if avec_cote else None,
                            "cote_moyenne": round(sum(x["cote"] for x in avec_cote) / len(avec_cote), 3) if avec_cote else None})
        n, w = len(lst), sum(x["gagne"] for x in lst)
        ac = [x for x in lst if x["cote"]]
        out["onglets"][onglet] = {"propositions": n, "reussite": _pct(w, n),
                                  "rendement": round(sum((x["cote"] if x["gagne"] else 0) - 1 for x in ac) / len(ac), 4) if ac else None,
                                  "marches": marches}
    return out


def main() -> None:
    archive = C.charger_archive()
    jours = sorted({m["jour"] for m in archive})
    coupe = jours[len(jours) // 2]
    appr = [m for m in archive if m["jour"] < coupe]
    test = [m for m in archive if m["jour"] >= coupe]
    params = C.calibrer(C.lignes(appr))
    res = {"coupe": coupe, "jours_apprentissage": len({m['jour'] for m in appr}), "jours_test": len({m['jour'] for m in test}),
           "parametres_apprentissage": {k: params[k] for k in ("marges", "seuils_resultat", "provisoire")},
           "test": rejouer(test, params)}
    SORTIE.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("coupe", coupe, "| matchs rejoués :", res["test"]["matchs_rejoues"])
    for onglet, d in res["test"]["onglets"].items():
        print(f"== {onglet} : {d['propositions']} propositions, réussite {d['reussite']}, rendement {d['rendement']}")
        for x in d["marches"][:8]:
            print("  ", x)


if __name__ == "__main__":
    main()
