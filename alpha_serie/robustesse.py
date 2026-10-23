"""Moteur alpha — couche de robustesse par scénarios (cahier des charges figé de Patrick, 23/10/2026).

Méthode (aucune cote à l'analyse) :
1. Séries au même lieu (alpha : domicile pour l'un, extérieur pour l'autre, strictement avant le jour), appariées un à un, n = plus petit échantillon.
2. Pour chaque paire i : A = marqués du domicile, C = encaissés de l'extérieur, B = marqués de l'extérieur, D = encaissés du domicile.
     fermé = (min(A, C), min(B, D)) ; habituel = (A, B) ; ouvert = (max(A, C), max(B, D)).
3. Scénario défavorable d'un marché = le pire des 4 coins (min/max pour chaque équipe) : la paire valide le défavorable seulement si le marché
   passe dans les 4 coins SANS être « juste au seuil » (un seul but de plus ou de moins pour une équipe le ferait perdre).
   Exception : marchés « zéro but » (BTTS non, cage inviolée oui, buts d'une équipe moins de 0,5) où ce test n'a pas de sens.
4. v_def = paires qui valident le défavorable ; v_hab = paires qui valident l'habituel.
5. Référence historique : table (marché, n, v_def, v_hab) -> réussite réelle sur Football-Data (10 194 matchs). Retenu si borne basse de Wilson 95 % >= 72 %
   (seuil fixé par Patrick le 23/10/2026, 80 % jugé trop strict). Un petit groupe ne peut pas l'atteindre : l'effectif minimum se règle tout seul.
6. Stabilité : on retire chaque paire une à une et on relit la table GELÉE (cellule n-1). Retenu seulement si chaque retrait reste retenu.
   La table contient aussi n = 3, uniquement pour ce test (aucun pronostic n'est fait à 3 matchs).
7. Calibrage par marché et par intervalle de cote gagnant sur TOUS les matchs ARCHETYPE (archive de test, sans doublon) : la stratégie tourne,
   puis pour chaque marché on cherche l'intervalle de cote (cote >= 1,25) qui garde le plus de paris avec une réussite (borne Wilson) >= 72 %.
   Priorité à la fréquence de réussite ; le rendement est publié à titre d'information.
Usage : python -m alpha_serie.robustesse
"""
from __future__ import annotations

import glob
import gzip
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import coeur, parametres as P
from .marches import libelle, test_du_marche

ROOT = Path(__file__).resolve().parent.parent
BLOC = ROOT / "data" / "bloc_saisons" / "bloc_2526_2627.json.gz"
TABLE = ROOT / "data" / "alpha_serie" / "robustesse_table.json"
RAPPORT = ROOT / "docs" / "alpha_robustesse_validation.json"
INTERVALLES = ROOT / "data" / "alpha_serie" / "robustesse_intervalles.json"
IDS = ROOT / "data" / "alpha_serie" / "robustesse_matchs.json.gz"

SEUIL_WILSON = 0.72                     # décision de Patrick (23/10/2026)
Z = 1.96
GMAX = 10                              # buts lus de 0 à 10 (au-delà : ramené à 10)
N_TABLE = range(3, P.MAX_MATCHS + 1)   # 3 : stabilité seulement
HORS_COUCHE = {"multigoals", "multiscores"}   # protocole final : ils gardent leur méthode propre
MIN_PARIS_HORS_ECHANTILLON = 50          # minimum pratique avant de qualifier un marché (protocole final, 24/10/2026)

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
    jambes = {f"plus_{x}": (f"plus de {x.replace('.', ',')} buts", (lambda h, a, x=float(x): h + a > x), False) for x in ("1.5", "2.5", "3.5")}
    jambes |= {f"moins_{x}": (f"moins de {x.replace('.', ',')} buts", (lambda h, a, x=float(x): h + a < x), False) for x in ("2.5", "3.5", "4.5")}
    jambes |= {"btts_oui": ("les deux marquent", lambda h, a: h >= 1 and a >= 1, False), "btts_non": ("les deux ne marquent pas", lambda h, a: h == 0 or a == 0, True)}
    for dk, (dl, dp) in dcs.items():
        for jk, (jl, jp, jz) in jambes.items():
            pred = (lambda h, a, dp=dp, jp=jp: dp(h, a) and jp(h, a))
            pred.jambes = ((dp, False), (jp, jz))          # « juste au seuil » d'un combo = juste sur l'une de ses jambes, chacune avec sa règle
            out.append((("combo", f"{dk}+{jk}"), f"{dl} + {jl}", pred, False))
    for nom, p in coeur.GROUPES_MULTISCORES.items():
        out.append((("multiscores", nom), f"Multiscore {nom}", p, False))
    return out


