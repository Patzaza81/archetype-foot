"""Signaux de MEGAPOWER : pour un match du flux commun (data/archive_test), ce que chaque moteur lit, ramené à tous les marchés du catalogue d'Analyse Verdict.

Tous les marchés dépendent seulement du score final : chaque moteur fournit donc une répartition de scores (grille domicile × extérieur), et la part de la grille
qui fait gagner un marché est la lecture de ce moteur pour ce marché.
  - Verdict : scores réels du domicile à domicile et de l'extérieur à l'extérieur (saison en cours), + buts attendus, xG, verdict de la page (code de verif_pronostic, inchangé) ;
  - Alpha   : séries appariées des 7 derniers matchs au même lieu (scénarios « attaques » et « défenses », alpha_serie.coeur, inchangé) ;
  - Omega   : buts attendus rapprochés de la moyenne + grille Poisson/Dixon-Coles (moteur_omega.modele, paramètres du moteur, inchangés) ;
  - Gamma   : tous les croisements attaque A × attaque B (19 derniers au plus), palier « strict » compatible avec les défenses, fréquence robuste (une observation retirée).
Aucun résultat du match lui-même n'entre ici : seulement des matchs strictement antérieurs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import verif_pronostic as V
from alpha_serie import coeur as AC
from moteur_omega import modele as OM

ROOT = Path(__file__).resolve().parent.parent
CAP = V.CAP
NOMS = V.NOMS
TABLE = V.TABLE                                    # (h, a, marché)
NB = len(NOMS)
P_OMEGA = json.loads((ROOT / "moteur_omega" / "parametres.json").read_text(encoding="utf-8"))
MAX_GAMMA = 19
NIVEAU_VERDICT = {"TIENT": 2, "TIENT AVEC RÉSERVE": 1, "NE TIENT PAS": 0}
SIGNAUX = ("v_dom", "v_ext", "v_niveau", "v_buts", "v_xg", "a_att", "a_def", "o_p", "g_brut", "g_strict", "g_robuste")


def _grille(scores) -> np.ndarray:
    g = np.zeros((CAP + 1, CAP + 1))
    for h, a in scores:
        g[min(h, CAP), min(a, CAP)] += 1
    return g / g.sum()


def _part(grille: np.ndarray) -> np.ndarray:
    return np.tensordot(grille, TABLE, axes=([0, 1], [0, 1]))


def _serie(equipe, domicile: bool, jour: str, maxi: int):
    ms = [m for m in (equipe or {}).get("matchs") or [] if bool(m.get("domicile")) is domicile and not m.get("provisoire") and str(m.get("date"))[:10] < jour
          and isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int)]
    ms.sort(key=lambda m: str(m["date"]))
    ms = ms[-maxi:]
    return [m["buts_marques"] for m in ms], [m["buts_encaisses"] for m in ms]


def _marg(v) -> np.ndarray:
    m = np.zeros(CAP + 1)
    for x in v:
        m[min(x, CAP)] += 1
    return m


def _gamma(aa, da, ab, db):
    """(brut, strict, robuste). brut = attaque A × attaque B ; strict = croisements où chaque attaque colle à la défense d'en face (écart 0) ; robuste = plus basse fréquence brute en retirant une observation."""
    ma, mb = _marg(aa), _marg(ab)
    brut = _part(np.outer(ma, mb) / (len(aa) * len(ab)))
    ca = np.array([sum(1 for d in db if min(d, CAP) == a) for a in range(CAP + 1)])     # défenses B compatibles avec a buts de A
    cb = np.array([sum(1 for d in da if min(d, CAP) == b) for b in range(CAP + 1)])
    gs = np.outer(ma * ca, mb * cb)
    strict = _part(gs / gs.sum()) if gs.sum() > 0 else np.full(NB, np.nan)
    rob = brut.copy()
    for marg, autre, cote_a in ((ma, mb, True), (mb, ma, False)):
        n = marg.sum()
        for v in np.nonzero(marg)[0]:
            r = marg.copy(); r[v] -= 1
            g = (np.outer(r, autre) if cote_a else np.outer(autre, r)) / ((n - 1) * autre.sum())
            rob = np.minimum(rob, _part(g))
    return brut, strict, rob


