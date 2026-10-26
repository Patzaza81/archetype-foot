"""Moteur alpha « séries » : analyse d'un match en deux étapes.

ÉTAPE 1 — ANALYSE (aucune cote) :
  1. Séries au MÊME LIEU (domicile pour l'équipe à domicile, extérieur pour l'autre), strictement avant le jour du match, 4 à 7 matchs.
  2. Scénarios APPARIÉS sur la même période (les n derniers matchs de chaque équipe, un contre un) :
       offensive : (buts marqués domicile, buts marqués extérieur) ;
       défensive : (buts encaissés par l'extérieur, buts encaissés par le domicile) = ce que marque chaque équipe.
  3. Chaque marché est lu en BUTS ENTIERS sur les scénarios. Admis seulement si la part de scénarios validants atteint le seuil dans LES DEUX
     branches ET si la marge de niveau (moyennes des séries) est respectée. Sinon : exclu, consigné au registre avec la raison.
  4. Valeur = moyenne des deux parts × k (k selon le plus petit échantillon).
ÉTAPE 2 — CHOIX (cote) : `choisir` ne retient que les marchés admis dont la cote est >= 1,25 (aucune limite pour les multiscores).
Les graduations (points et goal-average par match) ne servent qu'à des ALERTES : elles ne créent ni ne retirent aucun marché.
"""
from __future__ import annotations

import re
from typing import Callable

from .marches import libelle, test_du_marche

from . import parametres as P

Predicat = Callable[[int, int], bool]

# --- Marchés lus par l'analyse (les cotes ne servent pas à les définir) ----------------------------------------
CATALOGUE: dict[str, list[tuple[str, str]]] = {
    "buts": [(f"over_under_{x}", s) for x in ("1.5", "2.5", "3.5", "4.5") for s in ("plus", "moins")] + [("btts", "Oui"), ("btts", "Non")],
    "equipes": (
        [("1x2", s) for s in ("1", "N", "2")]
        + [("double_chance", s) for s in ("1N", "N2", "12")]
        + [(f"handicap_{x}", s) for x in ("-1.5", "-0.5", "0.5", "1.5") for s in ("domicile", "exterieur")]
        + [(f"over_under_{q}_{x}", s) for q in ("domicile", "exterieur") for x in ("0.5", "1.5", "2.5") for s in ("plus", "moins")]
        + [(f"cages_inviolees_{q}", s) for q in ("domicile", "exterieur") for s in ("oui", "non")]
    ),
}

GROUPES_MULTISCORES: dict[str, Predicat] = {
    "1:0 / 2:0 / 3:0": lambda h, a: a == 0 and 1 <= h <= 3,
    "0:1 / 0:2 / 0:3": lambda h, a: h == 0 and 1 <= a <= 3,
    "2:1 / 3:1 / 4:1": lambda h, a: a == 1 and 2 <= h <= 4,
    "1:2 / 1:3 / 1:4": lambda h, a: h == 1 and 2 <= a <= 4,
    "Match nul": lambda h, a: h == a,
}


# --- Séries et scénarios ----------------------------------------------------------------------------------------
def serie_lieu(equipe: dict | None, domicile: bool, jour: str) -> tuple[list[int], list[int]]:
    """(marqués, encaissés) au lieu demandé, STRICTEMENT avant `jour` (anti-fuite), du plus ancien au plus récent, 7 derniers au plus."""
    ms = [m for m in (equipe or {}).get("matchs") or []
          if bool(m.get("domicile")) is bool(domicile) and not m.get("provisoire") and str(m.get("date"))[:10] < jour
          and isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int)]
    ms.sort(key=lambda m: str(m["date"]))
    ms = ms[-P.MAX_MATCHS:]
    return [m["buts_marques"] for m in ms], [m["buts_encaisses"] for m in ms]


