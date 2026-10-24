"""Moteur alpha — couche de robustesse par scénarios : lecture de la stratégie et calibrage par famille de marchés (état au 24/10/2026).

LECTURE (aucune cote, aucune issue) :
1. Séries au même lieu (domicile pour l'un, extérieur pour l'autre, strictement avant le jour du match), 4 à 7 matchs, appariées un à un.
2. Paire i : A = marqués du domicile, C = encaissés de l'extérieur, B = marqués de l'extérieur, D = encaissés du domicile.
   fermé = (min(A, C), min(B, D)) ; habituel = (A, B) ; ouvert = (max(A, C), max(B, D)).
3. Défavorable = pire des 4 coins (égal au coin propre au marché pour les marchés monotones, prouvé par test) ; une validation « juste au seuil »
   compte comme échec (exemptés : BTTS non, cage inviolée oui, buts d'une équipe moins de 0,5). Combos : juste si une jambe est juste, selon sa règle.
4. Parts défavorable et habituelle lues après retrait de chaque paire (la plus petite est gardée). Combos : mêmes parts pour leur jambe la plus fragile.
   Coefficient k de l'alpha conservé dans chaque lecture, sans rôle de preuve.

CALIBRAGE (`main`) :
5. Matchs ARCHETYPE sans doublon, cotes prises avant le coup d'envoi uniquement. Familles : totaux, buts par équipe, BTTS, 1N2, double chance,
   handicaps, combos, multigoals, multiscores ; chaque ligne précise est un marché à part.
6. Voies : A (cote 1,25 à moins de 1,39), B (1,39 et plus, sans limite haute, objectif rendement), sans_cote (combos, multigoals, multiscores),
   cote_manquante (marché simple sans cote pour ce match, voie séparée). Sous 1,25 : non proposable. Aucun taux de réussite commun.
7. Marges apprises par marché et par voie sur le passé (candidats = valeurs observées, admissibles si meilleures que « tout prendre » dans chaque
   moitié, classées par l'écart avec les paris non retenus).
8. Développement : validation jour par jour. Période réservée = dernier tiers des jours, jamais utilisée pour choisir : règles du développement gelées,
   appliquées une fois. Tests exacts (Fisher, permutation) sélection contre paris non retenus ; faux positifs contrôlés par Benjamini-Hochberg 5 %.
   Statuts : rejeté, exploratoire, non confirmé, prometteur, validé hors échantillon.
L'ancienne version (table Football-Data, 80 %) reste dans `construire_table` / `verdict`, à titre de référence, non utilisée par `main`.
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


ETUDIES_SANS_COTE = {"combo", "multigoals", "multiscores"}   # groupes sans aucune cote dans l'archive : étudiés sur la réussite seule


def voie(cote: float | None, cle: tuple[str, str] | None = None) -> str | None:
    """Catégorie d'un pari.
    A : cote de 1,25 à moins de 1,39 ; B : 1,39 et plus, sans limite haute ;
    sans_cote : combos, multigoals, multiscores (aucune cote archivée pour ces groupes) ;
    cote_manquante : marché SIMPLE dont la cote manque pour ce match (voie séparée, jamais mélangée aux deux autres) ;
    None : cote sous 1,25 (le pari ne peut pas être proposé). Valeur financière non évaluable pour sans_cote et cote_manquante."""
    if cote is None:
        return "sans_cote" if cle and cle[0] in ETUDIES_SANS_COTE else "cote_manquante"
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


def apport(v: str, sel: list[dict], ref: list[dict]) -> float:
    """Apport affiché : valeur de la sélection moins celle de la référence sans filtre (même marché, même voie, mêmes jours)."""
    return _valeur(v, sel) - _valeur(v, ref)


def test_selection(v: str, sel: list[dict], ref: list[dict]) -> tuple[float, float]:
    """Comparaison correcte : la sélection est INCLUSE dans la référence, on la compare donc aux paris NON retenus (groupes disjoints).
    Statistique z (deux proportions ; rendement : Welch) servant SEULEMENT à classer les marges candidates à l'apprentissage.
    Les verdicts utilisent `p_exacte` (Fisher / permutation), valable pour les petits effectifs. Aucun pari non retenu : (0, 1)."""
    ids = {id(x) for x in sel}
    non = [x for x in ref if id(x) not in ids]
    if not sel or not non:
        return 0.0, 1.0
    if _objectif_voie(v) == "reussite":
        n1, n2 = len(sel), len(non)
        p1, p2 = sum(x["gagne"] for x in sel) / n1, sum(x["gagne"] for x in non) / n2
        pp = (p1 * n1 + p2 * n2) / (n1 + n2)
        se = math.sqrt(max(pp * (1 - pp), 1e-12) * (1 / n1 + 1 / n2))
        z = (p1 - p2) / se
    else:
        if len(sel) < 2 or len(non) < 2:
            return 0.0, 1.0
        z = (_valeur(v, sel) - _valeur(v, non)) / math.sqrt(_ecart_type(v, sel) ** 2 + _ecart_type(v, non) ** 2 + 1e-12)
    return z, 0.5 * math.erfc(z / math.sqrt(2))


def p_exacte(v: str, sel: list[dict], ref: list[dict], tirages: int = 10000) -> float:
    """p unilatérale (sélection meilleure que les paris NON retenus), valable pour les petits effectifs.
    Réussite : test exact de Fisher (loi hypergéométrique). Rendement : test de permutation (graine fixe 0, résultat reproductible).
    Aucun pari non retenu ou sélection vide : 1."""
    ids = {id(x) for x in sel}
    non = [x for x in ref if id(x) not in ids]
    if not sel or not non:
        return 1.0
    if _objectif_voie(v) == "reussite":
        n1, n2 = len(sel), len(non)
        w1, w = sum(x["gagne"] for x in sel), sum(x["gagne"] for x in sel) + sum(x["gagne"] for x in non)
        tot = math.comb(n1 + n2, n1)
        return min(1.0, sum(math.comb(w, k) * math.comb(n1 + n2 - w, n1 - k) for k in range(w1, min(w, n1) + 1)) / tot)
    import random
    g = [_gain(x) for x in sel] + [_gain(x) for x in non]
    n1, obs = len(sel), sum(_gain(x) for x in sel) / len(sel)
    rnd, ok = random.Random(0), 0
    for _ in range(tirages):
        rnd.shuffle(g)
        ok += sum(g[:n1]) / n1 >= obs - 1e-12
    return (ok + 1) / (tirages + 1)


def benjamini_hochberg(pvals: dict, q: float = 0.05) -> set:
    """Contrôle des faux positifs sur l'ensemble des comparaisons (taux de fausses découvertes 5 %). Renvoie les clés significatives."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, k = len(items), 0
    for i, (_, pv) in enumerate(items, 1):
        if pv <= q * i / m:
            k = i
    return {key for key, _ in items[:k]}


