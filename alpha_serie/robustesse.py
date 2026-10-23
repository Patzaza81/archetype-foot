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
HORS_COUCHE: set[str] = set()   # 24/10 (calibrage par famille) : multigoals et multiscores sont réintégrés comme familles à part ; leur règle de production n'est pas modifiée

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


REJETS_COTES: list[str] = []


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
            pris, coup = (x.get("run") or {}).get("pris_le"), x.get("coup_d_envoi_utc")
            if not pris or not coup or str(pris) >= str(coup):
                REJETS_COTES.append(str(x.get("match_id") or k))   # cotes non prouvées antérieures au coup d'envoi : match écarté
                continue
            jour = str(x["date"])[:10]
            cle = str(x.get("match_id") or f"{jour}|{x.get('domicile')}|{x.get('exterieur')}")
            vus[cle] = {"id": f"archetype|{cle}", "jour": jour, "source": "archetype", "domicile": x.get("domicile"), "exterieur": x.get("exterieur"),
                        "dom": dom, "ext": ext, "cotes": x["cotes_betpawa"], "h": sc["buts_dom"], "a": sc["buts_ext"],
                        "cotes_prises_le": pris, "coup_d_envoi_utc": coup}
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


# --- Calibrage par famille de marchés (24/10/2026) ---------------------------------------------------------------
# Aucun taux de réussite commun : chaque marché (ligne précise) apprend sa propre marge sur le passé, et son verdict est jugé par rapport à
# SA propre référence (même marché, même catégorie de cote, mêmes jours, sans filtre). Les combos ont un calibrage autonome sur leur jambe la plus fragile.
FRONTIERE_VOIES = 1 / 0.72      # séparation des deux voies de cote (A : 1,25 à moins de 1,39 ; B : 1,39 et plus, sans limite haute). Sert au rangement, jamais de seuil de réussite.
Z95 = 1.96
FAMILLES = ["totaux", "buts par équipe", "BTTS", "1N2", "double chance", "handicaps", "combos", "multigoals", "multiscores"]


def famille(cle: tuple[str, str]) -> str:
    g = cle[0]
    if g == "combo":
        return "combos"
    if g in ("multigoals", "multiscores"):
        return g
    if g == "btts":
        return "BTTS"
    if g == "1x2":
        return "1N2"
    if g == "double_chance":
        return "double chance"
    if g.startswith("handicap"):
        return "handicaps"
    if g.startswith(("over_under_domicile", "over_under_exterieur", "cages_inviolees")):
        return "buts par équipe"
    return "totaux"


def voie(cote: float | None, cle: tuple[str, str] | None = None) -> str | None:
    """Catégorie de cote. Sans cote (combos, multigoals, multiscores : absents de l'archive, ou cote introuvable pour ce match) : « sans_cote »,
    valeur financière NON ÉVALUABLE. Sous 1,25 : aucune voie (cote minimale de Patrick, le pari ne peut pas être proposé)."""
    if cote is None:
        return "sans_cote"
    if cote < P.COTE_MIN:
        return None
    return "A" if cote < FRONTIERE_VOIES - 1e-12 else "B"


def lire_strategie(matchs: list[dict], cat=None) -> tuple[list[dict], int]:
    """Lecture de la stratégie sur chaque match et chaque marché (aucune cote, aucune issue lue). Parts défavorable et habituelle lues après
    retrait de chaque paire (la plus petite est gardée). Combos : mêmes parts pour CHAQUE jambe, avec sa propre règle ; la plus fragile est gardée."""
    cat = cat or catalogue()
    gr = {cle: grilles(p, z) for cle, _, p, z in cat}
    gj = {cle: [_solide_simple(jp, jz) for jp, jz in p.jambes] for cle, _, p, _ in cat if getattr(p, "jambes", None)}
    lignes, analyses = [], 0
    for m in matchs:
        prs = series(m)
        if len(prs) < P.MIN_MATCHS:
            continue
        analyses += 1
        for cle, lib, pred, _ in cat:
            n, vd, vh, loo = lire(prs, *gr[cle])
            x = {"id": m["id"], "jour": m["jour"], "cle": cle, "marche": lib, "famille": famille(cle), "n": n, "k": P.coef_k(n),
                 "v_def": vd, "v_hab": vh, "def": min(round(a / k, 4) for k, a, _ in loo), "hab": min(round(b / k, 4) for k, _, b in loo),
                 "cote": cote_reelle(m, cle) if cle[0] not in ("combo", "multigoals", "multiscores") else None, "gagne": bool(pred(m["h"], m["a"]))}
            if cle in gj:
                parts = []
                for passe, solide in gj[cle]:
                    _, _, _, lj = lire(prs, passe, solide)
                    parts.append((min(a / k for k, a, _ in lj), min(b / k for k, _, b in lj)))
                x["def_fragile"] = round(min(d for d, _ in parts), 4)
                x["hab_fragile"] = round(min(h for _, h in parts), 4)
                x["jambes"] = 2
                dc, jambe = cle[1].split("+")
                x["type_combo"] = f"{dc} + {jambe.rsplit('_', 1)[0] if jambe.startswith(('plus_', 'moins_')) else jambe}"
            lignes.append(x)
    return lignes, analyses


