"""Backtest du moteur en deux étapes + recalage par famille. Lecture seule.

1) Courbes de recalage apprises sur Football-Data (résultats seuls, 60 % premiers jours), pour TOUTES les sélections.
2) Évaluation sur l'archive jouée (cotes BetPawa réelles, filtre cote >= 1,26) : réussite et probabilité annoncée,
   avant / après recalage. Intervalle de confiance par rééchantillonnage des JOURNÉES (matchs d'un même jour corrélés).
Usage : python -m matrice_scenarios.backtest_comportement
"""
from __future__ import annotations

import glob
import gzip
import json
import random
from collections import defaultdict
from pathlib import Path

from . import comportement as C
from . import recalage as R
from . import scanner_marches as S
from .pronostic_sur import derniers_matchs

ROOT = Path(__file__).resolve().parent.parent
COTE_MIN = 1.26
PAS_APPRENTISSAGE = 3          # un match sur 3 pour l'apprentissage (vitesse)


def historiques(dom: dict, ext: dict, jour: str):
    d, e = derniers_matchs(dom, True, jour), derniers_matchs(ext, False, jour)
    if len(d) < 3 or len(e) < 3:
        d, e = derniers_matchs(dom, True, jour, meme_lieu=False), derniers_matchs(ext, False, jour, meme_lieu=False)
        if len(d) < 3 or len(e) < 3:
            return None
    return d, e


def charger_archive() -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
        for x in json.load(gzip.open(f)).values():
            sc, a = x.get("score"), x.get("assemblage") or {}
            if not sc or sc.get("buts_dom") is None or not x.get("cotes_betpawa"):
                continue
            if "matchs" not in (a.get("equipe_dom") or {}) or "matchs" not in (a.get("equipe_ext") or {}):
                continue
            h = historiques(a["equipe_dom"], a["equipe_ext"], x["date"])
            if h:
                out.append({"date": x["date"], "hist": h, "cotes": x["cotes_betpawa"], "gd": sc["buts_dom"], "ge": sc["buts_ext"]})
    return out


def selections_standard(archive: list[dict]) -> list[tuple[str, str]]:
    vus = {}
    for m in archive:
        for g, sels in m["cotes"].items():
            for s in (sels or {}):
                if S.test_du_marche(g, s):
                    vus[(g, s)] = 1
    return list(vus)


def apprendre_courbes(selections: list[tuple[str, str]]) -> dict[str, list]:
    """Courbes par famille, apprises sur les 60 % premiers jours de Football-Data."""
    from .football_data import load_football_data
    fd, _ = load_football_data()
    lignes = []
    for r in sorted(fd, key=lambda r: r["date"]):
        d = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["home_history"] if x["venue"] == "home" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[-5:]]
        e = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["away_history"] if x["venue"] == "away" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[-5:]]
        if len(d) >= 3 and len(e) >= 3:
            lignes.append((d, e, r["home_goals"], r["away_goals"]))
    train = lignes[: int(len(lignes) * 0.6)][::PAS_APPRENTISSAGE]
    tests = {sel: S.test_du_marche(*sel) for sel in selections}
    par_fam: dict[str, list] = defaultdict(list)
    for d, e, gd, ge in train:
        g = C.grille(*C.buts_attendus(d, e), C.RHO)
        for (grp, sel), t in tests.items():
            par_fam[R.famille(grp)].append((C.proba(g, t), int(t(gd, ge))))
    return {f: R.isotone(p) for f, p in par_fam.items()} | {"_matchs_apprentissage": len(train)}


def pick(match: dict, courbes: dict | None) -> dict | None:
    g = C.grille(*C.buts_attendus(*match["hist"]), C.RHO)
    marches, _ = S.scanner(g, match["cotes"])
    if courbes is not None:
        for m in marches:
            m["probabilite"] = R.appliquer(courbes.get(R.famille(m["groupe"]), []), m["probabilite"])
    p = S.choisir(marches, COTE_MIN)
    if p:
        p["gagne"] = bool(S.test_du_marche(p["groupe"], p["selection"])(match["gd"], match["ge"]))
    return p


def resume(picks: list[tuple[str, dict]]) -> dict:
    n = len(picks)
    h = sum(p["gagne"] for _, p in picks)
    jours = defaultdict(list)
    for j, p in picks:
        jours[j].append(p["gagne"])
    cles, rnd, taux = list(jours), random.Random(0), []
    for _ in range(2000):
        tir = [jours[rnd.choice(cles)] for _ in cles]
        tot = sum(len(t) for t in tir)
        taux.append(sum(sum(t) for t in tir) / tot)
    taux.sort()
    return {"n": n, "reussite": round(h / n, 4), "annonce": round(sum(p["probabilite"] for _, p in picks) / n, 4),
            "cote_moyenne": round(sum(p["cote"] for _, p in picks) / n, 3), "ic95_jours": [round(taux[50], 4), round(taux[1949], 4)]}


def calibrer_annonce(archive: list[dict]) -> dict:
    """Recalage de la probabilité ANNONCÉE du pick (le choix ne change pas), appris sur la 1re moitié des jours de l'archive
    et jugé sur la 2e (marche avant). Compare : aucun recalage / courbe unique / courbe par famille du marché choisi."""
    picks = [(m["date"], p) for m in archive if (p := pick(m, None))]
    coupe = sorted(j for j, _ in picks)[len(picks) // 2]      # coupe à la moitié des PICKS (les jours sont très inégaux)
    apprent = [p for j, p in picks if j < coupe]
    test = [p for j, p in picks if j >= coupe]
    unique = R.isotone([(p["probabilite"], int(p["gagne"])) for p in apprent], blocs=8)
    par_fam = defaultdict(list)
    for p in apprent:
        par_fam[R.famille(p["groupe"])].append((p["probabilite"], int(p["gagne"])))
    fam = {f: R.isotone(v, blocs=max(1, len(v) // 40)) if len(v) >= 80 else unique for f, v in par_fam.items()}

    def score(f):
        pr = [f(p) for p in test]
        y = [int(p["gagne"]) for p in test]
        return {"annonce": round(sum(pr) / len(pr), 4), "reel": round(sum(y) / len(y), 4),
                "brier": round(sum((a - b) ** 2 for a, b in zip(pr, y)) / len(y), 4)}
    return {"jour_de_coupe": coupe, "picks_apprentissage": len(apprent), "picks_test": len(test),
            "aucun": score(lambda p: p["probabilite"]),
            "courbe_unique": score(lambda p: R.appliquer(unique, p["probabilite"])),
            "par_famille": score(lambda p: R.appliquer(fam.get(R.famille(p["groupe"]), unique), p["probabilite"])),
            "courbe_unique_points": [[round(a, 3), round(b, 3)] for a, b in unique]}


def main() -> None:
    archive = charger_archive()
    courbes = apprendre_courbes(selections_standard(archive))
    res = {}
    for nom, c in (("sans_recalage", None), ("recalage_par_famille", courbes)):
        picks = [(m["date"], p) for m in archive if (p := pick(m, c))]
        res[nom] = resume(picks)
        print(nom, res[nom])
    res["annonce_marche_avant"] = calibrer_annonce(archive)
    print(json.dumps(res["annonce_marche_avant"], ensure_ascii=False, indent=1))
    (ROOT / "docs" / "recalage_familles.json").write_text(json.dumps({"courbes": courbes, "resultats_archive": res}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