def calibrer_marche_voie(L: list[dict], v: str) -> dict | None:
    """Apprentissage sur le passé seulement. Candidats = toutes les marges observées (part défavorable, part habituelle ; jambe la plus fragile
    pour un combo). Un candidat n'est admissible que si son apport sur « tout prendre » est positif dans CHAQUE moitié chronologique.
    Retenu : le candidat dont l'écart avec les paris non retenus est le plus net (statistique z), ni le volume, ni un taux commun.
    Aucun admissible : None (pas de filtre). Ce choix est fait sur l'apprentissage : son optimisme est mesuré à part (surajustement)."""
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
            d = apport(v, sel, L)
            z, _ = test_selection(v, sel, L)
            if best is None or z > best["z_apprentissage"]:
                best = {"marge_defavorable": td, "marge_habituelle": th, "axes": "jambe la plus fragile" if "def_fragile" in L[0] else "marché",
                        "objectif": _objectif_voie(v), "paris": len(sel), "reference": len(L),
                        "valeur": round(_valeur(v, sel), 4), "valeur_sans_filtre": round(_valeur(v, L), 4),
                        "apport": round(d, 4), "z_apprentissage": round(z, 3)}
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
    """Pour chaque jour : règles apprises sur les jours STRICTEMENT antérieurs, gelées, appliquées à ce seul jour.
    Ne reçoit que les jours de développement : la période réservée n'y entre jamais."""
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


def _ref_par_couple(lignes: list[dict], jours: set) -> dict:
    ref: dict[tuple, list] = defaultdict(list)
    for x in lignes:
        if x["jour"] in jours:
            v = voie(x["cote"], x["cle"])
            if v:
                ref[(x["marche"], v)].append(x)
    return ref


def _base(lignes: list[dict], jours: set) -> dict:
    b: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for x in lignes:
        if x["jour"] in jours:
            b[x["marche"]][0] += x["gagne"]
            b[x["marche"]][1] += 1
    return {k: w / n for k, (w, n) in b.items() if n}


