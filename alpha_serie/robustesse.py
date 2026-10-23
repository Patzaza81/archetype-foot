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


# --- Correction méthodologique (24/10/2026) : deux voies, aucune bande de cote apprise, aucun plafond ------------------
# Frontière entre les voies = 1 / 0,72 : au-dessus, la cote annonce une probabilité implicite sous 72 %, l'objectif « fréquence » n'a plus de sens.
# Elle découle du seul seuil de Patrick (72 %) ; ce n'est pas un plafond : la voie B n'a AUCUNE limite haute.
FRONTIERE_VOIES = 1 / SEUIL_WILSON
VOIES = {"A": "sélections robustes à forte fréquence de réussite (cote de 1,25 à moins de 1,39)",
         "B": "occasions à cote élevée (cote de 1,39 et plus, sans limite haute)",
         "sans_cote": "combos (aucune cote dans l'archive) : réussite seule, cote à lire sur Betpawa"}


def voie(cote: float | None, cle: tuple[str, str] | None = None) -> str | None:
    """Catégorie de cote d'un pari. Sous 1,25 : aucune voie (cote minimale de Patrick).
    Sans cote : seuls les combos (marché absent de l'archive) vont en « sans_cote ». Un marché simple dont la cote manque pour CE match
    est écarté (cote introuvable) : il ne peut être ni vérifié ni joué à 1,25 minimum."""
    if cote is None:
        return "sans_cote" if cle and cle[0] == "combo" else None
    if cote < P.COTE_MIN:
        return None
    return "A" if cote < FRONTIERE_VOIES - 1e-12 else "B"


def _gain(x: dict) -> float:
    return (x["cote"] - 1) if x["gagne"] else -1.0


def _mesures(sel: list[dict]) -> dict:
    n = len(sel)
    w = sum(x["gagne"] for x in sel)
    ac = [x for x in sel if x["cote"]]
    return {"n": n, "w": w, "taux": w / n if n else 0.0, "gain": sum(_gain(x) for x in ac),
            "implicite": sum(1 / x["cote"] for x in ac) / len(ac) if ac else None}


def _objectif(v: str, sel: list[dict]) -> float:
    """Objectif déclaré de la voie. A : fréquence de réussite fiable (borne de Wilson, indicateur qui tient compte de l'effectif — jamais un filtre).
    B : gain net total à mise égale. sans_cote : comme A."""
    m = _mesures(sel)
    return m["gain"] if v == "B" else wilson_bas(m["w"], m["n"])


def _stable(v: str, sel: list[dict], coupe: str) -> bool:
    """La règle doit remplir l'objectif de sa voie dans CHAQUE moitié chronologique de ses données d'apprentissage.
    A et sans_cote : >= 72 % dans chaque moitié. B : gain net > 0 dans chaque moitié."""
    for moitie in ([x for x in sel if x["jour"] < coupe], [x for x in sel if x["jour"] >= coupe]):
        if not moitie:
            return False
        m = _mesures(moitie)
        if v == "B":
            if m["gain"] <= 0:
                return False
        elif m["taux"] < SEUIL_WILSON:
            return False
    return True