def _axes(x: dict) -> tuple[float, float]:
    """Ce que la règle filtre : parts du marché ; pour un combo, parts de sa jambe la plus fragile (critère propre aux combos)."""
    return (x["def_fragile"], x["hab_fragile"]) if "def_fragile" in x else (x["def"], x["hab"])


def _gain(x: dict) -> float:
    return (x["cote"] - 1) if x["gagne"] else -1.0


def _objectif_voie(v: str) -> str:
    return "rendement" if v == "B" else "reussite"


def _valeur(v: str, sel: list[dict]) -> float:
    return sum(_gain(x) for x in sel) / len(sel) if _objectif_voie(v) == "rendement" else sum(x["gagne"] for x in sel) / len(sel)


def _ecart_type(v: str, sel: list[dict]) -> float:
    n = len(sel)
    if _objectif_voie(v) == "rendement":
        g = [_gain(x) for x in sel]
        mu = sum(g) / n
        return math.sqrt(sum((y - mu) ** 2 for y in g) / max(n - 1, 1) / n)
    p = sum(x["gagne"] for x in sel) / n
    return math.sqrt(max(p * (1 - p), 1e-9) / n)


def apport(v: str, sel: list[dict], ref: list[dict]) -> tuple[float, float]:
    """(apport du filtre, borne basse à 95 %) : valeur de la sélection filtrée moins celle de la référence sans filtre (même marché, même voie).
    Réussite : borne basse de Wilson de la sélection moins le taux de la référence (juste pour les petits effectifs : 3 sur 3 ne prouve rien).
    Rendement : moyenne moins 1,96 erreur-type ; moins de 2 paris -> borne non calculable (moins l'infini)."""
    d = _valeur(v, sel) - _valeur(v, ref)
    if _objectif_voie(v) == "reussite":
        w = sum(x["gagne"] for x in sel)
        return d, wilson_bas(w, len(sel)) - _valeur(v, ref)
    if len(sel) < 2:
        return d, float("-inf")
    return d, d - Z95 * _ecart_type(v, sel)


