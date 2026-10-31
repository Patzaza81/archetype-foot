"""Évaluation de la règle n°1 (compatibilité) contre la sélection par P — protocole : docs/DC_COMPATIBILITE_PROTOCOLE.md. Archive/rejeu, PAS un bilan réel.

Calibrage 2025-26 (seuil de chaque variante appris, régression logistique ajustée), test 2026-27, séparation stricte.
Candidats d'un match = une issue par marché et jamais deux fois le même événement (comme selecteur.py), dans l'ordre du score testé.
Score de P : la probabilité. Score de compatibilité : Comp_Croisée (min / moyenne / produit des bornes basses de Wilson dom et ext) ; P ne sert qu'à départager les égalités.
Usage : python -m moteur_dc.compatibilite_eval  → docs/DC_COMPATIBILITE_RESULTATS.md et .json
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as CAL, coeur, marches as M, selecteur as S
from .compatibilite import SORTIE

ROOT = Path(__file__).resolve().parent.parent
TIRAGES, NIVEAU, GRAINE = 4000, 0.025, 20261031
VARIANTES = ("min", "moyenne", "produit")
P_POOL = 0.5                 # le pool de la régression : marchés que le modèle donne plus probables que non (déclaré avant le calcul)
GROUPES = [c[0] for c in coeur.CLES]
_SIG = {}
SIG_ID = np.array([_SIG.setdefault(M.signature(tuple(c)), len(_SIG)) for c in coeur.CLES])
GRP_ID = np.array([{g: i for i, g in enumerate(dict.fromkeys(GROUPES))}[g] for g in GROUPES])


def wilson_bas(k: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Borne basse de Wilson 95 % (0 si n = 0)."""
    n = np.asarray(n, float)
    k = np.asarray(k, float)
    ok = n > 0
    nn = np.where(ok, n, 1.0)
    p = k / nn
    z = S.Z_WILSON
    d = 1 + z * z / nn
    c = (p + z * z / (2 * nn)) / d
    r = z * np.sqrt(p * (1 - p) / nn + z * z / (4 * nn * nn)) / d
    return np.where(ok, np.clip(c - r, 0.0, 1.0), 0.0)


def comp_croisee(L: dict[str, np.ndarray], variante: str) -> np.ndarray:
    d, e = L["dom"], L["ext"]
    return {"min": np.minimum(d, e), "moyenne": (d + e) / 2, "produit": d * e}[variante]


def candidats(score: np.ndarray, depart: np.ndarray) -> np.ndarray:
    """Masque (matchs, marchés) : par match, ordre du score décroissant (égalités : `depart` décroissant), une issue par marché et par événement."""
    garde = np.zeros(score.shape, bool)
    for i in range(len(score)):
        for j in np.lexsort((-depart[i], -score[i])):
            g, s = GRP_ID[j], SIG_ID[j]
            if g in vus_g(garde, i) or s in vus_s(garde, i):
                continue
            garde[i, j] = True
    return garde


def vus_g(garde: np.ndarray, i: int) -> set:
    return set(GRP_ID[garde[i]])


def vus_s(garde: np.ndarray, i: int) -> set:
    return set(SIG_ID[garde[i]])


def pav_seuil(s: np.ndarray, y: np.ndarray, min_paris: int = CAL.MIN_PARIS) -> dict[str, Any]:
    """Même règle que le seuil par marché : tranches de 5 points dès 50 %, réussite lissée croissante, 1re tranche à 70 % avec ≥ 30 paris au-dessus."""
    bornes = [round(0.5 + CAL.PAS_SEUIL * k, 2) for k in range(int(0.5 / CAL.PAS_SEUIL))]
    tr = []
    for b in bornes:
        m = (s >= b) & ((s < b + CAL.PAS_SEUIL) if b < bornes[-1] else (s <= 1))
        if m.sum():
            tr.append((b, int(m.sum()), int(y[m].sum())))
    lisse = CAL._pav([t[1] for t in tr], [t[2] for t in tr])
    for (b, _, _), r in zip(tr, lisse):
        m = s >= b
        if r >= S.REUSSITE_CIBLE and m.sum() >= min_paris:
            return {"seuil": b, "n": int(m.sum()), "reussite": float(y[m].mean())}
    return {"seuil": None}


def bootstrap_ecart(nA, wA, nB, wB, rng) -> tuple[float, float, float, float]:
    """Écart de taux de réussite A − B, apparié (mêmes matchs rééchantillonnés), IC 95 % par percentiles ; renvoie (écart, bas, haut, sd)."""
    N = len(nA)
    c = rng.multinomial(N, np.full(N, 1.0 / N), size=TIRAGES).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (c @ wA) / (c @ nA) - (c @ wB) / (c @ nB)
    d = d[np.isfinite(d)]
    obs = wA.sum() / nA.sum() - wB.sum() / nB.sum()
    return float(obs), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)), float(d.std())


