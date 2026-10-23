"""Moteur alpha — couche de robustesse par scénarios (cahier des charges figé de Patrick, 23/10/2026).

Méthode (aucune cote à l'analyse) :
1. Séries au même lieu (alpha : domicile pour l'un, extérieur pour l'autre, strictement avant le jour), appariées un à un, n = plus petit échantillon.
2. Pour chaque paire i : A = marqués du domicile, C = encaissés de l'extérieur, B = marqués de l'extérieur, D = encaissés du domicile.
     fermé = (min(A, C), min(B, D)) ; habituel = (A, B) ; ouvert = (max(A, C), max(B, D)).
3. Scénario défavorable d'un marché = le pire des 4 coins (min/max pour chaque équipe) : la paire valide le défavorable seulement si le marché
   passe dans les 4 coins SANS être « juste au seuil » (un seul but de plus ou de moins pour une équipe le ferait perdre).
   Exception : marchés « zéro but » (BTTS non, cage inviolée oui, buts d'une équipe moins de 0,5) où ce test n'a pas de sens.
4. v_def = paires qui valident le défavorable ; v_hab = paires qui valident l'habituel.
5. Référence historique : table (marché, n, v_def, v_hab) -> réussite réelle sur l'échantillon de réglage. Retenu si borne basse de Wilson 95 % >= 80 %
   (80 % = 1 / 1,25, la cote minimale de Patrick). Un petit groupe ne peut pas l'atteindre : l'effectif minimum se règle tout seul.
6. Stabilité : on retire chaque paire une à une et on relit la table GELÉE (cellule n-1). Retenu seulement si chaque retrait reste retenu.
   La table contient aussi n = 3, uniquement pour ce test (aucun pronostic n'est fait à 3 matchs).
Usage : python -m alpha_serie.robustesse  (réglage sur la saison 2526, validation unique sur 2627 + archive ARCHETYPE)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import calibration as C, coeur, parametres as P
from .marches import libelle, test_du_marche

ROOT = Path(__file__).resolve().parent.parent
BLOC = ROOT / "data" / "bloc_saisons" / "bloc_2526_2627.json.gz"
TABLE = ROOT / "data" / "alpha_serie" / "robustesse_table.json"
RAPPORT = ROOT / "docs" / "alpha_robustesse_validation.json"

SEUIL_WILSON = 1 / P.COTE_MIN          # 0,80
Z = 1.96
GMAX = 10                              # buts lus de 0 à 10 (au-delà : ramené à 10)
N_TABLE = range(3, P.MAX_MATCHS + 1)   # 3 : stabilité seulement

Pred = Callable[[int, int], bool]


# --- Catalogue : tous les marchés de l'alpha + combos double chance -------------------------------------------------
def catalogue(params: dict | None = None) -> list[tuple[tuple[str, str], str, Pred, bool]]:
    """(clé, libellé, condition, exempté du test « juste au seuil »)."""
    params = params or P.charger()
    out = []
    for items in coeur.CATALOGUE.values():
        for g, s in items:
            p = test_du_marche(g, s)
            if p is None:
                continue
            zero = (g, s) in {("btts", "Non"), ("cages_inviolees_domicile", "oui"), ("cages_inviolees_exterieur", "oui"),
                              ("over_under_domicile_0.5", "moins"), ("over_under_exterieur_0.5", "moins")}
            out.append(((g, s), libelle(g, s), p, zero))
    for lo, hi in params["multigoals"]["plages"]:
        out.append((("multigoals", f"{lo}-{hi}"), f"Multigoals {lo}-{hi}", (lambda h, a, lo=lo, hi=hi: lo <= h + a <= hi), False))
    dcs = {"1N": ("Domicile ne perd pas", lambda h, a: h >= a), "N2": ("Extérieur ne perd pas", lambda h, a: h <= a), "12": ("Pas de nul", lambda h, a: h != a)}
    jambes = {f"plus_{x}": (f"plus de {x.replace('.', ',')} buts", (lambda h, a, x=float(x): h + a > x)) for x in ("1.5", "2.5", "3.5")}
    jambes |= {f"moins_{x}": (f"moins de {x.replace('.', ',')} buts", (lambda h, a, x=float(x): h + a < x)) for x in ("2.5", "3.5", "4.5")}
    jambes |= {"btts_oui": ("les deux marquent", lambda h, a: h >= 1 and a >= 1), "btts_non": ("les deux ne marquent pas", lambda h, a: h == 0 or a == 0)}
    for dk, (dl, dp) in dcs.items():
        for jk, (jl, jp) in jambes.items():
            out.append((("combo", f"{dk}+{jk}"), f"{dl} + {jl}", (lambda h, a, dp=dp, jp=jp: dp(h, a) and jp(h, a)), False))
    for nom, p in coeur.GROUPES_MULTISCORES.items():
        out.append((("multiscores", nom), f"Multiscore {nom}", p, False))
    return out


def grilles(pred: Pred, zero: bool) -> tuple[list[list[bool]], list[list[bool]]]:
    """passe[h][a] et solide[h][a] (passe et pas « juste au seuil »)."""
    passe = [[bool(pred(h, a)) for a in range(GMAX + 2)] for h in range(GMAX + 2)]
    solide = [[False] * (GMAX + 1) for _ in range(GMAX + 1)]
    for h in range(GMAX + 1):
        for a in range(GMAX + 1):
            if not passe[h][a]:
                continue
            if zero:
                solide[h][a] = True
                continue
            voisins = [(h + 1, a), (h, a + 1)] + ([(h - 1, a)] if h else []) + ([(h, a - 1)] if a else [])
            solide[h][a] = all(passe[x][y] for x, y in voisins)
    return passe, solide


def _c(x: int) -> int:
    return min(max(int(x), 0), GMAX)


def paires(hm: list[int], hc: list[int], am: list[int], ac: list[int]) -> list[tuple[int, int, int, int]]:
    """(A, C, B, D) par paire, n derniers matchs de chaque équipe appariés un à un."""
    n = min(len(hm), len(am))
    return [(_c(hm[-n:][i]), _c(ac[-n:][i]), _c(am[-n:][i]), _c(hc[-n:][i])) for i in range(n)]


def lecture_paire(pr: tuple[int, int, int, int], passe, solide) -> tuple[int, int]:
    """(valide le défavorable ?, valide l'habituel ?) pour une paire."""
    A, Cc, B, D = pr
    hs, as_ = (min(A, Cc), max(A, Cc)), (min(B, D), max(B, D))
    dfv = all(solide[h][a] for h in hs for a in as_)
    return int(dfv), int(passe[A][B])


def lire(prs: list, passe, solide) -> tuple[int, int, int, list[tuple[int, int, int]]]:
    """n, v_def, v_hab et, pour chaque retrait d'une paire, (n-1, v_def', v_hab')."""
    lp = [lecture_paire(p, passe, solide) for p in prs]
    vd, vh = sum(x for x, _ in lp), sum(y for _, y in lp)
    loo = [(len(lp) - 1, vd - x, vh - y) for x, y in lp]
    return len(lp), vd, vh, loo


def wilson_bas(s: int, n: int) -> float:
    if n == 0:
        return 0.0
    p = s / n
    d = 1 + Z * Z / n
    c = p + Z * Z / (2 * n)
    r = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return (c - r) / d


def cle_cellule(cle: tuple[str, str], n: int, vd: int, vh: int) -> str:
    return f"{cle[0]}|{cle[1]}|{n}|{vd}|{vh}"


# --- Données -------------------------------------------------------------------------------------------------------
def charger_bloc() -> list[dict]:
    """Matchs du bloc Football-Data avec les deux équipes reconstituées (matchs strictement antérieurs, même division)."""
    liste = sorted(json.load(gzip.open(BLOC))["liste"], key=lambda m: (m["date"], m["id"]))
    equipes: dict[tuple, list] = defaultdict(list)
    for m in liste:
        equipes[(m["division"], m["domicile"])].append({"date": m["date"], "domicile": True, "buts_marques": m["buts_dom"], "buts_encaisses": m["buts_ext"]})
        equipes[(m["division"], m["exterieur"])].append({"date": m["date"], "domicile": False, "buts_marques": m["buts_ext"], "buts_encaisses": m["buts_dom"]})
    out = []
    for m in liste:
        if m.get("buts_dom") is None or m.get("buts_ext") is None:
            continue
        out.append({"id": m["id"], "saison": m["saison"], "jour": m["date"], "source": "football-data",
                    "dom": {"matchs": equipes[(m["division"], m["domicile"])]}, "ext": {"matchs": equipes[(m["division"], m["exterieur"])]},
                    "h": m["buts_dom"], "a": m["buts_ext"], "cotes_fd": m.get("cotes") or {}})
    return out


def charger_archive_archetype() -> list[dict]:
    out = []
    for i, m in enumerate(C.charger_archive()):
        out.append({**m, "id": f"archetype|{m['jour']}|{i}", "source": "archetype"})
    return out


def series(m: dict) -> list:
    hm, hc = coeur.serie_lieu(m["dom"], True, m["jour"])
    am, ac = coeur.serie_lieu(m["ext"], False, m["jour"])
    return paires(hm, hc, am, ac)


# --- Réglage : construction de la table ----------------------------------------------------------------------------
def construire_table(matchs: list[dict], cat=None) -> dict:
    cat = cat or catalogue()
    gr = {cle: grilles(p, z) for cle, _, p, z in cat}
    cellules: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    ids = []
    for m in matchs:
        prs = series(m)
        if len(prs) < min(N_TABLE):
            continue
        ids.append(m["id"])
        for cle, _, p, _ in cat:
            passe, solide = gr[cle]
            n, vd, vh, _ = lire(prs, passe, solide)
            c = cellules[cle_cellule(cle, n, vd, vh)]
            c[0] += int(bool(p(m["h"], m["a"])))
            c[1] += 1
    table = {}
    for k, (s, t) in cellules.items():
        lb = wilson_bas(s, t)
        table[k] = {"succes": s, "total": t, "reussite": round(s / t, 4), "wilson_bas": round(lb, 4), "retenu": lb >= SEUIL_WILSON}
    empreinte = hashlib.sha256("\n".join(ids).encode()).hexdigest()
    return {"gele_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "regle": "borne basse de Wilson 95 % >= 1/1,25",
            "matchs_reglage": len(ids), "du": min(m["jour"] for m in matchs), "au": max(m["jour"] for m in matchs),
            "empreinte_ids": empreinte, "cellules": table}


# --- Verdict -------------------------------------------------------------------------------------------------------
def verdict(prs: list, cle, passe, solide, cellules: dict) -> dict:
    n, vd, vh, loo = lire(prs, passe, solide)
    ref = cellules.get(cle_cellule(cle, n, vd, vh))
    out = {"n": n, "v_def": vd, "v_hab": vh, "reference": ref}
    if n < P.MIN_MATCHS:
        return {**out, "statut": "exclu", "raison": "échantillon insuffisant"}
    if not ref or not ref["retenu"]:
        return {**out, "statut": "abstention", "raison": "référence historique sous 80 % (borne Wilson) ou absente"}
    for n2, vd2, vh2 in loo:
        r2 = cellules.get(cle_cellule(cle, n2, vd2, vh2))
        if not r2 or not r2["retenu"]:
            return {**out, "statut": "instable", "raison": f"un retrait de paire fait tomber le verdict ({vd2}/{n2} défavorable, {vh2}/{n2} habituel)"}
    return {**out, "statut": "retenu", "raison": f"tient dans le défavorable ({vd}/{n}), l'habituel ({vh}/{n}) et à chaque retrait"}


def analyser(m: dict, cellules: dict, cat=None, gr=None) -> list[dict]:
    """Marchés RETENUS pour un match (les autres ne sont pas affichés)."""
    cat = cat or catalogue()
    gr = gr or {cle: grilles(p, z) for cle, _, p, z in cat}
    prs = series(m)
    res = []
    for cle, lib, p, _ in cat:
        v = verdict(prs, cle, *gr[cle], cellules)
        if v["statut"] == "retenu":
            res.append({"cle": cle, "marche": lib, **v})
    return res


# --- Cotes réelles (évaluation seulement) --------------------------------------------------------------------------
def cote_reelle(m: dict, cle: tuple[str, str]) -> float | None:
    g, s = cle
    if m["source"] == "archetype":
        return coeur.cote_de(m.get("cotes"), cle)
    fd = m.get("cotes_fd") or {}
    if g == "1x2" and "1x2_cloture" in fd:
        v = (fd["1x2_cloture"].get("moy") or [None] * 3)[{"1": 0, "N": 1, "2": 2}[s]]
        return v if v and v > 1 else None
    if g == "over_under_2.5" and "plus_moins_2_5_cloture" in fd:
        v = (fd["plus_moins_2_5_cloture"].get("moy") or [None] * 2)[0 if s == "plus" else 1]
        return v if v and v > 1 else None
    if g.startswith("handicap_") and "handicap_asiatique_ouverture" in fd:
        ah = fd["handicap_asiatique_ouverture"]
        try:
            if float(ah.get("ligne_domicile")) == float(g.split("_")[1]):
                v = (ah.get("moy") or [None] * 2)[0 if s == "domicile" else 1]
                return v if v and v > 1 else None
        except (TypeError, ValueError):
            return None
    return None


def valider(matchs: list[dict], cellules: dict) -> dict:
    cat = catalogue()
    gr = {cle: grilles(p, z) for cle, _, p, z in cat}
    par: dict[str, dict] = {}
    base: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    analyses = abstentions = 0
    for m in matchs:
        prs = series(m)
        if len(prs) < P.MIN_MATCHS:
            continue
        analyses += 1
        ret = analyser(m, cellules, cat, gr)
        if not ret:
            abstentions += 1
        for cle, lib, p, _ in cat:
            b = base[lib]
            b[0] += int(bool(p(m["h"], m["a"])))
            b[1] += 1
        for r in ret:
            lib = r["marche"]
            d = par.setdefault(lib, {"marche": lib, "n": 0, "gagnes": 0, "avec_cote": 0, "gain_net": 0.0, "somme_cotes": 0.0})
            g = bool(dict((c, p) for c, _, p, _ in cat)[r["cle"]](m["h"], m["a"]))
            d["n"] += 1
            d["gagnes"] += g
            c = cote_reelle(m, r["cle"])
            if c:
                d["avec_cote"] += 1
                d["somme_cotes"] += c
                d["gain_net"] += (c - 1) if g else -1
    lignes = []
    for d in sorted(par.values(), key=lambda x: -x["n"]):
        b = base[d["marche"]]
        lignes.append({"marche": d["marche"], "propositions": d["n"], "reussite": round(d["gagnes"] / d["n"], 4),
                       "base": round(b[0] / b[1], 4) if b[1] else None, "avec_cote": d["avec_cote"],
                       "cote_moyenne": round(d["somme_cotes"] / d["avec_cote"], 3) if d["avec_cote"] else None,
                       "rendement": round(d["gain_net"] / d["avec_cote"], 4) if d["avec_cote"] else None})
    tot_n = sum(x["propositions"] for x in lignes)
    tot_g = sum(round(x["reussite"] * x["propositions"]) for x in lignes)
    ac = sum(par[x["marche"]]["avec_cote"] for x in lignes)
    gn = sum(par[x["marche"]]["gain_net"] for x in lignes)
    return {"matchs_analyses": analyses, "matchs_sans_aucun_marche": abstentions, "propositions": tot_n,
            "reussite": round(tot_g / tot_n, 4) if tot_n else None, "avec_cote": ac, "rendement": round(gn / ac, 4) if ac else None,
            "marches": lignes}


def main() -> None:
    bloc = charger_bloc()
    reglage = [m for m in bloc if m["saison"] == "2526"]
    validation_fd = [m for m in bloc if m["saison"] == "2627"]
    table = construire_table(reglage)
    TABLE.write_text(json.dumps(table, ensure_ascii=False, indent=0), encoding="utf-8")
    cel = table["cellules"]
    archetype = charger_archive_archetype()
    rapport = {"reglage": {k: table[k] for k in ("gele_le", "matchs_reglage", "du", "au", "empreinte_ids", "regle")},
               "cellules_retenues": sum(1 for c in cel.values() if c["retenu"]), "cellules": len(cel),
               "validation_football_data_2627": valider(validation_fd, cel),
               "validation_archive_archetype": valider(archetype, cel)}
    RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rapport.items() if not k.startswith("validation")}, ensure_ascii=False))
    for k in ("validation_football_data_2627", "validation_archive_archetype"):
        v = rapport[k]
        print(f"== {k}: {v['matchs_analyses']} matchs, {v['matchs_sans_aucun_marche']} sans marché, {v['propositions']} propositions, "
              f"réussite {v['reussite']}, rendement {v['rendement']} sur {v['avec_cote']} cotes")
        for x in v["marches"][:25]:
            print("  ", x)


if __name__ == "__main__":
    main()