def _solide_simple(pred: Pred, zero: bool):
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


def grilles(pred: Pred, zero: bool) -> tuple[list[list[bool]], list[list[bool]]]:
    """passe[h][a] et solide[h][a] (passe et pas « juste au seuil »). Combo : solide si chaque jambe est solide selon sa propre règle."""
    jambes = getattr(pred, "jambes", None)
    if not jambes:
        return _solide_simple(pred, zero)
    passe = [[bool(pred(h, a)) for a in range(GMAX + 2)] for h in range(GMAX + 2)]
    sj = [_solide_simple(p, z)[1] for p, z in jambes]
    solide = [[all(g[h][a] for g in sj) for a in range(GMAX + 1)] for h in range(GMAX + 1)]
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
    """TOUS les matchs ARCHETYPE avec historique des deux équipes, cotes BetPawa et score. Sans doublon : un match_id (ou date + équipes) une seule fois,
    on garde l'enregistrement le plus récent. Historique : assemblage figé, sinon le bloc équipe de l'archive (même règle anti-fuite)."""
    vus: dict[str, dict] = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
        for k, x in json.load(gzip.open(f)).items():
            sc = x.get("score") or {}
            if sc.get("buts_dom") is None or sc.get("buts_ext") is None or not x.get("cotes_betpawa"):
                continue
            a = x.get("assemblage") or {}
            dom = a.get("equipe_dom") if "matchs" in (a.get("equipe_dom") or {}) else x.get("equipe_dom")
            ext = a.get("equipe_ext") if "matchs" in (a.get("equipe_ext") or {}) else x.get("equipe_ext")
            if "matchs" not in (dom or {}) or "matchs" not in (ext or {}):
                continue
            jour = str(x["date"])[:10]
            cle = str(x.get("match_id") or f"{jour}|{x.get('domicile')}|{x.get('exterieur')}")
            vus[cle] = {"id": f"archetype|{cle}", "jour": jour, "source": "archetype", "domicile": x.get("domicile"), "exterieur": x.get("exterieur"),
                        "dom": dom, "ext": ext, "cotes": x["cotes_betpawa"], "h": sc["buts_dom"], "a": sc["buts_ext"]}
    par_equipes: dict[tuple, dict] = {}
    for m in vus.values():                                   # deuxième garde : même jour et mêmes équipes sous deux identifiants
        par_equipes[(m["jour"], m["domicile"], m["exterieur"])] = m
    return sorted(par_equipes.values(), key=lambda m: (m["jour"], m["id"]))


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
    jours = [m["jour"] for m in matchs if m["id"] in set(ids)]
    return {"gele_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "regle": f"borne basse de Wilson 95 % >= {SEUIL_WILSON:.0%}",
            "matchs_reglage": len(ids), "du": min(jours), "au": max(jours), "empreinte_ids": empreinte, "ids": ids, "cellules": table}


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


def lire_strategie(matchs: list[dict], cat=None) -> tuple[list[dict], int]:
    """Fait tourner la lecture de la stratégie sur chaque match et chaque marché (aucune cote à la lecture).
    Pour chaque marché : part défavorable et part habituelle, et leur plus petite valeur après le retrait de chaque paire (stabilité)."""
    cat = cat or catalogue()
    gr = {cle: grilles(p, z) for cle, _, p, z in cat}
    lignes, analyses = [], 0
    for m in matchs:
        prs = series(m)
        if len(prs) < P.MIN_MATCHS:
            continue
        analyses += 1
        for cle, lib, pred, _ in cat:
            if cle[0] in HORS_COUCHE:
                continue
            n, vd, vh, loo = lire(prs, *gr[cle])
            lignes.append({"id": m["id"], "jour": m["jour"], "cle": cle, "marche": lib, "n": n, "k": P.coef_k(n), "v_def": vd, "v_hab": vh,
                           "def": min(round(x / k, 4) for k, x, _ in loo), "hab": min(round(y / k, 4) for k, _, y in loo),
                           "cote": cote_reelle(m, cle), "gagne": bool(pred(m["h"], m["a"]))})
    return lignes, analyses