def fiche(v: str, sel: list[dict], ref: list[dict], base: float | None) -> dict:
    sel = sorted(sel, key=lambda x: x["jour"])
    z, _ = test_selection(v, sel, ref)
    pv = p_exacte(v, sel, ref)
    moities = []
    if sel:
        jc = sel[len(sel) // 2]["jour"]
        for part in ([x for x in sel if x["jour"] < jc], [x for x in sel if x["jour"] >= jc]):
            rj = {x["jour"] for x in part}
            rp = [x for x in ref if x["jour"] in rj]
            moities.append(round(apport(v, part, rp), 4) if part and rp else None)
    sem: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for x in sel:
        sem[_semaine(x["jour"])][0] += x["gagne"]
        sem[_semaine(x["jour"])][1] += 1
    return {**indicateurs(sel), "sans_filtre": indicateurs(ref), "taux_de_base_marche": round(base, 4) if base is not None else None,
            "apport": round(apport(v, sel, ref), 4) if sel and ref else None, "apport_par_moitie": moities,
            "z_contre_non_retenus": round(z, 3), "p_unilaterale_exacte": round(pv, 5),
            "par_semaine": {k: {"paris": c[1], "gagnes": c[0]} for k, c in sorted(sem.items())}}


def juger(dev_paris: list[dict], res_paris: list[dict], lignes: list[dict], jours_dev_testes: set, jours_res: set) -> list[dict]:
    """Deux étages, sans réutiliser les données qui ont servi à choisir :
    1. DÉVELOPPEMENT (validation jour par jour sur les jours de développement) : rejeté si apport <= 0 (ou, en A / sans cote / cote manquante,
       réussite pas au-dessus du taux de base) ; exploratoire si apport positif mais pas dans les deux moitiés ; candidat sinon.
    2. PÉRIODE RÉSERVÉE (jamais utilisée pour choisir) : les règles apprises sur tout le développement sont gelées et appliquées une seule fois.
       Seuls les candidats y sont testés ; faux positifs contrôlés par Benjamini-Hochberg (5 %) sur ces seuls tests.
       validé hors échantillon : apport réservé > 0 et significatif après correction ; prometteur : apport réservé > 0 non significatif ;
       non confirmé : apport réservé <= 0 ou aucun pari sur la réserve."""
    ref_d, ref_r = _ref_par_couple(lignes, jours_dev_testes), _ref_par_couple(lignes, jours_res)
    base_d, base_r = _base(lignes, jours_dev_testes), _base(lignes, jours_res)
    par_d: dict[tuple, list] = defaultdict(list)
    par_r: dict[tuple, list] = defaultdict(list)
    for x in dev_paris:
        par_d[(x["marche"], x["voie"])].append(x)
    for x in res_paris:
        par_r[(x["marche"], x["voie"])].append(x)
    out, pvals = {}, {}
    for (nom, v) in sorted(set(par_d) | set(par_r)):
        Ld, Lr = par_d.get((nom, v), []), par_r.get((nom, v), [])
        cle = (Ld or Lr)[0]["cle"]
        fd = fiche(v, Ld, ref_d[(nom, v)], base_d.get(nom)) if Ld else None
        fr = fiche(v, Lr, ref_r[(nom, v)], base_r.get(nom)) if Lr else None
        if not fd:
            etage1, raison = "exploratoire", "aucun pari en développement"
        elif fd["apport"] is None or fd["apport"] <= 0:
            etage1, raison = "rejeté", "le filtre ne fait pas mieux que tout prendre (développement)"
        elif v != "B" and fd["taux_de_base_marche"] is not None and fd["reussite"] <= fd["taux_de_base_marche"]:
            etage1, raison = "rejeté", "réussite pas au-dessus du taux de base du marché (développement)"
        elif None in fd["apport_par_moitie"] or min(fd["apport_par_moitie"]) <= 0:
            etage1, raison = "exploratoire", "apport positif mais pas dans les deux moitiés (développement)"
        else:
            etage1, raison = "candidat", "apport positif dans les deux moitiés (développement)"
            if fr and fr["apport"] is not None and fr["apport"] > 0:
                pvals[(nom, v)] = fr["p_unilaterale_exacte"]
        out[(nom, v)] = {"marche": nom, "famille": famille(cle), "voie": v, "objectif": _objectif_voie(v), "etage_developpement": etage1,
                         "raison": raison, "developpement": fd, "periode_reservee": fr,
                         **({"jambes": 2, "type_combo": (Ld or Lr)[0].get("type_combo")} if cle[0] == "combo" else {})}
    sig = benjamini_hochberg(pvals)
    for k, f in out.items():
        if f["etage_developpement"] != "candidat":
            f["statut"] = f["etage_developpement"]
        elif k in sig:
            f["statut"], f["raison"] = "validé hors échantillon", "candidat confirmé sur la période réservée, significatif après contrôle des faux positifs"
        elif k in pvals:
            f["statut"], f["raison"] = "prometteur", "candidat, apport positif sur la période réservée mais non significatif après correction"
        else:
            f["statut"], f["raison"] = "non confirmé", "candidat sans apport positif sur la période réservée (ou aucun pari)"
    res = list(out.values())
    res.sort(key=lambda f: (FAMILLES.index(f["famille"]), f["marche"], f["voie"]))
    return res


VOIES_ORDRE = ["A", "B", "sans_cote", "cote_manquante"]


def par_famille(paris: list[dict], verdicts: list[dict], etage: str) -> dict:
    """Totaux de famille, toujours SÉPARÉS par voie (cotes disponibles / sans cote / cote manquante). Complément des fiches par marché."""
    out = {}
    for fam in FAMILLES:
        d = {}
        for v in VOIES_ORDRE:
            sel = [x for x in paris if x["famille"] == fam and x["voie"] == v]
            vs = [f[etage] for f in verdicts if f["famille"] == fam and f["voie"] == v and f.get(etage)]
            n = sum(f["paris"] for f in vs)
            if not sel:
                continue
            att = sum(f["paris"] * f["sans_filtre"]["reussite"] for f in vs) / n if n else None
            a = indicateurs(sel)
            d[v] = {**a, "attendu_sans_filtre_meme_melange": round(att, 4) if att is not None else None,
                    "apport": round(a["reussite"] - att, 4) if att is not None else None}
        st = defaultdict(int)
        for f in verdicts:
            if f["famille"] == fam:
                st[f["statut"]] += 1
        out[fam] = {"par_voie": d, "statuts": dict(st)}
    return out


def surajustement(lignes: list[dict], jours_dev: list[str], verdicts: list[dict]) -> dict:
    """Optimisme de la recherche de marges : apport des règles sur leurs propres données d'apprentissage (développement complet)
    contre apport mesuré en validation jour par jour et sur la période réservée, par famille."""
    regles = calibrer([x for x in lignes if x["jour"] in set(jours_dev)])
    out = {}
    for fam in FAMILLES:
        ins = [(r["apport"], r["paris"]) for (nom, v), r in regles.items() if r and famille(next(c for c, l, _, _ in catalogue() if l == nom)) == fam]
        dv = [(f["developpement"]["apport"], f["developpement"]["paris"]) for f in verdicts if f["famille"] == fam and f["developpement"] and f["developpement"]["apport"] is not None]
        rv = [(f["periode_reservee"]["apport"], f["periode_reservee"]["paris"]) for f in verdicts if f["famille"] == fam and f["periode_reservee"] and f["periode_reservee"]["apport"] is not None]
        moy = lambda L: round(sum(a * n for a, n in L) / sum(n for _, n in L), 4) if L and sum(n for _, n in L) else None
        out[fam] = {"apport_sur_apprentissage": moy(ins), "apport_validation_jour_par_jour": moy(dv), "apport_periode_reservee": moy(rv)}
    return out


def combos_par_type(paris: list[dict], lignes: list[dict], jours: set) -> dict:
    out = {}
    for t in sorted({x["type_combo"] for x in lignes if "type_combo" in x}):
        out[t] = {"jambes": 2, "avec_filtre": indicateurs([x for x in paris if x.get("type_combo") == t]),
                  "sans_filtre": indicateurs([x for x in lignes if x.get("type_combo") == t and x["jour"] in jours])}
    return out


def avant(chemin_git: str = "2e5f090:docs/alpha_robustesse_validation.json") -> dict | None:
    """Statuts de la version précédente (2e5f090), pour l'avant / après."""
    import subprocess
    try:
        old = json.loads(subprocess.run(["git", "show", chemin_git], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    except Exception:
        return None
    return {f"{f['marche']} | {f['voie']}": f["statut"] for f in old.get("verdicts", [])}


def main() -> None:
    REJETS_COTES.clear()
    archetype = charger_archive_archetype()
    lignes, analyses = lire_strategie(archetype)
    jours = sorted({x["jour"] for x in lignes})
    coupe = jours[(2 * len(jours)) // 3]                          # période réservée : le dernier tiers des jours, fixé AVANT tout calcul
    jours_dev, jours_res = [j for j in jours if j < coupe], [j for j in jours if j >= coupe]
    dev = [x for x in lignes if x["jour"] < coupe]
    dev_paris, journal, jt = marche_avant(dev)
    regles_dev = calibrer(dev)                                    # gelées avant d'ouvrir la période réservée
    res_paris = appliquer([x for x in lignes if x["jour"] >= coupe], regles_dev)
    verdicts = juger(dev_paris, res_paris, lignes, jt, set(jours_res))
    precedent = avant()
    for f in verdicts:
        f["statut_version_precedente"] = (precedent or {}).get(f"{f['marche']} | {f['voie']}")
    gele = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ids = [m["id"] for m in archetype]
    valides = [(f["marche"], f["voie"]) for f in verdicts if f["statut"] == "validé hors échantillon"]
    IDS.write_bytes(gzip.compress(json.dumps({"archetype": ids, "ecartes_cotes_non_anterieures": REJETS_COTES,
                                              "jours_developpement": jours_dev, "jours_reserves": jours_res}).encode()))
    INTERVALLES.write_text(json.dumps({"gele_le": gele, "statut": "marges apprises sur la période de développement, gelées, des seuls marchés validés sur la période réservée",
                                       "frontiere_voies": round(FRONTIERE_VOIES, 4), "cote_min": P.COTE_MIN, "coupe_reserve": coupe,
                                       "empreinte_ids": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
                                       "regles": {f"{n} | voie {v}": regles_dev.get((n, v)) for n, v in valides}}, ensure_ascii=False, indent=1), encoding="utf-8")
    statuts = defaultdict(int)
    for f in verdicts:
        statuts[f["statut"]] += 1
    rapport = {"gele_le": gele,
               "protocole": "développement : validation jour par jour (règles apprises sur les jours antérieurs) ; période réservée = dernier tiers des jours, "
                            "jamais utilisée pour choisir, règles du développement gelées et appliquées une fois ; comparaison sélection / paris non retenus ; "
                            "faux positifs contrôlés par Benjamini-Hochberg 5 % ; aucun taux commun ; combos sur leur jambe la plus fragile",
               "donnees": {"matchs_sans_doublon": len(ids), "matchs_analyses": analyses, "du": jours[0], "au": jours[-1],
                           "jours_developpement": [jours_dev[0], jours_dev[-1], len(jours_dev)], "jours_reserves": [jours_res[0], jours_res[-1], len(jours_res)],
                           "ecartes_cotes_non_anterieures_au_coup_d_envoi": len(REJETS_COTES),
                           "lectures_par_voie": {v: sum(1 for x in lignes if voie(x["cote"], x["cle"]) == v) for v in VOIES_ORDRE},
                           "lectures_sous_cote_minimale": sum(1 for x in lignes if x["cote"] is not None and x["cote"] < P.COTE_MIN),
                           "cotes_des_combos": "aucune dans l'archive, ni dans precalcul.json (625 matchs avec cotes BetPawa, 0 groupe combiné) : "
                                               "le lecteur parse_combines_betpawa.py est branché au scraper mais ne produit rien ; rentabilité des combos non évaluable"},
               "statuts": dict(statuts),
               "par_famille_developpement": par_famille(dev_paris, verdicts, "developpement"),
               "par_famille_periode_reservee": par_famille(res_paris, verdicts, "periode_reservee"),
               "surajustement": surajustement(lignes, jours_dev, verdicts),
               "combos_par_type_periode_reservee": combos_par_type(res_paris, lignes, set(jours_res)),
               "verdicts": verdicts, "journal_developpement": journal}
    RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONNEES:", json.dumps(rapport["donnees"], ensure_ascii=False))
    print("STATUTS:", dict(statuts))
    print("SURAJUSTEMENT:", json.dumps(rapport["surajustement"], ensure_ascii=False))
    for f in verdicts:
        if f["statut"] in ("validé hors échantillon", "prometteur", "non confirmé"):
            r = f["periode_reservee"] or {}
            d = f["developpement"] or {}
            print(f"  {f['statut']:<24} {f['famille']:<15} {f['marche']:<44} {f['voie']:<14} dev {d.get('paris')} {d.get('reussite')} apport {d.get('apport')} | "
                  f"réserve {r.get('paris')} {r.get('reussite')} sans filtre {(r.get('sans_filtre') or {}).get('reussite')} apport {r.get('apport')} p {r.get('p_unilaterale_exacte')} "
                  f"gain {r.get('gain_net')} | avant: {f['statut_version_precedente']}")


if __name__ == "__main__":
    main()
