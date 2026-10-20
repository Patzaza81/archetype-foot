"""Calibration des marges et seuils d'écart attendu sur l'archive de test (résultats seulement, aucune cote).

Règle : pour chaque famille de marché, on cherche le plus petit cran (pas de 0,25 but) tel que, parmi les matchs qui respectent la marge,
  - la réussite dépasse la fréquence de base du marché de plus d'une erreur-type (le bruit d'échantillon),
  - et reste au moins égale à la base dans CHAQUE moitié chronologique où la marge est présente.
Une marge calibrée ne peut qu'ÉLARGIR le plancher de départ (`parametres.DEFAUT`) : elle ne le resserre jamais. Si aucun cran ne passe le test,
le plancher est gardé et la famille est listée dans `provisoire`.
Usage : python -m alpha_serie.calibration
"""
from __future__ import annotations

import copy
import glob
import gzip
import json
import math
from pathlib import Path

from . import coeur, parametres as P

ROOT = Path(__file__).resolve().parent.parent
PAS = 0.25
GRILLE = [round(i * PAS, 2) for i in range(0, 13)]       # 0 à 3 buts


def charger_archive() -> list[dict]:
    """Un enregistrement par match de l'archive avec score, assemblage des deux équipes et cotes BetPawa (cotes gardées pour le backtest)."""
    out = []
    for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
        for x in json.load(gzip.open(f)).values():
            sc, a = x.get("score"), x.get("assemblage") or {}
            if not sc or sc.get("buts_dom") is None or sc.get("buts_ext") is None:
                continue
            if "matchs" not in (a.get("equipe_dom") or {}) or "matchs" not in (a.get("equipe_ext") or {}):
                continue
            out.append({"jour": str(x["date"])[:10], "dom": a["equipe_dom"], "ext": a["equipe_ext"], "cotes": x.get("cotes_betpawa") or {},
                        "h": sc["buts_dom"], "a": sc["buts_ext"]})
    return out


def lignes(archive: list[dict]) -> list[dict]:
    """Matchs analysables (4 matchs au même lieu minimum pour chaque équipe) avec leurs buts attendus."""
    rows = []
    for m in archive:
        hm, hc = coeur.serie_lieu(m["dom"], True, m["jour"])
        am, ac = coeur.serie_lieu(m["ext"], False, m["jour"])
        if P.coef_k(min(len(hm), len(am))) is None:
            continue
        rows.append({"jour": m["jour"], "niv": coeur.niveaux(hm, hc, am, ac), "h": m["h"], "a": m["a"]})
    return rows