def calibrer_marche_voie(L: list[dict], v: str) -> dict | None:
    """Apprentissage sur le passé seulement. Candidats = toutes les marges observées (part défavorable, part habituelle ; jambe la plus fragile
    pour un combo). Un candidat n'est admissible que si son apport sur « tout prendre » est positif dans CHAQUE moitié chronologique.
    Retenu : le candidat dont la borne basse de l'apport est la plus haute (ni le volume, ni un taux commun). Aucun admissible : None (pas de filtre)."""
    if len(L) < 2:
        return None
    jl = sorted({x["jour"] for x in L})
    coupe = jl[len(jl) // 2]
    moities = ([x for x in L if x["jour"] < coupe], [x for x in L if x["jour"] >= coupe])
    if not all(moities):
        return None
    ax = [_axes(x) for x in L]
    best = None
    for td in sorted({a for a, _ in ax}):
        for th in sorted({b for _, b in ax}):
            if td == 0 and th == 0:
                continue
            sel = [x for x, (a, b) in zip(L, ax) if a >= td and b >= th]
            if not sel or len(sel) == len(L):
                continue
            ok = True
            for M in moities:
                s2 = [x for x in M if _axes(x)[0] >= td and _axes(x)[1] >= th]
                if not s2 or _valeur(v, s2) <= _valeur(v, M):
                    ok = False
                    break
            if not ok:
                continue
            d, lb = apport(v, sel, L)
            if lb == float("-inf"):
                continue
            if best is None or lb > best["apport_borne_basse"]:
                best = {"marge_defavorable": td, "marge_habituelle": th, "axes": "jambe la plus fragile" if "def_fragile" in L[0] else "marché",
                        "objectif": _objectif_voie(v), "paris": len(sel), "reference": len(L),
                        "valeur": round(_valeur(v, sel), 4), "valeur_sans_filtre": round(_valeur(v, L), 4),
                        "apport": round(d, 4), "apport_borne_basse": round(lb, 4)}
    return best


def calibrer(lignes: list[dict]) -> dict:
    par: dict[tuple, list] = defaultdict(list)
    for x in lignes:
        v = voie(x["cote"], x["cle"])
        if v:
            par[(x["marche"], v)].append(x)
    return {k: calibrer_marche_voie(L, k[1]) for k, L in sorted(par.items())}


def appliquer(lignes: list[dict], regles: dict) -> list[dict]:
    """Règles GELÉES. Ne lit jamais l'issue du match."""
    out = []
    for x in lignes:
        v = voie(x["cote"], x["cle"])
        r = regles.get((x["marche"], v)) if v else None
        if r:
            a, b = _axes(x)
            if a >= r["marge_defavorable"] and b >= r["marge_habituelle"]:
                out.append({**x, "voie": v})
    return out


def _semaine(jour: str) -> str:
    d = datetime.strptime(jour, "%Y-%m-%d")
    return f"{d.isocalendar()[0]}-S{d.isocalendar()[1]:02d}"


def marche_avant(lignes: list[dict]) -> tuple[list[dict], list[dict], set]:
    """Pour chaque jour : règles apprises sur les jours STRICTEMENT antérieurs, gelées, appliquées à ce seul jour."""
    jours = sorted({x["jour"] for x in lignes})
    paris, journal = [], []
    for d in jours[1:]:
        regles = calibrer([x for x in lignes if x["jour"] < d])
        pris = appliquer([x for x in lignes if x["jour"] == d], regles)
        paris += pris
        journal.append({"jour": d, "regles": sum(1 for r in regles.values() if r), "paris": len(pris), "gagnes": sum(x["gagne"] for x in pris)})
    return paris, journal, set(jours[1:])


def _wilson(w: int, n: int) -> list[float]:
    if not n:
        return [0.0, 0.0]
    p, d = w / n, 1 + Z95 ** 2 / n
    c, r = p + Z95 ** 2 / (2 * n), Z95 * math.sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n * n))
    return [round((c - r) / d, 4), round((c + r) / d, 4)]


def indicateurs(sel: list[dict]) -> dict:
    n, w = len(sel), sum(x["gagne"] for x in sel)
    ac = [x for x in sel if x["cote"]]
    out = {"paris": n, "gagnes": w, "perdus": n - w, "reussite": round(w / n, 4) if n else None, "intervalle_95": _wilson(w, n)}
    if not n:
        return out
    if len(ac) == n:
        g = sum(_gain(x) for x in ac)
        out |= {"cote_moyenne_pre_match": round(sum(x["cote"] for x in ac) / n, 3), "gain_net": round(g, 3), "rendement": round(g / n, 4)}
    else:
        out |= {"valeur_financiere": "non évaluable (aucune cote pré-match prouvée dans l'archive)" if not ac else
                f"partielle : {len(ac)} paris sur {n} avec cote", "cote_moyenne_pre_match": None, "gain_net": None, "rendement": None}
    return out