def calibrer_marche_voie(L: list[dict], v: str) -> dict | None:
    """Règle d'un marché dans une voie, apprise sur les données d'apprentissage seulement : part défavorable minimale et part habituelle minimale
    (valeurs réellement observées, lues après retrait d'une paire). La règle « sans filtre » (0, 0) est candidate.
    Retenue = meilleure selon l'objectif de la voie, parmi les règles stables ET meilleures que la sélection sans filtre de la même voie."""
    if not L:
        return None
    jl = sorted({x["jour"] for x in L})
    coupe = jl[len(jl) // 2]
    ref = _mesures(L)                                            # sélection sans filtre de scénarios, même marché, même voie
    best = None
    for td in sorted({x["def"] for x in L}):
        Ld = [x for x in L if x["def"] >= td]
        for th in sorted({x["hab"] for x in L}):
            sel = [x for x in Ld if x["hab"] >= th]
            if not sel:
                break
            if not _stable(v, sel, coupe):
                continue
            m = _mesures(sel)
            sans_filtre = (td == 0 and th == 0) or len(sel) == len(L)
            if not sans_filtre:                                   # un filtre doit apporter quelque chose par rapport à « tout prendre »
                if v == "B" and m["gain"] / m["n"] <= ref["gain"] / ref["n"]:
                    continue
                if v != "B" and m["taux"] <= ref["taux"]:
                    continue
            obj = _objectif(v, sel)
            if best is None or obj > best["objectif"]:
                best = {"part_defavorable_min": td, "part_habituelle_min": th, "filtre_scenarios": not sans_filtre, "objectif": round(obj, 4),
                        "paris": m["n"], "gagnes": m["w"], "reussite": round(m["taux"], 4), "gain_net": round(m["gain"], 3)}
    return best


def calibrer(lignes: list[dict]) -> dict:
    """{(marché, voie): règle | None}."""
    par: dict[tuple, list] = defaultdict(list)
    for x in lignes:
        v = voie(x["cote"], x["cle"])
        if v:
            par[(x["marche"], v)].append(x)
    return {k: calibrer_marche_voie(L, k[1]) for k, L in sorted(par.items())}


def appliquer(lignes: list[dict], regles: dict) -> list[dict]:
    """Applique des règles GELÉES. N'utilise ni le score ni l'issue du match (champ « gagne » jamais lu)."""
    out = []
    for x in lignes:
        v = voie(x["cote"], x["cle"])
        r = regles.get((x["marche"], v)) if v else None
        if r and x["def"] >= r["part_defavorable_min"] and x["hab"] >= r["part_habituelle_min"]:
            out.append({**x, "voie": v})
    return out


def _semaine(jour: str) -> str:
    d = datetime.strptime(jour, "%Y-%m-%d")
    return f"{d.isocalendar()[0]}-S{d.isocalendar()[1]:02d}"


def marche_avant(lignes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validation chronologique répétée : pour chaque jour, règles apprises sur les jours STRICTEMENT antérieurs, gelées, appliquées à ce jour."""
    jours = sorted({x["jour"] for x in lignes})
    paris, journal = [], []
    for d in jours[1:]:
        regles = calibrer([x for x in lignes if x["jour"] < d])
        pris = appliquer([x for x in lignes if x["jour"] == d], regles)
        for x in pris:
            r = regles[(x["marche"], x["voie"])]
            x["filtre_scenarios"] = r["filtre_scenarios"]
        paris += pris
        journal.append({"jour": d, "regles": sum(1 for r in regles.values() if r), "paris": len(pris), "gagnes": sum(x["gagne"] for x in pris)})
    return paris, journal


def juger(paris_oos: list[dict], lignes: list[dict]) -> dict:
    """Verdicts hors échantillon, SÉPARÉS par voie. Références sur les mêmes jours :
      - base du marché : tous les matchs analysés, toutes cotes ;
      - sans filtre : tous les paris du même marché dans la même voie (même catégorie de cote), sans filtre de scénarios.
    A / sans_cote : validé si >= 50 paris, >= 72 %, >= 72 % dans chaque moitié chronologique, au-dessus de la sélection sans filtre.
    B : opportunité démontrée si >= 50 paris, gain net > 0 au total et dans chaque moitié, réussite au-dessus de la probabilité implicite des cotes.
    Moins de 50 paris : exploratoire. Sinon : rejeté."""
    jours = {x["jour"] for x in paris_oos} | ({x["jour"] for x in lignes} - {min(x["jour"] for x in lignes)} if lignes else set())
    base: dict[str, list] = defaultdict(list)
    tout: dict[tuple, list] = defaultdict(list)
    for x in lignes:
        if x["jour"] not in jours:
            continue
        base[x["marche"]].append(x)
        v = voie(x["cote"], x["cle"])
        if v:
            tout[(x["marche"], v)].append(x)
    par: dict[tuple, list] = defaultdict(list)
    for x in paris_oos:
        par[(x["marche"], x["voie"])].append(x)
    out: dict[str, dict] = {"A": {}, "B": {}, "sans_cote": {}}
    for (nom, v), L in sorted(par.items(), key=lambda kv: -len(kv[1])):
        L.sort(key=lambda x: x["jour"])
        m = _mesures(L)
        h1, h2 = _mesures(L[: m["n"] // 2]), _mesures(L[m["n"] // 2:])
        b = _mesures(base[nom])
        sf = _mesures(tout[(nom, v)])
        sem: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for x in L:
            sem[_semaine(x["jour"])][0] += x["gagne"]
            sem[_semaine(x["jour"])][1] += 1
        cotes = sorted(x["cote"] for x in L if x["cote"])
        fiche = {"paris": m["n"], "gagnes": m["w"], "perdus": m["n"] - m["w"], "reussite": round(m["taux"], 4),
                 "base_marche": round(b["taux"], 4) if b["n"] else None, "sans_filtre_meme_voie": round(sf["taux"], 4) if sf["n"] else None,
                 "paris_sans_filtre": sf["n"], "apport_filtre": round(m["taux"] - sf["taux"], 4) if sf["n"] else None,
                 "part_des_paris_avec_filtre_actif": round(sum(1 for x in L if x.get("filtre_scenarios")) / m["n"], 4),
                 "premiere_moitie": round(h1["taux"], 4) if h1["n"] else None, "seconde_moitie": round(h2["taux"], 4) if h2["n"] else None,
                 "wilson_bas_indicatif": round(wilson_bas(m["w"], m["n"]), 4),
                 "par_semaine": {k: {"paris": c[1], "gagnes": c[0]} for k, c in sorted(sem.items())}}
        if cotes:
            fiche |= {"cotes_min_max": [cotes[0], cotes[-1]], "cote_moyenne": round(sum(cotes) / len(cotes), 3),
                      "probabilite_implicite": round(m["implicite"], 4), "gain_net": round(m["gain"], 3), "rendement": round(m["gain"] / len(cotes), 4),
                      "rendement_sans_filtre": round(sf["gain"] / sf["n"], 4) if sf["n"] else None,
                      "gain_premiere_moitie": round(h1["gain"], 3), "gain_seconde_moitie": round(h2["gain"], 3)}
        if m["n"] < MIN_PARIS_HORS_ECHANTILLON:
            statut, raison = "exploratoire", f"{m['n']} paris hors échantillon (minimum {MIN_PARIS_HORS_ECHANTILLON}) : aucune conclusion"
        elif v == "B":
            if m["gain"] <= 0:
                statut, raison = "rejeté", f"gain net {m['gain']:+.2f} unités"
            elif min(h1["gain"], h2["gain"]) <= 0:
                statut, raison = "rejeté", f"gain instable ({h1['gain']:+.2f} puis {h2['gain']:+.2f})"
            elif m["taux"] <= m["implicite"]:
                statut, raison = "rejeté", f"réussite {m['taux']:.1%} sous la probabilité implicite {m['implicite']:.1%}"
            else:
                statut, raison = "opportunité démontrée", f"gain {m['gain']:+.2f} unités, {m['taux']:.1%} contre {m['implicite']:.1%} implicite"
        else:
            if m["taux"] < SEUIL_WILSON:
                statut, raison = "rejeté", f"réussite {m['taux']:.1%} sous 72 %"
            elif min(h1["taux"], h2["taux"]) < SEUIL_WILSON:
                statut, raison = "rejeté", f"incohérent entre périodes ({h1['taux']:.0%} puis {h2['taux']:.0%})"
            elif sf["n"] and m["taux"] <= sf["taux"]:
                statut, raison = "rejeté", f"aucun apport du filtre ({m['taux']:.1%} contre {sf['taux']:.1%} sans filtre)"
            else:
                statut, raison = "validé", f"{m['taux']:.1%}, sans filtre {sf['taux']:.1%}, {h1['taux']:.0%} puis {h2['taux']:.0%}"
        out[v][nom] = {"statut": statut, "raison": raison, **fiche}
    return out


def main() -> None:
    REJETS_COTES.clear()
    archetype = charger_archive_archetype()
    lignes, analyses = lire_strategie(archetype)
    jours = sorted({m["jour"] for m in archetype})
    paris_oos, journal = marche_avant(lignes)
    verdicts = juger(paris_oos, lignes)
    regles = calibrer(lignes)
    retenus = {(nom, v) for v, d in verdicts.items() for nom, f in d.items() if f["statut"] in ("validé", "opportunité démontrée")}
    gele = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ids = [m["id"] for m in archetype]
    IDS.write_bytes(gzip.compress(json.dumps({"archetype": ids, "ecartes_cotes_non_anterieures": REJETS_COTES}).encode()))
    INTERVALLES.write_text(json.dumps({"gele_le": gele, "statut": "règles gelées des seuls marchés validés hors échantillon (par voie)",
                                       "voies": VOIES, "frontiere_voies": round(FRONTIERE_VOIES, 4), "cote_min": P.COTE_MIN,
                                       "min_paris_hors_echantillon": MIN_PARIS_HORS_ECHANTILLON, "matchs_archetype": len(ids), "du": jours[0], "au": jours[-1],
                                       "empreinte_ids": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
                                       "regles": {f"{nom} | voie {v}": regles[(nom, v)] for nom, v in sorted(retenus) if regles.get((nom, v))}},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    par_voie = {}
    for v in ("A", "B", "sans_cote"):
        L = [x for x in paris_oos if x["voie"] == v]
        m = _mesures(L)
        par_voie[v] = {"paris": m["n"], "gagnes": m["w"], "reussite": round(m["taux"], 4) if m["n"] else None,
                       "gain_net": round(m["gain"], 3), "paris_avec_filtre_actif": sum(1 for x in L if x.get("filtre_scenarios"))}
    rapport = {"gele_le": gele, "protocole": "correction méthodologique du 24/10/2026 : validation chronologique répétée jour par jour, deux voies séparées, "
                                            "aucune bande de cote apprise, aucun plafond de cote, Wilson indicatif",
               "voies": VOIES, "frontiere_voies": round(FRONTIERE_VOIES, 4),
               "donnees": {"matchs_sans_doublon": len(ids), "matchs_analyses": analyses, "du": jours[0], "au": jours[-1],
                           "ecartes_cotes_non_anterieures_au_coup_d_envoi": len(REJETS_COTES)},
               "lectures_ecartees_cote_introuvable": sum(1 for x in lignes if x["cle"][0] != "combo" and x["cote"] is None),
               "lectures_ecartees_cote_sous_1_25": sum(1 for x in lignes if x["cote"] is not None and x["cote"] < P.COTE_MIN),
               "hors_echantillon_par_voie": par_voie, "verdicts": verdicts, "journal_des_jours": journal,
               "jours_sans_aucun_pari": sum(1 for j in journal if not j["paris"])}
    RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONNEES:", rapport["donnees"])
    print("PAR VOIE:", par_voie)
    for v in ("A", "B", "sans_cote"):
        print(f"== VOIE {v}")
        for k, f in verdicts[v].items():
            print(f"  {f['statut']:<22} {k:<38} {f['paris']:>4} paris {f['reussite']:.1%} | base {f['base_marche']} sans filtre {f['sans_filtre_meme_voie']} "
                  f"apport {f['apport_filtre']} | gain {f.get('gain_net')} | {f['raison']}")


if __name__ == "__main__":
    main()