def _meilleur_intervalle(pts: list[tuple[float, int]]):
    """pts triés par cote. Intervalle [bas, haut] (bornes = cotes observées, sans couper une même cote) qui garde le plus de paris
    avec une borne de Wilson >= 72 % ; à égalité, la meilleure réussite."""
    cotes = sorted({c for c, _ in pts})
    par = {c: [0, 0] for c in cotes}
    for c, g in pts:
        par[c][0] += g
        par[c][1] += 1
    best = None
    for i in range(len(cotes)):
        s = n = 0
        for j in range(i, len(cotes)):
            s += par[cotes[j]][0]
            n += par[cotes[j]][1]
            if wilson_bas(s, n) >= SEUIL_WILSON and (best is None or (n, s / n) > (best[2], best[3] / best[2])):
                best = (cotes[i], cotes[j], n, s)
    return best


def _tient_dans_chaque_moitie(sel, td, th, bas, haut, coupe) -> bool:
    """Garde anti-hasard (même principe que calibration.py) : la règle doit garder au moins 72 % de réussite dans CHAQUE moitié chronologique."""
    for moitie in (lambda j: j < coupe, lambda j: j >= coupe):
        g = [x["gagne"] for x in sel if moitie(x["jour"]) and (bas is None or (x["cote"] and bas <= x["cote"] <= haut))]
        if not g or sum(g) / len(g) < SEUIL_WILSON:
            return False
    return True