def juger(paris_oos: list[dict], lignes: list[dict], jours_testes: set) -> dict:
    """Verdict de chaque marché (ligne précise) dans chaque voie, hors échantillon, contre SA référence sans filtre (même marché, même voie, mêmes jours).
    rejeté : apport <= 0 (le filtre ne fait pas mieux que tout prendre) ou, en voies A / sans cote, réussite <= taux de base du marché ;
    validé hors échantillon : borne basse à 95 % de l'apport > 0 ET apport > 0 dans chaque moitié chronologique ;
    prometteur : apport > 0 dans chaque moitié, borne basse <= 0 ; exploratoire : apport > 0 mais pas dans les deux moitiés (ou une moitié vide)."""
    base: dict[str, list] = defaultdict(list)
    ref: dict[tuple, list] = defaultdict(list)
    for x in lignes:
        if x["jour"] in jours_testes:
            base[x["marche"]].append(x)
            v = voie(x["cote"], x["cle"])
            if v:
                ref[(x["marche"], v)].append(x)
    par: dict[tuple, list] = defaultdict(list)
    for x in paris_oos:
        par[(x["marche"], x["voie"])].append(x)
    out = []
    for (nom, v), L in par.items():
        L.sort(key=lambda x: x["jour"])
        R_ = ref[(nom, v)]
        d, lb = apport(v, L, R_)
        h = len(L) // 2
        jc = L[h]["jour"] if L else None
        moities = []
        for part in ([x for x in L if x["jour"] < jc], [x for x in L if x["jour"] >= jc]):
            rj = {x["jour"] for x in part}
            rp = [x for x in R_ if x["jour"] in rj]
            moities.append(round(_valeur(v, part) - _valeur(v, rp), 4) if part and rp else None)
        b = base[nom]
        tb = sum(x["gagne"] for x in b) / len(b) if b else None
        taux = sum(x["gagne"] for x in L) / len(L)
        sem: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for x in L:
            sem[_semaine(x["jour"])][0] += x["gagne"]
            sem[_semaine(x["jour"])][1] += 1
        if d <= 0:
            statut, raison = "rejeté", "le filtre ne fait pas mieux que tout prendre"
        elif v != "B" and tb is not None and taux <= tb:
            statut, raison = "rejeté", f"réussite {taux:.1%} pas au-dessus du taux de base {tb:.1%}"
        elif None in moities or min(moities) <= 0:
            statut, raison = "exploratoire", "apport positif mais pas dans les deux moitiés chronologiques"
        elif lb > 0:
            statut, raison = "validé hors échantillon", "apport positif dans les deux moitiés, borne basse à 95 % au-dessus de zéro"
        else:
            statut, raison = "prometteur", "apport positif dans les deux moitiés, mais l'incertitude inclut zéro"
        out.append({"marche": nom, "famille": famille(L[0]["cle"]), "voie": v, "objectif": _objectif_voie(v), "statut": statut, "raison": raison,
                    **indicateurs(L), "sans_filtre": indicateurs(R_), "taux_de_base_marche": round(tb, 4) if tb is not None else None,
                    "apport": round(d, 4), "apport_borne_basse_95": round(lb, 4) if lb != float("-inf") else None, "apport_par_moitie": moities,
                    "par_semaine": {k: {"paris": c[1], "gagnes": c[0]} for k, c in sorted(sem.items())},
                    **({"jambes": 2, "type_combo": L[0]["type_combo"]} if "type_combo" in L[0] else {})})
    out.sort(key=lambda f: (FAMILLES.index(f["famille"]), f["marche"], f["voie"]))
    return out


def par_famille(paris: list[dict], lignes: list[dict], jours: set, verdicts: list[dict]) -> dict:
    out = {}
    for fam in FAMILLES:
        sel = [x for x in paris if x["famille"] == fam]
        tout = [x for x in lignes if x["famille"] == fam and x["jour"] in jours and voie(x["cote"], x["cle"])]
        st = defaultdict(int)
        for f in verdicts:
            if f["famille"] == fam:
                st[f["statut"]] += 1
        vs = [f for f in verdicts if f["famille"] == fam]
        n = sum(f["paris"] for f in vs)
        attendu = sum(f["paris"] * f["sans_filtre"]["reussite"] for f in vs) / n if n else None   # même mélange de marchés et de voies que les paris filtrés
        a = indicateurs(sel)
        out[fam] = {"avec_filtre": a, "reussite_attendue_sans_filtre_meme_melange": round(attendu, 4) if attendu is not None else None,
                    "apport_famille": round(a["reussite"] - attendu, 4) if attendu is not None and a["reussite"] is not None else None,
                    "toutes_lectures_sans_filtre": indicateurs(tout), "statuts": dict(st)}
    return out


def combos_par_type(paris: list[dict], lignes: list[dict], jours: set) -> dict:
    out = {}
    types = sorted({x["type_combo"] for x in lignes if "type_combo" in x})
    for t in types:
        sel = [x for x in paris if x.get("type_combo") == t]
        tout = [x for x in lignes if x.get("type_combo") == t and x["jour"] in jours]
        out[t] = {"jambes": 2, "avec_filtre": indicateurs(sel), "sans_filtre": indicateurs(tout)}
    return out


