"""Solidité d'un pari (affichage, ordre de Patrick du 28/10/2026) : « les marchés les plus pertinents et robustes » d'un coup d'œil.

Croise, pour le MÊME TYPE DE MARCHÉ, deux lectures des derniers matchs au même lieu des deux équipes (séries gelées du match) :
- la FRÉQUENCE : part des matchs où le pari passait (moyenne des deux équipes) ;
- les ÉCARTS DE BUTS : distance moyenne au basculement du score (`indice.distance` : combien de buts à changer pour que le pari change d'issue),
  normalisée par l'écart-type propre à ce type de marché.
Régression logistique de la réussite réelle sur : un niveau de départ par type de marché + logit(fréquence) + écart normalisé.
Les poids sont APPRIS sur l'archive (tous les marchés des matchs joués, avec ou sans cote ; jamais fixés à la main) et écrits dans docs/omega_solidite.json
à chaque passage du pipeline. N'utilise NI la cote NI la probabilité du modèle : c'est la lecture des seuls derniers matchs.
Marché jamais vu à l'apprentissage : aucune solidité (rien n'est inventé). Ne touche ni à la sélection, ni au journal, ni aux pronostics gelés.
Usage : python -m moteur_omega.solidite  -> docs/omega_solidite.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from . import coeur, donnees as D, indice as IND, marches as M

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "omega_solidite.json"
PARAMS = Path(__file__).with_name("parametres.json")
MIN_OBS_MARCHE = 100     # en dessous, le niveau de départ d'un type de marché n'est pas jugeable : il n'a pas de solidité


def _logit(p: float) -> float:
    p = min(max(float(p), 0.02), 0.98)
    return math.log(p / (1 - p))


def cle_marche(cle: Any) -> str:
    return "|".join(cle)


def _lignes(matchs: list[dict[str, Any]], refs: D.References, params: dict[str, Any]) -> list[tuple[str, float, float, float, str]]:
    """(marché, fréquence, écart, réussite, jour) pour tous les marchés des matchs joués analysables."""
    out = []
    for m in matchs:
        if m.get("h") is None:
            continue
        a = coeur.analyser(m, refs, params, avec_stabilite=False)
        if a.get("statut") != "analyse":
            continue
        for l in a["marches"]:
            cle = tuple(l["cle"])
            ms = IND.mesures(cle, a["series"])
            t = M.test_du_marche(*cle)
            if ms is None or t is None:
                continue
            out.append((cle_marche(cle), ms["passe"], ms["ecart"], float(bool(t(m["h"], m["a"]))), m["jour"]))
    return out


def _ajuster_logistique(X: np.ndarray, y: np.ndarray, iterations: int = 60) -> np.ndarray:
    w = np.zeros(X.shape[1])
    for _ in range(iterations):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        poids = p * (1 - p) + 1e-9
        pas = np.linalg.solve((X * poids[:, None]).T @ X + 1e-6 * np.eye(X.shape[1]), X.T @ (y - p))
        w = w + pas
        if np.max(np.abs(pas)) < 1e-8:
            break
    return w


def _matrice(lignes: list[tuple], marches: list[str], sd: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    ix = {k: i for i, k in enumerate(marches)}
    X = np.zeros((len(lignes), len(marches) + 2))
    for r, (mk, f, e, _y, _j) in enumerate(lignes):
        X[r, ix[mk]] = 1.0
        X[r, -2] = _logit(f)
        X[r, -1] = e / sd[mk]
    return X, np.array([l[3] for l in lignes], float)


def ajuster_lignes(lignes: list[tuple]) -> dict[str, Any]:
    n_par = {}
    for l in lignes:
        n_par[l[0]] = n_par.get(l[0], 0) + 1
    marches = sorted(k for k, n in n_par.items() if n >= MIN_OBS_MARCHE)
    if len(lignes) < 1000 or not marches:
        raise ValueError(f"trop peu de marchés pour apprendre les poids ({len(lignes)})")
    lignes = [l for l in lignes if l[0] in marches]
    sd = {k: max(float(np.std([l[2] for l in lignes if l[0] == k])), 1e-6) for k in marches}
    X, y = _matrice(lignes, marches, sd)
    w = _ajuster_logistique(X, y)
    p = 1 / (1 + np.exp(-X @ w))
    return {"n_marches": int(len(y)), "marches": {k: {"niveau": round(float(w[i]), 4), "ecart_type_ecart": round(sd[k], 4), "n": n_par[k]} for i, k in enumerate(marches)},
            "poids_frequence": round(float(w[-2]), 4), "poids_ecart": round(float(w[-1]), 4), "brier": round(float(np.mean((p - y) ** 2)), 4)}


def ajuster(matchs: list[dict[str, Any]], refs: D.References, params: dict[str, Any]) -> dict[str, Any]:
    return ajuster_lignes(_lignes(matchs, refs, params))


def probabilite(poids: dict[str, Any], cle: Any, s: dict[str, list[int]]) -> float | None:
    """Solidité d'un pari (0 à 1) ; None si le type de marché n'a pas été appris ou si les séries manquent."""
    mk = poids.get("marches", {}).get(cle_marche(cle))
    if not mk:
        return None
    ms = IND.mesures(tuple(cle), s)
    if ms is None:
        return None
    z = mk["niveau"] + poids["poids_frequence"] * _logit(ms["passe"]) + poids["poids_ecart"] * ms["ecart"] / mk["ecart_type_ecart"]
    return 1 / (1 + math.exp(-z))


def charger(chemin: Path = SORTIE) -> dict[str, Any] | None:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return None


def ecrire(sortie: Path = SORTIE, matchs: list[dict[str, Any]] | None = None, refs: D.References | None = None) -> dict[str, Any]:
    if matchs is None:
        matchs, refs = D.charger_archive(avec_futurs=False)
    out = ajuster(matchs, refs, json.loads(PARAMS.read_text(encoding="utf-8")))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = ecrire()
    print(r["n_marches"], "marchés,", len(r["marches"]), "types, poids fréquence", r["poids_frequence"], "poids écart", r["poids_ecart"], "Brier", r["brier"])