def retenu(bas: float) -> bool:
    """Règle déclarée d'avance (comme la piste A) : retenu si et seulement si la borne basse de l'IC 95 % est > 0."""
    return bas > 0


def holm(pvals: list[float], niveau: float = NIVEAU) -> list[bool]:
    ordre = sorted(range(len(pvals)), key=lambda i: pvals[i])
    ok = [False] * len(pvals)
    for r, i in enumerate(ordre):
        if pvals[i] <= niveau / (len(pvals) - r):
            ok[i] = True
        else:
            break
    return ok


def logistique(X: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        W = p * (1 - p) + 1e-9
        H = (X * W[:, None]).T @ X + 1e-6 * np.eye(X.shape[1])
        pas = np.linalg.solve(H, X.T @ (y - p))
        b += pas
        if np.abs(pas).max() < 1e-8:
            break
    return b


def charger() -> dict[str, Any]:
    lignes = pickle.load(open(SORTIE, "rb"))
    Y = CAL._resultats(np.array([l["h"] for l in lignes]), np.array([l["a"] for l in lignes])).astype(float)
    P = np.stack([l["P"] for l in lignes]).astype(float)
    kd, ke = np.stack([l["kd"] for l in lignes]), np.stack([l["ke"] for l in lignes])
    nd, ne = np.array([l["nd"] for l in lignes])[:, None], np.array([l["ne"] for l in lignes])[:, None]
    L = {"dom": wilson_bas(kd, np.broadcast_to(nd, kd.shape)), "ext": wilson_bas(ke, np.broadcast_to(ne, ke.shape))}
    return {"saison": np.array([l["saison"] for l in lignes]), "id": [l["id"] for l in lignes], "date": [l["date"] for l in lignes],
            "P": P, "Y": Y, "L": L, "kd": kd, "ke": ke, "nd": nd, "ne": ne}


def sous(D: dict[str, Any], masque: np.ndarray) -> dict[str, Any]:
    return {"saison": D["saison"][masque], "id": [x for x, m in zip(D["id"], masque) if m], "date": [x for x, m in zip(D["date"], masque) if m],
            "P": D["P"][masque], "Y": D["Y"][masque], "L": {k: v[masque] for k, v in D["L"].items()}, "kd": D["kd"][masque], "ke": D["ke"][masque],
            "nd": D["nd"][masque], "ne": D["ne"][masque]}


def regression(cal: dict[str, Any], tst: dict[str, Any], rng: np.random.Generator, centrer: bool = False) -> dict[str, Any]:
    """La compatibilité ajoute-t-elle de l'information au-delà de P ? Logistique ajustée sur le calibrage, lue sur le test (gain de log-vraisemblance apparié, IC par match).
    centrer=True (amendement post-hoc, déclaré) : la compatibilité est centrée par marché sur la moyenne du calibrage. Sans cela elle identifie le TYPE de marché
    (un « plus de 0,5 but » est toujours compatible) et le placebo (compatibilité mélangée entre matchs) donne le même gain : on mesurerait le marché, pas les équipes."""
    poolc, poolt = cal["P"] >= P_POOL, tst["P"] >= P_POOL
    def feats(Dx, mask, v, mu=None, sd=None):
        lp = np.log(np.clip(Dx["P"][mask], 1e-6, 1 - 1e-6) / (1 - np.clip(Dx["P"][mask], 1e-6, 1 - 1e-6)))
        s = comp_croisee(Dx["L"], v)
        if centrer:
            s = s - comp_croisee(cal["L"], v).mean(axis=0)
        return lp, s[mask]
    nm_t = len(tst["P"])
    reg = {}
    for v in VARIANTES:
        lp_c, s_c = feats(cal, poolc, v)
        mu, sd = s_c.mean(), s_c.std() or 1.0
        y_c = cal["Y"][poolc]
        b0 = logistique(np.column_stack([np.ones_like(lp_c), lp_c]), y_c)
        b1 = logistique(np.column_stack([np.ones_like(lp_c), lp_c, (s_c - mu) / sd]), y_c)
        lp_t, s_t = feats(tst, poolt, v)
        y_t = tst["Y"][poolt]
        def ll(b, X):
            q = np.clip(1 / (1 + np.exp(-(X @ b))), 1e-9, 1 - 1e-9)
            return y_t * np.log(q) + (1 - y_t) * np.log(1 - q)
        g = ll(b1, np.column_stack([np.ones_like(lp_t), lp_t, (s_t - mu) / sd])) - ll(b0, np.column_stack([np.ones_like(lp_t), lp_t]))
        mid = np.broadcast_to(np.arange(nm_t)[:, None], poolt.shape)[poolt]
        gm = np.bincount(mid, weights=g, minlength=nm_t)
        nn = np.bincount(mid, minlength=nm_t).astype(float)
        c = rng.multinomial(nm_t, np.full(nm_t, 1.0 / nm_t), size=TIRAGES).astype(float)
        d = (c @ gm) / np.maximum(c @ nn, 1)
        reg[v] = {"coef_P": float(b1[1]), "coef_compat_std": float(b1[2]), "gain_ll_par_obs": float(gm.sum() / nn.sum()), "ic95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                  "mde": float(1.96 * d.std()), "observations": int(nn.sum()), "retenu": retenu(float(np.percentile(d, 2.5)))}
    return reg


def evaluer(D: dict[str, Any], log=print) -> dict[str, Any]:
    rng = np.random.default_rng(GRAINE)
    cal, tst = sous(D, D["saison"] == "2526"), sous(D, D["saison"] == "2627")
    nm_c, nm_t = len(cal["P"]), len(tst["P"])
    out: dict[str, Any] = {"matchs_calibrage": nm_c, "matchs_test": nm_t, "periode_test": [min(tst["date"]), max(tst["date"])],
                           "periode_calibrage": [min(cal["date"]), max(cal["date"])], "variantes": {}}
    # --- P seul : seuil appris sur 2025-26 (même règle) ---
    mP_c = candidats(cal["P"], cal["P"])
    sp = pav_seuil(cal["P"][mP_c], cal["Y"][mP_c])
    mP_t = candidats(tst["P"], tst["P"])
    out["P_seul"] = {"seuil": sp["seuil"]}
    if sp["seuil"] is not None:
        sel = mP_t & (tst["P"] >= sp["seuil"])
        out["P_seul"].update(paris=int(sel.sum()), matchs_avec_pari=int(sel.any(axis=1).sum()), reussite=float(tst["Y"][sel].mean()) if sel.any() else None)
    # --- variantes ---
    ps = []
    for v in VARIANTES:
        sc_c, sc_t = comp_croisee(cal["L"], v), comp_croisee(tst["L"], v)
        mC_c = candidats(sc_c, cal["P"])
        mC_t = candidats(sc_t, tst["P"])
        sv = pav_seuil(sc_c[mC_c], cal["Y"][mC_c])
        r: dict[str, Any] = {"seuil_compatibilite": sv["seuil"], "calibrage": sv}
        if sv["seuil"] is None:
            r["note"] = "aucune tranche de compatibilité n'atteint 70 % de réussite lissée sur 2025-26 : la règle n'a pas de seuil"
            out["variantes"][v] = r
            continue
        selC = mC_t & (sc_t >= sv["seuil"])
        V = int(selC.sum())
        r.update(paris=V, matchs_avec_pari=int(selC.any(axis=1).sum()), reussite=float(tst["Y"][selC].mean()) if V else None, p_moyenne=float(tst["P"][selC].mean()) if V else None)
        comparaisons = {}
        volumes = {"volume_compat": V, "volume_P_seuil": out["P_seul"].get("paris"), "demi_pari_par_match": int(round(0.5 * nm_t))}
        for nom, vol in volumes.items():
            if not vol:
                continue
            # compatibilité : les `vol` meilleurs (score décroissant, égalités par P) ; P seul : les `vol` plus probables — mêmes volumes, mêmes matchs
            def top(score, depart, masque):
                idx = np.argwhere(masque)
                ordre = np.lexsort((-depart[masque], -score[masque]))[:vol]
                return idx[ordre]
            iC, iP = top(sc_t, tst["P"], mC_t), top(tst["P"], tst["P"], mP_t)
            def agreg(ix):
                n = np.bincount(ix[:, 0], minlength=nm_t).astype(float)
                w = np.bincount(ix[:, 0], weights=tst["Y"][ix[:, 0], ix[:, 1]], minlength=nm_t)
                return n, w
            nA, wA = agreg(iC)
            nB, wB = agreg(iP)
            ecart, bas, haut, sd = bootstrap_ecart(nA, wA, nB, wB, rng)
            commun = len({tuple(x) for x in iC.tolist()} & {tuple(x) for x in iP.tolist()})
            comparaisons[nom] = {"paris": int(vol), "reussite_compat": float(wA.sum() / nA.sum()), "reussite_P": float(wB.sum() / nB.sum()), "ecart": ecart,
                                 "ic95": [bas, haut], "sd_bootstrap": sd, "mde": 1.96 * sd, "retenu": retenu(bas), "paris_communs": commun,
                                 "p_unilat": float(np.mean(np.array([0]) > 1))}
        r["comparaisons"] = comparaisons
        out["variantes"][v] = r
        if "volume_compat" in comparaisons:
            ps.append((v, comparaisons["volume_compat"]))
    # Holm sur la comparaison principale (3 variantes, volume de la règle de compatibilité) ; p unilatéral = part des tirages ≤ 0
    if ps:
        pv = []
        for v, c in ps:
            # p unilatéral approché depuis l'IC : écart/sd (normale), cohérent avec le bootstrap de la piste A
            from math import erf, sqrt
            z = c["ecart"] / c["sd_bootstrap"] if c["sd_bootstrap"] else 0.0
            pv.append(0.5 * (1 - erf(z / sqrt(2))))
        for (v, c), p_, ok in zip(ps, pv, holm(pv)):
            out["variantes"][v]["comparaisons"]["volume_compat"].update(p_unilat=p_, holm_retenu=ok)
    out["regression"] = regression(cal, tst, rng)
    out["regression_centree"] = regression(cal, tst, rng, centrer=True)
    out["_exemples"] = None
    return out


def rapport_md(o: dict[str, Any]) -> str:
    L = ["# Règle n°1 (compatibilité) — rapport d'évaluation", "",
         "> **Exploration sur archive/rejeu (Football-Data), PAS un bilan réel.** Aucun de ces paris n'a été gelé par le moteur avant le coup d'envoi. Le seul juge reste `bilan_reel.py`.",
         "> Cotes absentes du rejeu : le filtre « cote ≥ 1,26 » n'est PAS appliqué. Test de la compatibilité brute.", "",
         f"- Calibrage : **{o['matchs_calibrage']} matchs** de la saison 2025-26 ({o['periode_calibrage'][0]} → {o['periode_calibrage'][1]}).",
         f"- Test : **{o['matchs_test']} matchs** de la saison 2026-27 ({o['periode_test'][0]} → {o['periode_test'][1]}), séparation stricte. Période courte, échantillon modeste.", "",
         "## Sélection par P seul (référence, seuil appris sur 2025-26)", "", f"`{json.dumps({k: v for k, v in o['P_seul'].items()}, ensure_ascii=False)}`", "",
         "## Écart apparié compatibilité − P, à nombre de paris égal (IC 95 % par bootstrap sur les matchs)", "",
         "| Variante | Seuil appris | Volume | Réussite compat. | Réussite P | Écart | IC 95 % | MDE | Retenu | Holm | Paris communs |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v, r in o["variantes"].items():
        if r.get("seuil_compatibilite") is None:
            L.append(f"| {v} | aucun | — | — | — | — | — | — | — | — | — |")
            continue
        for nom, c in r["comparaisons"].items():
            L.append(f"| {v} ({nom}) | {r['seuil_compatibilite']:.2f} | {c['paris']} | {c['reussite_compat']:.1%} | {c['reussite_P']:.1%} | {c['ecart']:+.1%} | "
                     f"[{c['ic95'][0]:+.1%} ; {c['ic95'][1]:+.1%}] | {c['mde']:.1%} | {'oui' if c['retenu'] else 'non'} | {c.get('holm_retenu', '—')} | {c['paris_communs']} |")
    L += ["", "## La compatibilité ajoute-t-elle de l'information à P ? (logistique ajustée sur 2025-26, lue sur 2026-27, pool P ≥ 50 %, observations : " + str(o["regression"]["min"]["observations"]) + ")"]
    for titre, cle in (("brute (sans placebo : biaisée, voir ci-dessous)", "regression"), ("CENTRÉE par marché (lecture décisive, amendement post-hoc)", "regression_centree")):
        L += ["", f"### Régression {titre}", "", "| Variante | Coef. P | Coef. compat. (std) | Gain LL / observation | IC 95 % | MDE | Retenu |", "|---|---|---|---|---|---|---|"]
        for v, r in o[cle].items():
            L.append(f"| {v} | {r['coef_P']:.2f} | {r['coef_compat_std']:+.3f} | {r['gain_ll_par_obs']:+.5f} | [{r['ic95'][0]:+.5f} ; {r['ic95'][1]:+.5f}] | {r['mde']:.5f} | {'oui' if r['retenu'] else 'non'} |")
    return "\n".join(L) + "\n"


def main() -> None:
    o = evaluer(charger())
    (ROOT / "docs" / "dc_compatibilite_resultats.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    md = rapport_md(o)
    (ROOT / "docs" / "DC_COMPATIBILITE_RESULTATS.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