def _moitiés(rows: list[dict]) -> str:
    jours = sorted({r["jour"] for r in rows})
    return jours[len(jours) // 2] if jours else ""


def _valide(rows: list[dict], cond, win, coupe: str) -> tuple[bool, dict]:
    sel = [r for r in rows if cond(r)]
    if not sel:
        return False, {"n": 0}
    base = sum(win(r) for r in rows) / len(rows)
    p = sum(win(r) for r in sel) / len(sel)
    se = math.sqrt(max(base * (1 - base), 1e-9) / len(sel))
    z = (p - base) / se
    ok = z >= 1.0
    for moitie in (lambda r: r["jour"] < coupe, lambda r: r["jour"] >= coupe):
        s, b = [r for r in sel if moitie(r)], [r for r in rows if moitie(r)]
        if s and b and sum(win(r) for r in s) / len(s) < sum(win(r) for r in b) / len(b) - 1e-9:
            ok = False
    return ok, {"n": len(sel), "reussite": round(p, 4), "base": round(base, 4), "z": round(z, 2)}


def _plus_petit_cran(rows, cond_t, win, coupe):
    for t in GRILLE:
        ok, info = _valide(rows, lambda r, t=t: cond_t(r, t), win, coupe)
        if ok:
            return t, info
    return None, {}


def calibrer(rows: list[dict]) -> dict:
    """Retourne des paramètres (planchers de départ élargis par l'archive) et le détail de la calibration."""
    params = P.defaut()
    coupe = _moitiés(rows)
    detail, provisoire = {}, []

    def regler(cible: dict, cle: str, nom: str, cond_t, win, rows_=None):
        t, info = _plus_petit_cran(rows_ if rows_ is not None else rows, cond_t, win, coupe)
        plancher = cible[cle]
        if t is None:
            provisoire.append(nom)
            detail[nom] = {"retenu": plancher, "plancher": plancher, "appris": None}
        else:
            cible[cle] = max(plancher, t)
            detail[nom] = {"retenu": cible[cle], "plancher": plancher, "appris": t, **info}

    for ligne in ("1.5", "2.5", "3.5", "4.5"):
        L = float(ligne)
        regler(params["marges"]["total_plus"], ligne, f"total_plus_{ligne}", lambda r, t, L=L: r["niv"]["total"] >= L + t, lambda r, L=L: r["h"] + r["a"] > L)
        regler(params["marges"]["total_moins"], ligne, f"total_moins_{ligne}", lambda r, t, L=L: r["niv"]["total"] <= L - t, lambda r, L=L: r["h"] + r["a"] < L)
    # marchés d'équipe : chaque match fournit deux observations (domicile et extérieur)
    eq = [{"jour": r["jour"], "e": r["niv"]["dom"], "g": r["h"]} for r in rows] + [{"jour": r["jour"], "e": r["niv"]["ext"], "g": r["a"]} for r in rows]
    for ligne in ("0.5", "1.5", "2.5"):
        L = float(ligne)
        regler(params["marges"]["equipe_plus"], ligne, f"equipe_plus_{ligne}", lambda r, t, L=L: r["e"] >= L + t, lambda r, L=L: r["g"] > L, eq)
        regler(params["marges"]["equipe_moins"], ligne, f"equipe_moins_{ligne}", lambda r, t, L=L: r["e"] <= L - t, lambda r, L=L: r["g"] < L, eq)
    s = params["seuils_resultat"]
    regler(s, "dom_gagne", "dom_gagne", lambda r, t: r["niv"]["d"] >= t, lambda r: r["h"] > r["a"])
    regler(s, "ext_gagne", "ext_gagne", lambda r, t: -r["niv"]["d"] >= t, lambda r: r["a"] > r["h"])
    regler(s, "dom_ne_perd_pas", "dom_ne_perd_pas", lambda r, t: r["niv"]["d"] >= t, lambda r: r["h"] >= r["a"])
    regler(s, "ext_ne_perd_pas", "ext_ne_perd_pas", lambda r, t: -r["niv"]["d"] >= t, lambda r: r["a"] >= r["h"])
    # nul : la condition s'élargit avec t ; on retient le seuil de meilleur z qui passe le test (None si aucun)
    meilleur = None
    for t in GRILLE[1:]:
        ok, info = _valide(rows, lambda r, t=t: abs(r["niv"]["d"]) <= t, lambda r: r["h"] == r["a"], coupe)
        if ok and (meilleur is None or info["z"] > meilleur[1]["z"]):
            meilleur = (t, info)
    s["nul"] = meilleur[0] if meilleur else None
    detail["nul"] = {"retenu": s["nul"], **(meilleur[1] if meilleur else {"appris": None})}
    if not meilleur:
        provisoire.append("nul")
    params["provisoire"] = provisoire
    params["detail_calibration"] = detail
    jours = sorted({r["jour"] for r in rows})
    params["source"] = f"archive de test, {len(rows)} matchs analysables, du {jours[0]} au {jours[-1]}" if jours else "aucune donnée"
    return params


def main() -> None:
    rows = lignes(charger_archive())
    params = calibrer(rows)
    P.ecrire(params)
    print(params["source"])
    for nom, d in sorted(params["detail_calibration"].items()):
        print(f"{nom:22s} plancher {d.get('plancher')} -> retenu {d.get('retenu')}  {({k: v for k, v in d.items() if k in ('n', 'reussite', 'base', 'z')})}")
    print("provisoires (aucun cran n'a passé le test, plancher gardé) :", params["provisoire"])


if __name__ == "__main__":
    main()
