"""Calibrage du moteur Omega V3 sur l'archive ARCHETYPE (`python -m moteur_omega_v3.calibrage`). Protocole de Patrick (30/10/2026) repris tel quel :

- échantillon = matchs JOUÉS de l'archive (`data/archive_test/`) dont les quatre séquences existent (≥ 5 matchs au même lieu, STRICTEMENT avant le jour du match) ;
- statistique de décision = la fréquence robuste g du marché (la plus basse fréquence brute quand on retire une observation à la fois) ;
- pour chaque marché : tranches de 5 points de g à partir de 50 %, réussite réelle par tranche, rendue croissante avec g (fusion des tranches voisines qui se contredisent) ;
- seuil du marché = début de la première tranche dont la réussite lissée atteint 70 % (cible de Patrick), avec au moins 30 prédictions au-dessus ; sinon aucun seuil, le marché n'est jamais retenu ;
- un remboursement n'est ni un gain ni une perte : il sort du décompte ;
- VALIDATION CHRONOLOGIQUE (§17) : seuils appris sur les 70 % de matchs les plus anciens, appliqués tels quels (code de production, cotes réelles) aux 30 % suivants ;
  Brier et log loss de la fréquence brute prise pour une probabilité, contre la réussite lissée apprise (§10 : une fréquence n'est pas une probabilité), table de calibration.
  Ce n'est PAS un bilan du moteur (règle de Patrick du 29/10/2026 : les bilans ne portent que sur les paris gelés avant le coup d'envoi et des matchs terminés).
- les seuils de production sont ensuite appris sur toute l'archive. Ils s'écrivent dans `parametres.json` ; le rapport complet dans `docs/omega_v3_validation.json`.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from . import coeur as C, donnees as D, marches as M

ROOT = Path(__file__).resolve().parent.parent
PARAMS = Path(__file__).with_name("parametres.json")
VALIDATION = ROOT / "docs" / "omega_v3_validation.json"
REUSSITE_CIBLE = 0.70          # Patrick, 30/10/2026
MIN_PARIS = 30                 # minimum de prédictions pour lire une réussite (règle du moteur DC, reprise)
PART_DEV = 0.70                # découpage chronologique : 70 % des matchs les plus anciens pour apprendre, le reste pour valider
PAS = C.PARAMS_DEFAUT["pas_tranche"]


def echantillon(log=print) -> tuple[list[dict[str, Any]], Counter]:
    """Pour chaque match joué de l'archive : séquences, fréquences robustes de tous les marchés, résultat de tous les marchés. Exclusions comptées par raison."""
    ligues = D.charger_ligues()
    out, exclus = [], Counter()
    for m in D.charger_archive(ligues):
        if m["h"] is None:
            continue
        liste = ligues.matchs.get(m["ligue"])
        if not liste:
            exclus["championnat sans match connu"] += 1
            continue
        try:
            s = D.sequences(liste, m["eq_dom"], m["eq_ext"], m["jour"])
        except ValueError as e:
            exclus[str(e).split(":")[0].split(" (")[0]] += 1
            continue
        a = C.analyser(s["att_a"], s["def_a"], s["att_b"], s["def_b"], cotes=m.get("cotes"))
        if not all(v["ok"] for v in a["verifications"]):
            exclus["contrôle mathématique échoué"] += 1
            continue
        res = M.vecteur(m["h"], m["a"])
        out.append({"m": m, "g": np.array([x["g"] for x in a["marches"]]), "f": np.array([x["f"] for x in a["marches"]]), "y": res, "sequences": s})
    log(f"  archive : {len(out)} matchs joués analysables ; exclus : {dict(exclus)}")
    return out, exclus


def _pav(n: list[int], k: list[float]) -> list[float]:
    """Réussite par tranche rendue croissante avec g (fusion des tranches voisines qui se contredisent, pondérée par n)."""
    blocs: list[list[float]] = []
    for ni, ki in zip(n, k):
        blocs.append([ni, ki, 1])
        while len(blocs) > 1 and blocs[-2][1] / blocs[-2][0] >= blocs[-1][1] / blocs[-1][0]:
            x = blocs.pop()
            blocs[-1] = [blocs[-1][0] + x[0], blocs[-1][1] + x[1], blocs[-1][2] + x[2]]
    out: list[float] = []
    for bl in blocs:
        out += [bl[1] / bl[0]] * int(bl[2])
    return out