def lire(x: dict, cfg: dict | None = None) -> dict | None:
    """Signaux d'un match. None si la règle des 4 matchs au même lieu (saison en cours, comme Analyse Verdict) n'est pas remplie."""
    cfg = cfg or V.config()
    a = x.get("assemblage") or {}
    jour = x["date"]
    cotes = V.cotes_betpawa(x.get("cotes_betpawa"))
    base = V.constat(x, "1", None, cfg)
    if base["verdict"] == "NON ÉVALUABLE":
        return None
    S = {k: np.full(NB, np.nan) for k in SIGNAUX}
    # --- Verdict : scores de la saison au même lieu (mêmes matchs que la page) ---
    saison = a.get("saison_football_data")
    def pris(eq, dom):
        M = [m for m in (a.get(eq) or {}).get("matchs") or [] if m.get("domicile") is dom and m.get("date") and m["date"] < jour and m.get("buts_marques") is not None and m.get("buts_encaisses") is not None]
        Ss = [m for m in M if m.get("saison") == saison] if saison else M
        return Ss if Ss or not saison else M
    MA, MB = pris("equipe_dom", True), pris("equipe_ext", False)
    S["v_dom"] = _part(_grille([(m["buts_marques"], m["buts_encaisses"]) for m in MA]))
    S["v_ext"] = _part(_grille([(m["buts_encaisses"], m["buts_marques"]) for m in MB]))
    for n in cotes:                                   # verdict de la page, marché par marché (seulement les marchés cotés)
        r = V.constat(x, n, None, cfg)
        k = V.IDX[n]
        S["v_niveau"][k] = NIVEAU_VERDICT.get(r["verdict"], np.nan)
    bm, xa = base["buts_attendus"], base["xg_attendus"]
    if bm[0] is not None and bm[1] is not None:
        S["v_buts"] = _poisson(bm[0], bm[1], 0.0)
    if xa[0] is not None and xa[1] is not None:
        S["v_xg"] = _poisson(xa[0], xa[1], 0.0)
    # --- Alpha : séries appariées (7 derniers au même lieu) ---
    hm, hc = AC.serie_lieu(a.get("equipe_dom"), True, jour)
    am, ac = AC.serie_lieu(a.get("equipe_ext"), False, jour)
    if min(len(hm), len(am)) >= 4:
        off, de = AC.scenarios(hm, hc, am, ac)
        S["a_att"], S["a_def"] = _part(_grille(off)), _part(_grille(de))
    # --- Omega et Gamma : jusqu'aux 19 derniers au même lieu ---
    aa, da = _serie(a.get("equipe_dom"), True, jour, MAX_GAMMA)
    ab, db = _serie(a.get("equipe_ext"), False, jour, MAX_GAMMA)
    if min(len(aa), len(ab)) >= 4:
        la, lb = OM.buts_attendus({"dom_marques": aa, "dom_encaisses": da, "ext_marques": ab, "ext_encaisses": db}, P_OMEGA["global_dom"], P_OMEGA["global_ext"], P_OMEGA)
        S["o_p"] = _poisson(la, lb, P_OMEGA["rho"])
        S["g_brut"], S["g_strict"], S["g_robuste"] = _gamma(aa, da, ab, db)
    cote = np.full(NB, np.nan)
    for n, c in cotes.items():
        cote[V.IDX[n]] = c
    return {"signaux": S, "cote": cote, "n_dom": len(MA), "n_ext": len(MB), "buts": bm, "xg": xa, "championnat": (base.get("championnat") or {}).get("buts")}


def _poisson(la: float, lb: float, rho: float) -> np.ndarray:
    g = OM.grilles(np.array([max(la, 0.05)]), np.array([max(lb, 0.05)]), rho)[0]       # grille 0..10 d'Omega (renormalisée)
    return _part(g[:CAP + 1, :CAP + 1])