def scenarios(hm: list[int], hc: list[int], am: list[int], ac: list[int]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Scénarios appariés (domicile, extérieur) : n = plus petit échantillon, on apparie les n derniers matchs de chaque équipe."""
    n = min(len(hm), len(am))
    hm, hc, am, ac = hm[-n:], hc[-n:], am[-n:], ac[-n:]
    offensive = [(hm[i], am[i]) for i in range(n)]
    defensive = [(ac[i], hc[i]) for i in range(n)]
    return offensive, defensive


def _moy(v: list[int]) -> float:
    return sum(v) / len(v)


def niveaux(hm: list[int], hc: list[int], am: list[int], ac: list[int]) -> dict:
    """Buts attendus (moyennes des séries complètes) : équipe = (ce qu'elle marque + ce que l'adversaire encaisse) / 2."""
    eh, ea = (_moy(hm) + _moy(ac)) / 2, (_moy(am) + _moy(hc)) / 2
    return {"dom": eh, "ext": ea, "total": eh + ea, "d": eh - ea}


def part(scen: list[tuple[int, int]], pred: Predicat) -> float:
    return sum(1 for h, a in scen if pred(h, a)) / len(scen)


# --- Normes de niveau (marges) ----------------------------------------------------------------------------------
def _marge(params: dict, famille: str, ligne: str) -> float:
    m = params["marges"]
    return float(m.get(famille, {}).get(ligne, m["defaut"]))


def _plus(e: float, ligne: float, marge: float) -> tuple[bool, float]:
    return e >= ligne + marge - 1e-9, e - (ligne + marge)


def _moins(e: float, ligne: float, marge: float) -> tuple[bool, float]:
    return e <= ligne - marge + 1e-9, (ligne - marge) - e


def norme_niveau(g: str, s: str, niv: dict, params: dict) -> tuple[bool, str, float | None]:
    """(respectée ?, texte, écart à la norme). Écart >= 0 : norme respectée. Aucune norme -> (True, 'sans objet', None)."""
    seuils = params["seuils_resultat"]
    d = niv["d"]
    m = re.fullmatch(r"over_under_(?:(domicile|exterieur)_)?(\d+\.\d+)", g)
    if m and s in ("plus", "moins"):
        qui, ligne = m.group(1), m.group(2)
        e = niv["total"] if qui is None else niv[{"domicile": "dom", "exterieur": "ext"}[qui]]
        fam = ("total_" if qui is None else "equipe_") + s
        ok, ecart = (_plus if s == "plus" else _moins)(e, float(ligne), _marge(params, fam, ligne))
        return ok, f"attendu {e:.2f}, marge {_marge(params, fam, ligne):g} sur la ligne {ligne}", ecart
    if g == "btts":
        mp, mm = _marge(params, "equipe_plus", "0.5"), _marge(params, "equipe_moins", "1.5")
        if s == "Oui":
            ok1, e1 = _plus(niv["dom"], 0.5, mp)
            ok2, e2 = _plus(niv["ext"], 0.5, mp)
            return ok1 and ok2, f"attendus {niv['dom']:.2f} et {niv['ext']:.2f}, chacun doit atteindre {0.5 + mp:g}", min(e1, e2)
        mn = min(niv["dom"], niv["ext"])
        ok, e = _moins(mn, 1.5, mm)
        return ok, f"plus petit attendu {mn:.2f}, doit être <= {1.5 - mm:g}", e
    m = re.fullmatch(r"cages_inviolees_(domicile|exterieur)", g)
    if m:                                    # cage du domicile inviolée = l'extérieur ne marque pas (et inversement)
        adverse = "ext" if m.group(1) == "domicile" else "dom"
        if s == "oui":
            ok, e = _moins(niv[adverse], 0.5, _marge(params, "equipe_moins", "0.5"))
        else:
            ok, e = _plus(niv[adverse], 0.5, _marge(params, "equipe_plus", "0.5"))
        return ok, f"attendu de l'équipe qui marque {niv[adverse]:.2f}", e
    if g == "1x2":
        if s == "1":
            return d >= seuils["dom_gagne"] - 1e-9, f"écart attendu {d:+.2f}, doit être >= {seuils['dom_gagne']:g}", d - seuils["dom_gagne"]
        if s == "2":
            return -d >= seuils["ext_gagne"] - 1e-9, f"écart attendu {d:+.2f}, doit être <= {-seuils['ext_gagne']:g}", -d - seuils["ext_gagne"]
        t = seuils.get("nul")
        if t is None:
            return False, "aucun seuil de niveau appris pour le nul sur l'archive", None
        return abs(d) <= t + 1e-9, f"|écart attendu| {abs(d):.2f}, doit être <= {t:g}", t - abs(d)
    if g == "double_chance":
        if s == "1N":
            return d >= seuils["dom_ne_perd_pas"] - 1e-9, f"écart attendu {d:+.2f}, doit être >= {seuils['dom_ne_perd_pas']:g}", d - seuils["dom_ne_perd_pas"]
        if s == "N2":
            return -d >= seuils["ext_ne_perd_pas"] - 1e-9, f"écart attendu {d:+.2f}, doit être <= {-seuils['ext_ne_perd_pas']:g}", -d - seuils["ext_ne_perd_pas"]
        return True, "sans objet (le niveau n'apporte rien au « pas de nul »)", None
    m = re.fullmatch(r"handicap_(-?\d+\.\d+)", g)
    if m and s in ("domicile", "exterieur"):
        x = float(m.group(1))
        dom = s == "domicile"
        if abs(x) == 0.5:                    # handicaps ±0,5 = victoire ou « ne perd pas » : mêmes normes
            if dom:
                cle = "dom_ne_perd_pas" if x > 0 else "dom_gagne"
                return d >= seuils[cle] - 1e-9, f"écart attendu {d:+.2f}, doit être >= {seuils[cle]:g}", d - seuils[cle]
            cle = "ext_gagne" if x > 0 else "ext_ne_perd_pas"
            return -d >= seuils[cle] - 1e-9, f"écart attendu {d:+.2f}, doit être <= {-seuils[cle]:g}", -d - seuils[cle]
        marge = float(params["marges"]["handicap_1_5"])      # ±1,5 : le domicile gagne si d > -x ; l'extérieur si -d > x
        borne = (-x if dom else x)
        ecart = (d if dom else -d) - (borne + marge)
        return ecart >= -1e-9, f"écart attendu {d:+.2f}, marge {marge:g} sur la borne {borne:g}", ecart
    return True, "sans objet", None


# --- Analyse ---------------------------------------------------------------------------------------------------
def _signature(pred: Predicat) -> tuple:
    return tuple(pred(h, a) for h in range(10) for a in range(10))


def analyser_match(equipe_dom: dict, equipe_ext: dict, jour: str, params: dict | None = None) -> dict:
    """Étape 1 (sans cote). Retourne les trois onglets (marchés admis), le registre des rejetés et les éléments de lecture."""
    params = params or P.charger()
    hm, hc = serie_lieu(equipe_dom, True, jour)
    am, ac = serie_lieu(equipe_ext, False, jour)
    n = min(len(hm), len(am))
    k = P.coef_k(n)
    base = {"jour": jour, "n_domicile": len(hm), "n_exterieur": len(am)}
    if k is None:
        return {**base, "statut": "exclu", "raison": f"échantillon insuffisant (minimum {P.MIN_MATCHS} matchs au même lieu pour chaque équipe)",
                "onglets": {"buts": [], "equipes": [], "multiscores": []}, "rejetes": []}
    off, de = scenarios(hm, hc, am, ac)
    niv = niveaux(hm, hc, am, ac)
    seuil = params["seuil_branche"]
    candidats, rejetes = [], []

    def traiter(onglet, cle, nom, pred, norme):
        so, sd = part(off, pred), part(de, pred)
        ok_n, txt, ecart = norme
        fiche = {"onglet": onglet, "cle": cle, "marche": nom, "offensive": round(so, 4), "defensive": round(sd, 4),
                 "valeur": round((so + sd) / 2 * k, 4), "niveau": txt, "ecart_niveau": None if ecart is None else round(ecart, 3), "_pred": pred}
        if so < seuil - 1e-9 or sd < seuil - 1e-9:
            branche = "offensive" if so < seuil - 1e-9 else "défensive"
            fiche["raison"] = f"branche {branche} sous {seuil:.0%} ({so:.0%} offensive, {sd:.0%} défensive)"
            rejetes.append(fiche)
        elif not ok_n:
            fiche["raison"] = f"norme de niveau non respectée : {txt}"
            rejetes.append(fiche)
        else:
            candidats.append(fiche)

    for onglet, items in CATALOGUE.items():
        for g, s in items:
            pred = test_du_marche(g, s)
            if pred is not None:
                traiter(onglet, (g, s), libelle(g, s), pred, norme_niveau(g, s, niv, params))
    mg = params["multigoals"]
    for lo, hi in mg["plages"]:                      # fourchette en entiers : bornes à lo-0,5 et hi+0,5, marge exigée de chaque côté
        pred = (lambda h, a, lo=lo, hi=hi: lo <= h + a <= hi)
        e = niv["total"]
        bas, haut = e - (lo - 0.5), (hi + 0.5) - e
        ok = bas >= mg["marge_borne"] - 1e-9 and haut >= mg["marge_borne"] - 1e-9
        traiter("buts", ("multigoals", f"{lo}-{hi}"), f"Multigoals {lo}-{hi}", pred,
                (ok, f"total attendu {e:.2f}, à {bas:.2f} de la borne basse et {haut:.2f} de la borne haute (marge {mg['marge_borne']:g})", min(bas, haut) - mg["marge_borne"]))

    candidats.sort(key=lambda f: (-f["valeur"], -min(f["offensive"], f["defensive"]), -(f["ecart_niveau"] if f["ecart_niveau"] is not None else 0)))
    onglets: dict[str, list] = {"buts": [], "equipes": [], "multiscores": []}
    vues: dict[tuple, str] = {}
    for f in candidats:                              # jamais deux événements identiques : on garde le mieux classé
        sig = _signature(f["_pred"])
        if sig in vues:
            f["raison"] = f"doublon de « {vues[sig]} » (même événement)"
            rejetes.append(f)
            continue
        vues[sig] = f["marche"]
        onglets[f["onglet"]].append(f)

    tout = off + de                                  # multiscores : lecture PAR GROUPE, constante de 3 sur l'ensemble des scénarios des deux branches
    for nom, pred in GROUPES_MULTISCORES.items():
        c = sum(1 for h, a in tout if pred(h, a))
        fiche = {"onglet": "multiscores", "cle": ("multiscores", nom), "marche": nom, "scenarios": c, "sur": len(tout), "valeur": round(c / len(tout) * k, 4)}
        if c >= P.CONSTANTE_MULTISCORE:
            onglets["multiscores"].append(fiche)
        else:
            fiche["raison"] = f"{c} scénario(s) sur {len(tout)}, sous la constante de {P.CONSTANTE_MULTISCORE}"
            rejetes.append(fiche)
    onglets["multiscores"].sort(key=lambda f: -f["scenarios"])

    for lst in list(onglets.values()) + [rejetes]:
        for f in lst:
            f.pop("_pred", None)
    return {**base, "statut": "analyse", "k": k, "scenarios_offensifs": off, "scenarios_defensifs": de,
            "niveaux": {c: round(v, 3) for c, v in niv.items()}, "onglets": onglets, "rejetes": rejetes}


# --- Étape 2 : choix avec la cote --------------------------------------------------------------------------------
def cote_de(cotes_betpawa: dict | None, cle: tuple[str, str]) -> float | None:
    g, s = cle
    v = ((cotes_betpawa or {}).get(g) or {}).get(s)
    return float(v) if isinstance(v, (int, float)) and v > 1 else None


def choisir(resultat: dict, cotes_betpawa: dict | None, cote_min: float = P.COTE_MIN) -> dict:
    """Étape 2. Buts et équipes : cote >= 1,25 (1,22 pour « Plus de 1,5 buts » seul), aucun maximum. Multiscores : aucune limite de cote. Cote introuvable : le marché reste, marqué « cote à lire »."""
    tab: dict[str, list] = {"buts": [], "equipes": [], "multiscores": []}
    ecartes = []
    for onglet, lst in resultat["onglets"].items():
        for f in lst:
            c = cote_de(cotes_betpawa, f["cle"])
            g = {**f, "cote": c}
            mini = min(cote_min, P.COTE_MIN_PLUS15) if tuple(f["cle"]) == P.CLE_PLUS15 else cote_min      # « Plus de 1,5 » seul : 1,22 (Patrick, 26/10/2026)
            if onglet != "multiscores" and c is not None and c < mini:
                ecartes.append({**g, "raison": f"cote {c:g} sous le minimum {mini:g}"})
            else:
                if c is None:
                    g["cote_a_lire"] = True
                tab[onglet].append(g)
    return {"onglets": tab, "ecartes_par_la_cote": ecartes}


# --- Graduation : alertes seulement ------------------------------------------------------------------------------
def graduation(classement: list[dict] | None, nom_dom: str, nom_ext: str) -> dict | None:
    """Points ÷ matchs et goal-average ÷ matchs (Matchendirect). Nom d'équipe EXACT, jamais par ressemblance : introuvable -> None."""
    par_nom = {r.get("equipe"): r for r in (classement or [])}
    d, e = par_nom.get(nom_dom), par_nom.get(nom_ext)
    if not d or not e or not d.get("j") or not e.get("j"):
        return None
    f = lambda r: {"pts_match": r["pts"] / r["j"], "diff_match": r["diff"] / r["j"]}
    return {"dom": f(d), "ext": f(e)}


def alerte_graduation(cle: tuple[str, str], grad: dict | None) -> str | None:
    """Alerte (jamais un filtre) : le marché favorise une équipe alors que points ET goal-average par match favorisent l'autre."""
    if not grad:
        return None
    g, s = cle
    pour_dom = (g, s) in {("1x2", "1"), ("double_chance", "1N"), ("handicap_-0.5", "domicile"), ("handicap_0.5", "domicile")}
    pour_ext = (g, s) in {("1x2", "2"), ("double_chance", "N2"), ("handicap_-0.5", "exterieur"), ("handicap_0.5", "exterieur")}
    dom_mieux = grad["dom"]["pts_match"] > grad["ext"]["pts_match"] and grad["dom"]["diff_match"] > grad["ext"]["diff_match"]
    ext_mieux = grad["ext"]["pts_match"] > grad["dom"]["pts_match"] and grad["ext"]["diff_match"] > grad["dom"]["diff_match"]
    if pour_dom and ext_mieux:
        return "contradiction : l'extérieur est mieux classé (points et goal-average par match)"
    if pour_ext and dom_mieux:
        return "contradiction : le domicile est mieux classé (points et goal-average par match)"
    return None