def calibrer_marche(L: list[dict]) -> dict:
    """Règle d'un marché, apprise sur les données : seuil de part défavorable, seuil de part habituelle (valeurs réellement observées,
    lues après retrait d'une paire) et, si le marché a des cotes, intervalle de cote gagnant (cote >= 1,25).
    On garde la règle qui retient le plus de paris avec une borne de Wilson >= 72 % ET au moins 72 % dans chaque moitié chronologique ;
    à égalité, la meilleure réussite. Aucune : marché écarté."""
    avec_cotes = any(x["cote"] for x in L)
    jl = sorted({x["jour"] for x in L})
    coupe = jl[len(jl) // 2]
    seuils_d = sorted({x["def"] for x in L})
    seuils_h = sorted({x["hab"] for x in L})
    best = None
    for td in seuils_d:
        Ld = [x for x in L if x["def"] >= td]
        for th in seuils_h:
            sel = [x for x in Ld if x["hab"] >= th]
            if not sel:
                break
            if avec_cotes:
                pts = [(x["cote"], int(x["gagne"])) for x in sel if x["cote"] and x["cote"] >= P.COTE_MIN]
                if not pts:
                    continue
                r = _meilleur_intervalle(pts)
                if r is None:
                    continue
                bas, haut, n, s = r
            else:
                n, s = len(sel), sum(x["gagne"] for x in sel)
                if wilson_bas(s, n) < SEUIL_WILSON:
                    continue
                bas = haut = None
            if not _tient_dans_chaque_moitie(sel, td, th, bas, haut, coupe):
                continue
            if best is None or (n, s / n) > (best["paris"], best["reussite"]):
                best = {"part_defavorable_min": td, "part_habituelle_min": th, "cote_bas": bas, "cote_haut": haut,
                        "paris": n, "gagnes": s, "reussite": round(s / n, 4), "wilson_bas": round(wilson_bas(s, n), 4)}
    return {"avec_cotes": avec_cotes, "regle": best}


def calibrer(lignes: list[dict]) -> dict:
    par: dict[str, list] = defaultdict(list)
    for x in lignes:
        par[x["marche"]].append(x)
    return {nom: calibrer_marche(L) for nom, L in sorted(par.items())}


def appliquer(lignes: list[dict], regles: dict) -> list[dict]:
    out = []
    for x in lignes:
        r = (regles.get(x["marche"]) or {}).get("regle")
        if not r or x["def"] < r["part_defavorable_min"] or x["hab"] < r["part_habituelle_min"]:
            continue
        if r["cote_bas"] is not None and not (x["cote"] and r["cote_bas"] <= x["cote"] <= r["cote_haut"]):
            continue
        out.append(x)
    return out


def bilan(paris: list[dict]) -> dict:
    n, w = len(paris), sum(p["gagne"] for p in paris)
    ac = [p for p in paris if p["cote"]]
    par: dict[str, list] = defaultdict(list)
    for p in paris:
        par[p["marche"]].append(p)
    return {"paris": n, "reussite": round(w / n, 4) if n else None, "avec_cote": len(ac),
            "rendement": round(sum((p["cote"] - 1) if p["gagne"] else -1 for p in ac) / len(ac), 4) if ac else None,
            "par_marche": {k: {"paris": len(v), "reussite": round(sum(x["gagne"] for x in v) / len(v), 4),
                               "cote_moyenne": round(sum(x["cote"] for x in v if x["cote"]) / max(1, sum(1 for x in v if x["cote"])), 3)}
                           for k, v in sorted(par.items(), key=lambda kv: -len(kv[1]))}}


def _semaine(jour: str) -> str:
    d = datetime.strptime(jour, "%Y-%m-%d")
    return f"{d.isocalendar()[0]}-S{d.isocalendar()[1]:02d}"


def marche_avant(lignes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validation chronologique répétée : pour chaque jour testé, les règles sont apprises sur les jours STRICTEMENT antérieurs, gelées,
    puis appliquées à ce seul jour. Renvoie (paris hors échantillon, journal des jours)."""
    jours = sorted({x["jour"] for x in lignes})
    paris, journal = [], []
    for d in jours[1:]:
        regles = calibrer([x for x in lignes if x["jour"] < d])
        jour = [x for x in lignes if x["jour"] == d]
        pris = appliquer(jour, regles)
        paris += pris
        journal.append({"jour": d, "marches_avec_regle": sum(1 for v in regles.values() if v["regle"]), "paris": len(pris),
                        "gagnes": sum(x["gagne"] for x in pris)})
    return paris, journal


def juger(paris_oos: list[dict], lignes: list[dict]) -> dict:
    """Verdict par marché sur les paris hors échantillon seulement.
    validé : au moins 50 paris, réussite >= 72 %, >= 72 % dans chaque moitié chronologique de ses paris, et au-dessus du taux de base du marché
    (tous les matchs analysés des mêmes jours). exploratoire : moins de 50 paris. rejeté : sinon."""
    jours_testes = {x["jour"] for x in paris_oos} | {x["jour"] for x in lignes if x["jour"] > min(x["jour"] for x in lignes)}
    base: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for x in lignes:
        if x["jour"] in jours_testes:
            base[x["marche"]][0] += x["gagne"]
            base[x["marche"]][1] += 1
    par: dict[str, list] = defaultdict(list)
    for x in paris_oos:
        par[x["marche"]].append(x)
    out = {}
    for nom, L in sorted(par.items(), key=lambda kv: -len(kv[1])):
        L.sort(key=lambda x: x["jour"])
        n, w = len(L), sum(x["gagne"] for x in L)
        b = base[nom][0] / base[nom][1] if base[nom][1] else None
        moitie = n // 2
        m1, m2 = L[:moitie], L[moitie:]
        t1 = sum(x["gagne"] for x in m1) / len(m1) if m1 else None
        t2 = sum(x["gagne"] for x in m2) / len(m2) if m2 else None
        sem: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for x in L:
            sem[_semaine(x["jour"])][0] += x["gagne"]
            sem[_semaine(x["jour"])][1] += 1
        ac = [x for x in L if x["cote"]]
        taux = w / n
        if n < MIN_PARIS_HORS_ECHANTILLON:
            statut, raison = "exploratoire", f"{n} paris hors échantillon, minimum {MIN_PARIS_HORS_ECHANTILLON}"
        elif taux < SEUIL_WILSON:
            statut, raison = "rejeté", f"réussite hors échantillon {taux:.1%} sous 72 %"
        elif t1 is None or t2 is None or min(t1, t2) < SEUIL_WILSON:
            statut, raison = "rejeté", f"incohérent entre périodes ({t1:.0%} puis {t2:.0%})"
        elif b is not None and taux <= b:
            statut, raison = "rejeté", f"aucun gain de sélection ({taux:.1%} contre {b:.1%} de base)"
        else:
            statut, raison = "validé", f"{taux:.1%} hors échantillon, base {b:.1%}, {t1:.0%} puis {t2:.0%}"
        out[nom] = {"statut": statut, "raison": raison, "paris": n, "gagnes": w, "perdus": n - w, "reussite": round(taux, 4),
                    "base": round(b, 4) if b is not None else None, "gain_selection": round(taux - b, 4) if b is not None else None,
                    "premiere_moitie": round(t1, 4) if t1 is not None else None, "seconde_moitie": round(t2, 4) if t2 is not None else None,
                    "wilson_bas_indicatif": round(wilson_bas(w, n), 4), "par_semaine": {k: {"paris": v[1], "gagnes": v[0]} for k, v in sorted(sem.items())},
                    "avec_cote": len(ac), "cote_moyenne": round(sum(x["cote"] for x in ac) / len(ac), 3) if ac else None,
                    "rendement_indicatif": round(sum((x["cote"] - 1) if x["gagne"] else -1 for x in ac) / len(ac), 4) if ac else None}
    return out


def main() -> None:
    archetype = charger_archive_archetype()
    lignes, analyses = lire_strategie(archetype)
    jours = sorted({m["jour"] for m in archetype})
    paris_oos, journal = marche_avant(lignes)
    verdicts = juger(paris_oos, lignes)
    valides = sorted(k for k, v in verdicts.items() if v["statut"] == "validé")
    regles_finales = calibrer(lignes)                              # règles apprises sur tout l'historique, gelées pour la suite
    regles_gelees = {k: regles_finales[k] for k in valides if regles_finales.get(k, {}).get("regle")}
    gele = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ids = [m["id"] for m in archetype]
    IDS.write_bytes(gzip.compress(json.dumps({"archetype": ids}).encode()))
    INTERVALLES.write_text(json.dumps({"gele_le": gele, "statut": "règles gelées des seuls marchés validés hors échantillon",
                                       "seuil": SEUIL_WILSON, "cote_min": P.COTE_MIN, "min_paris_hors_echantillon": MIN_PARIS_HORS_ECHANTILLON,
                                       "matchs_archetype": len(ids), "matchs_analyses": analyses, "du": jours[0], "au": jours[-1],
                                       "empreinte_ids": hashlib.sha256("\n".join(ids).encode()).hexdigest(), "regles": regles_gelees},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    n, w = len(paris_oos), sum(x["gagne"] for x in paris_oos)
    vp = [x for x in paris_oos if x["marche"] in valides]
    rapport = {"gele_le": gele, "protocole": "validation chronologique répétée jour par jour (règles apprises sur les jours antérieurs, gelées, appliquées au jour suivant)",
               "archetype": {"matchs_sans_doublon": len(ids), "matchs_analyses": analyses, "du": jours[0], "au": jours[-1]},
               "hors_echantillon_tous_marches": {"paris": n, "gagnes": w, "reussite": round(w / n, 4) if n else None},
               "hors_echantillon_marches_valides": {"paris": len(vp), "gagnes": sum(x["gagne"] for x in vp),
                                                    "reussite": round(sum(x["gagne"] for x in vp) / len(vp), 4) if vp else None},
               "marches_valides": valides,
               "verdicts": verdicts, "journal_des_jours": journal,
               "abstentions": {"jours_sans_aucun_pari": sum(1 for j in journal if not j["paris"])}}
    RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ARCHETYPE:", len(ids), "matchs,", analyses, "analysés,", jours[0], "->", jours[-1])
    print("HORS ECHANTILLON (tous):", rapport["hors_echantillon_tous_marches"])
    print("VALIDES:", valides, rapport["hors_echantillon_marches_valides"])
    for k, v in verdicts.items():
        print(f"  {v['statut']:<12} {k:<38} {v['paris']:>4} paris {v['reussite']:.1%} base {v['base']} | {v['raison']}")


if __name__ == "__main__":
    main()