def avant_par_famille(chemin_git: str = "03e7e51:docs/alpha_robustesse_validation.json") -> dict | None:
    """Résultats de la version précédente (seuil commun de 72 %), regroupés par famille, pour la comparaison avant / après."""
    import subprocess
    try:
        old = json.loads(subprocess.run(["git", "show", chemin_git], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    except Exception:
        return None
    noms = {lib: famille(c) for c, lib, _, _ in catalogue()}
    out: dict[str, dict] = {f: {"paris": 0, "gagnes": 0, "valides": 0} for f in FAMILLES}
    for v, d in old.get("verdicts", {}).items():
        for nom, f in d.items():
            fam = noms.get(nom)
            if fam:
                out[fam]["paris"] += f["paris"]
                out[fam]["gagnes"] += f["gagnes"]
                out[fam]["valides"] += f["statut"] in ("validé", "opportunité démontrée")
    for f in out.values():
        f["reussite"] = round(f["gagnes"] / f["paris"], 4) if f["paris"] else None
    return out


def main() -> None:
    REJETS_COTES.clear()
    archetype = charger_archive_archetype()
    lignes, analyses = lire_strategie(archetype)
    jours = sorted({m["jour"] for m in archetype})
    paris_oos, journal, jt = marche_avant(lignes)
    verdicts = juger(paris_oos, lignes, jt)
    familles = par_famille(paris_oos, lignes, jt, verdicts)
    regles = calibrer(lignes)
    retenus = {(f["marche"], f["voie"]) for f in verdicts if f["statut"] in ("validé hors échantillon", "prometteur")}
    gele = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ids = [m["id"] for m in archetype]
    IDS.write_bytes(gzip.compress(json.dumps({"archetype": ids, "ecartes_cotes_non_anterieures": REJETS_COTES}).encode()))
    INTERVALLES.write_text(json.dumps({"gele_le": gele, "statut": "marges apprises sur tout l'historique, gelées, pour les seuls marchés « validé » ou « prometteur » hors échantillon",
                                       "frontiere_voies": round(FRONTIERE_VOIES, 4), "cote_min": P.COTE_MIN, "matchs_archetype": len(ids),
                                       "du": jours[0], "au": jours[-1], "empreinte_ids": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
                                       "regles": {f"{nom} | voie {v}": regles.get((nom, v)) for nom, v in sorted(retenus)}},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    rapport = {"gele_le": gele,
               "protocole": "calibrage par marché (ligne précise) et par voie de cote, marges apprises sur les jours antérieurs, jugées jour par jour "
                            "contre la référence sans filtre du même marché ; aucun taux commun ; combos calibrés sur leur jambe la plus fragile",
               "donnees": {"matchs_sans_doublon": len(ids), "matchs_analyses": analyses, "du": jours[0], "au": jours[-1],
                           "ecartes_cotes_non_anterieures_au_coup_d_envoi": len(REJETS_COTES),
                           "lectures_sous_cote_minimale": sum(1 for x in lignes if x["cote"] is not None and x["cote"] < P.COTE_MIN),
                           "lectures_sans_cote": sum(1 for x in lignes if x["cote"] is None),
                           "cotes_des_combos": "absentes de l'archive (parse_combines_betpawa.py existe, mais ses groupes ne sont pas archivés)"},
               "par_famille": familles, "combos_par_type": combos_par_type(paris_oos, lignes, jt),
               "avant_seuil_commun_72": avant_par_famille(), "verdicts": verdicts, "journal_des_jours": journal}
    RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONNEES:", rapport["donnees"])
    for fam, d in familles.items():
        a = d["avec_filtre"]
        print(f"{fam:<16} {a['paris']:>5} paris {a['reussite']} (attendu sans filtre {d['reussite_attendue_sans_filtre_meme_melange']}, apport {d['apport_famille']}) "
              f"gain {a.get('gain_net')} | {d['statuts']}")
    for f in verdicts:
        if f["statut"] in ("validé hors échantillon", "prometteur"):
            print(f"  {f['statut']:<24} {f['famille']:<15} {f['marche']:<40} {f['voie']:<9} {f['paris']:>4} {f['reussite']:.1%} "
                  f"sans filtre {f['sans_filtre']['reussite']:.1%} apport {f['apport']:+.3f} [{f['apport_borne_basse_95']}] moitiés {f['apport_par_moitie']} "
                  f"gain {f.get('gain_net')}")


if __name__ == "__main__":
    main()