def seuils(ech: list[dict[str, Any]]) -> dict[str, Any]:
    """Seuil et tranches de chaque marché sur l'échantillon donné."""
    G = np.array([x["g"] for x in ech])
    Y = np.array([x["y"] for x in ech])
    bornes = [round(0.5 + PAS * k, 2) for k in range(int(round(0.5 / PAS)))]
    out: dict[str, Any] = {}
    for i, c in enumerate(M.CLES):
        jouable = Y[:, i] != 2                                  # un remboursé n'est ni gagné ni perdu
        g, y = G[jouable, i], (Y[jouable, i] == 1).astype(float)
        tr = []
        for b in bornes:
            m = (g >= b - 1e-12) & ((g < b + PAS - 1e-12) if b < bornes[-1] else (g <= 1.0 + 1e-12))
            if m.sum():
                tr.append({"debut": b, "n": int(m.sum()), "gagnes": int(y[m].sum()), "reussite": round(float(y[m].mean()), 4)})
        lisse = _pav([t["n"] for t in tr], [t["gagnes"] for t in tr])
        seuil = None
        for t, r in zip(tr, lisse):
            t["reussite_lissee"] = round(r, 4)
            m = g >= t["debut"] - 1e-12
            if seuil is None and r >= REUSSITE_CIBLE and m.sum() >= MIN_PARIS:
                seuil = {"seuil": t["debut"], "reussite": round(float(y[m].mean()), 4), "n": int(m.sum())}
        out[M.cle_txt(c)] = {**(seuil or {"seuil": None}), "predictions": int(len(g)), "tranches": tr}
    return out


def calib_de(s: dict[str, Any], ech: list[dict[str, Any]]) -> dict[str, Any]:
    return {"seuils": {k: {"seuil": v["seuil"], "tranches": v["tranches"]} for k, v in s.items()}, "cote_min": C.PARAMS_DEFAUT["cote_min"],
            "echantillon": {"matchs": len(ech), "du": min(x["m"]["jour"] for x in ech), "au": max(x["m"]["jour"] for x in ech)}}


def _brier_logloss(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    q = np.clip(p, 1e-3, 1 - 1e-3)
    return float(np.mean((p - y) ** 2)), float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def validation(ech: list[dict[str, Any]], log=print) -> dict[str, Any]:
    ech = sorted(ech, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    k = int(len(ech) * PART_DEV)
    coupe = ech[k]["m"]["jour"]
    dev = [x for x in ech if x["m"]["jour"] < coupe]
    res = [x for x in ech if x["m"]["jour"] >= coupe]
    out: dict[str, Any] = {"coupe": coupe, "developpement": {"matchs": len(dev), "du": dev[0]["m"]["jour"], "au": dev[-1]["m"]["jour"]},
                           "reserve": {"matchs": len(res), "du": res[0]["m"]["jour"], "au": res[-1]["m"]["jour"]}}
    if len(dev) < 30 or not res:
        return {**out, "erreur": "échantillon trop petit pour une validation chronologique"}
    cal = calib_de(seuils(dev), dev)
    # --- probabilité : la fréquence brute prise pour une probabilité contre la réussite lissée apprise (pool de tous les marchés, matchs de réserve) ---
    def pool(L: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
        g = np.concatenate([x["g"] for x in L]); y = np.concatenate([x["y"] for x in L])
        j = y != 2                                             # remboursé : ni gagné ni perdu
        return g[j], (y[j] == 1).astype(float)
    def tranche(g: np.ndarray, b: float) -> np.ndarray:
        return (g >= b - 1e-12) & ((g < b + 0.1 - 1e-12) if b < 0.9 else (g <= 1 + 1e-12))
    gd, yd = pool(dev)
    gr, yr = pool(res)
    bornes = [round(0.1 * q, 1) for q in range(10)]
    pleines = [(b, int(tranche(gd, b).sum()), float(yd[tranche(gd, b)].sum())) for b in bornes if tranche(gd, b).any()]
    lis = dict(zip([b for b, _, _ in pleines], _pav([n for _, n, _ in pleines], [k for _, _, k in pleines])))
    def lisse(v: float) -> float:
        b = min(lis, key=lambda x: (abs(x - min(int(v * 10), 9) / 10), x))
        return lis[b]
    cal_p = np.array([lisse(v) for v in gr])
    br_raw, ll_raw = _brier_logloss(gr, yr)
    br_cal, ll_cal = _brier_logloss(cal_p, yr)
    table = []
    for b in bornes:
        t = tranche(gr, b)
        table.append({"tranche": f"{b:.1f}-{b + 0.1:.1f}", "n": int(t.sum()), "g_moyen": round(float(gr[t].mean()), 4) if t.any() else None, "reussite": round(float(yr[t].mean()), 4) if t.any() else None})
    out["probabilite"] = {"observations": int(len(gr)), "frequence_brute_prise_pour_probabilite": {"brier": round(br_raw, 4), "log_loss": round(ll_raw, 4)},
                          "reussite_lissee_apprise": {"brier": round(br_cal, 4), "log_loss": round(ll_cal, 4)}, "calibration_reserve": table}
    # --- sélection : le code de production, les seuils appris sur le développement, les vraies cotes, sur la réserve ---
    paris, principaux, matchs_avec = [], [], 0
    par_marche: dict[str, list[int]] = {}
    for x in res:
        s = x["sequences"]
        a = C.analyser(s["att_a"], s["def_a"], s["att_b"], s["def_b"], cotes=x["m"].get("cotes"), calib=cal)
        sel = C.selection(a)
        lignes = ([sel["principal"]] if sel["principal"] else []) + sel["autres"]
        matchs_avec += bool(lignes)
        for q, l in enumerate(lignes):
            r = M.resultat((l["cle"][0], l["cle"][1]), x["m"]["h"], x["m"]["a"])
            if r == 2:
                continue
            paris.append((r == 1, l["p_calibree"], l["cote"]))
            if q == 0:
                principaux.append(r == 1)
            par_marche.setdefault(M.cle_txt((l["cle"][0], l["cle"][1])), []).append(int(r == 1))
    def stat(L: list[bool]) -> dict[str, Any]:
        return {"paris": len(L), "reussite": round(sum(L) / len(L), 4) if L else None}
    out["selection_reserve"] = {"matchs_analyses": len(res), "matchs_avec_pari": matchs_avec, "tous_paris": {**stat([g for g, _, _ in paris]),
                                "annonce_moyenne": round(float(np.mean([p for _, p, _ in paris if p is not None])), 4) if paris else None,
                                "cote_moyenne": round(float(np.mean([c for _, _, c in paris])), 3) if paris else None},
                                "paris_principaux": stat(principaux), "par_marche": {k: {"paris": len(v), "reussite": round(sum(v) / len(v), 4)} for k, v in sorted(par_marche.items())}}
    log(f"  validation chronologique : développement {len(dev)} matchs → réserve {len(res)} matchs ; {out['selection_reserve']['tous_paris']}")
    return out


def tout(log=print) -> None:
    ech, exclus = echantillon(log)
    if len(ech) < 60:
        raise SystemExit(f"échantillon trop petit ({len(ech)} matchs) : calibrage refusé, rien n'est écrit")
    val = validation(ech, log)
    s = seuils(ech)
    cal = calib_de(s, ech)
    n_seuil = sum(1 for v in s.values() if v["seuil"] is not None)
    params = {"version": "omega-v3-1", "reglages": C.PARAMS_DEFAUT, "cote_min": cal["cote_min"], "echantillon": {**cal["echantillon"], "exclus": dict(exclus)},
              "seuils": {k: {"seuil": v["seuil"], "tranches": [{"debut": t["debut"], "n": t["n"], "reussite_lissee": t["reussite_lissee"]} for t in v["tranches"]]}
                         for k, v in s.items() if v["seuil"] is not None}}
    PARAMS.write_text(json.dumps(params, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    VALIDATION.write_text(json.dumps({"reussite_cible": REUSSITE_CIBLE, "min_predictions": MIN_PARIS, "echantillon": cal["echantillon"], "exclus": dict(exclus),
                                      "validation_chronologique": val, "seuils_par_marche": {k: {kk: v[kk] for kk in ("seuil", "reussite", "n", "predictions") if kk in v} for k, v in s.items()}},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  seuils : {n_seuil} marchés sur {len(s)} ont un seuil ({len(ech)} matchs)")


if __name__ == "__main__":
    tout()
